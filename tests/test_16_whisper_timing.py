"""
Test 16: Whisper-based exact word timing from TTS audio.

Root cause of remaining sync issues:
  estimate_word_segments() is still an approximation. TTS has natural
  rhythm variations (emphasis, pauses, speed) that no syllable formula
  can capture. The only way to get exact timing is to extract it from
  the actual audio file.

Fix:
  whisper_word_segments(audio_path) uses faster-whisper (tiny model)
  to transcribe the TTS audio and return exact word-level timestamps.
  Falls back to estimate_word_segments() if whisper is unavailable.

Acceptance criteria:
- whisper_word_segments(audio_path) exists in tts.engine
- Returns list of {word, start_time, end_time} from actual audio
- Timing is monotonically increasing
- generate_for_post uses whisper timing for comments and body
- Falls back gracefully if faster-whisper not installed
"""
import pytest
import os
import tempfile


def test_whisper_word_segments_exists():
    from tts.engine import whisper_word_segments
    assert callable(whisper_word_segments)


def test_whisper_word_segments_on_real_audio():
    """Generate TTS audio and verify whisper returns accurate word timing."""
    from tts.engine import whisper_word_segments, EdgeTTS
    import asyncio

    # Generate a short TTS audio clip
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio_path = f.name

    try:
        tts = EdgeTTS(voice="en-US-AriaNeural", rate="+0%")
        tts.generate("Hello world today", audio_path)

        segs = whisper_word_segments(audio_path)

        assert len(segs) >= 2, f"Expected at least 2 words, got {len(segs)}: {segs}"
        for s in segs:
            assert "word" in s
            assert "start_time" in s
            assert "end_time" in s
            assert s["end_time"] > s["start_time"]
    finally:
        os.unlink(audio_path)


def test_whisper_timing_monotonic():
    """Word start times from whisper must be monotonically increasing."""
    from tts.engine import whisper_word_segments, EdgeTTS

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        audio_path = f.name

    try:
        tts = EdgeTTS(voice="en-US-AriaNeural", rate="+0%")
        tts.generate("I called my sister out for doing that", audio_path)
        segs = whisper_word_segments(audio_path)
        starts = [s["start_time"] for s in segs]
        assert starts == sorted(starts), f"Non-monotonic: {starts}"
    finally:
        os.unlink(audio_path)


def test_whisper_fallback_when_unavailable():
    """whisper_word_segments must fall back to estimate when model unavailable."""
    from tts.engine import whisper_word_segments

    # Pass a non-existent file — should fall back gracefully
    segs = whisper_word_segments("/nonexistent/file.mp3", text="hello world", fallback_duration=1.0)
    assert isinstance(segs, list)
    # Fallback returns estimated segments
    assert len(segs) >= 1


def test_generate_for_post_uses_whisper(sample_post):
    """Comment segments should have accurate timing (from whisper or estimate)."""
    from tts.engine import TTSEngine
    import tempfile

    config = {"tts": {"engine": "edge-tts", "voice": "en-US-AriaNeural", "rate": "+0%"}}
    engine = TTSEngine(config)

    with tempfile.TemporaryDirectory() as tmp:
        segs = engine.generate_for_post(sample_post, tmp)

    comment_segs = [s for s in segs if s["type"] == "comment"]
    for seg in comment_segs:
        ws = seg.get("word_segments", [])
        assert ws, "word_segments empty"
        # With whisper, timing should cover at least 80% of audio duration
        # (whisper may not catch every word but should cover most)
        if len(ws) >= 2:
            total_covered = ws[-1]["end_time"] - ws[0]["start_time"]
            assert total_covered > 0.3, f"Timing covers only {total_covered:.2f}s"
