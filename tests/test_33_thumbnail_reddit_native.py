"""
Thumbnail improvements: Reddit-native look + real color emoji.

Direction 1: Use Apple Color Emoji for real colored icons (instead of
            programmatic circle+triangle).
Direction 3: Reddit-native aesthetic — dark card look with upvote
            arrow, score, num_comments, r/subreddit header.

These make the thumbnail feel like an authentic Reddit post enlargement,
driving neophyte click-through on channel page and search results.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from video.card_renderer import render_thumbnail


def _bright_pixel_count(img: Image.Image, region: tuple, threshold: int = 170) -> int:
    """Count bright (text-like) pixels in a region."""
    rgb = img.convert("RGB").crop(region)
    return sum(1 for p in rgb.getdata() if (p[0] + p[1] + p[2]) / 3 >= threshold)


class TestRedditNativeSignature:
    def test_accepts_score_parameter(self):
        img = render_thumbnail("Title", subreddit="steam", score=5432)
        assert img.size == (1080, 1920)

    def test_accepts_num_comments_parameter(self):
        img = render_thumbnail("Title", subreddit="steam",
                               score=5432, num_comments=890)
        assert img.size == (1080, 1920)

    def test_backward_compat_without_score(self):
        """Existing callsites without score/num_comments still work."""
        img = render_thumbnail("Title", subreddit="steam")
        assert img.size == (1080, 1920)


class TestScoreRendering:
    def test_score_increases_text_pixels(self):
        """When score is provided, score text should render as extra bright pixels."""
        # Bottom region where score row should appear (below accent bar ~1574)
        bottom_region = (0, 1580, 1080, 1780)
        img_no_score = render_thumbnail("Short", subreddit="steam")
        img_score = render_thumbnail("Short", subreddit="steam", score=9500)
        px_no = _bright_pixel_count(img_no_score, bottom_region)
        px_yes = _bright_pixel_count(img_score, bottom_region)
        assert px_yes > px_no, (
            f"Score rendering should add bright pixels to bottom: {px_yes} vs {px_no}"
        )


class TestEmojiRendering:
    def test_emoji_region_has_colored_pixels(self):
        """Apple Color Emoji should produce colored (non-grayscale) pixels."""
        # Top region where icon/emoji is drawn
        img = render_thumbnail("Test", subreddit="amitheasshole")
        top_region = img.crop((400, 250, 680, 530))
        # Colored pixels = R,G,B values differ meaningfully
        colored = 0
        for p in top_region.convert("RGB").getdata():
            r, g, b = p
            spread = max(r, g, b) - min(r, g, b)
            if spread > 40:  # Colored, not grayscale
                colored += 1
        assert colored > 300, (
            f"Emoji region should contain colored pixels (got {colored})"
        )


class TestBackwardCompatFromTest28:
    def test_still_rgb(self):
        img = render_thumbnail("Test", subreddit="steam")
        assert img.mode == "RGB"

    def test_still_correct_dimensions(self):
        img = render_thumbnail("Test", subreddit="steam")
        assert img.size == (1080, 1920)
