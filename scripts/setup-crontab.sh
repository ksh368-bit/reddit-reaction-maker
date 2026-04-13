#!/bin/bash
#
# Setup crontab automation for Reddit Shorts Video Maker
#
# Usage:
#   ./scripts/setup-crontab.sh                    # Interactive setup
#   ./scripts/setup-crontab.sh --hour 8 --limit 1  # Non-interactive (8 AM, 1 video)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
HOUR=8
LIMIT=1
WEEKDAY="*"  # Every day
EMAIL=""

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_CMD="/usr/bin/python3"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hour)
            HOUR="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --weekday)
            WEEKDAY="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --python)
            PYTHON_CMD="$2"
            shift 2
            ;;
        --help)
            echo "Setup crontab automation for Reddit Shorts Video Maker"
            echo ""
            echo "Usage: ./scripts/setup-crontab.sh [options]"
            echo ""
            echo "Options:"
            echo "  --hour HOUR       Hour to run (0-23, default: 8)"
            echo "  --limit LIMIT     Videos per run (default: 1)"
            echo "  --weekday DAYS    Crontab weekday spec (default: * = every day)"
            echo "                    Examples: 1-5 (Mon-Fri), 0 (Sunday only), * (every day)"
            echo "  --email EMAIL     Email for error notifications"
            echo "  --python PYTHON   Path to Python 3 (default: /usr/bin/python3)"
            echo "  --help            Show this help"
            echo ""
            echo "Examples:"
            echo "  ./scripts/setup-crontab.sh                          # Interactive"
            echo "  ./scripts/setup-crontab.sh --hour 8 --limit 1       # 8 AM daily, 1 video"
            echo "  ./scripts/setup-crontab.sh --weekday 1-5 --hour 10  # Mon-Fri at 10 AM"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Interactive mode if no arguments
if [[ $# -eq 0 ]]; then
    echo -e "${BLUE}=== Reddit Shorts Video Maker - Crontab Setup ===${NC}\n"

    # Hour
    read -p "What hour to run? (0-23, default 8): " HOUR_INPUT
    HOUR=${HOUR_INPUT:-8}

    # Limit
    read -p "Videos per run? (default 1): " LIMIT_INPUT
    LIMIT=${LIMIT_INPUT:-1}

    # Weekday
    echo ""
    echo "Which days? (crontab format)"
    echo "  * = every day (default)"
    echo "  1-5 = Mon-Fri"
    echo "  0 = Sunday only"
    read -p "Days (default *): " WEEKDAY_INPUT
    WEEKDAY=${WEEKDAY_INPUT:-*}

    # Email
    read -p "Email for error notifications (optional): " EMAIL
fi

# Validate hour
if ! [[ "$HOUR" =~ ^[0-9]+$ ]] || [ "$HOUR" -lt 0 ] || [ "$HOUR" -gt 23 ]; then
    echo -e "${RED}Error: Hour must be 0-23${NC}"
    exit 1
fi

# Validate limit
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [ "$LIMIT" -lt 1 ]; then
    echo -e "${RED}Error: Limit must be >= 1${NC}"
    exit 1
fi

# Verify Python exists
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    echo -e "${RED}Error: Python not found at $PYTHON_CMD${NC}"
    echo "Try: --python /path/to/python3"
    exit 1
fi

# Verify project directory
if [ ! -f "$PROJECT_ROOT/main.py" ]; then
    echo -e "${RED}Error: main.py not found in $PROJECT_ROOT${NC}"
    exit 1
fi

# Verify config exists
if [ ! -f "$PROJECT_ROOT/config.toml" ]; then
    echo -e "${YELLOW}Warning: config.toml not found. Using default settings.${NC}"
    if [ ! -f "$PROJECT_ROOT/config.template.toml" ]; then
        echo -e "${RED}Error: config.template.toml not found${NC}"
        exit 1
    fi
    echo "Creating config.toml from template..."
    cp "$PROJECT_ROOT/config.template.toml" "$PROJECT_ROOT/config.toml"
fi

# Create crontab entry
CRON_MINUTE="0"
CRON_HOUR="$HOUR"
CRON_DAY="*"
CRON_MONTH="*"
CRON_WEEKDAY="$WEEKDAY"

CRON_COMMAND="cd $PROJECT_ROOT && $PYTHON_CMD main.py --limit $LIMIT"

# Add MAILTO if email provided
if [ -n "$EMAIL" ]; then
    CRON_HEADER="MAILTO=$EMAIL"
else
    CRON_HEADER=""
fi

# Show what we're going to add
echo ""
echo -e "${BLUE}=== Crontab Entry Preview ===${NC}"
echo ""
if [ -n "$CRON_HEADER" ]; then
    echo "$CRON_HEADER"
fi
echo "$CRON_MINUTE $CRON_HOUR $CRON_DAY $CRON_MONTH $CRON_WEEKDAY $CRON_COMMAND"
echo ""

# Show schedule explanation
echo -e "${BLUE}=== Schedule ===${NC}"
if [ "$CRON_WEEKDAY" = "*" ]; then
    echo "Frequency: Every day"
else
    echo "Frequency: Weekday spec: $CRON_WEEKDAY"
fi
echo "Time: $(printf "%02d:00" "$HOUR")"
echo "Command: $PYTHON_CMD main.py --limit $LIMIT"
echo "Project: $PROJECT_ROOT"
echo ""

# Confirmation
read -p "Add this to crontab? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

# Create temporary crontab file
TMP_CRONTAB=$(mktemp)
trap "rm -f $TMP_CRONTAB" EXIT

# Get current crontab (if any) and add new entry
{
    # Export current crontab (ignore "no crontab for user" error)
    crontab -l 2>/dev/null || true

    # Add blank line if not empty
    if [ -s "$TMP_CRONTAB" ]; then
        echo ""
    fi

    # Add header if email specified
    if [ -n "$EMAIL" ]; then
        echo "MAILTO=$EMAIL"
    fi

    # Add new entry
    echo "$CRON_MINUTE $CRON_HOUR $CRON_DAY $CRON_MONTH $CRON_WEEKDAY $CRON_COMMAND"
} > "$TMP_CRONTAB"

# Install new crontab
crontab "$TMP_CRONTAB"

echo -e "${GREEN}✓ Crontab updated successfully!${NC}"
echo ""
echo -e "${BLUE}=== Next Steps ===${NC}"
echo "1. Verify: crontab -l"
echo "2. Check logs: tail -f $PROJECT_ROOT/output/logs/\$(date +%Y-%m-%d).log"
echo "3. First run at $(printf "%02d:00" "$HOUR")"
echo ""
echo "For more details, see: $PROJECT_ROOT/CRONTAB.md"
