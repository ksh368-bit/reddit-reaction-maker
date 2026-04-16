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
    "amitheasshole":       ["#AITA", "#AmITheAsshole", "#RedditStories", "#RedditDrama", "#Verdict"],
    "relationship_advice": ["#RelationshipAdvice", "#RedditStories", "#Relationships", "#Advice"],
    "tifu":                ["#TIFU", "#RedditStories", "#FailStory", "#Funny"],
    "pettyrevenge":        ["#PettyRevenge", "#RedditStories", "#Revenge", "#Justice"],
    "maliciouscompliance": ["#MaliciousCompliance", "#RedditStories", "#WorkStories", "#Funny"],
    "choosingbeggars":     ["#ChoosingBeggars", "#RedditStories", "#Entitled", "#Cringe"],
    "entitledpeople":      ["#Entitled", "#RedditStories", "#Cringe", "#ChoosingBeggars"],
    "JustNoMIL":           ["#FamilyDrama", "#RedditStories", "#MIL", "#FamilyProblems"],
    "askcarsales":         ["#CarSales", "#LookOutFraud", "#CarBuying", "#CarTips"],
    # General Reddit
    "askreddit":           ["#AskReddit", "#RedditStories", "#Reddit", "#Discussion"],
    "todayilearned":       ["#TodayILearned", "#FunFacts", "#DidYouKnow", "#Learning"],
    "lifeprotips":         ["#LifeHacks", "#LifeTips", "#Tips", "#LifeAdvice"],
    # Gaming
    "steam":               ["#Steam", "#Gaming", "#PCGaming", "#SteamDeals", "#PCGamer"],
    "pcgaming":            ["#PCGaming", "#Gaming", "#Steam", "#PCGamer", "#GamersOfReddit"],
    "gaming":              ["#Gaming", "#Gamers", "#VideoGames", "#GamingCommunity"],
    "consoles":            ["#ConsoleGaming", "#Gaming", "#PlayStation", "#Xbox"],
    "WoW":                 ["#WorldOfWarcraft", "#Gaming", "#MMO", "#WoW"],
    "leagueoflegends":     ["#LeagueOfLegends", "#Esports", "#Gaming", "#LoL"],
    # Anime & Manga
    "manga":               ["#Manga", "#Anime", "#RedditStories", "#MangaArt"],
    "manhwa":              ["#Manhwa", "#Webtoon", "#RedditStories", "#Korean"],
    "anime":               ["#Anime", "#AnimeCommunity", "#AnimeFan", "#Otaku"],
    "anime_irl":           ["#Anime", "#Memes", "#AnimeMemes", "#Otaku"],
    # Lifestyle & Self-improvement
    "fitness":             ["#Fitness", "#WorkoutTips", "#Gym", "#HealthyLifestyle"],
    "loseit":              ["#WeightLoss", "#Fitness", "#HealthJourney", "#Diet"],
    "EatCheapAndHealthy":  ["#EatCheap", "#Recipes", "#BudgetFood", "#MealPrep"],
    "personalfinance":     ["#PersonalFinance", "#MoneyTips", "#Budgeting", "#SaveMoney"],
    "investing":           ["#Investing", "#Stocks", "#Finance", "#WealthBuilding"],
    "buyitforlife":        ["#BuyItForLife", "#ProductReview", "#LifeHacks", "#Shopping"],
    "asianbeauty":         ["#AsianBeauty", "#Skincare", "#BeautyTips", "#KBeauty"],
    "skincare":            ["#Skincare", "#BeautyTips", "#GlowUp", "#SkincareTips"],
    # Tech & Programming
    "programming":         ["#Programming", "#Code", "#Developer", "#Tech"],
    "learnprogramming":    ["#LearnProgramming", "#Coding", "#Developer", "#Tech"],
    "webdev":              ["#WebDevelopment", "#Code", "#Frontend", "#Tech"],
    "python":              ["#Python", "#Programming", "#Code", "#DataScience"],
    "javascript":          ["#JavaScript", "#Programming", "#WebDev", "#Code"],
}

