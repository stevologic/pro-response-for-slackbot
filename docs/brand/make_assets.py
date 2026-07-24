#!/usr/bin/env python3
"""Generate the Pro Response brand assets served from docs/.

One geometry definition drives every output, so the SVG and the rasters can't
drift apart. Regenerate after changing any constant below:

    pip install pillow
    python docs/brand/make_assets.py

Outputs (all written to docs/):
    favicon.svg              vector source of truth, modern browsers
    favicon.ico              16/32/48, legacy browsers + Windows shortcuts
    apple-touch-icon.png     180x180, opaque, full-bleed -- iOS home screen
    icon-192.png             web app manifest
    icon-512.png             web app manifest
    icon-maskable-512.png    Android adaptive icon (content inside safe zone)
    og.png                   1200x630 link-share card
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DOCS = Path(__file__).resolve().parent.parent

SITE = "https://stevologic.github.io/pro-response/"

# Brand palette -- kept in sync with the :root custom properties in index.html.
BRAND = (0x4A, 0x5C, 0xFF)
BRAND_2 = (0x8B, 0x5C, 0xF6)
ACCENT = (0x5E, 0xEA, 0xD4)
INK = (0x0B, 0x0E, 0x17)
MUTED = (0x9A, 0xA4, 0xBD)
WHITE = (0xFF, 0xFF, 0xFF)

S = 1024          # master canvas
SS = 4            # supersample factor for antialiasing
CORNER = 230      # rounded-square radius (22.5% -- squircle-ish)

# --- pen geometry, in master units -------------------------------------------
TIP = (300.0, 700.0)          # nib tip, pointing down-left
ANGLE = -45.0                 # pen axis, degrees (up-right from the tip)
PEN_LEN = 560.0
PEN_HALF_W = 100.0
NIB_LEN = 150.0               # where the taper stops
GAP = (195.0, 245.0)          # ferrule: gradient shows through here
RULE_Y = 790.0                # the "written" stroke under the nib
RULE_X = (270.0, 760.0)
RULE_W = 84.0
NUDGE = (-3.0, -20.0)         # centre the composed mark on the canvas


def _pen_points(scale: float = 1.0):
    """Return (nib polygon, body polygon, rule endpoints) at the given scale.

    `scale` grows the mark about the canvas centre -- small favicons get a
    slightly larger mark so it survives being resampled down to 16px.
    """
    rad = math.radians(ANGLE)
    axis = (math.cos(rad), math.sin(rad))            # tip -> cap
    perp = (-axis[1], axis[0])                       # across the barrel

    def at(u: float, v: float):
        x = TIP[0] + axis[0] * u + perp[0] * v + NUDGE[0]
        y = TIP[1] + axis[1] * u + perp[1] * v + NUDGE[1]
        c = S / 2
        return (c + (x - c) * scale, c + (y - c) * scale)

    w = PEN_HALF_W
    nib = [at(0, 0), at(NIB_LEN, w), at(GAP[0], w), at(GAP[0], -w), at(NIB_LEN, -w)]
    body = [at(GAP[1], w), at(PEN_LEN, w), at(PEN_LEN, -w), at(GAP[1], -w)]

    c = S / 2
    def pt(x, y):
        return (c + (x + NUDGE[0] - c) * scale, c + (y + NUDGE[1] - c) * scale)

    rule = (pt(RULE_X[0], RULE_Y), pt(RULE_X[1], RULE_Y))
    return nib, body, rule


def _gradient(size: tuple[int, int], a=BRAND, b=BRAND_2) -> Image.Image:
    """Diagonal (CSS 135deg) linear gradient, built small and scaled up.

    A linear ramp survives bilinear upscaling exactly, so this is both fast and
    pixel-accurate.
    """
    n = 128
    small = Image.new("RGB", (n, n))
    px = small.load()
    for y in range(n):
        for x in range(n):
            t = (x + y) / (2 * (n - 1))
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return small.resize(size, Image.Resampling.BILINEAR)


def render_icon(size: int, *, rounded: bool = True, opaque: bool = False,
                scale: float = 1.0, simple: bool = False) -> Image.Image:
    """Draw the icon at `size` px.

    rounded -- rounded-square silhouette (off for iOS/maskable, which are
               masked by the platform and must be full-bleed).
    opaque  -- flatten onto the gradient; iOS composites alpha onto black.
    simple  -- drop the ferrule gap, fatten the rule (for <=32px).
    """
    big = size * SS
    nib, body, rule = _pen_points(scale)
    k = big / S

    def sc(pts):
        return [(x * k, y * k) for x, y in pts]

    img = _gradient((big, big)).convert("RGBA")

    rule_only = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(rule_only)
    rw = (RULE_W * (1.35 if simple else 1.0)) * k * scale
    (x0, y0), (x1, y1) = ((p * k for p in end) for end in rule)
    d.line([(x0, y0), (x1, y1)], fill=255, width=round(rw))
    for cx, cy in ((x0, y0), (x1, y1)):  # round caps, as in favicon.svg
        d.ellipse((cx - rw / 2, cy - rw / 2, cx + rw / 2, cy + rw / 2), fill=255)

    pen = Image.new("L", (big, big), 0)
    dp = ImageDraw.Draw(pen)
    if simple:
        # One continuous barrel: the ferrule gap turns to mush below ~32px.
        dp.polygon(sc(nib[:2] + body[1:3] + nib[3:]), fill=255)
    else:
        dp.polygon(sc(nib), fill=255)
        dp.polygon(sc(body), fill=255)

    img.paste(ACCENT, (0, 0), rule_only)
    img.paste(WHITE, (0, 0), pen)

    if rounded:
        silhouette = Image.new("L", (big, big), 0)
        ImageDraw.Draw(silhouette).rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=round(CORNER * k), fill=255)
        img.putalpha(silhouette)

    img = img.resize((size, size), Image.Resampling.LANCZOS)
    if opaque:
        flat = Image.new("RGB", (size, size), BRAND)
        flat.paste(img, (0, 0), img)
        return flat
    return img


def write_svg(path: Path) -> None:
    nib, body, rule = _pen_points()

    def poly(pts):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" '
        'viewBox="0 0 1024 1024" role="img" aria-label="Pro Response">\n'
        '  <defs>\n'
        '    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">\n'
        '      <stop offset="0" stop-color="#4a5cff"/>\n'
        '      <stop offset="1" stop-color="#8b5cf6"/>\n'
        '    </linearGradient>\n'
        '  </defs>\n'
        f'  <rect width="1024" height="1024" rx="{CORNER}" fill="url(#g)"/>\n'
        f'  <path d="M{rule[0][0]:.1f} {rule[0][1]:.1f} H{rule[1][0]:.1f}" '
        f'stroke="#5eead4" stroke-width="{RULE_W:.0f}" stroke-linecap="round" fill="none"/>\n'
        f'  <polygon points="{poly(nib)}" fill="#fff"/>\n'
        f'  <polygon points="{poly(body)}" fill="#fff"/>\n'
        '</svg>\n',
        encoding="utf-8",
    )


# --- link-share card ----------------------------------------------------------

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in (f"C:/Windows/Fonts/{name}", f"/usr/share/fonts/truetype/dejavu/{name}"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


BOLD = "segoeuib.ttf"
SEMI = "seguisb.ttf"
REG = "segoeui.ttf"


def _glow(size: tuple[int, int], centre: tuple[float, float], radius: float,
          colour: tuple[int, int, int], strength: float) -> Image.Image:
    """Soft radial wash, mirroring the hero's radial-gradient in index.html."""
    w, h = 150, round(150 * size[1] / size[0])
    small = Image.new("RGB", (w, h), (0, 0, 0))
    px = small.load()
    cx, cy = centre[0] * w, centre[1] * h
    r = radius * w
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, (y - cy) * (w / h))
            t = max(0.0, 1.0 - d / r) ** 2 * strength
            px[x, y] = tuple(round(c * t) for c in colour)
    return small.resize(size, Image.Resampling.BICUBIC)


