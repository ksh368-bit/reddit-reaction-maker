#!/usr/bin/env bash
# YouTube OAuth 재인증 + 오늘 Steam 영상 업로드
# 실행: bash scripts/reauth_and_upload.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$PROJECT_DIR/path/to/venv/bin/python3"

cd "$PROJECT_DIR"

echo "=== YouTube 재인증 + 업로드 ==="
"$PYTHON" -c "
from youtube.uploader import upload_video

result = upload_video(
    video_path='output/steam/Which_game_is_this.mp4',
    title='🎮 Steam community: Which game is this?',
    description='''🎮 The gaming community has spoken 👇

🔥 17.5k upvotes on Reddit

Steam community reacts — Stardew Valley and Terraria.

Would you agree? Drop your take below! 👇

#Shorts #Reddit #Steam #Gaming #PCGaming #SteamDeals #PCGamer
🔔 Subscribe for daily gaming reactions''',
    privacy='public',
)
print('업로드 완료:', result)
"
