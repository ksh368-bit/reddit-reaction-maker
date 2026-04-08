"""Background video URL health checker and auto-repair."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Search queries per game name (used when finding replacements)
_SEARCH_QUERIES: dict[str, str] = {
    "Subway Surfers":   "subway surfers gameplay no commentary vertical shorts",
    "Minecraft Parkour":"minecraft parkour no commentary gameplay",
    "Geometry Dash":    "geometry dash gameplay no commentary",
    "Roblox Parkour":   "roblox parkour no commentary gameplay",
}
_DEFAULT_QUERY_SUFFIX = "gameplay no commentary shorts"

# Path to yt-dlp — prefer venv binary
_YTDLP = str(Path(sys.executable).parent / "yt-dlp")


def check_url(url: str) -> bool:
    """Return True if the YouTube URL is still available."""
    try:
        r = subprocess.run(
            [_YTDLP, "--simulate", "--quiet", "--no-warnings", url],
            capture_output=True,
            timeout=20,
        )
        return r.returncode == 0
    except Exception:
        return False


def find_replacement(game_name: str) -> str | None:
    """
    Search YouTube for a replacement video for *game_name*.
    Returns a full YouTube URL or None.
    """
    query = _SEARCH_QUERIES.get(game_name, f"{game_name} {_DEFAULT_QUERY_SUFFIX}")
    search_term = f"ytsearch5:{query}"

    try:
        r = subprocess.run(
            [_YTDLP, "--simulate", "--quiet", "--no-warnings",
             "--print", "id", search_term],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return None

        ids = [
            line.strip()
            for line in r.stdout.splitlines()
            if line.strip() and not line.startswith("WARNING")
        ]
        for vid_id in ids:
            url = f"https://www.youtube.com/watch?v={vid_id}"
            if check_url(url):
                return url
    except Exception:
        pass

    return None


def validate_and_repair(json_path: str) -> dict:
    """
    Check every URL in *json_path* (background_videos.json format).
    Dead URLs are replaced automatically when possible, and the file is
    updated in-place.

    Returns a report dict:
        {
          "ok":          [key, ...],
          "dead":        [key, ...],
          "repaired":    [key, ...],
          "unrepairable":[key, ...],
        }
    """
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    videos: dict = data.get("videos", {})

    report: dict[str, list[str]] = {
        "ok": [],
        "dead": [],
        "repaired": [],
        "unrepairable": [],
    }
    changed = False

    for key, info in videos.items():
        url = info.get("url", "")
        if not url:
            continue

        if check_url(url):
            report["ok"].append(key)
            continue

        # Dead URL
        report["dead"].append(key)
        game_name = info.get("game", key)
        replacement = find_replacement(game_name)

        if replacement:
            info["url"] = replacement
            report["repaired"].append(key)
            changed = True
        else:
            report["unrepairable"].append(key)

    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


# ──────────────────────────────────────────────
#  CLI entry point
# ──────────────────────────────────────────────

def _main() -> None:
    import argparse
    from rich.console import Console
    from rich.table import Table

    console = Console()
    parser = argparse.ArgumentParser(description="Validate & auto-repair background video URLs")
    parser.add_argument(
        "--json",
        default="assets/background_videos.json",
        help="Path to background_videos.json",
    )
    args = parser.parse_args()

    console.print(f"[cyan]Checking URLs in {args.json}...[/cyan]")
    report = validate_and_repair(args.json)

    table = Table(title="URL Health Check", show_lines=True)
    table.add_column("Key", style="bold")
    table.add_column("Status")

    for key in report["ok"]:
        table.add_row(key, "[green]OK[/green]")
    for key in report["repaired"]:
        table.add_row(key, "[yellow]DEAD → repaired[/yellow]")
    for key in report["unrepairable"]:
        table.add_row(key, "[red]DEAD (no replacement)[/red]")

    console.print(table)

    if report["unrepairable"]:
        console.print(
            f"\n[red]⚠ {len(report['unrepairable'])} URL(s) could not be repaired. "
            "Manual update required.[/red]"
        )
        sys.exit(1)
    elif report["repaired"]:
        console.print(f"\n[green]✓ {len(report['repaired'])} URL(s) auto-repaired.[/green]")
    else:
        console.print("\n[green]✓ All URLs healthy.[/green]")


if __name__ == "__main__":
    _main()
