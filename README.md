# 31 Days of Vibe Coding - Podcast Generator

Convert the [31 Days of Vibe Coding](https://31daysofvibecoding.com/) article series into podcast episodes you can listen to anywhere.

## Features

- **Multiple TTS Engines**: Choose between ElevenLabs (high quality, paid), Piper (good quality, free/local), or macOS built-in TTS
- **Smart Content Processing**: Code blocks are summarized for audio (nobody wants to hear curly braces read aloud)
- **Cached Processing**: Scrape once, generate audio anytime
- **Progress Tracking**: Character counts, estimated costs, and generation stats

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd 31Days
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate all episodes with Piper (free, local)
python main.py --engine piper --from-cache
```

## Installation

### Prerequisites

- Python 3.9+ (tested with 3.13)
- For Piper TTS: `espeak-ng` and `ffmpeg`
- For ElevenLabs: API key

### Step 1: Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Install System Dependencies (for Piper)

**macOS:**

```bash
brew install espeak-ng ffmpeg
```

**Ubuntu/Debian:**

```bash
sudo apt install espeak-ng ffmpeg
```

**Windows:**

- Download espeak-ng from [GitHub releases](https://github.com/espeak-ng/espeak-ng/releases)
- Download ffmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)

### Step 4: Configure ElevenLabs (Optional)

If you want to use ElevenLabs for higher quality audio:

```bash
cp .env.example .env
# Edit .env and add your API key
```

## Usage

### TTS Engine Options

| Engine     | Flag                  | Quality   | Cost                 | Requirements      |
| ---------- | --------------------- | --------- | -------------------- | ----------------- |
| ElevenLabs | `--engine elevenlabs` | Excellent | ~$53 for all 31 days | API key           |
| Piper      | `--engine piper`      | Good      | Free                 | espeak-ng, ffmpeg |
| macOS      | `--engine macos`      | Decent    | Free                 | macOS only        |

### Generate All Episodes

```bash
# Using Piper (recommended for free generation)
python main.py --engine piper --from-cache

# Using ElevenLabs (requires API key)
python main.py --engine elevenlabs --from-cache

# Using macOS built-in TTS
python main.py --engine macos --from-cache
```

### Generate Specific Days

```bash
# Generate only Day 1
python main.py --engine piper --from-cache --day 1

# Generate Days 1-5 by running multiple times
for i in {1..5}; do
  python main.py --engine piper --from-cache --day $i
done
```

### Test Mode

```bash
# Process only first 2 articles (for testing)
python main.py --engine piper --test
```

### Choose a Voice

```bash
# List available voices for an engine
python main.py --engine piper --list-voices
python main.py --engine elevenlabs --list-voices
python main.py --engine macos --list-voices

# Use a specific voice
python main.py --engine piper --voice ryan --from-cache
python main.py --engine elevenlabs --voice josh --from-cache
python main.py --engine macos --voice alex --from-cache
```

### Scrape Fresh Content

```bash
# Re-scrape all articles (if content has been updated)
python main.py --engine piper

# Scrape only, don't generate audio
python main.py --scrape-only
```

## Available Voices

### Piper Voices

| Voice         | Description                       |
| ------------- | --------------------------------- |
| `amy`         | US English, female (default)      |
| `arctic`      | US English, multiple speakers     |
| `lessac`      | US English, neutral               |
| `lessac-high` | US English, neutral, high quality |
| `ryan`        | US English, male                  |
| `ryan-high`   | US English, male, high quality    |
| `kristin`     | US English, female                |
| `libritts`    | US English, LibriTTS trained      |
| `ljspeech`    | US English, LJSpeech trained      |
| `danny`       | British English, male             |

### ElevenLabs Voices

| Voice    | Description                     |
| -------- | ------------------------------- |
| `rachel` | American female, calm (default) |
| `bella`  | American female, soft           |
| `antoni` | American male                   |
| `josh`   | American male, deep             |
| `arnold` | American male, crisp            |
| `adam`   | American male, deep             |
| `sam`    | American male, raspy            |

### macOS Voices

| Voice      | Description                  |
| ---------- | ---------------------------- |
| `samantha` | US English, female (default) |
| `alex`     | US English, male             |
| `tom`      | US English, male             |
| `karen`    | Australian English, female   |
| `daniel`   | British English, male        |

_Run `--list-voices` for the complete list on your system._

## Project Structure

```
31Days/
├── main.py              # Main entry point
├── scraper.py           # Web scraper for articles
├── processor.py         # HTML to audio-friendly text
├── audio_generator.py   # ElevenLabs integration
├── piper_generator.py   # Piper TTS integration
├── macos_generator.py   # macOS TTS integration
├── requirements.txt     # Python dependencies
├── .env.example         # API key template
├── .gitignore
├── README.md            # Development journey writeup
├── models/
│   └── piper/           # Downloaded Piper voice models
└── output/
    ├── text/            # Processed article text (cached)
    │   ├── day_01.txt
    │   ├── day_02.txt
    │   └── ...
    └── audio/           # Generated MP3 files
        ├── day_01.mp3
        ├── day_02.mp3
        └── ...
```

## Command Reference

```
usage: main.py [-h] [--test] [--day DAY] [--scrape-only] [--from-cache]
               [--engine {elevenlabs,piper,macos}] [--voice VOICE]
               [--delay DELAY] [--list-voices]

Generate podcast episodes from 31 Days of Vibe Coding

options:
  -h, --help            Show this help message and exit
  --test                Test mode: only process first 2 articles
  --day DAY             Generate specific day only (1-31)
  --scrape-only         Only scrape and process, don't generate audio
  --from-cache          Generate audio from cached text files (skip scraping)
  --engine {elevenlabs,piper,macos}
                        TTS engine to use (default: elevenlabs)
  --voice VOICE         Voice to use for TTS
  --delay DELAY         Delay between web requests in seconds (default: 1.0)
  --list-voices         List available voices for the selected engine
```

## Content Processing

The processor handles several transformations to make content audio-friendly:

- **Code blocks** → Summarized descriptions (e.g., "The following code shows how to commit changes")
- **URLs** → Removed (not useful in audio)
- **File paths** → Made speakable (`server/api.js` → "server slash api dot js")
- **Special characters** → Converted (`→` → "leads to", `✓` → "check")
- **Markdown formatting** → Stripped
- **Intro/Outro** → Added to each episode

## Troubleshooting

### Piper: "espeakbridge" import error

Make sure you're using piper-tts version 1.3.0:

```bash
pip install piper-tts==1.3.0
```

### Piper: espeak-ng not found

Install espeak-ng for your platform:

```bash
# macOS
brew install espeak-ng

# Ubuntu/Debian
sudo apt install espeak-ng
```

### MP3 conversion fails

Install ffmpeg:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### ElevenLabs: API key not found

1. Copy `.env.example` to `.env`
2. Add your API key from [ElevenLabs dashboard](https://elevenlabs.io/app/settings/api-keys)

### macOS TTS: Only works on Mac

The macOS engine uses the built-in `say` command, which is only available on macOS. Use `--engine piper` on other platforms.

## Cost Estimates

| Engine               | Cost for 31 Episodes (~221k characters) |
| -------------------- | --------------------------------------- |
| ElevenLabs (Pro)     | ~$53                                    |
| ElevenLabs (Creator) | ~$66                                    |
| Piper                | Free                                    |
| macOS                | Free                                    |

## License

MIT

## Credits

- Content: [31 Days of Vibe Coding](https://31daysofvibecoding.com/) by Jeff Blankenburg
- TTS: [ElevenLabs](https://elevenlabs.io/), [Piper](https://github.com/rhasspy/piper)
