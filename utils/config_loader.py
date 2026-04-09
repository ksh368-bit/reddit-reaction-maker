"""Configuration loader for the Roblox Shorts Maker."""

import shutil
import sys
from pathlib import Path

import toml
from rich.console import Console

console = Console()

DEFAULT_CONFIG_PATH = "config.toml"
TEMPLATE_CONFIG_PATH = "config.template.toml"


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """
    Load configuration from TOML file.

    If config.toml doesn't exist, copies from template.
    No API keys required - uses Reddit .json endpoints.
    """
    path = Path(config_path)

    if not path.exists():
        template = Path(TEMPLATE_CONFIG_PATH)
        if template.exists():
            shutil.copy(template, path)
            console.print(
                f"[green]Created {config_path} from template.[/green]"
            )
            console.print(
                "[cyan]No API keys needed! You can customize settings in config.toml[/cyan]"
            )
        else:
            console.print(
                f"[red]Error: Neither {config_path} nor {TEMPLATE_CONFIG_PATH} found.[/red]"
            )
            sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        config = toml.load(f)

    # Ensure required sections exist with defaults
    config.setdefault("reddit", {"subreddit": "roblox", "post_limit": 5})
    config.setdefault("tts", {"engine": "gtts", "language": "en"})
    config.setdefault("video", {})
    config.setdefault("output", {"dir": "output", "history_file": "output/history.json"})
    config.setdefault("youtube", {
        "enabled": False,
        "credentials_path": "credentials.json",
        "token_path": "token.json",
        "privacy": "public",
        "category_id": "24",
        "made_for_kids": False,
        "notify_subscribers": True,
        "upload_thumbnail": True,
    })

    return config
