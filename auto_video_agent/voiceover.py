"""
voiceover.py — Text-to-speech generation using Edge TTS.

Takes a Script and produces an audio file plus word-level timestamps
for caption synchronization.
"""

import logging
import os
from dataclasses import dataclass, field

import edge_tts

from .scriptwriter import Script

logger = logging.getLogger(__name__)

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

    logger.debug(f"Generating voiceover: voice={voice}, rate={rate}, text_len={len(full_text)}")

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

    logger.info(f"Audio saved ({round(total_duration, 1)}s, {round(file_size_kb, 1)}KB)")
    logger.info(f"  Path: {output_path}")
    logger.info(f"  Words tracked: {len(word_timings)}")

    return VoiceoverResult(
        audio_path=output_path,
        duration=round(total_duration, 1),
        word_timings=word_timings,
        file_size_kb=round(file_size_kb, 1),
    )


def load_voice_config(config: dict) -> tuple[str, str]:
    """Load voice and speed settings from parsed config dict."""
    vo = config.get("voiceover", {})
    voice = vo.get("edge_voice", "en-US-GuyNeural")
    speed = vo.get("speed", 1.0)
    # Convert speed multiplier to edge-tts rate format
    rate_pct = int((speed - 1.0) * 100)
    rate = f"{rate_pct:+d}%"
    return voice, rate
