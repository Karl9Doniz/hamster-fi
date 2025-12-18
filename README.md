Below is a copy-paste README.md + an installer script that (1) installs hamsterfi-diag + hamsterfi-recover into /usr/local/bin, (2) creates the hamsterfi-web.service if it’s missing, (3) enables & starts it, and (4) optionally fixes the common “sudo: unable to resolve host hamsterfi” issue.

I’m assuming your repo path is something like /home/admin/Documents/hamster-fi (that matches what your service already used).  ￼

⸻

README.md (drop this into your repo root)

# Hamster-Fi 🐹📶 (Raspberry Pi 5 Wi-Fi Router for Humans)

A tiny “Wi-Fi for hamsters” router appliance for Raspberry Pi (5) with a **Quick Wizard** and **Advanced** settings.

## Features

### Modes / Profiles
1) **AP Router (Ethernet WAN → Wi-Fi LAN)**  
   - Pi creates Wi-Fi AP (SSID/PSK you set)
   - LAN subnet: `192.168.50.0/24`
   - Pi runs DHCP/DNS (dnsmasq)
   - NAT + minimal firewall (nftables)

2) **AP Router (Wi-Fi WAN → Wi-Fi LAN)**  
   - Pi joins upstream Wi-Fi (SSID/PSK you enter)
   - Pi creates AP simultaneously (single-radio: AP channel is aligned to upstream)
   - LAN subnet: `192.168.50.0/24`
   - Pi runs DHCP/DNS + NAT

3) **Station Router (Wi-Fi WAN → Ethernet LAN)** *(Use-case 2)*  
   - Pi joins dorm Wi-Fi
   - Laptop connects by Ethernet and gets `192.168.50.x`
   - NAT on Pi
   - UI reachable at `http://192.168.50.1:8080`

4) **Bridge AP (Ethernet uplink, no NAT)** *(Use-case 3)*  
   - Pi behaves like a simple AP bridged to Ethernet
   - Main router does DHCP
   - **No DHCP server on Pi**
   - Pi gets a **management IP via DHCP on `br0`**, so the UI is reachable on the main LAN
   - Note: bridging Wi-Fi station ↔ Wi-Fi AP is not reliable on Raspberry Pi without special 4addr/WDS, so Bridge assumes **Ethernet uplink**

---

## Quick Start (Debian/RPi OS)

