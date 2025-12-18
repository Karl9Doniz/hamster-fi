# Test plan (user-perspective)

## Use-case 1 — AP Router (Ethernet WAN)

**I want:** plug Pi into home ethernet, connect phone to Hamster Wi-Fi, have internet.

Steps:
1. Connect Pi eth0 to router/switch with internet
2. Open web UI: `http://<pi-ip>:8080` (before Apply)
3. Quick Wizard → AP Router
4. WAN: Ethernet, DHCP
5. Set SSID/PSK → Apply
6. Connect phone to SSID

Expected:
- Phone gets `192.168.50.x`
- Default gateway is `192.168.50.1`
- Internet works
- Web UI reachable at `http://192.168.50.1:8080`

Notes:
- This is the most stable/typical setup for Pi (separate radios: Wi-Fi for LAN, Ethernet for WAN).

## Use-case 1b — AP Router (Wi-Fi WAN)

**I want:** Pi creates Hamster Wi-Fi, but internet is taken from an upstream Wi-Fi network (no Ethernet needed).

Steps:
1. Open web UI (e.g., from your current LAN / SSH tunnel)
2. Quick Wizard → AP Router
3. WAN: Wi-Fi (wlan0)
4. Enter upstream Wi-Fi SSID + password
5. Set Hamster SSID/PSK → Apply
6. Connect phone to Hamster SSID

Expected:
- Phone gets `192.168.50.x`
- Default gateway is `192.168.50.1`
- Internet works (NAT via wlan0)

Notes:
- This uses one physical radio with two interfaces (wlan0 station + ap0 AP). If your regulatory domain/channel settings are unusual, AP may take longer to reappear after Apply.

## Use-case 2 — Station Router (Wi-Fi WAN → Ethernet LAN)

**I want:** Pi joins dorm Wi-Fi, my laptop uses Pi via ethernet.

Steps:
1. Plug laptop into Pi ethernet
2. Quick Wizard → Station Router
3. Enter upstream Wi-Fi SSID + password
4. Apply

Expected:
- Laptop gets `192.168.50.x` from Pi DHCP
- Laptop internet works (NAT via Pi)
- UI reachable at `http://192.168.50.1:8080`

Notes:
- Useful when you only have Wi-Fi internet available and want to share it over Ethernet.

## Use-case 3 — Bridge AP (Ethernet uplink, no NAT)

**I want:** Pi behaves like a simple AP, main router handles DHCP.

Steps:
1. Connect Pi eth0 into main router LAN
2. Wizard → Bridge AP
3. Set SSID/PSK → Apply
4. Connect phone to SSID

Expected:
- Phone gets IP from main router (same subnet as other devices)
- No NAT (devices are in the same LAN)
- Pi does not run DHCP

Notes:
- In bridge mode, the Pi tries to get a management IP on `br0` via DHCP, so the UI is reachable on the main LAN.
- Bridging Wi-Fi WAN (station) to Wi-Fi LAN (AP) is not reliably supported on Raspberry Pi without special 4addr/WDS support, so this profile assumes Ethernet uplink.

---

### Bonus sanity checks (optional but recommended)

- On the Pi, run:
  - `ip -br addr` (interfaces up, expected IPs)
  - `ip -4 route` (only one default route on the chosen WAN)
  - `sudo nft list ruleset` (in router modes: forward+masquerade present)
  - `sudo ss -lunp | egrep ':(53|67)\b'` (dnsmasq is listening in router modes)
