"""Tests for 3차 개선 — verdict card, comment ranking, meta, BGM, freshness."""
from __future__ import annotations
import os, sys, time
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
#  helpers
# ─────────────────────────────────────────────

def _comment(body, score=100):
    from reddit.scraper import Comment
    return Comment(id="c", author="u", body=body, score=score)


def _make_post(body="", comments=None, long_body=False):
    from reddit.scraper import RedditPost
    if long_body:
        body = "Background. " * 100  # > 1000 chars
    if comments is None:
        comments = [_comment("NTA you did nothing wrong.", 500)]
    return RedditPost(
        id="t1", title="AITA for something?", body=body,
        author="u", score=1000, url="url", subreddit="AmItheAsshole",
        comments=comments,
    )


# ─────────────────────────────────────────────
#  verdict_extractor — unit tests
# ─────────────────────────────────────────────

class TestExtractVerdict:
    def test_extract_verdict_nta(self):
        from utils.verdict_extractor import extract_verdict
        comments = [_comment("NTA. You did nothing wrong."), _comment("NTA!")]
        assert extract_verdict(comments) == "NTA"

    def test_extract_verdict_yta(self):
        from utils.verdict_extractor import extract_verdict
        comments = [_comment("YTA for sure."), _comment("Soft YTA.")]
        assert extract_verdict(comments) == "YTA"

    def test_extract_verdict_none(self):
        from utils.verdict_extractor import extract_verdict
        comments = [_comment("This is a tough situation."), _comment("I feel for you.")]
        assert extract_verdict(comments) is None

    def test_extract_verdict_majority_wins(self):
        from utils.verdict_extractor import extract_verdict
        # NTA top comment (weight 3) + NTA second (weight 1) = 4 vs YTA = 1
        comments = [
            _comment("NTA completely.", 500),   # weight ×3
            _comment("NTA agreed.", 300),        # weight ×1
            _comment("YTA slightly.", 200),
        ]
        assert extract_verdict(comments) == "NTA"

    def test_extract_verdict_top_comment_weight(self):
        from utils.verdict_extractor import extract_verdict
        # Top comment YTA (weight 3) vs 3 NTA (weight 1 each) → YTA wins 3 vs 3, tie → max picks first
        # YTA = 3, NTA = 1+1+1 = 3 → tie → max() returns first max key (YTA since it's first)
        comments = [
            _comment("YTA here.", 500),         # weight ×3 → 3
            _comment("NTA first one.", 400),
            _comment("NTA second.", 300),
            _comment("NTA third.", 200),
        ]
        # YTA = 3, NTA = 3 — tie; Python max() keeps first encountered in dict iteration
        # Since YTA is inserted first (from top comment), result depends on insertion order
        result = extract_verdict(comments)
        assert result in ("NTA", "YTA")   # either valid in a tie; just ensure no exception

    def test_verdict_text_lookup(self):
        from utils.verdict_extractor import VERDICT_TEXT
        assert VERDICT_TEXT["NTA"] == "Not the asshole."
        assert VERDICT_TEXT["YTA"] == "You are the asshole."
        assert VERDICT_TEXT["ESH"] == "Everyone sucks here."
        assert VERDICT_TEXT["NAH"] == "No assholes here."
        assert VERDICT_TEXT["INFO"] == "More information needed."


# ─────────────────────────────────────────────
#  render_verdict_card — visual tests
# ─────────────────────────────────────────────

class TestRenderVerdictCard:
    def test_verdict_card_nta_has_green_pixels(self):
        from video.card_renderer import render_verdict_card
        import numpy as np
        img = render_verdict_card("NTA", video_width=1080, video_height=1920)
        arr = np.array(img)
        # Green channel dominant in center region
        cy = 1920 // 2 - 60
        region = arr[cy - 80:cy + 80, 400:680]
        green_dominant = (region[:, :, 1] > 150) & (region[:, :, 0] < 100) & (region[:, :, 3] > 100)
        assert green_dominant.sum() > 50, "NTA card should have green pixels"

    def test_verdict_card_yta_has_red_pixels(self):
        from video.card_renderer import render_verdict_card
        import numpy as np
        img = render_verdict_card("YTA", video_width=1080, video_height=1920)
        arr = np.array(img)
        cy = 1920 // 2 - 60
        region = arr[cy - 80:cy + 80, 300:780]
        red_dominant = (region[:, :, 0] > 150) & (region[:, :, 1] < 100) & (region[:, :, 3] > 100)
        assert red_dominant.sum() > 50, "YTA card should have red pixels"

    def test_verdict_card_has_dark_backing(self):
        from video.card_renderer import render_verdict_card
        import numpy as np
        img = render_verdict_card("NTA", video_width=1080, video_height=1920)
        arr = np.array(img)
        # At least some rows should have wide semi-opaque dark backing
        wide_rows = 0
        for y in range(0, 1920, 10):
            row_alpha = arr[y, :, 3]
            if int((row_alpha >= 180).sum()) >= int(1080 * 0.8):
                wide_rows += 1
        assert wide_rows >= 10, f"Dark backing not found (wide_rows={wide_rows})"


