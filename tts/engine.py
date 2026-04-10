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


def count_syllables(word: str) -> int:
    """
    Estimate syllable count for a word — correlates with TTS speech duration.

    Uses vowel-group counting: each cluster of consecutive vowels = 1 syllable.
    Silent trailing 'e' is not counted. Minimum 1 syllable per word.

    This is far more accurate than character count for proportional
    word-timing estimation.
    """
    word = word.lower().strip(".,!?;:\"'()-")
    if not word:
        return 1

    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel

    # Silent trailing 'e' — subtract if word ends in vowel-consonant-e
    if (len(word) > 2
            and word[-1] == "e"
            and word[-2] not in vowels
            and word[-3] in vowels
            and count > 1):
        count -= 1

    return max(1, count)


def whisper_word_segments(
    audio_path: str,
    text: str = "",
    fallback_duration: float = 0.0,
) -> list[dict]:
    """
    Extract exact word-level timestamps from a TTS audio file using
    faster-whisper (tiny model, CPU, int8).

    TTS audio is clean with no background noise, so tiny model gives
    near-perfect accuracy while being fast (<1s for a 10s clip).

    Falls back to estimate_word_segments() if:
    - faster_whisper is not installed
    - audio file doesn't exist or can't be read
    - whisper returns no segments

    Returns list of {word, start_time, end_time} dicts.
    """
    try:
        if not audio_path or not Path(audio_path).exists():
            raise FileNotFoundError(audio_path)

        from faster_whisper import WhisperModel

        # Load model (cached after first call)
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            audio_path,
            word_timestamps=True,
            language="en",
            beam_size=1,       # fast, accuracy sufficient for clean TTS
            vad_filter=False,  # don't skip any audio segments
        )

        result = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    word = w.word.strip()
                    if word:
                        result.append({
                            "word": word,
                            "start_time": round(w.start, 4),
                            "end_time":   round(w.end, 4),
                        })

        if result:
            return result

    except ImportError:
        pass  # faster-whisper not installed — fall through to estimate
    except Exception:
        pass  # any other error — fall through to estimate

    # Fallback: syllable-based estimation
    return estimate_word_segments(audio_path, text, fallback_duration)


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

    # --- Step 1: syllable-proportional base durations ---
    syllable_counts = [count_syllables(w) for w in words]
    total_syllables = sum(syllable_counts)
    base_durations = [(syl / total_syllables) * total_duration
                      for syl in syllable_counts]

    # --- Step 2: punctuation pause bonus ---
    # TTS pauses naturally after clause-ending punctuation; add extra time
    PUNCT_BONUS = 0.12   # seconds added for words ending in , . ! ?
    punct_bonus = [PUNCT_BONUS if w[-1] in ",.!?" else 0.0 for w in words]

    # --- Step 3: minimum floor so highlight is always perceptible ---
    MIN_DUR = 0.18       # ~5 frames at 30fps — minimum to register a highlight
    raw_durations = [max(MIN_DUR, b + p)
                     for b, p in zip(base_durations, punct_bonus)]

    # --- Step 4: rescale to preserve total_duration exactly ---
    raw_total = sum(raw_durations)
    scale = total_duration / raw_total if raw_total > 0 else 1.0
    final_durations = [d * scale for d in raw_durations]

    segments = []
    t = 0.0
    for word, dur in zip(words, final_durations):
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
    def prepare_tts_text(cls, text: str, max_chars: int = 500) -> str:
        """
        Return the exact text that will be sent to TTS (cleaned + truncated).

        This is the single source of truth for what TTS reads — use it
        whenever building word_segments so screen text matches audio exactly.
        """
        cleaned = cls.clean_text(text)
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars].rsplit(" ", 1)[0] + "..."
        return cleaned

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean text for TTS: remove emojis, URLs, preamble filler, excessive whitespace."""
        # ── 1. Strip EDIT/UPDATE sections (everything from the marker onward) ──
        text = re.sub(r"\bEDIT\s*\d*\s*:", "EDITMARKER", text, flags=re.IGNORECASE)
        text = re.sub(r"\bUPDATE\s*\d*\s*:", "EDITMARKER", text, flags=re.IGNORECASE)
        if "EDITMARKER" in text:
            text = text[: text.index("EDITMARKER")].strip()

        # ── 2. Strip filler preamble lines (line-by-line) ──
        _PREAMBLE = re.compile(
            r"^("
            r"throwaway\b.*"
            r"|long\s+post.*"
            r"|sorry.*long\s+post.*"
            r"|for\s+context[,.]?.*"
            r"|not\s+sure\s+if\s+(this\s+is\s+)?the\s+right\s+place.*"
            r")\s*$",
            re.IGNORECASE,
        )
        lines = text.splitlines()
        lines = [ln for ln in lines if not _PREAMBLE.match(ln.strip())]
        text = "\n".join(lines)

        # ── 3. Remove URLs ──
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
        cleaned = self.prepare_tts_text(text, max_chars)
        if not cleaned:
            console.print("[yellow]  Skipped empty text segment[/yellow]")
            return None

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

        from utils.hook_extractor import extract_money_quote, extract_conflict_core
        from utils.verdict_extractor import extract_verdict, VERDICT_TEXT

        # ── Hook: money quote from body as TTS first utterance ──
        # Viewer hears (and sees) the most shocking sentence first — mid-conflict start.
        if post.body and len(post.body.strip()) > 30:
            quote = extract_money_quote(self.clean_text(post.body))
            if quote:
                hook_path = os.path.join(temp_dir, "hook.mp3")
                result_h = self.generate_audio(quote, hook_path, capture_boundaries=use_karaoke)
                if result_h is not None:
                    a_path_h = result_h[0] if isinstance(result_h, tuple) else result_h
                    ws_h     = (result_h[1] if isinstance(result_h, tuple) else []) or []
                    ws_h     = ws_h or whisper_word_segments(a_path_h, quote)
                    segments.append({
                        "type": "hook",
                        "text": quote,
                        "audio_path": a_path_h,
                        "word_segments": ws_h,
                    })

        # Title
        title_path = os.path.join(temp_dir, "title.mp3")
        result = self.generate_audio(post.title, title_path)
        if result:
            segments.append({
                "text": self.clean_text(post.title),
                "audio_path": result,
                "type": "title",
            })

        # Body — cut at conflict peak (not naive 500-char slice)
        if post.body and len(post.body.strip()) > 0:
            body_text  = post.body.strip()
            body_path  = os.path.join(temp_dir, "body.mp3")
            body_clean = self.clean_text(body_text)
            tts_text_b = extract_conflict_core(body_clean, max_chars=500)
            result = self.generate_audio(
                tts_text_b, body_path, capture_boundaries=use_karaoke
            )
            if result is not None:
                if use_karaoke and isinstance(result, tuple):
                    audio_path_b, word_events_b = result
                    word_segments_b = split_into_word_segments(word_events_b)
                else:
                    audio_path_b = result
                    word_segments_b = []
                if not word_segments_b:
                    word_segments_b = whisper_word_segments(audio_path_b, tts_text_b)
                segments.append({
                    "text": tts_text_b,
                    "audio_path": audio_path_b,
                    "type": "body",
                    "word_segments": word_segments_b,
                })

            # ── Cliffhanger CTA for long posts (>1000 chars raw) ──
            # Research: long posts → 2-part series outperforms single Short
            if len(body_text) > 1000:
                cta_text = "Comment NTA or YTA below — and catch Part 2 for what happens next."
                cta_path = os.path.join(temp_dir, "cta.mp3")
                result_cta = self.generate_audio(cta_text, cta_path, capture_boundaries=use_karaoke)
                if result_cta:
                    if use_karaoke and isinstance(result_cta, tuple):
                        cta_audio, cta_word_events = result_cta
                        cta_word_segs = split_into_word_segments(cta_word_events)
                    else:
                        cta_audio = result_cta[0] if isinstance(result_cta, tuple) else result_cta
                        cta_word_segs = []

                    tts_text_cta = self.prepare_tts_text(cta_text)
                    if not cta_word_segs:
                        cta_word_segs = whisper_word_segments(cta_audio, tts_text_cta)

                    segments.append({
                        "type": "cta",
                        "text": tts_text_cta,
                        "audio_path": cta_audio,
                        "word_segments": cta_word_segs,
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

            tts_text_c = self.prepare_tts_text(comment.body)
            # Use whisper for exact timing; falls back to estimate if unavailable
            if not word_segments:
                word_segments = whisper_word_segments(audio_path, tts_text_c)

            segments.append({
                "text": tts_text_c,
                "audio_path": audio_path,
                "type": "comment",
                "author": comment.author,
                "score": comment.score,
                "word_segments": word_segments,
            })

        # ── Verdict Card ──
        # Skip when CTA is present (long post teases Part 2 instead of showing verdict).
        has_cta = post.body and len(post.body.strip()) > 1000
        if not has_cta and post.comments:
            verdict = extract_verdict(post.comments)
            if verdict:
                vtext = VERDICT_TEXT.get(verdict, verdict)
                v_path = os.path.join(temp_dir, "verdict.mp3")
                result_v = self.generate_audio(vtext, v_path)
                if result_v is not None:
                    a_path_v = result_v[0] if isinstance(result_v, tuple) else result_v
                    segments.append({
                        "type":          "verdict",
                        "verdict_label": verdict,
                        "text":          vtext,
                        "audio_path":    a_path_v,
                        "word_segments": [],   # static card — no karaoke
                    })

        console.print(
            f"  [green][OK][/green] Generated {len(segments)} audio segments"
        )
        return segments
