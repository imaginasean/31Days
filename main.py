#!/usr/bin/env python3
"""
31 Days of Vibe Coding Podcast Generator

Main orchestration script that:
1. Scrapes all 31 articles from the website
2. Processes content for audio (sanitizes HTML, summarizes code blocks)
3. Generates podcast episodes using ElevenLabs API or Piper TTS
4. Saves audio files and tracking stats

Usage:
    python main.py                           # Generate all with ElevenLabs
    python main.py --engine piper            # Generate all with Piper (free, local)
    python main.py --test                    # Test with first 2 articles only
    python main.py --day 7                   # Generate specific day only
    python main.py --scrape-only             # Only scrape and process, no audio
    python main.py --from-cache              # Use cached text files (skip scraping)
    python main.py --engine piper --voice amy # Use Piper with specific voice
    python main.py --use-llm                 # Use Claude for code block summaries
    python main.py --use-llm --resummarize   # Re-generate all code summaries
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scraper import VibeCodingScraper
from processor import ContentProcessor
from audio_generator import AudioGenerator, GenerationStats
from piper_generator import PiperGenerator, PiperGenerationStats, PIPER_VOICES
from macos_generator import MacOSGenerator, MACOS_VOICES


def setup_directories():
    """Ensure output directories exist."""
    Path("output/text").mkdir(parents=True, exist_ok=True)
    Path("output/audio").mkdir(parents=True, exist_ok=True)


def save_text(processed_article, output_dir: str = "output/text"):
    """Save processed text to a file."""
    filename = f"day_{processed_article.day:02d}.txt"
    filepath = Path(output_dir) / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Title: {processed_article.title}\n")
        f.write(f"Day: {processed_article.day}\n")
        f.write(f"Date: {processed_article.date}\n")
        f.write(f"Characters: {processed_article.char_count}\n")
        f.write(f"Words: {processed_article.word_count}\n")
        f.write("=" * 50 + "\n\n")
        f.write(processed_article.text)
    
    return filepath


def load_text(day: int, input_dir: str = "output/text") -> tuple[str, dict]:
    """Load processed text from cache file."""
    filename = f"day_{day:02d}.txt"
    filepath = Path(input_dir) / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Cached text not found: {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse metadata from header
    lines = content.split("\n")
    metadata = {}
    text_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith("="):
            text_start = i + 2  # Skip separator and blank line
            break
        if ": " in line:
            key, value = line.split(": ", 1)
            metadata[key.lower()] = value
    
    text = "\n".join(lines[text_start:])
    return text, metadata


def scrape_and_process(
    scraper: VibeCodingScraper,
    processor: ContentProcessor,
    specific_day: int = None
) -> list:
    """Scrape articles and process them for audio."""
    
    print("\n" + "=" * 60)
    print("STEP 1: SCRAPING ARTICLES")
    print("=" * 60)
    
    if specific_day:
        # Discover URLs to find the specific day
        urls = scraper.discover_article_urls()
        target_url = None
        for url in urls:
            if f"/01/{specific_day:02d}/" in url:
                target_url = url
                break
        
        if not target_url:
            print(f"Could not find URL for Day {specific_day}")
            return []
        
        articles = [scraper.parse_article(target_url)]
        articles = [a for a in articles if a]  # Remove None
    else:
        articles = scraper.scrape_all()
    
    print(f"\nScraped {len(articles)} articles")
    
    print("\n" + "=" * 60)
    print("STEP 2: PROCESSING CONTENT")
    print("=" * 60)
    
    processed_articles = []
    total_chars = 0
    
    for article in articles:
        print(f"\nProcessing Day {article.day}: {article.title}")
        
        processed = processor.process(
            html_content=article.content,
            day=article.day,
            title=article.title,
            date=article.date
        )
        
        # Save text file
        filepath = save_text(processed)
        print(f"  Saved: {filepath}")
        print(f"  Characters: {processed.char_count:,}")
        print(f"  Words: {processed.word_count:,}")
        
        processed_articles.append(processed)
        total_chars += processed.char_count
    
    print(f"\n{'=' * 60}")
    print(f"PROCESSING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total articles: {len(processed_articles)}")
    print(f"Total characters: {total_chars:,}")
    print(f"Estimated ElevenLabs cost (Pro tier): ${total_chars * 0.00024:.2f}")
    print(f"Piper TTS cost: $0.00 (local processing)")
    
    return processed_articles


def generate_audio(
    processed_articles: list,
    generator: AudioGenerator,
    output_dir: str = "output/audio"
) -> GenerationStats:
    """Generate audio for all processed articles."""
    
    print("\n" + "=" * 60)
    print("STEP 3: GENERATING AUDIO")
    print("=" * 60)
    
    for processed in processed_articles:
        print(f"\nDay {processed.day}: {processed.title}")
        
        output_path = Path(output_dir) / f"day_{processed.day:02d}.mp3"
        
        generator.generate_episode(
            text=processed.text,
            output_path=str(output_path),
            day=processed.day
        )
    
    return generator.stats


def generate_from_cache(
    generator: AudioGenerator,
    days: list[int] = None,
    input_dir: str = "output/text",
    output_dir: str = "output/audio"
):
    """Generate audio from cached text files."""
    
    print("\n" + "=" * 60)
    print("GENERATING AUDIO FROM CACHED TEXT")
    print("=" * 60)
    
    # Find all cached text files if no specific days provided
    if days is None:
        text_dir = Path(input_dir)
        days = []
        for f in sorted(text_dir.glob("day_*.txt")):
            day_num = int(f.stem.split("_")[1])
            days.append(day_num)
    
    for day in days:
        print(f"\nProcessing Day {day}...")
        
        try:
            text, metadata = load_text(day, input_dir)
            output_path = Path(output_dir) / f"day_{day:02d}.mp3"
            
            generator.generate_episode(
                text=text,
                output_path=str(output_path),
                day=day
            )
        except FileNotFoundError as e:
            print(f"  ✗ {e}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    return generator.stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate podcast episodes from 31 Days of Vibe Coding"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only process first 2 articles"
    )
    parser.add_argument(
        "--day",
        type=int,
        help="Generate specific day only (1-31)"
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape and process, don't generate audio"
    )
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Generate audio from cached text files (skip scraping)"
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["elevenlabs", "piper", "macos"],
        default="elevenlabs",
        help="TTS engine: 'elevenlabs' (API, paid), 'piper' (local, free), or 'macos' (built-in, free)"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help="Voice to use. ElevenLabs: rachel, josh, bella. Piper: lessac, ryan. macOS: samantha, alex, etc."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between web requests in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices for the selected engine and exit"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM (Claude) to generate detailed code block summaries"
    )
    parser.add_argument(
        "--resummarize",
        action="store_true",
        help="Force re-summarization of code blocks (ignore cache)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Handle --list-voices
    if args.list_voices:
        print(f"Available voices for {args.engine}:\n")
        if args.engine == "elevenlabs":
            for name, vid in AudioGenerator.VOICES.items():
                print(f"  {name}: {vid}")
        elif args.engine == "piper":
            for name, info in PIPER_VOICES.items():
                print(f"  {name}: {info[2]} ({info[1]} quality)")
        else:  # macos
            voices = MacOSGenerator.list_voices()
            for name, info in list(voices.items())[:15]:
                desc = info.get('description', '') or info.get(2, '')
                print(f"  {name}: {desc}")
        sys.exit(0)
    
    # Setup
    setup_directories()
    
    print("=" * 60)
    print("31 DAYS OF VIBE CODING - PODCAST GENERATOR")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Engine: {args.engine.upper()}")
    
    if args.test:
        print("Mode: TEST (first 2 articles only)")
    elif args.day:
        print(f"Mode: SINGLE DAY (Day {args.day})")
    elif args.scrape_only:
        print("Mode: SCRAPE ONLY (no audio generation)")
    elif args.from_cache:
        print("Mode: FROM CACHE (using saved text files)")
    else:
        print("Mode: FULL (all 31 articles)")
    
    # Initialize components
    scraper = VibeCodingScraper(delay=args.delay)
    
    # Initialize LLM summarizer if requested
    llm_summarizer = None
    if args.use_llm:
        try:
            from code_summarizer import CodeSummarizer
            if not os.environ.get("ANTHROPIC_API_KEY"):
                print("\n✗ Error: ANTHROPIC_API_KEY not set")
                print("  Set it in .env file to use --use-llm")
                sys.exit(1)
            llm_summarizer = CodeSummarizer()
            print("LLM Summarization: ENABLED")
            if args.resummarize:
                print("  (forcing re-summarization, ignoring cache)")
        except ImportError as e:
            print(f"\n✗ Error: Could not load CodeSummarizer: {e}")
            print("  Make sure anthropic is installed: pip install anthropic")
            sys.exit(1)
    
    processor = ContentProcessor(
        summarize_code=True,
        use_llm=args.use_llm,
        llm_summarizer=llm_summarizer,
        force_resummarize=args.resummarize
    )
    
    # Create the appropriate generator based on engine choice
    def create_generator():
        """Create the appropriate TTS generator based on args."""
        if args.engine == "piper":
            voice = args.voice or "lessac"
            if voice not in PIPER_VOICES and not voice.startswith("en_"):
                print(f"Unknown Piper voice '{voice}', using 'lessac'")
                voice = "lessac"
            print(f"Voice: {voice}")
            return PiperGenerator(voice=voice)
        elif args.engine == "macos":
            voice = args.voice or "samantha"
            print(f"Voice: {voice}")
            return MacOSGenerator(voice=voice)
        else:
            # ElevenLabs
            if not os.environ.get("ELEVENLABS_API_KEY"):
                print("\n✗ Error: ELEVENLABS_API_KEY not set")
                print("  Copy .env.example to .env and add your API key")
                print("  Or use --engine macos for free built-in TTS (macOS only)")
                print("  Or use --engine piper for free local TTS (requires espeak-ng)")
                sys.exit(1)
            
            voice_id = None
            if args.voice:
                voice_map = AudioGenerator.VOICES
                if args.voice.lower() in voice_map:
                    voice_id = voice_map[args.voice.lower()]
                    print(f"Voice: {args.voice}")
                else:
                    print(f"Unknown voice '{args.voice}', using default")
            
            return AudioGenerator(voice_id=voice_id)
    
    # Handle different modes
    if args.from_cache:
        # Generate from cached text files
        generator = create_generator()
        
        days = [args.day] if args.day else None
        stats = generate_from_cache(generator, days=days)
        
    else:
        # Scrape and process
        specific_day = args.day
        processed_articles = scrape_and_process(scraper, processor, specific_day)
        
        if args.test:
            processed_articles = processed_articles[:2]
            print(f"\nTest mode: limited to {len(processed_articles)} articles")
        
        if not processed_articles:
            print("\n✗ No articles to process")
            sys.exit(1)
        
        # Generate audio unless scrape-only mode
        if not args.scrape_only:
            generator = create_generator()
            stats = generate_audio(processed_articles, generator)
        else:
            stats = None
    
    # Final summary
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    
    if stats:
        print(stats.summary())
        
        # Save stats
        stats_path = "output/generation_stats.json"
        stats.save(stats_path)
        print(f"\nStats saved to: {stats_path}")
    
    # Print LLM summarization stats if used
    if args.use_llm and llm_summarizer:
        llm_stats = llm_summarizer.get_stats()
        print(f"\nLLM Code Summarization:")
        print(f"  API calls: {llm_stats['api_calls']}")
        print(f"  Cache hits: {llm_stats['cache_hits']}")
        print(f"  Errors: {llm_stats['errors']}")
        print(f"  Cache size: {llm_stats['cache_size']} summaries")
    
    print(f"\nText files: output/text/")
    print(f"Audio files: output/audio/")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
