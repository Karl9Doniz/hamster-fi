import os
import shutil
import subprocess
import time
from typing import Iterable, List, Optional, Tuple

from hamsterfi.core.models import AppConfig
from hamsterfi.system.render import (
    HOSTAPD_PATH,
    DNSMASQ_PATH,
    NFT_PATH,
    WPA_SUPPLICANT_WLAN0,
    render_hostapd,
    render_dnsmasq,
    render_nft,
    render_wpa_supplicant,
)

UI_PORT = int(os.environ.get("HAMSTERFI_UI_PORT", "8080"))
DHCPCD_DROPIN = "/etc/dhcpcd.conf.d/hamster-fi.conf"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _out(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _sysctl_set(key: str, value: str) -> None:
    subprocess.run(["sysctl", "-w", f"{key}={value}"], check=False)


def _enable_router_sysctls() -> None:
    _sysctl_set("net.ipv4.ip_forward", "1")
    _sysctl_set("net.ipv4.conf.all.rp_filter", "0")
    _sysctl_set("net.ipv4.conf.default.rp_filter", "0")

    os.makedirs("/etc/sysctl.d", exist_ok=True)
    _write(
        "/etc/sysctl.d/99-hamster-fi.conf",
        "net.ipv4.ip_forward=1\n"
        "net.ipv4.conf.all.rp_filter=0\n"
        "net.ipv4.conf.default.rp_filter=0\n",
    )


def _write_resolv(dns_list: Iterable[str]) -> None:
    _write("/etc/resolv.conf", "".join([f"nameserver {d}\n" for d in dns_list]))


def _dhcp_release(iface: str) -> None:
    if _have("dhcpcd"):
        subprocess.run(["dhcpcd", "-k", iface], check=False)
    if _have("dhclient"):
        subprocess.run(["dhclient", "-r", iface], check=False)
    if _have("nmcli"):
        subprocess.run(["nmcli", "device", "disconnect", iface], check=False)

    subprocess.run(["ip", "route", "del", "default", "dev", iface], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", iface], check=False)


def _dhcp_up(iface: str) -> None:
    subprocess.run(["ip", "link", "set", iface, "up"], check=False)

    if _have("dhcpcd"):
        subprocess.run(["dhcpcd", "-k", iface], check=False)
        subprocess.run(["dhcpcd", "-n", iface], check=False)
        subprocess.run(["systemctl", "restart", "dhcpcd"], check=False)
        return

    if _have("dhclient"):
        subprocess.run(["dhclient", "-v", "-r", iface], check=False)
        subprocess.run(["dhclient", "-v", iface], check=True)
        return

    if _have("udhcpc"):
        subprocess.run(["udhcpc", "-i", iface, "-q", "-f"], check=True)
        return

    if _have("nmcli"):
        subprocess.run(["nmcli", "device", "set", iface, "managed", "yes"], check=False)
        subprocess.run(["nmcli", "device", "disconnect", iface], check=False)
        subprocess.run(["nmcli", "device", "connect", iface], check=False)
        return

    raise RuntimeError(f"No DHCP client found to configure {iface}.")


def _static_up(iface: str, address: str, gateway: str, dns: Iterable[str]) -> None:
    subprocess.run(["ip", "link", "set", iface, "up"], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", iface], check=False)
    subprocess.run(["ip", "addr", "add", address, "dev", iface], check=True)
    subprocess.run(["ip", "route", "replace", "default", "via", gateway], check=True)
    _write_resolv(dns)


def _dhcp_or_static(iface: str, cfg: AppConfig) -> None:
    if cfg.wan.ipv4 == "dhcp":
        _dhcp_up(iface)
    else:
        _static_up(iface, cfg.wan.static.address, cfg.wan.static.gateway, cfg.wan.static.dns)


def _ensure_ap_iface() -> str:
    try:
        out = _out(["ip", "link", "show"])
    except Exception:
        out = ""
    if "ap0" in out:
        return "ap0"

    try:
        subprocess.run(["iw", "dev", "wlan0", "interface", "add", "ap0", "type", "__ap"], check=True)
        return "ap0"
    except Exception:
        return "wlan0"


def _detect_default_uplink() -> Optional[str]:
    try:
        out = _out(["ip", "-4", "route", "show", "default"])
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    return None


def _persist_nft_rules(cfg: AppConfig, wan_if: str, lan_if: str) -> None:
    rules = render_nft(cfg, wan_if=wan_if, lan_if=lan_if, ui_port=UI_PORT)
    _write(NFT_PATH, rules)

    _write(
        "/etc/nftables.conf",
        "flush ruleset\n"
        "include \"/etc/nftables.d/*.nft\"\n",
    )

    _run(["nft", "-f", "/etc/nftables.conf"], check=True)
    subprocess.run(["systemctl", "enable", "nftables"], check=False)
    subprocess.run(["systemctl", "restart", "nftables"], check=False)


def _cleanup_duplicate_defaults(preferred_if: str) -> None:
    try:
        out = _out(["ip", "-4", "route", "show", "default"])
    except Exception:
        return

    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    for ln in lines:
        parts = ln.split()
        if "dev" not in parts:
            continue
        dev = parts[parts.index("dev") + 1]
        if dev != preferred_if:
            subprocess.run(["ip", "route", "del"] + parts, check=False)

    seen = 0
    try:
        out2 = _out(["ip", "-4", "route", "show", "default", "dev", preferred_if])
        for ln in out2.splitlines():
            if not ln.strip():
                continue
            seen += 1
            if seen >= 2:
                subprocess.run(["ip", "route", "del"] + ln.split(), check=False)
    except Exception:
        pass


def _freq_to_channel(freq_mhz: float) -> int:
    f = int(round(freq_mhz))
    if 2412 <= f <= 2484:
        if f == 2484:
            return 14
        return int((f - 2407) / 5)
    if 5000 <= f <= 5900:
        return int((f - 5000) / 5)
    return 6


def _read_wlan0_link_freq_channel() -> Optional[Tuple[float, int]]:
    try:
        out = _out(["iw", "dev", "wlan0", "link"])
    except Exception:
        return None
    if "Not connected" in out:
        return None

    freq = None
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("freq:"):
            try:
                freq = float(ln.split()[1])
            except Exception:
                freq = None
    if freq is None:
        return None
    return (freq, _freq_to_channel(freq))


def _rm_bridge() -> None:
    subprocess.run(["ip", "link", "set", "ap0", "nomaster"], check=False)
    subprocess.run(["ip", "link", "set", "eth0", "nomaster"], check=False)
    subprocess.run(["ip", "link", "set", "wlan0", "nomaster"], check=False)
    subprocess.run(["ip", "link", "set", "br0", "down"], check=False)
    subprocess.run(["ip", "link", "del", "br0"], check=False)


def _set_dhcpcd_mode(mode: str, wan_if: str) -> None:
    os.makedirs("/etc/dhcpcd.conf.d", exist_ok=True)

    if mode == "bridge":
        deny = ["eth0", "wlan0", "ap0"]
    else:
        deny = ["eth0", "wlan0", "ap0", "br0"]
        if wan_if in deny:
            deny.remove(wan_if)

    content = "# hamster-fi: prevent route/DHCP fights\n" + "".join([f"denyinterfaces {d}\n" for d in deny])
    _write(DHCPCD_DROPIN, content)
    subprocess.run(["systemctl", "restart", "dhcpcd"], check=False)


def _restart_wpa_supplicant_wlan0() -> None:
    """
    On Raspberry Pi OS, the correct unit is often wpa_supplicant@wlan0.
    We try that first, then fall back to generic wpa_supplicant.
    """
    if _have("systemctl"):
        subprocess.run(["systemctl", "enable", "wpa_supplicant@wlan0.service"], check=False)
        subprocess.run(["systemctl", "restart", "wpa_supplicant@wlan0.service"], check=False)
        # fallback
        subprocess.run(["systemctl", "enable", "wpa_supplicant"], check=False)
        subprocess.run(["systemctl", "restart", "wpa_supplicant"], check=False)


def _wait_wlan0_connected(timeout_s: int = 15) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            out = _out(["iw", "dev", "wlan0", "link"])
            if "Connected to" in out and "Not connected" not in out:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def apply(cfg: AppConfig) -> None:
    # Crash-safe-ish apply:
    # 1) snapshot current on-disk config files we touch
    # 2) attempt to apply requested mode
    # 3) on any failure, restore files + restart services so the box stays reachable

    files_to_backup = [
        HOSTAPD_PATH,
        DNSMASQ_PATH,
        NFT_PATH,
        WPA_SUPPLICANT_WLAN0,
        "/etc/dhcpcd.conf",
    ]

    backups = {}
    for p in files_to_backup:
        try:
            with open(p, "r", encoding="utf-8") as f:
                backups[p] = f.read()
        except FileNotFoundError:
            backups[p] = None
        except Exception:
            # don't fail apply because a backup read failed
            backups[p] = None

    def _restore_files() -> None:
        for p, content in backups.items():
            try:
                if content is None:
                    # remove file if we created it
                    if os.path.exists(p):
                        os.remove(p)
                else:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(content)
            except Exception:
                pass

    try:
        # Stop LAN services before changing interfaces/config.
        # (We restart them later in the mode-specific routines.)
        subprocess.run(["systemctl", "stop", "hostapd"], check=False)
        subprocess.run(["systemctl", "stop", "dnsmasq"], check=False)

        # Never leave physical links down.
        subprocess.run(["ip", "link", "set", "eth0", "up"], check=False)
        subprocess.run(["ip", "link", "set", "wlan0", "up"], check=False)

        if cfg.mode == "ap":
            _apply_ap_router(cfg)
        elif cfg.mode == "station":
            _apply_station_router(cfg)
        elif cfg.mode == "bridge":
            _apply_bridge_ap(cfg)
        else:
            raise RuntimeError(f"Unknown mode: {cfg.mode}")

    except Exception:
        # Restore on-disk configs and try to put services back.
        _restore_files()

        # Remove any unexpected bridge that could have been created.
        try:
            _rm_bridge()
        except Exception:
            pass

        # Best-effort: bring AP iface back so user can recover via UI
        try:
            ap_if = _ensure_ap_iface()
            subprocess.run(["ip", "link", "set", ap_if, "up"], check=False)
        except Exception:
            pass

        # Restart core services (best-effort)
        for svc in ["dhcpcd", "nftables", "hostapd", "dnsmasq", "wpa_supplicant@wlan0"]:
            subprocess.run(["systemctl", "restart", svc], check=False)

        raise

def _apply_ap_router(cfg: AppConfig) -> None:
    import time

    wan_if = cfg.wan.device
    ap_if = _ensure_ap_iface()

    _set_dhcpcd_mode("ap", wan_if)
    _rm_bridge()

    # Avoid route fights: release DHCP on the non-WAN interface,
    # but DO NOT force the link down (it breaks management + surprises the user).
    other = "wlan0" if wan_if == "eth0" else "eth0"
    _dhcp_release(other)
    subprocess.run(["ip", "addr", "flush", "dev", other], check=False)
    subprocess.run(["ip", "link", "set", other, "up"], check=False)

    def _safe_out(cmd: list[str]) -> str:
        try:
            return _out(cmd) or ""
        except Exception:
            return ""

    def _default_gw_for_dev(dev: str) -> str | None:
        txt = _safe_out(["ip", "-4", "route", "show", "default", "dev", dev]).strip()
        for ln in txt.splitlines():
            parts = ln.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                return parts[2]
        return None

    def _default_gw_any() -> str | None:
        txt = _safe_out(["ip", "-4", "route", "show", "default"]).strip()
        for ln in txt.splitlines():
            parts = ln.split()
            if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
                return parts[2]
        return None

    def _dhcpcd_lease_router(dev: str) -> str | None:
        candidates = [
            f"/var/lib/dhcpcd5/dhcpcd-{dev}.lease",
            f"/var/lib/dhcpcd/dhcpcd-{dev}.lease",
        ]
        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for ln in f:
                        ln = ln.strip()
                        if ln.startswith("routers=") or ln.startswith("router="):
                            v = ln.split("=", 1)[1].strip()
                            if v:
                                return v.split()[0]
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return None

    def _wait_for_gw(preferred_dev: str, timeout_s: int = 15) -> str | None:
        """
        dhcpcd is async; sometimes it adds the default route a bit later.
        Poll until we can infer a gateway.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            gw = _default_gw_for_dev(preferred_dev)
            if not gw:
                gw = _default_gw_any()
            if not gw:
                gw = _dhcpcd_lease_router(preferred_dev)
            if gw:
                return gw
            time.sleep(0.5)
        return None

    def _prefer_default(preferred_dev: str, backup_dev: str) -> None:
        """
        Force preferred default route by metric.
        This is required in your situation because both interfaces receive defaults,
        and eth0 has a lower metric so it wins (exactly what you’re seeing).  [oai_citation:2‡log.txt](sediment://file_000000005cac7243aa3d6d90c7eb260c)
        """
        gw_pref = _wait_for_gw(preferred_dev, timeout_s=15)
        if not gw_pref:
            raise RuntimeError(
                f"{preferred_dev} is up but no gateway could be inferred (even after waiting). "
                f"Check: ip -4 route show default ; iw dev {preferred_dev} link"
            )

        # Preferred route (low metric)
        subprocess.run(
            ["ip", "route", "replace", "default", "via", gw_pref, "dev", preferred_dev, "metric", "50"],
            check=False,
        )

        # Backup route (high metric)
        gw_bak = _default_gw_for_dev(backup_dev) or _dhcpcd_lease_router(backup_dev) or gw_pref
        subprocess.run(
            ["ip", "route", "replace", "default", "via", gw_bak, "dev", backup_dev, "metric", "5000"],
            check=False,
        )

        # Flush route cache so "ip route get" stops showing cached old choice
        subprocess.run(["ip", "route", "flush", "cache"], check=False)

    # If WAN is wlan0: connect upstream FIRST and obtain DHCP FIRST.
    if wan_if == "wlan0":
        if not cfg.wan.upstream_ssid or not cfg.wan.upstream_psk:
            raise RuntimeError("AP mode with WAN=wlan0 requires upstream SSID+PSK.")

        _write(
            WPA_SUPPLICANT_WLAN0,
            render_wpa_supplicant(cfg.wlan.country, cfg.wan.upstream_ssid, cfg.wan.upstream_psk),
        )
        _restart_wpa_supplicant_wlan0()

        if not _wait_wlan0_connected(timeout_s=20):
            raise RuntimeError("wlan0 did not associate to upstream Wi-Fi (check SSID/PSK).")

        _dhcp_or_static("wlan0", cfg)

        # THE FIX: force wlan0 to win (eth0 currently wins due to metric).  [oai_citation:3‡log.txt](sediment://file_000000005cac7243aa3d6d90c7eb260c)
        _prefer_default(preferred_dev="wlan0", backup_dev="eth0")

        # Align AP channel to upstream channel (single-radio requirement)
        link = _read_wlan0_link_freq_channel()
        if link is not None:
            _, upstream_ch = link
            cfg.wlan.channel = upstream_ch

    # LAN address on AP iface
    subprocess.run(["ip", "link", "set", ap_if, "up"], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", ap_if], check=False)
    subprocess.run(["ip", "addr", "add", cfg.lan.address, "dev", ap_if], check=True)

    # Start AP
    _write(HOSTAPD_PATH, render_hostapd(cfg, ap_if=ap_if))
    subprocess.run(["systemctl", "enable", "hostapd"], check=False)
    subprocess.run(["systemctl", "restart", "hostapd"], check=False)

    # Configure WAN if eth0
    if wan_if == "eth0":
        _dhcp_or_static("eth0", cfg)
        _prefer_default(preferred_dev="eth0", backup_dev="wlan0")

    # DHCP/DNS on LAN
    _write(DNSMASQ_PATH, render_dnsmasq(cfg, lan_if=ap_if))
    subprocess.run(["systemctl", "enable", "dnsmasq"], check=False)
    subprocess.run(["systemctl", "restart", "dnsmasq"], check=False)

    _enable_router_sysctls()

    effective_wan = _detect_default_uplink() or wan_if
    _persist_nft_rules(cfg, wan_if=effective_wan, lan_if=ap_if)


def _apply_station_router(cfg: AppConfig) -> None:
    _set_dhcpcd_mode("station", "wlan0")
    _rm_bridge()

    if not cfg.wan.upstream_ssid or not cfg.wan.upstream_psk:
        raise RuntimeError("Station mode requires upstream SSID + PSK.")

    _write(
        WPA_SUPPLICANT_WLAN0,
        render_wpa_supplicant(cfg.wlan.country, cfg.wan.upstream_ssid, cfg.wan.upstream_psk),
    )
    _restart_wpa_supplicant_wlan0()

    if not _wait_wlan0_connected(timeout_s=20):
        raise RuntimeError("wlan0 did not associate to upstream Wi-Fi (check SSID/PSK).")

    _dhcp_release("eth0")
    subprocess.run(["ip", "link", "set", "eth0", "down"], check=False)

    _dhcp_or_static("wlan0", cfg)
    _cleanup_duplicate_defaults(preferred_if="wlan0")

    subprocess.run(["ip", "addr", "flush", "dev", "eth0"], check=False)
    subprocess.run(["ip", "addr", "add", cfg.lan.address, "dev", "eth0"], check=True)
    subprocess.run(["ip", "link", "set", "eth0", "up"], check=False)

    _write(DNSMASQ_PATH, render_dnsmasq(cfg, lan_if="eth0"))
    subprocess.run(["systemctl", "enable", "dnsmasq"], check=False)
    subprocess.run(["systemctl", "restart", "dnsmasq"], check=False)

    subprocess.run(["systemctl", "stop", "hostapd"], check=False)
    subprocess.run(["systemctl", "disable", "hostapd"], check=False)

    _enable_router_sysctls()
    effective_wan = _detect_default_uplink() or "wlan0"
    _persist_nft_rules(cfg, wan_if=effective_wan, lan_if="eth0")


def _apply_bridge_ap(cfg: AppConfig) -> None:
    import time
    br = "br0"
    ap_if = _ensure_ap_iface()

    # Bridge AP = no DHCP server, no NAT/firewall from us
    subprocess.run(["systemctl", "stop", "dnsmasq"], check=False)
    subprocess.run(["systemctl", "disable", "dnsmasq"], check=False)
    subprocess.run(["nft", "flush", "ruleset"], check=False)
    subprocess.run(["systemctl", "stop", "nftables"], check=False)
    subprocess.run(["systemctl", "disable", "nftables"], check=False)

    # Clean up any old bridge first
    _rm_bridge()

    # IMPORTANT: keep current eth0 IP alive until br0 obtains DHCP
    # (eth0 can temporarily keep an IP even while being a bridge port)

    # Create bridge
    subprocess.run(["ip", "link", "add", br, "type", "bridge"], check=False)
    # make it fast / predictable
    subprocess.run(["ip", "link", "set", br, "type", "bridge", "stp_state", "0"], check=False)
    subprocess.run(["ip", "link", "set", br, "up"], check=False)

    # Enslave ports to bridge (DO NOT flush eth0 yet)
    subprocess.run(["ip", "link", "set", "eth0", "up"], check=False)
    subprocess.run(["ip", "link", "set", ap_if, "up"], check=False)

    subprocess.run(["ip", "link", "set", "eth0", "master", br], check=False)
    subprocess.run(["ip", "link", "set", ap_if, "master", br], check=False)

    # Start AP (hostapd) on ap_if, but in bridge mode hostapd should know the bridge
    conf = render_hostapd(cfg, ap_if=ap_if)
    if f"\nbridge={br}\n" not in conf and not conf.rstrip().endswith(f"bridge={br}"):
        conf = conf.rstrip() + f"\nbridge={br}\n"
    _write(HOSTAPD_PATH, conf)

    subprocess.run(["systemctl", "enable", "hostapd"], check=False)
    subprocess.run(["systemctl", "restart", "hostapd"], check=False)

    # Now br0 exists, so set dhcpcd mode AFTER creation
    _set_dhcpcd_mode("bridge", br)

    # Request DHCP on br0 (and WAIT). This is the key part.
    got_ip = False
    if _have("dhcpcd"):
        # Ensure daemon sees new iface + config
        subprocess.run(["systemctl", "restart", "dhcpcd"], check=False)
        # Ask specifically for br0 and wait up to 25s
        subprocess.run(["dhcpcd", "-4", "-t", "25", "-w", br], check=False)
    elif _have("dhclient"):
        subprocess.run(["dhclient", "-v", "-r", br], check=False)
        subprocess.run(["dhclient", "-v", br], check=False)

    # Poll for IPv4 on br0
    deadline = time.time() + 25
    while time.time() < deadline:
        out = subprocess.check_output(["ip", "-4", "-br", "addr", "show", br], text=True).strip()
        # looks like: "br0 UP 192.168.110.123/24 ..."
        if "inet " in out or ("/" in out and br in out):
            if "169.254." not in out:  # ignore link-local fallback
                got_ip = True
                break
        time.sleep(1)

    if not got_ip:
        # Roll back bridge so you don't get stranded
        subprocess.run(["ip", "link", "set", "eth0", "nomaster"], check=False)
        subprocess.run(["ip", "link", "set", ap_if, "nomaster"], check=False)
        subprocess.run(["ip", "link", "del", br], check=False)

        # Bring eth0 back (best-effort)
        if _have("dhcpcd"):
            subprocess.run(["systemctl", "restart", "dhcpcd"], check=False)
            subprocess.run(["dhcpcd", "-n", "eth0"], check=False)
        elif _have("dhclient"):
            subprocess.run(["dhclient", "-v", "eth0"], check=False)

        raise RuntimeError(
            "Bridge AP: br0 did not obtain a DHCP address; rolled back to avoid leaving UI unreachable."
        )

    # ✅ We have a br0 management IP now — safe to clean addresses on member ports
    subprocess.run(["ip", "addr", "flush", "dev", "eth0"], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", ap_if], check=False)

    # Also ensure br0 is the management interface for routing decisions (Pi itself)
    # (No NAT here, but Pi needs default route for its own outbound access)
    # dhcpcd/dhclient should have installed it; no extra changes required.
