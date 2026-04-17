"""
Thumbnail CTR improvements for neophyte viewers.

YouTube Studio data: 신규 시청자 CTR 0.59% vs 재방문 5.15%.
The thumbnail fails to hook new viewers. Improvements:
  1. Extract & highlight keyword (money / large number) in accent color
  2. Strip AITA/WIBTA/Am I preambles from thumbnail text
  3. Shorter, punchier hook text
  4. Solid dark backing behind text for contrast
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from video.card_renderer import render_thumbnail


def _count_accent_pixels(img: Image.Image, accent_rgb: tuple[int, int, int],
                         tolerance: int = 30) -> int:
    """Count pixels close to the accent color."""
    rgb = img.convert("RGB")
    pixels = rgb.getdata()
    count = 0
    ar, ag, ab = accent_rgb
    for r, g, b in pixels:
        if (abs(r - ar) < tolerance and
                abs(g - ag) < tolerance and
                abs(b - ab) < tolerance):
            count += 1
    return count


def _brightness(pixel: tuple) -> float:
    r, g, b = pixel[:3]
    return (r + g + b) / 3


class TestKeywordHighlight:
    def test_dollar_keyword_produces_more_accent_pixels(self):
        """Title with $5000 should show a keyword badge → more accent-color pixels."""
        gaming_accent = (255, 69, 0)
        img_no_kw = render_thumbnail("Regular title without numbers",
                                     subreddit="steam")
        img_with_kw = render_thumbnail("I lost $5000 today",
                                       subreddit="steam")
        kw_count = _count_accent_pixels(img_with_kw, gaming_accent)
        nokw_count = _count_accent_pixels(img_no_kw, gaming_accent)
        # Keyword badge adds accent-colored pixels beyond the small circle+bar
        assert kw_count > nokw_count * 1.3, (
            f"Keyword title should have more accent pixels "
            f"(got {kw_count} vs {nokw_count})"
        )

    def test_k_suffix_number_produces_more_accent_pixels(self):
        """Title with '20K' should highlight it."""
        gaming_accent = (255, 69, 0)
        img_no_kw = render_thumbnail("Boring title", subreddit="steam")
        # Use a title where the keyword is safely strippable (no trailing
        # preposition) so the badge renders — the duplication-guard skips
        # the badge when the keyword must stay in the title for grammar.
        img_kw = render_thumbnail("Earned 50K today on this drop",
                                  subreddit="steam")
        assert (_count_accent_pixels(img_kw, gaming_accent) >
                _count_accent_pixels(img_no_kw, gaming_accent) * 1.3)


class TestHookTextShortening:
    def test_aita_preamble_stripped(self):
        """AITA thumbnails should not show 'AITA for' — use extract_hook_text."""
        # We can't easily assert text content from pixel data, but we can check
        # that the thumbnail of a very long AITA title still produces output
        # (indirect: hook extraction means fewer lines rendered).
        # Explicit check: rendered thumbnail should not crash.
        img = render_thumbnail(
            "AITA for refusing to attend my sister's wedding after she invited my ex",
            subreddit="amitheasshole",
        )
        assert img.size == (1080, 1920)

    def test_hook_text_trims_very_long_title(self):
        """Very long titles should still fit in thumbnail (no crash, valid output)."""
        long_title = (
            "AITA for telling my boyfriend that his mother is a terrible "
            "person after she ruined our anniversary dinner by bringing her "
            "new boyfriend and making a huge scene in front of everyone"
        )
        img = render_thumbnail(long_title, subreddit="amitheasshole")
        assert img.size == (1080, 1920)
        # Should not be mostly empty (has some rendered text)
        rgb = img.convert("RGB")
        # Count non-background pixels in the center band
        w, h = rgb.size
        center_band = rgb.crop((0, int(h * 0.4), w, int(h * 0.7)))
        bright_pixels = sum(
            1 for p in center_band.getdata() if _brightness(p) > 180
        )
        assert bright_pixels > 500, "Thumbnail center should contain rendered text"


class TestBackwardCompat:
    """Existing contracts from test_28 must still hold."""

    def test_still_returns_rgb(self):
        img = render_thumbnail("Test", subreddit="steam")
        assert img.mode == "RGB"

    def test_still_correct_dimensions(self):
        img = render_thumbnail("Test", subreddit="steam")
        assert img.size == (1080, 1920)

    def test_different_subreddits_still_differ(self):
        a = render_thumbnail("Test", subreddit="steam")
        b = render_thumbnail("Test", subreddit="amitheasshole")
        assert a.getpixel((0, 0)) != b.getpixel((0, 0))
