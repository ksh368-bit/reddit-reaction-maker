"""
Card renderer:
  - Title segments  → Reddit dark card (original style)
  - Comment segments → Bold white text + black outline, lower-center overlay
"""

import hashlib
import os
import re
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rich.console import Console
from utils.verdict_extractor import VERDICT_TEXT

console = Console()

# In-memory cache for rendered cards (session-scoped)
_CARD_CACHE = {}


def _get_cache_key(content: str, card_type: str, **kwargs) -> str:
    """Generate cache key from content and rendering parameters."""
    key_str = f"{card_type}:{content}:" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(key_str.encode()).hexdigest()


def _get_cached_card(cache_key: str) -> Image.Image | None:
    """Get card from cache if it exists."""
    return _CARD_CACHE.get(cache_key)


def _cache_card(cache_key: str, card: Image.Image) -> Image.Image:
    """Store card in cache and return it."""
    _CARD_CACHE[cache_key] = card
    return card


def clear_card_cache():
    """Clear the card cache (call at end of video generation)."""
    global _CARD_CACHE
    _CARD_CACHE.clear()


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
    """Extract a short highlight keyword: dollar amounts → K/M numbers →
    comma-separated large numbers → percentages → bare 3+ digit numbers."""
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
    # Bare 3+ digit numbers (e.g. "3000 games", "1500 items") — triggers only
    # for meaningfully large counts so small incidental numbers don't grab
    # the badge spot.
    m = re.search(r'\b\d{3,}\b', text)
    if m:
        return m.group()
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
#  3. CTA card (dedicated — avoids 165px comment fallback)
# ──────────────────────────────────────────────

def render_cta_card(
    text: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
) -> Image.Image:
    """
    CTA용 전용 카드: 60px 폰트, 다크 배킹 스트립, 하단 중앙.
    comment_card fallback(165px)을 피해 적정 크기로 렌더링.
    """
    img  = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 60
    font = _load_bold_font(font_path, font_size)
    padding = 80
    content_width = video_width - padding * 2

    lines = _wrap_text(draw, text, font, content_width)[:4]
    line_h  = int(font_size * 1.45)
    block_h = len(lines) * line_h

    y_center = int(video_height * 0.72)
    y = y_center - block_h // 2

    # 다크 반투명 배킹
    backing_pad = 24
    draw.rectangle(
        [0, y - backing_pad, video_width, y + block_h + backing_pad],
        fill=(0, 0, 0, 160),
    )

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x  = (video_width - lw) // 2 - bbox[0]
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=3, stroke_fill=(0, 0, 0, 255))
        y += line_h

    return img


