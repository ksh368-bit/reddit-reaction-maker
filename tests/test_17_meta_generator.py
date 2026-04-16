"""Tests for YouTube meta (title, description, hashtags) generator."""

import os
import sys
import pytest
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reddit.scraper import RedditPost, Comment
from utils.meta_generator import MetaGenerator


def make_post(
    title="AITA for telling my sister she ruined Christmas?",
    body="So this happened last December. My sister invited her new boyfriend...",
    subreddit="AmItheAsshole",
    score=5000,
    comments=None,
):
    if comments is None:
        comments = [Comment("c1", "user1", "NTA. Your sister was out of line.", 300)]
    return RedditPost(
        id="abc123",
        title=title,
        body=body,
        author="throwaway",
        score=score,
        url="https://reddit.com/r/AmItheAsshole/comments/abc123",
        subreddit=subreddit,
        comments=comments,
    )


class TestYouTubeTitle:
    def test_title_max_60_chars(self):
        post = make_post(title="AITA for " + "a" * 100)
        title = MetaGenerator.generate_title(post)
        assert len(title) <= 60

    def test_title_strips_aita_prefix(self):
        post = make_post(title="AITA for telling my sister off?")
        title = MetaGenerator.generate_title(post)
        assert not title.lower().startswith("aita")

    def test_title_strips_wibta_prefix(self):
        post = make_post(title="WIBTA for cutting off my mom?")
        title = MetaGenerator.generate_title(post)
        assert not title.lower().startswith("wibta")

    def test_title_strips_am_i_prefix(self):
        post = make_post(title="Am I the asshole for quitting my job?")
        title = MetaGenerator.generate_title(post)
        assert not title.lower().startswith("am i")

    def test_title_not_empty(self):
        post = make_post(title="AITA?")
        title = MetaGenerator.generate_title(post)
        assert len(title) > 0

    def test_title_capitalised(self):
        post = make_post(title="aita for something")
        title = MetaGenerator.generate_title(post)
        # Strip leading emoji/space before checking capitalisation
        text_part = title.lstrip("😤😬😈🙃🤔🎮🖥️📖💡✨ ")
        assert text_part[0].isupper()

    def test_steam_title_keeps_game_context(self):
        post = make_post(
            title="$40 for a DLC that adds 2 hours of content?",
            subreddit="Steam",
        )
        title = MetaGenerator.generate_title(post)
        assert "$40" in title or "DLC" in title or "2 hours" in title


class TestHashtags:
    def test_always_includes_shorts(self):
        post = make_post()
        tags = MetaGenerator.generate_hashtags(post)
        assert "#Shorts" in tags

    def test_always_includes_reddit(self):
        post = make_post()
        tags = MetaGenerator.generate_hashtags(post)
        assert "#Reddit" in tags or "#RedditStories" in tags

    def test_aita_subreddit_includes_aita_tag(self):
        post = make_post(subreddit="AmItheAsshole")
        tags = MetaGenerator.generate_hashtags(post)
        assert "#AITA" in tags

    def test_tifu_subreddit_includes_tifu_tag(self):
        post = make_post(subreddit="tifu")
        tags = MetaGenerator.generate_hashtags(post)
        assert "#TIFU" in tags

    def test_steam_subreddit_includes_gaming_tag(self):
        post = make_post(subreddit="Steam")
        tags = MetaGenerator.generate_hashtags(post)
        assert "#Gaming" in tags or "#Steam" in tags

    def test_tag_count_between_3_and_8(self):
        post = make_post()
        tags = MetaGenerator.generate_hashtags(post)
        count = len([t for t in tags.split() if t.startswith("#")])
        assert 3 <= count <= 8


class TestDescription:
    def test_description_not_empty(self):
        post = make_post()
        desc = MetaGenerator.generate_description(post)
        assert len(desc.strip()) > 0

    def test_description_contains_hashtags(self):
        post = make_post()
        desc = MetaGenerator.generate_description(post)
        assert "#Shorts" in desc

    def test_description_contains_story_sentence(self):
        post = make_post(body="My sister did something awful at Christmas dinner.")
        desc = MetaGenerator.generate_description(post)
        # First line should be a natural-language sentence
        first_line = desc.strip().split("\n")[0]
        assert len(first_line) > 20

    def test_description_under_500_chars(self):
        post = make_post(body="x" * 1000)
        desc = MetaGenerator.generate_description(post)
        assert len(desc) <= 500

    def test_description_includes_cta(self):
        post = make_post()
        desc = MetaGenerator.generate_description(post)
        assert "Subscribe" in desc or "subscribe" in desc


