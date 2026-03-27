"""
captions.py — Generates timed caption segments from word-level timestamps.

Groups words into short caption frames (2-4 words) with precise timing.
Supports two rendering modes:
  - "drawtext": FFmpeg native text overlay (fast, basic styling)
  - "image": Pillow-rendered PNG overlays (rich styling, highlight effect)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml
from PIL import Image, ImageDraw, ImageFont

from .voiceover import WordTiming


@dataclass
class CaptionFrame:
    text: str
    start: float    # seconds
    end: float      # seconds
    duration: float  # seconds
    image_path: Optional[str] = None  # path to rendered PNG (image mode)
    words: list[str] = field(default_factory=list)  # individual words for highlight


@dataclass
class CaptionTrack:
    frames: list[CaptionFrame] = field(default_factory=list)
    style: str = "highlight"  # highlight | pop | simple

    @property
    def count(self) -> int:
        return len(self.frames)


@dataclass
class CaptionStyle:
    font_path: str = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_size: int = 64
    text_color: str = "#FFFFFF"
    highlight_color: str = "#FFD700"  # gold highlight for current word group
    bg_color: str = "#000000"
    bg_opacity: int = 160  # 0-255
    stroke_color: str = "#000000"
    stroke_width: int = 4
    padding: int = 20
    border_radius: int = 16
    canvas_width: int = 1080
    canvas_height: int = 1920
    y_position: float = 0.72  # relative vertical position (0=top, 1=bottom)
    style: str = "highlight"  # highlight | pop | simple


def generate_captions(
    word_timings: list[WordTiming],
    words_per_frame: int = 3,
) -> CaptionTrack:
    """Group word timings into caption frames of N words each."""
    if not word_timings:
        return CaptionTrack()

    frames = []
    i = 0

    while i < len(word_timings):
        chunk = word_timings[i:i + words_per_frame]
        text = " ".join(w.word for w in chunk)
        start = chunk[0].start
        end = chunk[-1].end

        frames.append(CaptionFrame(
            text=text,
            start=round(start, 3),
            end=round(end, 3),
            duration=round(end - start, 3),
            words=[w.word for w in chunk],
        ))

        i += words_per_frame

    return CaptionTrack(frames=frames)


def render_caption_images(
    track: CaptionTrack,
    output_dir: str,
    style: Optional[CaptionStyle] = None,
) -> CaptionTrack:
    """Render each caption frame as a transparent PNG image with styled text.

    Returns the same CaptionTrack with image_path populated on each frame.
    """
    if style is None:
        style = CaptionStyle()

    os.makedirs(output_dir, exist_ok=True)

    font = _load_font(style.font_path, style.font_size)

    for i, frame in enumerate(track.frames):
        img_path = os.path.join(output_dir, f"caption_{i:04d}.png")

        if style.style == "highlight":
            img = _render_highlight_frame(frame, font, style)
        elif style.style == "pop":
            img = _render_pop_frame(frame, font, style)
        else:
            img = _render_simple_frame(frame, font, style)

        img.save(img_path, "PNG")
        frame.image_path = img_path

    track.style = style.style
    return track


def _render_highlight_frame(
    frame: CaptionFrame,
    font: ImageFont.FreeTypeFont,
    style: CaptionStyle,
) -> Image.Image:
    """Render a caption with a rounded background pill and white text.

    The text sits on a semi-transparent dark pill, centered on the canvas.
    """
    canvas = Image.new("RGBA", (style.canvas_width, style.canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    text = frame.text.upper()

    # Measure text
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=style.stroke_width)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Background pill
    pad = style.padding
    pill_w = text_w + pad * 2
    pill_h = text_h + pad * 2
    pill_x = (style.canvas_width - pill_w) // 2
    pill_y = int(style.canvas_height * style.y_position) - pill_h // 2

    # Draw rounded rectangle background
    bg_r, bg_g, bg_b = _hex_to_rgb(style.bg_color)
    _draw_rounded_rect(
        draw,
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=style.border_radius,
        fill=(bg_r, bg_g, bg_b, style.bg_opacity),
    )

    # Draw text centered in pill
    text_x = pill_x + pad
    text_y = pill_y + pad

    # Stroke/outline
    stroke_r, stroke_g, stroke_b = _hex_to_rgb(style.stroke_color)
    draw.text(
        (text_x, text_y), text, font=font,
        fill=_hex_to_rgb(style.text_color),
        stroke_width=style.stroke_width,
        stroke_fill=(stroke_r, stroke_g, stroke_b),
    )

    return canvas


def _render_pop_frame(
    frame: CaptionFrame,
    font: ImageFont.FreeTypeFont,
    style: CaptionStyle,
) -> Image.Image:
    """Render a 'pop' style caption — large bold text with a colored shadow, no pill."""
    canvas = Image.new("RGBA", (style.canvas_width, style.canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    text = frame.text.upper()

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=style.stroke_width)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = (style.canvas_width - text_w) // 2
    text_y = int(style.canvas_height * style.y_position) - text_h // 2

    # Shadow offset
    shadow_offset = 4
    shadow_color = _hex_to_rgb(style.highlight_color)
    draw.text(
        (text_x + shadow_offset, text_y + shadow_offset), text, font=font,
        fill=shadow_color,
        stroke_width=style.stroke_width,
        stroke_fill=shadow_color,
    )

    # Main text
    stroke_rgb = _hex_to_rgb(style.stroke_color)
    draw.text(
        (text_x, text_y), text, font=font,
        fill=_hex_to_rgb(style.text_color),
        stroke_width=style.stroke_width,
        stroke_fill=stroke_rgb,
    )

    return canvas


def _render_simple_frame(
    frame: CaptionFrame,
    font: ImageFont.FreeTypeFont,
    style: CaptionStyle,
) -> Image.Image:
    """Render plain white text with black stroke — no background."""
    canvas = Image.new("RGBA", (style.canvas_width, style.canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    text = frame.text.upper()

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=style.stroke_width)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = (style.canvas_width - text_w) // 2
    text_y = int(style.canvas_height * style.y_position) - text_h // 2

    stroke_rgb = _hex_to_rgb(style.stroke_color)
    draw.text(
        (text_x, text_y), text, font=font,
        fill=_hex_to_rgb(style.text_color),
        stroke_width=style.stroke_width,
        stroke_fill=stroke_rgb,
    )

    return canvas


def caption_images_to_ffmpeg_overlay(track: CaptionTrack) -> str:
    """Build FFmpeg filter to overlay caption PNGs at their timed intervals.

    Each caption image is added as an input and overlaid with enable='between(t,start,end)'.
    Returns a tuple of (extra_inputs, filter_string) to be added to the FFmpeg command.
    """
    # This is handled directly in compositor.py since it needs to manage inputs
    pass


def load_caption_config(config_path: str = "config.yaml") -> CaptionStyle:
    """Load caption styling from config file."""
    style = CaptionStyle()
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        cap = config.get("captions", {})
        style.font_path = cap.get("font_path", style.font_path)
        style.font_size = cap.get("font_size", style.font_size)
        style.text_color = cap.get("font_color", style.text_color)
        style.stroke_color = cap.get("stroke_color", style.stroke_color)
        style.stroke_width = cap.get("stroke_width", style.stroke_width)
        style.style = cap.get("style", style.style)

        # If font_path doesn't exist, fallback to system font
        if not os.path.exists(style.font_path):
            style.font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    except FileNotFoundError:
        pass
    return style


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font, falling back to default if not found."""
    try:
        return ImageFont.truetype(font_path, size)
    except (OSError, IOError):
        # Fallback to system font
        for fallback in [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            try:
                return ImageFont.truetype(fallback, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    bbox: tuple,
    radius: int,
    fill: tuple,
) -> None:
    """Draw a rounded rectangle on a PIL ImageDraw."""
    x1, y1, x2, y2 = bbox
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def print_captions_summary(track: CaptionTrack) -> None:
    """Print a summary of the generated captions."""
    has_images = any(f.image_path for f in track.frames)
    mode = f"styled ({track.style})" if has_images else "timed"
    print(f"\n  Captions generated ({track.count} frames, {mode})")
    if track.frames:
        print(f"   Time span: {track.frames[0].start}s - {track.frames[-1].end}s")
        for frame in track.frames[:5]:
            print(f"    [{frame.start:.1f}s - {frame.end:.1f}s] \"{frame.text}\"")
        if track.count > 5:
            print(f"    ... and {track.count - 5} more")
    print()
