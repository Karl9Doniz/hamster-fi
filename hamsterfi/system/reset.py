import os
from hamsterfi.core.config import CONFIG_PATH, save_config
from hamsterfi.core.models import AppConfig

def reset_config() -> None:
    # Keep current file but reset to defaults
    save_config(AppConfig())

def factory_defaults() -> None:
    # Remove config file entirely
    try:
        os.remove(CONFIG_PATH)
    except FileNotFoundError:
        pass
