"""
Video composer - assembles background video, screenshot overlays,
TTS audio, and BGM into final Shorts video.

Uses the same approach as the original RedditVideoMakerBot:
- Pre-rendered PNG screenshots (from Playwright or Pillow cards)
- Scaled to ~45% of video width and centered
- Each screenshot shown in sync with its TTS audio clip
"""

import os
from pathlib import Path

import numpy as np
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
)
from moviepy.video.fx import CrossFadeIn
from rich.console import Console

from video.background import (
    setup_backgrounds,
    select_random_background,
    select_random_audio,
    get_random_start_time,
)
from video.screenshot import capture_post_screenshots

console = Console()


class VideoComposer:
    """Composes YouTube Shorts videos using screenshot overlay approach."""

    def __init__(self, config: dict):
        video_cfg = config.get("video", {})
        self.width = video_cfg.get("width", 1080)
        self.height = video_cfg.get("height", 1920)
        self.fps = video_cfg.get("fps", 30)
        self.max_duration = video_cfg.get("max_duration", 58)
        self.background_dir = video_cfg.get("background_dir", "assets/backgrounds")
        self.opacity = video_cfg.get("opacity", 0.7)

        # Screenshot scaling
        self.screenshot_scale = video_cfg.get("screenshot_scale", 0.90)

        # Font settings (passed to card renderer)
        self.font_path = video_cfg.get("font", None)
        self.title_font_size = video_cfg.get("title_font_size", 48)
        self.comment_font_size = video_cfg.get("comment_font_size", 40)

        # Background music settings
        self.bgm_enabled = video_cfg.get("bgm_enabled", True)
        self.bgm_volume = video_cfg.get("bgm_volume", 0.15)

        # Watermark overlay (e.g. "r/roblox")
        self.watermark = video_cfg.get("watermark", "")

        self.output_dir = config.get("output", {}).get("dir", "output")
        os.makedirs(self.output_dir, exist_ok=True)

        # Auto-download background assets on init
        self._backgrounds = setup_backgrounds(self.background_dir)

    def _create_background_clip(self, duration: float) -> VideoFileClip | ColorClip:
        """Create the background video clip, cropped to 9:16."""
        bg_path = select_random_background(self.background_dir)

        if bg_path is None:
            console.print("[yellow]No background video found. Using solid color.[/yellow]")
            return ColorClip(
                size=(self.width, self.height),
                color=(20, 20, 30),
                duration=duration,
            )

        console.print(f"  [dim]Background: {os.path.basename(bg_path)}[/dim]")
        video = VideoFileClip(bg_path)

        start_time = get_random_start_time(video.duration, duration)
        video = video.subclipped(start_time, start_time + duration)

        # Crop/resize to 9:16 portrait
        vid_w, vid_h = video.size
        target_ratio = self.width / self.height

        if vid_w / vid_h > target_ratio:
            new_w = int(vid_h * target_ratio)
            x_offset = (vid_w - new_w) // 2
            video = video.cropped(x1=x_offset, x2=x_offset + new_w)
        else:
            new_h = int(vid_w / target_ratio)
            y_offset = (vid_h - new_h) // 2
            video = video.cropped(y1=y_offset, y2=y_offset + new_h)

        video = video.resized((self.width, self.height))

        # Dim background for readability
        overlay = ColorClip(
            size=(self.width, self.height),
            color=(0, 0, 0),
            duration=duration,
        ).with_opacity(1 - self.opacity)

        return CompositeVideoClip([video, overlay])

    def _create_manga_background(self, post_title: str, duration: float, cards_dir: str):
        """Try to create a background from manga cover art via AniList."""
        try:
            from video.manga_cover import get_manga_background

            bg_path = get_manga_background(
                post_title, cards_dir, self.width, self.height
            )
            if bg_path:
                return ImageClip(bg_path, duration=duration)
        except Exception as e:
            console.print(f"  [dim]Manga cover background failed: {e}[/dim]")
        return None

    def _create_screenshot_clip(
        self, card_path: str, duration: float, seg_type: str = "comment"
    ) -> ImageClip | None:
        """
        Create an ImageClip from a card PNG.

        - title   : Reddit dark card, scaled and centered in upper half
        - comment : full-canvas transparent overlay, placed at (0, 0)
        """
        if not card_path or not os.path.exists(card_path):
            return None

        try:
            img_clip = ImageClip(card_path, duration=duration)

            if seg_type == "title":
                # Scale to fit width, pin to top of screen
                img_w, img_h = img_clip.size
                target_w = int(self.width * self.screenshot_scale)
                if img_w > target_w:
                    img_clip = img_clip.resized(target_w / img_w)
                img_w, img_h = img_clip.size
                x = (self.width - img_w) // 2
                y = int(self.height * 0.04)   # ~4% from top
                return img_clip.with_position((x, y))
            else:
                # Full-canvas transparent overlay
                return img_clip.with_position((0, 0))

        except Exception as e:
            console.print(f"  [yellow]Card clip error: {e}[/yellow]")
            return None

    def _create_progress_bar(self, total_duration: float) -> VideoClip:
        """Create a progress bar clip that fills left-to-right over total_duration."""
        bar_height = 10
        width = self.width

        def make_frame(t):
            progress = min(t / total_duration, 1.0)
            frame = np.full((bar_height, width, 3), [34, 34, 34], dtype=np.uint8)
            fill_w = max(0, int(progress * width))
            if fill_w > 0:
                frame[:, :fill_w] = [255, 69, 0]
            return frame

        bar = VideoClip(make_frame, duration=total_duration)
        return bar.with_position((0, self.height - bar_height))

    def _create_watermark_clip(
        self, total_duration: float, temp_dir: str
    ) -> ImageClip | None:
        """Create a semi-transparent watermark text overlay (top-right corner)."""
        if not self.watermark:
            return None

        try:
            from PIL import Image, ImageDraw
            from video.card_renderer import _load_font

            font = _load_font(self.font_path, 28)

            # Measure text on a temp canvas
            tmp = Image.new("RGBA", (400, 60), (0, 0, 0, 0))
            tmp_draw = ImageDraw.Draw(tmp)
            bbox = tmp_draw.textbbox((0, 0), self.watermark, font=font)
            w = bbox[2] - bbox[0] + 20
            h = bbox[3] - bbox[1] + 10

            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 5), self.watermark, fill=(255, 255, 255, 153), font=font)

            path = os.path.join(temp_dir, "_watermark.png")
            img.save(path, "PNG")

            clip = ImageClip(path, duration=total_duration)
            x = self.width - w - 20
            y = 20
            return clip.with_position((x, y))

        except Exception as e:
            console.print(f"  [yellow]Watermark error: {e}[/yellow]")
            return None

    def _create_bgm_clip(self, duration: float) -> AudioFileClip | None:
        """Create a background music audio clip (volume-adjusted)."""
        if not self.bgm_enabled:
            return None

        audio_path = select_random_audio(self.background_dir)
        if audio_path is None:
            return None

        console.print(f"  [dim]BGM: {os.path.basename(audio_path)} (vol: {self.bgm_volume})[/dim]")

        try:
            bgm = AudioFileClip(audio_path)

            if bgm.duration >= duration:
                bgm = bgm.subclipped(0, duration)

            bgm = bgm.with_volume_scaled(self.bgm_volume)
            return bgm

        except Exception as e:
            console.print(f"  [yellow]BGM load error: {e}[/yellow]")
            return None

    def compose_video(
        self,
        post,
        segments: list[dict],
        output_filename: str | None = None,
    ) -> str | None:
        """
        Compose the final Shorts video using screenshot overlay approach.

        Pipeline (matching original RedditVideoMakerBot):
        1. Capture/render screenshot cards (PNG) for each segment
        2. Load TTS audio clips and calculate timing
        3. Create background video
        4. Overlay each screenshot centered, synced with audio
        5. Mix TTS + BGM audio
        6. Render to MP4
        """
        if not segments:
            console.print("[red]No audio segments to compose.[/red]")
            return None

        console.print(f"[cyan]Composing video for: {post.title[:50]}...[/cyan]")

        try:
            # ── Step 1: Capture screenshot cards ──
            cards_dir = os.path.join(self.output_dir, f"_cards_{post.id}")

            # Add post metadata to title segment for card rendering
            for seg in segments:
                if seg.get("type") == "title":
                    seg["author"] = getattr(post, "author", "Author")
                    seg["score"] = getattr(post, "score", 0)
                    seg["subreddit"] = getattr(post, "subreddit", "roblox")
                    seg["num_comments"] = getattr(post, "num_comments", 0)

            segments = capture_post_screenshots(
                post, segments, cards_dir, theme="dark",
                font_path=self.font_path,
                title_font_size=self.title_font_size,
                comment_font_size=self.comment_font_size,
                video_width=self.width,
                video_height=self.height,
            )

            # ── Step 2: Load audio and calculate timing ──
            audio_clips = []
            timing_info = []  # (start_time, audio_duration, display_duration, segment)
            current_time = 0.0
            gap = 0.2  # tight pacing between segments

            for seg in segments:
                audio = AudioFileClip(seg["audio_path"])
                clip_duration = audio.duration

                if current_time + clip_duration > self.max_duration:
                    audio.close()
                    break

                audio_clips.append(audio.with_start(current_time))
                # Display duration = audio duration + gap so card stays visible
                # during the silence between segments (no blank frames)
                timing_info.append((current_time, clip_duration, clip_duration + gap, seg))
                current_time += clip_duration + gap

            if not audio_clips:
                console.print("[red]No audio clips within duration limit.[/red]")
                return None

            total_duration = current_time - gap
            total_duration = min(total_duration, self.max_duration)
            total_duration = max(total_duration, 1.0)

            # ── Step 3: Create background ──
            # Try manga cover background first (for manga/manhwa posts)
            bg_clip = self._create_manga_background(post.title, total_duration, cards_dir)
            if bg_clip is None:
                bg_clip = self._create_background_clip(total_duration)

            # ── Step 4: Overlay screenshots synced with audio ──
            overlay_clips = []
            fade_in = 0.15  # seconds — quick fade-in to soften hard cuts

            for start, audio_dur, display_dur, seg in timing_info:
                card_path = seg.get("card_path")
                clamped_display = min(display_dur, total_duration - start)
                clip = self._create_screenshot_clip(
                    card_path, max(clamped_display, audio_dur),
                    seg_type=seg.get("type", "comment"),
                )

                if clip:
                    if start > 0:
                        clip = clip.with_effects([CrossFadeIn(fade_in)])
                    clip = clip.with_start(start)
                    overlay_clips.append(clip)

            # ── Step 5: Compose all layers ──
            progress_bar = self._create_progress_bar(total_duration)
            # Use actual post subreddit for watermark instead of config default
            post_subreddit = getattr(post, "subreddit", "")
            watermark_text = f"r/{post_subreddit}" if post_subreddit else self.watermark
            orig_watermark = self.watermark
            self.watermark = watermark_text
            watermark_clip = self._create_watermark_clip(total_duration, cards_dir)
            self.watermark = orig_watermark

            extra_clips = [progress_bar]
            if watermark_clip is not None:
                extra_clips.append(watermark_clip)

            final_video = CompositeVideoClip(
                [bg_clip] + overlay_clips + extra_clips,
                size=(self.width, self.height),
            )

            # ── Step 6: Mix audio ──
            tts_audio = CompositeAudioClip(audio_clips)

            bgm_clip = self._create_bgm_clip(total_duration)
            if bgm_clip:
                mixed_audio = CompositeAudioClip([tts_audio, bgm_clip.with_start(0)])
            else:
                mixed_audio = tts_audio

            final_video = final_video.with_audio(mixed_audio)
            final_video = final_video.with_duration(total_duration)

            # ── Step 7: Render ──
            if output_filename is None:
                from utils.text_cleaner import sanitize_filename
                output_filename = sanitize_filename(post.title[:80])

            output_path = os.path.join(self.output_dir, f"{output_filename}.mp4")

            console.print(f"  [dim]Rendering {total_duration:.1f}s video...[/dim]")
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                bitrate="8M",
                preset="medium",
                logger=None,
            )

            # Cleanup
            final_video.close()
            for ac in audio_clips:
                ac.close()
            if bgm_clip:
                bgm_clip.close()

            # Clean up card images
            import shutil
            shutil.rmtree(cards_dir, ignore_errors=True)

            file_size = os.path.getsize(output_path) / (1024 * 1024)
            console.print(
                f"  [green][OK][/green] Saved: {output_path} "
                f"({total_duration:.1f}s, {file_size:.1f}MB)"
            )
            return output_path

        except Exception as e:
            console.print(f"[red]Video composition error: {e}[/red]")
            import traceback
            traceback.print_exc()
            return None
