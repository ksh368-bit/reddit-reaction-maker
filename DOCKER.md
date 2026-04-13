# Docker Deployment Guide

## Quick Start

### Build the image
```bash
docker build -t reddit-shorts:latest .
```

### Run with docker-compose
```bash
# Fetch top posts from r/roblox this week
docker-compose up

# Or with custom arguments
docker compose run --rm reddit-shorts --limit 3 --time month
```

### Run standalone
```bash
# Fetch top posts
docker run -v $(pwd)/output:/app/output reddit-shorts:latest --limit 1

# Process local text file
docker run -v $(pwd):/app reddit-shorts:latest --file scripts/test.txt

# Process all text files in directory
docker run -v $(pwd):/app reddit-shorts:latest --dir scripts/
```

## Environment Variables

### Optional: Datadog Metrics
```bash
docker run \
  -e DATADOG_API_KEY=your-key-here \
  -v $(pwd)/output:/app/output \
  reddit-shorts:latest --limit 1
```

### Optional: YouTube Upload
```bash
docker run \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  reddit-shorts:latest --limit 1
```

## Configuration

### Via config.toml mount
```bash
docker run \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/output:/app/output \
  reddit-shorts:latest
```

### Via environment
Create `.env`:
```
DATADOG_API_KEY=xxx
```

Then:
```bash
docker run --env-file .env -v $(pwd)/output:/app/output reddit-shorts:latest
```

## Troubleshooting

### View logs
```bash
docker run -v $(pwd)/output:/app/output reddit-shorts:latest --limit 1 2>&1 | tail -50
```

### Interactive shell
```bash
docker run -it -v $(pwd)/output:/app/output reddit-shorts:latest /bin/bash
```

### Check image contents
```bash
docker run -it reddit-shorts:latest ls -la
```

## CI/CD Deployment

GitHub Actions automatically:
1. **Tests**: Runs on every push (test.yml)
2. **Releases**: Creates releases for tags (release.yml)
3. **Docker**: Optionally builds Docker image on release

### Manual release
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Performance Notes

- Multi-stage build reduces image size
- Python 3.11-slim base (160MB)
- FFmpeg included (~50MB)
- Total image: ~280MB
- TTS generation: 6-9s (with parallelization)
- Video composition: ~20-30s
- YouTube upload: 30-300s (depends on file size)
