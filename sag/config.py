from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "sag"
CONFIG_FILE = CONFIG_DIR / "config.json"

AVAILABLE_MODELS = [
    "KittenML/kitten-tts-nano-0.8",
    "KittenML/kitten-tts-micro-0.8",
    "KittenML/kitten-tts-mini-0.8",
]


def load_config() -> dict:
    """Load config from disk, returning empty dict if missing."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def get_default(key: str, fallback: str) -> str:
    """Get a config value, falling back to the provided default."""
    return load_config().get(key, fallback)


def set_default(key: str, value: str) -> None:
    """Set a config value and persist."""
    config = load_config()
    config[key] = value
    save_config(config)
