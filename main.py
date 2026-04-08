#!/usr/bin/env python3
"""
Roblox Shorts Video Maker

Automated pipeline that generates YouTube Shorts from Reddit r/roblox posts.
No Reddit API key required - uses .json endpoints directly.
Also supports text file input for offline video creation.

Usage:
    python main.py                           # Fetch top posts from r/roblox
    python main.py --post <post_id>          # Process a specific Reddit post
    python main.py --limit 3 --time day      # Top 3 posts from today
    python main.py --file script.txt         # Create video from text file
    python main.py --dir scripts/            # Process all .txt files in directory
    python main.py --subreddit askreddit     # Use a different subreddit
"""

import argparse
import os
import sys
import tempfile
import shutil
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_loader import load_config
from utils.meta_generator import MetaGenerator
from reddit.scraper import RedditScraper, TextFileScraper
from tts.engine import TTSEngine
from video.composer import VideoComposer

console = Console()

BANNER = """
[bold cyan]
 ____       _     _               ____  _                _
|  _ \\ ___ | |__ | | _____  __  / ___|| |__   ___  _ __| |_ ___
| |_) / _ \\| '_ \\| |/ _ \\ \\/ /  \\___ \\| '_ \\ / _ \\| '__| __/ __|
|  _ < (_) | |_) | | (_) >  <    ___) | | | | (_) | |  | |_\\__ \\
|_| \\_\\___/|_.__/|_|\\___/_/\\_\\  |____/|_| |_|\\___/|_|   \\__|___/
[/bold cyan]
[dim]Automated YouTube Shorts · No API Key Required[/dim]
"""


def process_post(post, tts_engine: TTSEngine, composer: VideoComposer, scraper) -> str | None:
    """Process a single post (Reddit or text file) into a Shorts video."""
    console.print(f"\n[bold]Processing: {post.title[:60]}...[/bold]")
    console.print(f"  [dim]ID: {post.id} | Score: {post.score} | Comments: {len(post.comments)}[/dim]")

    # Create temp directory for this post's audio files
    temp_dir = tempfile.mkdtemp(prefix=f"roblox_shorts_{post.id}_")

    try:
        # Step 1: Generate TTS audio
        console.print("  [cyan][1/3] Generating TTS audio...[/cyan]")
        segments = tts_engine.generate_for_post(post, temp_dir)

        if not segments:
            console.print("  [yellow]No valid segments generated. Skipping.[/yellow]")
            return None

        # Step 2: Compose video
        console.print("  [cyan][2/3] Composing video...[/cyan]")
        output_path = composer.compose_video(post, segments)

        if not output_path:
            console.print("  [red]Video composition failed. Skipping.[/red]")
            return None

        # Step 3: Save meta + history
        console.print("  [cyan][3/3] Updating history & saving meta...[/cyan]")
        scraper.save_to_history(post.id)
        meta_path = MetaGenerator.save_meta(post, output_path)
        console.print(f"  [dim]Meta: {os.path.basename(meta_path)}[/dim]")

        return output_path

    finally:
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    console.print(BANNER)

    # Parse arguments
    parser = argparse.ArgumentParser(description="Roblox Shorts Video Maker")

    # Source options (mutually exclusive group)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--post", type=str, help="Specific Reddit post ID")
    source_group.add_argument("--file", type=str, help="Text file to create video from")
    source_group.add_argument("--dir", type=str, help="Directory of .txt files to process")

    # Reddit options
    parser.add_argument("--subreddit", type=str, help="Subreddit to fetch from (default: roblox)")
    parser.add_argument("--limit", type=int, help="Maximum number of posts to process")
    parser.add_argument(
        "--time",
        type=str,
        default="week",
        choices=["hour", "day", "week", "month", "year", "all"],
        help="Time filter for top posts (default: week)",
    )

    # General options
    parser.add_argument("--config", type=str, default="config.toml", help="Config file path")
    args = parser.parse_args()

    # Load config
    console.print("[cyan]Loading configuration...[/cyan]")
    config = load_config(args.config)

    # Override config with CLI args
    if args.limit:
        config["reddit"]["post_limit"] = args.limit
    if args.subreddit:
        config["reddit"]["subreddit"] = args.subreddit

    # Initialize TTS and video composer
    console.print("[cyan]Initializing components...[/cyan]")
    tts_engine = TTSEngine(config)
    composer = VideoComposer(config)

    # Determine source mode and fetch posts
    posts = []

    if args.file:
        # === Text File Mode ===
        console.print(Panel("[bold]Mode: Text File Input[/bold]", style="green"))
        scraper = TextFileScraper(config)
        post = scraper.load_from_file(args.file)
        posts = [post] if post else []

    elif args.dir:
        # === Directory Mode ===
        console.print(Panel("[bold]Mode: Directory Batch[/bold]", style="green"))
        scraper = TextFileScraper(config)
        posts = scraper.load_from_directory(args.dir)

    else:
        # === Reddit Mode (no API key needed) ===
        console.print(Panel("[bold]Mode: Reddit Scraping (no API key)[/bold]", style="cyan"))
        scraper = RedditScraper(config)

        if args.post:
            console.print(f"[cyan]Fetching specific post: {args.post}[/cyan]")
            post = scraper.fetch_single_post(args.post)
            posts = [post] if post else []
        else:
            posts = scraper.fetch_posts(time_filter=args.time)

    if not posts:
        console.print("[yellow]No posts found to process. Exiting.[/yellow]")
        return

    # Process each post
    results = []
    for i, post in enumerate(posts, 1):
        console.print(
            Panel(f"[bold]Post {i}/{len(posts)}[/bold]", style="cyan")
        )
        output = process_post(post, tts_engine, composer, scraper)
        if output:
            results.append({"post": post, "output": output})

    # Summary
    console.print("\n")
    if results:
        table = Table(title="Generated Videos", show_lines=True)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Title", style="green", max_width=45)
        table.add_column("Score", justify="right")
        table.add_column("Output File", style="cyan")

        for i, r in enumerate(results, 1):
            table.add_row(
                str(i),
                r["post"].title[:45],
                str(r["post"].score),
                os.path.basename(r["output"]),
            )

        console.print(table)
        console.print(
            f"\n[bold green][OK] Successfully generated {len(results)} video(s)![/bold green]"
        )
        console.print(f"[dim]Output directory: {composer.output_dir}/[/dim]")
    else:
        console.print("[yellow]No videos were generated.[/yellow]")


if __name__ == "__main__":
    main()
