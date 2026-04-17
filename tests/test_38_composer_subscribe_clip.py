"""
Composer integration: the subscribe CTA overlay must appear in the final
~2.5 seconds of the video. This test exercises the helper in isolation
so it stays fast.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.composer import VideoComposer


def _make_composer():
    return VideoComposer({
        "video": {"width": 1080, "height": 1920, "fps": 30},
        "output": {"dir": tempfile.mkdtemp()},
    })


class TestSubscribeClipTiming:
    def test_clip_starts_near_end(self):
        comp = _make_composer()
        with tempfile.TemporaryDirectory() as td:
            clip = comp._create_subscribe_overlay_clip(total_duration=30.0, temp_dir=td)
        assert clip is not None
        # Should start in the final 3 seconds
        assert clip.start >= 30.0 - 3.1
        assert clip.start < 30.0

    def test_clip_does_not_exceed_total_duration(self):
        comp = _make_composer()
        with tempfile.TemporaryDirectory() as td:
            clip = comp._create_subscribe_overlay_clip(total_duration=30.0, temp_dir=td)
        end = clip.start + clip.duration
        assert end <= 30.0 + 0.01  # allow tiny float slack

    def test_clip_has_video_size(self):
        comp = _make_composer()
        with tempfile.TemporaryDirectory() as td:
            clip = comp._create_subscribe_overlay_clip(total_duration=30.0, temp_dir=td)
        assert clip.size == [1080, 1920] or clip.size == (1080, 1920)

    def test_handles_short_videos(self):
        """Very short videos (< 3s) should still get a (trimmed) overlay."""
        comp = _make_composer()
        with tempfile.TemporaryDirectory() as td:
            clip = comp._create_subscribe_overlay_clip(total_duration=2.0, temp_dir=td)
        assert clip is not None
        assert clip.duration > 0
        assert clip.start + clip.duration <= 2.0 + 0.01

    def test_returns_none_for_very_short(self):
        """<1s video: no time for a CTA, return None."""
        comp = _make_composer()
        with tempfile.TemporaryDirectory() as td:
            clip = comp._create_subscribe_overlay_clip(total_duration=0.5, temp_dir=td)
        assert clip is None
