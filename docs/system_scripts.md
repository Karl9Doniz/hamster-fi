# System Scripts and Commands

### render.py (config generators)

- Paths prepared for rendered configs: `/etc/hostapd/hostapd.conf`, `/etc/dnsmasq.d/hamster-fi.conf`, `/etc/nftables.d/hamster-fi.nft`, `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`.
- Chooses 2.4 GHz vs 5 GHz hostapd blocks based on channel and builds SSID/PSK configs.
- dnsmasq renderer enables DHCP on the LAN interface, sets range, router + DNS options, or disables DNS/DHCP with `port=0`.
- nft renderer builds filter + NAT tables and can allow SSH from LAN; injects mDNS accept rule when missing.
- wpa_supplicant renderer writes country + upstream SSID/PSK for wlan0 station joins.

### apply.py (bring-up + recovery)

#### Safety nets

- Backs up hostapd/dnsmasq/nft/wpa_supplicant/dhcpcd configs before changes; restores them on failure.
- Stops AP/DHCP services up front: `systemctl stop hostapd dnsmasq`.
- Restarts services after rollback attempts: `systemctl restart dhcpcd nftables hostapd dnsmasq wpa_supplicant@wlan0`.

#### DHCP + addressing helpers

```bash
sysctl -w net.ipv4.ip_forward=1                # router sysctls enabled and persisted in /etc/sysctl.d/99-hamster-fi.conf
dhcpcd -k <iface>                              # release dhcpcd lease (if present)
dhclient -r <iface>                            # release dhclient lease (fallback)
nmcli device disconnect <iface>                # drop NM-managed link to avoid route fights
ip route del default dev <iface>               # clear defaults on the interface
ip addr flush dev <iface>                      # drop assigned addresses
ip link set <iface> up                         # ensure link is up
dhcpcd -n <iface> / dhclient -v <iface> / udhcpc -i <iface>  # renew DHCP depending on available client
ip addr add <cidr> dev <iface>                 # static address assignment
ip route replace default via <gateway>         # static default route
echo "nameserver <dns>" > /etc/resolv.conf     # writes resolvers via helper
```

- Prefers a specific uplink by metric: `ip route replace default via <gw> dev <wan> metric 50` and demotes backups with metric 5000; flushes route cache.
- Cleans duplicate defaults on re-run: `ip -4 route show default` then `ip route del ...` for non-preferred devices.

#### Interface prep

```bash
iw dev wlan0 interface add ap0 type __ap       # create AP vNIC if not present
ip link show                                   # detect existing ap0
ip link set ap0/eth0/wlan0 nomaster            # detach from bridges
ip link del br0                                # remove existing bridge
ip link add br0 type bridge                    # create bridge (bridge mode)
ip link set br0 type bridge stp_state 0        # disable STP
ip link set br0 up                             # bring bridge up
ip link set eth0 master br0                    # enslave LAN port into bridge
ip link set ap0 master br0                     # bridge AP into br0
```

- Adds dhcpcd drop-in to avoid dhcpcd configuring non-WAN interfaces: `/etc/dhcpcd.conf.d/hamster-fi.conf` with `denyinterfaces ...`; restarts dhcpcd.

#### Wi-Fi association

```bash
systemctl enable/restart wpa_supplicant@wlan0.service  # prefer per-interface unit, fallback to generic wpa_supplicant
iw dev wlan0 link                                      # poll for association + upstream frequency
```

- Writes `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` with upstream SSID/PSK before restarting supplicant.
- Converts upstream frequency to channel so the AP can mirror the uplink channel when WAN is wlan0.

#### Firewall, NAT, discovery, and services

```bash
nft -f /etc/nftables.conf                  # apply composed nftables ruleset (includes /etc/nftables.d/hamster-fi.nft)
systemctl enable/restart nftables          # ensure persistence
systemctl enable/restart avahi-daemon      # keep mDNS responding after nft changes
systemctl enable/restart hostapd           # apply AP config
systemctl enable/restart dnsmasq           # apply DHCP/DNS config
```

- Writes `/etc/nftables.conf` shim to include `*.nft`, then injects mDNS accept rule (`udp dport 5353`) if missing.
- When entering bridge mode, flushes nftables and stops/disables dnsmasq/nftables to keep the bridge L2-only.

#### Mode flows

- **AP router (WAN = wlan0 or eth0):** ensures ap0 exists, releases the non-WAN interface, joins upstream Wi-Fi when WAN=wlan0, prefers WAN default route via metrics, assigns LAN IP to ap0, writes hostapd/dnsmasq, enables NAT/firewall, and sets router sysctls.
- **Station router (WAN = wlan0, LAN = eth0):** joins upstream Wi-Fi, purges defaults on eth0, assigns LAN IP to eth0, runs dnsmasq on eth0, disables hostapd, cleans duplicate default routes, and applies NAT/firewall.
- **Bridge AP (LAN bridge):** builds br0 with eth0 + ap0, appends `bridge=br0` to hostapd config, obtains DHCP on br0 via dhcpcd/dhclient, rolls back on failure, removes stale default via eth0, and leaves routing to upstream bridge gateway.

### reset.py (config resetters)

- `reset_config()` writes a fresh `AppConfig()` over the existing config file via `save_config`, keeping the file but resetting values.
- `factory_defaults()` deletes the config file at `hamsterfi/core/config.py:CONFIG_PATH` if it exists to simulate out-of-box state.
