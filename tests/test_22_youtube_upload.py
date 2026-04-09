"""Tests for YouTube auto-upload integration (TDD — written before implementation)."""

from __future__ import annotations

import os
import sys
import json
import wave
import struct
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
#  _parse_tags_from_description (pure unit)
# ─────────────────────────────────────────────

class TestParseTagsFromDescription:
    def test_extracts_hashtags(self):
        from youtube.uploader import _parse_tags_from_description
        result = _parse_tags_from_description("#Shorts #Reddit #AITA")
        assert result == ["Shorts", "Reddit", "AITA"]

    def test_empty_description_returns_empty(self):
        from youtube.uploader import _parse_tags_from_description
        assert _parse_tags_from_description("") == []

    def test_ignores_plain_words(self):
        from youtube.uploader import _parse_tags_from_description
        assert _parse_tags_from_description("hello world foo bar") == []

    def test_hashtags_in_full_description(self):
        from youtube.uploader import _parse_tags_from_description
        desc = "A Redditor shares their story.\n\n#Shorts #Reddit #RelationshipAdvice\n🔔 Subscribe"
        tags = _parse_tags_from_description(desc)
        assert "Shorts" in tags
        assert "Reddit" in tags
        assert "RelationshipAdvice" in tags


# ─────────────────────────────────────────────
#  _get_credentials
# ─────────────────────────────────────────────

