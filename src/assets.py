"""
assets.py — Asset manager for video clips and visual elements.

Validates user-supplied clips, probes metadata, auto-scales/crops to 9:16,
and generates fallback backgrounds when clips are missing.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw


TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT  # 0.5625


@dataclass
class ClipInfo:
    path: str
    width: int
    height: int
    duration: float
    codec: str
    label: str = ""
    needs_scaling: bool = False


def probe_clip(clip_path: str) -> Optional[ClipInfo]:
    """Probe a video clip with ffprobe and return its metadata."""
    if not os.path.exists(clip_path):
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                clip_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)

        video_stream = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                video_stream = s
                break

        if not video_stream:
            return None

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float(data.get("format", {}).get("duration", 0))
        codec = video_stream.get("codec_name", "unknown")

        needs_scaling = width != TARGET_WIDTH or height != TARGET_HEIGHT

        return ClipInfo(
            path=clip_path,
            width=width,
            height=height,
            duration=duration,
            codec=codec,
            needs_scaling=needs_scaling,
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        return None


def scale_crop_filter(clip_info: ClipInfo) -> str:
    """Return an FFmpeg filter string to scale and crop a clip to 9:16.

    Strategy: scale to fill the target frame, then center-crop.
    """
    src_ratio = clip_info.width / clip_info.height

    if src_ratio > TARGET_RATIO:
        # Source is wider — scale by height, crop width
        return (
            f"scale=-1:{TARGET_HEIGHT},"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
        )
    else:
        # Source is taller or same — scale by width, crop height
        return (
            f"scale={TARGET_WIDTH}:-1,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
        )


def generate_color_background(
    output_path: str,
    duration: float,
    color: str = "1A1A1A",
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = 30,
) -> str:
    """Generate a solid color video background using FFmpeg.

    Returns the path to the generated video.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x{color}:s={width}x{height}:r={fps}:d={duration}",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True, timeout=30,
    )

    return output_path


def generate_gradient_background(
    output_path: str,
    duration: float,
    color_top: str = "#1A1A2E",
    color_bottom: str = "#16213E",
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = 30,
) -> str:
    """Generate a vertical gradient background image, then make it a video."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Create gradient image with Pillow
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    top_rgb = _hex_to_rgb(color_top)
    bot_rgb = _hex_to_rgb(color_bottom)

    for y in range(height):
        ratio = y / height
        r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * ratio)
        g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * ratio)
        b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    img_path = output_path.replace(".mp4", "_bg.png")
    img.save(img_path)

    # Convert to video
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-t", str(duration),
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            output_path,
        ],
        capture_output=True, timeout=30,
    )

    # Clean up temp image
    if os.path.exists(img_path):
        os.remove(img_path)

    return output_path


def prepare_clips(
    clip_paths: list[dict],
    project_root: str,
    fallback_duration: float = 5.0,
) -> list[ClipInfo]:
    """Validate and prepare all user clips. Returns list of ClipInfo.

    Clips that don't exist are skipped (compositor will use backgrounds instead).
    """
    prepared = []

    for clip_data in clip_paths:
        path = clip_data.get("path", "")
        label = clip_data.get("label", "")

        # Try absolute, then relative to project root
        if not os.path.isabs(path):
            path = os.path.join(project_root, path)

        info = probe_clip(path)
        if info:
            info.label = label
            prepared.append(info)

    return prepared


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )
