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


def extract_hook_text(title: str) -> str:
    """
    Extract the most impactful hook phrase from a Reddit post title.

    Strips AITA/WIBTA/Am I preambles and returns the transgression/action
    part — the first thing viewers should see in the opening hook.

    Examples:
      "AITA for kicking out my sister after she stole $5000"
        → "kicking out my sister after she stole $5000"
      "WIBTA if I refused to attend my brother's wedding"
        → "I refused to attend my brother's wedding"
    """
    # Patterns to strip from the start (case-insensitive)
    preambles = [
        r"^AITA\s+for\s+",
        r"^AITA\s+",
        r"^WIBTA\s+if\s+",
        r"^WIBTA\s+for\s+",
        r"^WIBTA\s+",
        r"^Am\s+I\s+the\s+asshole\s+for\s+",
        r"^Am\s+I\s+the\s+asshole\s+",
        r"^Am\s+I\s+wrong\s+for\s+",
        r"^Am\s+I\s+wrong\s+",
        r"^Am\s+I\s+being\s+",
        r"^Am\s+I\s+",
    ]
    text = title.strip()
    for pattern in preambles:
        cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
        if cleaned and cleaned != text:
            text = cleaned
            break

    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]

    return text or title


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
#  2. Opening hook card  (first frame, 0-3s)
# ──────────────────────────────────────────────

def render_hook_card(
    title: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
) -> Image.Image:
    """
    Full-canvas RGBA overlay for the opening hook (first 0-3 seconds).

    Displays the most compelling part of the title in large centered text
    with a semi-transparent dark background strip — grabs attention before
    the Reddit card appears.

    Layout:
      - Dark gradient strip in upper-center
      - Large bold white text with black outline
      - Optional accent line below text
    """
    img  = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 120
    font      = _load_bold_font(font_path, font_size)
    padding   = 60
    content_w = video_width - padding * 2

    hook_text = extract_hook_text(title)
    lines   = _wrap_text(draw, hook_text, font, content_w)[:3]
    line_h  = int(font_size * 1.45)
    block_h = len(lines) * line_h

    # Dark semi-transparent background strip
    strip_top = video_height // 2 - block_h // 2 - 40
    strip_h   = block_h + 80
    strip = Image.new("RGBA", (video_width, strip_h), (0, 0, 0, 170))
    img.paste(strip, (0, strip_top), strip)

    # Text
    y = strip_top + 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x  = (video_width - lw) // 2 - bbox[0]
        draw.text((x, y), line, font=font, fill=WHITE,
                  stroke_width=4, stroke_fill=BLACK)
        y += line_h

    # Orange accent line below text
    line_y = strip_top + strip_h - 8
    draw.rectangle([padding, line_y, video_width - padding, line_y + 5],
                   fill=(255, 69, 0, 220))

    return img


# ──────────────────────────────────────────────
#  3. Bold text overlay  (comment segments)
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
#  4. Chunk caption overlay  (3-4 words, active word highlighted)
# ──────────────────────────────────────────────

HIGHLIGHT_COLOR = (255, 184, 0, 255)   # yellow-orange highlight box
HIGHLIGHT_TEXT  = (0, 0, 0, 255)       # black text on highlight


