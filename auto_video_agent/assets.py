"""
assets.py — Asset manager for video clips and visual elements.

Validates user-supplied clips, probes metadata, auto-scales/crops to 9:16,
and generates fallback backgrounds when clips are missing.

Handles HDR content (iPhone Dolby Vision, Samsung HDR10+) by auto-detecting
10-bit / BT.2020 sources and tone-mapping to SDR for consistent output.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageDraw

from .utils import hex_to_rgb

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT  # 0.5625

# Pixel formats that indicate 10-bit or higher (HDR-capable)
HDR_PIX_FMTS = {
    "yuv420p10le", "yuv420p10be", "yuv420p12le", "yuv420p12be",
    "yuv422p10le", "yuv422p10be", "yuv444p10le", "yuv444p10be",
    "p010le", "p010be",
}

# Transfer characteristics that indicate HDR
HDR_TRANSFERS = {
    "smpte2084",      # PQ (HDR10, Dolby Vision)
    "arib-std-b67",   # HLG
    "smpte-st-2084",  # alternate naming
}

# Color primaries that indicate wide gamut
HDR_PRIMARIES = {"bt2020"}


@dataclass
class ClipInfo:
    path: str
    width: int
    height: int
    duration: float
    codec: str
    label: str = ""
    needs_scaling: bool = False
    # HDR metadata
    is_hdr: bool = False
    pix_fmt: str = ""
    color_transfer: str = ""
    color_primaries: str = ""
    color_space: str = ""
    bit_depth: int = 8


# Cache the result so we only check once per process
_zscale_available: Optional[bool] = None


def _has_zscale() -> bool:
    """Check if FFmpeg was compiled with libzimg (zscale filter)."""
    global _zscale_available
    if _zscale_available is not None:
        return _zscale_available

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        _zscale_available = "zscale" in result.stdout
    except Exception:
        _zscale_available = False

    if _zscale_available:
        logger.debug("zscale filter available — will use for HDR tone mapping")
    else:
        logger.debug("zscale filter not available — will use colorspace fallback")

    return _zscale_available


def probe_clip(clip_path: str) -> Optional[ClipInfo]:
    """Probe a video clip with ffprobe and return its metadata.

    Detects HDR content by checking pixel format, color transfer
    characteristics, and color primaries.
    """
    if not os.path.exists(clip_path):
        logger.debug(f"Clip not found: {clip_path}")
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
            logger.warning(f"No video stream in {clip_path}")
            return None

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float(data.get("format", {}).get("duration", 0))
        codec = video_stream.get("codec_name", "unknown")
        pix_fmt = video_stream.get("pix_fmt", "")
        color_transfer = video_stream.get("color_transfer", "")
        color_primaries = video_stream.get("color_primaries", "")
        color_space = video_stream.get("color_space", "")

        # Determine bit depth from pixel format
        bit_depth = 8
        if pix_fmt in HDR_PIX_FMTS or "10" in pix_fmt:
            bit_depth = 10
        elif "12" in pix_fmt:
            bit_depth = 12

        # Detect HDR: any of these signals means HDR content
        is_hdr = (
            pix_fmt in HDR_PIX_FMTS
            or color_transfer in HDR_TRANSFERS
            or color_primaries in HDR_PRIMARIES
            or bit_depth > 8
        )

        if is_hdr:
            logger.info(
                f"  HDR detected: {os.path.basename(clip_path)} "
                f"({pix_fmt}, {color_transfer or 'unknown transfer'}, "
                f"{color_primaries or 'unknown primaries'}, {bit_depth}-bit)"
            )

        needs_scaling = width != TARGET_WIDTH or height != TARGET_HEIGHT

        return ClipInfo(
            path=clip_path,
            width=width,
            height=height,
            duration=duration,
            codec=codec,
            needs_scaling=needs_scaling,
            is_hdr=is_hdr,
            pix_fmt=pix_fmt,
            color_transfer=color_transfer,
            color_primaries=color_primaries,
            color_space=color_space,
            bit_depth=bit_depth,
        )
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to probe clip {clip_path}: {e}")
        return None


def hdr_to_sdr_filter(clip_info: ClipInfo) -> str:
    """Return an FFmpeg filter string to tone-map HDR to SDR.

    Uses zscale (libzimg) if available for best quality.
    Falls back to colorspace filter + format conversion otherwise.
    """
    if not clip_info.is_hdr:
        return ""

    if _has_zscale():
        # Best quality: zscale tone mapping
        # linearize → tone map → convert to BT.709 SDR
        tonemap_filter = (
            "zscale=t=linear:npl=100,format=gbrpf32le,"
            "zscale=p=bt709:t=bt709:m=bt709:r=tv,"
            "format=yuv420p"
        )
        logger.debug(f"Using zscale tone mapping for {os.path.basename(clip_info.path)}")
    else:
        # Fallback: colorspace filter (lower quality but widely available)
        tonemap_filter = (
            "colorspace=all=bt709:iall=bt2020:fast=1,"
            "format=yuv420p"
        )
        logger.debug(f"Using colorspace fallback for {os.path.basename(clip_info.path)}")

    return tonemap_filter


def scale_crop_filter(clip_info: ClipInfo) -> str:
    """Return an FFmpeg filter string to scale and crop a clip to 9:16.

    If the clip is HDR, prepends tone-mapping filters to convert to SDR
    before scaling. This prevents washed-out colors and pixel format errors.
    """
    filters = []

    # HDR → SDR tone mapping (if needed)
    tonemap = hdr_to_sdr_filter(clip_info)
    if tonemap:
        filters.append(tonemap)

    # Scale and crop
    src_ratio = clip_info.width / clip_info.height

    if src_ratio > TARGET_RATIO:
        # Source is wider — scale by height, crop width
        filters.append(
            f"scale=-1:{TARGET_HEIGHT},"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
        )
    else:
        # Source is taller or same — scale by width, crop height
        filters.append(
            f"scale={TARGET_WIDTH}:-1,"
            f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}"
        )

    return ",".join(filters)


def generate_color_background(
    output_path: str,
    duration: float,
    color: str = "1A1A1A",
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = 30,
) -> str:
    """Generate a solid color video background using FFmpeg."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x{color}:s={width}x{height}:r={fps}:d={duration}",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            output_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        logger.error(f"Failed to generate color background: {result.stderr[-300:]}")

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

    top_rgb = hex_to_rgb(color_top)
    bot_rgb = hex_to_rgb(color_bottom)

    for y in range(height):
        ratio = y / height
        r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * ratio)
        g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * ratio)
        b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    img_path = output_path.replace(".mp4", "_bg.png")
    img.save(img_path)

    # Convert to video
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_path,
            "-t", str(duration),
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            output_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        logger.error(f"Failed to generate gradient background: {result.stderr[-300:]}")

    # Clean up temp image
    if os.path.exists(img_path):
        os.remove(img_path)

    return output_path


def prepare_clips(
    clip_paths: list[dict],
    project_root: str,
) -> list[ClipInfo]:
    """Validate and prepare all user clips. Returns list of ClipInfo.

    Clips that don't exist are skipped (compositor will use backgrounds instead).
    Logs HDR detection results so the user knows tone mapping will be applied.
    """
    prepared = []
    hdr_count = 0

    for clip_data in clip_paths:
        path = clip_data.get("path", "")
        label = clip_data.get("label", "")

        # Try absolute, then relative to project root
        if not os.path.isabs(path):
            path = os.path.join(project_root, path)

        info = probe_clip(path)
        if info:
            info.label = label
            if info.is_hdr:
                hdr_count += 1
            prepared.append(info)

    if hdr_count > 0:
        logger.info(
            f"  {hdr_count} HDR clip(s) detected — will auto tone-map to SDR"
        )

    return prepared
