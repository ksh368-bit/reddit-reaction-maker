#!/usr/bin/env bash
# Cleanup output files older than 14 days
# Scheduled via cron: 0 3 * * * .../scripts/cleanup_old_outputs.sh
#
# Deletes per-video files (.mp4, .mp3, _thumb.png, _meta.txt) older than KEEP_DAYS.
# Logs are kept for 30 days. history.json is never deleted.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/output"
LOG_DIR="$OUTPUT_DIR/logs"
DATE="$(date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/cleanup_${DATE}.log"
KEEP_DAYS=14
LOG_KEEP_DAYS=30

mkdir -p "$LOG_DIR"

{
    echo "=========================================="
    echo "Cleanup run: $DATE $(date '+%H:%M:%S')"
    echo "Removing output files older than ${KEEP_DAYS} days"
    echo "=========================================="

    # Count and delete old video/audio/thumbnail/meta files
    deleted=0
    freed=0

    while IFS= read -r -d '' file; do
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        echo "  DEL $file ($(( size / 1024 / 1024 ))MB)"
        rm -f "$file"
        (( deleted++ )) || true
        (( freed += size )) || true
    done < <(find "$OUTPUT_DIR" \
        -not -path "$LOG_DIR/*" \
        \( -name "*.mp4" -o -name "*.mp3" -o -name "*_thumb.png" -o -name "*_meta.txt" \) \
        -mtime +${KEEP_DAYS} \
        -print0)

    freed_mb=$(( freed / 1024 / 1024 ))
    echo ""
    echo "Deleted: ${deleted} file(s), freed: ${freed_mb}MB"

    # Prune old log files (keep 30 days)
    old_logs=$(find "$LOG_DIR" -name "*.log" -mtime +${LOG_KEEP_DAYS} | wc -l | tr -d ' ')
    if [ "$old_logs" -gt 0 ]; then
        find "$LOG_DIR" -name "*.log" -mtime +${LOG_KEEP_DAYS} -delete
        echo "Pruned: ${old_logs} old log file(s)"
    fi

    echo "=========================================="
    echo "Done: $(date '+%H:%M:%S')"
    echo "=========================================="
} 2>&1 | tee -a "$LOG_FILE"
