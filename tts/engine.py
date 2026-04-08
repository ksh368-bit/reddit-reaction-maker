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


def estimate_word_segments(
    audio_path: str | None,
    text: str,
    fallback_duration: float = 0.0,
) -> list[dict]:
    """
    Estimate per-word timing from audio duration + character proportions.

    Used when edge-tts WordBoundary events are unavailable (edge-tts 7.x
    no longer emits WordBoundary — only SentenceBoundary).

    Timing is proportional to each word's character count: longer words
    get more time, approximating natural speech cadence.

    Args:
        audio_path: Path to generated MP3 (read for actual duration).
                    Pass None to use fallback_duration.
        text: The text that was spoken.
        fallback_duration: Duration to use when audio_path is None or unreadable.

    Returns:
        List of {word, start_time, end_time} dicts.
    """
    words = text.split()
    if not words:
        return []

    total_duration = fallback_duration
    if audio_path and Path(audio_path).exists():
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(audio_path) as ac:
                total_duration = ac.duration
        except Exception:
            pass

    if total_duration <= 0:
        # Rough estimate: ~3 words/second at +20% speed
        total_duration = len(words) / 3.0

    # Proportional timing by character count
    char_counts = [max(1, len(w)) for w in words]
    total_chars = sum(char_counts)

    segments = []
    t = 0.0
    for word, chars in zip(words, char_counts):
        dur = (chars / total_chars) * total_duration
        segments.append({
            "word": word,
            "start_time": round(t, 4),
            "end_time":   round(t + dur, 4),
        })
        t += dur

    return segments


def split_into_word_segments(word_boundary_events: list[dict]) -> list[dict]:
    """
    Convert edge-tts WordBoundary events into word-timing segments.

    Each event has:
      {"type": "WordBoundary", "offset": <100ns ticks>, "duration": <100ns ticks>, "text": "<word>"}

    Returns list of:
      {"word": str, "start_time": float (seconds), "end_time": float (seconds)}
    """
    TICKS_PER_SEC = 10_000_000  # edge-tts uses 100-nanosecond ticks

    segments = []
    for event in word_boundary_events:
        if event.get("type") != "WordBoundary":
            continue
        word = event.get("text", "").strip()
        if not word:
            continue
        start = event["offset"] / TICKS_PER_SEC
        end   = (event["offset"] + event["duration"]) / TICKS_PER_SEC
        segments.append({"word": word, "start_time": start, "end_time": end})

    return segments


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

    def generate_with_boundaries(self, text: str, output_path: str) -> tuple[str, list[dict]]:
        """
        Generate speech and return (audio_path, word_boundary_events).

        word_boundary_events: list of edge-tts WordBoundary dicts with
          {type, offset (100ns ticks), duration (100ns ticks), text}
        """
        import edge_tts

        word_events: list[dict] = []

        async def _run():
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
            chunks = []
            async for event in communicate.stream():
                if event["type"] == "audio":
                    chunks.append(event["data"])
                elif event["type"] == "WordBoundary":
                    word_events.append(event)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(b"".join(chunks))

        asyncio.run(_run())
        return output_path, word_events


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
        self, text: str, output_path: str, max_chars: int = 500,
        capture_boundaries: bool = False,
    ) -> str | tuple[str, list[dict]] | None:
        """
        Generate TTS audio for a text segment.

        Args:
            text: The text to convert to speech
            output_path: Where to save the MP3 file
            max_chars: Maximum character limit for TTS
            capture_boundaries: If True (and provider is EdgeTTS), also return
                                 word boundary events as (path, events) tuple.

        Returns:
            The output path if successful (or (path, events) if capture_boundaries),
            None otherwise.
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
            if capture_boundaries and isinstance(self.provider, EdgeTTS):
                path, events = self.provider.generate_with_boundaries(cleaned, output_path)
                return path, events
            else:
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
        use_karaoke = isinstance(self.provider, EdgeTTS)

        # Title
        title_path = os.path.join(temp_dir, "title.mp3")
        result = self.generate_audio(post.title, title_path)
        if result:
            segments.append({
                "text": self.clean_text(post.title),
                "audio_path": result,
                "type": "title",
            })

        # Body (always included — generate_audio handles truncation via max_chars)
        if post.body and len(post.body.strip()) > 0:
            body_text = post.body.strip()
            body_path = os.path.join(temp_dir, "body.mp3")
            result = self.generate_audio(
                body_text, body_path, capture_boundaries=use_karaoke
            )
            if result is not None:
                if use_karaoke and isinstance(result, tuple):
                    audio_path_b, word_events_b = result
                    word_segments_b = split_into_word_segments(word_events_b)
                else:
                    audio_path_b = result
                    word_segments_b = []
                if not word_segments_b:
                    cleaned_b = self.clean_text(body_text)
                    word_segments_b = estimate_word_segments(audio_path_b, cleaned_b)
                segments.append({
                    "text": self.clean_text(body_text),
                    "audio_path": audio_path_b,
                    "type": "body",
                    "word_segments": word_segments_b,
                })

        # Comments — capture word boundaries for karaoke captions.
        for i, comment in enumerate(post.comments):
            comment_path = os.path.join(temp_dir, f"comment_{i}.mp3")
            result = self.generate_audio(
                comment.body, comment_path, capture_boundaries=use_karaoke
            )
            if result is None:
                continue
            if use_karaoke and isinstance(result, tuple):
                audio_path, word_events = result
                word_segments = split_into_word_segments(word_events)
            else:
                audio_path = result
                word_segments = []

            # If WordBoundary events were empty (edge-tts 7.x), use estimated timing
            if not word_segments:
                cleaned = self.clean_text(comment.body)
                word_segments = estimate_word_segments(audio_path, cleaned)

            segments.append({
                "text": self.clean_text(comment.body),
                "audio_path": audio_path,
                "type": "comment",
                "author": comment.author,
                "score": comment.score,
                "word_segments": word_segments,
            })

        console.print(
            f"  [green][OK][/green] Generated {len(segments)} audio segments"
        )
        return segments
