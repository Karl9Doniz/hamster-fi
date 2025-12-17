# Enabling routing (NAT + firewall)

**What we already have (confirmed):**

- LAN: ap0 --> 192.168.50.0/24

- Gateway: 192.168.50.1

- Clients: get DHCP (iPhone = 192.168.50.99)

- WAN: wlan0 (connected to upstream Wi-Fi)

- AP: working

**Right now:**

Packets stop at the Pi. We will allow them to pass through safely.

### Enable IP forwarding (temporary, to check)

```sudo sysctl net.ipv4.ip_forward```

Got:

```net.ipv4.ip_forward = 0```

Now will enable it:

```sudo sysctl -w net.ipv4.ip_forward=1```

Verify:

```sudo sysctl net.ipv4.ip_forward```

Got, as expected:

```net.ipv4.ip_forward = 1```

### NAT

- LAN clients use private IPs

- Upstream Wi-Fi sees only the Pi

- Pi rewrites source addresses on egress

Now we identify interfaces and conform using ```ip route```:

```bash
admin@admin:~ $ ip route
default via 192.168.110.1 dev wlan0 proto dhcp src 192.168.110.209 metric 600 
192.168.50.0/24 dev ap0 proto kernel scope link src 192.168.50.1 
192.168.110.0/24 dev wlan0 proto kernel scope link src 192.168.110.209 metric 600 
admin@admin:~ $ 
```

Confirmed default for wlan0 and 192.168.50.0 via ap0.

#### Create NAT

Will use **nftables** here.

Created ```/etc/nftables.conf```:

```bash
flush ruleset

define LAN_IF = "ap0"
define WAN_IF = "wlan0"

table ip nat {
  chain postrouting {
    type nat hook postrouting priority 100;
    oifname $WAN_IF masquerade
  }
}
```

Applied rules:

```bash
sudo nft -f /etc/nftables.conf
```

Checked with ```sudo nft list ruleset```, got:

```bash
admin@admin:~ $ sudo nft list ruleset
table ip nat {
	chain postrouting {
		type nat hook postrouting priority srcnat; policy accept;
		oifname "wlan0" masquerade
	}
}
```

See the postrouting ... oifname "wlan0" masquerade - exactly what is expected.

#### NAT test (no Firewall yet)

Through connecting Phone to the network we checked that NAT actually works (the webiste opens on phone), which is already a good proof, but also can be reliably checked with conntrack:

```bash
admin@admin:~ $ sudo conntrack -L | head
udp      17 5 src=192.168.110.209 dst=192.168.110.1 sport=46195 dport=53 src=192.168.110.1 dst=192.168.110.209 sport=53 dport=46195 mark=0 use=1
tcp      6 431975 ESTABLISHED src=192.168.110.209 dst=142.250.130.95 sport=39086 dport=443 src=142.250.130.95 dst=192.168.110.209 sport=443 dport=39086 [ASSURED] mark=0 use=1
tcp      6 431998 ESTABLISHED src=192.168.110.209 dst=172.64.148.235 sport=47590 dport=443 src=172.64.148.235 dst=192.168.110.209 sport=443 dport=47590 [ASSURED] mark=0 use=1
udp      17 4 src=192.168.110.209 dst=192.168.110.1 sport=59507 dport=53 src=192.168.110.1 dst=192.168.110.209 sport=53 dport=59507 mark=0 use=1
tcp      6 115 TIME_WAIT src=192.168.110.209 dst=20.103.36.96 sport=40700 dport=443 src=20.103.36.96 dst=192.168.110.209 sport=443 dport=40700 [ASSURED] mark=0 use=1
unknown  2 529 src=192.168.110.221 dst=224.0.0.251 [UNREPLIED] src=224.0.0.251 dst=192.168.110.221 mark=0 use=1
udp      17 5 src=192.168.110.209 dst=142.250.130.95 sport=33546 dport=443 src=142.250.130.95 dst=192.168.110.209 sport=443 dport=33546 mark=0 use=1
tcp      6 431994 ESTABLISHED src=192.168.110.209 dst=140.82.114.25 sport=51008 dport=443 src=140.82.114.25 dst=192.168.110.209 sport=443 dport=51008 [ASSURED] mark=0 use=1
tcp      6 83 TIME_WAIT src=192.168.110.209 dst=172.64.155.209 sport=33882 dport=443 src=172.64.155.209 dst=192.168.110.209 sport=443 dport=33882 [ASSURED] mark=0 use=1
tcp      6 431947 ESTABLISHED src=192.168.50.99 dst=17.57.146.26 sport=55428 dport=5223 src=17.57.146.26 dst=192.168.110.209 sport=5223 dport=55428 [ASSURED] mark=0 use=1
conntrack v1.4.8 (conntrack-tools): 39 flow entries have been shown.
```

