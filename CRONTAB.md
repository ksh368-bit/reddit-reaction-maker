# Crontab Automation Guide

**Generate YouTube Shorts automatically on a schedule** using `crontab` in Linux/Unix environments.

## Quick Start

### 1. Verify crontab compatibility

The project is designed for crontab with:
- ✅ Automatic path resolution (absolute paths)
- ✅ File locking to prevent concurrent execution conflicts
- ✅ Comprehensive error logging to `output/logs/`
- ✅ Exit codes for monitoring (0=success, 1=error, 130=interrupted)

### 2. Set up crontab entry

```bash
# Edit crontab
crontab -e

# Add this line (runs every day at 8 AM):
0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1 >> /tmp/reddit-shorts.log 2>&1
```

**Key points:**
- Use **absolute paths** (`/path/to/reddit-reaction-maker`, not `~/`, not relative)
- Use **full path to Python** (`/usr/bin/python3`, not `python3`)
- Redirect output to log file (crontab doesn't capture stdout/stderr by default)

### 3. Verify it works

```bash
# Check crontab entry
crontab -l

# View detailed logs in project
tail -f output/logs/$(date +%Y-%m-%d).log

# View cron execution log (Linux/macOS)
log stream --predicate 'eventMessage contains[cd] "reddit-shorts"' --level debug
```

---

## Configuration for Crontab

All paths in `config.toml` are automatically resolved to absolute paths when the script runs.
You can use relative or absolute paths in the config—both work.

### Recommended crontab `config.toml` settings

```toml
[reddit]
subreddit = "roblox"
post_limit = 1
min_upvotes = 100

[tts]
engine = "edge-tts"
voice = "en-US-GuyNeural"

[video]
width = 1080
height = 1920
max_duration = 58

[output]
# Optional: use absolute paths for crontab clarity
dir = "/home/user/reddit-shorts/output"
history_file = "/home/user/reddit-shorts/output/history.json"

[logging]
level = "INFO"  # Use INFO for production crontab (not DEBUG—too verbose)
log_dir = "/home/user/reddit-shorts/output/logs"

[youtube]
enabled = true
credentials_path = "/home/user/reddit-shorts/credentials.json"
token_path = "/home/user/reddit-shorts/token.json"
privacy = "unlisted"
```

---

## Crontab Schedule Examples

```bash
# Run every day at 8 AM
0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1

# Run every 6 hours
0 */6 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1

# Run twice a day (8 AM and 8 PM)
0 8,20 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1

# Run every weekday at 10 AM (Mon-Fri)
0 10 * * 1-5 cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1

# Run on Sunday at 3 PM
0 15 * * 0 cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1
```

**Crontab format:** `minute hour day month weekday command`
- `*` = any
- `0` = first of range (00:00 in 24-hour format)
- `,` = multiple values (8,20 = 8 AM and 8 PM)
- `/` = interval (*/6 = every 6)
- `-` = range (1-5 = Monday-Friday)

---

## Error Monitoring & Notifications

### Option 1: Email Alerts (Recommended)

Crontab can email error output automatically:

```bash
# At the top of your crontab:
MAILTO=your-email@example.com

# Your crontab entries will email on error
0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1
```

### Option 2: Log File Monitoring

Check logs for errors:

```bash
# View today's log
tail -100 output/logs/$(date +%Y-%m-%d).log

# Watch logs in real-time
tail -f output/logs/$(date +%Y-%m-%d).log

# Check for ERROR or EXCEPTION entries
grep -E "ERROR|EXCEPTION" output/logs/$(date +%Y-%m-%d).log
```

### Option 3: Datadog Integration

If you have Datadog set up:

```bash
# Set API key in environment
export DATADOG_API_KEY="your-api-key"

# Metrics automatically export to Datadog when script runs
# Check metrics in: output/_metrics/metrics_*.json
```

### Option 4: Custom Monitoring Script

Create `scripts/check-cron-health.sh`:

```bash
#!/bin/bash

LOG_DIR="/path/to/reddit-reaction-maker/output/logs"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/$TODAY.log"

# Check if today's log has errors
if grep -q "ERROR" "$LOG_FILE"; then
    echo "ALERT: Errors found in cron run on $TODAY"
    tail -20 "$LOG_FILE" | mail -s "Reddit Shorts Cron Error" your-email@example.com
fi
```

Then add to crontab:

```bash
# Run monitoring script every hour
0 * * * * /path/to/reddit-reaction-maker/scripts/check-cron-health.sh
```

---

## Concurrent Execution Protection

The project uses **file locking** to prevent conflicts when multiple crontab instances run simultaneously:

- Lock file: `.history.lock` in output directory
- Timeout: 10 seconds (gives other instances time to finish)
- Automatic cleanup on exit

**Example scenario:**
- 8 AM cron starts generating video 1
- 8:05 AM cron checks history (locks prevent conflict)
- Both complete successfully without corrupting `history.json`

---

## Environment Variables

Set environment variables in crontab to override config:

```bash
# In your crontab:
REDDIT_SUBREDDIT=steam
TTS_VOICE=en-US-AriaNeural
YOUTUBE_ENABLED=true

# Then your command:
0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1
```

### Common environment variables:

- `REDDIT_SUBREDDIT` — Override subreddit (e.g., `steam`, `askreddit`)
- `TTS_VOICE` — Override TTS voice
- `TTS_ENGINE` — Override TTS engine (`edge-tts`, `gtts`)
- `YOUTUBE_ENABLED` — Enable/disable YouTube upload (`true`, `false`)
- `DATADOG_API_KEY` — Datadog API key for metrics export
- `LOG_LEVEL` — Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

---

## Troubleshooting Crontab Issues

### Problem: "Command not found"

**Cause:** Using relative path instead of absolute, or `python3` not found

**Solution:**
```bash
# Find absolute path to Python
which python3
# Output: /usr/bin/python3

# Use full path in crontab:
0 8 * * * cd /home/user/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1
```

### Problem: "No config.toml found"

**Cause:** `cd` command failed, or working directory not set

**Solution:**
```bash
# Always include `cd` before running:
0 8 * * * cd /home/user/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1

# Or use full paths in command:
0 8 * * * /usr/bin/python3 /home/user/reddit-reaction-maker/main.py --limit 1
```

### Problem: "output directory not found"

**Cause:** output/ directory not created

**Solution:**
```bash
# Create output directory manually once:
mkdir -p /path/to/reddit-reaction-maker/output/logs

# Or use config with absolute path:
# In config.toml: dir = "/home/user/reddit-shorts/output"
```

### Problem: No videos generated, but no errors

**Cause:** Likely no posts matching filters, or Reddit API timeout

**Check logs:**
```bash
# View detailed logs
tail -50 output/logs/$(date +%Y-%m-%d).log

# Check metrics to see what happened
cat output/_metrics/metrics_*.json | grep -E "segments_count|success"
```

### Problem: "YAML error" or "config error"

**Cause:** Invalid `config.toml` syntax

**Solution:**
```bash
# Validate config manually:
python3 -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"
# If no error, config is valid

# Common mistakes in TOML:
# - Quotes: strings need quotes ("value", not value)
# - Booleans: true/false (not True/False)
# - Numbers: 0.5 (not 0,5 in non-US locale)
```

### Problem: YouTube upload fails in crontab

**Cause:** `credentials.json` or `token.json` path not found

**Solution:**
```bash
# Verify credentials exist:
ls -la /home/user/reddit-reaction-maker/credentials.json

# If missing, generate once manually:
python3 main.py --limit 1  # Browser opens to authorize
# Then credentials.json is created

# Use absolute path in config.toml:
credentials_path = "/home/user/reddit-reaction-maker/credentials.json"
```

---

## Docker Alternative (No Crontab Setup Needed)

If crontab is too complex, use Docker:

```bash
# Build image once
docker build -t reddit-shorts .

# Run in background (alternative to crontab)
docker run -d \
  --restart on-failure \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/config.toml:/app/config.toml \
  -e YOUTUBE_ENABLED=true \
  reddit-shorts --limit 1
```

Or use `docker-compose` for regular scheduled runs.

---

## Performance Tips for Crontab

1. **Use `--limit 1`** for daily runs
   - Generates 1 video per day = predictable resource usage
   - Change to `--limit 2` or `--limit 3` for multiple videos

2. **Schedule during off-peak hours**
   - 8 AM or midnight is good
   - Avoid peak hours (noon, evening)
   - Consider YouTube API quota limits

3. **Monitor CPU/memory:**
   ```bash
   # Check resource usage during cron run
   top -o %CPU | head -20
   
   # Video generation is CPU-intensive (peak: 50-70% single core)
   # TTS is parallelized (2-4 cores used)
   ```

4. **Set realistic intervals:**
   - Daily: `0 8 * * *` (safe, sustainable)
   - Multiple per day: `0 8,20 * * *` (OK with powerful server)
   - Hourly: `0 * * * *` (risky, may hit YouTube API limits)

---

## Security Notes

1. **Keep `credentials.json` secure**
   ```bash
   # Set restrictive permissions
   chmod 600 credentials.json
   ```

2. **Use environment variables for secrets**
   ```bash
   # Don't put API keys in crontab file directly
   # Instead, use .env file and source it:
   DATADOG_API_KEY=xxx python3 main.py
   ```

3. **Monitor log files for sensitive data**
   ```bash
   # Logs may contain post content—keep secure
   chmod 640 output/logs/*.log
   ```

---

## Reference: Crontab Exit Codes

The script returns standard Unix exit codes:

- `0` — Success (no errors, videos may or may not be generated)
- `1` — Error (check logs for details)
- `130` — Interrupted by user (SIGINT)

Use exit codes for monitoring:

```bash
# Send alert only on failure
0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1 || mail -s "Cron failed" email@example.com
```

---

## Testing Before Adding to Crontab

Always test manually first:

```bash
# 1. Test Python + environment
python3 --version

# 2. Test from project directory
cd /path/to/reddit-reaction-maker
python3 main.py --limit 1

# 3. Check output
ls -la output/
cat output/logs/$(date +%Y-%m-%d).log

# 4. If successful, add to crontab
crontab -e
# Add: 0 8 * * * cd /path/to/reddit-reaction-maker && /usr/bin/python3 main.py --limit 1
```

---

## Next Steps

1. ✅ Copy `config.template.toml` to `config.toml`
2. ✅ Customize `config.toml` with your settings
3. ✅ Test manually: `python3 main.py --limit 1`
4. ✅ Find Python path: `which python3`
5. ✅ Find project path: `pwd`
6. ✅ Add to crontab: `crontab -e`
7. ✅ Monitor first run: `tail -f output/logs/$(date +%Y-%m-%d).log`

Happy automating! 🚀
