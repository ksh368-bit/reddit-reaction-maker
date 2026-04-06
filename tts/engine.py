"""Text-to-Speech engine with pluggable providers."""

import asyncio
import os
import re
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from gtts import gTTS
from rich.console import Console

console = Console()


class TTSProvider(ABC):
    """Base class for TTS providers."""

    @abstractmethod
    def generate(self, text: str, output_path: str) -> str:
        """Generate speech from text and save to output_path. Returns the path."""
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class GoogleTTS(TTSProvider):
    """Google Text-to-Speech (free, supports many languages)."""

    def __init__(self, language: str = "en", slow: bool = False):
        self.language = language
        self.slow = slow

    def name(self) -> str:
        return "Google TTS"

    def generate(self, text: str, output_path: str) -> str:
        tts = gTTS(text=text, lang=self.language, slow=self.slow)
        tts.save(output_path)
        return output_path


class EdgeTTS(TTSProvider):
    """
    Microsoft Edge TTS (free, natural-sounding voices, speed control).

    Uses `edge-tts` Python package. Voice options:
      en-US-AriaNeural  — female, natural, warm
      en-US-GuyNeural   — male, conversational
      en-US-JennyNeural — female, upbeat
    """

    def __init__(self, voice: str = "en-US-GuyNeural", rate: str = "+20%"):
        self.voice = voice
        self.rate = rate  # e.g. "+20%" for faster speech

    def name(self) -> str:
        return f"Edge TTS ({self.voice})"

    def generate(self, text: str, output_path: str) -> str:
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            await communicate.save(output_path)

        asyncio.run(_run())
        return output_path


class TTSEngine:
    """
    TTS engine that manages text-to-speech generation for video segments.

    Handles text preprocessing, audio generation, and file management.
    """

    # Regex to match most emoji characters
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Misc Symbols and Pictographs
        "\U0001f680-\U0001f6ff"  # Transport and Map
        "\U0001f1e0-\U0001f1ff"  # Flags
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "\U00002600-\U000026ff"  # Misc Symbols
        "]+",
        flags=re.UNICODE,
    )

    def __init__(self, config: dict):
        tts_cfg = config.get("tts", {})
        engine_name = tts_cfg.get("engine", "gtts")
        language = tts_cfg.get("language", "en")
        slow = tts_cfg.get("slow", False)

        if engine_name == "edge-tts":
            voice = tts_cfg.get("voice", "en-US-GuyNeural")
            rate = tts_cfg.get("rate", "+20%")
            self.provider = EdgeTTS(voice=voice, rate=rate)
        elif engine_name == "gtts":
            self.provider = GoogleTTS(language=language, slow=slow)
        else:
            console.print(
                f"[yellow]Unknown TTS engine '{engine_name}', "
                f"falling back to edge-tts[/yellow]"
            )
            self.provider = EdgeTTS()

        console.print(f"[cyan]TTS Engine: {self.provider.name()}[/cyan]")

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean text for TTS: remove emojis, URLs, excessive whitespace."""
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove Reddit-style references
        text = re.sub(r"r/\w+", "", text)
        text = re.sub(r"u/\w+", "", text)
        # Remove emojis
        text = cls.EMOJI_PATTERN.sub("", text)
        # Remove markdown formatting
        text = re.sub(r"[*_~`#>]", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [text](url) -> text
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def generate_audio(
        self, text: str, output_path: str, max_chars: int = 500
    ) -> str | None:
        """
        Generate TTS audio for a text segment.

        Args:
            text: The text to convert to speech
            output_path: Where to save the MP3 file
            max_chars: Maximum character limit for TTS

        Returns:
            The output path if successful, None otherwise
        """
        cleaned = self.clean_text(text)
        if not cleaned:
            console.print("[yellow]  Skipped empty text segment[/yellow]")
            return None

        # Truncate if too long
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + "..."

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self.provider.generate(cleaned, output_path)
            return output_path
        except Exception as e:
            console.print(f"[red]TTS Error: {e}[/red]")
            return None

    def generate_for_post(
        self, post, temp_dir: str
    ) -> list[dict]:
        """
        Generate TTS audio for all segments of a Reddit post.

        Args:
            post: RedditPost object
            temp_dir: Directory to store temporary audio files

        Returns:
            List of dicts with 'text', 'audio_path', and 'type' keys
        """
        segments = []
        os.makedirs(temp_dir, exist_ok=True)

        # Title
        title_path = os.path.join(temp_dir, "title.mp3")
        result = self.generate_audio(post.title, title_path)
        if result:
            segments.append({
                "text": self.clean_text(post.title),
                "audio_path": result,
                "type": "title",
            })

        # Body (if exists and is short enough)
        if post.body and len(post.body.strip()) > 0:
            body_text = post.body.strip()
            if len(body_text) <= 300:  # Only include short bodies
                body_path = os.path.join(temp_dir, "body.mp3")
                result = self.generate_audio(body_text, body_path)
                if result:
                    segments.append({
                        "text": self.clean_text(body_text),
                        "audio_path": result,
                        "type": "body",
                    })

        # Comments
        for i, comment in enumerate(post.comments):
            comment_path = os.path.join(temp_dir, f"comment_{i}.mp3")
            result = self.generate_audio(comment.body, comment_path)
            if result:
                segments.append({
                    "text": self.clean_text(comment.body),
                    "audio_path": result,
                    "type": "comment",
                    "author": comment.author,
                    "score": comment.score,
                })

        console.print(
            f"  [green][OK][/green] Generated {len(segments)} audio segments"
        )
        return segments