### Install runtime deps
```bash
sudo apt update
sudo apt install -y hostapd dnsmasq nftables iw wpasupplicant iproute2 python3 python3-venv avahi-daemon
sudo systemctl enable --now avahi-daemon

Clone + venv

cd /home/admin/Documents
git clone <YOUR_GIT_URL> hamster-fi
cd hamster-fi
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

Install systemd service + tools (recommended)

From repo root:

sudo ./scripts/install-hamsterfi.sh

This installs:
	•	/etc/systemd/system/hamsterfi-web.service
	•	/usr/local/bin/hamsterfi-diag (quick diagnostics)
	•	/usr/local/bin/hamsterfi-recover (known-good fallback AP router mode)
	•	/usr/local/bin/hamsterfi-ip (prints the URLs you can try for the UI)

hamsterfi-diag prints interfaces/routes/services/rules and recent logs.  ￼
hamsterfi-recover backs up current configs, then restores a known-good AP router mode (SSID + DHCP + NAT) and starts the UI.  ￼  ￼

⸻

How to reach the UI

In Router modes (AP Router / Station Router)
	•	UI is always: http://192.168.50.1:8080

In Bridge AP mode
	•	UI is on the main LAN IP you got from DHCP on br0
	•	Run:

hamsterfi-ip

It prints all “best guess” URLs.

Also useful:

hostname -I
ip -br a
ip route

Optional mDNS (hamsterfi.local)

If your LAN allows mDNS, and Avahi is running, try:
	•	http://hamsterfi.local:8080

If you see sudo: unable to resolve host hamsterfi, your hostname is missing from /etc/hosts.
Fix:

echo "127.0.1.1 hamsterfi" | sudo tee -a /etc/hosts


⸻

Test Plan (3 use-cases)

Use-case 1 — AP Router (Ethernet WAN → Wi-Fi LAN)

I want: Pi provides Wi-Fi for my phone, internet comes from Ethernet.

Steps:
	1.	Plug Pi eth0 into main router LAN
	2.	Wizard → AP Router, WAN = eth0, WAN IPv4 = DHCP
	3.	Set SSID/PSK → Apply
	4.	Connect phone to the new SSID

Expected:
	•	Phone receives 192.168.50.x from Pi
	•	Phone has internet
	•	UI reachable at http://192.168.50.1:8080

Verify:
	•	On phone: IP in 192.168.50.0/24
	•	On Pi:

hamsterfi-diag
ip route get 1.1.1.1



Use-case 2 — Station Router (Wi-Fi WAN → Ethernet LAN)

I want: Pi joins dorm Wi-Fi, my laptop uses Pi via Ethernet.

Steps:
	1.	Plug laptop into Pi eth0
	2.	Wizard → Station Router
	3.	Enter upstream Wi-Fi SSID + password → Apply

Expected:
	•	Laptop gets 192.168.50.x from Pi DHCP
	•	Laptop internet works (NAT via Pi)
	•	UI reachable at http://192.168.50.1:8080

Verify (laptop):
	•	ipconfig getifaddr enX (macOS) or ip a (Linux) shows 192.168.50.x
	•	curl -I https://1.1.1.1

Verify (Pi):

hamsterfi-diag
iw dev wlan0 link
ip route get 1.1.1.1

Use-case 3 — Bridge AP (Ethernet uplink, no NAT)

I want: Pi behaves like a simple AP, main router handles DHCP.

Steps:
	1.	Connect Pi eth0 into main router LAN
	2.	Wizard → Bridge AP
	3.	Set SSID/PSK → Apply
	4.	Connect phone to SSID

Expected:
	•	Phone gets IP from main router (same subnet as other devices)
	•	No NAT
	•	Pi does not run DHCP

Verify:
	•	Phone IP is in main LAN subnet (not 192.168.50.x)
	•	On Pi:

systemctl is-active dnsmasq   # should be inactive
ip -br a
bridge link
hamsterfi-ip



⸻

Testing Static WAN IPv4

Static WAN means: “Pi itself uses a fixed IP on the upstream network”.

AP Router, WAN=eth0 (static)

Pick an unused IP in your main LAN, for example:
	•	address: 192.168.110.250/24
	•	gateway: 192.168.110.1  (your main router)
	•	DNS: 1.1.1.1, 8.8.8.8

Apply, then verify:

ip -br a show eth0
ip route
ip route get 1.1.1.1

AP Router, WAN=wlan0 (static)

Same idea, but the fixed IP is on the Wi-Fi upstream network.
Use the dorm/router’s subnet + its gateway as provided by your network admin (or infer from DHCP first).

Practical method:
	1.	First connect with DHCP and read:

ip -4 addr show wlan0
ip -4 route show default

	2.	Then choose an unused address in that subnet, keep the same gateway.

Bridge AP (static management IP)

You usually do DHCP on br0 so you can always find it in the main router leases.
If you really want static management, you can do br0 static in your dhcpcd config — but DHCP is easier for demos.

⸻

Recovery (when you break Wi-Fi)

If you lose access:
	1.	Connect via HDMI/keyboard or known working access path
	2.	Run:

sudo hamsterfi-recover

This restores a known-good AP router mode (192.168.50.1/24, DHCP range 50-200, NAT, hostapd SSID).  ￼

⸻

Useful Commands

sudo hamsterfi-recover
hamsterfi-diag
hamsterfi-ip
sudo systemctl restart hamsterfi-web
journalctl -u hamsterfi-web -n 200 --no-pager

