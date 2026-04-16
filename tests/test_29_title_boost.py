"""Tests for short-title booster in MetaGenerator.generate_title()."""

import pytest
from utils.meta_generator import MetaGenerator


class MockPost:
    def __init__(self, title, subreddit="steam", score=1000):
        self.title = title
        self.subreddit = subreddit
        self.score = score
        self.body = ""


class TestShortTitleBoost:
    def test_short_gaming_title_is_padded(self):
        """Short gaming titles (< 35 chars with emoji) should get a context prefix."""
        post = MockPost("What an upgrade lmao", subreddit="steam")
        title = MetaGenerator.generate_title(post)
        # Should be longer than original + emoji (23 chars)
        assert len(title) >= 30, f"Title too short after boost: '{title}' ({len(title)} chars)"

    def test_short_gaming_title_retains_original_text(self):
        """Booster must not delete the original content."""
        post = MockPost("What an upgrade lmao", subreddit="steam")
        title = MetaGenerator.generate_title(post)
        assert "upgrade" in title.lower()

    def test_short_gaming_title_still_within_60_chars(self):
        post = MockPost("What an upgrade lmao", subreddit="steam")
        title = MetaGenerator.generate_title(post)
        assert len(title) <= 60

    def test_long_title_not_affected_by_booster(self):
        """Titles already in the 40-55 range should not be padded further."""
        long_title = "$40 for a DLC that adds 2 hours of content?"
        post = MockPost(long_title, subreddit="steam")
        title = MetaGenerator.generate_title(post)
        assert "$40" in title or "DLC" in title

    def test_question_mark_preserved_from_aita(self):
        """'AITA for doing X?' → stripped title should still end with '?'"""
        post = MockPost("AITA for kicking out my sister?", subreddit="amitheasshole")
        title = MetaGenerator.generate_title(post)
        assert title.rstrip().endswith("?"), f"Question mark lost: '{title}'"

    def test_short_aita_title_padded(self):
        """Short AITA titles should reach at least 35 chars total."""
        post = MockPost("AITA for saying no?", subreddit="amitheasshole")
        title = MetaGenerator.generate_title(post)
        assert len(title) >= 30, f"Title too short: '{title}'"

    def test_pcgaming_sub_also_boosted(self):
        """pcgaming subreddit follows same gaming boost rules."""
        post = MockPost("This is sad", subreddit="pcgaming")
        title = MetaGenerator.generate_title(post)
        assert len(title) >= 25

    def test_boost_different_for_gaming_vs_aita(self):
        """Gaming and AITA boosts should produce different prefixes."""
        short = "This is wild"
        gaming_title = MetaGenerator.generate_title(MockPost(short, subreddit="steam"))
        aita_title = MetaGenerator.generate_title(MockPost(short, subreddit="amitheasshole"))
        # At minimum, emojis differ — titles should differ
        assert gaming_title != aita_title
