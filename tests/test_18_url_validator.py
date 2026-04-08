"""Tests for background video URL validator and auto-repair."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.url_validator import check_url, find_replacement, validate_and_repair


class TestCheckUrl:
    def test_returns_true_for_valid_url(self):
        # Mock yt-dlp simulate succeeding (returncode=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_url("https://www.youtube.com/watch?v=validid") is True

    def test_returns_false_for_unavailable_url(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert check_url("https://www.youtube.com/watch?v=deadid") is False

    def test_returns_false_on_exception(self):
        with patch("subprocess.run", side_effect=Exception("timeout")):
            assert check_url("https://www.youtube.com/watch?v=anything") is False


class TestFindReplacement:
    def test_returns_url_string_when_found(self):
        with patch("subprocess.run") as mock_run:
            # First call: ytsearch returns an ID
            # Second call: simulate check passes
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="abc123XYZ\n", stderr=""),
                MagicMock(returncode=0),  # simulate check
            ]
            result = find_replacement("Subway Surfers")
            assert result is not None
            assert "youtube.com" in result
            assert "abc123XYZ" in result

    def test_returns_none_when_no_results(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = find_replacement("Subway Surfers")
            assert result is None

    def test_skips_warning_lines_in_output(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(
                    returncode=0,
                    stdout="WARNING: some warning\nabc123XYZ\n",
                    stderr="",
                ),
                MagicMock(returncode=0),  # simulate check
            ]
            result = find_replacement("Minecraft Parkour")
            assert result is not None
            assert "abc123XYZ" in result


class TestValidateAndRepair:
    def _make_json(self, tmpdir, videos: dict) -> str:
        path = os.path.join(tmpdir, "background_videos.json")
        Path(path).write_text(json.dumps({"videos": videos}))
        return path

    def test_no_changes_when_all_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            videos = {
                "game-1": {
                    "url": "https://www.youtube.com/watch?v=goodid1",
                    "filename": "game-1.mp4",
                    "game": "Good Game",
                }
            }
            json_path = self._make_json(tmpdir, videos)
            with patch("video.url_validator.check_url", return_value=True):
                report = validate_and_repair(json_path)
            assert report["dead"] == []
            assert report["repaired"] == []
            # JSON unchanged
            data = json.loads(Path(json_path).read_text())
            assert data["videos"]["game-1"]["url"] == "https://www.youtube.com/watch?v=goodid1"

    def test_repairs_dead_url_when_replacement_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            videos = {
                "game-1": {
                    "url": "https://www.youtube.com/watch?v=deadid",
                    "filename": "game-1.mp4",
                    "game": "Subway Surfers",
                }
            }
            json_path = self._make_json(tmpdir, videos)
            new_url = "https://www.youtube.com/watch?v=newid123"
            with patch("video.url_validator.check_url", return_value=False), \
                 patch("video.url_validator.find_replacement", return_value=new_url):
                report = validate_and_repair(json_path)
            assert "game-1" in report["dead"]
            assert "game-1" in report["repaired"]
            # JSON updated
            data = json.loads(Path(json_path).read_text())
            assert data["videos"]["game-1"]["url"] == new_url

    def test_marks_unrepairable_when_no_replacement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            videos = {
                "game-1": {
                    "url": "https://www.youtube.com/watch?v=deadid",
                    "filename": "game-1.mp4",
                    "game": "Obscure Game",
                }
            }
            json_path = self._make_json(tmpdir, videos)
            with patch("video.url_validator.check_url", return_value=False), \
                 patch("video.url_validator.find_replacement", return_value=None):
                report = validate_and_repair(json_path)
            assert "game-1" in report["dead"]
            assert "game-1" in report["unrepairable"]
            assert "game-1" not in report["repaired"]

    def test_handles_multiple_entries_mixed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            videos = {
                "ok-game":   {"url": "https://www.youtube.com/watch?v=goodid", "game": "OK"},
                "dead-game": {"url": "https://www.youtube.com/watch?v=deadid", "game": "Dead"},
            }
            json_path = self._make_json(tmpdir, videos)
            def fake_check(url):
                return "goodid" in url
            with patch("video.url_validator.check_url", side_effect=fake_check), \
                 patch("video.url_validator.find_replacement",
                       return_value="https://www.youtube.com/watch?v=fixedid"):
                report = validate_and_repair(json_path)
            assert report["dead"] == ["dead-game"]
            assert report["repaired"] == ["dead-game"]

    def test_returns_report_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = self._make_json(tmpdir, {})
            report = validate_and_repair(json_path)
            assert "dead" in report
            assert "repaired" in report
            assert "unrepairable" in report
            assert "ok" in report
