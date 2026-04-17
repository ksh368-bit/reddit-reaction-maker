"""
Thumbnail polish fixes:
  1. 💬 tofu box removed — use drawn icon instead of emoji font.
  2. Keyword de-duplication — keyword badge shouldn't duplicate in title.
  3. Tighter vertical rhythm — less whitespace between elements.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.card_renderer import render_thumbnail, _strip_keyword_from_title


class TestKeywordStripping:
    def test_dollar_amount_stripped_when_at_end(self):
        """End-of-title keyword has no grammar dependency → safe to strip."""
        out = _strip_keyword_from_title("I lost everything, $500", "$500")
        assert "$500" not in out

    def test_k_suffix_stripped_when_safe(self):
        """Non-preposition context → safe to strip."""
        out = _strip_keyword_from_title("Earned 50K today", "50K")
        assert "50K" not in out and "50k" not in out

    def test_case_insensitive(self):
        out = _strip_keyword_from_title("I earned 5K", "5K")
        assert "5K" not in out and "5k" not in out

    def test_no_keyword_returns_title(self):
        out = _strip_keyword_from_title("Plain title", None)
        assert out == "Plain title"

    def test_double_spaces_collapsed(self):
        """After stripping, leftover spaces should be normalized."""
        out = _strip_keyword_from_title(
            "I won $500 today overall", "$500"
        )
        assert "  " not in out  # no double spaces
        assert out.strip() == out  # no leading/trailing space


class TestNoCrash:
    def test_renders_with_keyword(self):
        img = render_thumbnail(
            "Refusing to pay my roommate $500 for rent",
            subreddit="amitheasshole",
            score=8200, num_comments=1400,
        )
        assert img.size == (1080, 1920)

    def test_renders_without_keyword(self):
        img = render_thumbnail("No numbers here",
                               subreddit="amitheasshole",
                               score=500, num_comments=100)
        assert img.size == (1080, 1920)