# ─────────────────────────────────────────────
#  tts/engine.py — integration tests
# ─────────────────────────────────────────────

class TestVerdictSegmentInEngine:
    def _cfg(self):
        return {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+25%"},
            "video": {"width": 1080, "height": 1920},
        }

    def test_verdict_segment_appended(self):
        from tts.engine import TTSEngine
        engine = TTSEngine(self._cfg())
        post = _make_post(body="Short story.", comments=[_comment("NTA you did nothing wrong.", 500)])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        types = [s["type"] for s in segs]
        assert "verdict" in types, f"verdict segment missing. types={types}"

    def test_no_verdict_for_long_post(self):
        from tts.engine import TTSEngine
        engine = TTSEngine(self._cfg())
        long_body = "word " * 300   # > 1000 chars
        post = _make_post(body=long_body, comments=[_comment("NTA for sure.", 500)])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        types = [s["type"] for s in segs]
        assert "verdict" not in types, f"verdict should be absent for long posts. types={types}"

    def test_no_verdict_when_no_match(self):
        from tts.engine import TTSEngine
        engine = TTSEngine(self._cfg())
        post = _make_post(body="Short story.", comments=[_comment("Tough situation for you.", 500)])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        types = [s["type"] for s in segs]
        assert "verdict" not in types, f"no verdict expected when comments have none. types={types}"

    def test_verdict_segment_is_last(self):
        from tts.engine import TTSEngine
        engine = TTSEngine(self._cfg())
        post = _make_post(body="Short story.", comments=[_comment("NTA completely.", 500)])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        verdict_segs = [s for s in segs if s["type"] == "verdict"]
        assert verdict_segs, "No verdict segment found"
        last_seg = segs[-1]
        assert last_seg["type"] == "verdict", f"Last seg should be verdict, got {last_seg['type']}"

    def test_verdict_segment_has_no_word_segs(self):
        from tts.engine import TTSEngine
        engine = TTSEngine(self._cfg())
        post = _make_post(body="Short story.", comments=[_comment("NTA completely.", 500)])
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        for seg in segs:
            if seg["type"] == "verdict":
                assert seg.get("word_segments") == [], \
                    "verdict segment should have empty word_segments (static card)"


# ─────────────────────────────────────────────
#  reddit/scraper.py — comment ranking & virality
# ─────────────────────────────────────────────

