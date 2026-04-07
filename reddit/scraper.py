"""Reddit r/roblox scraper using .json endpoints (no API key required)."""

import json
import os
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import requests
from rich.console import Console

console = Console()

# Reddit .json endpoint base
REDDIT_BASE = "https://www.reddit.com"
HEADERS = {
    "User-Agent": "RobloxShortsMaker/1.0 (educational project)",
    "Accept": "application/json",
}


@dataclass
class Comment:
    """Represents a single Reddit comment."""
    id: str
    author: str
    body: str
    score: int


@dataclass
class RedditPost:
    """Represents a Reddit post with its top comments."""
    id: str
    title: str
    body: str
    author: str
    score: int
    url: str
    subreddit: str
    comments: list[Comment] = field(default_factory=list)
    num_comments: int = 0

    def all_text_segments(self) -> list[str]:
        """Return all text segments in order: title, body (if any), then comments."""
        segments = [self.title]
        if self.body and len(self.body.strip()) > 0:
            segments.append(self.body)
        for comment in self.comments:
            segments.append(comment.body)
        return segments


@dataclass
class TextFilePost:
    """Post created from a local text file (no Reddit needed)."""
    id: str
    title: str
    body: str
    author: str = "Author"
    score: int = 0
    url: str = ""
    subreddit: str = "roblox"
    comments: list[Comment] = field(default_factory=list)

    def all_text_segments(self) -> list[str]:
        segments = [self.title]
        if self.body and len(self.body.strip()) > 0:
            segments.append(self.body)
        for comment in self.comments:
            segments.append(comment.body)
        return segments


class RedditScraper:
    """Scrapes posts and comments from Reddit using .json endpoints (no API key)."""

    def __init__(self, config: dict):
        reddit_cfg = config.get("reddit", {})
        self.subreddit_name = reddit_cfg.get("subreddit", "roblox")
        self.post_limit = reddit_cfg.get("post_limit", 5)
        self.min_upvotes = reddit_cfg.get("min_upvotes", 100)
        self.min_comments_count = reddit_cfg.get("min_comments", 10)
        self.max_comment_length = reddit_cfg.get("max_comment_length", 500)
        self.min_comment_score = reddit_cfg.get("min_comment_score", 0)
        self.top_comments = reddit_cfg.get("top_comments", 5)
        self.history_file = config.get("output", {}).get(
            "history_file", "output/history.json"
        )
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._session.verify = False  # Handle corporate proxies / SSL issues
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _request_json(self, url: str, params: dict = None) -> dict | None:
        """Make a request to Reddit .json endpoint with rate limiting."""
        try:
            time.sleep(1.5)  # Rate limiting - be polite
            resp = self._session.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                console.print("[yellow]Rate limited. Waiting 10s...[/yellow]")
                time.sleep(10)
                resp = self._session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            console.print(f"[red]Request error: {e}[/red]")
            return None

    def _load_history(self) -> set[str]:
        """Load previously processed post IDs."""
        path = Path(self.history_file)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("processed_ids", []))
        return set()

    def save_to_history(self, post_id: str):
        """Save a post ID to history to avoid duplicates."""
        path = Path(self.history_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        history = {"processed_ids": []}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)

        if post_id not in history["processed_ids"]:
            history["processed_ids"].append(post_id)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def _parse_comments(self, comments_data: list) -> list[Comment]:
        """Parse comments from Reddit JSON response."""
        comments = []
        if not comments_data or len(comments_data) < 2:
            return comments

        # Comments are in the second element of the response
        comment_listing = comments_data[1].get("data", {}).get("children", [])

        for child in comment_listing[:self.top_comments * 2]:
            if child.get("kind") != "t1":
                continue
            data = child.get("data", {})
            body = data.get("body", "").strip()
            author = data.get("author", "Anonymous")

            score = data.get("score", 0)
            if (
                body
                and body not in ("[deleted]", "[removed]")
                and len(body) <= self.max_comment_length
                and author not in ("[deleted]", "AutoModerator")
                and score >= self.min_comment_score
            ):
                comments.append(Comment(
                    id=data.get("id", ""),
                    author=author,
                    body=body,
                    score=score,
                ))

            if len(comments) >= self.top_comments:
                break

        return comments

    def fetch_posts(self, time_filter: str = "week") -> list[RedditPost]:
        """
        Fetch top posts from the configured subreddit using .json endpoint.

        Auto-expands time filter if no new posts are found:
        week → month → year → all

        Args:
            time_filter: Starting time filter (hour, day, week, month, year, all)

        Returns:
            List of RedditPost objects with their top comments
        """
        fallback_filters = ["week", "month", "year", "all"]
        if time_filter in fallback_filters:
            start_idx = fallback_filters.index(time_filter)
            filters_to_try = fallback_filters[start_idx:]
        else:
            filters_to_try = [time_filter]

        for tf in filters_to_try:
            posts = self._fetch_posts_with_filter(tf)
            if posts:
                return posts
            console.print(
                f"  [yellow]No new posts for time_filter='{tf}', trying broader range...[/yellow]"
            )

        return []

    def _fetch_posts_with_filter(self, time_filter: str) -> list[RedditPost]:
        """Internal: fetch posts for a specific time filter."""
        history = self._load_history()
        posts = []

        console.print(
            f"[cyan]Fetching posts from r/{self.subreddit_name} "
            f"(time={time_filter})...[/cyan]"
        )

        # Fetch subreddit top posts via .json
        url = f"{REDDIT_BASE}/r/{self.subreddit_name}/top.json"
        params = {
            "t": time_filter,
            "limit": self.post_limit * 3,  # Fetch extra for filtering
        }
        data = self._request_json(url, params)

        if not data:
            console.print("[red]Failed to fetch subreddit data.[/red]")
            return posts

        children = data.get("data", {}).get("children", [])

        for child in children:
            post_data = child.get("data", {})
            post_id = post_data.get("id", "")

            # Skip already processed
            if post_id in history:
                continue

            # Filter by upvotes
            score = post_data.get("score", 0)
            if score < self.min_upvotes:
                continue

            # Filter by comment count
            num_comments = post_data.get("num_comments", 0)
            if num_comments < self.min_comments_count:
                continue

            # Fetch comments for this post
            permalink = post_data.get("permalink", "")
            if not permalink:
                continue

            comments_url = f"{REDDIT_BASE}{permalink}.json"
            comments_data = self._request_json(comments_url, {"sort": "top", "limit": self.top_comments * 2})

            comments = []
            if comments_data and isinstance(comments_data, list):
                comments = self._parse_comments(comments_data)

            if len(comments) == 0:
                continue

            post = RedditPost(
                id=post_id,
                title=post_data.get("title", ""),
                body=post_data.get("selftext", ""),
                author=post_data.get("author", "Anonymous"),
                score=score,
                url=post_data.get("url", ""),
                subreddit=self.subreddit_name,
                comments=comments,
                num_comments=num_comments,
            )
            posts.append(post)

            console.print(
                f"  [green][OK][/green] {post.title[:60]}... "
                f"(+{post.score}, {len(comments)} comments)"
            )

            if len(posts) >= self.post_limit:
                break

        console.print(f"[cyan]Found {len(posts)} eligible posts.[/cyan]")
        return posts

    def fetch_single_post(self, post_id: str) -> RedditPost | None:
        """Fetch a specific post by ID using .json endpoint."""
        console.print(f"[cyan]Fetching post {post_id}...[/cyan]")

        url = f"{REDDIT_BASE}/comments/{post_id}.json"
        data = self._request_json(url, {"sort": "top"})

        if not data or not isinstance(data, list) or len(data) == 0:
            console.print(f"[red]Failed to fetch post {post_id}[/red]")
            return None

        try:
            post_data = data[0]["data"]["children"][0]["data"]
            comments = self._parse_comments(data)

            return RedditPost(
                id=post_data.get("id", post_id),
                title=post_data.get("title", ""),
                body=post_data.get("selftext", ""),
                author=post_data.get("author", "Anonymous"),
                score=post_data.get("score", 0),
                url=post_data.get("url", ""),
                subreddit=post_data.get("subreddit", self.subreddit_name),
                comments=comments,
                num_comments=post_data.get("num_comments", 0),
            )
        except (KeyError, IndexError) as e:
            console.print(f"[red]Error parsing post {post_id}: {e}[/red]")
            return None


