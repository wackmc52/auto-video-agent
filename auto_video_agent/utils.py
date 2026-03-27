"""
utils.py — Shared utility functions.

Consolidates hex color parsing, font loading, and config loading
to avoid duplication across modules.
"""

import logging
import os
from typing import Optional

import yaml
from PIL import ImageFont

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string (#RRGGBB or RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: #{hex_color}")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def load_font(path: str = "", size: int = 64, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a TrueType font, falling back to system fonts if not found.

    Args:
        path: Path to a .ttf file. If empty or not found, uses system fallbacks.
        size: Font size in pixels.
        bold: If True, prefer bold system fallbacks.
    """
    if path:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            logger.debug(f"Font not found at {path}, trying fallbacks")

    fallbacks = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ] if bold else [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for fallback in fallbacks:
        try:
            return ImageFont.truetype(fallback, size)
        except (OSError, IOError):
            continue

    logger.warning("No TrueType fonts found, using PIL default")
    return ImageFont.load_default()


def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return the full project config as a dict.

    Returns an empty dict if the file doesn't exist.
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config if isinstance(config, dict) else {}
    except FileNotFoundError:
        logger.debug(f"Config file not found: {config_path}")
        return {}


def find_project_root(start: Optional[str] = None) -> str:
    """Walk up from start (or cwd) looking for config.yaml to find project root.

    Falls back to cwd if not found.
    """
    current = os.path.abspath(start or os.getcwd())
    for _ in range(10):  # safety limit
        if os.path.exists(os.path.join(current, "config.yaml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start or os.getcwd())
