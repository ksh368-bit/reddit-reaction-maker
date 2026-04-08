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
    "relationship_advice",
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


def test_config_has_subreddits_rotation_list():
    """config.toml must have a subreddits list with multiple high-emotion subs."""
    from utils.config_loader import load_config
    config = load_config("config.toml")
    subs = config.get("reddit", {}).get("subreddits", [])
    assert len(subs) >= 3, f"subreddits list has only {len(subs)} entries — add more high-emotion subs"
    for s in subs:
        assert s.lower() in HIGH_EMOTION_SUBREDDITS, (
            f"'{s}' in subreddits list is not a recognized high-emotion subreddit"
        )


def test_scraper_picks_from_subreddits_list():
    """RedditScraper picks a subreddit from the subreddits rotation list."""
    from reddit.scraper import RedditScraper
    config = {
        "reddit": {
            "subreddits": ["AmItheAsshole", "tifu", "pettyrevenge"],
            "post_limit": 1, "min_upvotes": 0, "min_comments": 0,
            "max_comment_length": 500, "min_comment_score": 0, "top_comments": 1,
        },
        "output": {"history_file": "output/history.json"},
    }
    scraper = RedditScraper(config)
    assert scraper.subreddit_name.lower() in {s.lower() for s in config["reddit"]["subreddits"]}
