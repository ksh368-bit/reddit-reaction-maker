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
    """Body segment 'text' must equal what TTS actually reads (truncated if needed)."""
    from tts.engine import TTSEngine
    import tempfile

    # Give the post a very long body that will be truncated
    long_body = "My wife disagreed with me on this. " * 50  # ~1750 chars
    sample_post.body = long_body

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(sample_post, tmp)

    body_segs = [s for s in segs if s["type"] == "body"]
    assert body_segs

    for seg in body_segs:
        seg_text = seg["text"]
        word_segs = seg["word_segments"]
        seg_word_count = len(seg_text.split())
        ws_word_count = len(word_segs)
        assert seg_word_count == ws_word_count, (
            f"Segment has {seg_word_count} words but word_segments has "
            f"{ws_word_count} entries — text/audio mismatch!"
        )


def test_comment_segment_text_matches_tts(sample_post):
    """Comment segment word_segments count must match segment text word count."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(sample_post, tmp)

    for seg in segs:
        if seg["type"] not in ("comment", "body"):
            continue
        seg_words = len(seg["text"].split())
        ws_words = len(seg.get("word_segments", []))
        assert seg_words == ws_words, (
            f"{seg['type']} text has {seg_words} words but word_segments "
            f"has {ws_words} — mismatch causes audio/text desync"
        )
