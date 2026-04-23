"""
Image-post title tag filter for manga/fanart subreddits.

[DISC], [FANART], [ART], [PIC], [OC], [IMAGE] tagged posts are image-centric
— the value is the artwork, not the text discussion. Our video format shows
Reddit text cards only, so these posts produce confusing videos where viewers
see text about a manga panel they can't see.

Additionally, using the copyrighted manga/fanart images directly as video
backgrounds carries significant DMCA/Content-ID risk from publishers.

Solution: filter these posts out at the scraper level so they never enter
the pipeline.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reddit.scraper import RedditScraper


def _make_scraper(subreddit="manga"):
    cfg = {
        "reddit": {
            "subreddit": subreddit,
            "min_upvotes": 100,
            "min_comments": 5,
            "history_file": "/tmp/test_hist_39.json",
        }
    }
    return RedditScraper(cfg)


class TestImageTagDetection:
    def test_disc_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[DISC] Both are succubi. - Oneshot by @medatarou1")

    def test_fanart_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[FANART] My drawing of Luffy")

    def test_art_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[ART] Amazing panel from Berserk")

    def test_oc_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[OC] I drew my favorite character")

    def test_image_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[IMAGE] Check out this page")

    def test_pic_tag_is_image_post(self):
        s = _make_scraper()
        assert s._is_image_post("[PIC] Screenshot from chapter 120")

    def test_case_insensitive(self):
        s = _make_scraper()
        assert s._is_image_post("[disc] lowercase tag")
        assert s._is_image_post("[Fanart] Mixed case")

    def test_discussion_text_post_not_filtered(self):
        """[DISCUSSION] is a text thread — should NOT be filtered."""
        s = _make_scraper()
        assert not s._is_image_post("[DISCUSSION] What's the best isekai of 2024?")

    def test_question_post_not_filtered(self):
        s = _make_scraper()
        assert not s._is_image_post("Which manga has the best art style?")

    def test_spoiler_post_not_filtered(self):
        s = _make_scraper()
        assert not s._is_image_post("[SPOILER] Chapter 400 broke me")

    def test_review_post_not_filtered(self):
        s = _make_scraper()
        assert not s._is_image_post("[REVIEW] Solo Leveling manhwa - my thoughts")
