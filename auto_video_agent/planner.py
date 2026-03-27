"""
planner.py — Parses and validates video plan YAML files.

Reads a user-supplied YAML plan, validates required fields,
resolves file paths for clips, and calculates rough timing per section.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

VALID_TYPES = {"educational_tip", "before_after", "common_mistake", "promo"}
VALID_TONES = {"friendly", "authoritative", "urgent", "humorous"}
VALID_MUSIC = {"upbeat", "chill", "dramatic", "none"}


@dataclass
class Clip:
    path: str
    label: str
    duration: Optional[float] = None  # populated after probing


@dataclass
class TimingBreakdown:
    hook_seconds: float
    body_seconds: float
    cta_seconds: float
    total_seconds: float


@dataclass
class VideoPlan:
    title: str
    type: str
    tone: str
    hook: str
    key_points: list[str]
    call_to_action: str
    music: str
    duration_target: int
    include_captions: bool
    include_logo: bool
    user_clips: list[Clip] = field(default_factory=list)
    timing: Optional[TimingBreakdown] = None


class PlanError(Exception):
    """Raised when a video plan is invalid."""
    pass


def load_plan(yaml_path: str, project_root: Optional[str] = None) -> VideoPlan:
    """Load and validate a video plan from a YAML file."""
    path = Path(yaml_path)
    if not path.exists():
        raise PlanError(f"Plan file not found: {yaml_path}")

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise PlanError("Plan file must contain a YAML mapping")

    plan = _validate(raw)

    if project_root:
        _resolve_clip_paths(plan, project_root)

    plan.timing = calculate_timing(plan)

    return plan


def _validate(raw: dict) -> VideoPlan:
    """Validate required fields and return a VideoPlan."""
    errors = []

    # Required string fields
    for field_name in ("title", "hook", "call_to_action"):
        if not raw.get(field_name):
            errors.append(f"Missing required field: {field_name}")

    # Type
    video_type = raw.get("type", "educational_tip")
    if video_type not in VALID_TYPES:
        errors.append(f"Invalid type '{video_type}'. Must be one of: {VALID_TYPES}")

    # Tone
    tone = raw.get("tone", "friendly")
    if tone not in VALID_TONES:
        errors.append(f"Invalid tone '{tone}'. Must be one of: {VALID_TONES}")

    # Music
    music = raw.get("music", "none")
    if music not in VALID_MUSIC:
        errors.append(f"Invalid music '{music}'. Must be one of: {VALID_MUSIC}")

    # Key points
    key_points = raw.get("key_points", [])
    if not isinstance(key_points, list) or len(key_points) == 0:
        errors.append("key_points must be a non-empty list")

    # Duration
    duration = raw.get("duration_target", 45)
    if not isinstance(duration, (int, float)) or duration < 15 or duration > 120:
        errors.append("duration_target must be between 15 and 120 seconds")

    # Clips
    clips = []
    for clip_data in raw.get("user_clips", []):
        if isinstance(clip_data, dict) and "path" in clip_data:
            clips.append(Clip(
                path=clip_data["path"],
                label=clip_data.get("label", ""),
            ))

    if errors:
        raise PlanError("Plan validation failed:\n  - " + "\n  - ".join(errors))

    return VideoPlan(
        title=raw["title"],
        type=video_type,
        tone=tone,
        hook=raw["hook"],
        key_points=key_points,
        call_to_action=raw["call_to_action"],
        music=music,
        duration_target=int(duration),
        include_captions=raw.get("include_captions", True),
        include_logo=raw.get("include_logo", True),
        user_clips=clips,
    )


def _resolve_clip_paths(plan: VideoPlan, project_root: str) -> None:
    """Resolve relative clip paths against the project root."""
    root = Path(project_root)
    for clip in plan.user_clips:
        resolved = root / clip.path
        clip.path = str(resolved)


def calculate_timing(plan: VideoPlan) -> TimingBreakdown:
    """Calculate rough timing breakdown for hook, body, and CTA."""
    total = plan.duration_target

    # Hook: ~10-12% of total, minimum 3s, max 7s
    hook = max(3.0, min(7.0, total * 0.12))

    # CTA: ~12-15% of total, minimum 4s, max 10s
    cta = max(4.0, min(10.0, total * 0.15))

    # Body gets the rest
    body = total - hook - cta

    return TimingBreakdown(
        hook_seconds=round(hook, 1),
        body_seconds=round(body, 1),
        cta_seconds=round(cta, 1),
        total_seconds=total,
    )


def print_plan_summary(plan: VideoPlan) -> None:
    """Log a human-readable summary of the video plan."""
    logger.info(f'Loading plan: "{plan.title}"')
    logger.info(f"  Type: {plan.type} | Tone: {plan.tone} | Target: {plan.duration_target}s")

    if plan.timing:
        t = plan.timing
        logger.info(f"  Timing: Hook {t.hook_seconds}s | Body {t.body_seconds}s | CTA {t.cta_seconds}s")

    if plan.user_clips:
        logger.info(f"  Clips: {len(plan.user_clips)} supplied")
        for clip in plan.user_clips:
            exists = " (found)" if os.path.exists(clip.path) else " (missing)"
            logger.info(f"    - {clip.label or clip.path}{exists}")

    logger.info(f"  Captions: {'yes' if plan.include_captions else 'no'} | Logo: {'yes' if plan.include_logo else 'no'}")
    logger.info(f"  Music: {plan.music}")
