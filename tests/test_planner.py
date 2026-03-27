"""Tests for auto_video_agent.planner"""

import pytest
import yaml

from auto_video_agent.planner import load_plan, calculate_timing, PlanError, VideoPlan


VALID_PLAN = {
    "title": "Test Video",
    "type": "educational_tip",
    "tone": "friendly",
    "hook": "Did you know this?",
    "key_points": ["Point one", "Point two", "Point three"],
    "call_to_action": "Book now!",
    "music": "upbeat",
    "duration_target": 45,
    "include_captions": True,
    "include_logo": True,
}


def _write_plan(tmp_path, data):
    plan_file = tmp_path / "test_plan.yaml"
    plan_file.write_text(yaml.dump(data))
    return str(plan_file)


class TestLoadPlan:
    def test_valid_plan(self, tmp_path):
        path = _write_plan(tmp_path, VALID_PLAN)
        plan = load_plan(path)
        assert plan.title == "Test Video"
        assert plan.type == "educational_tip"
        assert len(plan.key_points) == 3
        assert plan.timing is not None

    def test_missing_title(self, tmp_path):
        data = {**VALID_PLAN}
        del data["title"]
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Missing required field: title"):
            load_plan(path)

    def test_missing_hook(self, tmp_path):
        data = {**VALID_PLAN}
        del data["hook"]
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Missing required field: hook"):
            load_plan(path)

    def test_missing_cta(self, tmp_path):
        data = {**VALID_PLAN}
        del data["call_to_action"]
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Missing required field: call_to_action"):
            load_plan(path)

    def test_invalid_type(self, tmp_path):
        data = {**VALID_PLAN, "type": "invalid_type"}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Invalid type"):
            load_plan(path)

    def test_invalid_tone(self, tmp_path):
        data = {**VALID_PLAN, "tone": "angry"}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Invalid tone"):
            load_plan(path)

    def test_invalid_music(self, tmp_path):
        data = {**VALID_PLAN, "music": "metal"}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="Invalid music"):
            load_plan(path)

    def test_empty_key_points(self, tmp_path):
        data = {**VALID_PLAN, "key_points": []}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="key_points must be a non-empty list"):
            load_plan(path)

    def test_duration_too_short(self, tmp_path):
        data = {**VALID_PLAN, "duration_target": 5}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="duration_target must be between"):
            load_plan(path)

    def test_duration_too_long(self, tmp_path):
        data = {**VALID_PLAN, "duration_target": 300}
        path = _write_plan(tmp_path, data)
        with pytest.raises(PlanError, match="duration_target must be between"):
            load_plan(path)

    def test_file_not_found(self):
        with pytest.raises(PlanError, match="Plan file not found"):
            load_plan("/nonexistent/path.yaml")

    def test_defaults_applied(self, tmp_path):
        minimal = {
            "title": "Minimal",
            "hook": "Hook here",
            "key_points": ["One point"],
            "call_to_action": "CTA here",
        }
        path = _write_plan(tmp_path, minimal)
        plan = load_plan(path)
        assert plan.type == "educational_tip"
        assert plan.tone == "friendly"
        assert plan.music == "none"
        assert plan.include_captions is True

    def test_clips_parsed(self, tmp_path):
        data = {
            **VALID_PLAN,
            "user_clips": [
                {"path": "clips/test.mp4", "label": "test clip"},
                {"path": "clips/other.mp4"},
            ],
        }
        path = _write_plan(tmp_path, data)
        plan = load_plan(path)
        assert len(plan.user_clips) == 2
        assert plan.user_clips[0].label == "test clip"
        assert plan.user_clips[1].label == ""


class TestCalculateTiming:
    def test_45s_plan(self):
        plan = VideoPlan(
            title="T", type="educational_tip", tone="friendly",
            hook="H", key_points=["P"], call_to_action="C",
            music="none", duration_target=45,
            include_captions=True, include_logo=True,
        )
        timing = calculate_timing(plan)
        assert timing.total_seconds == 45
        assert timing.hook_seconds >= 3.0
        assert timing.cta_seconds >= 4.0
        assert abs(timing.hook_seconds + timing.body_seconds + timing.cta_seconds - 45) < 0.5

    def test_short_plan(self):
        plan = VideoPlan(
            title="T", type="educational_tip", tone="friendly",
            hook="H", key_points=["P"], call_to_action="C",
            music="none", duration_target=15,
            include_captions=True, include_logo=True,
        )
        timing = calculate_timing(plan)
        assert timing.total_seconds == 15
        assert timing.hook_seconds >= 3.0
        assert timing.cta_seconds >= 4.0

    def test_long_plan(self):
        plan = VideoPlan(
            title="T", type="educational_tip", tone="friendly",
            hook="H", key_points=["P"], call_to_action="C",
            music="none", duration_target=120,
            include_captions=True, include_logo=True,
        )
        timing = calculate_timing(plan)
        assert timing.total_seconds == 120
        assert timing.body_seconds > timing.hook_seconds
