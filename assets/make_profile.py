from PIL import Image, ImageDraw, ImageFont

SIZE = 800
ORANGE = (255, 69, 0)
WHITE = (255, 255, 255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle
draw.ellipse([0, 0, SIZE, SIZE], fill=ORANGE)

# Speech bubble rounded rect
bx, by, bw, bh = 155, 165, 490, 325
r = 48
draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=r, fill=WHITE)

# Speech bubble tail (triangle)
draw.polygon([(255, by + bh), (215, 575), (355, by + bh)], fill=WHITE)

# "썰" text inside bubble
font_bold = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 220, index=7)
text = "썰"
bbox = draw.textbbox((0, 0), text, font=font_bold)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = bx + (bw - tw) // 2 - bbox[0]
ty = by + (bh - th) // 2 - bbox[1] - 10
draw.text((tx, ty), text, font=font_bold, fill=ORANGE)

# "REDDIT" label
font_label = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 68)
label = "REDDIT"
lbbox = draw.textbbox((0, 0), label, font=font_label)
lw = lbbox[2] - lbbox[0]
draw.text(((SIZE - lw) // 2, 650), label, font=font_label, fill=WHITE)

out = "channel_profile.png"
img.save(out, "PNG")
print(f"Saved: {out}")
