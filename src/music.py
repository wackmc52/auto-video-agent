"""
music.py — Background music manager.

Generates simple royalty-free background tracks using FFmpeg's audio
synthesis, or loads user-supplied tracks from assets/music/.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


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
        return user_track

    if mood == "none":
        return None

    # Generate a synthesized track
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
    """Generate a simple ambient background track using FFmpeg synthesis.

    Creates a layered pad sound with a low drone and gentle melodic tones.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"_bgm_{mood}.mp3")

    preset = MOOD_PRESETS.get(mood, MOOD_PRESETS["chill"])
    base_freq = preset["base_freq"]

    # Build a multi-layered ambient pad using FFmpeg's sine generator
    # Layer 1: Low bass drone
    # Layer 2: Mid pad chord
    # Layer 3: Light melodic sequence

    # Create a warm pad by mixing detuned sines
    pad_freq1 = base_freq * 2  # octave up
    pad_freq2 = base_freq * 3  # fifth above that
    pad_freq3 = base_freq * 4  # two octaves up

    filter_parts = [
        # Bass drone with slow volume swell
        f"sine=f={base_freq}:d={duration},volume=0.15,afade=t=in:d=2,afade=t=out:st={duration-2}:d=2[bass]",
        # Pad layer 1
        f"sine=f={pad_freq1}:d={duration},volume=0.08,afade=t=in:d=3,afade=t=out:st={duration-2}:d=2[pad1]",
        # Pad layer 2 (slightly detuned for warmth)
        f"sine=f={pad_freq2 * 1.003}:d={duration},volume=0.06,afade=t=in:d=3,afade=t=out:st={duration-2}:d=2[pad2]",
        # High shimmer
        f"sine=f={pad_freq3}:d={duration},volume=0.04,afade=t=in:d=4,afade=t=out:st={duration-3}:d=3[shimmer]",
        # Mix all layers
        "[bass][pad1]amix=inputs=2[mix1]",
        "[mix1][pad2]amix=inputs=2[mix2]",
        "[mix2][shimmer]amix=inputs=2,volume=2.0[out]",
    ]

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-b:a", "128k",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        # Fallback: simple sine drone
        return _generate_simple_drone(base_freq, duration, output_path)

    return output_path


def _generate_simple_drone(freq: float, duration: float, output_path: str) -> str:
    """Fallback: generate a simple sine drone."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=f={freq}:d={duration}",
            "-af", f"volume=0.1,afade=t=in:d=2,afade=t=out:st={duration-2}:d=2",
            "-c:a", "libmp3lame", "-b:a", "128k",
            output_path,
        ],
        capture_output=True, timeout=15,
    )
    return output_path
