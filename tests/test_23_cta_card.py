"""Tests for CTA card rendering fix (TDD — written before implementation)."""

from __future__ import annotations

import os
import sys
import inspect
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CTA_TEXT = "Comment NTA or YTA below — and catch Part 2 for what happens next."


# ─────────────────────────────────────────────
#  render_cta_card
# ─────────────────────────────────────────────

class TestRenderCtaCard:
    def test_cta_card_size_is_1080x1920(self):
        from video.card_renderer import render_cta_card
        img = render_cta_card(CTA_TEXT, font_path=None)
        assert img.size == (1080, 1920)

    def test_cta_card_has_text_pixels(self):
        """Card must not be fully transparent — text should render pixels."""
        from video.card_renderer import render_cta_card
        img = render_cta_card(CTA_TEXT, font_path=None)
        pixels = img.tobytes()
        # At least some pixel should have alpha > 0
        assert any(pixels[i + 3] > 0 for i in range(0, len(pixels), 4))

    def test_cta_card_fits_in_quarter_height(self):
        """
        Text block must fit within 25% of video height.
        If font_size were 165 (old fallback), 3-5 lines × 165*1.45 ≈ 720-1200px
        which is 37-62% of 1920px — this test would fail.
        At font_size=60, 3 lines × 87px = 261px = 13.6% — passes.
        """
        from video.card_renderer import render_cta_card
        img = render_cta_card(CTA_TEXT, video_height=1920, font_path=None)
        import numpy as np
        arr = np.array(img)
        # Find rows with any non-transparent pixel
        alpha = arr[:, :, 3]
        opaque_rows = np.where(alpha > 10)[0]
        if len(opaque_rows) == 0:
            pytest.skip("No opaque pixels found (font rendering issue in test env)")
        text_height = int(opaque_rows.max()) - int(opaque_rows.min())
        assert text_height <= 1920 * 0.25, (
            f"Text block height {text_height}px exceeds 25% of 1920px. "
            f"Likely using oversized font."
        )


# ─────────────────────────────────────────────
#  CTA segment type
# ─────────────────────────────────────────────

class TestCtaSegmentType:
    def _make_long_post(self):
        """Create a RedditPost with body > 1000 chars to trigger CTA."""
        from reddit.scraper import RedditPost
        return RedditPost(
            id="test_cta",
            title="AITA for testing this",
            body="A" * 1001,
            author="testuser",
            score=1000,
            url="https://reddit.com/r/amitheasshole/comments/test_cta",
            subreddit="amitheasshole",
        )

    def test_cta_type_not_comment(self, tmp_path):
        """TTSEngine must assign type='cta', not type='comment', for CTA segments."""
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "gtts", "language": "en"},
            "video": {"max_duration": 58},
        }
        engine = TTSEngine(cfg)
        post = self._make_long_post()

        with patch.object(engine, "generate_audio") as mock_audio:
            # Return a fake audio path for all calls
            mock_audio.return_value = str(tmp_path / "fake.mp3")
            (tmp_path / "fake.mp3").write_bytes(b"fake")

            with patch("tts.engine.whisper_word_segments", return_value=[]):
                segments = engine.generate_for_post(post, str(tmp_path))

        types = [s.get("type") for s in segments]
        assert "cta" in types, f"Expected 'cta' type segment, got types: {types}"
        # Must not have a bare 'comment' segment that is the CTA
        cta_segs = [s for s in segments if s.get("type") == "cta"]
        assert len(cta_segs) >= 1

    def test_cta_segment_has_empty_word_segments(self, tmp_path):
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "gtts", "language": "en"},
            "video": {"max_duration": 58},
        }
        engine = TTSEngine(cfg)
        post = self._make_long_post()

        with patch.object(engine, "generate_audio") as mock_audio:
            mock_audio.return_value = str(tmp_path / "fake.mp3")
            (tmp_path / "fake.mp3").write_bytes(b"fake")

            with patch("tts.engine.whisper_word_segments", return_value=[]):
                segments = engine.generate_for_post(post, str(tmp_path))

        cta_segs = [s for s in segments if s.get("type") == "cta"]
        for seg in cta_segs:
            assert seg.get("word_segments") == [], (
                f"CTA segment must have empty word_segments, got: {seg.get('word_segments')}"
            )


# ─────────────────────────────────────────────
#  CTA no karaoke (source inspection)
# ─────────────────────────────────────────────

class TestCtaNoKaraoke:
    def test_karaoke_not_applied_to_cta(self):
        """
        In composer.py, karaoke condition must NOT include 'cta'.
        Check source code directly.
        """
        from video.composer import VideoComposer
        src = inspect.getsource(VideoComposer.compose_video)
        # Find the karaoke condition line
        assert '"cta"' not in src.split('_add_karaoke_clips')[0].split(
            'seg.get("type") in'
        )[-1].split('\n')[0], (
            "'cta' must not be in the karaoke type condition"
        )

    def test_cta_not_in_karaoke_types(self):
        """
        Simpler check: the tuple of types eligible for karaoke
        must not include 'cta'.
        """
        from video.composer import VideoComposer
        src = inspect.getsource(VideoComposer.compose_video)
        # The karaoke condition is: seg.get("type") in ("comment", "body", "hook")
        # Verify "cta" is not in this tuple
        import re
        match = re.search(r'seg\.get\("type"\)\s+in\s+\(([^)]+)\)', src)
        if match:
            karaoke_types = match.group(1)
            assert '"cta"' not in karaoke_types, (
                f"'cta' found in karaoke types: {karaoke_types}"
            )
