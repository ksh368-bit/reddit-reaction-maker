"""
Test 06: Karaoke word-caption pipeline wiring.

When edge-tts word boundary events are present in a segment,
compose_video must generate per-word overlay clips (karaoke style)
instead of a single static card.

Acceptance criteria:
- TTSEngine.generate_audio supports capture_boundaries=True
- EdgeTTS.generate_with_boundaries returns (path, events) tuple
- generate_for_post stores word_segments in comment segments
- VideoComposer._add_karaoke_clips is callable
- render_word_caption produces correct output (from test_05, re-confirmed here)
"""
import pytest


def test_generate_audio_capture_boundaries_signature():
    """generate_audio must accept capture_boundaries kwarg."""
    from tts.engine import TTSEngine
    import inspect
    sig = inspect.signature(TTSEngine.generate_audio)
    assert "capture_boundaries" in sig.parameters


def test_edge_tts_has_generate_with_boundaries():
    """EdgeTTS must have generate_with_boundaries method."""
    from tts.engine import EdgeTTS
    assert callable(getattr(EdgeTTS, "generate_with_boundaries", None))


def test_generate_for_post_stores_word_segments(sample_post):
    """generate_for_post must include word_segments key in comment segments."""
    from tts.engine import TTSEngine
    import tempfile, os

    config = {
        "tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}
    }
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segments = engine.generate_for_post(sample_post, tmp)

    comment_segs = [s for s in segments if s["type"] == "comment"]
    assert len(comment_segs) > 0, "No comment segments generated"
    for seg in comment_segs:
        assert "word_segments" in seg, (
            "Comment segment missing 'word_segments' key — karaoke wiring incomplete"
        )
        # word_segments can be empty if TTS fails, but key must exist
        assert isinstance(seg["word_segments"], list)


def test_composer_has_add_karaoke_clips():
    """VideoComposer must have _add_karaoke_clips method."""
    from video.composer import VideoComposer
    assert callable(getattr(VideoComposer, "_add_karaoke_clips", None))


def test_word_segments_used_when_present(base_config, sample_post):
    """If word_segments present in segment, karaoke path is taken (no card_path needed)."""
    from video.composer import VideoComposer

    composer = VideoComposer(base_config)

    # Simulate a comment segment with word boundaries
    fake_word_segs = [
        {"word": "NTA", "start_time": 0.0, "end_time": 0.4},
        {"word": "you", "start_time": 0.45, "end_time": 0.7},
        {"word": "owe", "start_time": 0.75, "end_time": 1.0},
    ]

    overlay_clips = []
    composer._add_karaoke_clips(
        overlay_clips,
        word_segs=fake_word_segs,
        seg_start=0.0,
        audio_dur=1.0,
        total_duration=5.0,
        fade_in=0.1,
    )
    # Should produce exactly 3 clips (one per word)
    assert len(overlay_clips) == 3, (
        f"Expected 3 karaoke clips, got {len(overlay_clips)}"
    )