def render_og(size=(1200, 630)) -> Image.Image:
    w, h = size
    card = Image.new("RGB", size, INK)
    for centre, radius, colour, strength in (
        ((0.30, 0.02), 0.85, BRAND, 0.62),
        ((0.92, 0.88), 0.62, BRAND_2, 0.42),
        ((0.06, 0.95), 0.42, ACCENT, 0.12),
    ):
        card = Image.blend(card, Image.new("RGB", size, (0, 0, 0)), 0.0)
        card = _screen(card, _glow(size, centre, radius, colour, strength))

    d = ImageDraw.Draw(card)

    # Masthead: icon + wordmark.
    icon = render_icon(104)
    card.paste(icon, (80, 74), icon)
    d.text((208, 96), "Pro Response", font=_font(BOLD, 46), fill=WHITE)
    d.text((210, 148), "AI WRITING ASSISTANT FOR SLACK", font=_font(SEMI, 21),
           fill=MUTED)

    # Headline, second line gradient-filled like the h1 on the page.
    head = _font(BOLD, 82)
    d.text((80, 250), "Sound your best", font=head, fill=WHITE)
    y2 = 348
    d.text((80, y2), "in ", font=head, fill=WHITE)
    x2 = 80 + d.textlength("in ", font=head)
    _gradient_text(card, "every message.", (x2, y2), head)

    d.text((80, 476), "Rewrite, refine, and reformat any message — fix grammar, shift tone,",
           font=_font(REG, 30), fill=MUTED)
    d.text((80, 516), "translate, or summarize. Preview it, then post.",
           font=_font(REG, 30), fill=MUTED)

    tags = _font(SEMI, 24)
    d.text((80, 574), "GPT-5  ·  Claude  ·  Groq  ·  Ollama", font=tags, fill=ACCENT)
    right = "Free · open source · self-hosted"
    d.text((w - 80 - d.textlength(right, font=tags), 574), right, font=tags, fill=MUTED)

    # Accent rail along the bottom edge.
    rail = _gradient((w, 10), BRAND, BRAND_2)
    card.paste(rail, (0, h - 10))
    return card


