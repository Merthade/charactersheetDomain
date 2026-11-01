#!/usr/bin/env python3
"""Build every image the CharacterSheet site serves, from the app repo's own sources.

- Icons (favicon.ico, favicon-32, apple-touch-icon, icon-512) from _gen/appicon-1024.png,
  which is ictool's render of CharacterSheet/IconV3.icon (an Icon Composer file has no PNG
  to read). Icon changed? Render it again:
    "/Applications/Xcode.app/Contents/Applications/Icon Composer.app/Contents/Executables/ictool" \
      CharacterSheet/IconV3.icon --export-image --output-file website/_gen/appicon-1024.png \
      --platform iOS --rendition Default --width 1024 --height 1024 --scale 1
- Screenshots: the App Store raws (Marketing/screenshots/raw/en, the store seed) framed in
  the web shell Choru's site uses (side buttons that protrude) plus the store set's Dynamic
  Island, exported as WebP at one uniform size.
- og-image.png (1200x630): the store set's blue gradient, the name, one line, the Home screen.

Needs Pillow. Run from anywhere: python3 _gen/make_assets.py
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

# Apple's own product bezel since 2026-11-01 (Holocron brand.md; bezel PNGs in ~/Documents/Xcode/AppleBezels,
# never in this repo). The bezel carries the Dynamic Island and camera, so nothing is painted on the capture.
sys.path.insert(0, os.path.expanduser("~/Documents/Holocron/tools/web-frames"))
from apple_bezel import frame as apple_frame  # noqa: E402

GEN = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(GEN)
APP = os.path.dirname(SITE)                      # the CharacterSheet app repo this site sits in
OUT = os.path.join(SITE, "assets")
RAW = os.path.join(APP, "Marketing", "screenshots", "raw", "en")
ICON = os.path.join(GEN, "appicon-1024.png")
FONT_BLACK = "/Library/Fonts/SF-Pro-Display-Black.otf"
FONT_BOLD = "/Library/Fonts/SF-Pro-Display-Bold.otf"

# The store set's shell and gradient (Marketing/screenshots/config.json).
SCREEN_R_RATIO = 0.145
BEZEL_RATIO = 0.030
RIM_RATIO = 0.011
RIM_COLOR = (0x2C, 0x2C, 0x2D, 255)
ISLAND = dict(w_ratio=0.286, h_ratio=0.0855, top_ratio=0.0318)
BLUE_TOP = (0x44, 0x88, 0xFF)
BLUE_BOTTOM = (0x05, 0x10, 0x1A)
WEB_W = 640                                      # every framed shot is this wide

SHOTS = {
    "shot-home.webp":      "home.png",
    "shot-recap.webp":     "recap.png",
    "shot-stats.webp":     "stats_cards.png",
    "shot-radar.webp":     "stats.png",
    "shot-quests.webp":    "quests.png",
    "shot-buffs.webp":     "buffs.png",
    "shot-body.webp":      "body.png",
    "shot-log.webp":       "log.png",
    "shot-workouts.webp":  "customize_strength.png",
    "shot-setup.webp":     "setup_strength.png",
    "shot-timer.webp":     "running.png",
    "shot-complete.webp":  "completion.png",
}


def shell(img):
    """The capture in Apple's iPhone bezel (Dynamic Island and camera included)."""
    return apple_frame(img)



def camera_lens(ih):
    """The front camera at the island's right end (a plain black pill reads as fake):
    concentric with the right cap, a dark ring, a navy glass, one small glint.
    Drawn at 4x and scaled down, so the edges are smooth."""
    s = 4
    size = ih * s
    lens = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lens)
    c, r = size / 2, size * 0.19
    d.ellipse([c - r, c - r, c + r, c + r], fill=(26, 26, 32, 255))
    g = r * 0.68
    d.ellipse([c - g, c - g, c + g, c + g], fill=(12, 17, 34, 255))
    h, hx, hy = r * 0.2, c - r * 0.3, c - r * 0.32
    d.ellipse([hx - h, hy - h, hx + h, hy + h], fill=(70, 78, 112, 200))
    return lens.resize((ih, ih), Image.LANCZOS)


def framed(raw):
    f = shell(Image.open(os.path.join(RAW, raw)))
    return f.resize((WEB_W, round(WEB_W * f.height / f.width)), Image.LANCZOS)


def save_webp(img, name, quality=82):
    path = os.path.join(OUT, name)
    img.save(path, "WEBP", quality=quality, method=6)
    print(f"{name:22s} {img.size[0]}x{img.size[1]}  {os.path.getsize(path) // 1024}KB")


def gradient(w, h):
    """The store's blue: top colour at (0,0), bottom colour at (0.72w, h)."""
    g = Image.new("RGB", (w, h))
    px = g.load()
    vx, vy = 0.72 * w, 1.0 * h
    norm = vx * vx + vy * vy
    for y in range(h):
        for x in range(w):
            t = max(0.0, min(1.0, (x * vx + y * vy) / norm))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(BLUE_TOP, BLUE_BOTTOM))
    return g


def og_image():
    W, H = 1200, 630
    img = gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(img)

    icon = Image.open(ICON).convert("RGBA").resize((96, 96), Image.LANCZOS)
    img.alpha_composite(icon, (72, 92))

    d.text((72, 212), "CharacterSheet", font=ImageFont.truetype(FONT_BLACK, 84), fill="white")
    sub = ImageFont.truetype(FONT_BOLD, 46)
    d.text((72, 326), "Level up in real life.", font=sub, fill=(255, 255, 255, 235))
    d.text((72, 500), "Fitness RPG for iPhone and Apple Watch", font=ImageFont.truetype(FONT_BOLD, 30),
           fill=(0xCF, 0xE0, 0xFF, 255))

    # The Home screen, cropped by the bottom edge like a phone leaning into the frame.
    phone = framed("home.png")
    phone = phone.resize((330, round(330 * phone.height / phone.width)), Image.LANCZOS)
    img.alpha_composite(phone.crop((0, 0, phone.width, H - 56)), (W - phone.width - 84, 56))

    path = os.path.join(OUT, "og-image.png")
    img.convert("RGB").save(path, "PNG", optimize=True)
    print(f"og-image.png           {W}x{H}  {os.path.getsize(path) // 1024}KB")


def icons():
    src = Image.open(ICON).convert("RGBA")
    src.resize((180, 180), Image.LANCZOS).save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    src.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "icon-512.png"), optimize=True)
    src.resize((32, 32), Image.LANCZOS).save(os.path.join(OUT, "favicon-32.png"), optimize=True)
    src.save(os.path.join(SITE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons: apple-touch-icon 180, icon-512, favicon-32, favicon.ico 16/32/48")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    icons()
    for name, raw in SHOTS.items():
        save_webp(framed(raw), name)
    og_image()