class TextFileScraper:
    """
    Load content from local text files instead of Reddit.
    Allows video creation without any API or web access.

    Text file format:
    ---
    title: Your Video Title Here
    author: AuthorName
    ---
    This is the body text (optional).

    ---comment---
    This is the first comment text.
    ---comment author:Username score:42---
    This is the second comment with metadata.
    """

    def __init__(self, config: dict):
        self.history_file = config.get("output", {}).get(
            "history_file", "output/history.json"
        )

    def save_to_history(self, post_id: str):
        """Save a post ID to history."""
        path = Path(self.history_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        history = {"processed_ids": []}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)

        if post_id not in history["processed_ids"]:
            history["processed_ids"].append(post_id)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def load_from_file(self, file_path: str) -> TextFilePost | None:
        """Load a post from a text file."""
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return None

        console.print(f"[cyan]Loading from file: {file_path}[/cyan]")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate a stable ID from file path
        file_id = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:10]

        # Parse header
        title = path.stem.replace("_", " ").replace("-", " ").title()
        author = "Author"
        body = ""
        comments = []

        sections = content.split("---")

        # Parse front matter if present
        if len(sections) >= 3 and sections[0].strip() == "":
            header = sections[1]
            for line in header.strip().split("\n"):
                if line.startswith("title:"):
                    title = line[6:].strip()
                elif line.startswith("author:"):
                    author = line[7:].strip()
            # Rest is body + comments
            remaining = "---".join(sections[2:])
        else:
            remaining = content

        # Split body and comments
        parts = remaining.split("---comment")
        body = parts[0].strip()

        # Parse comments
        for i, part in enumerate(parts[1:]):
            lines = part.strip().split("\n", 1)
            comment_meta = lines[0].strip().rstrip("---")
            comment_body = lines[1].strip() if len(lines) > 1 else ""

            if not comment_body:
                continue

            # Parse optional metadata from comment header
            c_author = "User"
            c_score = 0
            if "author:" in comment_meta:
                try:
                    c_author = comment_meta.split("author:")[1].split()[0]
                except IndexError:
                    pass
            if "score:" in comment_meta:
                try:
                    c_score = int(comment_meta.split("score:")[1].split()[0])
                except (IndexError, ValueError):
                    pass

            comments.append(Comment(
                id=f"c_{i}",
                author=c_author,
                body=comment_body,
                score=c_score,
            ))

        post = TextFilePost(
            id=file_id,
            title=title,
            body=body,
            author=author,
            comments=comments,
        )

        console.print(
            f"  [green][OK][/green] Loaded: {title} "
            f"({len(comments)} comments)"
        )
        return post

    def load_from_directory(self, dir_path: str) -> list[TextFilePost]:
        """Load all .txt files from a directory as posts."""
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            console.print(f"[red]Directory not found: {dir_path}[/red]")
            return []

        posts = []
        for txt_file in sorted(path.glob("*.txt")):
            post = self.load_from_file(str(txt_file))
            if post:
                posts.append(post)

        console.print(f"[cyan]Loaded {len(posts)} post(s) from {dir_path}[/cyan]")
        return posts
