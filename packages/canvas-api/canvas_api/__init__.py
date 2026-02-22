"""Canvas LMS API client library."""

from .client import CanvasAPI
from .config import get_canvas_client, get_config_path, load_config, save_config

__version__ = "0.1.0"

__all__ = [
    "CanvasAPI",
    "get_canvas_client",
    "get_config_path",
    "load_config",
    "save_config",
]
