#!/usr/bin/env bash
# Weekly background video URL health check + auto-repair
# Scheduled via cron: 0 9 * * 1 (every Monday 09:00)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$PROJECT_DIR/path/to/venv/bin/python3"
LOG_DIR="$PROJECT_DIR/output/logs"
LOG_FILE="$LOG_DIR/url_health_$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

{
    echo "=== URL health check: $(date '+%Y-%m-%d %H:%M:%S') ==="
    cd "$PROJECT_DIR"
    "$PYTHON" -m video.url_validator --json assets/background_videos.json
    EXIT_CODE=$?
    echo "=== Exit: $EXIT_CODE at $(date '+%Y-%m-%d %H:%M:%S') ==="
    exit $EXIT_CODE
} 2>&1 | tee -a "$LOG_FILE"