class TestGetCredentials:
    def test_uses_existing_valid_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False

        with patch("youtube.uploader.Credentials.from_authorized_user_file",
                   return_value=mock_creds) as mock_load, \
             patch("youtube.uploader.InstalledAppFlow.from_client_secrets_file") as mock_flow:
            from youtube.uploader import _get_credentials
            result = _get_credentials(str(tmp_path / "creds.json"), str(token_file))

        mock_flow.return_value.run_local_server.assert_not_called()
        assert result is mock_creds

    def test_refreshes_expired_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        token_file.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "tok"

        with patch("youtube.uploader.Credentials.from_authorized_user_file",
                   return_value=mock_creds), \
             patch("youtube.uploader.Request") as mock_req, \
             patch("youtube.uploader.InstalledAppFlow.from_client_secrets_file") as mock_flow:
            mock_creds.to_json.return_value = "{}"
            from youtube.uploader import _get_credentials
            _get_credentials(str(tmp_path / "creds.json"), str(token_file))

        mock_creds.refresh.assert_called_once()
        mock_flow.return_value.run_local_server.assert_not_called()

    def test_browser_flow_when_no_token(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        token_file = tmp_path / "token.json"
        # token_file does NOT exist

        mock_new_creds = MagicMock()
        mock_new_creds.to_json.return_value = '{"token": "new"}'

        with patch("youtube.uploader.Credentials.from_authorized_user_file") as mock_load, \
             patch("youtube.uploader.InstalledAppFlow.from_client_secrets_file") as mock_flow:
            mock_flow.return_value.run_local_server.return_value = mock_new_creds
            from youtube.uploader import _get_credentials
            result = _get_credentials(str(creds_file), str(token_file))

        mock_flow.return_value.run_local_server.assert_called_once()
        assert result is mock_new_creds

    def test_writes_token_json_after_auth(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        token_file = tmp_path / "token.json"

        mock_new_creds = MagicMock()
        mock_new_creds.to_json.return_value = '{"access_token": "abc"}'

        with patch("youtube.uploader.Credentials.from_authorized_user_file"), \
             patch("youtube.uploader.InstalledAppFlow.from_client_secrets_file") as mock_flow:
            mock_flow.return_value.run_local_server.return_value = mock_new_creds
            from youtube.uploader import _get_credentials
            _get_credentials(str(creds_file), str(token_file))

        assert token_file.exists()
        assert "access_token" in token_file.read_text()


# ─────────────────────────────────────────────
#  upload_video
# ─────────────────────────────────────────────

def _make_fake_video(tmp_path: Path) -> Path:
    p = tmp_path / "test.mp4"
    p.write_bytes(b"fake mp4 content")
    return p


def _make_fake_thumb(tmp_path: Path) -> Path:
    p = tmp_path / "test_thumb.png"
    p.write_bytes(b"fake png content")
    return p


class TestUploadVideo:
    @pytest.fixture(autouse=True)
    def patch_media_upload(self):
        """Patch MediaFileUpload for all tests (it's None when packages not yet imported)."""
        with patch("youtube.uploader.MediaFileUpload") as m:
            m.return_value = MagicMock()
            yield m

    def _mock_youtube_client(self):
        mock_yt = MagicMock()
        # videos().insert() returns a request whose next_chunk returns (None, {"id": "abc123"})
        mock_insert_req = MagicMock()
        mock_insert_req.next_chunk.return_value = (None, {"id": "abc123"})
        mock_yt.videos.return_value.insert.return_value = mock_insert_req
        return mock_yt

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_returns_video_id_on_success(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_build.return_value = self._mock_youtube_client()

        from youtube.uploader import upload_video
        result = upload_video(
            str(video), "Test Title", "desc #Shorts",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
        )
        assert result == "abc123"

    def test_returns_none_when_no_credentials(self, tmp_path):
        video = _make_fake_video(tmp_path)
        # credentials.json does NOT exist
        from youtube.uploader import upload_video
        result = upload_video(
            str(video), "Title", "desc",
            credentials_path=str(tmp_path / "missing.json"),
            token_path=str(tmp_path / "token.json"),
        )
        assert result is None

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_returns_none_on_api_exception(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_build.side_effect = Exception("API quota exceeded")

        from youtube.uploader import upload_video
        result = upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
        )
        assert result is None  # must not propagate

    def test_returns_none_when_packages_missing(self, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in ("googleapiclient.discovery", "googleapiclient.http"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            # Need to reload to trigger ImportError
            import importlib
            import youtube.uploader as mod
            importlib.reload(mod)
            result = mod.upload_video(
                str(video), "Title", "desc",
                credentials_path=str(creds_file),
                token_path=str(tmp_path / "token.json"),
            )
        assert result is None

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_passes_correct_tags(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "#Shorts #Reddit #NTA",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
        )

        call_kwargs = mock_yt.videos.return_value.insert.call_args[1]
        tags = call_kwargs["body"]["snippet"]["tags"]
        assert "Shorts" in tags
        assert "Reddit" in tags
        assert "NTA" in tags

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_passes_correct_privacy(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
            privacy="unlisted",
        )

        call_kwargs = mock_yt.videos.return_value.insert.call_args[1]
        assert call_kwargs["body"]["status"]["privacyStatus"] == "unlisted"

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_category_id_default_is_24(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
        )

        call_kwargs = mock_yt.videos.return_value.insert.call_args[1]
        assert call_kwargs["body"]["snippet"]["categoryId"] == "24"

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_self_declared_made_for_kids_in_body(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
            made_for_kids=False,
        )

        call_kwargs = mock_yt.videos.return_value.insert.call_args[1]
        # Must use selfDeclaredMadeForKids (not madeForKids which is read-only)
        assert call_kwargs["body"]["status"]["selfDeclaredMadeForKids"] is False

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_thumbnail_uploaded_when_thumb_path(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        thumb = _make_fake_thumb(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
            thumb_path=str(thumb),
        )

        # thumbnails().set() should have been called with the video ID
        mock_yt.thumbnails.return_value.set.assert_called_once()
        call_kwargs = mock_yt.thumbnails.return_value.set.call_args[1]
        assert call_kwargs["videoId"] == "abc123"

    @patch("youtube.uploader._get_credentials")
    @patch("youtube.uploader.build")
    def test_thumbnail_skipped_when_no_thumb(self, mock_build, mock_creds, tmp_path):
        video = _make_fake_video(tmp_path)
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_yt = self._mock_youtube_client()
        mock_build.return_value = mock_yt

        from youtube.uploader import upload_video
        upload_video(
            str(video), "Title", "desc",
            credentials_path=str(creds_file),
            token_path=str(tmp_path / "token.json"),
            thumb_path=None,
        )

        mock_yt.thumbnails.return_value.set.assert_not_called()


# ─────────────────────────────────────────────
#  TestProcessPost — enabled=false guard
# ─────────────────────────────────────────────

class TestProcessPost:
    def test_upload_not_called_when_disabled(self, tmp_path):
        """process_post should not call upload_video when youtube.enabled = False."""
        # Minimal config with youtube disabled
        cfg = {
            "reddit": {"subreddit": "amitheasshole", "post_limit": 1,
                       "min_upvotes": 0, "min_comments": 0,
                       "top_comments": 0, "max_comment_length": 80, "min_comment_score": 0},
            "output": {"dir": str(tmp_path), "history_file": str(tmp_path / "hist.json")},
            "youtube": {"enabled": False},
        }

        with patch("main.upload_video") as mock_upload, \
             patch("main.TTSEngine") as MockTTS, \
             patch("main.VideoComposer") as MockComposer, \
             patch("main.MetaGenerator.save_meta", return_value=str(tmp_path / "meta.txt")), \
             patch("main.extract_verdict", return_value=None):

            mock_tts = MockTTS.return_value
            mock_tts.generate_for_post.return_value = [{"type": "title", "text": "t",
                                                         "audio_path": str(tmp_path / "a.mp3"),
                                                         "word_segments": []}]
            mock_composer = MockComposer.return_value
            mock_composer.compose_video.return_value = str(tmp_path / "video.mp4")
            mock_composer.output_dir = str(tmp_path)

            # Create a fake video file so os.path.exists check passes
            (tmp_path / "video.mp4").write_bytes(b"fake")

            # Create a fake scraper
            mock_scraper = MagicMock()

            from reddit.scraper import RedditPost
            post = RedditPost(id="x1", title="Test post", body="body text",
                              author="u", score=100, url="url", subreddit="amitheasshole")

            from main import process_post
            process_post(post, mock_tts, mock_composer, mock_scraper, cfg)

        mock_upload.assert_not_called()


# ─────────────────────────────────────────────
#  Config defaults
# ─────────────────────────────────────────────

class TestConfigDefaults:
    def test_youtube_defaults_in_load_config(self, tmp_path):
        """load_config should inject [youtube] defaults when section is absent."""
        cfg_file = tmp_path / "test_config.toml"
        cfg_file.write_text("[reddit]\nsubreddit = 'amitheasshole'\n")

        from utils.config_loader import load_config
        config = load_config(str(cfg_file))

        assert "youtube" in config
        yt = config["youtube"]
        assert yt["enabled"] is False
        assert yt["credentials_path"] == "credentials.json"
        assert yt["token_path"] == "token.json"
        assert yt["privacy"] == "public"
        assert yt["category_id"] == "24"
        assert yt["made_for_kids"] is False
        assert yt["notify_subscribers"] is True
        assert yt["upload_thumbnail"] is True

    def test_enabled_false_by_default(self, tmp_path):
        cfg_file = tmp_path / "test_config.toml"
        cfg_file.write_text("[reddit]\nsubreddit = 'amitheasshole'\n")

        from utils.config_loader import load_config
        config = load_config(str(cfg_file))
        assert config["youtube"]["enabled"] is False