The most important lines here are:

```bash
tcp 6 ESTABLISHED 
src=192.168.50.99 dst=17.57.146.26 sport=55428 dport=5223
src=17.57.146.26 dst=192.168.110.209 sport=5223 dport=55428
```

- 192.168.50.99 --> an iPhone (LAN client)

- 192.168.110.209 --> Raspberry Pi’s WAN address on wlan0

- 17.57.146.26 --> external Apple server

**Now there is kernel-level evidence that:**

1. LAN and WAN are separated

    - Private subnet 192.168.50.0/24

    - WAN subnet 192.168.110.0/24

2. IP forwarding is active

    - Packets traverse ap0 --> wlan0

3. NAT is functioning

- Source IP rewritten from LAN --> WAN

- Reverse mapping tracked correctly

### Minimal firewall

We need to allow LAN --> WAN traffic, but block unsolicited inbound traffic.

We need to replace NAT rules with updated filters:

```bash
flush ruleset

define LAN_IF = "ap0"
define WAN_IF = "wlan0"


table inet filter {
  chain input {
    type filter hook input priority 0;
    policy drop;

    iif "lo" accept

    ct state established,related accept

    iifname $LAN_IF udp dport {67, 53} accept
    iifname $LAN_IF tcp dport 53 accept

    ip protocol icmp accept

    iifname $LAN_IF tcp dport 22 accept
  }

  chain forward {
    type filter hook forward priority 0;
    policy drop;

    ct state established,related accept

    iifname $LAN_IF oifname $WAN_IF accept
  }
}

table ip nat {
  chain postrouting {
    type nat hook postrouting priority srcnat;
    oifname $WAN_IF masquerade
  }
}
```

And we apply them immediately.

We again verify firewall behavior:

```bash
admin@admin:~ $ sudo nft list ruleset
table inet filter {
	chain input {
		type filter hook input priority filter; policy drop;
		iif "lo" accept
		ct state established,related accept
		iifname "ap0" udp dport { 53, 67 } accept
		iifname "ap0" tcp dport 53 accept
		ip protocol icmp accept
		iifname "ap0" tcp dport 22 accept
	}

	chain forward {
		type filter hook forward priority filter; policy drop;
		ct state established,related accept
		iifname "ap0" oifname "wlan0" accept
	}
}
table ip nat {
	chain postrouting {
		type nat hook postrouting priority srcnat; policy accept;
		oifname "wlan0" masquerade
	}
}
```

Checking functionality from the phone and with simple ping prove that minimal firewall setup is complete:

```bash
admin@admin:~/Documents/hamster-fi $ ping -c 2 1.1.1.1
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=56 time=14.2 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=56 time=10.5 ms

--- 1.1.1.1 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 10.517/12.359/14.201/1.842 ms
```

### Adding Persistence

Created sysctl config:

```echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-router.conf```

Applied, verified with ```sudo sysctl --system | grep ip_forward```, got:

```net.ipv4.ip_forward = 1```.

That is exactly what is expected.

Now need to enable nftables at boot:

```bash
sudo systemctl enable nftables
sudo systemctl restart nftables
```

Verified:

```bash
admin@admin:~/Documents/hamster-fi $ systemctl is-enabled nftables
enabled
```

After reboot, Pi's wifi network is accessible again.


