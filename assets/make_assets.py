from PIL import Image, ImageDraw, ImageFont
import math

ORANGE = (255, 69, 0)
DARK_ORANGE = (204, 34, 0)
WHITE = (255, 255, 255)
DARK_BG = (18, 8, 2)

HELVETICA = "/System/Library/Fonts/Helvetica.ttc"
HELVETICA_BOLD_IDX = 1


def make_profile():
    SIZE = 800
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([0, 0, SIZE, SIZE], fill=ORANGE)

    # Subtle inner glow (lighter center)
    for i in range(60, 0, -1):
        alpha = int(40 * (1 - i / 60))
        draw.ellipse([SIZE//2 - i*4, SIZE//2 - i*4, SIZE//2 + i*4, SIZE//2 + i*4],
                     fill=(255, 106, 51, alpha))

    # Speech bubble
    bx, by, bw, bh = 150, 155, 500, 330
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=50, fill=WHITE)
    draw.polygon([(255, by + bh - 1), (210, 585), (365, by + bh - 1)], fill=WHITE)

    # "R" upvote arrow shape (simple arrow)
    # Arrow pointing up (upvote symbol)
    cx, cy = SIZE // 2, by + bh // 2 - 10
    arrow_pts = [
        (cx, cy - 90),
        (cx - 70, cy - 10),
        (cx - 35, cy - 10),
        (cx - 35, cy + 60),
        (cx + 35, cy + 60),
        (cx + 35, cy - 10),
        (cx + 70, cy - 10),
    ]
    draw.polygon(arrow_pts, fill=ORANGE)

    # "REDDIT REACTS" label
    font_label = ImageFont.truetype(HELVETICA, 56, index=HELVETICA_BOLD_IDX)
    label = "REDDIT REACTS"
    lbbox = draw.textbbox((0, 0), label, font=font_label)
    lw = lbbox[2] - lbbox[0]
    draw.text(((SIZE - lw) // 2 - lbbox[0], 648), label, font=font_label, fill=WHITE)

    img.save("channel_profile.png", "PNG")
    print("Saved: channel_profile.png")


def make_banner():
    W, H = 2560, 1440
    img = Image.new("RGB", (W, H), DARK_BG)
    draw = ImageDraw.Draw(img)

    # Background gradient effect (manual horizontal bands)
    for y in range(H):
        t = y / H
        r = int(DARK_BG[0] + (30 - DARK_BG[0]) * (1 - abs(t - 0.5) * 2))
        g = int(DARK_BG[1] + (12 - DARK_BG[1]) * (1 - abs(t - 0.5) * 2))
        b = int(DARK_BG[2])
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Orange radial glow in center
    glow_cx, glow_cy = W // 2, H // 2
    for i in range(350, 0, -1):
        alpha = int(60 * (1 - i / 350))
        r2 = int(DARK_BG[0] + (255 - DARK_BG[0]) * alpha / 255)
        g2 = int(DARK_BG[1] + (69 - DARK_BG[1]) * alpha / 255)
        b2 = int(DARK_BG[2])
        draw.ellipse([glow_cx - i*3, glow_cy - i*2, glow_cx + i*3, glow_cy + i*2],
                     fill=(r2, g2, b2))

    # Dot grid - left
    for row in range(6):
        for col in range(7):
            x, y = 100 + col * 88, 360 + row * 88
            draw.ellipse([x-7, y-7, x+7, y+7], fill=(255, 69, 0, 0))
            # Use alpha workaround with a separate layer
    dot_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ddraw = ImageDraw.Draw(dot_layer)
    for row in range(7):
        for col in range(8):
            x, y = 80 + col * 85, 340 + row * 85
            ddraw.ellipse([x-7, y-7, x+7, y+7], fill=(255, 69, 0, 30))
    for row in range(7):
        for col in range(8):
            x, y = W - 80 - col * 85, H - 340 - row * 85
            ddraw.ellipse([x-7, y-7, x+7, y+7], fill=(255, 69, 0, 30))
    img = Image.alpha_composite(img.convert("RGBA"), dot_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Accent lines
    draw.rectangle([507, 530, 511, 910], fill=(255, 69, 0))
    draw.rectangle([2049, 530, 2053, 910], fill=(255, 69, 0))

    # Mini upvote arrow (logo mark left of title)
    ax, ay = 870, 620
    aw = 90
    arrow = [
        (ax + aw//2, ay),
        (ax, ay + aw//2),
        (ax + aw//3, ay + aw//2),
        (ax + aw//3, ay + aw),
        (ax + aw*2//3, ay + aw),
        (ax + aw*2//3, ay + aw//2),
        (ax + aw, ay + aw//2),
    ]
    draw.polygon(arrow, fill=ORANGE)

    # Main title
    font_title = ImageFont.truetype(HELVETICA, 210, index=HELVETICA_BOLD_IDX)
    title = "Reddit Reacts"
    tbbox = draw.textbbox((0, 0), title, font=font_title)
    tw = tbbox[2] - tbbox[0]
    draw.text((W//2 - tw//2 - tbbox[0], 560), title, font=font_title, fill=WHITE)

    # Orange underline
    draw.rounded_rectangle([870, 800, W - 870, 814], radius=4, fill=ORANGE)

    # Subtitle
    font_sub = ImageFont.truetype(HELVETICA, 58)
    sub = "Top Reddit Threads  •  Daily Shorts  •  Real Reactions"
    sbbox = draw.textbbox((0, 0), sub, font=font_sub)
    sw = sbbox[2] - sbbox[0]
    draw.text((W//2 - sw//2 - sbbox[0], 850), sub, font=font_sub,
              fill=(255, 255, 255))

    img.save("channel_banner.png", "PNG")
    print("Saved: channel_banner.png")


make_profile()
make_banner()
