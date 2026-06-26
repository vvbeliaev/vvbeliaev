#!/usr/bin/env python3
"""Corona Bloom social kit generator.

Emits self-contained SVG masters for YouTube banner, 9:16 vertical, 1:1 square
and 1.9:1 OG card. Each follows the DESIGN.md "skybox under a HUD" recipe:
cosmos->chthonic gradient, coral ember, cold nebula, seeded twinkling star field
(masked fade), constellation lines in the side margins, then a legible wordmark.
"""
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

FG = "#e3e5ee"
EMBER = "#f08a72"
STEEL = "#5f95c2"
MUTED = "#8b90a4"
SANS = "'Sora','Segoe UI Variable','Segoe UI',system-ui,-apple-system,sans-serif"
MONO = "'JetBrains Mono','SF Mono',ui-monospace,monospace"


def defs(w, h, ember_cy=0.18, fade_start=0.55):
    return f"""  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#06070f"/>
      <stop offset="0.5" stop-color="#04050b"/>
      <stop offset="1" stop-color="#020308"/>
    </linearGradient>
    <radialGradient id="ember" cx="0.5" cy="{ember_cy}" r="0.6">
      <stop offset="0" stop-color="{EMBER}" stop-opacity="0.30"/>
      <stop offset="0.35" stop-color="{EMBER}" stop-opacity="0.10"/>
      <stop offset="1" stop-color="{EMBER}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="nebL" cx="0.1" cy="0.35" r="0.55">
      <stop offset="0" stop-color="{STEEL}" stop-opacity="0.12"/>
      <stop offset="1" stop-color="{STEEL}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="nebR" cx="0.92" cy="0.68" r="0.55">
      <stop offset="0" stop-color="#9a86c4" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#9a86c4" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="floor" cx="0.5" cy="1" r="0.8">
      <stop offset="0" stop-color="#020308" stop-opacity="0.95"/>
      <stop offset="1" stop-color="#020308" stop-opacity="0"/>
    </radialGradient>
    <filter id="glow" x="-200%" y="-200%" width="500%" height="500%">
      <feGaussianBlur stdDeviation="{round(max(w,h)*0.004,2)}" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="starMaskGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="1"/>
      <stop offset="{fade_start}" stop-color="#fff" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <mask id="fade"><rect width="{w}" height="{h}" fill="url(#starMaskGrad)"/></mask>
  </defs>"""


def skybox(w, h):
    return "\n".join([
        f'  <rect width="{w}" height="{h}" fill="url(#sky)"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#nebL)"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#nebR)"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#ember)"/>',
        f'  <rect width="{w}" height="{h}" fill="url(#floor)"/>',
    ])


def stars(w, h, count, seed, top_frac=0.66, rmax=1.0):
    rng = random.Random(seed)
    out = ['  <g fill="#e3e5ee" mask="url(#fade)">']
    scale = max(w, h) / 1200.0
    for _ in range(count):
        x = round(rng.uniform(0, w), 1)
        # bias toward the top: power curve concentrates stars near y=0
        y = round((rng.random() ** 1.8) * h * top_frac, 1)
        r = round(rng.uniform(0.5, rmax + 0.4) * scale, 2)
        lo = round(rng.uniform(0.15, 0.4), 2)
        hi = round(lo + rng.uniform(0.3, 0.6), 2)
        dur = round(rng.uniform(4, 8), 1)
        begin = round(rng.uniform(0, 3), 2)
        out.append(
            f'    <circle cx="{x}" cy="{y}" r="{r}">'
            f'<animate attributeName="opacity" values="{lo};{hi};{lo}" '
            f'dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></circle>'
        )
    out.append("  </g>")
    return "\n".join(out)


def constellations(w, h, seed):
    """A few short silver polylines confined to the side margins."""
    rng = random.Random(seed)
    scale = max(w, h) / 1200.0
    left = (0.02 * w, 0.26 * w)
    right = (0.74 * w, 0.98 * w)
    out = [f'  <g stroke="#9aa3bd" stroke-width="{round(0.6*scale,2)}" '
           f'stroke-opacity="0.26" fill="none" stroke-linecap="round" '
           f'stroke-linejoin="round" mask="url(#fade)">']
    for band in (left, right, left, right):
        n = rng.randint(3, 4)
        pts = []
        for _ in range(n):
            x = round(rng.uniform(*band), 1)
            y = round(rng.uniform(0.05 * h, 0.4 * h), 1)
            pts.append(f"{x},{y}")
        dur = round(rng.uniform(6.5, 9.5), 1)
        out.append(
            f'    <polyline points="{" ".join(pts)}">'
            f'<animate attributeName="stroke-opacity" values="0.1;0.3;0.1" '
            f'dur="{dur}s" repeatCount="indefinite"/></polyline>'
        )
    out.append("  </g>")
    return "\n".join(out)


