"""
End-screen subscribe CTA overlay.

YouTube Studio data: only 2 subscribers gained in ~30 days despite 5,747
views. New viewers aren't converting. Add a prominent subscribe overlay
in the final seconds of each Short — proven pattern for driving Shorts
subscription lift.

Renderer contract:
  - Full-canvas RGBA at video dimensions
  - Red YouTube-style SUBSCRIBE button with white text
  - Prompt text ("For more stories" / "Tap to subscribe")
  - Transparent background outside the CTA region (overlay-friendly)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video.card_renderer import render_subscribe_overlay


class TestSubscribeOverlayShape:
    def test_returns_rgba_at_video_dimensions(self):
        img = render_subscribe_overlay(video_width=1080, video_height=1920)
        assert img.mode == "RGBA"
        assert img.size == (1080, 1920)

    def test_default_dimensions_are_shorts(self):
        img = render_subscribe_overlay()
        assert img.size == (1080, 1920)

    def test_transparent_outside_cta_region(self):
        """Top 40% of frame should be fully transparent so the overlay
        does not obscure the video content behind it."""
        img = render_subscribe_overlay()
        top_band = img.crop((0, 0, 1080, int(1920 * 0.4)))
        alphas = [p[3] for p in top_band.getdata()]
        opaque = sum(1 for a in alphas if a > 20)
        # Allow some margin for anti-aliasing artifacts but most should be 0
        assert opaque < 500, (
            f"Top 40% should be mostly transparent (got {opaque} opaque pixels)"
        )


class TestSubscribeButton:
    def test_has_youtube_red_pixels(self):
        """YouTube-red (~#CC0000 or #FF0000) button should be prominent."""
        img = render_subscribe_overlay()
        rgba = img.convert("RGBA")
        # Count red-dominant pixels (r high, g/b low)
        red_count = 0
        for r, g, b, a in rgba.getdata():
            if a > 200 and r > 180 and g < 80 and b < 80:
                red_count += 1
        assert red_count > 10000, (
            f"Should have a prominent red subscribe button (got {red_count})"
        )

    def test_has_white_text_on_button(self):
        """SUBSCRIBE text should be white/bright."""
        img = render_subscribe_overlay()
        # Look in the lower half where the CTA lives
        lower = img.crop((0, int(1920 * 0.5), 1080, 1920)).convert("RGBA")
        white_count = 0
        for r, g, b, a in lower.getdata():
            if a > 200 and r > 220 and g > 220 and b > 220:
                white_count += 1
        assert white_count > 2000, (
            f"Should have white text pixels in lower half (got {white_count})"
        )


class TestCustomization:
    def test_respects_custom_dimensions(self):
        img = render_subscribe_overlay(video_width=720, video_height=1280)
        assert img.size == (720, 1280)
