"""
Test 10: Estimated word timing (edge-tts 7.x WordBoundary workaround).

edge-tts 7.x no longer emits WordBoundary events (only SentenceBoundary).
We must estimate per-word timing from audio duration + character proportions.

Acceptance criteria:
- estimate_word_segments(audio_path, text) exists in tts.engine
- Returns list of {word, start_time, end_time}
- Timing spans the full audio duration (last end_time ≈ audio duration)
- Monotonically increasing start times
- generate_for_post always populates word_segments (never empty list for comments)
"""
import pytest
import os
import tempfile


def test_estimate_word_segments_exists():
    from tts.engine import estimate_word_segments
    assert callable(estimate_word_segments)


def test_estimate_word_segments_structure(tmp_path):
    """Returns correct {word, start_time, end_time} structure."""
    from tts.engine import estimate_word_segments

    # Create a fake MP3 — use a real edge-tts generated one if available,
    # or just pass a duration directly via the fallback path (no file)
    segs = estimate_word_segments(None, "Hello world today is great", fallback_duration=3.0)
    assert len(segs) == 5
    for s in segs:
        assert "word" in s
        assert "start_time" in s
        assert "end_time" in s
        assert s["end_time"] > s["start_time"]


def test_estimate_word_segments_monotonic():
    from tts.engine import estimate_word_segments

    segs = estimate_word_segments(None, "A B C D E", fallback_duration=2.0)
    starts = [s["start_time"] for s in segs]
    assert starts == sorted(starts)


def test_estimate_word_segments_spans_full_duration():
    """Last word end_time must equal the total duration."""
    from tts.engine import estimate_word_segments

    segs = estimate_word_segments(None, "one two three", fallback_duration=2.0)
    assert abs(segs[-1]["end_time"] - 2.0) < 0.01


def test_estimate_word_segments_proportional():
    """Longer words should get more time than shorter words."""
    from tts.engine import estimate_word_segments

    segs = estimate_word_segments(None, "I supercalifragilistic", fallback_duration=2.0)
    assert len(segs) == 2
    # "supercalifragilistic" (20 chars) should get more time than "I" (1 char)
    assert segs[1]["end_time"] - segs[1]["start_time"] > segs[0]["end_time"] - segs[0]["start_time"]


def test_generate_for_post_always_populates_word_segments(sample_post):
    """Comment segments must always have non-empty word_segments."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segments = engine.generate_for_post(sample_post, tmp)

    comment_segs = [s for s in segments if s["type"] == "comment"]
    assert comment_segs, "No comment segments generated"
    for seg in comment_segs:
        assert seg.get("word_segments"), (
            f"word_segments is empty for comment '{seg['text'][:30]}' — "
            "estimated timing must always be populated"
        )
