"""
compositor.py — FFmpeg-based video assembly engine.

Stitches together background/clips, voiceover audio, styled caption overlays,
background music (ducked), logo watermark, and intro/outro into a final 9:16 MP4.
"""

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from .assets import (
    ClipInfo, TARGET_WIDTH, TARGET_HEIGHT,
    generate_gradient_background, scale_crop_filter,
    hdr_to_sdr_filter,
)
from .captions import CaptionTrack, CaptionStyle, render_caption_images
from .voiceover import VoiceoverResult
from .music import get_music_track
from .branding import generate_intro, generate_outro, generate_placeholder_logo

logger = logging.getLogger(__name__)


@dataclass
class CompositorConfig:
    width: int = TARGET_WIDTH
    height: int = TARGET_HEIGHT
    fps: int = 30
    # Caption settings
    caption_style: str = "highlight"
    font_path: str = ""
    font_size: int = 64
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 4
    caption_y: str = "h*0.75"
    # Background
    bg_color_top: str = "#1A1A2E"
    bg_color_bottom: str = "#16213E"
    # Music
    music_volume: float = 0.15
    music_fade_out: float = 2.0
    # Logo
    logo_path: str = ""
    logo_size: int = 100
    logo_position: str = "top-right"
    # Branding
    accent_color: str = "#FFD700"
    include_intro: bool = True
    include_outro: bool = True
    intro_duration: float = 2.5
    outro_duration: float = 3.0


