"""Tests for dedicated thumbnail renderer (render_thumbnail)."""

from PIL import Image
import pytest


def _make_post(title="What an upgrade lmao", subreddit="steam"):
    from reddit.scraper import RedditPost
    return RedditPost(
        id="test", title=title, body="", author="user",
        score=1234, url="", subreddit=subreddit,
    )


class TestRenderThumbnail:
    def test_returns_pil_image(self):
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", subreddit="steam")
        assert isinstance(img, Image.Image)

    def test_correct_dimensions(self):
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", subreddit="steam")
        assert img.size == (1080, 1920)

    def test_rgb_mode_not_rgba(self):
        """Thumbnail must be RGB so it saves without white transparency artifacts."""
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", subreddit="steam")
        assert img.mode == "RGB"

    def test_not_white_background(self):
        """Background must NOT be pure white — that's the current broken behavior."""
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", subreddit="steam")
        # Check top-left corner pixel: should be dark, not white
        r, g, b = img.getpixel((0, 0))
        brightness = (r + g + b) / 3
        assert brightness < 200, f"Background too bright (looks white): brightness={brightness:.0f}"

    def test_different_subreddits_different_colors(self):
        """Gaming vs AITA should produce visually different thumbnails."""
        from video.card_renderer import render_thumbnail
        img_gaming = render_thumbnail("Test", subreddit="steam")
        img_aita = render_thumbnail("Test", subreddit="amitheasshole")
        # At least some pixels should differ
        px_gaming = img_gaming.getpixel((0, 0))
        px_aita = img_aita.getpixel((0, 0))
        assert px_gaming != px_aita

    def test_custom_dimensions(self):
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", video_width=720, video_height=1280)
        assert img.size == (720, 1280)

    def test_long_title_does_not_crash(self):
        from video.card_renderer import render_thumbnail
        long_title = "This is a very long title that should wrap across multiple lines without crashing the renderer at all"
        img = render_thumbnail(long_title, subreddit="steam")
        assert img.size == (1080, 1920)

    def test_empty_subreddit_does_not_crash(self):
        from video.card_renderer import render_thumbnail
        img = render_thumbnail("Test title", subreddit="")
        assert isinstance(img, Image.Image)