class TestSaveMetaFile:
    def test_saves_meta_txt_next_to_video(self):
        post = make_post()
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test_video.mp4")
            Path(video_path).touch()
            meta_path = MetaGenerator.save_meta(post, video_path)
            assert os.path.exists(meta_path)
            assert meta_path.endswith("_meta.txt")

    def test_meta_file_contains_all_sections(self):
        post = make_post()
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "test_video.mp4")
            Path(video_path).touch()
            meta_path = MetaGenerator.save_meta(post, video_path)
            content = Path(meta_path).read_text()
            assert "TITLE" in content
            assert "DESCRIPTION" in content

    def test_meta_filename_matches_video(self):
        post = make_post()
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "my_video.mp4")
            Path(video_path).touch()
            meta_path = MetaGenerator.save_meta(post, video_path)
            assert "my_video" in meta_path


# ─────────────────────────────────────────────
#  CTR optimization tests
# ─────────────────────────────────────────────

class TestTitleCTR:
    def test_title_has_emoji_for_aita(self):
        post = make_post(title="AITA for telling my boss off?", subreddit="amitheasshole")
        title = MetaGenerator.generate_title(post)
        assert "😤" in title

    def test_title_has_emoji_for_tifu(self):
        post = make_post(title="TIFU by sending the wrong email", subreddit="tifu")
        title = MetaGenerator.generate_title(post)
        assert "😬" in title

    def test_title_has_emoji_for_steam(self):
        post = make_post(title="Thanks Bethesda", subreddit="Steam")
        title = MetaGenerator.generate_title(post)
        assert "🎮" in title

    def test_title_has_emoji_for_manga(self):
        post = make_post(
            title="[DISC] The Hunter, Into The Wolf's Belly - Oneshot",
            subreddit="manga",
        )
        title = MetaGenerator.generate_title(post)
        assert "📖" in title

    def test_title_max_60_chars_with_emoji(self):
        post = make_post(
            title="AITA for doing something very long that might overflow the title limit easily?",
            subreddit="amitheasshole",
        )
        title = MetaGenerator.generate_title(post)
        assert len(title) <= 60, f"Title too long ({len(title)}): {title!r}"

    def test_title_strips_manga_disc_prefix(self):
        post = make_post(
            title="[DISC] The Hunter, Into The Wolf's Belly - Oneshot",
            subreddit="manga",
        )
        title = MetaGenerator.generate_title(post)
        assert "[DISC]" not in title
        assert "Hunter" in title

    def test_title_strips_manga_title_prefix(self):
        post = make_post(title="[TITLE] Solo Leveling Season 2", subreddit="manga")
        title = MetaGenerator.generate_title(post)
        assert "[TITLE]" not in title
        assert "Solo Leveling" in title

    def test_title_has_emoji_for_products(self):
        post = make_post(
            title="What's a totally unsexy purchase that changed your life?",
            subreddit="BuyItForLife",
        )
        title = MetaGenerator.generate_title(post)
        assert "💡" in title


class TestDescriptionCTR:
    def test_description_first_line_has_hook(self):
        post = make_post(subreddit="amitheasshole")
        desc = MetaGenerator.generate_description(post)
        first_line = desc.strip().split("\n")[0]
        assert "👇" in first_line, f"Expected hook in first line, got: {first_line!r}"

    def test_description_verdict_highlighted(self):
        post = make_post(subreddit="amitheasshole")
        desc = MetaGenerator.generate_description(post, verdict="NTA")
        assert "Reddit voted" in desc
        assert "NTA" in desc

    def test_description_manga_has_hook(self):
        post = make_post(
            title="[DISC] Solo Leveling ch.200",
            subreddit="manga",
        )
        desc = MetaGenerator.generate_description(post)
        first_line = desc.strip().split("\n")[0]
        assert "👇" in first_line

    def test_description_products_has_hook(self):
        post = make_post(
            title="Best unsexy purchase of your life?",
            subreddit="BuyItForLife",
        )
        desc = MetaGenerator.generate_description(post)
        first_line = desc.strip().split("\n")[0]
        assert "👇" in first_line

    def test_description_tifu_has_hook(self):
        post = make_post(title="TIFU by sending the wrong email", subreddit="tifu")
        desc = MetaGenerator.generate_description(post)
        first_line = desc.strip().split("\n")[0]
        assert "👇" in first_line

    def test_description_under_500_chars_with_hook(self):
        post = make_post(body="x" * 1000, subreddit="amitheasshole")
        desc = MetaGenerator.generate_description(post, verdict="NTA")
        assert len(desc) <= 500