def compose_video(
    voiceover: VoiceoverResult,
    caption_track: Optional[CaptionTrack],
    clips: list[ClipInfo],
    output_path: str,
    config: CompositorConfig,
    music_mood: str = "none",
    video_title: str = "",
    cta_text: str = "",
) -> str:
    """Assemble the final video from all components.

    Full pipeline:
    1. Prepare base video (user clips or gradient background)
    2. Render styled caption images and overlay them
    3. Add logo watermark
    4. Mix voiceover + background music (with ducking)
    5. Prepend intro, append outro
    6. Final render

    Returns the path to the rendered video.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    duration = voiceover.duration

    with tempfile.TemporaryDirectory(prefix="auto_video_") as temp_dir:
        # --- Step 1: Base video ---
        logger.info("Step 1/6: Preparing base video")
        if clips:
            base_video = _sequence_clips(clips, duration, temp_dir, config)
        else:
            base_video = generate_gradient_background(
                os.path.join(temp_dir, "background.mp4"),
                duration=duration,
                color_top=config.bg_color_top,
                color_bottom=config.bg_color_bottom,
                width=config.width,
                height=config.height,
                fps=config.fps,
            )

        # --- Step 2: Render and overlay styled captions ---
        logger.info("Step 2/6: Rendering captions")
        if caption_track and caption_track.count > 0:
            caption_dir = os.path.join(temp_dir, "captions")
            style = CaptionStyle(
                font_path=config.font_path,
                font_size=config.font_size,
                text_color=config.font_color,
                stroke_color=config.stroke_color,
                stroke_width=config.stroke_width,
                canvas_width=config.width,
                canvas_height=config.height,
                style=config.caption_style,
                highlight_color=config.accent_color,
            )
            render_caption_images(caption_track, caption_dir, style)
            captioned_video = _overlay_caption_images(
                base_video, caption_track, temp_dir, config
            )
        else:
            captioned_video = base_video

        # --- Step 3: Add logo watermark ---
        logger.info("Step 3/6: Adding logo watermark")
        logo_path = config.logo_path
        if not logo_path or not os.path.exists(logo_path):
            logo_path = os.path.join(temp_dir, "logo.png")
            generate_placeholder_logo(logo_path, text="AUTO", size=300)

        logoed_video = _add_logo_overlay(
            captioned_video, logo_path, temp_dir, config
        )

        # --- Step 4: Mix audio (voiceover + music) ---
        logger.info("Step 4/6: Mixing audio")
        music_path = None
        if music_mood != "none":
            music_path = get_music_track(music_mood, duration + 5, temp_dir)

        main_video = _mix_audio(
            logoed_video, voiceover.audio_path, music_path,
            duration, temp_dir, config
        )

        # --- Step 5: Prepend intro / append outro ---
        logger.info("Step 5/6: Adding intro/outro")
        segments = []

        if config.include_intro and video_title:
            intro_path = os.path.join(temp_dir, "intro.mp4")
            generate_intro(
                intro_path,
                title=video_title,
                duration=config.intro_duration,
                logo_path=logo_path,
                bg_color_top=config.bg_color_top,
                bg_color_bottom=config.bg_color_bottom,
                accent_color=config.accent_color,
                width=config.width,
                height=config.height,
                fps=config.fps,
            )
            segments.append(intro_path)

        segments.append(main_video)

        if config.include_outro and cta_text:
            outro_path = os.path.join(temp_dir, "outro.mp4")
            generate_outro(
                outro_path,
                cta_text=cta_text,
                duration=config.outro_duration,
                logo_path=logo_path,
                bg_color_top=config.bg_color_top,
                bg_color_bottom=config.bg_color_bottom,
                accent_color=config.accent_color,
                width=config.width,
                height=config.height,
                fps=config.fps,
            )
            segments.append(outro_path)

        # --- Step 6: Final render ---
        logger.info("Step 6/6: Final render")
        if len(segments) > 1:
            _concat_segments(segments, output_path, config)
        else:
            subprocess.run(
                ["ffmpeg", "-y", "-i", main_video, "-c", "copy", output_path],
                capture_output=True, timeout=30,
            )

    # temp_dir auto-cleaned by context manager
    return output_path


def _sequence_clips(
    clips: list[ClipInfo],
    target_duration: float,
    temp_dir: str,
    config: CompositorConfig,
) -> str:
    """Scale, crop, and concatenate user clips to fill target duration."""
    scaled_paths = []

    for i, clip in enumerate(clips):
        scaled_path = os.path.join(temp_dir, f"clip_{i}_scaled.mp4")

        if clip.needs_scaling:
            vf = scale_crop_filter(clip)
        else:
            # Already correct resolution — still need HDR tone mapping if applicable
            tonemap = hdr_to_sdr_filter(clip)
            base_filter = (
                f"scale={config.width}:{config.height}"
                f":force_original_aspect_ratio=decrease,"
                f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            vf = f"{tonemap},{base_filter}" if tonemap else base_filter

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", clip.path,
                "-vf", vf,
                "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p", "-an",
                scaled_path,
            ],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to scale clip {clip.path}: {result.stderr[-200:]}")
        elif os.path.exists(scaled_path):
            scaled_paths.append(scaled_path)

    if not scaled_paths:
        logger.warning("No clips could be processed, using gradient background")
        return generate_gradient_background(
            os.path.join(temp_dir, "background.mp4"),
            duration=target_duration,
            width=config.width, height=config.height,
        )

    concat_path = os.path.join(temp_dir, "concat.txt")
    with open(concat_path, "w") as f:
        for p in scaled_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    output = os.path.join(temp_dir, "base_video.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_path,
            "-t", str(target_duration),
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            output,
        ],
        capture_output=True, timeout=60,
    )
    return output


def _overlay_caption_images(
    video_path: str,
    track: CaptionTrack,
    temp_dir: str,
    config: CompositorConfig,
) -> str:
    """Overlay rendered caption PNG images onto the video at their timed intervals."""
    output = os.path.join(temp_dir, "captioned.mp4")

    cmd = ["ffmpeg", "-y", "-i", video_path]

    for frame in track.frames:
        if frame.image_path and os.path.exists(frame.image_path):
            cmd += ["-i", frame.image_path]

    # Build overlay filter chain
    filters = []
    current = "0:v"
    input_idx = 1

    for frame in track.frames:
        if not frame.image_path or not os.path.exists(frame.image_path):
            continue

        out_label = f"v{input_idx}"
        enable = f"between(t\\,{frame.start:.3f}\\,{frame.end:.3f})"
        filters.append(
            f"[{current}][{input_idx}:v]overlay=0:0:enable='{enable}'[{out_label}]"
        )
        current = out_label
        input_idx += 1

    if not filters:
        return video_path

    filter_complex = ";".join(filters)
    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"[{current}]",
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        output,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        logger.warning(f"Caption overlay failed, continuing without captions: {result.stderr[-200:]}")
        return video_path

    return output


def _add_logo_overlay(
    video_path: str,
    logo_path: str,
    temp_dir: str,
    config: CompositorConfig,
) -> str:
    """Overlay a logo watermark on the video."""
    if not os.path.exists(logo_path):
        return video_path

    output = os.path.join(temp_dir, "logoed.mp4")
    size = config.logo_size
    margin = 30

    pos_map = {
        "top-right": f"W-{size}-{margin}:{margin}",
        "top-left": f"{margin}:{margin}",
        "bottom-right": f"W-{size}-{margin}:H-{size}-{margin}",
        "bottom-left": f"{margin}:H-{size}-{margin}",
    }
    pos = pos_map.get(config.logo_position, pos_map["top-right"])

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex",
        f"[1:v]scale={size}:-1,format=rgba,colorchannelmixer=aa=0.7[logo];"
        f"[0:v][logo]overlay={pos}[out]",
        "-map", "[out]",
        "-c:v", "libx264", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-an",
        output,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        logger.warning(f"Logo overlay failed: {result.stderr[-200:]}")
        return video_path

    return output


def _mix_audio(
    video_path: str,
    voiceover_path: str,
    music_path: Optional[str],
    duration: float,
    temp_dir: str,
    config: CompositorConfig,
) -> str:
    """Combine video with voiceover and optional background music."""
    output = os.path.join(temp_dir, "with_audio.mp4")

    if music_path and os.path.exists(music_path):
        vol = config.music_volume
        fade_out = config.music_fade_out
        fade_start = max(0, duration - fade_out)

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voiceover_path,
            "-i", music_path,
            "-filter_complex",
            f"[2:a]volume={vol},afade=t=in:d=1.5,"
            f"afade=t=out:st={fade_start}:d={fade_out}[bgm];"
            f"[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-t", str(duration),
            output,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", voiceover_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-t", str(duration),
            output,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        raise RuntimeError(f"Audio mixing failed:\n{result.stderr[-500:]}")

    return output


def _concat_segments(
    segments: list[str],
    output_path: str,
    config: CompositorConfig,
) -> None:
    """Concatenate intro + main + outro into final video."""
    temp_dir = os.path.dirname(segments[0])

    # Re-encode all segments to ensure matching formats
    normalized = []
    for i, seg in enumerate(segments):
        norm_path = os.path.join(temp_dir, f"norm_{i}.mp4")

        # Check if segment has audio
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_streams", "-print_format", "json", seg],
            capture_output=True, text=True, timeout=10,
        )
        has_audio = False
        if probe.returncode == 0:
            try:
                has_audio = any(
                    s.get("codec_type") == "audio"
                    for s in json.loads(probe.stdout).get("streams", [])
                )
            except json.JSONDecodeError:
                pass

        # Build command — add silent audio if segment has none
        cmd = ["ffmpeg", "-y", "-i", seg]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

        cmd += [
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-ar", "44100", "-ac", "2",
            "-r", str(config.fps),
            "-s", f"{config.width}x{config.height}",
            "-shortest",
            norm_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(norm_path):
            normalized.append(norm_path)
        else:
            logger.warning(f"Failed to normalize segment {seg}: {result.stderr[-200:]}")
            normalized.append(seg)

    concat_path = os.path.join(temp_dir, "final_concat.txt")
    with open(concat_path, "w") as f:
        for p in normalized:
            f.write(f"file '{os.path.abspath(p)}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_path,
            "-c", "copy",
            output_path,
        ],
        capture_output=True, timeout=60,
    )


def load_compositor_config(config: dict) -> CompositorConfig:
    """Load compositor settings from a parsed config dict."""
    cfg = CompositorConfig()

    video = config.get("video", {})
    cfg.width = video.get("width", cfg.width)
    cfg.height = video.get("height", cfg.height)
    cfg.fps = video.get("fps", cfg.fps)

    captions = config.get("captions", {})
    cfg.font_path = captions.get("font_path", cfg.font_path)
    cfg.font_size = captions.get("font_size", cfg.font_size)
    cfg.font_color = captions.get("font_color", cfg.font_color)
    cfg.stroke_color = captions.get("stroke_color", cfg.stroke_color)
    cfg.stroke_width = captions.get("stroke_width", cfg.stroke_width)
    cfg.caption_style = captions.get("style", cfg.caption_style)

    branding = config.get("branding", {})
    cfg.logo_path = branding.get("logo_path", cfg.logo_path)
    cfg.logo_size = branding.get("logo_size", cfg.logo_size)
    cfg.logo_position = branding.get("logo_position", cfg.logo_position)
    cfg.bg_color_top = branding.get("secondary_color", cfg.bg_color_top)
    cfg.accent_color = branding.get("primary_color", cfg.accent_color)

    music = config.get("music", {})
    cfg.music_volume = music.get("volume", cfg.music_volume)
    cfg.music_fade_out = music.get("fade_out", cfg.music_fade_out)

    return cfg
