"""YouTube meta generator: title, description, hashtags for Shorts."""

from __future__ import annotations

import os
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Subreddit → hashtag mapping
# ---------------------------------------------------------------------------
_SUBREDDIT_TAGS: dict[str, list[str]] = {
    "amitheasshole":      ["#AITA", "#AmITheAsshole", "#RedditStories"],
    "relationship_advice":["#RelationshipAdvice", "#RedditStories"],
    "tifu":               ["#TIFU", "#RedditStories"],
    "pettyrevenge":       ["#PettyRevenge", "#RedditStories"],
    "maliciouscompliance":["#MaliciousCompliance", "#RedditStories"],
    "askreddit":          ["#AskReddit", "#RedditStories"],
    "steam":              ["#Steam", "#Gaming", "#PCGaming"],
    "pcgaming":           ["#PCGaming", "#Gaming", "#Steam"],
}

# Prefixes to strip from Reddit titles before using as YouTube title
_STRIP_PREFIXES = re.compile(
    r"^(aita|wibta|wita|am i the asshole|am i wrong|am i being|tifu by|tifu:?)\s*(for|by|:)?\s*",
    re.IGNORECASE,
)

# Subreddit-level story type for the description intro sentence
_SUBREDDIT_INTRO: dict[str, str] = {
    "amitheasshole":      "A Redditor asks if they're wrong",
    "relationship_advice":"A Redditor shares their relationship dilemma",
    "tifu":               "A Redditor shares an embarrassing fail",
    "pettyrevenge":       "A Redditor gets sweet petty revenge",
    "maliciouscompliance":"A Redditor takes instructions a little too literally",
    "steam":              "Steam community reacts",
    "pcgaming":           "PC gamers react",
}


class MetaGenerator:
    """Generate YouTube-optimised title, description, and hashtags."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def generate_title(post, verdict: str | None = None) -> str:
        """Return a YouTube Shorts hook title (≤60 chars)."""
        text = _STRIP_PREFIXES.sub("", post.title).strip()
        # Capitalise first letter
        if text:
            text = text[0].upper() + text[1:]
        # Ensure something remains
        if not text:
            text = post.title.strip()
        # Truncate at word boundary (≤60 chars including ellipsis)
        if len(text) > 60:
            text = text[:59].rsplit(" ", 1)[0].rstrip(",.") + "…"
        # Append verdict badge if it fits
        if verdict and len(text) + len(f" ({verdict})") <= 60:
            text = f"{text} ({verdict})"
        return text

    @staticmethod
    def generate_hashtags(post, verdict: str | None = None) -> str:
        """Return a space-joined hashtag string (3-5 tags, always #Shorts #Reddit)."""
        sub_key = post.subreddit.lower().split("+")[0]  # e.g. "Steam+pcgaming" → "steam"
        niche = _SUBREDDIT_TAGS.get(sub_key, ["#RedditStories"])[:2]

        tags = ["#Shorts", "#Reddit"] + niche
        if verdict in ("NTA", "YTA", "ESH"):
            tags.append(f"#{verdict}")
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return " ".join(unique[:5])

    @staticmethod
    def generate_description(post, verdict: str | None = None) -> str:
        """Return a YouTube description with story summary + hashtags + CTA."""
        sub_key = post.subreddit.lower().split("+")[0]
        intro = _SUBREDDIT_INTRO.get(sub_key, "A Redditor shares their story")

        # Build 1-sentence summary from body (first 120 chars) or title
        source = (post.body or post.title).strip()
        # Strip markdown-ish noise
        source = re.sub(r"\*+|#+|`+", "", source)
        source = re.sub(r"\s+", " ", source).strip()

        if len(source) > 120:
            summary_raw = source[:120].rsplit(" ", 1)[0]
        else:
            summary_raw = source

        summary = f"{intro} — {summary_raw.rstrip('.,')}."

        hashtags = MetaGenerator.generate_hashtags(post, verdict=verdict)
        cta = "🔔 Subscribe for daily Reddit stories"

        verdict_line = f"The internet says: {verdict}\n\n" if verdict else ""
        desc = f"{verdict_line}{summary}\n\n{hashtags}\n{cta}"

        # Hard cap 500 chars (YouTube shows ~250 before "Show more")
        if len(desc) > 500:
            # Shorten summary only
            max_summary = 500 - len(f"{verdict_line}\n\n{hashtags}\n{cta}") - 5
            summary = summary[:max_summary].rsplit(" ", 1)[0] + "…"
            desc = f"{verdict_line}{summary}\n\n{hashtags}\n{cta}"

        return desc

    @staticmethod
    def save_meta(post, video_path: str, verdict: str | None = None) -> str:
        """Write _meta.txt next to the video file and return its path."""
        base = os.path.splitext(video_path)[0]
        meta_path = f"{base}_meta.txt"

        title = MetaGenerator.generate_title(post, verdict=verdict)
        description = MetaGenerator.generate_description(post, verdict=verdict)

        sep = "=" * 60
        content = "\n".join([
            sep,
            "TITLE",
            sep,
            title,
            "",
            sep,
            "DESCRIPTION",
            sep,
            description,
            "",
        ])

        Path(meta_path).write_text(content, encoding="utf-8")
        return meta_path
