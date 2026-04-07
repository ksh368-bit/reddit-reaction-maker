"""
Card renderer:
  - Title segments  → Reddit dark card (original style)
  - Comment segments → Bold white text + black outline, lower-center overlay
"""

import os
import re
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rich.console import Console

console = Console()


def detect_keyword(text: str) -> str | None:
    """Extract a short highlight keyword: dollar amounts → K/M numbers → large numbers → percentages."""
    m = re.search(r'\$\s*[\d,]+(?:\.\d+)?\s*[KMBkmb]?', text)
    if m:
        kw = re.sub(r'\s+', '', m.group()).upper()
        return kw if len(kw) <= 10 else None
    m = re.search(r'\b\d+(?:\.\d+)?\s*[KMBkmb]\b', text, re.IGNORECASE)
    if m:
        return re.sub(r'\s+', '', m.group()).upper()
    m = re.search(r'\b\d{1,3}(?:,\d{3})+\b', text)
    if m:
        return m.group()
    m = re.search(r'\b\d+\s*%', text)
    if m:
        return re.sub(r'\s+', '', m.group())
    return None


COLORS = {
    "card_bg":     (26, 26, 27),
    "card_border": (52, 53, 54),
    "title_text":  (215, 218, 220),
    "body_text":   (215, 218, 220),
    "meta_text":   (129, 131, 132),
    "upvote":      (255, 69, 0),
    "score_text":  (215, 218, 220),
    "divider":     (52, 53, 54),
}

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)


# ──────────────────────────────────────────────
#  Font helpers
# ──────────────────────────────────────────────

def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    for f in [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def _load_bold_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if font_path and os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)
    for f, idx in [
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 7),
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
        ("C:/Windows/Fonts/arialbd.ttf", 0),
    ]:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size, index=idx)
            except Exception:
                return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _format_score(score: int) -> str:
    return f"{score / 1000:.1f}k" if score >= 1000 else str(score)


def _draw_upvote_icon(draw, x, y, size, color):
    half = size // 2
    draw.polygon([(x + half, y), (x, y + size), (x + size, y + size)], fill=color)


def _draw_score_row(draw, x, y, score_str, comments_str,
                    score_font, score_height,
                    upvote_color, score_text_color, meta_color):
    icon_size = max(10, score_height - 4)
    icon_y = y + (score_height - icon_size) // 2
    _draw_upvote_icon(draw, x, icon_y, icon_size, upvote_color)
    x += icon_size + 8
    draw.text((x, y), score_str, fill=score_text_color, font=score_font)
    if comments_str:
        tmp = Image.new("RGB", (400, 60))
        sw = ImageDraw.Draw(tmp).textbbox((0, 0), score_str, font=score_font)
        x += sw[2] - sw[0] + 20
        draw.text((x, y), f"· {comments_str} cmts", fill=meta_color, font=score_font)


# ──────────────────────────────────────────────
#  1. Reddit dark card  (title segments)
# ──────────────────────────────────────────────

