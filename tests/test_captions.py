"""Tests for auto_video_agent.captions"""

from auto_video_agent.captions import generate_captions, CaptionTrack
from auto_video_agent.voiceover import WordTiming


def _make_timings(n: int) -> list[WordTiming]:
    """Create n sequential word timings, each 0.3s long."""
    timings = []
    for i in range(n):
        start = i * 0.35
        dur = 0.3
        timings.append(WordTiming(
            word=f"word{i}",
            start=round(start, 3),
            end=round(start + dur, 3),
            duration=dur,
        ))
    return timings


class TestGenerateCaptions:
    def test_empty_input(self):
        track = generate_captions([])
        assert isinstance(track, CaptionTrack)
        assert track.count == 0

    def test_groups_by_3(self):
        timings = _make_timings(9)
        track = generate_captions(timings, words_per_frame=3)
        assert track.count == 3
        assert track.frames[0].words == ["word0", "word1", "word2"]
        assert track.frames[1].words == ["word3", "word4", "word5"]
        assert track.frames[2].words == ["word6", "word7", "word8"]

    def test_groups_by_2(self):
        timings = _make_timings(6)
        track = generate_captions(timings, words_per_frame=2)
        assert track.count == 3

    def test_remainder_frame(self):
        timings = _make_timings(7)
        track = generate_captions(timings, words_per_frame=3)
        assert track.count == 3  # 3 + 3 + 1
        assert len(track.frames[-1].words) == 1

    def test_single_word(self):
        timings = _make_timings(1)
        track = generate_captions(timings, words_per_frame=3)
        assert track.count == 1
        assert track.frames[0].text == "word0"

    def test_timing_continuity(self):
        timings = _make_timings(6)
        track = generate_captions(timings, words_per_frame=3)
        # Each frame should start at or after the previous frame's start
        for i in range(1, len(track.frames)):
            assert track.frames[i].start >= track.frames[i - 1].start

    def test_frame_text_joined(self):
        timings = _make_timings(3)
        track = generate_captions(timings, words_per_frame=3)
        assert track.frames[0].text == "word0 word1 word2"

    def test_duration_positive(self):
        timings = _make_timings(6)
        track = generate_captions(timings, words_per_frame=3)
        for frame in track.frames:
            assert frame.duration > 0
