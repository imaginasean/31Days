"""
Piper TTS integration for local text-to-speech conversion.
Generates podcast episodes without requiring an API key.

Piper is a fast, local neural text-to-speech engine that runs entirely offline.

Requirements:
- piper-tts Python package: pip install piper-tts
- espeak-ng (for phonemization):
  - macOS: brew install espeak-ng
  - Ubuntu/Debian: sudo apt install espeak-ng
  - Windows: Download from https://github.com/espeak-ng/espeak-ng/releases
"""

import io
import os
import json
import shutil
import subprocess
import sys
import wave
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to import numpy for audio handling
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Try to import pydub for audio conversion
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False


# Available Piper voices (common English voices)
# Format: name -> (model_name, quality, description)
PIPER_VOICES = {
    "lessac": ("en_US-lessac-medium", "medium", "US English, neutral"),
    "lessac-high": ("en_US-lessac-high", "high", "US English, neutral, high quality"),
    "amy": ("en_US-amy-medium", "medium", "US English, female"),
    "arctic": ("en_US-arctic-medium", "medium", "US English, multiple speakers"),
    "danny": ("en_GB-danny-low", "low", "British English, male"),
    "jenny": ("en_US-jenny_dioco-medium", "medium", "US English, female"),
    "ryan": ("en_US-ryan-medium", "medium", "US English, male"),
    "ryan-high": ("en_US-ryan-high", "high", "US English, male, high quality"),
    "kusal": ("en_US-kusal-medium", "medium", "US English, male"),
    "libritts": ("en_US-libritts-high", "high", "US English, LibriTTS trained"),
    "ljspeech": ("en_US-ljspeech-medium", "medium", "US English, LJSpeech trained"),
    "kristin": ("en_US-kristin-medium", "medium", "US English, female"),
    "hfc_female": ("en_US-hfc_female-medium", "medium", "US English, female"),
}


def check_espeak_installed() -> bool:
    """Check if espeak-ng is installed on the system."""
    return shutil.which("espeak-ng") is not None


@dataclass
class PiperGenerationStats:
    """Statistics for Piper audio generation."""
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
                "engine": "piper",
                "total_characters": self.total_characters,
                "total_episodes": self.total_episodes,
                "cost": "$0.00 (local processing)",
                "episodes": self.episodes_generated,
                "errors": self.errors
            }, f, indent=2)
    
    def summary(self) -> str:
        """Return a summary string."""
        return (
            f"Generated {self.total_episodes} episodes with Piper TTS\n"
            f"Total characters: {self.total_characters:,}\n"
            f"Cost: $0.00 (local processing)\n"
            f"Errors: {len(self.errors)}"
        )