def render_caption_chunk(
    words: list[str],
    active_idx: int,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
    font_size: int = 85,
) -> Image.Image:
    """
    Full-canvas RGBA overlay showing 3 words as a chunk (MrBeast/viral style).

    - Active word: yellow/orange rounded-rect highlight with glow
    - Inactive words: white text with black stroke
    - Dark semi-transparent backing strip behind entire caption block
      (ensures readability over any background video)
    - Position: lower-center (~65% down frame)
    """
    img  = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font      = _load_bold_font(font_path, font_size)
    h_gap     = 24
    v_pad     = 16
    h_pad     = 20
    line_h    = int(font_size * 1.4)
    strip_v   = 24          # vertical padding for dark backing strip

    # Measure each word (ALL CAPS for punch)
    upper_words = [w.upper() for w in words]
    word_widths = []
    word_heights = []
    for w in upper_words:
        bb = draw.textbbox((0, 0), w, font=font)
        word_widths.append(bb[2] - bb[0])
        word_heights.append(bb[3] - bb[1])

    # Wrap into lines if total width exceeds frame
    max_line_w = video_width - 80
    lines: list[list[int]] = []
    current_line: list[int] = []
    current_w = 0

    for i, ww in enumerate(word_widths):
        needed = ww + (h_pad * 2 if i == active_idx else 0)
        spacer = h_gap if current_line else 0
        if current_w + spacer + needed > max_line_w and current_line:
            lines.append(current_line)
            current_line = [i]
            current_w = needed
        else:
            current_line.append(i)
            current_w += spacer + needed
    if current_line:
        lines.append(current_line)

    block_h = len(lines) * line_h
    y_anchor = int(video_height * 0.65) - block_h // 2

    # ── Dark semi-transparent backing strip (full-width) ──────────────────
    strip_top = y_anchor - strip_v
    strip_bot = y_anchor + block_h + strip_v
    backing = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    ImageDraw.Draw(backing).rectangle(
        [0, strip_top, video_width, strip_bot],
        fill=(0, 0, 0, 140),   # semi-transparent black
    )
    img = Image.alpha_composite(img, backing)
    draw = ImageDraw.Draw(img)

    # ── Draw words ──────────────────────────────────────────────────────────
    y_start = y_anchor
    for line_indices in lines:
        line_w = sum(
            word_widths[i] + (h_pad * 2 if i == active_idx else 0)
            for i in line_indices
        ) + h_gap * (len(line_indices) - 1)

        x = (video_width - line_w) // 2

        for i in line_indices:
            w_text = upper_words[i]
            ww     = word_widths[i]
            wh     = word_heights[i]
            bb     = draw.textbbox((0, 0), w_text, font=font)

            if i == active_idx:
                box_w = ww + h_pad * 2
                box_h = wh + v_pad * 2
                bx = x
                by = y_start + (line_h - box_h) // 2

                # ── Glow: blurred copy of the highlight box behind it ──────
                glow_layer = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
                glow_draw  = ImageDraw.Draw(glow_layer)
                glow_spread = 18
                glow_draw.rounded_rectangle(
                    [bx - glow_spread, by - glow_spread,
                     bx + box_w + glow_spread, by + box_h + glow_spread],
                    radius=28, fill=(255, 184, 0, 110),
                )
                glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(14))
                img = Image.alpha_composite(img, glow_blurred)
                draw = ImageDraw.Draw(img)

                # ── Solid highlight box ────────────────────────────────────
                draw.rounded_rectangle(
                    [bx, by, bx + box_w, by + box_h],
                    radius=14, fill=HIGHLIGHT_COLOR,
                )
                tx = bx + h_pad - bb[0]
                ty = by + v_pad - bb[1]
                draw.text((tx, ty), w_text, font=font, fill=HIGHLIGHT_TEXT)
                x += box_w + h_gap
            else:
                tx = x - bb[0]
                ty = y_start + (line_h - wh) // 2 - bb[1]
                draw.text((tx, ty), w_text, font=font, fill=WHITE,
                          stroke_width=4, stroke_fill=BLACK)
                x += ww + h_gap

        y_start += line_h

    return img


# ──────────────────────────────────────────────
#  5. Word-level caption overlay  (legacy single-word)
# ──────────────────────────────────────────────

def render_word_caption(
    word: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
    font_size: int = 165,
) -> Image.Image:
    """
    Full-canvas RGBA overlay showing a single word in black rounded-rect box.
    Used for word-by-word caption sync with edge-tts WordBoundary events.

    Same visual style as the keyword box in render_comment_card.
    """
    img  = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    text    = word.upper()
    kw_font = _load_bold_font(font_path, font_size)

    kb   = draw.textbbox((0, 0), text, font=kw_font)
    tw   = kb[2] - kb[0]
    th   = kb[3] - kb[1]
    h_pad, v_pad = 52, 32
    box_w = tw + h_pad * 2
    box_h = th + v_pad * 2

    # Cap box width to 90% of frame
    if box_w > video_width * 0.9:
        scale   = (video_width * 0.9) / box_w
        kw_font = _load_bold_font(font_path, int(font_size * scale))
        kb   = draw.textbbox((0, 0), text, font=kw_font)
        tw   = kb[2] - kb[0]
        th   = kb[3] - kb[1]
        box_w = tw + h_pad * 2
        box_h = th + v_pad * 2

    bx = (video_width  - box_w) // 2
    by = video_height  // 2 - box_h // 2

    draw.rounded_rectangle([bx, by, bx + box_w, by + box_h],
                            radius=24, fill=(0, 0, 0, 220))
    draw.text((bx + h_pad - kb[0], by + v_pad - kb[1]),
              text, font=kw_font, fill=WHITE)

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
        if seg.get("type") == "hook":
            # money quote displayed as hook card (same visual as static hook overlay)
            card_img = render_hook_card(
                seg["text"],
                video_width=video_width,
                video_height=video_height,
                font_path=font_path,
            )
        elif seg.get("type") == "title":
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
