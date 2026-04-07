"""
Test 03: Default subreddit should be high-emotion content, not r/roblox.

Target subreddits for virality:
  r/AmItheAsshole, r/ChoosingBeggars, r/MaliciousCompliance,
  r/pettyrevenge, r/tifu

Acceptance criteria:
- config.toml subreddit is one of the high-emotion list
- RedditScraper picks up the config value correctly
"""
import pytest

HIGH_EMOTION_SUBREDDITS = {
    "amitheasshole",
    "choosingbeggars",
    "maliciouscompliance",
    "pettyrevenge",
    "tifu",
    "prorevenge",
    "entitledparents",
    "nuclearrevenge",
}


def test_config_subreddit_is_high_emotion():
    """config.toml subreddit must be a high-emotion sub, not r/roblox."""
    from utils.config_loader import load_config
    config = load_config("config.toml")
    sub = config.get("reddit", {}).get("subreddit", "").lower()
    assert sub in HIGH_EMOTION_SUBREDDITS, (
        f"subreddit='{sub}' is not a high-emotion subreddit. "
        f"Choose one of: {sorted(HIGH_EMOTION_SUBREDDITS)}"
    )


def test_scraper_uses_config_subreddit(base_config):
    """RedditScraper.subreddit_name must match config."""
    from reddit.scraper import RedditScraper
    base_config["reddit"]["subreddit"] = "amitheasshole"
    scraper = RedditScraper(base_config)
    assert scraper.subreddit_name == "amitheasshole"


def test_scraper_not_roblox(base_config):
    """Default config must not use r/roblox."""
    from utils.config_loader import load_config
    config = load_config("config.toml")
    sub = config.get("reddit", {}).get("subreddit", "").lower()
    assert sub != "roblox", (
        "subreddit is still 'roblox' — change to a high-emotion sub for better virality"
    )
