#!/usr/bin/env python3
"""Render docs/preview.png and docs/demo.gif showing the teleprompter look.

This mirrors the app's two-line layout, per-speaker colors and ease-out slide,
so the README can show what it looks like without a live screen capture.

Run:  python tools/generate_preview.py
"""

import os
from PIL import Image, ImageDraw, ImageFont

W, H = 900, 230
HINT_H = 28
BG = (0, 0, 0)
DIM_FACTOR = 0.62
HINT_TEXT = ("SPACE/click next  ·  ←back  ·  R restart  ·  +/- size  ·  "
             "C colors  ·  E edit  ·  L load  ·  ESC quit")

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(os.path.dirname(HERE), "docs")
os.makedirs(DOCS, exist_ok=True)


def load_font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


BIG = load_font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 40)
SMALL = load_font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 12)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dim_of(rgb):
    return lerp(rgb, BG, DIM_FACTOR)


def ease(t):
    return 1 - (1 - t) ** 3


def centered(draw, text, cx, cy, font, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (r - l) / 2, cy - (b - t) / 2 - t), text, font=font, fill=fill)


def frame(items):
    """items: list of (text, y_center, rgb)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for text, y, rgb in items:
        if text:
            centered(d, text, W / 2, y, BIG, rgb)
    # hint bar
    d.rectangle([0, H - HINT_H, W, H], fill=(17, 17, 17))
    centered(d, HINT_TEXT, W / 2, H - HINT_H / 2, SMALL, (119, 119, 119))
    return img


# Script + speaker colors used in the preview
RED = (255, 99, 99)     # J
BLUE = (79, 140, 255)   # M
L1 = "J: Press C to color a speaker's lines."
L2 = "M: Lines with my letter show in blue."
L3 = "J: Two people, one screen, no mix-ups."

Y_CUR = H * 0.30
Y_NEXT = H * 0.66
GAP = Y_NEXT - Y_CUR

# ---- static preview: current (red, bright) on top, next (blue, dim) below ----
frame([(L1, Y_CUR, RED), (L2, Y_NEXT, dim_of(BLUE))]).save(
    os.path.join(DOCS, "preview.png"))

# ---- animated GIF: hold, slide up one line, hold ----
frames, durations = [], []
STEPS = 16
for _ in range(14):                                  # hold on first pair
    frames.append(frame([(L1, Y_CUR, RED), (L2, Y_NEXT, dim_of(BLUE))]))
    durations.append(60)
for n in range(STEPS):                               # slide L1 out, L2 -> top
    t = ease((n + 1) / STEPS)
    frames.append(frame([
        (L1, Y_CUR - GAP * t, lerp(RED, BG, t)),
        (L2, Y_NEXT - GAP * t, lerp(dim_of(BLUE), BLUE, t)),
        (L3, Y_NEXT + GAP - GAP * t, lerp(BG, dim_of(RED), t)),
    ]))
    durations.append(28)
for _ in range(20):                                  # hold on new pair
    frames.append(frame([(L2, Y_CUR, BLUE), (L3, Y_NEXT, dim_of(RED))]))
    durations.append(60)

frames[0].save(os.path.join(DOCS, "demo.gif"), save_all=True,
               append_images=frames[1:], duration=durations, loop=0, optimize=True)

print("wrote", os.path.join(DOCS, "preview.png"))
print("wrote", os.path.join(DOCS, "demo.gif"))
