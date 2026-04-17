"""
Subreddit-tier-based filter thresholds.

YouTube Studio data showed AITA/PettyRevenge posts performed far worse
than Steam/manga/BuyItForLife. To let only high-signal drama through
while keeping the bar relaxed for strong-performing niches, each
subreddit gets its own (min_score, min_comments) tier.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reddit.scraper import RedditScraper


def _make_scraper(min_upvotes=100, min_comments=10):
    config = {
        "reddit": {
            "subreddits": ["AmItheAsshole"],
            "min_upvotes": min_upvotes,
            "min_comments": min_comments,
        },
        "output": {"history_file": "/tmp/_nonexistent_history.json"},
    }
    return RedditScraper(config)


def test_aita_tier_has_high_bar():
    """AITA needs score>=5000 & comments>=500 (poor CTR → strict filter)."""
    s = _make_scraper()
    min_score, min_comments = s._tier_threshold("AmItheAsshole")
    assert min_score >= 5000
    assert min_comments >= 500


def test_pettyrevenge_tier_has_high_bar():
    """PettyRevenge also performed poorly → strict filter."""
    s = _make_scraper()
    min_score, min_comments = s._tier_threshold("pettyrevenge")
    assert min_score >= 5000
    assert min_comments >= 500


def test_tifu_tier_has_high_bar():
    """TIFU same tier as AITA (story drama)."""
    s = _make_scraper()
    min_score, min_comments = s._tier_threshold("tifu")
    assert min_score >= 5000


def test_steam_tier_uses_config_defaults():
    """Steam performed well → keep config defaults."""
    s = _make_scraper(min_upvotes=100, min_comments=10)
    min_score, min_comments = s._tier_threshold("Steam")
    # Should not be the strict tier
    assert min_score < 5000
    assert min_score == 100
    assert min_comments == 10


def test_manga_tier_uses_config_defaults():
    """manga performed well → config defaults."""
    s = _make_scraper(min_upvotes=100, min_comments=10)
    min_score, _ = s._tier_threshold("manga")
    assert min_score == 100


def test_buyitforlife_tier_uses_config_defaults():
    """BuyItForLife performed well → config defaults."""
    s = _make_scraper(min_upvotes=100, min_comments=10)
    min_score, _ = s._tier_threshold("BuyItForLife")
    assert min_score == 100


def test_case_insensitive_lookup():
    """Subreddit lookup should be case-insensitive."""
    s = _make_scraper()
    lower = s._tier_threshold("amitheasshole")
    upper = s._tier_threshold("AmItheAsshole")
    assert lower == upper


def test_unknown_subreddit_uses_config():
    """Unknown subreddit falls back to config defaults."""
    s = _make_scraper(min_upvotes=100, min_comments=10)
    min_score, min_comments = s._tier_threshold("SomeRandomSub")
    assert min_score == 100
    assert min_comments == 10