def _screen(base: Image.Image, layer: Image.Image) -> Image.Image:
    """Additive-ish screen blend, so the glows stack without washing out."""
    from PIL import ImageChops
    return ImageChops.screen(base, layer)


def _gradient_text(card: Image.Image, text: str, xy: tuple[float, float],
                   font: ImageFont.FreeTypeFont) -> None:
    """Paint text with the h1 sweep from index.html (brand -> violet -> accent).

    The ramp spans the text's own bounding box, so the full sweep lands inside
    the words rather than being sampled from one corner of the card.
    """
    mask = Image.new("L", card.size, 0)
    md = ImageDraw.Draw(mask)
    md.text(xy, text, font=font, fill=255)
    x0, y0, x1, y1 = md.textbbox(xy, text, font=font)

    span = Image.new("RGB", (max(1, round(x1 - x0)), max(1, round(y1 - y0))))
    px = span.load()
    stops = ((0.0, (0x8E, 0xA2, 0xFF)), (0.6, (0xB7, 0x94, 0xFF)), (1.0, ACCENT))
    for x in range(span.width):
        t = x / max(1, span.width - 1)
        (ta, ca), (tb, cb) = next(
            (stops[i], stops[i + 1]) for i in range(len(stops) - 1)
            if t <= stops[i + 1][0])
        f = (t - ta) / (tb - ta)
        col = tuple(round(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
        for y in range(span.height):
            px[x, y] = col

    fill = Image.new("RGB", card.size, (0, 0, 0))
    fill.paste(span, (round(x0), round(y0)))
    card.paste(fill, (0, 0), mask)


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)

    write_svg(DOCS / "favicon.svg")

    # iOS: full-bleed and opaque -- the OS applies its own mask, and any alpha
    # is composited onto black.
    render_icon(180, rounded=False, opaque=True, scale=0.84).save(
        DOCS / "apple-touch-icon.png")

    render_icon(192).save(DOCS / "icon-192.png")
    render_icon(512).save(DOCS / "icon-512.png")
    # Android adaptive icons crop to a circle of ~80% -- keep the mark inside it.
    render_icon(512, rounded=False, opaque=True, scale=0.62).save(
        DOCS / "icon-maskable-512.png")

    ico = [render_icon(48), render_icon(32, scale=1.12, simple=True),
           render_icon(16, scale=1.12, simple=True)]
    ico[0].save(DOCS / "favicon.ico", format="ICO",
                sizes=[(48, 48), (32, 32), (16, 16)], append_images=ico[1:])

    render_og().save(DOCS / "og.png", optimize=True)

    (DOCS / "site.webmanifest").write_text(json.dumps({
        "name": "Pro Response",
        "short_name": "Pro Response",
        "description": "An AI writing assistant for Slack — rewrite, refine, "
                       "and reformat your team's messages.",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#0b0e17",
        "theme_color": "#4a5cff",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "icon-maskable-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
            {"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }, indent=2) + "\n", encoding="utf-8")

    print(f"wrote brand assets to {DOCS} (site: {SITE})")


if __name__ == "__main__":
    main()
