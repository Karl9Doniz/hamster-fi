### Notes on the progress

#### Major checks

1. Network manager

Current system uses NetworkManager.
For router implementation we will switch to systemd-networkd and disable NetworkManager before configuring AP/Station/Bridge profiles

2. WIFI hardware capability

Supported interfaces are:

* managed
* AP
* P2P-client
* P2P-GO

- Travel-router mode (Wi-Fi WAN + Wi-Fi AP) is supported
- Possible to design a wizard (!)
- Harware is compatible with project requirements

BCM4345/6 (brcmfmac) supports concurrent managed + AP interfaces on a single channel.
All AP+Station setups must use same band/channel as uplink.

3. AP interface creation test

Test passed, used this command:

```iw dev wlan0 interface add ap0 type __ap```

Result:

```ap0: UP, NO-CARRIER```

Meaning:

- Kernel + driver allow AP virtual interface

- Can design:
    - wlan0 = Station (WAN)
    - ap0 = Access point (LAN)


4. Regulatory domain

UA set - good. But, kernel log shows ```Firmware rejected country setting``` - firmware ignores kernel regulatory domain. So, hostapd must explicitly set country. 2.4 GHz is preferred for stability; 5 GHz DFS channels may be unreliable.

Practical decision (pre-setup):

- Default AP band: 2.4 GHz

- Wizard should not expose DFS complexity

5. Firmware & kernel status

Overall ok. Only problems with regulatory settings, but it is not critical. 

6. Decisions

- Disable NetworkManager
- Use systemd-networkd for all IP configuration
- hostapd for AP
- wpa_supplicant or iwd for Station
- dnsmasq for DHCP/DNS
- nftables for NAT/firewall
- AP + Station supported on same radio
- Single channel only
- 2.4 GHz preferred
- Wi-Fi bridge over Wi-Fi uplink cannot be true L2


#### Useful to note

```bash
admin@admin:~ $ iw dev
iw dev ap0 info
iw dev wlan0 info
phy#0
	Interface ap0
		ifindex 4
		wdev 0x3
		addr 2e:cf:67:f0:a8:82
		type managed
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 31.00 dBm
	Unnamed/non-netdev interface
		wdev 0x2
		addr 2e:cf:67:50:a8:82
		type P2P-device
		txpower 31.00 dBm
	Interface wlan0
		ifindex 3
		wdev 0x1
		addr 2c:cf:67:50:a8:82
		ssid House_5G
		type managed
		channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
		txpower 31.00 dBm
Interface ap0
	ifindex 4
	wdev 0x3
	addr 2e:cf:67:f0:a8:82
	type managed
	wiphy 0
	channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
	txpower 31.00 dBm
Interface wlan0
	ifindex 3
	wdev 0x1
	addr 2c:cf:67:50:a8:82
	ssid House_5G
	type managed
	wiphy 0
	channel 149 (5745 MHz), width: 80 MHz, center1: 5775 MHz
	txpower 31.00 dBm
admin@admin:~ $ 
```
