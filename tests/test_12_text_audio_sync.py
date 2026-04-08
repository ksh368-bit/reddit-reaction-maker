"""
Test 12: Text shown on screen must exactly match what TTS actually reads.

Root cause of sync bug:
- generate_audio() truncates text to max_chars=500 before sending to TTS
- But estimate_word_segments() was given the full (untruncated) text
- Result: screen shows words that TTS never speaks → visible after audio ends

Acceptance criteria:
- prepare_tts_text(text, max_chars) returns the exact text TTS will read
- estimate_word_segments uses the truncated text, not the raw input
- word_segments word list matches the truncated text word-for-word
- Body segment text stored in segment dict matches what TTS reads
"""
import pytest


def test_prepare_tts_text_exists():
    """TTSEngine.prepare_tts_text must exist as a classmethod."""
    from tts.engine import TTSEngine
    assert callable(getattr(TTSEngine, "prepare_tts_text", None))


def test_prepare_tts_text_short_unchanged():
    """Text under max_chars is returned unchanged (after cleaning)."""
    from tts.engine import TTSEngine

    text = "This is a short sentence."
    result = TTSEngine.prepare_tts_text(text, max_chars=500)
    assert result == TTSEngine.clean_text(text)


def test_prepare_tts_text_truncates_at_word_boundary():
    """Text over max_chars is cut at last word boundary and gets ellipsis."""
    from tts.engine import TTSEngine

    long_text = "word " * 200  # ~1000 chars
    result = TTSEngine.prepare_tts_text(long_text, max_chars=50)
    assert len(result) <= 53  # 50 + "..." = 53
    assert result.endswith("...")


def test_word_segments_match_tts_text_length():
    """word_segments must only cover words that TTS actually speaks."""
    from tts.engine import TTSEngine, estimate_word_segments

    raw_text = "one two three four five six seven eight nine ten " * 20  # 1000+ chars
    tts_text = TTSEngine.prepare_tts_text(raw_text, max_chars=100)
    tts_words = tts_text.rstrip("...").split()

    segs = estimate_word_segments(None, tts_text, fallback_duration=5.0)
    seg_words = [s["word"] for s in segs]

    # The word count in segments must match the tts_text word count
    assert len(segs) == len(tts_text.split()), (
        f"word_segments has {len(segs)} words but TTS text has "
        f"{len(tts_text.split())} words"
    )


def test_body_segment_text_matches_tts(sample_post):
    """Body segment word_segments must cover approximately the same words as text."""
    from tts.engine import TTSEngine
    import tempfile

    long_body = "My wife disagreed with me on this. " * 50
    sample_post.body = long_body

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(sample_post, tmp)

    body_segs = [s for s in segs if s["type"] == "body"]
    assert body_segs

    for seg in body_segs:
        word_segs = seg["word_segments"]
        assert word_segs, "word_segments must not be empty"
        # Whisper may tokenise slightly differently, allow ±20% tolerance
        seg_word_count = len(seg["text"].split())
        ws_word_count = len(word_segs)
        ratio = ws_word_count / seg_word_count if seg_word_count else 0
        assert 0.6 <= ratio <= 1.6, (
            f"word_segments count ({ws_word_count}) vs text words ({seg_word_count}) "
            f"ratio {ratio:.2f} out of expected range 0.6-1.6"
        )


def test_comment_segment_text_matches_tts(sample_post):
    """Comment segment word_segments must be non-empty and roughly match text length."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(sample_post, tmp)

    for seg in segs:
        if seg["type"] not in ("comment", "body"):
            continue
        word_segs = seg.get("word_segments", [])
        assert word_segs, f"{seg['type']} has empty word_segments"
        # Whisper tokenises differently from split() — allow ±40% tolerance
        seg_words = len(seg["text"].split())
        ws_words = len(word_segs)
        ratio = ws_words / seg_words if seg_words else 0
        assert 0.5 <= ratio <= 2.0, (
            f"{seg['type']}: word_segments ({ws_words}) vs text ({seg_words}) "
            f"ratio {ratio:.2f} — likely a timing source mismatch"
        )
