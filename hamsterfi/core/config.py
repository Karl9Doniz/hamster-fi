import os
import yaml
from .models import AppConfig

CONFIG_PATH = os.environ.get("HAMSTERFI_CONFIG", "/etc/hamster-fi/config.yaml")

def ensure_dirs() -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

def load_config() -> AppConfig:
    ensure_dirs()
    if not os.path.exists(CONFIG_PATH):
        cfg = AppConfig()
        save_config(cfg)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return AppConfig.model_validate(data)

def save_config(cfg: AppConfig) -> None:
    ensure_dirs()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.model_dump(), f, sort_keys=False)
