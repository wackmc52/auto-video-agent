"""
scriptwriter.py — Generates timed video scripts via Claude API.

Takes a validated VideoPlan and produces a structured script with
hook, body, and CTA sections, including per-line timing and caption text.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field

import anthropic
from dotenv import load_dotenv

from .planner import VideoPlan

load_dotenv(override=True)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds


@dataclass
class ScriptLine:
    text: str
    duration: float  # estimated seconds
    section: str     # hook | body | cta
    caption: str     # short caption overlay text


@dataclass
class Script:
    lines: list[ScriptLine] = field(default_factory=list)
    total_duration: float = 0.0

    @property
    def hook_lines(self) -> list[ScriptLine]:
        return [l for l in self.lines if l.section == "hook"]

    @property
    def body_lines(self) -> list[ScriptLine]:
        return [l for l in self.lines if l.section == "body"]

    @property
    def cta_lines(self) -> list[ScriptLine]:
        return [l for l in self.lines if l.section == "cta"]


SYSTEM_PROMPT = """You are a short-form video scriptwriter for an automotive repair shop's social media.
You write scripts for 30-60 second videos on Facebook Reels, Instagram Reels, and TikTok.

Your scripts must:
- Open with a strong hook that stops the scroll (first 3-5 seconds)
- Deliver 2-4 key points concisely in the body
- End with a clear call to action
- Sound natural and conversational when read aloud
- Use simple language — no jargon unless explaining it
- Match the requested tone (friendly, authoritative, urgent, or humorous)

You MUST respond with valid JSON in this exact format:
{
  "lines": [
    {
      "text": "The spoken words for this line",
      "duration": 4.5,
      "section": "hook",
      "caption": "Short caption text"
    }
  ]
}

Rules for the JSON:
- "section" must be one of: "hook", "body", "cta"
- "duration" is estimated seconds to speak the line naturally
- "caption" should be a punchy, shortened version of the text (2-6 words) for on-screen display
- Total duration of all lines should be close to the target duration
- Start with hook lines, then body, then cta
- Do NOT include any text outside the JSON object
"""


def generate_script(plan: VideoPlan, model: str = "") -> Script:
    """Generate a timed script from a video plan using Claude API.

    Args:
        plan: The video plan to generate a script for.
        model: Claude model to use. Falls back to DEFAULT_MODEL.
    """
    model = model or DEFAULT_MODEL
    client = anthropic.Anthropic()
    user_prompt = _build_prompt(plan)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"API call attempt {attempt + 1}/{MAX_RETRIES} using {model}")
            message = client.messages.create(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            response_text = message.content[0].text
            return _parse_response(response_text)

        except (anthropic.APIError, anthropic.APIConnectionError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                logger.warning(f"API error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"API failed after {MAX_RETRIES} attempts: {e}")

    raise last_error


def _build_prompt(plan: VideoPlan) -> str:
    """Build the user prompt from the video plan."""
    points = "\n".join(f"  - {p}" for p in plan.key_points)
    timing = ""
    if plan.timing:
        t = plan.timing
        timing = f"""
Timing targets:
  - Hook: ~{t.hook_seconds}s
  - Body: ~{t.body_seconds}s
  - CTA: ~{t.cta_seconds}s"""

    return f"""Write a script for this video:

Title: {plan.title}
Type: {plan.type}
Tone: {plan.tone}
Target Duration: {plan.duration_target} seconds

Hook idea: {plan.hook}

Key points to cover:
{points}

Call to action: {plan.call_to_action}
{timing}

Generate the script as JSON."""


def _parse_response(response_text: str) -> Script:
    """Parse Claude's JSON response into a Script object."""
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)

    script_lines = []
    total = 0.0

    for item in data["lines"]:
        line = ScriptLine(
            text=item["text"],
            duration=float(item["duration"]),
            section=item["section"],
            caption=item["caption"],
        )
        script_lines.append(line)
        total += line.duration

    return Script(lines=script_lines, total_duration=round(total, 1))


def print_script(script: Script) -> None:
    """Log a formatted script for review."""
    logger.info(f"Script ready ({len(script.lines)} lines, ~{script.total_duration} seconds)")

    current_section = ""
    for line in script.lines:
        if line.section != current_section:
            current_section = line.section
            logger.info(f"  [{current_section.upper()}]")
        logger.info(f"    ({line.duration}s) {line.text}")
        logger.info(f"           Caption: \"{line.caption}\"")
