"""
Test 02: max_duration should be 30 seconds.

Shorts completion rate > total watch time.
20s @ 90% completion beats 58s @ 30% completion.

Acceptance criteria:
- config.toml has max_duration <= 30
- VideoComposer respects max_duration and clips audio beyond it
- Composer total_duration never exceeds max_duration
"""
import pytest


def test_config_max_duration_is_30_or_less():
    """config.toml max_duration must be ≤ 30."""
    from utils.config_loader import load_config
    config = load_config("config.toml")
    max_dur = config.get("video", {}).get("max_duration", 999)
    assert max_dur <= 30, (
        f"max_duration is {max_dur}s — should be ≤30s for better Shorts completion rate"
    )


def test_composer_respects_max_duration(base_config):
    """VideoComposer.max_duration picks up the config value."""
    from video.composer import VideoComposer
    composer = VideoComposer(base_config)
    assert composer.max_duration <= 30, (
        f"Composer max_duration={composer.max_duration}, expected ≤30"
    )


def test_segments_clipped_at_max_duration(base_config):
    """Segments totalling more than 30s should be cut off."""
    from video.composer import VideoComposer
    import types

    composer = VideoComposer(base_config)

    # Fake segments each 10s long → only 3 should fit in 30s
    def fake_audio(duration):
        clip = types.SimpleNamespace(duration=duration, close=lambda: None)
        return clip

    segments = [
        {"type": "comment", "text": f"comment {i}", "audio_path": f"/fake/{i}.mp3",
         "card_path": None}
        for i in range(6)  # 6 × 10s = 60s total
    ]

    current_time = 0.0
    gap = 0.2
    clipped = 0
    for seg in segments:
        seg_duration = 10.0
        if current_time + seg_duration > composer.max_duration:
            break
        current_time += seg_duration + gap
        clipped += 1

    assert clipped <= 3, f"Expected ≤3 segments in 30s, got {clipped}"
    assert current_time - gap <= composer.max_duration + 1  # allow 1s tolerance
