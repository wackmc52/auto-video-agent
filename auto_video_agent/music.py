"""
music.py — Background music manager.

Generates simple royalty-free background tracks using FFmpeg's audio
synthesis, or loads user-supplied tracks from assets/music/.
"""

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Mood-based synthesis parameters (frequency, tempo feel)
MOOD_PRESETS = {
    "upbeat": {
        "notes": [
            (329.63, 0.4),  # E4
            (392.00, 0.4),  # G4
            (440.00, 0.4),  # A4
            (523.25, 0.4),  # C5
            (440.00, 0.4),  # A4
            (392.00, 0.4),  # G4
            (329.63, 0.4),  # E4
            (293.66, 0.8),  # D4
        ],
        "base_freq": 110,  # bass drone
    },
    "chill": {
        "notes": [
            (261.63, 0.8),  # C4
            (329.63, 0.8),  # E4
            (392.00, 0.8),  # G4
            (329.63, 0.8),  # E4
        ],
        "base_freq": 82.41,
    },
    "dramatic": {
        "notes": [
            (220.00, 0.6),  # A3
            (233.08, 0.6),  # Bb3
            (261.63, 0.6),  # C4
            (220.00, 0.6),  # A3
            (196.00, 1.0),  # G3
        ],
        "base_freq": 55,
    },
}


def get_music_track(
    mood: str,
    duration: float,
    output_dir: str = "output",
    music_dir: str = "assets/music",
) -> Optional[str]:
    """Get a background music track for the given mood.

    First checks assets/music/ for user-supplied tracks matching the mood name.
    If none found, generates a simple synthesized ambient track.
    """
    # Check for user-supplied tracks
    user_track = _find_user_track(mood, music_dir)
    if user_track:
        logger.info(f"Using user-supplied music track: {user_track}")
        return user_track

    if mood == "none":
        return None

    # Generate a synthesized track
    logger.debug(f"Generating synthesized {mood} track ({duration}s)")
    return generate_ambient_track(mood, duration, output_dir)


def _find_user_track(mood: str, music_dir: str) -> Optional[str]:
    """Look for a user-supplied music file matching the mood."""
    if not os.path.exists(music_dir):
        return None

    for ext in (".mp3", ".wav", ".aac", ".m4a"):
        path = os.path.join(music_dir, f"{mood}{ext}")
        if os.path.exists(path):
            return path

    # Also check for any file with mood in the name
    for f in os.listdir(music_dir):
        if mood.lower() in f.lower() and f.endswith((".mp3", ".wav", ".aac", ".m4a")):
            return os.path.join(music_dir, f)

    return None


def generate_ambient_track(
    mood: str,
    duration: float,
    output_dir: str,
) -> str:
    """Generate a simple ambient background track using FFmpeg synthesis."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"_bgm_{mood}.mp3")

    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["chill"])
    base_freq = preset["base_freq"]

    pad_freq1 = base_freq * 2
    pad_freq2 = base_freq * 3
    pad_freq3 = base_freq * 4

    filter_parts = [
        f"sine=f={base_freq}:d={duration},volume=0.15,afade=t=in:d=2,afade=t=out:st={duration-2}:d=2[bass]",
        f"sine=f={pad_freq1}:d={duration},volume=0.08,afade=t=in:d=3,afade=t=out:st={duration-2}:d=2[pad1]",
        f"sine=f={pad_freq2 * 1.003}:d={duration},volume=0.06,afade=t=in:d=3,afade=t=out:st={duration-2}:d=2[pad2]",
        f"sine=f={pad_freq3}:d={duration},volume=0.04,afade=t=in:d=4,afade=t=out:st={duration-3}:d=3[shimmer]",
        "[bass][pad1]amix=inputs=2[mix1]",
        "[mix1][pad2]amix=inputs=2[mix2]",
        "[mix2][shimmer]amix=inputs=2,volume=2.0[out]",
    ]

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        logger.warning(f"Ambient track generation failed, falling back to simple drone")
        return _generate_simple_drone(base_freq, duration, output_path)

    return output_path


def _generate_simple_drone(freq: float, duration: float, output_path: str) -> str:
    """Fallback: generate a simple sine drone."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=f={freq}:d={duration}",
            "-af", f"volume=0.1,afade=t=in:d=2,afade=t=out:st={duration-2}:d=2",
            "-c:a", "libmp3lame", "-b:a", "128k",
            output_path,
        ],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        logger.error(f"Even simple drone failed: {result.stderr[-200:]}")
    return output_path
