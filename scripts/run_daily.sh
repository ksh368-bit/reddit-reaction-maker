#!/usr/bin/env bash
# Daily automation: generate 2 videos per channel across all configs
# Scheduled via cron: 0 17 * * * .../scripts/run_daily.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$PROJECT_DIR/path/to/venv/bin/python3"
LOG_DIR="$PROJECT_DIR/output/logs"
DATE="$(date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/daily_${DATE}.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

OVERALL_EXIT=0

run_channel() {
    local config="$1"
    local label="$2"
    echo ""
    echo "=== [$label] start: $(date '+%H:%M:%S') ==="
    if "$PYTHON" main.py --config "$config" --limit 1; then
        echo "=== [$label] done ==="
    else
        echo "=== [$label] FAILED (exit $?) ==="
        OVERALL_EXIT=1
    fi
}

{
    echo "=========================================="
    echo "Daily run: $DATE $(date '+%H:%M:%S')"
    echo "=========================================="

    run_channel "config.toml"          "AITA/Reddit"
    run_channel "config-steam.toml"    "Steam"
    run_channel "config-manga.toml"    "Manga"
    run_channel "config-products.toml" "Products"

    echo ""
    echo "=========================================="
    echo "All channels done: $(date '+%H:%M:%S')"
    echo "=========================================="
} 2>&1 | tee -a "$LOG_FILE"

exit $OVERALL_EXIT
