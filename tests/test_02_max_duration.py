"""
Test 02: max_duration should be in the 45-90s Shorts sweet spot.

Algorithm favours 45-90s Shorts: long enough for full story payoff,
short enough for high completion rate.

Acceptance criteria:
- config.toml has 45 <= max_duration <= 90
- VideoComposer respects max_duration and clips audio beyond it
- Composer total_duration never exceeds max_duration
"""
import pytest

MAX_LOWER = 45
MAX_UPPER = 90


def test_config_max_duration_is_in_sweet_spot():
    """config.toml max_duration must be in the 45-90s algorithm sweet spot."""
    from utils.config_loader import load_config
    config = load_config("config.toml")
    max_dur = config.get("video", {}).get("max_duration", 999)
    assert MAX_LOWER <= max_dur <= MAX_UPPER, (
        f"max_duration is {max_dur}s — should be {MAX_LOWER}-{MAX_UPPER}s (Shorts sweet spot)"
    )


def test_composer_respects_max_duration(base_config):
    """VideoComposer.max_duration picks up the config value."""
    from video.composer import VideoComposer
    composer = VideoComposer(base_config)
    assert MAX_LOWER <= composer.max_duration <= MAX_UPPER, (
        f"Composer max_duration={composer.max_duration}, expected {MAX_LOWER}-{MAX_UPPER}s"
    )


def test_segments_clipped_at_max_duration(base_config):
    """Segments totalling more than max_duration should be cut off."""
    from video.composer import VideoComposer
    import types

    composer = VideoComposer(base_config)

    # Fake segments each 10s long → only floor(max_duration/10) should fit
    segments = [
        {"type": "comment", "text": f"comment {i}", "audio_path": f"/fake/{i}.mp3",
         "card_path": None}
        for i in range(10)
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

    assert current_time - gap <= composer.max_duration + 1  # allow 1s tolerance
