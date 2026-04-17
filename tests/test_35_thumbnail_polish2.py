"""
Thumbnail polish round 2:
  1. Icon size increased (380px) — more presence
  2. buyitforlife + more subreddit emoji mappings
  3. Title auto-shrinks to fit (no mid-word truncation)
  4. Bare 3+ digit numbers detected as keywords (e.g. "3000")
  5. Smart keyword stripping — preserves grammar by keeping trailing
     preposition intact (don't strip when it'd orphan "for rent")
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.card_renderer import (
    render_thumbnail,
    detect_keyword,
    _strip_keyword_from_title,
    _THUMB_EMOJI,
)


class TestEmojiMapping:
    def test_buyitforlife_has_emoji(self):
        assert _THUMB_EMOJI.get("buyitforlife") is not None

    def test_lifeprotips_has_emoji(self):
        assert _THUMB_EMOJI.get("lifeprotips") is not None


class TestBareNumberDetection:
    def test_detects_3000(self):
        kw = detect_keyword("Just passed 3000 games owned on Steam")
        assert kw == "3000"

    def test_detects_4_digit(self):
        kw = detect_keyword("Bought 1500 items at the sale")
        assert kw == "1500"

    def test_dollar_still_preferred_over_bare_number(self):
        """When $ amount is present, prefer it over bare number."""
        kw = detect_keyword("Lost $500 and found 3000 pennies")
        assert kw == "$500"

    def test_small_numbers_not_detected(self):
        """Numbers under 100 shouldn't trigger badge (too common)."""
        assert detect_keyword("I had 3 apples") is None
        assert detect_keyword("Only 50 views") is None


class TestSmartStripping:
    def test_preserves_when_followed_by_preposition(self):
        """Don't strip $500 if removing it orphans 'for rent'."""
        out = _strip_keyword_from_title(
            "Refusing to pay my roommate $500 for rent", "$500"
        )
        # Should keep the keyword to preserve grammar
        assert "$500" in out or "for rent" not in out.split("$500")[-1]

    def test_strips_when_at_end(self):
        """Strip when keyword is at the end (no orphan)."""
        out = _strip_keyword_from_title("I lost $500", "$500")
        assert "$500" not in out


class TestTitleAutoFit:
    def test_long_title_does_not_get_truncated_to_meaninglessness(self):
        """Long titles should shrink font rather than cut off key words."""
        img = render_thumbnail(
            "Just passed 3000 games owned on Steam",
            subreddit="steam", score=5000, num_comments=500,
        )
        # Can't easily assert text content from pixels; verify no crash
        # and reasonable brightness in lower-half (title rendered)
        assert img.size == (1080, 1920)
        lower = img.crop((0, 800, 1080, 1700)).convert("RGB")
        bright = sum(1 for p in lower.getdata() if (p[0] + p[1] + p[2]) / 3 > 180)
        assert bright > 2000, "Title region should have substantial text pixels"


class TestBackwardCompat:
    def test_no_regression_existing_render(self):
        img = render_thumbnail("Test", subreddit="steam")
        assert img.size == (1080, 1920)
        assert img.mode == "RGB"
