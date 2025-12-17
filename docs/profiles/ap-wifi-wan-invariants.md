## ap-wifi-wan Profile Invariants

- wlan0 is the only active uplink
- eth0 must be administratively DOWN
- default route must resolve via wlan0
- NAT and forward rules only reference wlan0
- AP + Station share a single channel
