"""Holler's logo, drawn in code so every size stays crisp: a warm squircle with a white voice waveform.

    python -m holler.brand OUTDIR     writes holler.ico, PNGs and the installer wizard images
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

TOP, BOTTOM = (255, 112, 67), (229, 36, 94)            # coral -> crimson
PAUSED_TOP, PAUSED_BOTTOM = (160, 160, 168), (110, 110, 120)
BARS = (0.30, 0.56, 0.80, 0.56, 0.30)                  # waveform heights, as a share of the icon
BARS_SMALL = (0.40, 0.76, 0.40)                        # three bars read better at 16-24 px


def _gradient(w, h, top, bottom):
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g.resize((w, h))


def _squircle_mask(n, inset=0):
    """A superellipse (iOS/Windows 11-style rounded square), n x n, antialiased by supersampling."""
    s = 4
    big = n * s
    m = Image.new("L", (big, big), 0)
    r = big / 2 - inset * s
    c = big / 2
    pts = []
    for i in range(720):
        a = 2 * math.pi * i / 720
        ca, sa = math.cos(a), math.sin(a)
        x = c + r * math.copysign(abs(ca) ** (2 / 5), ca)
        y = c + r * math.copysign(abs(sa) ** (2 / 5), sa)
        pts.append((x, y))
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m.resize((n, n), Image.LANCZOS)


def make_logo(size: int = 256, paused: bool = False) -> Image.Image:
    s = 4 if size < 128 else 2
    n = size * s
    top, bottom = (PAUSED_TOP, PAUSED_BOTTOM) if paused else (TOP, BOTTOM)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    body = _gradient(n, n, top, bottom)
    pad = 0 if size <= 32 else n // 32
    mask = _squircle_mask(n, inset=pad / s)
    img.paste(body, (0, 0), mask)
    if size >= 48:                                      # soft light on the upper half
        hl = Image.new("L", (n, n), 0)
        ImageDraw.Draw(hl).ellipse([-n * 0.3, -n * 0.9, n * 1.3, n * 0.42], fill=34)
        hl = hl.filter(ImageFilter.GaussianBlur(n / 10))
        hl = Image.composite(hl, Image.new("L", (n, n), 0), mask)
        img = _screen(img, hl)
    bars = BARS_SMALL if size <= 24 else BARS
    d = ImageDraw.Draw(img)
    k = len(bars)
    gap = n * (0.115 if k == 5 else 0.19)
    w = n * (0.085 if k == 5 else 0.13)
    cx, cy = n / 2, n / 2
    for i, h in enumerate(bars):
        x = cx + (i - (k - 1) / 2) * gap
        half = n * h / 2 * 0.82
        d.rounded_rectangle([x - w / 2, cy - half, x + w / 2, cy + half], radius=w / 2, fill=(255, 255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


def _screen(img, light):
    white = Image.new("RGBA", img.size, (255, 255, 255, 0))
    white.putalpha(light)
    return Image.alpha_composite(img, white)


def write_assets(out: str) -> None:
    os.makedirs(out, exist_ok=True)
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    frames = [make_logo(z) for z in sizes]
    frames[-1].save(os.path.join(out, "holler.ico"), sizes=[(z, z) for z in sizes], append_images=frames[:-1])
    for z in (32, 64, 128, 256, 512, 1024):
        make_logo(z).save(os.path.join(out, f"holler-{z}.png"))
    # Inno Setup wizard images (100% and 200% scale)
    for scale in (1, 2):
        w, h = 164 * scale, 314 * scale
        side = _gradient(w, h, (40, 22, 36), (22, 14, 22)).convert("RGB")
        lg = make_logo(96 * scale)
        side.paste(lg, ((w - lg.width) // 2, int(h * 0.18)), lg)
        side.save(os.path.join(out, f"wizard-large-{scale}x.bmp"))
        z = 55 * scale
        small = Image.new("RGB", (z, z), (255, 255, 255))
        lg = make_logo(int(z * 0.9))
        small.paste(lg, ((z - lg.width) // 2, (z - lg.height) // 2), lg)
        small.save(os.path.join(out, f"wizard-small-{scale}x.bmp"))


if __name__ == "__main__":
    write_assets(sys.argv[1] if len(sys.argv) > 1 else "brand")
