# Auto Video Agent

AI-powered CLI tool that generates short-form marketing videos (30–60s) for auto repair shops. Goes from a video idea to a ready-to-post Reel in under 2 minutes.

**Platforms:** Facebook Reels, Instagram Reels, TikTok
**Output:** 1080x1920 MP4, H.264 + AAC

## Quick Start

```bash
# Install (editable mode for development)
pip install -e .

# Install FFmpeg (Ubuntu/WSL)
sudo apt install ffmpeg

# Copy and fill in your API key (optional — preview mode works without it)
cp .env.example .env

# Preview a video (no API key needed)
auto-video-agent preview templates/brake_shaking.yaml

# Full AI-powered generation
auto-video-agent generate templates/brake_shaking.yaml

# Alternative: run as a Python module
python -m auto_video_agent preview templates/brake_shaking.yaml
```

## Commands

| Command | Description |
|---|---|
| `generate <plan.yaml>` | Full pipeline — AI script + voiceover + video |
| `preview <plan.yaml>` | Quick render using plan text directly (no API) |
| `batch <dir or files>` | Process multiple plans at once |
| `interactive` | Guided prompts to build a plan and generate |
| `new-plan "Title"` | Scaffold a new YAML template |
| `validate <plan.yaml>` | Check a plan file without generating |

## CLI Flags

| Flag | Commands | Description |
|---|---|---|
| `--verbose` / `-v` | All | Enable debug logging |
| `--quiet` / `-q` | All | Only show warnings and errors |
| `--output` / `-o` | generate, preview | Custom output file path |
| `--dry-run` | generate, preview | Run script + voiceover, skip FFmpeg assembly |
| `--no-api` | batch | Use plan text directly (no Claude API) |
| `--project-root` | generate, preview, batch | Override project root path |

## How It Works

1. **Script** — Claude AI writes a timed script with hook, body, and CTA
2. **Voiceover** — Edge TTS generates natural speech with word-level timestamps
3. **Captions** — Styled text overlays synced to each word
4. **Music** — Background track auto-ducked under the voice
5. **Branding** — Logo watermark, intro card, outro CTA card
6. **Assembly** — FFmpeg composites everything into a 9:16 MP4

## Video Plan Format

```yaml
title: "Why Your Car Shakes When Braking"
type: educational_tip        # educational_tip | before_after | common_mistake | promo
tone: friendly               # friendly | authoritative | urgent | humorous
hook: "Your car shakes when you hit the brakes? Here's what's really going on."
key_points:
  - "Warped brake rotors are the #1 cause"
  - "This happens from heat buildup over time"
  - "Resurfacing or replacing rotors fixes it"
call_to_action: "Book your brake inspection today — link in bio."
music: upbeat                # upbeat | chill | dramatic | none
duration_target: 45
include_captions: true
include_logo: true
```

## Configuration

All settings are in `config.yaml`:

- **`ai.model`** — Claude model for script generation (default: `claude-sonnet-4-20250514`)
- **`video.*`** — Resolution, FPS, codec settings
- **`branding.*`** — Logo, colors, positioning
- **`captions.*`** — Font, style, caption appearance
- **`voiceover.*`** — TTS provider, voice, speed
- **`music.*`** — Volume, fade settings
- **`output.*`** — Output directory, file size limits

## Project Structure

```
auto_video_agent/
├── cli.py           # CLI commands and pipeline orchestration
├── planner.py       # YAML plan parser & validator
├── scriptwriter.py  # Claude API script generation (with retry)
├── voiceover.py     # Edge TTS with word timestamps
├── captions.py      # Styled caption rendering (Pillow)
├── compositor.py    # FFmpeg video assembly
├── assets.py        # Clip validation & scaling
├── music.py         # Background music generation
├── branding.py      # Logo, intro, and outro cards
├── exporter.py      # Output validation
└── utils.py         # Shared helpers (colors, fonts, config)

assets/
├── clips/           # Your video clips (optional)
├── music/           # Custom background tracks (optional)
├── logo/            # Your shop logo
└── fonts/           # Custom fonts

templates/           # Video plan YAML files
tests/               # Test suite
```

## Requirements

- Python 3.11+
- FFmpeg
- Anthropic API key (optional for preview mode)

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run with debug logging
auto-video-agent -v generate templates/brake_shaking.yaml
```

## Use Case

See [USE_CASE.md](USE_CASE.md) for a detailed walkthrough of how an auto repair shop uses this tool to produce a full week of social media content in under 10 minutes.

## License

MIT
