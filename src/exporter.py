"""
exporter.py — Final render validation and metadata.

Validates output video meets platform specs, reports file info,
and generates a clean output filename.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class ExportResult:
    path: str
    file_size_mb: float
    duration: float
    width: int
    height: int
    valid: bool
    warnings: list[str]


# Platform limits
MAX_FILE_SIZE_MB = 50
MAX_DURATION = 90
MIN_DURATION = 3
EXPECTED_WIDTH = 1080
EXPECTED_HEIGHT = 1920


def generate_output_path(title: str, output_dir: str = "output") -> str:
    """Generate a clean output filename from the video title."""
    slug = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    slug = slug.strip().replace(" ", "_").lower()[:40]
    today = date.today().isoformat()
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, f"{slug}_{today}.mp4")


def validate_output(video_path: str) -> ExportResult:
    """Validate the rendered video meets platform requirements."""
    warnings = []

    if not os.path.exists(video_path):
        return ExportResult(
            path=video_path, file_size_mb=0, duration=0,
            width=0, height=0, valid=False,
            warnings=["Output file does not exist"],
        )

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

    # Probe the output
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
    except Exception as e:
        return ExportResult(
            path=video_path, file_size_mb=round(file_size_mb, 1),
            duration=0, width=0, height=0, valid=False,
            warnings=[f"Failed to probe output: {e}"],
        )

    # Extract video info
    video_stream = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            video_stream = s
            break

    if not video_stream:
        return ExportResult(
            path=video_path, file_size_mb=round(file_size_mb, 1),
            duration=0, width=0, height=0, valid=False,
            warnings=["No video stream found in output"],
        )

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    duration = float(data.get("format", {}).get("duration", 0))

    # Validate
    valid = True

    if file_size_mb > MAX_FILE_SIZE_MB:
        warnings.append(f"File size {file_size_mb:.1f}MB exceeds {MAX_FILE_SIZE_MB}MB limit")
        valid = False

    if duration > MAX_DURATION:
        warnings.append(f"Duration {duration:.1f}s exceeds {MAX_DURATION}s limit")
    elif duration < MIN_DURATION:
        warnings.append(f"Duration {duration:.1f}s is under {MIN_DURATION}s minimum")
        valid = False

    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
        warnings.append(f"Resolution {width}x{height} differs from expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")

    return ExportResult(
        path=video_path,
        file_size_mb=round(file_size_mb, 1),
        duration=round(duration, 1),
        width=width,
        height=height,
        valid=valid,
        warnings=warnings,
    )


def print_export_summary(result: ExportResult) -> None:
    """Print export validation results."""
    status = "READY" if result.valid else "ISSUES FOUND"
    print(f"\n  Export: {status}")
    print(f"   {result.path}")
    print(f"   {result.file_size_mb}MB | {result.duration}s | {result.width}x{result.height}")

    if result.warnings:
        for w in result.warnings:
            print(f"   Warning: {w}")
    else:
        print(f"   All checks passed — ready to upload!")
    print()
