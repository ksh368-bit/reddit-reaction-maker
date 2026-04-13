"""YouTube meta generator: title, description, hashtags for Shorts."""

from __future__ import annotations

import os
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Subreddit → hashtag mapping
# ---------------------------------------------------------------------------
_SUBREDDIT_TAGS: dict[str, list[str]] = {
    # Reddit judgment stories
    "amitheasshole":       ["#AITA", "#AmITheAsshole", "#RedditStories"],
    "relationship_advice": ["#RelationshipAdvice", "#RedditStories"],
    "tifu":                ["#TIFU", "#RedditStories"],
    "pettyrevenge":        ["#PettyRevenge", "#RedditStories"],
    "maliciouscompliance": ["#MaliciousCompliance", "#RedditStories"],
    "choosingbeggars":     ["#ChoosingBeggars", "#RedditStories"],
    "entitledpeople":      ["#Entitled", "#RedditStories"],
    "JustNoMIL":           ["#FamilyDrama", "#RedditStories"],
    "askcarsales":         ["#CarSales", "#LookOutFraud"],
    # General Reddit
    "askreddit":           ["#AskReddit", "#RedditStories"],
    "todayilearned":       ["#TodayILearned", "#FunFacts"],
    "lifeprotips":         ["#LifeHacks", "#LifeTips"],
    # Gaming
    "steam":               ["#Steam", "#Gaming", "#PCGaming"],
    "pcgaming":            ["#PCGaming", "#Gaming", "#Steam"],
    "gaming":              ["#Gaming", "#Gamers"],
    "consoles":            ["#ConsoleGaming", "#Gaming"],
    "WoW":                 ["#WorldOfWarcraft", "#Gaming", "#MMO"],
    "leagueoflegends":     ["#LeagueOfLegends", "#Esports"],
    # Anime & Manga
    "manga":               ["#Manga", "#Anime", "#RedditStories"],
    "manhwa":              ["#Manhwa", "#Webtoon", "#RedditStories"],
    "anime":               ["#Anime", "#AnimeCommunity"],
    "anime_irl":           ["#Anime", "#Memes"],
    # Lifestyle & Self-improvement
    "fitness":             ["#Fitness", "#WorkoutTips"],
    "loseit":              ["#WeightLoss", "#Fitness"],
    "EatCheapAndHealthy":  ["#EatCheap", "#Recipes"],
    "personalfinance":     ["#PersonalFinance", "#MoneyTips"],
    "investing":           ["#Investing", "#Stocks"],
    "buyitforlife":        ["#BuyItForLife", "#ProductReview", "#LifeHacks"],
    "asianbeauty":         ["#AsianBeauty", "#Skincare", "#BeautyTips"],
    "skincare":            ["#Skincare", "#BeautyTips"],
    # Tech & Programming
    "programming":         ["#Programming", "#Code"],
    "learnprogramming":    ["#LearnProgramming", "#Coding"],
    "webdev":              ["#WebDevelopment", "#Code"],
    "python":              ["#Python", "#Programming"],
    "javascript":          ["#JavaScript", "#Programming"],
}

# Prefixes to strip from Reddit titles before using as YouTube title
_STRIP_PREFIXES = re.compile(
    r"^(aita|wibta|wita|am i the asshole|am i wrong|am i being|tifu by|tifu:?"
    r"|\[disc\]|\[title\]|\[chapter\s*\d*\]|\[review\])\s*(for|by|:)?\s*",
    re.IGNORECASE,
)

# Subreddit-level story type for the description intro sentence
_SUBREDDIT_INTRO: dict[str, str] = {
    # Reddit judgment stories
    "amitheasshole":       "A Redditor asks if they're wrong",
    "relationship_advice": "A Redditor shares their relationship dilemma",
    "tifu":                "A Redditor shares an embarrassing fail",
    "pettyrevenge":        "A Redditor gets sweet petty revenge",
    "maliciouscompliance": "A Redditor takes instructions a little too literally",
    "choosingbeggars":     "Someone asks for too much",
    "entitledpeople":      "An entitled person shows their true colors",
    "JustNoMIL":           "Family drama unfolds",
    "askcarsales":         "A car salesman spills the tea",
    # General Reddit
    "askreddit":           "Reddit debates this hot topic",
    "todayilearned":       "Reddit discovers something surprising",
    "lifeprotips":         "A simple life hack nobody knew about",
    # Gaming
    "steam":               "Steam community reacts",
    "pcgaming":            "PC gamers react",
    "gaming":              "Gamers debate this",
    "consoles":            "Console wars heating up",
    "WoW":                 "WoW players have opinions",
    "leagueoflegends":     "The League community weighs in",
    # Anime & Manga
    "manga":               "Manga fans are discussing",
    "manhwa":              "Manhwa fans are discussing",
    "anime":               "Anime fans debate",
    "anime_irl":           "Anime community reacts",
    # Lifestyle & Self-improvement
    "fitness":             "Fitness enthusiasts share wisdom",
    "loseit":              "Weight loss transformation shared",
    "EatCheapAndHealthy":  "Cheap meal hack everyone needs",
    "personalfinance":     "Personal finance advice from Reddit",
    "investing":           "Investors debate strategy",
    "buyitforlife":        "Reddit found a life-changing product",
    "asianbeauty":         "The beauty community recommends",
    "skincare":            "Skincare experts weigh in",
    # Tech & Programming
    "programming":         "Developers debate best practices",
    "learnprogramming":    "New programmer asks question",
    "webdev":              "Web developers discuss",
    "python":              "Python community votes",
    "javascript":          "JavaScript drama erupts",
}

