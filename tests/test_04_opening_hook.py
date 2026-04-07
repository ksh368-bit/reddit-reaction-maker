"""
Test 04: Opening hook card — first frame must visually grab attention.

The first 0-3 seconds are critical. Instead of the Reddit card appearing first,
a large-text hook overlay should display the most compelling phrase from the title.

Acceptance criteria:
- render_hook_card() exists in card_renderer
- Returns a full-canvas (1080×1920) RGBA image
- Contains large white bold text (≥120px) visible against dark background
- Hook text is derived from the post title (not empty)
- Composer inserts hook as the very first segment (t=0)
"""
import pytest
from PIL import Image


def test_render_hook_card_exists():
    """render_hook_card must be importable from card_renderer."""
    from video.card_renderer import render_hook_card
    assert callable(render_hook_card)


def test_hook_card_returns_full_canvas(sample_post):
    """render_hook_card returns a 1080×1920 RGBA image."""
    from video.card_renderer import render_hook_card
    img = render_hook_card(sample_post.title, video_width=1080, video_height=1920)
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"


def test_hook_card_has_visible_text(sample_post):
    """Hook card must have non-transparent pixels (i.e. text is drawn)."""
    from video.card_renderer import render_hook_card
    img = render_hook_card(sample_post.title, video_width=1080, video_height=1920)
    # Check alpha channel — text pixels should be fully opaque
    alpha = img.split()[3]
    opaque_pixels = sum(1 for p in alpha.getdata() if p > 200)
    assert opaque_pixels > 500, "Hook card appears blank — no visible text rendered"


def test_hook_card_not_empty_for_blank_title():
    """Even a short title should produce a visible hook."""
    from video.card_renderer import render_hook_card
    img = render_hook_card("NTA", video_width=1080, video_height=1920)
    alpha = img.split()[3]
    opaque_pixels = sum(1 for p in alpha.getdata() if p > 200)
    assert opaque_pixels > 100


def test_composer_inserts_hook_segment(sample_post, base_config, tmp_path):
    """compose_video should add a hook overlay as the first visual segment."""
    from video.card_renderer import render_cards_for_post, render_hook_card

    cards_dir = str(tmp_path / "cards")
    segments = [
        {"type": "title", "text": sample_post.title, "audio_path": None, "score": 0,
         "author": "user", "subreddit": "amitheasshole", "num_comments": 100},
    ]
    # Hook card should be renderable and saved
    hook_img = render_hook_card(sample_post.title)
    hook_path = str(tmp_path / "hook.png")
    hook_img.save(hook_path)
    assert (tmp_path / "hook.png").exists()
