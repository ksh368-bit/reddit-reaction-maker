"""Shared fixtures for all tests."""
import sys
import os
import pytest

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def base_config():
    """Minimal config dict used across tests."""
    return {
        "reddit": {
            "subreddit": "AmItheAsshole",
            "post_limit": 5,
            "min_upvotes": 100,
            "min_comments": 5,
            "max_comment_length": 500,
            "min_comment_score": 0,
            "top_comments": 3,
        },
        "tts": {
            "engine": "gtts",
            "language": "en",
            "slow": False,
        },
        "video": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "max_duration": 55,
            "background_dir": "assets/backgrounds",
            "font": None,
            "title_font_size": 48,
            "comment_font_size": 165,
            "watermark": "",
            "opacity": 0.7,
            "bgm_enabled": False,
            "bgm_volume": 0.1,
        },
        "output": {
            "dir": "output",
            "history_file": "output/history.json",
        },
    }


@pytest.fixture
def sample_post():
    """A fake Reddit post for rendering tests."""
    from reddit.scraper import RedditPost, Comment
    return RedditPost(
        id="test123",
        title="I bought my own house after everyone betrayed me",
        body="My ex-wife cheated, my sister stole from me, parents sided with them.",
        author="throwaway_user",
        score=45200,
        url="https://reddit.com/r/AmItheAsshole/test123",
        subreddit="AmItheAsshole",
        num_comments=3820,
        comments=[
            Comment(id="c1", author="user1", body="NTA. You owe them nothing.", score=8400),
            Comment(id="c2", author="user2", body="Absolutely NTA. You worked hard for this.", score=5200),
        ],
    )
