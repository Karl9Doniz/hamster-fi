#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y hostapd dnsmasq nftables wpasupplicant isc-dhcp-client iw python3-venv

sudo mkdir -p /opt/hamster-fi
sudo rsync -a ./ /opt/hamster-fi/

cd /opt/hamster-fi
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

sudo cp scripts/systemd/hamsterfi-web.service /etc/systemd/system/
sudo cp scripts/systemd/hamsterfi-apply.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hamsterfi-web.service
sudo systemctl enable hamsterfi-apply.service
sudo systemctl start hamsterfi-web.service

echo "Installed. Open http://<pi-ip>:8080"
