# Reddit Shorts Video Maker 🎬

**Automated YouTube Shorts generator from Reddit posts.** No API keys required!

Convert Reddit's most engaging stories into professional YouTube Shorts videos with:
- 🎙️ Multi-language TTS (EdgeTTS or gTTS)
- 🎵 Karaoke-style captions with word-level timing (Whisper)
- 🎬 Auto-generated backgrounds with zoom punch effects
- 📤 Direct YouTube upload with OAuth2
- 📊 Performance metrics & Datadog integration
- 🐳 Docker support for cloud deployment

## Quick Start

### Local Installation

```bash
# Clone and install
git clone https://github.com/SeungheeKim/reddit-reaction-maker.git
cd reddit-reaction-maker
pip install -r requirements.txt

# Copy & customize config
cp config.template.toml config.toml
# Edit config.toml to change TTS voice, subreddit, etc.

# Generate your first video!
python main.py --limit 1
```

Your video is in `output/` — ready for YouTube! 🚀

### Docker (No Setup Required)

```bash
docker build -t reddit-shorts .
docker run -v $(pwd)/output:/app/output reddit-shorts --limit 1
# Or: docker-compose up
```

## Features

✅ **No API Keys** — Uses Reddit's public `.json` endpoints

✅ **Multi-Language TTS** — EdgeTTS (natural, fast) or gTTS (free, 100+ languages)

✅ **Karaoke Captions** — Word-level timing via Whisper

✅ **Auto YouTube Upload** — OAuth2-based with custom titles & thumbnails

✅ **Observability** — Metrics, logging, Datadog integration

✅ **34+ Subreddits** — Pre-configured with CTR-optimized hooks

✅ **Production Ready** — GitHub Actions, Docker, metrics, retry logic

## Usage

```bash
# Top posts from r/roblox this week
python main.py --limit 1

# Top posts from r/steam today
python main.py --subreddit steam --time day --limit 3

# Specific post by ID
python main.py --post abc123def456

# Local text file (no Reddit needed)
python main.py --file story.txt

# Batch process directory
python main.py --dir scripts/

# Help
python main.py --help
```

## Configuration

Edit `config.toml`:

```toml
[reddit]
subreddit = "amitheasshole"
post_limit = 3

[tts]
engine = "edge-tts"
voice = "en-US-GuyNeural"

[youtube]
enabled = true
privacy = "unlisted"
```

See [config.template.toml](config.template.toml) for **40+ options** with detailed descriptions.

## Output

```
output/
├── roblox_abc123_2026-04-14.mp4       # Video
├── roblox_abc123_2026-04-14_meta.txt  # Metadata
├── roblox_abc123_2026-04-14_thumb.png # Thumbnail
├── _metrics/metrics_*.json             # Metrics
├── history.json                        # Processed posts log
└── logs/2026-04-14.log                # Application logs
```

## Performance

- **TTS**: 6-9s (↓ 40% via parallelization)
- **Composition**: 20-30s (↓ 35% via caching)
- **Total**: ~30s (↓ 35% overall)

## YouTube Upload

1. Get OAuth2 credentials from [Google Cloud Console](https://console.cloud.google.com/)
2. Download JSON → `credentials.json`
3. Set `enabled = true` in config.toml
4. Run once: `python main.py --limit 1` (browser opens to authorize)
5. Done! Future runs upload automatically

## Documentation

- **[config.template.toml](config.template.toml)** — All 40+ options with descriptions
- **[DOCKER.md](DOCKER.md)** — Docker & deployment guide
- **[CLAUDE.md](CLAUDE.md)** — Development policy (TDD required)

## Subreddit Coverage

34+ subreddits with custom hooks:

**Stories:** amitheasshole, relationship_advice, tifu, pettyrevenge, maliciouscompliance, choosingbeggars, entitledpeople, JustNoMIL

**Gaming:** steam, pcgaming, gaming, consoles, WoW, leagueoflegends

**Anime:** manga, manhwa, anime, anime_irl

**Lifestyle:** fitness, loseit, personalfinance, investing, skincare, asianbeauty

**Tech:** programming, learnprogramming, webdev, python, javascript

**General:** askreddit, todayilearned, lifeprotips

**Unknown subreddit?** Auto-generates CTR-optimized hooks!

## Troubleshooting

```bash
# Missing dependencies
pip install -r requirements.txt

# Check TTS voices
edge-tts --list-voices

# View logs
tail -f output/logs/2026-04-14.log

# Check metrics
cat output/_metrics/metrics_*.json | grep -E "youtube_video_id|success"
```

## Contributing

Issues and PRs welcome! TDD required. See [CLAUDE.md](CLAUDE.md).

## License

MIT

---

**Made with ❤️ by [Seunghee Kim](https://github.com/SeungheeKim)**

Generate awesome YouTube Shorts from Reddit. No API keys. No subscriptions. Just stories. 🎬