class PiperGenerator:
    """Generates audio from text using Piper TTS (local, offline)."""
    
    # Hugging Face URL for downloading models
    MODEL_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    
    def __init__(
        self,
        voice: str = "amy",
        model_path: Optional[str] = None,
        models_dir: str = "models/piper",
        output_format: str = "mp3",
        speaker_id: Optional[int] = None
    ):
        """
        Initialize the Piper generator.
        
        Args:
            voice: Voice name from PIPER_VOICES or custom model name
            model_path: Direct path to .onnx model file (overrides voice)
            models_dir: Directory to store downloaded models
            output_format: Output format ('mp3' or 'wav')
            speaker_id: Speaker ID for multi-speaker models (optional)
        """
        self.models_dir = Path(models_dir)
        self.output_format = output_format
        self.speaker_id = speaker_id
        self.stats = PiperGenerationStats()
        self.voice = None  # Will hold the loaded PiperVoice
        
        # Determine model to use
        if model_path:
            self.model_path = Path(model_path)
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model not found: {model_path}")
        else:
            self.voice_name = voice
            if voice in PIPER_VOICES:
                self.model_name = PIPER_VOICES[voice][0]
            else:
                # Assume it's a direct model name
                self.model_name = voice
            self.model_path = None  # Will be set after download/check
        
        # Check if piper is available
        self._check_piper_installed()
    
    def _check_piper_installed(self):
        """Check if piper-tts and dependencies are installed."""
        # Check for espeak-ng first
        if not check_espeak_installed():
            raise RuntimeError(
                "espeak-ng not found. Piper requires espeak-ng for phonemization.\n"
                "Install it with:\n"
                "  macOS:        brew install espeak-ng\n"
                "  Ubuntu/Debian: sudo apt install espeak-ng\n"
                "  Windows:      Download from https://github.com/espeak-ng/espeak-ng/releases"
            )
        
        # Try to import the Piper Python API
        try:
            from piper import PiperVoice
            self._PiperVoice = PiperVoice
        except ImportError:
            raise ImportError(
                "piper-tts not installed. Run: pip install piper-tts"
            )
    
    def _ensure_model(self) -> Path:
        """Ensure the model is downloaded and return its path."""
        if self.model_path and self.model_path.exists():
            return self.model_path
        
        # Check if model already exists
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        model_file = self.models_dir / f"{self.model_name}.onnx"
        config_file = self.models_dir / f"{self.model_name}.onnx.json"
        
        if model_file.exists() and config_file.exists():
            self.model_path = model_file
            return model_file
        
        # Download the model
        print(f"  Downloading Piper voice model: {self.model_name}")
        self._download_model(self.model_name, model_file, config_file)
        
        self.model_path = model_file
        return model_file
    
    def _load_voice(self):
        """Load the Piper voice model."""
        if self.voice is None:
            model_path = self._ensure_model()
            print(f"  Loading voice model: {model_path}")
            self.voice = self._PiperVoice.load(str(model_path))
        return self.voice
    
    def _download_model(self, model_name: str, model_file: Path, config_file: Path):
        """Download a Piper model from Hugging Face."""
        import requests
        
        # Parse model name to get the path
        # Format: en_US-lessac-medium -> en/en_US/lessac/medium/
        parts = model_name.split("-")
        lang = parts[0]  # en_US
        lang_short = lang.split("_")[0]  # en
        speaker = parts[1]  # lessac
        quality = parts[2] if len(parts) > 2 else "medium"  # medium
        
        base_path = f"{lang_short}/{lang}/{speaker}/{quality}"
        
        # Download ONNX model
        model_url = f"{self.MODEL_BASE_URL}/{base_path}/{model_name}.onnx"
        print(f"    Downloading model from: {model_url}")
        
        response = requests.get(model_url, stream=True)
        response.raise_for_status()
        
        with open(model_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Download config JSON
        config_url = f"{self.MODEL_BASE_URL}/{base_path}/{model_name}.onnx.json"
        print(f"    Downloading config from: {config_url}")
        
        response = requests.get(config_url)
        response.raise_for_status()
        
        with open(config_file, "w") as f:
            f.write(response.text)
        
        print(f"    Model saved to: {model_file}")
    
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
            
            # Load the voice model
            voice = self._load_voice()
            
            char_count = len(text)
            print(f"  Generating audio for {char_count:,} characters...")
            
            # Determine output file paths
            output_path = Path(output_path)
            if self.output_format == "mp3":
                wav_path = output_path.with_suffix(".wav")
                final_path = output_path
            else:
                wav_path = output_path
                final_path = output_path
            
            # Generate audio using Piper Python API
            self._synthesize_with_api(text, voice, wav_path)
            
            # Convert to MP3 if requested
            if self.output_format == "mp3":
                self._convert_to_mp3(wav_path, final_path)
                wav_path.unlink()  # Remove temporary WAV
            
            # Estimate duration (roughly 150 words per minute, ~5 chars per word)
            duration_estimate = char_count / (150 * 5)  # minutes
            
            self.stats.add_episode(day, char_count, duration_estimate)
            print(f"  ✓ Saved to {final_path} (est. {duration_estimate:.1f} min)")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.stats.add_error(day, error_msg)
            print(f"  ✗ Error: {error_msg}")
            import traceback
            traceback.print_exc()
            return False
    
    def _synthesize_with_api(self, text: str, voice, output_path: Path):
        """Synthesize text to audio using Piper Python API."""
        from piper import SynthesisConfig
        
        # Create synthesis config
        syn_config = SynthesisConfig(
            speaker_id=self.speaker_id,
            length_scale=1.0,  # Normal speed
            noise_scale=0.667,  # Default variation
            noise_w_scale=0.8,  # Default speaking variation
        )
        
        # Synthesize all audio chunks
        print(f"    Synthesizing audio...")
        audio_chunks = list(voice.synthesize(text, syn_config))
        
        if not audio_chunks:
            raise RuntimeError("No audio generated")
        
        # Get sample rate from first chunk
        sample_rate = audio_chunks[0].sample_rate
        
        # Concatenate all audio data
        if HAS_NUMPY:
            import numpy as np
            audio_data = np.concatenate([chunk.audio_float_array for chunk in audio_chunks])
            # Convert float32 to int16 for WAV
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
        else:
            # Fallback without numpy - use raw bytes
            audio_bytes = b"".join([chunk.audio_bytes for chunk in audio_chunks])
        
        # Write WAV file
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_bytes)
        
        print(f"    Generated {len(audio_chunks)} audio chunks")
    
    def _convert_to_mp3(self, wav_path: Path, mp3_path: Path):
        """Convert WAV to MP3."""
        if HAS_PYDUB:
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3", bitrate="128k")
        else:
            # Try using ffmpeg directly
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "128k", str(mp3_path)],
                capture_output=True
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "Could not convert to MP3. Install pydub or ffmpeg."
                )
    
    @staticmethod
    def list_voices() -> dict:
        """List available pre-configured voices."""
        return {
            name: {
                "model": info[0],
                "quality": info[1],
                "description": info[2]
            }
            for name, info in PIPER_VOICES.items()
        }


def main():
    """Test the Piper generator."""
    print("Testing PiperGenerator...")
    print("\nAvailable voices:")
    for name, info in PiperGenerator.list_voices().items():
        print(f"  {name}: {info['description']} ({info['quality']} quality)")
    
    try:
        generator = PiperGenerator(voice="lessac")
        
        # Test with a short sample
        test_text = (
            "Welcome to 31 Days of Vibe Coding. "
            "This is a test of the Piper text to speech system. "
            "If you can hear this, the local audio generator is working correctly."
        )
        
        print("\nGenerating test audio...")
        success = generator.generate_episode(
            text=test_text,
            output_path="output/audio/test_piper_episode.mp3",
            day=0
        )
        
        if success:
            print("\n✓ Test successful!")
            print(generator.stats.summary())
        else:
            print("\n✗ Test failed")
            
    except ImportError as e:
        print(f"\n✗ {e}")
        print("Install with: pip install piper-tts")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()
