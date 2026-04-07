"""
Test 01: Background videos should be gameplay (high-motion), not ASMR/craft.

Acceptance criteria:
- background_videos.json contains gameplay entries (Subway Surfers, Minecraft, etc.)
- No ASMR/craft-only entries remain
- At least 4 gameplay videos configured
- select_random_background returns a path when videos exist
"""
import json
import os
import pytest
from pathlib import Path


VIDEOS_JSON = "assets/background_videos.json"
GAMEPLAY_KEYWORDS = {
    "subway", "minecraft", "roblox", "parkour", "game",
    "geometry", "temple", "run", "fruit", "ninja",
}
ASMR_KEYWORDS = {
    "cement", "sand-art", "slime", "clay", "pottery",
    "soap", "candle", "kinetic", "food-prep", "paper-cutting",
}


def load_videos_json():
    path = Path(VIDEOS_JSON)
    assert path.exists(), f"{VIDEOS_JSON} not found"
    with open(path) as f:
        return json.load(f).get("videos", {})


def test_gameplay_videos_exist():
    """At least 4 gameplay video entries must be configured."""
    videos = load_videos_json()
    gameplay = [
        k for k in videos
        if any(kw in k.lower() for kw in GAMEPLAY_KEYWORDS)
    ]
    assert len(gameplay) >= 4, (
        f"Expected ≥4 gameplay videos, found {len(gameplay)}: {list(videos.keys())}"
    )


def test_no_asmr_only_entries():
    """ASMR/craft-only entries should be removed."""
    videos = load_videos_json()
    asmr_entries = [
        k for k in videos
        if any(kw in k.lower() for kw in ASMR_KEYWORDS)
    ]
    assert len(asmr_entries) == 0, (
        f"Found ASMR/craft entries that should be removed: {asmr_entries}"
    )


def test_all_entries_have_url_and_filename():
    """Every video entry must have a url and filename."""
    videos = load_videos_json()
    for key, info in videos.items():
        assert info.get("url"), f"Entry '{key}' missing 'url'"
        assert info.get("filename"), f"Entry '{key}' missing 'filename'"


def test_select_random_background_returns_path(tmp_path):
    """select_random_background returns a file path when a video exists."""
    from video.background import select_random_background

    # Create a fake video file in tmp dir
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    fake_video = video_dir / "fake.mp4"
    fake_video.write_bytes(b"fake")

    result = select_random_background(str(tmp_path))
    assert result is not None
    assert result.endswith(".mp4")


def test_select_random_background_returns_none_when_empty(tmp_path):
    """select_random_background returns None when no videos present."""
    from video.background import select_random_background
    result = select_random_background(str(tmp_path))
    assert result is None
