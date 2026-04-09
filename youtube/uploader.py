"""YouTube Data API v3 uploader for Reddit Shorts pipeline."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# youtube scope (not youtube.upload) — required for thumbnails.set()
SCOPES = ["https://www.googleapis.com/auth/youtube"]

# Auth imports at module level so tests can patch them
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    Credentials = None  # type: ignore[assignment,misc]
    Request = None      # type: ignore[assignment]
    InstalledAppFlow = None  # type: ignore[assignment]

# API imports at module level so @patch("youtube.uploader.build") works in tests
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    build = None          # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]


def _get_credentials(credentials_path: str, token_path: str):
    """Return valid OAuth2 credentials, refreshing or re-authing as needed."""
    creds = None
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(token_path).write_text(creds.to_json())

    return creds


def _parse_tags_from_description(description: str) -> list[str]:
    """Extract hashtag words from description, e.g. '#Shorts' → 'Shorts'."""
    return re.findall(r"#(\w+)", description)


def upload_video(
    video_path: str,
    title: str,
    description: str,
    *,
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
    privacy: str = "public",
    category_id: str = "24",
    made_for_kids: bool = False,
    notify_subscribers: bool = True,
    thumb_path: str | None = None,
) -> str | None:
    """
    Upload video_path to YouTube. Returns the video ID on success, None on failure.
    Never raises — all exceptions are caught and logged.
    """
    try:
        if build is None:
            logger.error(
                "google-api-python-client not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
            return None

        if not Path(credentials_path).exists():
            logger.error(
                "credentials.json not found at %s. See YouTube upload setup instructions.",
                credentials_path,
            )
            return None

        creds = _get_credentials(credentials_path, token_path)
        youtube = build("youtube", "v3", credentials=creds)

        tags = _parse_tags_from_description(description)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        media = MediaFileUpload(
            video_path, chunksize=-1, resumable=True, mimetype="video/mp4"
        )
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id: str = response["id"]
        logger.info("Uploaded: https://www.youtube.com/shorts/%s", video_id)

        # Upload thumbnail if provided
        if thumb_path and Path(thumb_path).exists():
            try:
                thumb_media = MediaFileUpload(thumb_path, mimetype="image/png")
                youtube.thumbnails().set(
                    videoId=video_id, media_body=thumb_media
                ).execute()
                logger.info("Thumbnail uploaded for video %s", video_id)
            except Exception as thumb_exc:
                logger.warning("Thumbnail upload failed (video still uploaded): %s", thumb_exc)

        return video_id

    except Exception as exc:  # noqa: BLE001
        logger.error("YouTube upload failed: %s", exc)
        return None
