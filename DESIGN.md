---
name: Corona Bloom
description: >-
  High-contrast cold cosmic-chthonic dark theme with luminous pink + blue
  accents. A painterly "skybox" atmosphere (concentrated warm/cool очаг, sparse
  silver constellation lines) under a disciplined typographic "HUD". Single fixed
  dark theme — no runtime toggle.
mode: dark
color-scheme: dark
radius: 0.5rem
fonts:
  display: "Sora"            # headings, numbers, brand — clean geometric, cosmic
  body: "Hanken Grotesk"     # long-form reading
  mono: "JetBrains Mono"     # field-log readouts, code, labels
colors:
  background: "#050711"      # deep cold cosmic-chthonic base
  foreground: "#eef0f6"
  card: "#0c0f1a"
  card-foreground: "#eef0f6"
  popover: "#0c0f1a"
  popover-foreground: "#eef0f6"
  primary: "#f48ab6"         # luminous pink — the action / warm "event"
  primary-foreground: "#1d0a13"
  secondary: "#161a28"
  secondary-foreground: "#eef0f6"
  muted: "#11141f"
  muted-foreground: "#8b91a4"
  accent: "#74bdf0"          # luminous blue — the cool counterpoint
  accent-foreground: "#04131f"
  destructive: "#f0688c"
  border: "#1f2640"
  input: "#1f2640"
  ring: "#f48ab6"
  chart-1: "#f48ab6"         # pink
  chart-2: "#74bdf0"         # blue
  chart-3: "#f0c08a"         # gold
  chart-4: "#b59cf0"         # violet
  chart-5: "#6fd0c0"         # teal
glow:
  blur: 26px
  spread: -8px
---

# Corona Bloom

A personal blog / field log. The aesthetic: **a deep, cold cosmos with a warm
luminous core** — pink and blue accents that *emit light* against a near-black
blue field. Inspired by the sun's corona: a bright halo in the dark.

## 1. Aesthetic DNA

- **Cold cosmic-chthonic base.** Deep blue-black (`#050711`), high contrast.
  Sky/void above, earth/depth below — the cosmos↔chthonic polarity is the
  recurring conceptual motif, not just decoration.
- **Luminous accents.** Pink (`#f48ab6`) is the action and the warm "event";
  blue (`#74bdf0`) is the cool counterpoint. Both *glow* (soft outer halo).
  They are distinct hues — never blended into a muddy lavender/purple.
- **No neon / electric-blue as a flat fill.** Brightness comes from the *glow*,
  not from max saturation. Accents are bright but slightly soft.
- **Restraint.** Accent is used sparingly as a focused source ("очаг"), not as
  an ambient wash. Most of the surface is dark and quiet.

## 2. Two-layer construction

The signature: a soft painterly **skybox** under a crisp **HUD**.

- **Skybox (atmosphere).** A fixed background layer carrying mood, kept
  deliberately clean: a concentrated warm pink glow (top), a cooler blue haze
  (lower), very faint star-dust masked to the top, subtle terminal scanlines,
  and a subtle grain. No schematic constellation linework on the base — it read
  as noise behind text. Implemented as `.atmosphere` (see `global.css`).
- **HUD (foreground).** Disciplined typography and iconography that stays
  invariant and legible at any size. Whatever happens in the skybox, text and
  previews must read.

## 3. Color

- Base: deep cold blue-black; cards one step lifted (`#0c0f1a`).
- Warm event: **pink** `#f48ab6` (primary). Cool structure: **blue** `#74bdf0`
  (accent). Secondary warm hues available in charts: gold, violet, teal.
- `destructive` is a cool-leaning rose (`#f0688c`), never a hot fire-red.
- Borders/inputs are low-contrast cool slate (`#1f2640`).
- **Glow**: luminous elements use the `glow-primary` / `glow-accent` utilities,
  driven by `--glow-blur` / `--glow-spread`. Apply to the primary CTA and the
  accent block — not to everything.

## 4. Typography

- **Display — Sora** (geometric, clean, quietly cosmic). Headings, the brand
  wordmark, and big numbers ("by the numbers"). Weight 700–800, tight tracking.
- **Body — Hanken Grotesk.** Long-form reading; comfortable, neutral.
- **Mono — JetBrains Mono.** Field-log readouts, note numbers, labels, code,
  and the blinking terminal cursor. Often uppercase with wide tracking
  (`0.3em`) for HUD labels.

## 5. Atmosphere (skybox) recipe

Kept clean — glow does the work, texture stays minimal. Back to front:
1. Solid base `#050711`.
2. Cool blue haze — `radial-gradient` lower-right, ~10% alpha.
3. Warm pink очаг — small `radial-gradient` at top-center, ~22% alpha
   (concentrated, not a wash).
4. Subtle terminal scanlines — faint `repeating-linear-gradient`, ~1.6% alpha.
5. Very faint star-dust (`::before`, ~22% opacity), masked to the top only;
   set `--stardust: none` for a fully plain backdrop.
6. Fractal-noise grain (`::after`, ~3%, `mix-blend-overlay`).

Removed as too noisy behind text: the schematic constellation linework.
(Reintroduce locally per-section if ever needed, never site-wide.)

## 6. Components

- **Cards** = the HUD panels: `bg-card`, 1px `border`, `--radius` corners,
  optional `backdrop-blur` so the skybox glows through faintly.
- **Buttons**: primary = solid pink with glow; secondary/outline/ghost stay
  quiet. Links use `primary`.
- **LED indicator** (`led-indicator`): a glowing status dot (borrowed from the
  legacy cogisoft "instrument panel" language).
- **Blinking cursor** (`animate-blink`): a terminal `_` after key headings.
- **Stat block** ("by the numbers"): mono/large display numbers in a bordered
  grid — a recurring ritual.

## 7. Voice & rituals (carry the brand more than any logo)

- **Field log**: numbered notes — "Note #14: why I shut down X".
- **Operator-essayist**: stoic restraint, premium, more philosopher than maker.
- **By-the-numbers** recaps as a recurring rubric.
- One consistent preview format + signature across channels.

## 8. Accessibility & discipline

- Body/headings (`#eef0f6`) on base/card clear AA+ contrast.
- Long-form prose is explicitly themed for dark (see `.prose` overrides).
- Readability beats atmosphere: the skybox never compromises text legibility.
- Glow and motion are subtle; respect `prefers-reduced-motion` for any future
  animation.

## 9. Implementation

- Tokens live in `:root` in `apps/web/src/styles/global.css`, mapped to Tailwind
  v4 via `@theme inline`. Fonts self-hosted via `@fontsource-variable/*`.
- The atmosphere is a single `<div class="atmosphere">` rendered once in
  `BaseLayout`. The site is a fixed dark theme (`<html class="dark">`).