# Subreddit-specific engagement questions (drives comments)
_ENGAGEMENT_Q: dict[str, str] = {
    "steam":               "Would you agree? Drop your take below! 👇",
    "pcgaming":            "What's YOUR gaming hot take? Comment below! 👇",
    "gaming":              "Agree or disagree? Let us know! 👇",
    "consoles":            "Console wars — which side are you on? 👇",
    "amitheasshole":       "Who's in the wrong? Vote in the comments! 👇",
    "relationship_advice": "What would YOU do in this situation? 👇",
    "tifu":                "Would you survive this? Comment below! 👇",
    "pettyrevenge":        "Was the revenge justified? Let us know! 👇",
    "maliciouscompliance": "Best malicious compliance you've seen? 👇",
    "choosingbeggars":     "How would you respond? Comment below! 👇",
    "entitledpeople":      "How would YOU handle this? Drop a comment! 👇",
    "askreddit":           "What's YOUR answer? Comment below! 👇",
    "todayilearned":       "Did you know this? Share your reaction! 👇",
    "manga":               "What's your favorite manga? Comment below! 👇",
    "anime":               "Agree with the community? Let us know! 👇",
    "personalfinance":     "What's your money move? Share below! 👇",
    "investing":           "Would you make this trade? Comment below! 👇",
}

# Subreddit-specific CTAs (replaces generic "daily Reddit stories")
_NICHE_CTA: dict[str, str] = {
    "steam":               "🔔 Subscribe for daily gaming reactions",
    "pcgaming":            "🔔 Subscribe for daily PC gaming highlights",
    "gaming":              "🔔 Subscribe for daily gaming reactions",
    "consoles":            "🔔 Subscribe for daily gaming content",
    "amitheasshole":       "🔔 Subscribe for daily AITA verdicts",
    "relationship_advice": "🔔 Subscribe for daily relationship stories",
    "tifu":                "🔔 Subscribe for daily Reddit fails",
    "pettyrevenge":        "🔔 Subscribe for daily revenge stories",
    "maliciouscompliance": "🔔 Subscribe for daily Reddit stories",
    "manga":               "🔔 Subscribe for daily manga community picks",
    "anime":               "🔔 Subscribe for daily anime community picks",
    "personalfinance":     "🔔 Subscribe for daily money tips from Reddit",
    "investing":           "🔔 Subscribe for daily investing discussions",
}

# Prefixes to strip from Reddit titles before using as YouTube title
_STRIP_PREFIXES = re.compile(
    r"^(aita|wibta|wita|am i the asshole|am i wrong|am i being|tifu by|tifu:?"
    r"|\[disc\]|\[title\]|\[chapter\s*\d*\]|\[review\])\s*(for|by|:)?\s*",
    re.IGNORECASE,
)

# Context prefixes injected into short gaming titles
_GAMING_BOOST: dict[str, str] = {
    "steam":          "Steam community: ",
    "pcgaming":       "PC gamers react: ",
    "gaming":         "Gamers react: ",
    "consoles":       "Console gamers: ",
    "videogaming":    "Gaming community: ",
    "wow":            "WoW players: ",
    "leagueoflegends": "League community: ",
}

# Context prefixes injected into short story/AITA titles
_STORY_BOOST: dict[str, str] = {
    "amitheasshole":       "Reddit has voted: ",
    "relationship_advice": "Reddit weighs in: ",
    "pettyrevenge":        "Sweet revenge: ",
    "maliciouscompliance": "Malicious compliance: ",
    "choosingbeggars":     "Entitled moment: ",
    "entitledpeople":      "Entitlement alert: ",
}

_BOOST_THRESHOLD = 32   # boost when emoji_len + text_len is below this
_BOOST_MAX_TOTAL = 55   # don't boost if result would exceed this