def vmark(cx, top_y, size):
    """V-as-constellation mark (favicon geometry) scaled into a `size` box,
    horizontally centered on cx with its top edge at top_y."""
    f = size / 32.0
    x0 = cx - size / 2.0
    def P(px, py):
        return round(x0 + px * f, 1), round(top_y + py * f, 1)
    al = P(8, 9); vx = P(16, 24); ar = P(24, 9)
    halo = round(5.4 * f, 1); mid = round(3 * f, 1); core = round(2.2 * f, 1)
    arm = round(2 * f, 1)
    return f"""  <g>
    <polyline points="{al[0]},{al[1]} {vx[0]},{vx[1]} {ar[0]},{ar[1]}" fill="none"
      stroke="{STEEL}" stroke-width="{round(1.1*f,1)}" stroke-linecap="round"
      stroke-linejoin="round" opacity="0.6"/>
    <g fill="#8fb4d8">
      <circle cx="{al[0]}" cy="{al[1]}" r="{arm}"/>
      <circle cx="{ar[0]}" cy="{ar[1]}" r="{arm}"/>
    </g>
    <circle cx="{vx[0]}" cy="{vx[1]}" r="{halo}" fill="{STEEL}" opacity="0.16"/>
    <circle cx="{vx[0]}" cy="{vx[1]}" r="{mid}" fill="{STEEL}" opacity="0.34"/>
    <circle cx="{vx[0]}" cy="{vx[1]}" r="{core}" fill="#e6eefb" filter="url(#glow)"/>
  </g>"""


def wordmark(cx, baseline, size, cursor=True):
    cur = (f'<tspan dx="{round(size*0.04,1)}" fill="{EMBER}">▎'
           f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1"'
           f' dur="1.1s" repeatCount="indefinite"/></tspan>') if cursor else ""
    return (f'  <text x="{cx}" y="{baseline}" text-anchor="middle" '
            f'font-family="{SANS}" font-size="{size}" font-weight="800" '
            f'letter-spacing="{round(-size*0.022,2)}" fill="{FG}">'
            f'Vladimir Beliaev{cur}</text>')


def tagline(cx, baseline, size, text="AI&#160;FULL&#160;STACK&#160;&#183;&#160;PRODUCT&#160;&#183;&#160;ANALYTICS"):
    return (f'  <text x="{cx}" y="{baseline}" text-anchor="middle" '
            f'font-family="{MONO}" font-size="{size}" '
            f'letter-spacing="{round(size*0.36,1)}" fill="{MUTED}">{text}</text>')


def handle(cx, baseline, size, text="@vvbeliaev"):
    return (f'  <text x="{cx}" y="{baseline}" text-anchor="middle" '
            f'font-family="{MONO}" font-size="{size}" '
            f'letter-spacing="{round(size*0.1,1)}" fill="{STEEL}">{text}</text>')


def safezone(x, y, w, h):
    """Faint guide for the YouTube safe area (kept very subtle, brand-colored)."""
    return (f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
            f'stroke="{EMBER}" stroke-opacity="0.0" rx="4"/>')


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" fill="none" role="img" aria-label="{label}">\n'
            f'  <title>{label}</title>\n{defs_block}\n{body}\n</svg>\n')


ARIA = "Vladimir Beliaev — AI Full Stack Engineer, Product Lead, Analytics Engineer"

# ---- YouTube 2560x1440, content inside the 1546x423 safe zone (centered) ----
w, h = 2560, 1440
cx, cy = w / 2, h / 2
defs_block = defs(w, h, ember_cy=0.2, fade_start=0.5)
body = "\n".join([
    skybox(w, h),
    constellations(w, h, seed=11),
    stars(w, h, count=150, seed=21, top_frac=0.62, rmax=1.4),
    wordmark(cx, cy + 6, size=132),
    tagline(cx, cy + 92, size=33),
])
(OUT / "youtube-banner.svg").write_text(svg(w, h, body, ARIA))

# ---- Vertical 9:16, 1080x1920 (Stories / TikTok / Reels) ----
w, h = 1080, 1920
cx = w / 2
defs_block = defs(w, h, ember_cy=0.16, fade_start=0.5)
body = "\n".join([
    skybox(w, h),
    constellations(w, h, seed=31),
    stars(w, h, count=130, seed=41, top_frac=0.55, rmax=1.5),
    vmark(cx, top_y=560, size=360),
    wordmark(cx, baseline=1180, size=86),
    tagline(cx, baseline=1238, size=25),
    handle(cx, baseline=1790, size=26),
])
(OUT / "vertical-9x16.svg").write_text(svg(w, h, body, ARIA))

# ---- Square 1:1, 1080x1080 (posts) ----
w, h = 1080, 1080
cx = w / 2
defs_block = defs(w, h, ember_cy=0.2, fade_start=0.55)
body = "\n".join([
    skybox(w, h),
    constellations(w, h, seed=51),
    stars(w, h, count=95, seed=61, top_frac=0.6, rmax=1.4),
    vmark(cx, top_y=250, size=250),
    wordmark(cx, baseline=700, size=74),
    tagline(cx, baseline=752, size=22),
    handle(cx, baseline=980, size=24),
])
(OUT / "square-1x1.svg").write_text(svg(w, h, body, ARIA))

# ---- OG card 1200x630 (link previews) ----
w, h = 1200, 630
cx, cy = w / 2, h / 2
defs_block = defs(w, h, ember_cy=0.22, fade_start=0.55)
body = "\n".join([
    skybox(w, h),
    constellations(w, h, seed=71),
    stars(w, h, count=90, seed=81, top_frac=0.6, rmax=1.3),
    wordmark(cx, baseline=cy + 4, size=92),
    tagline(cx, baseline=cy + 66, size=24),
    handle(cx, baseline=cy + 150, size=22),
])
(OUT / "og-1200x630.svg").write_text(svg(w, h, body, ARIA))

print("written:")
for p in sorted(OUT.glob("*.svg")):
    print(" ", p.relative_to(OUT.parent.parent.parent), p.stat().st_size, "bytes")
