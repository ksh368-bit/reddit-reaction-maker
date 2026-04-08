"""
Test 11: Post body must always be read after title, before comments.

Current bug: body text is skipped when len(body) > 300 chars.
AITA posts routinely have 500-2000 char bodies.

Acceptance criteria:
- generate_for_post includes body segment regardless of length
- Body segment is ordered: title → body → comments
- Long body text is truncated to max_chars (same as TTS limit)
- Body segment has word_segments for karaoke
"""
import pytest


def _make_post(body: str):
    from reddit.scraper import RedditPost, Comment
    return RedditPost(
        id="testbody",
        title="AITA for doing the thing",
        body=body,
        author="user",
        score=1000,
        url="",
        subreddit="AmItheAsshole",
        num_comments=5,
        comments=[
            Comment(id="c1", author="a", body="NTA you did the right thing.", score=100),
        ],
    )


def test_short_body_included():
    """Short body (< 300 chars) must be included as a segment."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)
    post = _make_post("This is a short body text.")

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(post, tmp)

    types = [s["type"] for s in segs]
    assert "body" in types, f"Short body not included. Segments: {types}"


def test_long_body_included():
    """Long body (> 300 chars) must also be included as a segment."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)
    long_body = "So this is a long story. " * 30  # ~750 chars
    post = _make_post(long_body)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(post, tmp)

    types = [s["type"] for s in segs]
    assert "body" in types, (
        f"Long body ({len(long_body)} chars) was skipped. "
        "Body must always be included regardless of length."
    )


def test_segment_order_is_title_body_comments():
    """Segments must be ordered: title → body → comments."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)
    post = _make_post("My wife disagreed and I did what I had to do.")

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(post, tmp)

    types = [s["type"] for s in segs]
    assert types[0] == "title", f"First segment is not title: {types}"
    assert "body" in types, f"No body segment: {types}"
    body_idx = types.index("body")
    first_comment_idx = next((i for i, t in enumerate(types) if t == "comment"), len(types))
    assert body_idx < first_comment_idx, (
        f"Body segment (idx={body_idx}) comes after comments (idx={first_comment_idx})"
    )


def test_body_has_word_segments():
    """Body segment must have word_segments for karaoke display."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)
    post = _make_post("My wife disagreed with me on this one.")

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(post, tmp)

    body_segs = [s for s in segs if s["type"] == "body"]
    assert body_segs, "No body segments found"
    for seg in body_segs:
        assert seg.get("word_segments"), (
            "Body segment missing word_segments — karaoke won't work for body"
        )
