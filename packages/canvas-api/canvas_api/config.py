"""Configuration management for Canvas API credentials."""

import os
from pathlib import Path

from .client import CanvasAPI


def get_config_path() -> Path:
    """Get path to config file."""
    config_dir = Path.home() / ".config" / "canvascli"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config"


def load_config() -> dict:
    """Load configuration from file."""
    config_path = get_config_path()
    config = {}

    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()

    return config


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")


def get_canvas_client() -> CanvasAPI | None:
    """Get a configured Canvas API client, or None if not configured."""
    config = load_config()

    base_url = config.get("CANVAS_URL") or os.environ.get("CANVAS_URL")
    access_token = config.get("CANVAS_TOKEN") or os.environ.get("CANVAS_TOKEN")

    if not base_url or not access_token:
        return None

    return CanvasAPI(base_url, access_token)
