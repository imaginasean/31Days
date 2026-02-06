# Building a Podcast Generator for "31 Days of Vibe Coding"

_How I turned a website into a podcast I can listen to in my car, using AI-assisted development and multiple TTS engines._

---

## The Problem

I've been following Jeff Blankenburg's excellent [31 Days of Vibe Coding](https://31daysofvibecoding.com/) series—a comprehensive guide to AI-assisted software development with real-world examples. The content is fantastic, but I wanted to consume it while commuting. Reading articles in the car isn't exactly safe.

The solution? Turn the entire 31-day series into a podcast using text-to-speech. I have an ElevenLabs subscription, so that seemed like the obvious choice. But as I'd discover, having options is always better.

## Planning the Pipeline

The plan was straightforward enough:

1. **Scrape** all 31 articles from the website
2. **Process** the content for audio (handle code blocks, clean up formatting)
3. **Generate** MP3 files using text-to-speech
4. **Listen** while driving

The tricky part? Code blocks. Hearing someone read `git add -A && git commit -m "WIP"` character by character is... not productive. Those needed to be summarized or described instead.

## Building the Scraper

First, I needed to figure out the URL structure. The homepage didn't list all the articles directly, but after some exploration, I discovered the pattern:

```
https://31daysofvibecoding.com/2026/01/{DD}/{slug}/
```

Each article had navigation links to previous and next days, making it easy to crawl the entire series. The scraper would:

- Start from a known article
- Follow navigation links to discover all 31 URLs
- Parse each article's HTML content
- Extract title, date, and main content

```python
class VibeCodingScraper:
    def discover_article_urls(self) -> list[str]:
        """Crawl from known articles to find all 31 days."""
        # ... discovery logic
```

## Processing Content for Audio

This was the interesting challenge. Raw HTML needed to become spoken-word-friendly text.

**Code blocks** got special treatment. Instead of reading code verbatim, the processor generates descriptions:

```
# Before (in HTML):
<pre><code class="language-bash">
git add -A
git commit -m "WIP: before AI changes"
</code></pre>

# After (for audio):
[Code Example: The following code commands show how to commit changes.]
```

**URLs** were removed entirely—they're useless in audio form.

**Special characters** got converted: `→` becomes "leads to", `✓` becomes "check".

**File paths** were made speakable: `server/routes/api.js` becomes "server slash routes slash api dot js".

Each episode also got an intro ("Welcome to Day 7 of 31 Days of Vibe Coding...") and outro to give it that podcast feel.

## The ElevenLabs Integration

With my ElevenLabs subscription, this should have been the easy part. The API is clean:

```python
from elevenlabs import ElevenLabs

client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

audio = client.text_to_speech.convert(
    text=article_text,
    voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
    model_id="eleven_multilingual_v2"
)
```

But there's a cost consideration. With 31 articles totaling ~221,000 characters, the estimated cost at Pro tier pricing ($0.24 per 1,000 characters) would be around **$53**. Not terrible for a one-time generation, but I wanted a free alternative too.

## Enter Piper TTS

[Piper](https://github.com/rhasspy/piper) is a fast, local neural text-to-speech engine. No API keys. No usage limits. No cost. Runs entirely on your machine.

Adding Piper support seemed straightforward. Install the package, load a voice model, synthesize text:

```python
from piper import PiperVoice

voice = PiperVoice.load("models/en_US-amy-medium.onnx")
audio_chunks = voice.synthesize(text)
```

### The Python 3.13 Problem

Here's where things got interesting. When I first tried Piper, it crashed immediately:

```
ImportError: cannot import name 'espeakbridge' from 'piper'
```

The `espeakbridge` module is a compiled C extension that handles phonemization (converting text to phonemes for the neural network). The latest piper-tts 1.4.0 didn't have this extension compiled for Python 3.13.

I was stuck. The error message was cryptic. I started adding better error handling, checking for espeak-ng installation, trying different approaches...

### The Breakthrough

Then I remembered—I had a working Piper setup in another project. Same machine. Same Python version. What was different?

```bash
# Check the working project's piper version
pip show piper-tts
# Version: 1.3.0

# Check my new project
pip show piper-tts
# Version: 1.4.0
```

The older version (1.3.0) had the `espeakbridge` module compiled for Python 3.13. The newer version (1.4.0) did not.

```bash
pip install piper-tts==1.3.0
```

Suddenly, everything worked.

### The Missing Dependencies

Well, almost everything. Piper also needs:

1. **espeak-ng** - For phonemization (converting text to phonemes)

   ```bash
   brew install espeak-ng
   ```

2. **ffmpeg** - For converting WAV to MP3
   ```bash
   brew install ffmpeg
   ```

With those installed, the full pipeline finally worked:

```
Processing Day 1...
  Loading voice model: models/piper/en_US-amy-medium.onnx
  Generating audio for 8,293 characters...
    Synthesizing audio...
    Generated 198 audio chunks
  ✓ Saved to output/audio/day_01.mp3 (est. 11.1 min)
```

## Adding macOS TTS as a Fallback

Since I was on macOS, I also added support for the built-in `say` command. It's not as high-quality as Piper or ElevenLabs, but it requires zero setup:

```python
subprocess.run([
    "say",
    "-v", "Samantha",
    "-r", "180",  # words per minute
    "-o", "output.aiff",
    text
])
```

Now the project supports three TTS engines, giving users flexibility based on their needs and setup.

## The Final Architecture

```
31Days/
├── main.py              # Orchestrates everything
├── scraper.py           # Fetches articles from the website
├── processor.py         # Converts HTML to audio-friendly text
├── audio_generator.py   # ElevenLabs API integration
├── piper_generator.py   # Local Piper TTS
├── macos_generator.py   # macOS built-in TTS
├── requirements.txt
└── output/
    ├── text/            # Processed article text (31 files)
    └── audio/           # Generated MP3 files
```

## Usage

The scraping and processing is already done—all 31 articles are cached as text files. Generating the podcast is now a single command:

```bash
# Free, local generation with Piper
python main.py --engine piper --from-cache

# Or with ElevenLabs for higher quality
python main.py --engine elevenlabs --from-cache

# Or test with just one day
python main.py --engine piper --from-cache --day 1
```

## Results

- **31 articles** scraped and processed
- **221,030 characters** of content
- **~11 minutes** per episode on average
- **~20 seconds** to generate each episode with Piper
- **$0** cost with local TTS

## Lessons Learned

1. **Version pinning matters.** The difference between piper-tts 1.3.0 and 1.4.0 was the difference between working and completely broken. Always check what version works before upgrading.

2. **Have fallbacks.** Building support for three TTS engines (ElevenLabs, Piper, macOS) means the tool works regardless of whether you have an API key, the right Python version, or specific dependencies.

3. **Check existing working code first.** When debugging the Piper issue, the breakthrough came from comparing against a known-working setup. Sometimes the answer is in code you've already written.

4. **Code blocks need special handling for audio.** Nobody wants to hear "open curly brace, newline, space space space space, const, space, user, space, equals, space..." The summarization approach makes the content actually listenable.

## What's Next

The podcast is ready. Time to load it onto my phone and start commuting through 31 days of vibe coding wisdom.

If you want to build something similar for your own content, the code handles the hard parts—scraping, processing, and multiple TTS engines. Fork it, point it at different content, and generate your own audio library.

Code examples aren't translated yet. Currently, it is explained as "a code example is here" and needs to be summarized better through another step of AI handling the evaluation of the code example to give a textual summary instead. This will be Part 2.

---

## Appendix: The Prompts Used

Here are the actual prompts I used with Claude in Cursor to build this project, in order:

### 1. Initial Request

> I want to create a podcast of the content from day 1 to day 31 so i can listen to this in the car. Please plan out how i can do this using eleven labs api, as i have a subscription

_Claude asked clarifying questions about where the content was located and what format it was in. I answered:_

> https://31daysofvibecoding.com/
>
> html, that needs to get pulled down and sanitized for podcast format and for coding examples they will need to be summarized since audio playing of code blocks usually is not very productive

### 2. Implementation

> Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

_This triggered the creation of the scraper, processor, and ElevenLabs integration._

### 3. Adding Piper TTS

> i would like to add the ability to do this with piper tts as well

_This led to adding Piper support, but we hit the Python 3.13 compatibility issue with piper-tts 1.4.0._

### 4. The Debugging Breakthrough

> look at this code where i have used this successfully on this machine @/Users/seankelly/projects/voicetts/tts-test

_Pointing Claude at my working Piper setup revealed the version difference (1.3.0 vs 1.4.0) that fixed everything._

### 5. Documentation

> create a markdown of the work/conversation it took to get to this point and in the style of a blogpost in a narative from start to finish. put this in blogpost.md in the root

> create a proper README for how to install and run with examples

### 6. Security Check

> make sure there are no secrets in this repo

### 7. Final Polish

> Add to the readme. the commands to run With the Amy Piper voice.

> include the prompts used to build the code at the end of the blogpost.md

---

**Total prompts: 8** (plus a few clarifying responses)

**Total time: ~45 minutes** from initial request to working podcast generator with three TTS engines, documentation, and this blog post.

---

_Built with Claude, Cursor, and some debugging of library compatibility issues._
