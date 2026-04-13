"""Configuration loader for the Roblox Shorts Maker."""

import logging
import shutil
import sys
from pathlib import Path

import toml
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

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


def validate_config(config: dict) -> bool:
    """
    Validate configuration at startup. Returns True if valid, False otherwise.
    Prints clear error messages for issues found.
    """
    errors = []

    # Check font file exists
    font_path = config.get("video", {}).get("font", "assets/fonts/Montserrat-Bold.ttf")
    if not Path(font_path).exists():
        errors.append(f"Font file not found: {font_path}")

    # Check background directory exists
    bg_dir = config.get("video", {}).get("background_dir", "assets/backgrounds")
    if not Path(bg_dir).exists():
        errors.append(f"Background directory not found: {bg_dir}")

    # Check TTS engine is valid
    tts_engine = config.get("tts", {}).get("engine", "gtts")
    valid_engines = ["gtts", "edge-tts"]
    if tts_engine not in valid_engines:
        errors.append(f"Invalid TTS engine: {tts_engine}. Must be one of: {', '.join(valid_engines)}")

    # Check TTS language is valid (basic check)
    tts_lang = config.get("tts", {}).get("language", "en")
    valid_languages = ["en", "ko", "ja", "es", "fr", "de", "it", "pt", "ru", "zh", "ar"]
    if tts_lang not in valid_languages:
        logger.warning(f"Unknown TTS language: {tts_lang}. May not be supported by TTS engine.")

    # Check subreddit is not empty
    subreddit = config.get("reddit", {}).get("subreddit", "").strip()
    if not subreddit:
        errors.append("Subreddit is empty in [reddit] section")

    # Check video dimensions are positive
    width = config.get("video", {}).get("width", 1080)
    height = config.get("video", {}).get("height", 1920)
    if width <= 0 or height <= 0:
        errors.append(f"Invalid video dimensions: {width}x{height} (must be positive)")

    # Check YouTube credentials exist if upload enabled
    if config.get("youtube", {}).get("enabled", False):
        creds_path = config.get("youtube", {}).get("credentials_path", "credentials.json")
        if not Path(creds_path).exists():
            errors.append(
                f"YouTube upload enabled but credentials.json not found at {creds_path}. "
                f"Set youtube.enabled = false or provide YouTube OAuth credentials."
            )

    # Report errors
    if errors:
        console.print("[red][Error] Configuration validation failed:[/red]")
        for i, error in enumerate(errors, 1):
            console.print(f"  {i}. {error}")
        return False

    logger.info("Configuration validation passed")
    return True
