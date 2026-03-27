"""
branding.py — Logo, intro, and outro generation.

Generates placeholder logos, brand intro sequences (logo reveal + title),
and outro cards (CTA screen) as short video segments.
"""

import logging
import os
import subprocess
from typing import Optional

from PIL import Image, ImageDraw

from .utils import hex_to_rgb, load_font

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def generate_placeholder_logo(
    output_path: str,
    text: str = "AUTO",
    size: int = 300,
    bg_color: str = "#FFD700",
    text_color: str = "#1A1A1A",
) -> str:
    """Generate a simple circular logo with text."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw circle
    bg_rgb = hex_to_rgb(bg_color)
    margin = 10
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=bg_rgb,
    )

    # Draw text
    font = load_font(size=size // 4, bold=True)
    text_rgb = hex_to_rgb(text_color)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((size - tw) // 2, (size - th) // 2 - 5),
        text, font=font, fill=text_rgb,
    )

    img.save(output_path, "PNG")
    return output_path


def generate_intro(
    output_path: str,
    title: str,
    duration: float = 2.5,
    logo_path: Optional[str] = None,
    bg_color_top: str = "#1A1A2E",
    bg_color_bottom: str = "#16213E",
    accent_color: str = "#FFD700",
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = 30,
) -> str:
    """Generate a brand intro video segment."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Gradient background
    _draw_gradient(draw, width, height, bg_color_top, bg_color_bottom)

    # Logo
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_size = 200
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        logo_x = (width - logo_size) // 2
        logo_y = height // 2 - 180
        frame.paste(logo, (logo_x, logo_y), logo)

    # Title text
    title_font = load_font(size=48, bold=True)

    # Word wrap title if too long
    wrapped = _wrap_text(title, title_font, draw, width - 120)
    title_y = height // 2 + 60

    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((width - tw) // 2, title_y),
            line, font=title_font, fill=(255, 255, 255),
            stroke_width=2, stroke_fill=(0, 0, 0),
        )
        title_y += bbox[3] - bbox[1] + 10

    # Accent line under title
    accent_rgb = hex_to_rgb(accent_color)
    line_w = 200
    line_y = title_y + 20
    draw.rectangle(
        [(width - line_w) // 2, line_y, (width + line_w) // 2, line_y + 4],
        fill=accent_rgb,
    )

    # Save frame as PNG then convert to video
    frame_path = output_path.replace(".mp4", "_frame.png")
    frame.save(frame_path, "PNG")

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-t", str(duration),
            "-vf", f"fade=t=in:d=0.5,fade=t=out:st={duration-0.5}:d=0.5",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            output_path,
        ],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        logger.error(f"Intro generation failed: {result.stderr[-300:]}")

    if os.path.exists(frame_path):
        os.remove(frame_path)
    return output_path


def generate_outro(
    output_path: str,
    cta_text: str,
    duration: float = 3.0,
    bg_color_top: str = "#1A1A2E",
    bg_color_bottom: str = "#16213E",
    accent_color: str = "#FFD700",
    logo_path: Optional[str] = None,
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    fps: int = 30,
) -> str:
    """Generate a brand outro video segment."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Gradient background
    _draw_gradient(draw, width, height, bg_color_top, bg_color_bottom)

    accent_rgb = hex_to_rgb(accent_color)

    # Logo at top
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo_size = 150
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        frame.paste(logo, ((width - logo_size) // 2, height // 2 - 250), logo)

    # CTA text
    cta_font = load_font(size=44, bold=True)
    wrapped = _wrap_text(cta_text, cta_font, draw, width - 120)
    y = height // 2 - 40

    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=cta_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((width - tw) // 2, y),
            line, font=cta_font, fill=(255, 255, 255),
            stroke_width=2, stroke_fill=(0, 0, 0),
        )
        y += bbox[3] - bbox[1] + 12

    # "Follow for more" text
    follow_font = load_font(size=32, bold=True)
    follow_text = "FOLLOW FOR MORE"
    bbox = draw.textbbox((0, 0), follow_text, font=follow_font)
    fw = bbox[2] - bbox[0]
    draw.text(
        ((width - fw) // 2, y + 60),
        follow_text, font=follow_font, fill=accent_rgb,
    )

    # Arrow/pointer icon (simple triangle)
    arrow_y = y + 120
    arrow_size = 30
    draw.polygon(
        [
            (width // 2, arrow_y),
            (width // 2 - arrow_size, arrow_y + arrow_size),
            (width // 2 + arrow_size, arrow_y + arrow_size),
        ],
        fill=accent_rgb,
    )

    # Save and convert
    frame_path = output_path.replace(".mp4", "_frame.png")
    frame.save(frame_path, "PNG")

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-t", str(duration),
            "-vf", f"fade=t=in:d=0.5,fade=t=out:st={duration-0.5}:d=0.5",
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            output_path,
        ],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        logger.error(f"Outro generation failed: {result.stderr[-300:]}")

    if os.path.exists(frame_path):
        os.remove(frame_path)
    return output_path


def _draw_gradient(draw: ImageDraw.ImageDraw, width: int, height: int,
                   color_top: str, color_bottom: str) -> None:
    """Draw a vertical gradient on the given ImageDraw."""
    top_rgb = hex_to_rgb(color_top)
    bot_rgb = hex_to_rgb(color_bottom)
    for y in range(height):
        ratio = y / height
        r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * ratio)
        g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * ratio)
        b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _wrap_text(text: str, font, draw, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines
