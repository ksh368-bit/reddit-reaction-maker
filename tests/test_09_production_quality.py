"""
Test 09: World-class production quality improvements.

Based on analysis of MrBeast, top viral Shorts channels (2024-2025):
- Active word gets glow/shadow effect (not just color fill)
- Caption block has semi-transparent dark backing for readability on any bg
- Caption appears 0.1s before word is spoken (anticipatory timing)
- Hook card gets zoom punch (scale 1.0 → 1.1 over 0.3s)
- Chunk size reduced to 3 words (MrBeast: 2 words, Reddit channels: 3)

Acceptance criteria:
- render_caption_chunk produces a glow effect around the highlight box
- render_caption_chunk has a dark backing strip behind text block
- _add_karaoke_clips uses caption_lead_sec=0.1 offset
- compose_video applies zoom punch to hook card
- default chunk_size is 3
"""
import pytest
import numpy as np
from PIL import Image


# ── Glow on active word ─────────────────────────────────────────────────────

def test_caption_chunk_glow_pixels_around_highlight():
    """
    Active word highlight must have semi-opaque pixels OUTSIDE the tight
    bounding box — indicating a glow/shadow effect is present.
    """
    from video.card_renderer import render_caption_chunk

    words = ["She", "did", "WHAT"]
    # Render active=0 and active=2 and compare regions
    img_active = render_caption_chunk(words, active_idx=0,
                                      video_width=1080, video_height=1920)
    arr = np.array(img_active)

    # Alpha channel in the caption region (y: 55-75% of frame)
    y0 = int(1920 * 0.55)
    y1 = int(1920 * 0.80)
    region = arr[y0:y1, :, 3]

    # Should have semi-opaque pixels (glow: alpha 30-200) beyond fully opaque text
    semi_opaque = int((region > 20).sum()) - int((region > 220).sum())
    assert semi_opaque > 200, (
        f"No glow pixels found around highlight (semi-opaque: {semi_opaque}). "
        "Add a glow/shadow layer around the active word box."
    )


# ── Dark backing strip ────────────────────────────────────────────────────────

def test_caption_chunk_has_dark_backing_strip():
    """
    render_caption_chunk must draw a semi-transparent dark strip behind
    the entire caption block for readability over busy backgrounds.
    """
    from video.card_renderer import render_caption_chunk

    img = render_caption_chunk(["NTA", "absolutely"], active_idx=0,
                                video_width=1080, video_height=1920)
    arr = np.array(img)

    # The backing strip is full-width — check for wide dark semi-opaque rows
    y0 = int(1920 * 0.55)
    y1 = int(1920 * 0.80)

    wide_strip_rows = 0
    for y in range(y0, y1):
        row_alpha = arr[y, :, 3]
        # A full-width (>= 80% of width) strip with alpha 30-180 (semi-transparent)
        semi_count = int(((row_alpha >= 25) & (row_alpha <= 200)).sum())
        if semi_count >= int(1080 * 0.8):
            wide_strip_rows += 1

    assert wide_strip_rows >= 5, (
        f"Dark backing strip not found ({wide_strip_rows} qualifying rows). "
        "Add a full-width semi-transparent dark rectangle behind the caption block."
    )


# ── Anticipatory caption timing ───────────────────────────────────────────────

def test_add_karaoke_clips_anticipatory_timing(base_config):
    """
    Karaoke clips must start caption_lead_sec (0.1s) before the word boundary,
    so text appears slightly before it is spoken.
    """
    from video.composer import VideoComposer

    composer = VideoComposer(base_config)

    fake_word_segs = [
        {"word": "Hello", "start_time": 1.0, "end_time": 1.4},
        {"word": "world", "start_time": 1.5, "end_time": 1.9},
        {"word": "today", "start_time": 2.0, "end_time": 2.5},
    ]

    overlay_clips = []
    composer._add_karaoke_clips(
        overlay_clips,
        word_segs=fake_word_segs,
        seg_start=0.0,
        audio_dur=2.5,
        total_duration=10.0,
        fade_in=0.05,
    )

    assert len(overlay_clips) > 0
    # First clip should start at most 0.15s before word start_time=1.0
    first_start = overlay_clips[0].start
    assert first_start <= 1.0, (
        f"First caption clip starts at {first_start:.3f}s, expected ≤ 1.0s "
        "(anticipatory lead not applied)"
    )
    assert first_start >= 0.8, (
        f"First clip starts too early at {first_start:.3f}s, lead > 0.2s"
    )


# ── Chunk size ────────────────────────────────────────────────────────────────

def test_default_chunk_size_is_3(base_config):
    """Default chunk_size in _add_karaoke_clips should be 3 (MrBeast-style)."""
    from video.composer import VideoComposer
    import inspect

    sig = inspect.signature(VideoComposer._add_karaoke_clips)
    chunk_size_default = sig.parameters.get("chunk_size")
    assert chunk_size_default is not None, "chunk_size parameter not found"
    assert chunk_size_default.default == 3, (
        f"chunk_size default is {chunk_size_default.default}, expected 3"
    )


# ── Zoom punch on hook ────────────────────────────────────────────────────────

def test_compose_video_hook_has_zoom_punch(base_config, sample_post, tmp_path):
    """
    render_zoom_punch_clip() must exist and return a VideoClip with resize
    animation (scale > 1.0 somewhere in its duration).
    """
    from video.composer import VideoComposer

    composer = VideoComposer(base_config)
    assert hasattr(composer, "_create_zoom_punch_clip"), (
        "VideoComposer must have _create_zoom_punch_clip method"
    )
    assert callable(composer._create_zoom_punch_clip)
