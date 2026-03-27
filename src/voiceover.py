"""
voiceover.py — Text-to-speech generation using Edge TTS.

Takes a Script and produces an audio file plus word-level timestamps
for caption synchronization.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import edge_tts
import yaml

from .scriptwriter import Script


TICKS_PER_SECOND = 10_000_000  # Edge TTS uses 100-nanosecond ticks


@dataclass
class WordTiming:
    word: str
    start: float   # seconds
    end: float     # seconds
    duration: float # seconds


@dataclass
class VoiceoverResult:
    audio_path: str
    duration: float
    word_timings: list[WordTiming] = field(default_factory=list)
    file_size_kb: float = 0.0


def generate_voiceover(
    script: Script,
    output_path: str,
    voice: str = "en-US-GuyNeural",
    rate: str = "+0%",
) -> VoiceoverResult:
    """Generate voiceover audio from a script with word-level timestamps."""
    # Combine all script lines into one text block
    full_text = " ".join(line.text for line in script.lines)

    # Generate audio with word boundary metadata
    comm = edge_tts.Communicate(
        full_text,
        voice=voice,
        rate=rate,
        boundary="WordBoundary",
    )

    # Collect audio chunks and word boundaries
    audio_data = bytearray()
    word_timings = []

    for chunk in comm.stream_sync():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start_sec = chunk["offset"] / TICKS_PER_SECOND
            dur_sec = chunk["duration"] / TICKS_PER_SECOND
            word_timings.append(WordTiming(
                word=chunk["text"],
                start=round(start_sec, 3),
                end=round(start_sec + dur_sec, 3),
                duration=round(dur_sec, 3),
            ))

    # Write audio file
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    # Calculate total duration from last word timing
    total_duration = 0.0
    if word_timings:
        last = word_timings[-1]
        total_duration = last.end + 0.5  # add small tail buffer

    file_size_kb = len(audio_data) / 1024

    return VoiceoverResult(
        audio_path=output_path,
        duration=round(total_duration, 1),
        word_timings=word_timings,
        file_size_kb=round(file_size_kb, 1),
    )


def load_voice_config(config_path: str = "config.yaml") -> tuple[str, str]:
    """Load voice and speed settings from config."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        vo = config.get("voiceover", {})
        voice = vo.get("edge_voice", "en-US-GuyNeural")
        speed = vo.get("speed", 1.0)
        # Convert speed multiplier to edge-tts rate format
        rate_pct = int((speed - 1.0) * 100)
        rate = f"{rate_pct:+d}%"
        return voice, rate
    except FileNotFoundError:
        return "en-US-GuyNeural", "+0%"


def print_voiceover_summary(result: VoiceoverResult) -> None:
    """Print a summary of the generated voiceover."""
    print(f"\n  Audio saved ({result.duration}s, {result.file_size_kb}KB)")
    print(f"   Path: {result.audio_path}")
    print(f"   Words tracked: {len(result.word_timings)}")
    print()
