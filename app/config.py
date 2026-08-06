"""
Configuration Manager
Handles loading/saving settings for Weather Provider
"""
import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"

DEFAULT_SETTINGS = {
    "provider": "open_meteo",
    "api_key": ""
}

def load_settings():
    """Load settings from JSON (or defaults)"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(provider, api_key):
    """Save settings to JSON"""
    settings = {
        "provider": provider,
        "api_key": api_key
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
    return settings

# Initialize
_settings = load_settings()

def get_provider():
    return _settings.get("provider", "open_meteo")

def get_api_key():
    return _settings.get("api_key", "")

def update_config(provider, api_key):
    global _settings
    _settings = save_settings(provider, api_key)
