# Access Point (AP) Mode with DHCP on Raspberry Pi

### Goal

The goal of this intermediate stage was to validate that the Raspberry Pi can operate as a Wi-Fi Access Point (AP) and provide:

- a visible Wi-Fi network (SSID),

- automatic IP address assignment to clients (DHCP),

- stable Layer-2/Layer-3 connectivity on the LAN side,

Without yet configuring routing, NAT, or advanced modes. This stage serves as the foundation for later Station and Bridge modes.


### ap0 interface creation

Using a separate virtual interface allows:

- wlan0 to remain a Wi-Fi client (WAN later),

- ap0 to serve as the LAN Access Point.

This separation is required for clean routing and later profile-based configuration.

```bash
sudo iw dev wlan0 interface add ap0 type __ap
sudo ip link set ap0 up
```

We created a dedicated systemd unit so the AP interface survives reboots:

```bash
[Unit]
Description=Create Wi-Fi AP interface ap0
After=network-pre.target
Before=hostapd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/iw dev wlan0 interface add ap0 type __ap
ExecStart=/sbin/ip link set ap0 up
ExecStop=/usr/sbin/iw dev ap0 del

[Install]
WantedBy=multi-user.target
```

### LAN addressing

Assign a fixed gateway IP to the AP interface.

```bash
sudo ip addr add 192.168.50.1/24 dev ap0
sudo ip link set ap0 up
```

**Result:**

```bash
inet 192.168.50.1/24 scope global ap0
```

This address later becomes:

- Default gateway for clients

- DHCP router option

- DNS forwarder address


### DHCP & DNS (dnsmasq)

**Initial issue:**

dnsmasq was already running (used by NetworkManager) but not serving DHCP.

**Resolution:**

We added a separate interface-specific configuration file to avoid conflicts.

```/etc/dnsmasq.d/ap0-lan.conf```

```bash
interface=ap0
bind-interfaces

dhcp-range=192.168.50.50,192.168.50.200,255.255.255.0,12h
dhcp-option=option:router,192.168.50.1
dhcp-option=option:dns-server,192.168.50.1

server=1.1.1.1
server=8.8.8.8

domain-needed
bogus-priv
```

**Verified with:**

```bash
sudo dnsmasq --test
sudo systemctl restart dnsmasq
sudo ss -lunp | grep ':67'
```

**Result:**

```bash
DHCP, IP range 192.168.50.50 -- 192.168.50.200
DHCP, sockets bound exclusively to interface ap0
```


### Wi-Fi Access Point (hostapd)

Kernel logs previously showed:

```Firmware rejected country setting```

**Fix:**

- Explicitly set country_code=UA in hostapd

- Avoid auto channel selection

- Use a known-good channel (149) matching the uplink


hostapd configuration (```/etc/hostapd/hostapd.conf```):

```bash
interface=ap0
driver=nl80211

ssid=PiHamsterNet
hw_mode=a
channel=149

country_code=UA
ieee80211d=1
ieee80211n=1
ieee80211ac=1
wmm_enabled=1

auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase=********
```

### Successful AP Activation

**Service status:**

```bash
sudo systemctl restart hostapd
sudo systemctl status hostapd
```

**Result:**

```bash
ap0: AP-ENABLED
Active: running
```

**Interface verification:**

```bash
iw dev ap0 info
```

Confirmed:

- SSID: PiHamsterNet

- Mode: AP

- Channel: 149


### Client Connection Verification

**DHCP lease confirmation:**

```bash
sudo cat /var/lib/misc/dnsmasq.leases
```

Result:

```192.168.50.99  iPhone```

**Neighbor table:**

```bash
ip neigh show dev ap0
```

**Result:**

```192.168.50.99 lladdr a6:7f:a7:df:d6:41```


### Known Limitations at This Stage

- No NAT or routing yet (LAN only)

- NetworkManager still controls wlan0

- AP + Station limited to same channel

- No firewall rules applied yet

### Status Summary

- AP interface created and persistent
- Wi-Fi SSID visible and connectable
- DHCP working correctly
- Client successfully assigned IP

By separating the Wi-Fi radio into a managed interface for WAN (wlan0) and a virtual AP interface for LAN (ap0), assigning a private subnet to the AP, and providing DHCP services, the Raspberry Pi is transformed into a functional Wi-Fi router capable of sharing an existing wireless connection.
