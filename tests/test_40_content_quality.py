"""
Content quality fixes (2026-04-20 analysis):

  1. Bracket tag stripping in YouTube title — [TITLE], [SPOILER], [QUESTION]
     etc. from manga/gaming subreddits leak into the YouTube title as-is,
     looking amateurish and confusing the recommendation algorithm.

  2. URL-based image post detection — Steam/gaming subreddits don't use
     [DISC] tags; image posts are identified by i.redd.it / i.imgur.com
     URLs or post_hint == "image". "What an upgrade lmao", "Yes..." etc.
     are screenshot posts that produce content-empty videos.

  3. min_comments floor for Steam — comments=4 is too low; short videos
     from 4-comment posts have low watch-time / completion rate.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.meta_generator import clean_reddit_title
from reddit.scraper import RedditScraper


def _make_scraper():
    return RedditScraper({
        "reddit": {
            "subreddit": "manga",
            "min_upvotes": 100,
            "min_comments": 5,
            "history_file": "/tmp/test_hist_40.json",
        }
    })


# ── Fix 1: bracket tag stripping ─────────────────────────────────────────────

class TestBracketTagStripping:
    def test_title_tag_stripped(self):
        out = clean_reddit_title("[TITLE]The reincarnation trope killed manhwa")
        assert "[TITLE]" not in out
        assert "reincarnation trope" in out

    def test_spoiler_tag_stripped(self):
        out = clean_reddit_title("[SPOILER] Chapter 400 broke me")
        assert "[SPOILER]" not in out
        assert "Chapter 400" in out

    def test_question_tag_stripped(self):
        out = clean_reddit_title("[QUESTION] Best isekai of 2024?")
        assert "[QUESTION]" not in out

    def test_discussion_tag_stripped(self):
        out = clean_reddit_title("[DISCUSSION] What's the best arc?")
        assert "[DISCUSSION]" not in out

    def test_misc_flair_tag_stripped(self):
        out = clean_reddit_title("[MISC] Random thoughts on solo leveling")
        assert "[MISC]" not in out

    def test_no_tag_unchanged(self):
        original = "Gabe the legend saves the day"
        out = clean_reddit_title(original)
        assert out == original

    def test_result_has_no_leading_space(self):
        out = clean_reddit_title("[TITLE]   Some title with spaces")
        assert out == out.strip()
        assert not out.startswith(" ")


# ── Fix 2: URL-based image post detection ────────────────────────────────────

class TestUrlImageDetection:
    def test_i_redd_it_url_is_image(self):
        s = _make_scraper()
        assert s._is_image_post_data(
            title="What an upgrade lmao",
            url="https://i.redd.it/abc123.jpg",
            post_hint="image",
        )

    def test_i_imgur_url_is_image(self):
        s = _make_scraper()
        assert s._is_image_post_data(
            title="Yes",
            url="https://i.imgur.com/abc123.png",
            post_hint="link",
        )

    def test_post_hint_image_is_image(self):
        s = _make_scraper()
        assert s._is_image_post_data(
            title="My setup",
            url="https://i.redd.it/xyz.jpg",
            post_hint="image",
        )

    def test_self_post_not_image(self):
        """Text self-posts (selftext) are not image posts."""
        s = _make_scraper()
        assert not s._is_image_post_data(
            title="Discussion about steam sales",
            url="https://www.reddit.com/r/Steam/comments/abc/",
            post_hint="self",
        )

    def test_youtube_link_not_image(self):
        s = _make_scraper()
        assert not s._is_image_post_data(
            title="Check out this review",
            url="https://www.youtube.com/watch?v=abc",
            post_hint="link",
        )

    def test_title_tag_check_still_works(self):
        """Original title-tag check should still catch [DISC] etc."""
        s = _make_scraper()
        assert s._is_image_post_data(
            title="[DISC] Both are succubi",
            url="https://www.reddit.com/r/manga/comments/abc/",
            post_hint="self",
        )
