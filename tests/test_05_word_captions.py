"""
Test 05: Word-level caption sync using edge-tts word boundaries.

Instead of showing the entire comment text at once, each word is highlighted
as the TTS voice speaks it. This increases perceived energy and viewer retention.

Acceptance criteria:
- split_into_word_segments() exists in tts/engine.py
- Returns list of {word, start_time, end_time} dicts
- Timing is monotonically increasing
- render_word_caption() in card_renderer renders a single word as overlay
- Word overlay is full-canvas RGBA
"""
import pytest


def test_split_into_word_segments_exists():
    """split_into_word_segments must be importable from tts.engine."""
    from tts.engine import split_into_word_segments
    assert callable(split_into_word_segments)


def test_word_segments_structure():
    """split_into_word_segments returns correctly structured word-timing data."""
    from tts.engine import split_into_word_segments

    # Simulate edge-tts word boundary events
    fake_events = [
        {"type": "WordBoundary", "offset": 0,        "duration": 3_750_000, "text": "Hello"},
        {"type": "WordBoundary", "offset": 4_375_000, "duration": 3_750_000, "text": "world"},
        {"type": "WordBoundary", "offset": 9_375_000, "duration": 5_000_000, "text": "today"},
    ]
    result = split_into_word_segments(fake_events)

    assert len(result) == 3
    for seg in result:
        assert "word"       in seg
        assert "start_time" in seg
        assert "end_time"   in seg
        assert seg["end_time"] > seg["start_time"]


def test_word_segments_monotonic():
    """Word start times must be monotonically increasing."""
    from tts.engine import split_into_word_segments

    fake_events = [
        {"type": "WordBoundary", "offset": 0,         "duration": 3_000_000, "text": "A"},
        {"type": "WordBoundary", "offset": 4_000_000, "duration": 3_000_000, "text": "B"},
        {"type": "WordBoundary", "offset": 8_000_000, "duration": 3_000_000, "text": "C"},
    ]
    result = split_into_word_segments(fake_events)
    starts = [s["start_time"] for s in result]
    assert starts == sorted(starts), "Word start times are not monotonically increasing"


def test_render_word_caption_exists():
    """render_word_caption must be importable from card_renderer."""
    from video.card_renderer import render_word_caption
    assert callable(render_word_caption)


def test_render_word_caption_returns_full_canvas():
    """render_word_caption returns a 1080×1920 RGBA image."""
    from video.card_renderer import render_word_caption
    from PIL import Image

    img = render_word_caption("MARRIED", video_width=1080, video_height=1920)
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"


def test_render_word_caption_has_visible_pixels():
    """render_word_caption must draw visible (non-transparent) pixels."""
    from video.card_renderer import render_word_caption

    img = render_word_caption("NTA", video_width=1080, video_height=1920)
    alpha = img.split()[3]
    opaque = sum(1 for p in alpha.getdata() if p > 200)
    assert opaque > 200, "Word caption appears blank"
