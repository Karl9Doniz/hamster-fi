import yaml
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from hamsterfi.core.config import load_config, save_config
from hamsterfi.core.models import AppConfig
from hamsterfi.core.status import status_snapshot
from hamsterfi.system.apply import apply as apply_system
from hamsterfi.system.reset import reset_config, factory_defaults

app = FastAPI()
templates = Jinja2Templates(directory="hamsterfi/templates")


@app.get("/", response_class=HTMLResponse)
def status(request: Request):
    cfg = load_config()
    snap = status_snapshot()
    return templates.TemplateResponse("status.html", {"request": request, "cfg": cfg, "snap": snap})

@app.get("/wizard", response_class=HTMLResponse)
def wizard_mode(request: Request):
    cfg = load_config()
    return templates.TemplateResponse("wizard_mode.html", {"request": request, "cfg": cfg})


@app.get("/wizard/mode")
def wizard_mode_get():
    return RedirectResponse("/wizard", status_code=303)


@app.post("/wizard/mode")
def wizard_mode_post(mode: str = Form(...)):
    cfg = load_config()
    cfg.mode = mode

    cfg.lan.address = "192.168.50.1/24"
    cfg.lan.subnet = "192.168.50.0/24"

    if cfg.mode == "ap":
        cfg.lan.dhcp.enabled = True
        cfg.wan.device = "eth0"
        cfg.wan.ipv4 = "dhcp"
        cfg.wan.upstream_ssid = None
        cfg.wan.upstream_psk = None

    if cfg.mode == "station":
        cfg.lan.dhcp.enabled = True
        cfg.wan.device = "wlan0"
        cfg.wan.ipv4 = "dhcp"

    if cfg.mode == "bridge":
        cfg.lan.dhcp.enabled = False
        cfg.wan.device = "eth0"
        cfg.wan.ipv4 = "dhcp"
        cfg.wan.upstream_ssid = None
        cfg.wan.upstream_psk = None

    save_config(cfg)
    return RedirectResponse("/wizard/wan", status_code=303)


@app.get("/wizard/wan", response_class=HTMLResponse)
def wizard_wan(request: Request):
    cfg = load_config()
    return templates.TemplateResponse("wizard_wan.html", {"request": request, "cfg": cfg})


@app.post("/wizard/wan", response_class=HTMLResponse)
def wizard_wan_post(
    request: Request,
    wan_device: str = Form(...),
    wan_ipv4: str = Form(...),
    static_address: str = Form(""),
    static_gateway: str = Form(""),
    static_dns: str = Form(""),
    upstream_ssid: str = Form(""),
    upstream_psk: str = Form(""),
):
    cfg = load_config()

    if cfg.mode == "bridge":
        wan_device = "eth0"
    if cfg.mode == "station":
        wan_device = "wlan0"

    cfg.wan.device = wan_device
    cfg.wan.ipv4 = wan_ipv4

    if wan_ipv4 == "static":
        cfg.wan.static.address = static_address.strip() or cfg.wan.static.address
        cfg.wan.static.gateway = static_gateway.strip() or cfg.wan.static.gateway
        dns_list = [x.strip() for x in static_dns.split(",") if x.strip()]
        if dns_list:
            cfg.wan.static.dns = dns_list

    need_upstream = (cfg.mode == "station") or (cfg.mode == "ap" and cfg.wan.device == "wlan0")

    if need_upstream:
        cfg.wan.upstream_ssid = upstream_ssid.strip() or None
        cfg.wan.upstream_psk = upstream_psk.strip() or None

        if not cfg.wan.upstream_ssid or not cfg.wan.upstream_psk:
            return templates.TemplateResponse(
                "wizard_wan.html",
                {
                    "request": request,
                    "cfg": cfg,
                    "error": "Upstream Wi‑Fi SSID and password are required when WAN is Wi‑Fi (wlan0).",
                },
            )
    else:
        cfg.wan.upstream_ssid = None
        cfg.wan.upstream_psk = None

    save_config(cfg)
    return RedirectResponse("/wizard/wlan", status_code=303)


@app.get("/wizard/wlan", response_class=HTMLResponse)
def wizard_wlan(request: Request):
    cfg = load_config()
    return templates.TemplateResponse("wizard_wlan.html", {"request": request, "cfg": cfg})


@app.post("/wizard/wlan")
def wizard_wlan_post(ssid: str = Form(...), psk: str = Form(...)):
    cfg = load_config()
    cfg.wlan.ssid = ssid.strip()
    cfg.wlan.psk = psk.strip()
    save_config(cfg)
    return RedirectResponse("/wizard/review", status_code=303)


@app.get("/wizard/review", response_class=HTMLResponse)
def wizard_review(request: Request):
    cfg = load_config()
    return templates.TemplateResponse("wizard_review.html", {"request": request, "cfg": cfg})


@app.get("/advanced", response_class=HTMLResponse)
def advanced(request: Request):
    cfg = load_config()
    yaml_text = yaml.safe_dump(cfg.model_dump(), sort_keys=False)
    return templates.TemplateResponse("advanced.html", {"request": request, "cfg": cfg, "yaml_text": yaml_text})


@app.post("/advanced")
def advanced_post(config_yaml: str = Form(...)):
    data = yaml.safe_load(config_yaml) or {}
    cfg = AppConfig.model_validate(data)
    save_config(cfg)
    return RedirectResponse("/", status_code=303)


@app.get("/api/config.yaml", response_class=PlainTextResponse)
def get_config_yaml():
    cfg = load_config()
    return yaml.safe_dump(cfg.model_dump(), sort_keys=False)



@app.get("/actions/apply")
def apply_get():
    return RedirectResponse("/", status_code=303)


@app.post("/actions/apply")
def apply_now():
    cfg = load_config()
    apply_system(cfg)
    return RedirectResponse("/", status_code=303)


@app.post("/actions/reset")
def do_reset():
    reset_config()
    return RedirectResponse("/", status_code=303)


@app.post("/actions/factory")
def do_factory():
    factory_defaults()
    return RedirectResponse("/", status_code=303)