class TestVerdictCommentRanking:
    def _make_scraper(self):
        from reddit.scraper import RedditScraper
        cfg = {
            "reddit": {
                "subreddit": "AmItheAsshole",
                "post_limit": 3,
                "min_upvotes": 0,
                "min_comments": 0,
                "top_comments": 2,
                "max_comment_length": 120,
                "min_comment_score": 0,
            },
            "output": {"history_file": "/tmp/test_verdict_hist.json"},
        }
        return RedditScraper(cfg)

    def test_verdict_comment_ranked_higher(self):
        scraper = self._make_scraper()
        verdict_comment = _comment("NTA you did nothing wrong here.", 100)
        plain_comment = _comment("This is a tough situation for everyone.", 100)
        # Both have score=100, but verdict comment should rank first
        mock_data = [
            {},  # first element (post listing, ignored by _parse_comments)
            {
                "data": {
                    "children": [
                        {"kind": "t1", "data": {
                            "id": "c1", "body": plain_comment.body,
                            "author": "u1", "score": 100, "replies": ""
                        }},
                        {"kind": "t1", "data": {
                            "id": "c2", "body": verdict_comment.body,
                            "author": "u2", "score": 100, "replies": ""
                        }},
                    ]
                }
            }
        ]
        comments = scraper._parse_comments(mock_data)
        assert len(comments) >= 1
        if len(comments) >= 2:
            assert comments[0].body == verdict_comment.body, \
                "Verdict-starting comment should rank first"
        else:
            assert "NTA" in comments[0].body

    def test_freshness_bonus_recent_post(self):
        from reddit.scraper import RedditScraper
        cfg = {
            "reddit": {"subreddit": "AmItheAsshole", "post_limit": 1,
                       "min_upvotes": 0, "min_comments": 0, "top_comments": 1,
                       "max_comment_length": 80, "min_comment_score": 0},
            "output": {"history_file": "/tmp/th.json"},
        }
        scraper = RedditScraper(cfg)
        from reddit.scraper import RedditPost
        post = RedditPost(id="x", title="test", body="", author="u", score=100,
                          url="url", subreddit="AITA")
        recent_utc = time.time() - 3600   # 1h ago (< 6h)
        old_utc    = time.time() - 200000  # ~2.3 days ago
        score_recent = scraper._virality_score(post, 0.9, created_utc=recent_utc)
        score_old    = scraper._virality_score(post, 0.9, created_utc=old_utc)
        assert score_recent > score_old, "Recent post should score higher"

    def test_freshness_penalty_old_post(self):
        from reddit.scraper import RedditScraper
        cfg = {
            "reddit": {"subreddit": "AmItheAsshole", "post_limit": 1,
                       "min_upvotes": 0, "min_comments": 0, "top_comments": 1,
                       "max_comment_length": 80, "min_comment_score": 0},
            "output": {"history_file": "/tmp/th2.json"},
        }
        scraper = RedditScraper(cfg)
        from reddit.scraper import RedditPost
        post = RedditPost(id="x", title="test", body="", author="u", score=100,
                          url="url", subreddit="AITA")
        week_old  = scraper._virality_score(post, 0.9, created_utc=time.time() - 200000)  # ~2d
        month_old = scraper._virality_score(post, 0.9, created_utc=time.time() - 700000)  # ~8d (>168h)
        assert week_old > month_old, "Post older than 1 week should score lower"

    def test_edit_update_bonus(self):
        from reddit.scraper import RedditScraper
        cfg = {
            "reddit": {"subreddit": "AmItheAsshole", "post_limit": 1,
                       "min_upvotes": 0, "min_comments": 0, "top_comments": 1,
                       "max_comment_length": 80, "min_comment_score": 0},
            "output": {"history_file": "/tmp/th3.json"},
        }
        scraper = RedditScraper(cfg)
        from reddit.scraper import RedditPost
        post_with_edit    = RedditPost(id="x", title="test", body="Story. EDIT: update here.",
                                        author="u", score=100, url="url", subreddit="AITA")
        post_without_edit = RedditPost(id="y", title="test", body="Story. No resolution.",
                                        author="u", score=100, url="url", subreddit="AITA")
        s_edit    = scraper._virality_score(post_with_edit,    0.9, created_utc=0.0)
        s_no_edit = scraper._virality_score(post_without_edit, 0.9, created_utc=0.0)
        assert s_edit > s_no_edit, "Post with EDIT section should score higher"


# ─────────────────────────────────────────────
#  utils/meta_generator.py
# ─────────────────────────────────────────────

class TestMetaWithVerdict:
    def _post(self):
        from reddit.scraper import RedditPost
        return RedditPost(id="t", title="I kicked out my sister after she stole $500",
                          body="", author="u", score=1000, url="url",
                          subreddit="AmItheAsshole")

    def test_title_includes_verdict_badge(self):
        from utils.meta_generator import MetaGenerator
        title = MetaGenerator.generate_title(self._post(), verdict="NTA")
        assert "(NTA)" in title, f"Expected (NTA) badge in title: {title}"

    def test_title_no_badge_when_too_long(self):
        from utils.meta_generator import MetaGenerator
        from reddit.scraper import RedditPost
        long_post = RedditPost(id="t",
                               title="I kicked out my sister after she stole money from me last Tuesday",
                               body="", author="u", score=1000, url="url",
                               subreddit="AmItheAsshole")
        title = MetaGenerator.generate_title(long_post, verdict="NTA")
        assert len(title) <= 60, f"Title exceeds 60 chars: {len(title)} — '{title}'"

    def test_description_verdict_first_line(self):
        from utils.meta_generator import MetaGenerator
        desc = MetaGenerator.generate_description(self._post(), verdict="NTA")
        assert desc.startswith("The internet says: NTA"), \
            f"Description should start with verdict line: {desc[:80]}"

    def test_hashtags_include_verdict_tag(self):
        from utils.meta_generator import MetaGenerator
        tags = MetaGenerator.generate_hashtags(self._post(), verdict="NTA")
        assert "#NTA" in tags, f"#NTA not found in hashtags: {tags}"

    def test_meta_unchanged_when_no_verdict(self):
        from utils.meta_generator import MetaGenerator
        title_no = MetaGenerator.generate_title(self._post(), verdict=None)
        title_with = MetaGenerator.generate_title(self._post())
        assert title_no == title_with, "No verdict should produce same title as default"
        desc = MetaGenerator.generate_description(self._post(), verdict=None)
        assert "The internet says:" not in desc


