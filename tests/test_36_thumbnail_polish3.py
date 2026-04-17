"""
Thumbnail polish round 3:
  1. No duplication — when preposition guard prevents stripping the keyword
     from the title, skip the badge so the keyword doesn't appear twice.
  2. Better vertical rhythm — short titles should use the available space
     between the badge/icon and the bottom bar, not hug the top.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.card_renderer import render_thumbnail, detect_keyword


def _bright_rows(img, x0, x1, threshold=180, min_px=20):
    """Return sorted list of y-coordinates whose row has >= min_px bright pixels."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    rows = []
    for y in range(h):
        c = 0
        for x in range(x0, x1):
            r, g, b = px[x, y]
            if (r + g + b) / 3 > threshold:
                c += 1
                if c >= min_px:
                    rows.append(y)
                    break
    return rows


class TestNoKeywordDuplication:
    def test_badge_suppressed_when_cannot_strip(self):
        """If keyword is followed by a preposition (grammar-preserved in title),
        the badge should be suppressed to avoid showing it twice."""
        # "$500 for rent" → preposition guard keeps $500 in title.
        # So badge must NOT render.
        title = "Refusing to pay my roommate $500 for rent"
        img = render_thumbnail(
            title, subreddit="amitheasshole",
            score=8200, num_comments=1400,
        )
        # Badge sits around y=0.28 * 1920 ≈ 537, with AITA red accent.
        # Count red-dominant pixels in the badge region — should be ~zero.
        badge_region = img.crop((200, 500, 880, 700)).convert("RGB")
        red_dominant = 0
        for p in badge_region.getdata():
            r, g, b = p
            if r > 180 and r - g > 60 and r - b > 60:
                red_dominant += 1
        # Without badge, red pill should be absent (allow a small tolerance
        # for vignette/text artifacts).
        assert red_dominant < 2000, (
            f"Badge should be suppressed when keyword stays in title "
            f"(got {red_dominant} red pixels in badge region)"
        )

    def test_badge_still_renders_when_safely_stripped(self):
        """When keyword CAN be stripped (no preposition after), badge renders."""
        title = "I lost $500 today"
        img = render_thumbnail(title, subreddit="amitheasshole",
                               score=1000, num_comments=100)
        badge_region = img.crop((200, 500, 880, 700)).convert("RGB")
        red_dominant = sum(
            1 for r, g, b in badge_region.getdata()
            if r > 180 and r - g > 60 and r - b > 60
        )
        assert red_dominant > 3000, (
            f"Badge SHOULD render when keyword is safely stripped "
            f"(got {red_dominant} red pixels)"
        )


class TestVerticalRhythm:
    def test_short_title_fills_vertical_space(self):
        """Short titles shouldn't leave a huge gap above the bottom bar.
        The title block should be vertically positioned so its bottom is
        reasonably close to the bottom accent bar."""
        # A short title that likely renders in 2–3 lines at max font.
        title = "Accidentally learning my coworker salary and now I can't sleep"
        img = render_thumbnail(title, subreddit="tifu",
                               score=22000, num_comments=1800)
        # Title occupies center column. Look at center column (x=400..680)
        # for bright rows.
        bright = _bright_rows(img, 400, 680, threshold=200, min_px=15)
        # Filter to title region: below icon (~400) and above bar (~1574).
        title_rows = [y for y in bright if 600 < y < 1560]
        assert title_rows, "Expected title pixels in the middle band"
        last_title_y = max(title_rows)
        bar_y = int(1920 * 0.82)  # ≈ 1574
        gap = bar_y - last_title_y
        assert gap < 300, (
            f"Title bottom should be close to the accent bar "
            f"(gap={gap}px; title ends at y={last_title_y}, bar at y={bar_y})"
        )
