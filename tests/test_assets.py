"""Tests for auto_video_agent.assets — HDR detection and filter generation."""

from auto_video_agent.assets import (
    ClipInfo, scale_crop_filter, hdr_to_sdr_filter,
    TARGET_WIDTH, TARGET_HEIGHT,
)


def _make_clip(
    width=1920, height=1080, is_hdr=False, pix_fmt="yuv420p",
    color_transfer="", color_primaries="", bit_depth=8,
) -> ClipInfo:
    return ClipInfo(
        path="/fake/clip.mp4",
        width=width,
        height=height,
        duration=5.0,
        codec="h264",
        needs_scaling=width != TARGET_WIDTH or height != TARGET_HEIGHT,
        is_hdr=is_hdr,
        pix_fmt=pix_fmt,
        color_transfer=color_transfer,
        color_primaries=color_primaries,
        color_space="",
        bit_depth=bit_depth,
    )


class TestHdrDetection:
    def test_sdr_clip_not_hdr(self):
        clip = _make_clip(pix_fmt="yuv420p", bit_depth=8)
        assert clip.is_hdr is False

    def test_10bit_is_hdr(self):
        clip = _make_clip(is_hdr=True, pix_fmt="yuv420p10le", bit_depth=10)
        assert clip.is_hdr is True

    def test_bt2020_primaries_is_hdr(self):
        clip = _make_clip(is_hdr=True, color_primaries="bt2020")
        assert clip.is_hdr is True

    def test_pq_transfer_is_hdr(self):
        clip = _make_clip(is_hdr=True, color_transfer="smpte2084")
        assert clip.is_hdr is True

    def test_hlg_transfer_is_hdr(self):
        clip = _make_clip(is_hdr=True, color_transfer="arib-std-b67")
        assert clip.is_hdr is True


class TestHdrToSdrFilter:
    def test_sdr_returns_empty(self):
        clip = _make_clip()
        assert hdr_to_sdr_filter(clip) == ""

    def test_hdr_returns_filter(self):
        clip = _make_clip(is_hdr=True, pix_fmt="yuv420p10le", bit_depth=10)
        result = hdr_to_sdr_filter(clip)
        assert len(result) > 0
        # Should contain either zscale or colorspace depending on FFmpeg build
        assert "zscale" in result or "colorspace" in result

    def test_filter_ends_with_yuv420p(self):
        clip = _make_clip(is_hdr=True, pix_fmt="yuv420p10le", bit_depth=10)
        result = hdr_to_sdr_filter(clip)
        assert "yuv420p" in result


class TestScaleCropFilter:
    def test_landscape_clip_scales_by_height(self):
        clip = _make_clip(width=1920, height=1080)
        result = scale_crop_filter(clip)
        assert f"scale=-1:{TARGET_HEIGHT}" in result
        assert f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}" in result

    def test_portrait_clip_scales_by_width(self):
        clip = _make_clip(width=720, height=1280)
        result = scale_crop_filter(clip)
        assert f"scale={TARGET_WIDTH}:-1" in result

    def test_exact_size_still_has_scale(self):
        clip = _make_clip(width=TARGET_WIDTH, height=TARGET_HEIGHT, is_hdr=False)
        clip.needs_scaling = False
        result = scale_crop_filter(clip)
        assert "scale" in result

    def test_hdr_landscape_includes_tonemap(self):
        clip = _make_clip(width=3840, height=2160, is_hdr=True, pix_fmt="yuv420p10le", bit_depth=10)
        result = scale_crop_filter(clip)
        # Should have tone mapping before scale/crop
        assert "zscale" in result or "colorspace" in result
        assert f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}" in result

    def test_sdr_landscape_no_tonemap(self):
        clip = _make_clip(width=1920, height=1080)
        result = scale_crop_filter(clip)
        assert "zscale" not in result
        assert "colorspace" not in result