def _boost_short_title(text: str, sub_key: str, emoji_prefix_len: int) -> str:
    """Prepend a subreddit context prefix when title is too short to be engaging."""
    if emoji_prefix_len + len(text) >= _BOOST_THRESHOLD:
        return text

    prefix = _GAMING_BOOST.get(sub_key) or _STORY_BOOST.get(sub_key)
    if not prefix:
        return text

    candidate = f"{prefix}{text}"
    if emoji_prefix_len + len(candidate) <= _BOOST_MAX_TOTAL:
        return candidate

    return text


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
# Optimized for 50%+ CTR: emoji + engagement word + 👇 CTA
_DESC_HOOK: dict[str, str] = {
    # Reddit judgment stories - "Reddit voted" pattern
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
    # General Reddit - "What would YOU" engagement
    "askreddit":           "🤔 Reddit's answer will surprise you 👇",
    "todayilearned":       "💡 This is actually wild 👇",
    "lifeprotips":         "💡 This life hack changes everything 👇",
    # Gaming - "community has spoken" pattern
    "steam":               "🎮 The gaming community has spoken 👇",
    "pcgaming":            "🖥️ PC gamers react 👇",
    "gaming":              "🎮 Gamers can't stop talking about this 👇",
    "consoles":            "🎮 Console wars heating up 👇",
    "WoW":                 "⚔️ WoW players are discussing this 👇",
    "leagueoflegends":     "⚔️ The League community verdict 👇",
    # Anime & Manga - community engagement
    "manga":               "📖 The manga community is talking about this 👇",
    "manhwa":              "📖 Manhwa fans can't stop discussing this 👇",
    "anime":               "🎬 Anime fans are fighting about this 👇",
    "anime_irl":           "😂 Anime community reacts 👇",
    # Lifestyle & Self-improvement - "Reddit found/discovered" pattern
    "fitness":             "💪 The fitness community weighs in 👇",
    "loseit":              "⚖️ Weight loss transformation 👇",
    "EatCheapAndHealthy":  "🥗 Budget meal hack everyone needs 👇",
    "personalfinance":     "💰 Money advice from Reddit 👇",
    "investing":           "📈 Investors are divided on this 👇",
    "buyitforlife":        "💡 Reddit found a purchase that changes everything 👇",
    "asianbeauty":         "✨ The beauty community's top recommendation 👇",
    "skincare":            "✨ Skincare secrets nobody talks about 👇",
    # Tech & Programming - "split/debate" engagement pattern
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
        """
        Return a YouTube Shorts title optimized for CTR (40-55 chars optimal, max 60).

        Optimization:
        - Emoji prefix for visual impact (+3-5% CTR)
        - 40-55 char sweet spot for mobile readability
        - Personal pronouns preserved for engagement
        - Update/sequel badge for series
        """
        sub_key = post.subreddit.lower().split("+")[0]
        emoji = _TITLE_EMOJI.get(sub_key, "")
        emoji_prefix = f"{emoji} " if emoji else ""

        # Detect update/sequel for special badge
        is_update = bool(re.search(r"\b(UPDATE|UPDATED|FOLLOW.?UP|PART\s*\d+)\b", post.title, re.IGNORECASE))
        update_badge = "UPDATE: " if is_update else ""

        text = _STRIP_PREFIXES.sub("", post.title).strip()
        # Capitalise first letter
        if text:
            text = text[0].upper() + text[1:]
        if not text:
            text = post.title.strip()

        # Boost very short titles with a subreddit context prefix
        if not is_update:
            text = _boost_short_title(text, sub_key, len(emoji_prefix))

        # Optimal range: 40-55 chars (sweet spot for mobile)
        # Hard cap: 60 chars (YouTube Shorts limit)
        # Reserve space for: emoji(3) + space(1) + update_badge(8) + "…"(3) + verdict(6) = ~21 chars
        optimal_max = 55
        hard_max = 60

        # Try to fit in optimal range first
        target = optimal_max - len(emoji_prefix) - len(update_badge)

        if len(text) > target:
            # Truncate to fit optimal range
            text = text[:target].rsplit(" ", 1)[0].rstrip(",.") + "…"
        elif len(text) <= hard_max - len(emoji_prefix) - len(update_badge):
            # Fits in optimal range, keep as is
            pass
        else:
            # Between 55-60, still acceptable
            max_text = hard_max - len(emoji_prefix) - len(update_badge) - 3
            if len(text) > max_text:
                text = text[:max_text].rsplit(" ", 1)[0].rstrip(",.") + "…"

        base = f"{emoji_prefix}{update_badge}{text}"

        # Append verdict badge if it fits within hard cap
        if verdict and len(base) + len(f" ({verdict})") <= hard_max:
            base = f"{base} ({verdict})"

        return base[:hard_max]

    @staticmethod
    def generate_hashtags(post, verdict: str | None = None) -> str:
        """Return a space-joined hashtag string (5-8 tags, always #Shorts #Reddit)."""
        sub_key = post.subreddit.lower().split("+")[0]  # e.g. "Steam+pcgaming" → "steam"
        niche = _SUBREDDIT_TAGS.get(sub_key, ["#RedditStories"])[:5]

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
        return " ".join(unique[:8])

    @staticmethod
    def generate_description(post, verdict: str | None = None) -> str:
        """
        Return optimized YouTube description for 50%+ CTR.

        Structure:
        1. Hook (emoji + CTA) - shown before "Show more" [primary engagement driver]
        2. Summary (story intro + verdict if applicable)
        3. Hashtags (3-5 relevant tags)
        4. CTA (Subscribe message)

        Optimizations:
        - "Reddit voted" pattern for judgment stories
        - "Community has spoken" for gaming
        - "What would YOU do?" engagement hook
        - 👇 CTA emoji in hook
        """
        sub_key = post.subreddit.lower().split("+")[0]

        # Hook first line — shown before YouTube "Show more", drives CTR
        hook = _DESC_HOOK.get(sub_key)
        if not hook:
            intro = _SUBREDDIT_INTRO.get(sub_key, "A Redditor shares their story")
            # Use heuristic to generate hook for unknown subreddit
            hook = _generate_hook_heuristic(sub_key, intro)

        # Summary: prefer body, fall back to top comment, then title
        intro = _SUBREDDIT_INTRO.get(sub_key, "A Redditor shares their story")
        body = (post.body or "").strip()
        if not body and getattr(post, "comments", None):
            body = post.comments[0].body  # top comment as teaser
        source = body or post.title
        source = re.sub(r"\*+|#+|`+", "", source)
        source = re.sub(r"\s+", " ", source).strip()

        if len(source) > 120:
            summary_raw = source[:120].rsplit(" ", 1)[0]
        else:
            summary_raw = source

        summary = f"{intro} — {summary_raw.rstrip('.,')}."

        # Social proof: show upvote count for popular posts
        score = getattr(post, "score", 0)
        if score >= 1000:
            score_str = f"{score / 1000:.1f}k"
            social_proof = f"🔥 {score_str} upvotes on Reddit"
        else:
            social_proof = ""

        # Verdict badge for judgment stories
        verdict_line = f"Reddit voted: {verdict} 🏆" if verdict else ""

        # Engagement question (drives comments)
        engagement = _ENGAGEMENT_Q.get(sub_key, "What do YOU think? Comment below! 👇")

        hashtags = MetaGenerator.generate_hashtags(post, verdict=verdict)
        cta = _NICHE_CTA.get(sub_key, "🔔 Subscribe for daily Reddit stories")

        # Build description from non-empty parts
        parts = [hook]
        if social_proof:
            parts.append(social_proof)
        parts.append(summary)
        if verdict_line:
            parts.append(verdict_line)
        parts.append(engagement)
        parts.append(f"{hashtags}\n{cta}")

        desc = "\n\n".join(parts)

        # Hard cap 500 chars — trim summary if needed
        if len(desc) > 500:
            fixed_parts = [hook]
            if social_proof:
                fixed_parts.append(social_proof)
            fixed_parts += ([verdict_line] if verdict_line else [])
            fixed_parts += [engagement, f"{hashtags}\n{cta}"]
            fixed = "\n\n".join(fixed_parts)
            budget = 500 - len(fixed) - 4  # 4 = "\n\n" separator
            if budget > 20:
                short_summary = summary[:budget].rsplit(" ", 1)[0] + "…"
                fixed_parts.insert(1 + bool(social_proof), short_summary)
            desc = "\n\n".join(p for p in fixed_parts if p).strip()

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
