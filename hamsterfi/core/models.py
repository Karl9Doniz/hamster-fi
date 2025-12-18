from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Mode = Literal["ap", "station", "bridge"]
WanDevice = Literal["eth0", "wlan0"]
IPv4Mode = Literal["dhcp", "static"]

class WanStatic(BaseModel):
    address: str = "192.168.1.200/24"
    gateway: str = "192.168.1.1"
    dns: List[str] = Field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])

class WanConfig(BaseModel):
    device: WanDevice = "eth0"
    ipv4: IPv4Mode = "dhcp"
    static: WanStatic = Field(default_factory=WanStatic)
    # used when device=wlan0 and joining upstream Wi‑Fi
    upstream_ssid: Optional[str] = None
    upstream_psk: Optional[str] = None

class DhcpConfig(BaseModel):
    enabled: bool = True
    range_start: str = "192.168.50.50"
    range_end: str = "192.168.50.200"
    lease_time: str = "12h"

class LanConfig(BaseModel):
    subnet: str = "192.168.50.0/24"
    address: str = "192.168.50.1/24"
    dhcp: DhcpConfig = Field(default_factory=DhcpConfig)

class WlanConfig(BaseModel):
    ssid: str = "HamsterNet"
    psk: str = "hamster12345"
    country: str = "UA"
    channel: int = 6

class FirewallConfig(BaseModel):
    enabled: bool = True
    allow_admin_from_lan: bool = True
    allow_ssh_from_lan: bool = True

class AppConfig(BaseModel):
    mode: Mode = "ap"
    wan: WanConfig = Field(default_factory=WanConfig)
    lan: LanConfig = Field(default_factory=LanConfig)
    wlan: WlanConfig = Field(default_factory=WlanConfig)
    firewall: FirewallConfig = Field(default_factory=FirewallConfig)
