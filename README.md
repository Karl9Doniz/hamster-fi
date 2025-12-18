# Hamster-Fi 🐹📶
**Raspberry Pi 5 Wi-Fi router for humans** — quick wizard + advanced mode, with ready-to-apply network profiles.

Hamster-Fi turns your Pi into:
- a normal home router/AP (**NAT + DHCP**),
- a **station router** (Wi-Fi WAN -> Ethernet LAN),
- or a simple **bridged AP** (**no NAT**, main router does DHCP).

---

## Features

### Modes / Profiles

#### 1) AP Router — Ethernet WAN -> Wi-Fi LAN
- Creates Wi-Fi AP (SSID/PSK you set)
- Downstream LAN: `192.168.50.0/24`
- Pi runs **DHCP + DNS** via `dnsmasq`
- Internet via **NAT + minimal firewall** (`nftables`)

#### 2) AP Router — Wi-Fi WAN -> Wi-Fi LAN
- Pi connects to upstream Wi-Fi (SSID/PSK you provide)
- Pi also creates AP (single-radio: AP channel aligns to upstream)
- Downstream LAN: `192.168.50.0/24`
- `dnsmasq` + NAT + firewall

#### 3) Station Router — Wi-Fi WAN -> Ethernet LAN (Use-case 2)
- Pi joins dorm Wi-Fi as WAN (`wlan0`)
- Laptop connects to Pi via Ethernet (`eth0`)
- Laptop gets `192.168.50.x` from Pi DHCP
- Internet works via NAT through Pi
- UI: `http://192.168.50.1:8080`

#### 4) Bridge AP — Ethernet uplink, no NAT (Use-case 3)
- Pi is a simple AP bridged to Ethernet
- **Main router provides DHCP** (Pi does **not** run DHCP)
- Bridge interface: `br0`
- Pi gets a **management IP via DHCP on `br0`** so UI is reachable on the main LAN
- Note: Wi-Fi station <-> Wi-Fi AP bridging is not reliable on Raspberry Pi without special 4addr/WDS,
  so this profile assumes **Ethernet uplink**.

---

## Requirements
- Raspberry Pi 5
- Debian / Raspberry Pi OS (systemd)
- Working Wi-Fi firmware/driver for `wlan0`

---

## Quick Start (on the Pi)

### 1) Install runtime dependencies
```bash
sudo apt update
sudo apt install -y   hostapd dnsmasq nftables iw wpasupplicant iproute2   python3 python3-venv avahi-daemon

sudo systemctl enable --now avahi-daemon
```

### 2) Clone + create venv
```bash
cd /home/admin/Documents
git clone <YOUR_GIT_URL> hamster-fi
cd hamster-fi

python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 3) Install systemd service + helper tools
From repo root:
```bash
sudo ./scripts/install-hamsterfi.sh
```

This installs:
- `/etc/systemd/system/hamsterfi-web.service`
- `/usr/local/bin/hamsterfi-diag` — quick diagnostics
- `/usr/local/bin/hamsterfi-recover` — known-good recovery (AP router)
- `/usr/local/bin/hamsterfi-ip` — prints the best URLs to open the UI

---

## How to reach the UI

### Router modes (AP Router / Station Router)
UI is always:
- `http://192.168.50.1:8080`

### Bridge AP mode
UI uses whatever DHCP gave to `br0` on your main LAN:
```bash
hamsterfi-ip
```

Useful low-level commands:
```bash
hostname -I
ip -br a
ip route
```

### Optional: mDNS (hamsterfi.local)
If your LAN allows mDNS and Avahi is running:
- `http://hamsterfi.local:8080`

If you see:
> `sudo: unable to resolve host hamsterfi`

Fix `/etc/hosts` once:
```bash
echo "127.0.1.1 hamsterfi" | sudo tee -a /etc/hosts
```

---

## Test Plan (3 use-cases)

### Use-case 1 — AP Router (Ethernet WAN -> Wi-Fi LAN)
**I want:** Pi provides Wi-Fi for my phone, internet comes from Ethernet.

**Steps**
1. Plug Pi `eth0` into main router LAN
2. Wizard -> **AP Router**, WAN = **eth0**, WAN IPv4 = **DHCP**
3. Set SSID/PSK -> Apply
4. Connect phone to the new SSID

**Expected**
- Phone receives `192.168.50.x` from Pi
- Phone has internet
- UI: `http://192.168.50.1:8080`

**Verify (Pi)**
```bash
hamsterfi-diag
ip route get 1.1.1.1
```

---

### Use-case 2 — Station Router (Wi-Fi WAN -> Ethernet LAN)
**I want:** Pi joins dorm Wi-Fi, my laptop uses Pi via Ethernet.

**Steps**
1. Plug laptop into Pi `eth0`
2. Wizard -> **Station Router**
3. Enter upstream Wi-Fi SSID + password -> Apply

**Expected**
- Laptop gets `192.168.50.x` from Pi DHCP
- Laptop internet works (NAT via Pi)
- UI: `http://192.168.50.1:8080`

**Verify (laptop)**
- macOS:
  ```bash
  ipconfig getifaddr enX
  ```
- Linux:
  ```bash
  ip a
  ```

Internet test:
```bash
curl -I https://1.1.1.1
```

**Verify (Pi)**
```bash
hamsterfi-diag
iw dev wlan0 link
ip route get 1.1.1.1
```

---

### Use-case 3 — Bridge AP (Ethernet uplink, no NAT)
**I want:** Pi behaves like a simple AP, main router handles DHCP.

**Steps**
1. Connect Pi `eth0` into main router LAN
2. Wizard -> **Bridge AP**
3. Set SSID/PSK -> Apply
4. Connect phone to SSID

**Expected**
- Phone gets IP from main router (same subnet as other devices)
- No NAT (devices are in the same LAN)
- Pi does not run DHCP

**Verify (Pi)**
```bash
systemctl is-active dnsmasq   # should be inactive
ip -br a
bridge link
hamsterfi-ip
```

---

## Testing Static WAN IPv4

**Static WAN** means: the Pi itself uses a fixed IP on the upstream network (instead of DHCP).

### AP Router, WAN = eth0 (static example)
If your main LAN is `192.168.110.0/24` and router is `192.168.110.1`:
- address: `192.168.110.250/24` (pick an unused IP)
- gateway: `192.168.110.1`
- DNS: `1.1.1.1`, `8.8.8.8` (or your router)

**Verify**
```bash
ip -br a show eth0
ip -4 route show default
ip route get 1.1.1.1
```

### Station Router, WAN = wlan0 (static)
Use the dorm Wi-Fi subnet + its gateway (often static may be blocked by policy).

Practical method:
1. Connect with DHCP once, inspect:
   ```bash
   ip -4 addr show wlan0
   ip -4 route show default
   ```
2. Choose a free IP in that subnet, keep the same gateway.

### Bridge AP (static management IP)
Typically you use DHCP reservation on the main router for `br0`.
Static management is possible but DHCP is easiest for demos.

---

## Recovery (when you break networking)
If you lose access:
1. Connect via HDMI/keyboard or any known working path
2. Run:
```bash
sudo hamsterfi-recover
```

This restores a known-good AP router mode (`192.168.50.1/24`, DHCP `50-200`, NAT, hostapd SSID) so you can reach the UI again.

---

## Useful commands
```bash
hamsterfi-ip
hamsterfi-diag

sudo hamsterfi-recover
sudo systemctl restart hamsterfi-web

journalctl -u hamsterfi-web -n 200 --no-pager
journalctl -u hostapd -n 200 --no-pager
journalctl -u dnsmasq -n 200 --no-pager
```