# Subreddit → emoji prefix for YouTube title (CTR boost)
_TITLE_EMOJI: dict[str, str] = {
    # Reddit judgment stories
    "amitheasshole":       "😤",
    "relationship_advice": "💔",
    "tifu":                "😬",
    "pettyrevenge":        "😈",
    "maliciouscompliance": "🙃",
    "choosingbeggars":     "🤦",
    "entitledpeople":      "🙄",
    "justnoMIL":           "😡",
    "JustNoMIL":           "😡",
    "askcarsales":         "🚗",
    # General Reddit
    "askreddit":           "🤔",
    "todayilearned":       "💡",
    "lifeprotips":         "💡",
    # Gaming
    "steam":               "🎮",
    "pcgaming":            "🖥️",
    "gaming":              "🎮",
    "consoles":            "🎮",
    "videogaming":         "🎮",
    "WoW":                 "⚔️",
    "leagueoflegends":     "⚔️",
    # Anime & Manga
    "manga":               "📖",
    "manhwa":              "📖",
    "anime":               "🎬",
    "anime_irl":           "😂",
    # Lifestyle & Self-improvement
    "fitness":             "💪",
    "loseit":              "⚖️",
    "EatCheapAndHealthy":  "🥗",
    "personalfinance":     "💰",
    "investing":           "📈",
    "buyitforlife":        "💡",
    "asianbeauty":         "✨",
    "skincare":            "✨",
    # Tech & Programming
    "programming":         "💻",
    "learnprogramming":    "💻",
    "webdev":              "🌐",
    "python":              "🐍",
    "javascript":          "⚡",
}

# Subreddit → description hook first line (shown before YouTube "Show more")
_DESC_HOOK: dict[str, str] = {
    # Reddit judgment stories
    "amitheasshole":       "📢 Reddit voted… and the comments are WILD 👇",
    "relationship_advice": "💬 Real advice. What would YOU do? 👇",
    "tifu":                "💀 This actually happened. Read it and cringe 👇",
    "pettyrevenge":        "😈 Sometimes revenge is the only answer 👇",
    "maliciouscompliance": "🙃 They asked for it… so he did exactly that 👇",
    "choosingbeggars":     "🤦 Someone asked for too much 👇",
    "entitledpeople":      "🙄 Entitlement at its finest 👇",
    "justnoMIL":           "😡 Family drama you won't believe 👇",
    "JustNoMIL":           "😡 Family drama you won't believe 👇",
    "askcarsales":         "🚗 The car salesman speaks 👇",
    # General Reddit
    "askreddit":           "🤔 Reddit's answer will surprise you 👇",
    "todayilearned":       "💡 This is actually wild 👇",
    "lifeprotips":         "💡 This life hack changes everything 👇",
    # Gaming
    "steam":               "🎮 The gaming community has spoken 👇",
    "pcgaming":            "🖥️ PC gamers react 👇",
    "gaming":              "🎮 Gamers can't stop talking about this 👇",
    "consoles":            "🎮 Console wars heating up 👇",
    "WoW":                 "⚔️ WoW players are discussing this 👇",
    "leagueoflegends":     "⚔️ The League community verdict 👇",
    # Anime & Manga
    "manga":               "📖 The manga community is talking about this 👇",
    "manhwa":              "📖 Manhwa fans can't stop discussing this 👇",
    "anime":               "🎬 Anime fans are fighting about this 👇",
    "anime_irl":           "😂 Anime community reacts 👇",
    # Lifestyle & Self-improvement
    "fitness":             "💪 The fitness community weighs in 👇",
    "loseit":              "⚖️ Weight loss transformation 👇",
    "EatCheapAndHealthy":  "🥗 Budget meal hack everyone needs 👇",
    "personalfinance":     "💰 Money advice from Reddit 👇",
    "investing":           "📈 Investors are divided on this 👇",
    "buyitforlife":        "💡 Reddit found a purchase that changes everything 👇",
    "asianbeauty":         "✨ The beauty community's top recommendation 👇",
    "skincare":            "✨ Dermatologists hate this one weird trick 👇",
    # Tech & Programming
    "programming":         "💻 Developers are split on this 👇",
    "learnprogramming":    "💻 New developers react 👇",
    "webdev":              "🌐 Web developers debate 👇",
    "python":              "🐍 Python community votes 👇",
    "javascript":          "⚡ JavaScript drama unfolds 👇",
}


