#!/usr/bin/env bash
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_PATH="/etc/systemd/system/hamsterfi-web.service"
BIN_DIR="/usr/local/bin"

echo "[install] APPDIR=$APPDIR"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/hamsterfi-diag" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "=== ip addr ==="; ip -br addr
echo "=== routes ==="; ip route | sed -n "1,15p"

echo "=== hostapd ==="
systemctl is-active hostapd >/dev/null && echo "OK" || systemctl status hostapd --no-pager

echo "=== dnsmasq ==="
systemctl is-active dnsmasq >/dev/null && echo "OK" || systemctl status dnsmasq --no-pager

echo "=== nft ==="; nft list ruleset | sed -n "1,180p"

echo "=== ports (53/67/8080) ==="
ss -lunp | egrep ':(53|67)\b' || true
ss -ltnp | grep ':8080' || echo "no 8080 listener"

echo "=== hamsterfi service ==="
systemctl status hamsterfi-web --no-pager 2>/dev/null || true

echo "=== recent logs (dnsmasq/hostapd/web) ==="
journalctl -u dnsmasq -n 30 --no-pager 2>/dev/null || true
journalctl -u hostapd -n 30 --no-pager 2>/dev/null || true
journalctl -u hamsterfi-web -n 30 --no-pager 2>/dev/null || true
EOF
chmod +x "$BIN_DIR/hamsterfi-diag"

if [[ -f "$APPDIR/scripts/systemd/hamsterfi-recover" ]]; then
  install -m 0755 "$APPDIR/scripts/systemd/hamsterfi-recover" "$BIN_DIR/hamsterfi-recover"
else
  echo "[install] NOTE: scripts/systemd/hamsterfi-recover not found in repo."
fi

cat > "$BIN_DIR/hamsterfi-ip" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

UI_PORT="${UI_PORT:-8080}"

has_ip() { ip -4 addr show "$1" 2>/dev/null | grep -q "inet "; }

ip_of() {
  ip -4 -o addr show "$1" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1
}

echo "=== Hamster-Fi UI candidates ==="

# Router modes: prefer 192.168.50.1 if ap0 exists with that IP
if ip -4 addr show ap0 2>/dev/null | grep -q "192\.168\.50\.1/"; then
  echo "AP/Station UI: http://192.168.50.1:${UI_PORT}"
fi

# Bridge mode: br0 gets DHCP
if has_ip br0; then
  echo "Bridge UI (br0): http://$(ip_of br0):${UI_PORT}"
fi

# Fallbacks
for dev in eth0 wlan0; do
  if has_ip "$dev"; then
    echo "UI via $dev: http://$(ip_of "$dev"):${UI_PORT}"
  fi
done

echo
echo "Tip: if you changed hostname, ensure /etc/hosts has '127.0.1.1 <hostname>'"
EOF
chmod +x "$BIN_DIR/hamsterfi-ip"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Hamster-Fi Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APPDIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${APPDIR}/.venv/bin/uvicorn hamsterfi.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=1
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now hamsterfi-web

echo
echo "[install] Done."
echo "[install] Try: hamsterfi-ip"