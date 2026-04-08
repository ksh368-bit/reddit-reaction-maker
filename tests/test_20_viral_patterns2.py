"""Tests for 100M+ Shorts viral pattern improvements (round 2)."""

from __future__ import annotations
import os, sys, inspect
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
#  hook_extractor — unit tests
# ─────────────────────────────────────────────

class TestScoreSentence:
    def test_shock_words_raise_score(self):
        from utils.hook_extractor import score_sentence
        assert score_sentence("She cheated on me with my best friend.") >= 4

    def test_money_raises_score(self):
        from utils.hook_extractor import score_sentence
        assert score_sentence("He stole $5000 from my savings account.") >= 6

    def test_plain_sentence_low_score(self):
        from utils.hook_extractor import score_sentence
        assert score_sentence("We went to the grocery store yesterday.") < 3


class TestExtractMoneyQuote:
    def test_returns_most_shocking_sentence(self):
        from utils.hook_extractor import extract_money_quote
        body = (
            "We had dinner together. It was nice. "
            "Then she admitted she had cheated on me for two years. "
            "I left the restaurant."
        )
        result = extract_money_quote(body)
        assert result is not None
        assert "cheated" in result

    def test_returns_none_if_boring(self):
        from utils.hook_extractor import extract_money_quote
        body = "We went shopping. Then we had lunch. It was a nice day overall."
        assert extract_money_quote(body) is None

    def test_returns_none_if_empty(self):
        from utils.hook_extractor import extract_money_quote
        assert extract_money_quote("") is None
        assert extract_money_quote("   ") is None

    def test_returns_none_if_too_short(self):
        from utils.hook_extractor import extract_money_quote
        assert extract_money_quote("OK.") is None

    def test_result_under_120_chars(self):
        from utils.hook_extractor import extract_money_quote
        body = (
            "She fired me from my job after ten years. "
            "I had done nothing wrong but she claimed I stole company property "
            "worth thousands and thousands of dollars which was completely false. "
            "I was devastated."
        )
        result = extract_money_quote(body)
        if result:
            assert len(result) <= 120

    def test_result_capitalised(self):
        from utils.hook_extractor import extract_money_quote
        body = "he lied about everything. she cheated with my brother."
        result = extract_money_quote(body)
        if result:
            assert result[0].isupper()


class TestExtractConflictCore:
    def test_cuts_after_peak_sentence(self):
        from utils.hook_extractor import extract_conflict_core
        body = (
            "We had been friends for ten years. "
            "Everything seemed fine until last Tuesday. "
            "That's when she betrayed me and stole all the money. "
            "I was absolutely devastated. "
            "Now I don't know what to do going forward."
        )
        result = extract_conflict_core(body, max_chars=500)
        # Must include the peak (betrayed/stole) but not necessarily everything after
        assert "betrayed" in result or "stole" in result

    def test_fallback_when_no_peak(self):
        from utils.hook_extractor import extract_conflict_core
        body = "We went shopping. Then we had lunch. It was a nice day."
        result = extract_conflict_core(body, max_chars=500)
        assert len(result) > 0  # falls back gracefully

    def test_respects_max_chars(self):
        from utils.hook_extractor import extract_conflict_core
        body = "word " * 300  # very long boring body
        result = extract_conflict_core(body, max_chars=500)
        assert len(result) <= 500

    def test_returns_empty_for_empty_body(self):
        from utils.hook_extractor import extract_conflict_core
        assert extract_conflict_core("", max_chars=500) == ""


# ─────────────────────────────────────────────
#  tts/engine.py — integration tests
# ─────────────────────────────────────────────

def _make_post(body="", title="AITA for something?", long_body=False):
    from reddit.scraper import RedditPost, Comment
    if long_body:
        body = (
            "We had been together for five years. Everything was fine. "
            "She cheated on me with my coworker. "
            "I found out when I saw the messages. " * 30  # > 1000 chars
        )
    return RedditPost(
        id="test1", title=title, body=body,
        author="user", score=1000, url="url",
        subreddit="AmItheAsshole",
        comments=[Comment("c1", "u1", "NTA you did nothing wrong.", 300)],
    )


