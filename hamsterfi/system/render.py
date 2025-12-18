from hamsterfi.core.models import AppConfig

HOSTAPD_PATH = "/etc/hostapd/hostapd.conf"
DNSMASQ_PATH = "/etc/dnsmasq.d/hamster-fi.conf"
NFT_PATH = "/etc/nftables.d/hamster-fi.nft"
WPA_SUPPLICANT_WLAN0 = "/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"


def _hostapd_band_block(channel: int) -> str:
    # 2.4 GHz channels are 1..14; everything else we treat as 5 GHz here.
    if 1 <= channel <= 14:
        # 2.4 GHz
        return """hw_mode=g
ieee80211n=1
"""
    # 5 GHz
    return """hw_mode=a
ieee80211n=1
ieee80211ac=1
"""


def render_hostapd(cfg: AppConfig, ap_if: str) -> str:
    chan = int(cfg.wlan.channel)
    band_block = _hostapd_band_block(chan)

    return f"""country_code={cfg.wlan.country}
interface={ap_if}
driver=nl80211

ssid={cfg.wlan.ssid}
channel={chan}
{band_block}
wmm_enabled=1
auth_algs=1
ignore_broadcast_ssid=0

wpa=2
wpa_passphrase={cfg.wlan.psk}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
"""


def render_dnsmasq(cfg: AppConfig, lan_if: str) -> str:
    if not cfg.lan.dhcp.enabled:
        return "port=0\n"

    lan_ip = cfg.lan.address.split("/")[0]
    return f"""interface={lan_if}
bind-dynamic
listen-address={lan_ip}

dhcp-range={cfg.lan.dhcp.range_start},{cfg.lan.dhcp.range_end},{cfg.lan.dhcp.lease_time}
dhcp-option=option:router,{lan_ip}
dhcp-option=option:dns-server,{lan_ip}

domain-needed
bogus-priv
"""


def render_nft(cfg: AppConfig, wan_if: str, lan_if: str, ui_port: int = 8080) -> str:
    allow_ssh = bool(getattr(cfg.firewall, "allow_ssh_from_lan", True))
    ssh_rule = f'    iifname "{lan_if}" tcp dport 22 accept\n' if allow_ssh else ""

    return f"""flush ruleset

table inet filter {{
  chain input {{
    type filter hook input priority 0; policy drop;

    iif lo accept
    ct state established,related accept

    ip protocol icmp accept
    ip6 nexthdr icmpv6 accept

    iifname "{lan_if}" udp dport {{ 67, 68 }} accept
    iifname "{lan_if}" udp dport 53 accept
    iifname "{lan_if}" tcp dport 53 accept

    iifname "{lan_if}" tcp dport {ui_port} accept
{ssh_rule.rstrip()}
  }}

  chain forward {{
    type filter hook forward priority 0; policy drop;

    ct state established,related accept
    iifname "{lan_if}" oifname "{wan_if}" accept
  }}
}}

table ip nat {{
  chain postrouting {{
    type nat hook postrouting priority 100; policy accept;
    oifname "{wan_if}" masquerade
  }}
}}
"""


def render_wpa_supplicant(country: str, ssid: str, psk: str) -> str:
    return f"""country={country}
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
  ssid="{ssid}"
  psk="{psk}"
}}
"""
