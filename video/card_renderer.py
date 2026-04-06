"""
Reddit-style card renderer using Pillow.

Generates PNG screenshot-like cards for each text segment,
matching the original RedditVideoMakerBot's approach of
overlaying pre-rendered images onto background video.
"""

import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

console = Console()


# Reddit dark theme colors
COLORS = {
    "card_bg": (26, 26, 27),         # Reddit dark card background
    "card_border": (52, 53, 54),     # Card border
    "title_text": (215, 218, 220),   # Post title (light grey)
    "body_text": (215, 218, 220),    # Body/comment text
    "meta_text": (129, 131, 132),    # Author, score (grey)
    "upvote": (255, 69, 0),          # Reddit orange for upvote
    "score_text": (215, 218, 220),   # Score number
    "divider": (52, 53, 54),         # Divider line
}


def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    """Load a font, falling back to system fonts."""
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)

    # Try common system fonts
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for font in candidates:
        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    return ImageFont.load_default(size)


def _load_bold_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    """Load a bold font variant."""
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)

    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/seguisb.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for font in candidates:
        if os.path.exists(font):
            return ImageFont.truetype(font, size)

    return _load_font(font_path, size)


def _wrap_text_to_width(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Wrap text to fit within a pixel width."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]


def render_title_card(
    title: str,
    author: str,
    score: int,
    subreddit: str,
    card_width: int = 800,
    font_path: str | None = None,
    font_size: int = 48,
) -> Image.Image:
    """
    Render a Reddit-style title card as PNG.

    Looks like:
    ┌─────────────────────────────┐
    │ r/roblox · u/author         │
    │                             │
    │  Title text here that       │
    │  wraps nicely               │
    │                             │
    │  ▲ 1.2k                     │
    └─────────────────────────────┘
    """
    padding = 36
    content_width = card_width - padding * 2

    # Fonts - sizes scale with title font_size
    title_font = _load_bold_font(font_path, font_size)
    meta_font = _load_font(font_path, max(18, font_size // 2))
    score_font = _load_bold_font(font_path, max(20, font_size // 2))

    # Pre-calculate text layout
    temp_img = Image.new("RGB", (card_width, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    # Meta line
    meta_text = f"r/{subreddit}  ·  u/{author}"
    meta_bbox = temp_draw.textbbox((0, 0), meta_text, font=meta_font)
    meta_height = meta_bbox[3] - meta_bbox[1]

    # Title lines
    title_lines = _wrap_text_to_width(temp_draw, title, title_font, content_width)
    line_height = int(font_size * 1.35)
    title_block_height = len(title_lines) * line_height

    # Score line
    score_str = _format_score(score)
    score_display = f"^  {score_str}"
    score_bbox = temp_draw.textbbox((0, 0), score_display, font=score_font)
    score_height = score_bbox[3] - score_bbox[1]

    # Calculate total card height
    card_height = (
        padding          # top padding
        + meta_height    # subreddit + author
        + 20             # gap
        + title_block_height  # title text
        + 25             # gap
        + score_height   # score
        + padding        # bottom padding
    )

    # Render card
    img = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Card background with rounded corners
    _draw_rounded_rect(draw, (0, 0, card_width, card_height), 16, COLORS["card_bg"])

    y = padding

    # Meta line (subreddit + author)
    draw.text((padding, y), meta_text, fill=COLORS["meta_text"], font=meta_font)
    y += meta_height + 20

    # Title text
    for line in title_lines:
        draw.text((padding, y), line, fill=COLORS["title_text"], font=title_font)
        y += line_height

    y += 10

    # Divider
    draw.line([(padding, y), (card_width - padding, y)], fill=COLORS["divider"], width=1)
    y += 15

    # Score
    draw.text((padding, y), "^", fill=COLORS["upvote"], font=score_font)
    draw.text((padding + 20, y), f" {score_str}", fill=COLORS["score_text"], font=score_font)

    return img


def render_comment_card(
    body: str,
    author: str,
    score: int,
    card_width: int = 800,
    font_path: str | None = None,
    font_size: int = 40,
) -> Image.Image:
    """
    Render a Reddit-style comment card as PNG.

    Looks like:
    ┌─────────────────────────────┐
    │ u/author · 245 points       │
    │                             │
    │  Comment text here that     │
    │  wraps to multiple lines    │
    │  if needed                  │
    │                             │
    │  ▲ 245                      │
    └─────────────────────────────┘
    """
    padding = 36
    content_width = card_width - padding * 2
    accent_bar_width = 5
    inner_padding = padding + accent_bar_width + 14

    # Fonts - sizes scale with font_size
    body_font = _load_font(font_path, font_size)
    meta_font = _load_font(font_path, max(18, font_size // 2))
    score_font = _load_bold_font(font_path, max(20, font_size // 2))

    # Pre-calculate
    temp_img = Image.new("RGB", (card_width, 100))
    temp_draw = ImageDraw.Draw(temp_img)

    # Meta
    meta_text = f"u/{author}"
    meta_bbox = temp_draw.textbbox((0, 0), meta_text, font=meta_font)
    meta_height = meta_bbox[3] - meta_bbox[1]

    # Body lines
    body_content_width = card_width - inner_padding - padding
    body_lines = _wrap_text_to_width(temp_draw, body, body_font, body_content_width)

    # Limit lines to prevent overflow (max ~10 lines for readability)
    max_lines = 10
    if len(body_lines) > max_lines:
        body_lines = body_lines[:max_lines]
        body_lines[-1] = body_lines[-1][:40] + "..."

    line_height = int(font_size * 1.4)
    body_block_height = len(body_lines) * line_height

    # Score
    score_str = _format_score(score)
    score_display = f"^  {score_str}"
    score_bbox = temp_draw.textbbox((0, 0), score_display, font=score_font)
    score_height = score_bbox[3] - score_bbox[1]

    # Card height
    card_height = (
        padding
        + meta_height
        + 16
        + body_block_height
        + 20
        + score_height
        + padding
    )

    # Render
    img = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Card background
    _draw_rounded_rect(draw, (0, 0, card_width, card_height), 16, COLORS["card_bg"])

    # Left accent bar (Reddit comment thread line)
    draw.rectangle(
        [padding, padding, padding + accent_bar_width, card_height - padding],
        fill=COLORS["card_border"],
    )

    y = padding

    # Author meta
    draw.text((inner_padding, y), meta_text, fill=COLORS["meta_text"], font=meta_font)
    y += meta_height + 16

    # Body text
    for line in body_lines:
        draw.text((inner_padding, y), line, fill=COLORS["body_text"], font=body_font)
        y += line_height

    y += 8

    # Score
    draw.text((inner_padding, y), "^", fill=COLORS["upvote"], font=score_font)
    draw.text((inner_padding + 18, y), f" {score_str}", fill=COLORS["score_text"], font=score_font)

    return img


def render_cards_for_post(
    post,
    segments: list[dict],
    output_dir: str,
    video_width: int = 1080,
    font_path: str | None = None,
    title_font_size: int = 48,
    comment_font_size: int = 40,
) -> list[dict]:
    """
    Render all cards for a post and save as PNG files.

    Returns segments list with 'card_path' added to each entry.
    """
    card_width = int(video_width * 0.88)  # 88% of video width for portrait
    os.makedirs(output_dir, exist_ok=True)

    for i, seg in enumerate(segments):
        seg_type = seg.get("type", "comment")

        if seg_type == "title":
            card_img = render_title_card(
                title=seg["text"],
                author=seg.get("author", "Author"),
                score=seg.get("score", 0),
                subreddit=seg.get("subreddit", "roblox"),
                card_width=card_width,
                font_path=font_path,
                font_size=title_font_size,
            )
        else:
            card_img = render_comment_card(
                body=seg["text"],
                author=seg.get("author", "Anonymous"),
                score=seg.get("score", 0),
                card_width=card_width,
                font_path=font_path,
                font_size=comment_font_size,
            )

        card_path = os.path.join(output_dir, f"card_{i:02d}.png")
        card_img.save(card_path, "PNG")
        seg["card_path"] = card_path

    console.print(f"  [green][OK][/green] Rendered {len(segments)} card image(s)")
    return segments


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _format_score(score: int) -> str:
    if score >= 1000:
        return f"{score / 1000:.1f}k"
    return str(score)


def _draw_rounded_rect(
    draw: ImageDraw.Draw,
    coords: tuple,
    radius: int,
    fill: tuple,
):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = coords
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)