def render_title_card(
    title: str,
    body: str = "",
    author: str = "",
    score: int = 0,
    subreddit: str = "",
    card_width: int = 800,
    font_path: str | None = None,
    font_size: int = 48,
    num_comments: int = 0,
    video_height: int = 1920,
) -> Image.Image:
    padding = 36
    content_width = card_width - padding * 2

    title_font = _load_bold_font(font_path, font_size)
    body_font  = _load_font(font_path, max(20, int(font_size * 0.72)))
    meta_font  = _load_font(font_path, max(18, font_size // 2))
    score_font = _load_bold_font(font_path, max(20, font_size // 2))

    tmp = Image.new("RGB", (card_width, 100))
    tmp_draw = ImageDraw.Draw(tmp)

    meta_text   = f"r/{subreddit}  ·  u/{author}"
    meta_bbox   = tmp_draw.textbbox((0, 0), meta_text, font=meta_font)
    meta_height = meta_bbox[3] - meta_bbox[1]

    title_lines  = _wrap_text(tmp_draw, title, title_font, content_width)
    line_height  = int(font_size * 1.35)
    title_height = len(title_lines) * line_height

    # Body text (max 5 lines, truncated at 400 chars)
    body_lines = []
    body_line_h = int(font_size * 0.72 * 1.4)
    if body and body.strip():
        preview = body.strip()[:400]
        if len(body.strip()) > 400:
            preview = preview.rsplit(" ", 1)[0] + "…"
        body_lines = _wrap_text(tmp_draw, preview, body_font, content_width)[:5]
    body_height = len(body_lines) * body_line_h + (16 if body_lines else 0)

    score_str    = _format_score(score)
    comments_str = _format_score(num_comments) if num_comments > 0 else ""
    score_bbox   = tmp_draw.textbbox((0, 0), score_str, font=score_font)
    score_height = score_bbox[3] - score_bbox[1]

    card_height = max(300,
        padding + meta_height + 20 + title_height + 10 + body_height + 15 + score_height + padding)

    shadow_size = 6
    total_w = card_width + shadow_size
    total_h = card_height + shadow_size
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [shadow_size, shadow_size, card_width + shadow_size, card_height + shadow_size],
        radius=16, fill=(0, 0, 0, 140))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(3)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(3)))

    card = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle(
        [0, 0, card_width, card_height], radius=16, fill=COLORS["card_bg"])
    img.paste(card, (0, 0), card)

    draw = ImageDraw.Draw(img)
    y = padding
    draw.text((padding, y), meta_text, fill=COLORS["meta_text"], font=meta_font)
    y += meta_height + 20

    for line in title_lines:
        draw.text((padding, y), line, fill=COLORS["title_text"], font=title_font)
        y += line_height
    y += 10

    # Body text block
    if body_lines:
        y += 6
        for line in body_lines:
            draw.text((padding, y), line, fill=COLORS["body_text"], font=body_font)
            y += body_line_h
        y += 10

    draw.line([(padding, y), (card_width - padding, y)], fill=COLORS["divider"], width=1)
    y += 15

    _draw_score_row(draw, padding, y,
                    score_str=score_str, comments_str=comments_str,
                    score_font=score_font, score_height=score_height,
                    upvote_color=COLORS["upvote"], score_text_color=COLORS["score_text"],
                    meta_color=COLORS["meta_text"])
    return img


# ──────────────────────────────────────────────
#  2. Bold text overlay  (comment segments)
# ──────────────────────────────────────────────

def render_comment_card(
    body: str,
    author: str = "",
    score: int = 0,
    card_width: int = 1080,
    font_path: str | None = None,
    font_size: int = 165,
    video_height: int = 1920,
) -> Image.Image:
    """
    Full-canvas transparent overlay.
    Keyword: large ALL-CAPS white text on black rounded-rect, centered.
    Fallback (no keyword): bold white text with black outline, lower-center.
    """
    img  = Image.new("RGBA", (card_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    keyword = detect_keyword(body)

    if keyword:
        # ── Keyword style: black pill background + white ALL-CAPS text ──
        kw_text = keyword.upper()
        kw_size = min(160, int(card_width * 0.148))
        kw_font = _load_bold_font(font_path, kw_size)

        kb   = draw.textbbox((0, 0), kw_text, font=kw_font)
        tw   = kb[2] - kb[0]
        th   = kb[3] - kb[1]
        h_pad, v_pad = 48, 28
        box_w = tw + h_pad * 2
        box_h = th + v_pad * 2
        bx = (card_width - box_w) // 2
        by = video_height // 2 - box_h // 2

        # Black rounded rectangle background
        draw.rounded_rectangle([bx, by, bx + box_w, by + box_h],
                                radius=20, fill=(0, 0, 0, 220))
        # White text centered in the box
        tx = bx + h_pad - kb[0]
        ty = by + v_pad - kb[1]
        draw.text((tx, ty), kw_text, font=kw_font, fill=WHITE)

    else:
        # ── Fallback: multi-line bold text with black outline, lower-center ──
        font    = _load_bold_font(font_path, font_size)
        padding = 72
        content_width = card_width - padding * 2

        lines   = _wrap_text(draw, body, font, content_width)[:5]
        line_h  = int(font_size * 1.45)
        block_h = len(lines) * line_h

        y_center = int(video_height * 0.72)
        y = y_center - block_h // 2

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw   = bbox[2] - bbox[0]
            x    = (card_width - lw) // 2 - bbox[0]
            draw.text((x, y), line, font=font, fill=WHITE,
                      stroke_width=5, stroke_fill=BLACK)
            y += line_h

    return img


# ──────────────────────────────────────────────
#  Batch renderer
# ──────────────────────────────────────────────

def render_cards_for_post(
    post,
    segments: list[dict],
    output_dir: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
    title_font_size: int = 48,
    comment_font_size: int = 60,
) -> list[dict]:
    card_width = int(video_width * 0.88)
    os.makedirs(output_dir, exist_ok=True)

    for i, seg in enumerate(segments):
        if seg.get("type") == "title":
            for s in segments:
                if s.get("type") == "title":
                    s["author"]       = getattr(post, "author", "")
                    s["score"]        = getattr(post, "score", 0)
                    s["subreddit"]    = getattr(post, "subreddit", "")
                    s["num_comments"] = getattr(post, "num_comments", 0)
                    break
            card_img = render_title_card(
                title=seg["text"],
                body=getattr(post, "body", ""),
                author=seg.get("author", ""),
                score=seg.get("score", 0),
                subreddit=seg.get("subreddit", ""),
                card_width=card_width,
                font_path=font_path,
                font_size=title_font_size,
                num_comments=seg.get("num_comments", 0),
                video_height=video_height,
            )
        else:
            card_img = render_comment_card(
                body=seg["text"],
                author=seg.get("author", ""),
                score=seg.get("score", 0),
                card_width=video_width,
                font_path=font_path,
                font_size=comment_font_size,
                video_height=video_height,
            )

        card_path = os.path.join(output_dir, f"card_{i:02d}.png")
        card_img.save(card_path, "PNG")
        seg["card_path"] = card_path

    console.print(f"  [green][OK][/green] Rendered {len(segments)} card(s)")
    return segments
