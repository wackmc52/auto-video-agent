"""Tests for auto_video_agent.exporter"""

import re
from datetime import date

from auto_video_agent.exporter import generate_output_path


class TestGenerateOutputPath:
    def test_creates_slug(self, tmp_path):
        path = generate_output_path("Why Your Car Shakes", output_dir=str(tmp_path))
        filename = path.split("/")[-1]
        assert "why_your_car_shakes" in filename
        assert filename.endswith(".mp4")

    def test_includes_date(self, tmp_path):
        path = generate_output_path("Test", output_dir=str(tmp_path))
        today = date.today().isoformat()
        assert today in path

    def test_strips_special_chars(self, tmp_path):
        path = generate_output_path("The #1 Oil Change Mistake!!!", output_dir=str(tmp_path))
        filename = path.split("/")[-1]
        # Should not contain # or !
        assert "#" not in filename
        assert "!" not in filename

    def test_truncates_long_title(self, tmp_path):
        long_title = "A" * 100
        path = generate_output_path(long_title, output_dir=str(tmp_path))
        filename = path.split("/")[-1]
        # Slug portion should be max 40 chars (before _date.mp4)
        slug_part = filename.split("_" + date.today().isoformat())[0]
        assert len(slug_part) <= 40

    def test_creates_output_dir(self, tmp_path):
        out_dir = tmp_path / "new_output"
        path = generate_output_path("Test", output_dir=str(out_dir))
        assert out_dir.exists()

    def test_filename_format(self, tmp_path):
        path = generate_output_path("Brake Check", output_dir=str(tmp_path))
        filename = path.split("/")[-1]
        # Should match pattern: slug_YYYY-MM-DD.mp4
        assert re.match(r"[a-z0-9_]+_\d{4}-\d{2}-\d{2}\.mp4", filename)
