"""
ElevenLabs API integration for text-to-speech conversion.
Generates podcast episodes from processed article text.
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class GenerationStats:
    """Statistics for audio generation."""
    total_characters: int = 0
    total_episodes: int = 0
    episodes_generated: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    
    def add_episode(self, day: int, chars: int, duration_estimate: float):
        """Record a successfully generated episode."""
        self.total_characters += chars
        self.total_episodes += 1
        self.episodes_generated.append({
            "day": day,
            "characters": chars,
            "duration_estimate_minutes": duration_estimate,
            "timestamp": datetime.now().isoformat()
        })
    
    def add_error(self, day: int, error: str):
        """Record an error."""
        self.errors.append({
            "day": day,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def save(self, path: str):
        """Save stats to a JSON file."""
        with open(path, "w") as f:
            json.dump({
                "total_characters": self.total_characters,
                "total_episodes": self.total_episodes,
                "estimated_cost_at_pro_tier": f"${self.total_characters * 0.00024:.2f}",
                "episodes": self.episodes_generated,
                "errors": self.errors
            }, f, indent=2)
    
    def summary(self) -> str:
        """Return a summary string."""
        return (
            f"Generated {self.total_episodes} episodes\n"
            f"Total characters: {self.total_characters:,}\n"
            f"Estimated cost (Pro tier): ${self.total_characters * 0.00024:.2f}\n"
            f"Errors: {len(self.errors)}"
        )


class AudioGenerator:
    """Generates audio from text using ElevenLabs API."""
    
    # Default voice IDs from ElevenLabs
    VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # American, female, calm
        "domi": "AZnzlk1XvdvUeBnXmlld",    # American, female, strong
        "bella": "EXAVITQu4vr4xnSDxMaL",   # American, female, soft
        "antoni": "ErXwobaYiN019PkySvjV",  # American, male
        "elli": "MF3mGyEYCl7XYWbV9V6O",    # American, female, young
        "josh": "TxGEqnHWrfWFTfGW9XjX",    # American, male, deep
        "arnold": "VR6AewLTigWG4xSOukaG",  # American, male, crisp
        "adam": "pNInz6obpgDQGcFmaJgB",    # American, male, deep
        "sam": "yoZ06aMxZJJ28mfd3POQ",     # American, male, raspy
    }
    
    # Character limit per API request (ElevenLabs limit is 5000 for most plans)
    MAX_CHARS_PER_REQUEST = 4500
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128"
    ):
        """
        Initialize the audio generator.
        
        Args:
            api_key: ElevenLabs API key (defaults to ELEVENLABS_API_KEY env var)
            voice_id: Voice ID to use (defaults to ELEVENLABS_VOICE_ID env var or Rachel)
            model_id: TTS model to use
            output_format: Audio output format
        """
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key not found. "
                "Set ELEVENLABS_API_KEY environment variable or pass api_key parameter."
            )
        
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", self.VOICES["rachel"])
        self.model_id = model_id
        self.output_format = output_format
        self.stats = GenerationStats()
        
        # Import elevenlabs here to allow the module to load without it installed
        try:
            from elevenlabs import ElevenLabs
            self.client = ElevenLabs(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "elevenlabs package not installed. "
                "Run: pip install elevenlabs"
            )
    
    def generate_episode(
        self,
        text: str,
        output_path: str,
        day: int
    ) -> bool:
        """
        Generate a podcast episode from text.
        
        Args:
            text: The text to convert to speech
            output_path: Path to save the audio file
            day: Day number (for stats tracking)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            char_count = len(text)
            print(f"  Generating audio for {char_count:,} characters...")
            
            # Check if we need to chunk the text
            if char_count <= self.MAX_CHARS_PER_REQUEST:
                # Single request
                audio_data = self._generate_audio(text)
                self._save_audio(audio_data, output_path)
            else:
                # Multiple requests - chunk and concatenate
                chunks = self._chunk_text(text)
                print(f"  Text too long, splitting into {len(chunks)} chunks...")
                
                audio_chunks = []
                for i, chunk in enumerate(chunks, 1):
                    print(f"    Processing chunk {i}/{len(chunks)} ({len(chunk):,} chars)...")
                    audio_data = self._generate_audio(chunk)
                    audio_chunks.append(audio_data)
                
                # Concatenate audio chunks
                self._concatenate_and_save(audio_chunks, output_path)
            
            # Estimate duration (roughly 150 words per minute, ~5 chars per word)
            duration_estimate = char_count / (150 * 5)  # minutes
            
            self.stats.add_episode(day, char_count, duration_estimate)
            print(f"  ✓ Saved to {output_path} (est. {duration_estimate:.1f} min)")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.stats.add_error(day, error_msg)
            print(f"  ✗ Error: {error_msg}")
            return False
    
    def _generate_audio(self, text: str) -> bytes:
        """Generate audio for a single chunk of text."""
        audio_generator = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            model_id=self.model_id,
            output_format=self.output_format
        )
        
        # Collect all audio chunks
        audio_data = b""
        for chunk in audio_generator:
            audio_data += chunk
        
        return audio_data
    
    def _save_audio(self, audio_data: bytes, output_path: str) -> None:
        """Save audio data to a file."""
        with open(output_path, "wb") as f:
            f.write(audio_data)
    
    def _concatenate_and_save(self, audio_chunks: list[bytes], output_path: str) -> None:
        """
        Concatenate multiple audio chunks and save to file.
        
        For MP3 files, we can simply concatenate the bytes.
        For better quality, you might want to use pydub.
        """
        try:
            # Try using pydub for proper audio concatenation
            from pydub import AudioSegment
            import io
            
            combined = AudioSegment.empty()
            for chunk in audio_chunks:
                segment = AudioSegment.from_mp3(io.BytesIO(chunk))
                combined += segment
            
            combined.export(output_path, format="mp3")
            
        except ImportError:
            # Fall back to simple byte concatenation (works for MP3)
            print("    Note: pydub not installed, using simple concatenation")
            combined = b"".join(audio_chunks)
            self._save_audio(combined, output_path)
    
    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks that fit within API limits.
        Tries to split at sentence boundaries.
        """
        chunks = []
        current_chunk = ""
        
        # Split by paragraphs first
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            # If adding this paragraph would exceed limit, save current chunk
            if len(current_chunk) + len(para) + 2 > self.MAX_CHARS_PER_REQUEST:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # If single paragraph is too long, split by sentences
                if len(para) > self.MAX_CHARS_PER_REQUEST:
                    sentences = self._split_into_sentences(para)
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 1 > self.MAX_CHARS_PER_REQUEST:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence
                        else:
                            current_chunk += " " + sentence if current_chunk else sentence
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def list_voices(self) -> dict:
        """List available voices from the API."""
        try:
            voices = self.client.voices.get_all()
            return {v.name: v.voice_id for v in voices.voices}
        except Exception as e:
            print(f"Error fetching voices: {e}")
            return self.VOICES


def main():
    """Test the audio generator."""
    # Check if API key is set
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY not set. Please set it in .env file.")
        print("Copy .env.example to .env and add your API key.")
        return
    
    print("Testing AudioGenerator...")
    
    try:
        generator = AudioGenerator()
        
        # List available voices
        print("\nAvailable voices:")
        voices = generator.list_voices()
        for name, vid in list(voices.items())[:5]:
            print(f"  {name}: {vid}")
        
        # Test with a short sample
        test_text = (
            "Welcome to 31 Days of Vibe Coding. "
            "This is a test of the podcast generation system. "
            "If you can hear this, the audio generator is working correctly."
        )
        
        print("\nGenerating test audio...")
        success = generator.generate_episode(
            text=test_text,
            output_path="output/audio/test_episode.mp3",
            day=0
        )
        
        if success:
            print("\n✓ Test successful!")
            print(generator.stats.summary())
        else:
            print("\n✗ Test failed")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