class TestHookSegmentInEngine:
    def test_hook_segment_first_when_shocking_body(self):
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+20%"},
            "video": {"width": 1080, "height": 1920},
        }
        engine = TTSEngine(cfg)
        shocking_body = (
            "We had been married for three years. "
            "She cheated on me with my brother and I found the messages. "
            "I confronted her immediately."
        )
        post = _make_post(body=shocking_body)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                # Create fake mp3 file
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[
                    {"word": "She", "start_time": 0.0, "end_time": 0.3},
                    {"word": "cheated", "start_time": 0.3, "end_time": 0.6},
                ]):
                    segs = engine.generate_for_post(post, tmp)
        types = [s["type"] for s in segs]
        assert "hook" in types
        assert types[0] == "hook", f"Expected hook first, got: {types}"

    def test_no_hook_segment_when_boring_body(self):
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+20%"},
            "video": {"width": 1080, "height": 1920},
        }
        engine = TTSEngine(cfg)
        boring_body = "We went shopping. Then we had lunch. It was a nice day overall."
        post = _make_post(body=boring_body)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        types = [s["type"] for s in segs]
        assert "hook" not in types

    def test_body_uses_conflict_core_not_naive_truncation(self):
        from tts.engine import TTSEngine
        from utils.hook_extractor import extract_conflict_core
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+20%"},
            "video": {"width": 1080, "height": 1920},
        }
        engine = TTSEngine(cfg)
        body = (
            "Background info. More background. Even more background. "
            "Then she betrayed me completely and stole everything. "
            "After that things got worse. " * 10  # make it long
        )
        post = _make_post(body=body)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        body_segs = [s for s in segs if s["type"] == "body"]
        if body_segs:
            naive = engine.clean_text(body)[:500]
            assert body_segs[0]["text"] != naive, \
                "body text should use conflict_core, not naive [:500] truncation"

    def test_cta_appended_for_long_post(self):
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+20%"},
            "video": {"width": 1080, "height": 1920},
        }
        engine = TTSEngine(cfg)
        post = _make_post(long_body=True)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        texts = [s.get("text", "") for s in segs]
        assert any("Part 2" in t or "verdict" in t for t in texts), \
            f"Expected CTA in segments, got texts: {texts[:5]}"


# ─────────────────────────────────────────────
#  video/composer.py
# ─────────────────────────────────────────────

class TestComposerLoopAndChunk:
    def test_chunk_size_default_is_2(self):
        from video.composer import VideoComposer
        sig = inspect.signature(VideoComposer._add_karaoke_clips)
        param = sig.parameters.get("chunk_size")
        assert param is not None, "chunk_size parameter not found"
        assert param.default == 2, f"chunk_size default is {param.default}, expected 2"

    def test_loop_hold_last_word_longer(self):
        """Last word's clip duration should be ~0.5s longer than other words."""
        from video.composer import VideoComposer
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+20%"},
            "video": {
                "width": 1080, "height": 1920, "fps": 30,
                "max_duration": 60, "background_dir": "assets/backgrounds",
                "font": "assets/fonts/Montserrat-Bold.ttf",
                "title_font_size": 52, "comment_font_size": 165,
                "text_color": "white", "text_stroke_color": "black",
                "text_stroke_width": 3, "watermark": "r/test",
                "opacity": 0.45, "bgm_enabled": False, "bgm_volume": 0.0,
            },
            "output": {"dir": "/tmp", "history_file": "/tmp/hist.json"},
        }
        composer = VideoComposer(cfg)

        word_segs = [
            {"word": "She",     "start_time": 0.0, "end_time": 0.3},
            {"word": "cheated", "start_time": 0.3, "end_time": 0.7},
            {"word": "on",      "start_time": 0.7, "end_time": 0.9},
            {"word": "me",      "start_time": 0.9, "end_time": 1.2},
        ]

        clips = []
        with patch("video.card_renderer.render_caption_chunk") as mock_render:
            from PIL import Image
            mock_render.return_value = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            import tempfile, os
            with tempfile.TemporaryDirectory() as tmp:
                # Monkeypatch temp dir
                orig = __import__("tempfile").mkdtemp
                with patch("tempfile.mkdtemp", return_value=tmp):
                    composer._add_karaoke_clips(
                        clips, word_segs,
                        seg_start=0.0, audio_dur=1.2,
                        total_duration=10.0, fade_in=0.15,
                    )

        durations = [c.duration for c in clips]
        assert len(durations) >= 2, "Expected at least 2 clip durations"
        last_dur  = durations[-1]
        other_dur = max(durations[:-1])
        assert last_dur > other_dur, \
            f"Last word dur ({last_dur:.3f}) should be > other words ({other_dur:.3f})"


