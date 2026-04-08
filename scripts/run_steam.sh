#!/usr/bin/env bash
# Daily automation script: generate 2 Steam channel videos
# Scheduled via cron: 0 17 * * * .../scripts/run_steam.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$PROJECT_DIR/path/to/venv/bin/python3"
LOG_DIR="$PROJECT_DIR/output/steam/logs"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

{
    echo "=== Steam channel run: $(date '+%Y-%m-%d %H:%M:%S') ==="
    cd "$PROJECT_DIR"
    "$PYTHON" main.py --config config-steam.toml --limit 2
    echo "=== Done: $(date '+%Y-%m-%d %H:%M:%S') ==="
} >> "$LOG_FILE" 2>&1
