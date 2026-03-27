"""Tests for auto_video_agent.scriptwriter"""

import json
import pytest

from auto_video_agent.scriptwriter import _parse_response, _build_prompt, Script
from auto_video_agent.planner import VideoPlan, calculate_timing


VALID_JSON = json.dumps({
    "lines": [
        {"text": "Hook line here", "duration": 4.0, "section": "hook", "caption": "Hook!"},
        {"text": "Body point one", "duration": 8.0, "section": "body", "caption": "Point 1"},
        {"text": "Body point two", "duration": 7.0, "section": "body", "caption": "Point 2"},
        {"text": "Call to action", "duration": 5.0, "section": "cta", "caption": "Book now"},
    ]
})


def _make_plan() -> VideoPlan:
    plan = VideoPlan(
        title="Test Brakes Video",
        type="educational_tip",
        tone="friendly",
        hook="Your brakes are squealing?",
        key_points=["Worn pads", "Rotor damage", "Longer stopping distance"],
        call_to_action="Book a brake check today!",
        music="upbeat",
        duration_target=45,
        include_captions=True,
        include_logo=True,
    )
    plan.timing = calculate_timing(plan)
    return plan


class TestParseResponse:
    def test_valid_json(self):
        script = _parse_response(VALID_JSON)
        assert isinstance(script, Script)
        assert len(script.lines) == 4
        assert script.total_duration == 24.0

    def test_markdown_wrapped_json(self):
        wrapped = f"```json\n{VALID_JSON}\n```"
        script = _parse_response(wrapped)
        assert len(script.lines) == 4

    def test_markdown_no_lang(self):
        wrapped = f"```\n{VALID_JSON}\n```"
        script = _parse_response(wrapped)
        assert len(script.lines) == 4

    def test_sections_correct(self):
        script = _parse_response(VALID_JSON)
        assert len(script.hook_lines) == 1
        assert len(script.body_lines) == 2
        assert len(script.cta_lines) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_response("not json at all")

    def test_missing_lines_key(self):
        with pytest.raises(KeyError):
            _parse_response('{"data": []}')


class TestBuildPrompt:
    def test_includes_title(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "Test Brakes Video" in prompt

    def test_includes_hook(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "Your brakes are squealing?" in prompt

    def test_includes_key_points(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "Worn pads" in prompt
        assert "Rotor damage" in prompt
        assert "Longer stopping distance" in prompt

    def test_includes_cta(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "Book a brake check today!" in prompt

    def test_includes_timing(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "Hook:" in prompt
        assert "Body:" in prompt
        assert "CTA:" in prompt

    def test_includes_type_and_tone(self):
        plan = _make_plan()
        prompt = _build_prompt(plan)
        assert "educational_tip" in prompt
        assert "friendly" in prompt