def _generate_hook_heuristic(subreddit: str, intro: str = "") -> str:
    """
    Generate description hook for unknown subreddit using heuristics.

    Args:
        subreddit: Subreddit name (lowercase)
        intro: Optional intro text from _SUBREDDIT_INTRO

    Returns:
        Description hook with emoji and context
    """
    # Heuristic emoji selection based on keywords
    sub_lower = subreddit.lower()

    if any(kw in sub_lower for kw in ["fitness", "gym", "strength", "muscle"]):
        emoji = "💪"
    elif any(kw in sub_lower for kw in ["food", "cook", "recipe", "bake"]):
        emoji = "🍳"
    elif any(kw in sub_lower for kw in ["game", "game", "esports"]):
        emoji = "🎮"
    elif any(kw in sub_lower for kw in ["dev", "code", "program", "tech"]):
        emoji = "💻"
    elif any(kw in sub_lower for kw in ["learn", "science", "education"]):
        emoji = "📚"
    elif any(kw in sub_lower for kw in ["art", "design", "creative"]):
        emoji = "🎨"
    elif any(kw in sub_lower for kw in ["story", "nosleep", "tifu"]):
        emoji = "📖"
    elif any(kw in sub_lower for kw in ["money", "invest", "finance", "budget"]):
        emoji = "💰"
    elif any(kw in sub_lower for kw in ["travel", "trip", "world"]):
        emoji = "✈️"
    elif any(kw in sub_lower for kw in ["advice", "relationship", "family"]):
        emoji = "💬"
    elif any(kw in sub_lower for kw in ["job", "career", "work", "employ"]):
        emoji = "💼"
    elif any(kw in sub_lower for kw in ["pet", "dog", "cat", "animal"]):
        emoji = "🐾"
    elif any(kw in sub_lower for kw in ["movie", "show", "tv", "film"]):
        emoji = "🎬"
    elif any(kw in sub_lower for kw in ["music", "song", "band", "spotify"]):
        emoji = "🎵"
    elif any(kw in sub_lower for kw in ["health", "medical", "doctor", "fitness"]):
        emoji = "💊"
    else:
        emoji = "🤔"

    # Capitalize subreddit name for context
    sub_name = subreddit.replace("_", " ").title()

    # Generate hook from intro if available, else fallback
    if intro:
        return f"{emoji} {intro} 👇"
    else:
        # Fallback: generic hook with subreddit name
        return f"{emoji} r/{sub_name} community reacts 👇"


class MetaGenerator:
    """Generate YouTube-optimised title, description, and hashtags."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def generate_title(post, verdict: str | None = None) -> str:
        """Return a YouTube Shorts hook title (≤60 chars) with emoji prefix."""
        sub_key = post.subreddit.lower().split("+")[0]
        emoji = _TITLE_EMOJI.get(sub_key, "")
        emoji_prefix = f"{emoji} " if emoji else ""

        text = _STRIP_PREFIXES.sub("", post.title).strip()
        # Capitalise first letter
        if text:
            text = text[0].upper() + text[1:]
        if not text:
            text = post.title.strip()

        # Reserve space: emoji_prefix + text + optional "…" (3) + optional " (NTA)" (6)
        max_text = 60 - len(emoji_prefix) - 3
        if len(text) > max_text:
            text = text[:max_text].rsplit(" ", 1)[0].rstrip(",.") + "…"

        base = f"{emoji_prefix}{text}"

        # Append verdict badge if it fits
        if verdict and len(base) + len(f" ({verdict})") <= 60:
            base = f"{base} ({verdict})"

        return base[:60]

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
        """Return a YouTube description with hook + story summary + hashtags + CTA."""
        sub_key = post.subreddit.lower().split("+")[0]

        # Hook first line — shown before YouTube "Show more", drives CTR
        hook = _DESC_HOOK.get(sub_key)
        if not hook:
            intro = _SUBREDDIT_INTRO.get(sub_key, "A Redditor shares their story")
            # Use heuristic to generate hook for unknown subreddit
            hook = _generate_hook_heuristic(sub_key, intro)

        # Build 1-sentence summary from body (first 120 chars) or title
        intro = _SUBREDDIT_INTRO.get(sub_key, "A Redditor shares their story")
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

        verdict_line = f"Reddit voted: {verdict} 🏆\n\n" if verdict else ""
        desc = f"{hook}\n\n{summary}\n\n{verdict_line}{hashtags}\n{cta}"

        # Hard cap 500 chars (YouTube shows ~250 before "Show more")
        if len(desc) > 500:
            # Shorten summary only
            fixed = f"{hook}\n\n\n\n{verdict_line}{hashtags}\n{cta}"
            max_summary = 500 - len(fixed) - 5
            summary = summary[:max_summary].rsplit(" ", 1)[0] + "…"
            desc = f"{hook}\n\n{summary}\n\n{verdict_line}{hashtags}\n{cta}"

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
