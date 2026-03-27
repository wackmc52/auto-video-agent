"""Tests for auto_video_agent.utils"""

import pytest
from auto_video_agent.utils import hex_to_rgb, load_font, load_config


class TestHexToRgb:
    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_without_hash(self):
        assert hex_to_rgb("FF0000") == (255, 0, 0)

    def test_lowercase(self):
        assert hex_to_rgb("#ff8800") == (255, 136, 0)

    def test_mixed_case(self):
        assert hex_to_rgb("#FfD700") == (255, 215, 0)

    def test_invalid_length(self):
        with pytest.raises(ValueError, match="Invalid hex color"):
            hex_to_rgb("#FFF")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            hex_to_rgb("")


class TestLoadFont:
    def test_returns_font_object(self):
        font = load_font(size=32)
        assert font is not None

    def test_fallback_on_missing_path(self):
        font = load_font(path="/nonexistent/font.ttf", size=32)
        assert font is not None

    def test_different_sizes(self):
        font_small = load_font(size=16)
        font_large = load_font(size=64)
        assert font_small is not None
        assert font_large is not None


class TestLoadConfig:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_config(str(tmp_path / "nonexistent.yaml"))
        assert result == {}

    def test_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("video:\n  width: 1080\n  height: 1920\n")
        result = load_config(str(config_file))
        assert result["video"]["width"] == 1080
        assert result["video"]["height"] == 1920