# ──────────────────────────────────────────────
#  4. Bold text overlay  (comment segments)
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

    Uses in-memory cache to avoid re-rendering identical cards.
    """
    # Check cache
    cache_key = _get_cache_key(body, "comment", author=author, score=score,
                               card_width=card_width, font_size=font_size,
                               video_height=video_height)
    cached = _get_cached_card(cache_key)
    if cached:
        return cached.copy()  # Return a copy to avoid mutation

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

    # Cache and return
    return _cache_card(cache_key, img)


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
#  Verdict card
# ──────────────────────────────────────────────

_VERDICT_COLORS: dict[str, tuple[int, int, int]] = {
    "NTA":  (50,  205,  50),
    "YTA":  (220,  50,  50),
    "ESH":  (255, 140,   0),
    "NAH":  (100, 200, 255),
    "INFO": (180, 180, 180),
}


def render_verdict_card(verdict: str, video_width: int, video_height: int,
                        font_path: str | None = None) -> Image.Image:
    """Full-screen verdict reveal: large colored label + subtitle."""
    img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    backing = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 210))
    img = Image.alpha_composite(img, backing)
    draw = ImageDraw.Draw(img)

    color = _VERDICT_COLORS.get(verdict.upper(), (255, 255, 255))
    cx, cy = video_width // 2, video_height // 2

    # Large verdict label (e.g. "NTA")
    draw.text(
        (cx, cy - 60), verdict.upper(),
        font=_load_bold_font(font_path, 220),
        fill=color + (255,),
        anchor="mm",
        stroke_width=6,
        stroke_fill=(0, 0, 0, 255),
    )

    # Subtitle (e.g. "Not the asshole.")
    subtitle = VERDICT_TEXT.get(verdict.upper(), "")
    draw.text(
        (cx, cy + 130), subtitle,
        font=_load_font(font_path, 52),
        fill=(255, 255, 255, 230),
        anchor="mm",
        stroke_width=3,
        stroke_fill=(0, 0, 0, 200),
    )
    return img


# ──────────────────────────────────────────────
#  6. Dedicated thumbnail renderer
# ──────────────────────────────────────────────

_THUMB_EMOJI: dict[str, str] = {
    "steam": "🎮", "pcgaming": "🖥️", "gaming": "🎮", "consoles": "🎮",
    "videogaming": "🎮", "wow": "⚔️", "leagueoflegends": "⚔️",
    "amitheasshole": "😤", "relationship_advice": "💔", "tifu": "😬",
    "pettyrevenge": "😈", "maliciouscompliance": "🙃",
    "choosingbeggars": "🤦", "entitledpeople": "🙄", "justnoMIL": "😡",
    "askcarsales": "🚗", "askreddit": "🤔", "todayilearned": "💡",
    "manga": "📖", "manhwa": "📖", "anime": "🎬",
    "personalfinance": "💰", "investing": "📈",
    "programming": "💻", "python": "🐍", "javascript": "⚡",
    # Product / lifestyle
    "buyitforlife": "💡", "lifeprotips": "💡", "frugal": "💰",
    "mildlyinteresting": "✨", "showerthoughts": "🤯",
}

# (top_color, bottom_color, accent_color) per subreddit category
_THUMB_SCHEME: dict[str, tuple] = {
    "gaming":       ((12, 18, 45),  (4, 8, 22),   (255, 69,  0)),
    "aita":         ((35, 8,  8),   (12, 3,  3),  (220, 50,  50)),
    "relationship": ((22, 8,  35),  (8,  3,  18), (200, 100, 255)),
    "tech":         ((8,  25, 35),  (3,  10, 15), (0,  180, 255)),
    "finance":      ((8,  30, 12),  (3,  12, 5),  (50, 220,  80)),
    "default":      ((18, 18, 22),  (6,  6,  8),  (255, 200,  0)),
}

_GAMING_SUBS  = {"steam", "pcgaming", "gaming", "consoles", "videogaming", "wow", "leagueoflegends"}
_AITA_SUBS    = {"amitheasshole", "relationship_advice", "pettyrevenge",
                 "maliciouscompliance", "choosingbeggars", "entitledpeople", "justnoMIL"}
_TECH_SUBS    = {"programming", "learnprogramming", "webdev", "python", "javascript"}
_FINANCE_SUBS = {"personalfinance", "investing", "frugal"}


_TRAILING_PREPOSITIONS = {
    "for", "of", "in", "on", "at", "to", "with", "from", "over", "under",
    "by", "per",
}


def _strip_keyword_from_title(title: str, keyword: str | None) -> str:
    """Remove the keyword from title text (case-insensitive) and normalize spaces.

    Used when the keyword is shown separately as a large badge — prevents
    visual duplication between badge and title text.

    Grammar-safe: if the keyword is followed by a preposition (e.g.
    "$500 for rent"), stripping would orphan the preposition. In that case
    we keep the original title to preserve readability.
    """
    if not keyword:
        return title
    # Check if keyword is mid-sentence followed by a preposition. If so,
    # removing it would leave awkward grammar ("...pay my roommate for rent").
    after_match = re.search(
        re.escape(keyword) + r"\s+(\w+)", title, flags=re.IGNORECASE
    )
    if after_match and after_match.group(1).lower() in _TRAILING_PREPOSITIONS:
        return title
    # Safe to strip
    pattern = re.escape(keyword)
    cleaned = re.sub(pattern, "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
    return cleaned or title


_APPLE_COLOR_EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
_EMOJI_NATIVE_SIZE = 160  # Apple Color Emoji only loads at specific bitmap sizes


def _render_color_emoji(emoji_char: str, target_size: int) -> Image.Image | None:
    """Render a color emoji at target_size px. Returns None if unavailable."""
    if not os.path.exists(_APPLE_COLOR_EMOJI):
        return None
    try:
        font = ImageFont.truetype(_APPLE_COLOR_EMOJI, _EMOJI_NATIVE_SIZE)
    except OSError:
        return None
    # Render to an oversized canvas at native bitmap size, then scale down
    canvas = Image.new("RGBA", (_EMOJI_NATIVE_SIZE + 40, _EMOJI_NATIVE_SIZE + 40),
                       (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 0), emoji_char, font=font, embedded_color=True)
    # Crop to content bbox for tight placement
    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    # Resize to target
    if target_size != canvas.size[0]:
        canvas = canvas.resize(
            (target_size, int(canvas.size[1] * target_size / canvas.size[0])),
            Image.Resampling.LANCZOS,
        )
    return canvas


def _make_gradient(width: int, height: int,
                   top: tuple[int, int, int],
                   bottom: tuple[int, int, int]) -> Image.Image:
    """Fast vertical gradient using 32 bands."""
    bands = 32
    band_h = max(1, height // bands)
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for i in range(bands + 1):
        t = i / bands
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        y0 = i * band_h
        y1 = min(y0 + band_h, height)
        draw.rectangle([0, y0, width, y1], fill=(r, g, b))
    return img


def render_thumbnail(
    title: str,
    subreddit: str = "",
    video_width: int = 1080,
    video_height: int = 1920,
    font_path: str | None = None,
    score: int = 0,
    num_comments: int = 0,
) -> Image.Image:
    """
    Generate a YouTube-ready thumbnail (RGB, no transparency).

    Layout:
      - Dark gradient background (subreddit-themed)
      - Large emoji icon (upper-center)
      - Bold white title text (center, 2-3 lines)
      - Accent bar at bottom
      - r/subreddit label (bottom)
    """
    sub_lower = subreddit.lower()

    # Pick color scheme
    if sub_lower in _GAMING_SUBS:
        scheme = _THUMB_SCHEME["gaming"]
    elif sub_lower in _AITA_SUBS:
        scheme = _THUMB_SCHEME["aita"]
    elif sub_lower in _TECH_SUBS:
        scheme = _THUMB_SCHEME["tech"]
    elif sub_lower in _FINANCE_SUBS:
        scheme = _THUMB_SCHEME["finance"]
    else:
        scheme = _THUMB_SCHEME["default"]

    top_color, bottom_color, accent_color = scheme

    # Build gradient background
    img = _make_gradient(video_width, video_height, top_color, bottom_color)
    draw = ImageDraw.Draw(img)

    # Subtle vignette: darken edges
    vignette = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    spread = video_width // 3
    for i in range(spread):
        alpha = int(90 * (1 - i / spread))
        vd.rectangle([0, 0, i, video_height], fill=(0, 0, 0, alpha))
        vd.rectangle([video_width - i, 0, video_width, video_height], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Decorative icon: real Apple Color Emoji if available, fallback to
    # accent circle + upvote triangle. Emoji gives a polished neophyte-friendly
    # look vs the previous geometric placeholder.
    icon_size = min(400, video_width // 3)
    icon_cx = video_width // 2
    icon_cy = int(video_height * 0.18)
    emoji_char = _THUMB_EMOJI.get(sub_lower)
    emoji_img = _render_color_emoji(emoji_char, icon_size) if emoji_char else None

    if emoji_img is not None:
        # Paste the color emoji, centered
        ex = icon_cx - emoji_img.size[0] // 2
        ey = icon_cy - emoji_img.size[1] // 2
        # Composite onto RGB img via alpha paste
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(emoji_img, (ex, ey))
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)
    else:
        # Fallback: accent circle + white upvote triangle
        icon_r = min(90, video_width // 10)
        draw.ellipse(
            [icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r],
            fill=accent_color,
        )
        tri_size = icon_r // 2
        tri_x, tri_y = icon_cx, icon_cy - tri_size // 2
        draw.polygon(
            [(tri_x, tri_y - tri_size),
             (tri_x - tri_size, tri_y + tri_size // 2),
             (tri_x + tri_size, tri_y + tri_size // 2)],
            fill=(255, 255, 255),
        )

    # Keyword badge — if the title contains a money amount or big number,
    # render it as a large accent-color pill below the icon. Drives neophyte
    # CTR by giving a single strong focal point the eye catches first.
    #
    # Duplication guard: only render the badge when the keyword can be
    # stripped from the title text. If the preposition guard forces the
    # keyword to remain in the title (e.g. "$500 for rent"), showing a
    # badge on top would display the same value twice.
    keyword = detect_keyword(title)
    hook_title = extract_hook_text(title)
    stripped_title = _strip_keyword_from_title(hook_title, keyword) if keyword else hook_title
    badge_visible = bool(keyword) and stripped_title != hook_title
    badge_bottom_y = icon_cy + icon_size // 2  # default: below icon
    if badge_visible:
        kw_size = min(200, video_width // 5)
        kw_font = _load_bold_font(font_path, kw_size)
        kb = draw.textbbox((0, 0), keyword, font=kw_font)
        kw_w = kb[2] - kb[0]
        kw_h = kb[3] - kb[1]
        hp, vp = 56, 28
        box_w = kw_w + hp * 2
        box_h = kw_h + vp * 2
        bx = (video_width - box_w) // 2
        by = int(video_height * 0.28)
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=24, fill=accent_color,
        )
        draw.text(
            (bx + hp - kb[0], by + vp - kb[1]),
            keyword, font=kw_font, fill=(255, 255, 255),
            stroke_width=4, stroke_fill=(0, 0, 0),
        )
        badge_bottom_y = by + box_h

    # Title text — strip AITA/WIBTA preambles; remove the keyword only when
    # the badge above is actually showing it (otherwise the keyword needs to
    # stay in the sentence for grammar).
    display_title = stripped_title if badge_visible else hook_title
    padding = 80
    content_w = video_width - padding * 2

    # Auto-shrink: start at max size, shrink until wrapped text fits in 4 lines
    # without mid-word truncation. Prevents "Just passed 3000 games owned on"
    # cutting off "Steam".
    max_lines = 4
    title_size = min(130, video_width // 7)
    while title_size >= 70:
        title_font = _load_bold_font(font_path, title_size)
        lines = _wrap_text(draw, display_title, title_font, content_w)
        if len(lines) <= max_lines:
            break
        title_size -= 8
    else:
        title_font = _load_bold_font(font_path, title_size)
        lines = _wrap_text(draw, display_title, title_font, content_w)[:max_lines]

    line_h = int(title_size * 1.35)
    block_h = len(lines) * line_h

    # Vertical position: center the title block in the space between the
    # badge/icon bottom and the accent bar. Prevents short titles from
    # leaving a giant void above the bottom bar (TIFU case).
    bar_y = int(video_height * 0.82)
    available_top = badge_bottom_y + 40
    available_bot = bar_y - 40
    if block_h < (available_bot - available_top):
        # Bias toward the bottom: title reads with the accent bar/score row
        # as a single anchored block; a big gap above looks more natural than
        # a big gap below (which reads as "empty footer").
        slack = (available_bot - available_top) - block_h
        y = available_top + int(slack * 0.7)
    else:
        y = available_top

    for line in lines:
        bb = draw.textbbox((0, 0), line, font=title_font)
        lw = bb[2] - bb[0]
        x = (video_width - lw) // 2 - bb[0]
        draw.text((x, y), line, font=title_font, fill=(255, 255, 255),
                  stroke_width=6, stroke_fill=(0, 0, 0))
        y += line_h

    # Accent bar
    bar_h = 8
    draw.rectangle([padding, bar_y, video_width - padding, bar_y + bar_h],
                   fill=accent_color)

    # Reddit-native bottom row: r/subreddit + upvote arrow + score + comments.
    # Makes the thumbnail look like an enlarged Reddit post — strong brand
    # signal on the channel page / search result grid.
    label_font = _load_bold_font(font_path, 52)
    meta_font = _load_font(font_path, 44)
    row_y = bar_y + bar_h + 32

    # r/subreddit (bold, accent color)
    if subreddit:
        sub_label = f"r/{subreddit}"
        sb = draw.textbbox((0, 0), sub_label, font=label_font)
        sw = sb[2] - sb[0]
    else:
        sub_label = ""
        sw = 0

    # Upvote icon (accent-colored arrow) + score
    icon_sz = 46
    score_str = _format_score(score) if score > 0 else ""
    score_bb = draw.textbbox((0, 0), score_str, font=label_font) if score_str else (0, 0, 0, 0)
    score_w = score_bb[2] - score_bb[0]

    # Comments (drawn speech-bubble icon + count — avoids 💬 font-fallback tofu)
    comments_num = _format_score(num_comments) if num_comments > 0 else ""
    comment_icon_sz = 38
    cb = draw.textbbox((0, 0), comments_num, font=meta_font) if comments_num else (0, 0, 0, 0)
    comments_w = (comment_icon_sz + 12 + (cb[2] - cb[0])) if comments_num else 0

    # Layout: [r/sub]  [▲ score]  [💬 comments], centered as a group
    gap = 40
    group_parts = []
    if sub_label:
        group_parts.append(("sub", sw))
    if score_str:
        group_parts.append(("score", icon_sz + 12 + score_w))
    if comments_num:
        group_parts.append(("comments", comments_w))
    total_w = sum(w for _, w in group_parts) + gap * max(0, len(group_parts) - 1)
    x = (video_width - total_w) // 2

    for kind, w in group_parts:
        if kind == "sub":
            draw.text((x, row_y), sub_label, font=label_font,
                      fill=accent_color, stroke_width=2, stroke_fill=(0, 0, 0))
        elif kind == "score":
            # Upvote triangle
            ty = row_y + 6
            draw.polygon(
                [(x + icon_sz // 2, ty),
                 (x, ty + icon_sz),
                 (x + icon_sz, ty + icon_sz)],
                fill=accent_color,
            )
            draw.text((x + icon_sz + 12, row_y), score_str,
                      font=label_font, fill=(240, 240, 240),
                      stroke_width=2, stroke_fill=(0, 0, 0))
        elif kind == "comments":
            # Drawn speech-bubble icon (rounded rect with a tail notch)
            ix = x
            iy = row_y + 8
            bubble_w = comment_icon_sz
            bubble_h = comment_icon_sz - 6
            draw.rounded_rectangle(
                [ix, iy, ix + bubble_w, iy + bubble_h],
                radius=8, outline=(200, 200, 200), width=4,
            )
            # Tail triangle on bottom-left
            draw.polygon(
                [(ix + 8, iy + bubble_h),
                 (ix + 16, iy + bubble_h),
                 (ix + 8, iy + bubble_h + 8)],
                fill=(200, 200, 200),
            )
            draw.text((x + comment_icon_sz + 12, row_y + 4),
                      comments_num, font=meta_font, fill=(200, 200, 200),
                      stroke_width=2, stroke_fill=(0, 0, 0))
        x += w + gap

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
        if seg.get("type") == "verdict":
            card_img = render_verdict_card(
                seg["verdict_label"],
                video_width=video_width,
                video_height=video_height,
                font_path=font_path,
            )
        elif seg.get("type") == "hook":
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
        elif seg.get("type") == "cta":
            card_img = render_cta_card(
                seg.get("text", ""),
                video_width=video_width,
                video_height=video_height,
                font_path=font_path,
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
