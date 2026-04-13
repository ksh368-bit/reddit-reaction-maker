"""Tests for CTA karaoke captions (TDD — written before implementation)."""

from __future__ import annotations

import os
import sys
import inspect
import re
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
#  CTA in karaoke types (composer)
# ─────────────────────────────────────────────

class TestCtaKaraokeInComposer:
    def test_cta_in_karaoke_types(self):
        """
        composer.py karaoke condition must include 'cta'.
        """
        from video.composer import VideoComposer
        src = inspect.getsource(VideoComposer.compose_video)
        match = re.search(r'seg\.get\("type"\)\s+in\s+\(([^)]+)\)', src)
        assert match, "Could not find karaoke types tuple in compose_video"
        karaoke_types = match.group(1)
        assert '"cta"' in karaoke_types, (
            f"'cta' must be in karaoke types, got: {karaoke_types}"
        )


# ─────────────────────────────────────────────
#  CTA word_segments from engine
# ─────────────────────────────────────────────

class TestCtaWordSegments:
    def _make_long_post(self):
        from reddit.scraper import RedditPost
        return RedditPost(
            id="test_cta_karaoke",
            title="AITA for testing this",
            body="A" * 1001,
            author="testuser",
            score=1000,
            url="https://reddit.com/r/amitheasshole/comments/test_cta_karaoke",
            subreddit="amitheasshole",
        )

    def test_cta_word_segments_populated_with_edge_tts(self, tmp_path):
        """
        When use_karaoke=True (EdgeTTS), CTA segment word_segments must be non-empty.
        """
        from tts.engine import TTSEngine, EdgeTTS

        cfg = {
            "tts": {"engine": "edge", "voice": "en-US-GuyNeural"},
            "video": {"max_duration": 58},
        }
        engine = TTSEngine(cfg)

        fake_audio = str(tmp_path / "fake.mp3")
        (tmp_path / "fake.mp3").write_bytes(b"fake")

        fake_word_events = [
            {"type": "WordBoundary", "text": "Comment", "offset": 0, "duration": 3000000},
            {"type": "WordBoundary", "text": "NTA", "offset": 4000000, "duration": 2000000},
        ]

        post = self._make_long_post()

        with patch.object(engine, "generate_audio") as mock_audio, \
             patch("tts.engine.whisper_word_segments", return_value=[]):
            # EdgeTTS returns (audio_path, word_events) tuple
            mock_audio.return_value = (fake_audio, fake_word_events)
            engine.provider = MagicMock(spec=EdgeTTS)

            # Force use_karaoke=True by patching isinstance check
            with patch("tts.engine.isinstance", return_value=True):
                segments = engine.generate_for_post(post, str(tmp_path))

        cta_segs = [s for s in segments if s.get("type") == "cta"]
        assert cta_segs, "No CTA segment found"
        cta = cta_segs[0]
        assert cta.get("word_segments"), (
            f"CTA word_segments must be non-empty with EdgeTTS, got: {cta.get('word_segments')}"
        )

    def test_cta_word_segments_empty_without_edge_tts(self, tmp_path):
        """
        When use_karaoke=False (gtts) and whisper returns [], word_segments stays [].
        """
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "gtts", "language": "en"},
            "video": {"max_duration": 58},
        }
        engine = TTSEngine(cfg)

        fake_audio = str(tmp_path / "fake.mp3")
        (tmp_path / "fake.mp3").write_bytes(b"fake")

        post = self._make_long_post()

        with patch.object(engine, "generate_audio") as mock_audio, \
             patch("tts.engine.whisper_word_segments", return_value=[]):
            mock_audio.return_value = fake_audio
            segments = engine.generate_for_post(post, str(tmp_path))

        cta_segs = [s for s in segments if s.get("type") == "cta"]
        assert cta_segs, "No CTA segment found"
        cta = cta_segs[0]
        assert cta.get("word_segments") == [], (
            f"CTA word_segments must be [] with gtts, got: {cta.get('word_segments')}"
        )
