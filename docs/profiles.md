# Profile-Based Networking Architecture

**Recorded state:**

```bash
admin@admin:~ $ ip -br link
ip -br addr
ip route
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 
eth0             UP             2c:cf:67:50:a8:7f <BROADCAST,MULTICAST,UP,LOWER_UP> 
wlan0            UP             2c:cf:67:50:a8:82 <BROADCAST,MULTICAST,UP,LOWER_UP> 
ap0              UP             2e:cf:67:f0:a8:82 <BROADCAST,MULTICAST,UP,LOWER_UP> 
lo               UNKNOWN        127.0.0.1/8 ::1/128 
eth0             UP             192.168.110.206/24 fe80::3e2f:1d8f:55f0:f3b7/64 
wlan0            UP             192.168.110.209/24 fe80::d720:2531:2124:9cbf/64 
ap0              UP             192.168.50.1/24 fe80::2ccf:67ff:fef0:a882/64 
default via 192.168.110.1 dev eth0 proto dhcp src 192.168.110.206 metric 100 
default via 192.168.110.1 dev wlan0 proto dhcp src 192.168.110.209 metric 600 
192.168.50.0/24 dev ap0 proto kernel scope link src 192.168.50.1 
192.168.110.0/24 dev eth0 proto kernel scope link src 192.168.110.206 metric 100 
192.168.110.0/24 dev wlan0 proto kernel scope link src 192.168.110.209 metric 600 
admin@admin:~ $ iw dev
iw dev wlan0 link
iw dev ap0 info
phy#0
	Unnamed/non-netdev interface
		wdev 0x3
		addr 2e:cf:67:50:a8:82
		type P2P-device
		txpower 31.00 dBm
	Interface ap0
		ifindex 4
		wdev 0x2
		addr 2e:cf:67:f0:a8:82
		ssid PiHamsterNet
		type AP
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 31.00 dBm
	Interface wlan0
		ifindex 3
		wdev 0x1
		addr 2c:cf:67:50:a8:82
		ssid House_5G
		type managed
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 31.00 dBm
Connected to c6:b2:5b:93:d1:ec (on wlan0)
	SSID: House_5G
	freq: 5745.0
	RX: 334644 bytes (1996 packets)
	TX: 8915 bytes (66 packets)
	signal: -48 dBm
	rx bitrate: 351.0 MBit/s
	tx bitrate: 24.0 MBit/s
	bss flags: 
	dtim period: 1
	beacon int: 100
Interface ap0
	ifindex 4
	wdev 0x2
	addr 2e:cf:67:f0:a8:82
	ssid PiHamsterNet
	type AP
	wiphy 0
	channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
	txpower 31.00 dBm
admin@admin:~ $ 

admin@admin:~ $ systemctl is-active hostapd
systemctl is-active dnsmasq
systemctl is-active nftables
systemctl is-active NetworkManager
active
active
active
active
admin@admin:~ $ 
```

## 1. Define Profile #1 (AP Router, Wi-Fi WAN)

Created profile file:

```sudo nano /etc/hamster-fi/profiles/ap-wifi-wan.yaml```

```bash
name: ap-wifi-wan
description: Wi-Fi WAN routed to local AP with NAT

wan:
  interface: wlan0
  type: wifi
  addressing: dhcp

lan:
  interface: ap0
  type: ap
  subnet: 192.168.50.0/24
  gateway: 192.168.50.1
  dhcp: enabled

wifi_ap:
  ssid: PiHamsterNet
  band: 2.4ghz
  channel: 6
  security: wpa2
  passphrase: ********

services:
  hostapd: true
  dnsmasq: true
  nftables: true

nat: enabled
firewall: enabled
```

Marked active

```echo "ap-wifi-wan" | sudo tee /etc/hamster-fi/runtime/active-profile```

Now we have named router.


## 2. First Profile Apply Script

Now we introduce the profile application skeleton, but without switching network managers yet.

```sudo nano /usr/local/sbin/hamster-fi-apply```

```bash
#!/bin/bash
set -e

PROFILE="$1"

if [ -z "$PROFILE" ]; then
  echo "Usage: hamster-fi-apply <profile>"
  exit 1
fi

PROFILE_FILE="/etc/hamster-fi/profiles/$PROFILE.yaml"

if [ ! -f "$PROFILE_FILE" ]; then
  echo "Profile not found: $PROFILE_FILE"
  exit 1
fi

echo "[+] Applying profile: $PROFILE"
echo "[+] Profile file: $PROFILE_FILE"

echo "[*] Stopping services"
systemctl stop hostapd dnsmasq || true

# --- WAN enforcement for ap-wifi-wan ---
if [ "$PROFILE" = "ap-wifi-wan" ]; then
  echo "[*] Enforcing WAN=wlan0 (bringing eth0 down to avoid default-route conflict)"
  ip link set eth0 down || true
fi


echo "[*] Applying firewall"
nft -f /etc/nftables.conf

echo "[*] Starting services"
systemctl start dnsmasq
systemctl start hostapd

echo "[+] Profile applied"
```
```sudo chmod +x /usr/local/sbin/hamster-fi-apply```

Applied after that.

Internet connection from WIFI confirmed!

We’ll make the script self-validating now:

Added this to ```hamster-fi-apply```:

```bash
echo "[*] Verifying routing state"
ip route | grep '^default' || { echo "ERROR: no default route"; exit 1; }

echo "[*] Verifying NAT presence"
nft list ruleset | grep -q masquerade || { echo "ERROR: NAT not active"; exit 1; }

echo "[+] Profile $PROFILE applied successfully"
```





