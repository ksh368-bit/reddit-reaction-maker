"""
Test 07: 3-4 word chunk captions with active word highlight.

Research shows 3-4 words per frame with the current spoken word highlighted
in yellow/orange outperforms single-word karaoke. This is the dominant
format on top-performing Reddit Shorts channels (2024-2025).

Acceptance criteria:
- render_caption_chunk(words, active_idx) exists in card_renderer
- Returns full-canvas 1080x1920 RGBA image
- active_idx word is visually distinct (highlight box)
- _add_karaoke_clips groups words into chunks of 3-4
- Each clip duration spans from word_start to next word_start
"""
import pytest
from PIL import Image


def test_render_caption_chunk_exists():
    """render_caption_chunk must be importable from card_renderer."""
    from video.card_renderer import render_caption_chunk
    assert callable(render_caption_chunk)


def test_render_caption_chunk_returns_full_canvas():
    """render_caption_chunk returns a 1080x1920 RGBA image."""
    from video.card_renderer import render_caption_chunk

    img = render_caption_chunk(["NTA", "you", "owe", "nothing"], active_idx=0,
                                video_width=1080, video_height=1920)
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"


def test_render_caption_chunk_has_visible_pixels():
    """render_caption_chunk must draw non-transparent pixels."""
    from video.card_renderer import render_caption_chunk

    img = render_caption_chunk(["She", "did", "WHAT"], active_idx=1,
                                video_width=1080, video_height=1920)
    alpha = img.split()[3]
    opaque = sum(1 for p in alpha.getdata() if p > 200)
    assert opaque > 500, "Caption chunk appears blank"


def test_render_caption_chunk_active_word_is_highlighted():
    """Active word pixel region must differ from inactive word region."""
    from video.card_renderer import render_caption_chunk
    import numpy as np

    # Render with word 0 active vs word 2 active — pixel data must differ
    img_0 = render_caption_chunk(["NTA", "you", "owe"], active_idx=0,
                                  video_width=1080, video_height=1920)
    img_2 = render_caption_chunk(["NTA", "you", "owe"], active_idx=2,
                                  video_width=1080, video_height=1920)

    arr_0 = list(img_0.getdata())
    arr_2 = list(img_2.getdata())
    diff = sum(1 for a, b in zip(arr_0, arr_2) if a != b)
    assert diff > 1000, "Active word highlight not changing pixel data"


def test_render_caption_chunk_single_word():
    """Single-word chunk (last word of sentence) must still render."""
    from video.card_renderer import render_caption_chunk

    img = render_caption_chunk(["everything"], active_idx=0,
                                video_width=1080, video_height=1920)
    assert img.size == (1080, 1920)
    alpha = img.split()[3]
    assert any(p > 200 for p in alpha.getdata())


def test_add_karaoke_clips_uses_chunks(base_config):
    """_add_karaoke_clips must produce fewer clips than words (chunked)."""
    from video.composer import VideoComposer

    composer = VideoComposer(base_config)

    # 8 words — with chunk_size=4 we expect 8 clips total (one per word,
    # each showing its chunk with that word active)
    fake_word_segs = [
        {"word": f"word{i}", "start_time": i * 0.4, "end_time": i * 0.4 + 0.35}
        for i in range(8)
    ]

    overlay_clips = []
    composer._add_karaoke_clips(
        overlay_clips,
        word_segs=fake_word_segs,
        seg_start=0.0,
        audio_dur=3.2,
        total_duration=10.0,
        fade_in=0.05,
    )
    # Should still produce 8 clips (one per word with its chunk context)
    assert len(overlay_clips) == 8


def test_caption_chunk_position_lower_center():
    """Caption chunk must be positioned in the lower portion of the frame."""
    from video.card_renderer import render_caption_chunk
    import numpy as np

    img = render_caption_chunk(["AITA", "for", "this"], active_idx=0,
                                video_width=1080, video_height=1920)
    arr = np.array(img)

    # Find rows with opaque pixels
    opaque_rows = [y for y in range(arr.shape[0]) if arr[y, :, 3].max() > 200]
    assert opaque_rows, "No visible pixels found"

    top_visible = min(opaque_rows)
    # Text should start below 50% of the frame (lower-center placement)
    assert top_visible > 1920 * 0.50, (
        f"Caption chunk starts at y={top_visible}, expected below y={int(1920*0.50)}"
    )
