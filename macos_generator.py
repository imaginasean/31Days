"""
macOS built-in TTS integration using the 'say' command.
Free, offline, and works on any Mac without additional dependencies.

This is a fallback option when ElevenLabs API key isn't available
and Piper has compatibility issues.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import pydub for audio conversion
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


# macOS voices available via 'say' command
# Run 'say -v ?' to see all available voices on your system
MACOS_VOICES = {
    # Premium voices (may need to be downloaded in System Settings > Accessibility > Spoken Content)
    "samantha": ("Samantha", "en-US", "Female, natural sounding"),
    "alex": ("Alex", "en-US", "Male, natural sounding"),
    "tom": ("Tom", "en-US", "Male, clear"),
    "karen": ("Karen", "en-AU", "Australian female"),
    "daniel": ("Daniel", "en-GB", "British male"),
    "moira": ("Moira", "en-IE", "Irish female"),
    "fiona": ("Fiona", "en-scotland", "Scottish female"),
    # Standard voices
    "fred": ("Fred", "en-US", "Male, robotic"),
    "victoria": ("Victoria", "en-US", "Female, standard"),
}


@dataclass
class MacOSGenerationStats:
    """Statistics for macOS TTS audio generation."""
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
                "engine": "macos",
                "total_characters": self.total_characters,
                "total_episodes": self.total_episodes,
                "cost": "$0.00 (built-in macOS TTS)",
                "episodes": self.episodes_generated,
                "errors": self.errors
            }, f, indent=2)
    
    def summary(self) -> str:
        """Return a summary string."""
        return (
            f"Generated {self.total_episodes} episodes with macOS TTS\n"
            f"Total characters: {self.total_characters:,}\n"
            f"Cost: $0.00 (built-in macOS TTS)\n"
            f"Errors: {len(self.errors)}"
        )


class MacOSGenerator:
    """Generates audio using macOS built-in 'say' command."""
    
    def __init__(
        self,
        voice: str = "samantha",
        rate: int = 180,  # Words per minute
        output_format: str = "mp3"
    ):
        """
        Initialize the macOS TTS generator.
        
        Args:
            voice: Voice name from MACOS_VOICES or any voice installed on your Mac
            rate: Speaking rate in words per minute (default: 180)
            output_format: Output format ('mp3' or 'aiff')
        """
        self.output_format = output_format
        self.rate = rate
        self.stats = MacOSGenerationStats()
        
        # Determine voice to use
        if voice.lower() in MACOS_VOICES:
            self.voice = MACOS_VOICES[voice.lower()][0]
        else:
            self.voice = voice
        
        # Check if we're on macOS
        if sys.platform != "darwin":
            raise RuntimeError(
                "macOS TTS is only available on macOS. "
                "Use --engine elevenlabs or --engine piper instead."
            )
        
        # Verify the say command works
        self._check_say_available()
    
    def _check_say_available(self):
        """Verify the say command is available."""
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise RuntimeError("macOS say command not working")
        except FileNotFoundError:
            raise RuntimeError("macOS say command not found")
    
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
            
            # Determine output file paths
            output_path = Path(output_path)
            if self.output_format == "mp3":
                aiff_path = output_path.with_suffix(".aiff")
                final_path = output_path
            else:
                aiff_path = output_path
                final_path = output_path
            
            # Generate audio using say command
            self._synthesize(text, aiff_path)
            
            # Convert to MP3 if requested
            if self.output_format == "mp3":
                self._convert_to_mp3(aiff_path, final_path)
                aiff_path.unlink()  # Remove temporary AIFF
            
            # Estimate duration based on rate
            word_count = len(text.split())
            duration_estimate = word_count / self.rate  # minutes
            
            self.stats.add_episode(day, char_count, duration_estimate)
            print(f"  ✓ Saved to {final_path} (est. {duration_estimate:.1f} min)")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.stats.add_error(day, error_msg)
            print(f"  ✗ Error: {error_msg}")
            return False
    
    def _synthesize(self, text: str, output_path: Path):
        """Synthesize text to audio using say command."""
        cmd = [
            "say",
            "-v", self.voice,
            "-r", str(self.rate),
            "-o", str(output_path),
            text
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"say command failed: {result.stderr}")
        
        if not output_path.exists():
            raise RuntimeError("say command did not create output file")
    
    def _convert_to_mp3(self, aiff_path: Path, mp3_path: Path):
        """Convert AIFF to MP3."""
        if HAS_PYDUB:
            audio = AudioSegment.from_file(str(aiff_path), format="aiff")
            audio.export(str(mp3_path), format="mp3", bitrate="128k")
        else:
            # Try using ffmpeg directly
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(aiff_path), "-b:a", "128k", str(mp3_path)],
                capture_output=True
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Could not convert to MP3. Install pydub (pip install pydub) "
                    "or ffmpeg (brew install ffmpeg)."
                )
    
    @staticmethod
    def list_voices() -> dict:
        """List available voices on this Mac."""
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True
            )
            
            voices = {}
            for line in result.stdout.strip().split("\n"):
                # Parse lines like: "Alex                en_US    # Most people recognize me by my voice."
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    lang = parts[1] if len(parts) > 1 else "en_US"
                    voices[name.lower()] = {
                        "name": name,
                        "language": lang,
                        "description": " ".join(parts[3:]) if len(parts) > 3 else ""
                    }
            
            return voices
        except Exception:
            return MACOS_VOICES


def main():
    """Test the macOS TTS generator."""
    import sys
    
    if sys.platform != "darwin":
        print("This generator only works on macOS")
        return
    
    print("Testing MacOSGenerator...")
    print("\nAvailable voices:")
    voices = MacOSGenerator.list_voices()
    for name, info in list(voices.items())[:10]:
        print(f"  {name}: {info.get('description', info.get('language', ''))}")
    
    try:
        generator = MacOSGenerator(voice="samantha")
        
        # Test with a short sample
        test_text = (
            "Welcome to 31 Days of Vibe Coding. "
            "This is a test of the macOS text to speech system. "
            "If you can hear this, the audio generator is working correctly."
        )
        
        print("\nGenerating test audio...")
        success = generator.generate_episode(
            text=test_text,
            output_path="output/audio/test_macos_episode.mp3",
            day=0
        )
        
        if success:
            print("\n✓ Test successful!")
            print(generator.stats.summary())
        else:
            print("\n✗ Test failed")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()
