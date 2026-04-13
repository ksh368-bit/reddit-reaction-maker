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
import logging
import logging.handlers
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

from utils.config_loader import load_config, validate_config
from utils.meta_generator import MetaGenerator
from utils.metrics import MetricsCollector
from utils.verdict_extractor import extract_verdict
from reddit.scraper import RedditScraper, TextFileScraper
from tts.engine import TTSEngine
from video.composer import VideoComposer
from youtube.uploader import upload_video

console = Console()


def setup_logging(log_dir: str = "output/logs", level: str = "INFO") -> None:
    """Configure file and console logging for the pipeline."""
    os.makedirs(log_dir, exist_ok=True)

    # Log file path: output/logs/YYYY-MM-DD.log
    log_file = os.path.join(log_dir, datetime.now().strftime("%Y-%m-%d.log"))

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Only add handlers if not already added (avoid duplicates on multiple calls)
    if not logger.handlers:
        # File handler with daily rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=10  # 10MB per file, keep 10
        )
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Console handler (minimal; Rich handles pretty output)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only warnings + errors to console

        # Format
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        logging.getLogger("rich").setLevel(logging.WARNING)  # Reduce Rich noise

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


def process_post(post, tts_engine: TTSEngine, composer: VideoComposer, scraper, config: dict, metrics: MetricsCollector | None = None) -> str | None:
    """Process a single post (Reddit or text file) into a Shorts video."""
    console.print(f"\n[bold]Processing: {post.title[:60]}...[/bold]")
    console.print(f"  [dim]ID: {post.id} | Score: {post.score} | Comments: {len(post.comments)}[/dim]")

    if metrics:
        metrics.record("post_id", post.id)
        metrics.record("subreddit", post.subreddit if hasattr(post, "subreddit") else "unknown")

    # Create temp directory for this post's audio files
    temp_dir = tempfile.mkdtemp(prefix=f"roblox_shorts_{post.id}_")

    try:
        # Step 1: Generate TTS audio
        console.print("  [cyan][1/3] Generating TTS audio...[/cyan]")
        tts_start = metrics.start_timer("tts_duration_sec") if metrics else 0
        segments = tts_engine.generate_for_post(post, temp_dir)
        if metrics:
            metrics.end_timer("tts_duration_sec", tts_start)

        if not segments:
            console.print("  [yellow]No valid segments generated. Skipping.[/yellow]")
            if metrics:
                metrics.mark_error("tts_failed", "No valid segments generated")
            return None

        if metrics:
            metrics.record("segments_count", len(segments))

        # Step 2: Compose video
        console.print("  [cyan][2/3] Composing video...[/cyan]")
        video_start = metrics.start_timer("video_composition_duration_sec") if metrics else 0
        output_path = composer.compose_video(post, segments)
        if metrics:
            metrics.end_timer("video_composition_duration_sec", video_start)

        if not output_path:
            console.print("  [red]Video composition failed. Skipping.[/red]")
            if metrics:
                metrics.mark_error("video_failed", "Video composition failed")
            return None

        # Step 3: Save meta + history
        console.print("  [cyan][3/3] Updating history & saving meta...[/cyan]")
        scraper.save_to_history(post.id)
        verdict   = extract_verdict(post.comments) if post.comments else None
        meta_path = MetaGenerator.save_meta(post, output_path, verdict=verdict)
        console.print(f"  [dim]Meta: {os.path.basename(meta_path)}[/dim]")

        # Step 4: Upload to YouTube (optional, graceful failure)
        yt_cfg = config.get("youtube", {})
        if yt_cfg.get("enabled", False):
            console.print("  [cyan][4/4] Uploading to YouTube...[/cyan]")
            title = MetaGenerator.generate_title(post, verdict=verdict)
            description = MetaGenerator.generate_description(post, verdict=verdict)
            thumb_path = os.path.splitext(output_path)[0] + "_thumb.png"
            if not os.path.exists(thumb_path):
                thumb_path = None
            yt_start = metrics.start_timer("youtube_upload_duration_sec") if metrics else 0
            video_id = upload_video(
                output_path, title, description,
                credentials_path=yt_cfg.get("credentials_path", "credentials.json"),
                token_path=yt_cfg.get("token_path", "token.json"),
                privacy=yt_cfg.get("privacy", "public"),
                category_id=yt_cfg.get("category_id", "24"),
                made_for_kids=yt_cfg.get("made_for_kids", False),
                notify_subscribers=yt_cfg.get("notify_subscribers", True),
                thumb_path=thumb_path if yt_cfg.get("upload_thumbnail", True) else None,
            )
            if metrics:
                metrics.end_timer("youtube_upload_duration_sec", yt_start)
            if video_id:
                if metrics:
                    metrics.record("youtube_video_id", video_id)
                console.print(f"  [green]YouTube: https://youtu.be/{video_id}[/green]")
            else:
                console.print("  [yellow]YouTube upload failed (video kept locally)[/yellow]")

        if metrics:
            metrics.mark_success()
        return output_path

    finally:
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    console.print(BANNER)

    # Parse arguments with comprehensive help
    parser = argparse.ArgumentParser(
        prog="reddit-shorts",
        description="🎬 Automated YouTube Shorts generator from Reddit posts (no API key required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  Fetch top posts from r/roblox this week:
    %(prog)s --limit 1

  Fetch top posts from r/steam today:
    %(prog)s --subreddit steam --time day --limit 3

  Process specific Reddit post:
    %(prog)s --post abc123def456

  Process local text file (no Reddit needed):
    %(prog)s --file story.txt

  Batch process directory of text files:
    %(prog)s --dir scripts/

  Use custom config file:
    %(prog)s --config my_config.toml --limit 1

FEATURES:
  • Multi-language TTS (EdgeTTS or gTTS)
  • Word-level karaoke captions with Whisper
  • Auto-upload to YouTube with OAuth2
  • Automatic metrics & logging to output/logs/
  • Configurable via config.toml (no CLI flag needed)

CONFIGURATION:
  See config.template.toml for all options:
    cp config.template.toml config.toml
    # Edit config.toml...
    %(prog)s

  CLI flags override config.toml values.

QUICK START:
  1. python %(prog)s --limit 1                 (default: r/roblox, top this week)
  2. Check output/ for generated videos
  3. Enable YouTube upload in config.toml if desired

For detailed help, see: https://github.com/SeungheeKim/reddit-reaction-maker
        """
    )

    # Source options (mutually exclusive group)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--post",
        type=str,
        metavar="POST_ID",
        help="Process specific Reddit post by ID (e.g., abc123def456)"
    )
    source_group.add_argument(
        "--file",
        type=str,
        metavar="FILE",
        help="Create video from text file (no Reddit API needed)"
    )
    source_group.add_argument(
        "--dir",
        type=str,
        metavar="DIRECTORY",
        help="Batch process all .txt files in directory"
    )

    # Reddit options
    parser.add_argument(
        "--subreddit",
        type=str,
        metavar="SUBREDDIT",
        help="Subreddit to fetch from (default: from config.toml)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of posts to process (default: from config.toml)"
    )
    parser.add_argument(
        "--time",
        type=str,
        default="week",
        choices=["hour", "day", "week", "month", "year", "all"],
        metavar="PERIOD",
        help="Time filter for top posts: hour, day, week (default), month, year, all"
    )

    # General options
    parser.add_argument(
        "--config",
        type=str,
        default="config.toml",
        metavar="FILE",
        help="Config file path (default: config.toml)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )

    args = parser.parse_args()

    # Load config
    console.print("[cyan]Loading configuration...[/cyan]")
    config = load_config(args.config)

    # Setup logging (file + console) - must be done early for validation logging
    logging_cfg = config.get("logging", {})
    setup_logging(
        log_dir=logging_cfg.get("log_dir", "output/logs"),
        level=logging_cfg.get("level", "INFO")
    )

    # Validate configuration
    if not validate_config(config):
        sys.exit(1)

    # Override config with CLI args
    if args.limit:
        config["reddit"]["post_limit"] = args.limit
    if args.subreddit:
        config["reddit"]["subreddit"] = args.subreddit

    # Initialize TTS, video composer, and metrics collector
    console.print("[cyan]Initializing components...[/cyan]")
    tts_engine = TTSEngine(config)
    composer = VideoComposer(config)
    metrics = MetricsCollector(enabled=True)  # Always enabled for observability

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
        output = process_post(post, tts_engine, composer, scraper, config, metrics=metrics)
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

    # Export metrics
    metrics_file = metrics.export_json(output_dir=composer.output_dir)
    if metrics_file:
        console.print(f"[dim]Metrics: {os.path.basename(metrics_file)}[/dim]")
        # Attempt Datadog export (optional, graceful failure)
        metrics.export_to_datadog()


if __name__ == "__main__":
    main()
