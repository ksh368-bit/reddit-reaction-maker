"""Tests for improved description generation."""

import pytest
from reddit.scraper import RedditPost, Comment
from utils.meta_generator import MetaGenerator


def _gaming_post(score=4200, with_comments=True):
    comments = [Comment("c1", "u1", "Honestly one of the best upgrades in years.", 800)] if with_comments else []
    return RedditPost(
        id="x", title="What an upgrade lmao", body="",
        author="gamer123", score=score, url="", subreddit="steam",
        comments=comments,
    )


def _aita_post(verdict=None):
    return RedditPost(
        id="y",
        title="AITA for kicking out my sister after she stole $5000",
        body="My sister borrowed money and never paid it back.",
        author="throwaway", score=12000, url="", subreddit="amitheasshole",
        comments=[Comment("c1", "u1", "NTA. She stole from you.", 2000)],
    )


class TestDescriptionEngagement:
    def test_engagement_question_present(self):
        """Description should include a 'What do YOU think?' style question."""
        desc = MetaGenerator.generate_description(_gaming_post())
        engagement_markers = ["you", "your", "think", "comment", "vote", "agree", "would"]
        desc_lower = desc.lower()
        has_engagement = any(m in desc_lower for m in engagement_markers)
        assert has_engagement, f"No engagement question found in:\n{desc}"

    def test_engagement_differs_by_subreddit(self):
        """Gaming and AITA should have different engagement prompts."""
        gaming_desc = MetaGenerator.generate_description(_gaming_post())
        aita_desc = MetaGenerator.generate_description(_aita_post())
        assert gaming_desc != aita_desc


class TestSocialProof:
    def test_high_score_shows_upvote_count(self):
        """Posts with 1k+ upvotes should mention the score as social proof."""
        desc = MetaGenerator.generate_description(_gaming_post(score=4200))
        # Should mention score in some form: "4.2k", "4,200", "upvote", etc.
        has_proof = any(x in desc for x in ["4.2k", "4,200", "upvotes", "upvote"])
        assert has_proof, f"No social proof in description:\n{desc}"

    def test_low_score_no_social_proof(self):
        """Posts with < 500 upvotes should not show score."""
        desc = MetaGenerator.generate_description(_gaming_post(score=120))
        assert "upvote" not in desc.lower()


class TestTopCommentTeaser:
    def test_top_comment_included_when_no_body(self):
        """When post has no body, top comment should appear as a teaser."""
        desc = MetaGenerator.generate_description(_gaming_post(with_comments=True))
        # Top comment: "Honestly one of the best upgrades in years."
        assert "best upgrades" in desc or "Honestly" in desc, \
            f"Top comment not included:\n{desc}"

    def test_no_crash_when_no_comments(self):
        desc = MetaGenerator.generate_description(_gaming_post(with_comments=False))
        assert len(desc) > 0


class TestHashtags:
    def test_hashtag_count_expanded(self):
        """Should have at least 5 hashtags (previously only 4)."""
        desc = MetaGenerator.generate_description(_gaming_post())
        tags = [w for w in desc.split() if w.startswith("#")]
        assert len(tags) >= 5, f"Only {len(tags)} hashtags: {tags}"

    def test_still_under_500_chars(self):
        desc = MetaGenerator.generate_description(_gaming_post())
        assert len(desc) <= 500, f"Description too long: {len(desc)} chars"


class TestNicheCTA:
    def test_gaming_cta_mentions_gaming(self):
        """Gaming subreddit CTA should mention gaming, not just 'Reddit stories'."""
        desc = MetaGenerator.generate_description(_gaming_post())
        assert "gam" in desc.lower() or "steam" in desc.lower(), \
            f"Gaming CTA missing gaming context:\n{desc}"

    def test_aita_cta_differs_from_gaming(self):
        gaming_desc = MetaGenerator.generate_description(_gaming_post())
        aita_desc = MetaGenerator.generate_description(_aita_post())
        # Extract last line (CTA)
        gaming_cta = gaming_desc.strip().split("\n")[-1]
        aita_cta = aita_desc.strip().split("\n")[-1]
        assert gaming_cta != aita_cta