# ─────────────────────────────────────────────
#  reddit/scraper.py
# ─────────────────────────────────────────────

class TestViralityScoring:
    def _make_scraper(self):
        from reddit.scraper import RedditScraper
        cfg = {
            "reddit": {
                "subreddit": "AmItheAsshole",
                "post_limit": 3,
                "min_upvotes": 100,
                "min_comments": 5,
                "top_comments": 2,
                "max_comment_length": 80,
                "min_comment_score": 0,
            },
            "output": {"history_file": "/tmp/test_history.json"},
        }
        return RedditScraper(cfg)

    def _make_post(self, title, score=1000):
        from reddit.scraper import RedditPost
        return RedditPost(
            id="x", title=title, body="", author="u",
            score=score, url="url", subreddit="AITA",
        )

    def test_virality_score_prefers_conflict_action(self):
        scraper = self._make_scraper()
        conflict = self._make_post("I kicked out my sister after she cheated")
        plain    = self._make_post("I had a nice day with my family")
        assert scraper._virality_score(conflict, 0.9) > \
               scraper._virality_score(plain, 0.9)

    def test_virality_score_controversy_bonus(self):
        scraper  = self._make_scraper()
        post     = self._make_post("regular post")
        low_ratio  = scraper._virality_score(post, upvote_ratio=0.75)
        high_ratio = scraper._virality_score(post, upvote_ratio=0.98)
        assert low_ratio > high_ratio, \
            "Controversial posts (low upvote_ratio) should score higher"

    def test_posts_sorted_by_virality(self):
        """_fetch_posts_with_filter returns posts in virality_score descending order."""
        from reddit.scraper import RedditScraper, RedditPost, Comment
        import json

        cfg = {
            "reddit": {
                "subreddit": "AmItheAsshole",
                "post_limit": 3,
                "min_upvotes": 0,
                "min_comments": 0,
                "top_comments": 2,
                "max_comment_length": 80,
                "min_comment_score": 0,
            },
            "output": {"history_file": "/tmp/test_hist2.json"},
        }
        scraper = RedditScraper(cfg)

        # Build minimal mock API responses
        def fake_request(url, params=None):
            if "comments" in url or ".json" in url and "top.json" not in url:
                return [
                    {"data": {"children": []}},
                    {"data": {"children": [
                        {"kind": "t1", "data": {
                            "id": "c1", "body": "NTA you did nothing wrong.",
                            "author": "user1", "score": 100, "replies": ""
                        }}
                    ]}}
                ]
            return {
                "data": {
                    "children": [
                        {"data": {
                            "id": "post1",
                            "title": "I kicked out my sister after she cheated",
                            "selftext": "",
                            "author": "u1",
                            "score": 500,
                            "upvote_ratio": 0.75,
                            "num_comments": 20,
                            "permalink": "/r/AITA/comments/post1/",
                            "url": "url1",
                        }},
                        {"data": {
                            "id": "post2",
                            "title": "I had a nice lunch with my mom",
                            "selftext": "",
                            "author": "u2",
                            "score": 5000,  # higher score but boring
                            "upvote_ratio": 0.98,
                            "num_comments": 20,
                            "permalink": "/r/AITA/comments/post2/",
                            "url": "url2",
                        }},
                    ]
                }
            }

        with patch.object(scraper, "_request_json", side_effect=fake_request), \
             patch.object(scraper, "_load_history", return_value=set()):
            posts = scraper._fetch_posts_with_filter("week")

        assert len(posts) >= 1
        # conflict post (post1) should come before boring post (post2)
        ids = [p.id for p in posts]
        if "post1" in ids and "post2" in ids:
            assert ids.index("post1") < ids.index("post2"), \
                "Conflict post should rank above boring high-upvote post"