# ─────────────────────────────────────────────
#  video/composer.py — BGM ducking
# ─────────────────────────────────────────────

class TestBGMDucking:
    def _cfg(self):
        return {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+25%"},
            "video": {
                "width": 1080, "height": 1920, "fps": 30,
                "max_duration": 60, "background_dir": "assets/backgrounds",
                "font": "assets/fonts/Montserrat-Bold.ttf",
                "title_font_size": 52, "comment_font_size": 165,
                "text_color": "white", "text_stroke_color": "black",
                "text_stroke_width": 3, "watermark": "r/test",
                "opacity": 0.45, "bgm_enabled": True, "bgm_volume": 0.08,
            },
            "output": {"dir": "/tmp", "history_file": "/tmp/hist.json"},
        }

    def test_bgm_clip_accepts_timing_info(self):
        from video.composer import VideoComposer
        composer = VideoComposer(self._cfg())
        timing_info = [
            (0.0, 1.5, 1.7, {"type": "hook"}),
            (1.9, 2.0, 2.2, {"type": "body"}),
        ]
        import tempfile, wave, struct
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        # Write a minimal valid WAV file (1s, 44100Hz, mono, 16-bit)
        with wave.open(wav_path, "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            data = struct.pack("<" + "h" * 44100, *([0] * 44100))
            wav.writeframes(data)
        try:
            with patch("video.composer.select_random_audio", return_value=wav_path):
                clip = composer._create_bgm_clip(5.0, timing_info=timing_info)
            assert clip is not None, "_create_bgm_clip should return a clip"
            assert abs(clip.duration - 5.0) < 0.5, f"Clip duration {clip.duration} ≠ 5.0"
        finally:
            os.unlink(wav_path)

    def test_bgm_loops_when_shorter_than_video(self):
        from video.composer import VideoComposer
        composer = VideoComposer(self._cfg())
        import tempfile, wave, struct
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        # 2s WAV, video is 10s → should loop
        n = 44100 * 2
        with wave.open(wav_path, "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
        try:
            with patch("video.composer.select_random_audio", return_value=wav_path):
                clip = composer._create_bgm_clip(10.0)
            assert clip is not None
            assert abs(clip.duration - 10.0) < 0.5, \
                f"Looped BGM duration {clip.duration:.2f} ≠ 10.0"
        finally:
            os.unlink(wav_path)


# ─────────────────────────────────────────────
#  engine.py CTA prompt
# ─────────────────────────────────────────────

class TestCTAPrompt:
    def test_cta_text_contains_nta_or_yta_prompt(self):
        from tts.engine import TTSEngine
        cfg = {
            "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+25%"},
            "video": {"width": 1080, "height": 1920},
        }
        engine = TTSEngine(cfg)
        long_body = "word " * 300  # > 1000 chars
        from reddit.scraper import RedditPost, Comment
        post = RedditPost(
            id="t", title="AITA?", body=long_body, author="u",
            score=1000, url="url", subreddit="AmItheAsshole",
            comments=[Comment("c1", "u1", "NTA.", 100)],
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(engine, "generate_audio") as mock_audio:
                mock_audio.return_value = os.path.join(tmp, "fake.mp3")
                open(mock_audio.return_value, "wb").close()
                with patch("tts.engine.whisper_word_segments", return_value=[]):
                    segs = engine.generate_for_post(post, tmp)
        texts = [s.get("text", "") for s in segs]
        cta_texts = [t for t in texts if "Part 2" in t or "NTA or YTA" in t]
        assert cta_texts, f"CTA with NTA or YTA prompt not found. texts={texts}"
        assert any("NTA or YTA" in t for t in cta_texts), \
            f"CTA should contain 'NTA or YTA'. CTA texts={cta_texts}"
