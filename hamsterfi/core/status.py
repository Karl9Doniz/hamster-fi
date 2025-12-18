import subprocess

def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)

def status_snapshot() -> dict:
    out = {}
    for k, cmd in {
        "ip_link": ["ip", "-br", "link"],
        "ip_addr": ["ip", "-br", "addr"],
        "ip_route": ["ip", "route"],
        "iw_wlan0": ["bash", "-lc", "iw dev wlan0 link 2>/dev/null || true"],
        "iw_ap0": ["bash", "-lc", "iw dev ap0 info 2>/dev/null || true"],
        "nft": ["bash", "-lc", "nft list ruleset 2>/dev/null | head -n 120 || true"],
        "dnsmasq": ["bash", "-lc", "systemctl is-active dnsmasq || true"],
        "hostapd": ["bash", "-lc", "systemctl is-active hostapd || true"],
    }.items():
        try:
            out[k] = _run(cmd).strip()
        except Exception as e:
            out[k] = f"ERROR: {e}"
    return out
