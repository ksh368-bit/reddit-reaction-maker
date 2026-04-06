"""Background video and audio management with yt-dlp auto-download."""

import json
import os
import random
from pathlib import Path

import requests
from rich.console import Console

console = Console()

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}

VIDEOS_JSON = "assets/background_videos.json"
AUDIOS_JSON = "assets/background_audios.json"


# ──────────────────────────────────────────────
#  Download helpers
# ──────────────────────────────────────────────

def _download_with_ytdlp(url: str, output_path: str, is_audio: bool = False) -> bool:
    """Download a video/audio from YouTube using yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        console.print(
            "[red]yt-dlp not installed. Run: pip install yt-dlp[/red]"
        )
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Remove extension - yt-dlp adds it
    output_template = os.path.splitext(output_path)[0]

    # Find FFmpeg from imageio_ffmpeg (bundled)
    ffmpeg_path = None
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass

    ydl_opts = {
        "outtmpl": output_template + ".%(ext)s",
        "retries": 5,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
    }
    if ffmpeg_path:
        # Pass the full path to the binary (not just the directory),
        # because the bundled binary may not be named "ffmpeg"
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    if is_audio:
        ydl_opts.update({
            "format": "bestaudio/best",
            "extract_audio": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        # Prefer single-file mp4 first to avoid ffmpeg merge requirement
        ydl_opts.update({
            "format": "best[height<=1080][ext=mp4]/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
            "merge_output_format": "mp4",
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        console.print(f"[red]yt-dlp download error: {e}[/red]")
        return False


def _download_direct(url: str, output_path: str) -> bool:
    """Download a file directly via HTTP (for Pixabay CDN etc)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://pixabay.com/",
        "Accept": "audio/webm,audio/ogg,audio/mp3,audio/*;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(url, stream=True, timeout=30, verify=False, headers=headers)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        console.print(f"[red]Download error: {e}[/red]")
        return False


# ──────────────────────────────────────────────
#  Background Video Management
# ──────────────────────────────────────────────

def load_video_options() -> dict:
    """Load background video options from JSON."""
    path = Path(VIDEOS_JSON)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("videos", {})


def download_background_videos(background_dir: str) -> list[str]:
    """
    Ensure background videos are downloaded.
    Downloads missing videos from YouTube using yt-dlp.

    Returns list of available video file paths.
    """
    video_dir = Path(background_dir) / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    options = load_video_options()
    downloaded = []

    for key, info in options.items():
        filename = info.get("filename", f"{key}.mp4")
        output_path = str(video_dir / filename)

        if os.path.exists(output_path):
            downloaded.append(output_path)
            continue

        url = info.get("url", "")
        if not url:
            continue

        console.print(
            f"  [cyan]Downloading background video: {info.get('game', key)}...[/cyan]"
        )
        if _download_with_ytdlp(url, output_path, is_audio=False):
            # yt-dlp may use slightly different extension
            actual_path = output_path
            if not os.path.exists(actual_path):
                # Try finding the downloaded file
                base = os.path.splitext(output_path)[0]
                for ext in [".mp4", ".webm", ".mkv"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        actual_path = candidate
                        break

            if os.path.exists(actual_path):
                downloaded.append(actual_path)
                console.print(
                    f"    [green][OK][/green] {info.get('game', key)} "
                    f"(credit: {info.get('credit', 'Unknown')})"
                )
            else:
                console.print(f"    [yellow]File not found after download: {key}[/yellow]")
        else:
            console.print(f"    [yellow]Failed to download: {key}[/yellow]")

    # Also include any manually placed videos
    for f in video_dir.iterdir():
        full = str(f)
        if f.suffix.lower() in VIDEO_EXTENSIONS and full not in downloaded:
            downloaded.append(full)

    # Fallback: check the background_dir itself (legacy location)
    bg_path = Path(background_dir)
    for f in bg_path.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            full = str(f)
            if full not in downloaded:
                downloaded.append(full)

    return downloaded


# ──────────────────────────────────────────────
#  Background Audio Management
# ──────────────────────────────────────────────

def load_audio_options() -> dict:
    """Load background audio options from JSON."""
    path = Path(AUDIOS_JSON)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("audios", {})


def download_background_audios(background_dir: str) -> list[str]:
    """
    Ensure background audio files are downloaded.
    Downloads from direct URLs (Pixabay CDN) or YouTube.

    Returns list of available audio file paths.
    """
    audio_dir = Path(background_dir) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    options = load_audio_options()
    downloaded = []

    for key, info in options.items():
        filename = info.get("filename", f"{key}.mp3")
        output_path = str(audio_dir / filename)

        if os.path.exists(output_path):
            downloaded.append(output_path)
            continue

        url = info.get("url", "")
        if not url:
            continue

        console.print(
            f"  [cyan]Downloading background music: {info.get('title', key)}...[/cyan]"
        )

        # Determine download method based on URL
        is_youtube = "youtube.com" in url or "youtu.be" in url
        if is_youtube:
            success = _download_with_ytdlp(url, output_path, is_audio=True)
        else:
            success = _download_direct(url, output_path)

        if success and os.path.exists(output_path):
            downloaded.append(output_path)
            license_info = info.get("license", "Check source")
            console.print(
                f"    [green][OK][/green] {info.get('title', key)} "
                f"[dim]({license_info})[/dim]"
            )
        else:
            # For yt-dlp, check alternative extensions
            base = os.path.splitext(output_path)[0]
            for ext in [".mp3", ".m4a", ".ogg", ".wav"]:
                candidate = base + ext
                if os.path.exists(candidate):
                    downloaded.append(candidate)
                    console.print(f"    [green][OK][/green] {info.get('title', key)}")
                    break
            else:
                console.print(f"    [yellow]Failed to download: {key}[/yellow]")

    # Also include any manually placed audio files
    for f in audio_dir.iterdir():
        full = str(f)
        if f.suffix.lower() in AUDIO_EXTENSIONS and full not in downloaded:
            downloaded.append(full)

    return downloaded


# ──────────────────────────────────────────────
#  Selection helpers (used by composer)
# ──────────────────────────────────────────────

def setup_backgrounds(background_dir: str) -> dict:
    """
    Download all missing background assets and return available files.

    Returns dict with 'videos' and 'audios' lists.
    """
    console.print("[cyan]Setting up background assets...[/cyan]")

    videos = download_background_videos(background_dir)
    audios = download_background_audios(background_dir)

    console.print(
        f"  [green]Ready:[/green] {len(videos)} video(s), {len(audios)} audio(s)"
    )
    return {"videos": videos, "audios": audios}


def select_random_background(background_dir: str) -> str | None:
    """Select a random background video."""
    # Check video subdirectory first, then root
    video_dir = Path(background_dir) / "video"
    search_dirs = [video_dir, Path(background_dir)]

    all_videos = []
    for d in search_dirs:
        if d.exists():
            all_videos.extend(
                str(f) for f in d.iterdir()
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
            )

    if not all_videos:
        return None
    return random.choice(all_videos)


def select_random_audio(background_dir: str) -> str | None:
    """Select a random background audio."""
    audio_dir = Path(background_dir) / "audio"
    if not audio_dir.exists():
        return None

    audios = [
        str(f) for f in audio_dir.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]

    if not audios:
        return None
    return random.choice(audios)


def get_random_start_time(video_duration: float, clip_duration: float) -> float:
    """Get a random start time for clipping from a background video."""
    max_start = max(0, video_duration - clip_duration - 1)
    if max_start <= 0:
        return 0
    return random.uniform(0, max_start)
