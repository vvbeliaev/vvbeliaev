---
name: Corona Bloom
description: >-
  Deep, somber cold cosmic-chthonic dark theme with a luminous coral-clay core
  and a steel-blue counterpoint. A painterly "skybox" atmosphere (depth
  gradients, a schematic star field with faint constellations in the margins,
  cosmos↔chthonic polarity) under a disciplined typographic "HUD". Single fixed
  dark theme — no runtime toggle.
mode: dark
color-scheme: dark
radius: 0.5rem
fonts:
  display: "Sora"            # headings, numbers, brand — clean geometric, cosmic
  body: "Hanken Grotesk"     # long-form reading
  mono: "JetBrains Mono"     # field-log readouts, code, labels
colors:
  background: "#04050b"      # deep, somber cosmic-chthonic base
  foreground: "#e3e5ee"
  card: "#0a0c14"
  card-foreground: "#e3e5ee"
  popover: "#0a0c14"
  popover-foreground: "#e3e5ee"
  primary: "#f08a72"         # luminous coral-clay — the action / warm core
  primary-foreground: "#1a0d07"
  secondary: "#13161f"
  secondary-foreground: "#e3e5ee"
  muted: "#0e1018"
  muted-foreground: "#7d8294"
  accent: "#5f95c2"          # muted steel-blue — the cool counterpoint
  accent-foreground: "#060f18"
  destructive: "#cf6178"
  border: "#1a2034"
  input: "#1a2034"
  ring: "#f08a72"
  chart-1: "#f08a72"         # coral-clay
  chart-2: "#5f95c2"         # steel blue
  chart-3: "#cfa878"         # muted gold
  chart-4: "#9a86c4"         # muted violet
  chart-5: "#5fb0a4"         # muted teal
glow:
  blur: 24px                 # luminous halo — alive, not faded; still not neon
  spread: -6px
---

# Corona Bloom

A personal blog / field log. The aesthetic: **a deep, somber cosmos with a
luminous warm core** — a coral-clay accent that glows like an ember against a
near-black field, with steel-blue as the cold counterpoint. Inspired by the
sun's corona seen in deep space: a living halo in the dark, not a neon sign.

## 1. Aesthetic DNA

- **Somber cosmic-chthonic base.** Deep near-black (`#04050b`), low ambient
  light. Sky/void above, earth/depth below — the cosmos↔chthonic polarity is the
  recurring conceptual motif, not just decoration.
- **Luminous warm core, cold counterpoint.** Coral-clay (`#f08a72`) is the
  action and the warm core — it should *glow*, alive, not faded; steel-blue
  (`#5f95c2`) is the cool counterpoint. Distinct hues — never blended into a
  muddy lavender/purple.
- **Luminous, not neon.** The accent carries real chroma and a soft halo so it
  reads as a living ember against the dark — but the base stays deep and quiet,
  the cold is carried by the atmosphere, not by dulling the accent.
- **Restraint.** The warm accent is used sparingly as a focused source ("очаг"),
  not as an ambient wash. Most of the surface is dark and still.

## 2. Two-layer construction

The signature: a soft painterly **skybox** under a crisp **HUD**.

- **Skybox (atmosphere).** A fixed background layer carrying mood, rendered as
  deep space — not a screen: a small warm coral очаг (top), a diffuse cold
  nebula haze, a vertical cosmos↔chthonic gradient (cool void above, denser
  black welling up below), a schematic **star field** (irregular stars, biased
  to the top, twinkling) with faint **constellation lines kept to the side
  margins** so they never cross the reading column, and a subtle grain. No
  terminal scanlines — the mood is cosmos, not CRT. Implemented as
  `Atmosphere.astro`.
- **HUD (foreground).** Disciplined typography and iconography that stays
  invariant and legible at any size. Whatever happens in the skybox, text and
  previews must read.

## 3. Color

- Base: deep somber near-black; cards one step lifted (`#0a0c14`).
- Warm core: **coral-clay** `#f08a72` (primary). Cool structure: **steel-blue**
  `#5f95c2` (accent). Muted secondary hues in charts: gold, violet, teal.
- `destructive` is a muted rose (`#cf6178`), never a hot fire-red.
- Borders/inputs are low-contrast cool slate (`#1a2034`).
- **Glow**: a luminous halo via `glow-primary` / `glow-accent`, driven by
  `--glow-blur` (24px) / `--glow-spread` (-6px). Apply to the primary CTA and
  the accent block only — it should glow like an ember, alive but not neon.

## 4. Typography

- **Display — Sora** (geometric, clean, quietly cosmic). Headings, the brand
  wordmark, and big numbers ("by the numbers"). Weight 700–800, tight tracking.
- **Body — Hanken Grotesk.** Long-form reading; comfortable, neutral.
- **Mono — JetBrains Mono.** Field-log readouts, note numbers, labels, code,
  and the blinking terminal cursor. Often uppercase with wide tracking
  (`0.3em`) for HUD labels.

## 5. Atmosphere (skybox) recipe

Rendered as deep space, not a screen. All of this lives in `Atmosphere.astro`.
Back to front:
1. Vertical polarity base — `linear-gradient` cool void `#06070f` (top) →
   `#04050b` → deep earth `#020308` (bottom): the cosmos↔chthonic axis.
2. Chthonic floor — a dark `radial-gradient` welling up from the bottom.
3. Cold nebula depth — large, diffuse, low-saturation indigo/steel
   `radial-gradient`s (~8–10% alpha) — reads as distance, not as an accent.
4. Warm coral очаг — small `radial-gradient` at top-center, ~12% alpha.
5. Schematic **star field** (inline SVG): ~88 irregular stars, seeded so the
   field is stable across builds, biased to the top and thinning toward the
   chthonic floor; the layer is masked to fade before the lower content. Bright
   stars twinkle slowly (staggered).
6. **Constellation lines** between the larger stars, restricted to the side
   bands (`cx < 300 || cx > 700`) with short segments — a faint silver sketch in
   the margins that never crosses the reading column; they twinkle too.
7. Fractal-noise grain (`::after`, ~2.5%, `mix-blend-overlay`) to kill banding.

No terminal scanlines — they read as "screen", and the goal is cosmos.
All motion respects `prefers-reduced-motion`.

## 6. Components

- **Cards** = the HUD panels: `bg-card`, 1px `border`, `--radius` corners,
  optional `backdrop-blur` so the skybox glows through faintly.
- **Buttons**: primary = solid coral-clay with a luminous glow;
  secondary/outline/ghost stay quiet. Links use `primary`.
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

- Body/headings (`#e3e5ee`) on base/card clear AA+ contrast.
- Long-form prose is explicitly themed for dark (see `.prose` overrides).
- Readability beats atmosphere: the skybox never compromises text legibility.
- Glow and motion are subtle; respect `prefers-reduced-motion` for any future
  animation.

## 9. Implementation

- Tokens live in `:root` in `apps/web/src/styles/global.css`, mapped to Tailwind
  v4 via `@theme inline`. Fonts self-hosted via `@fontsource-variable/*`.
- The atmosphere is a single `<Atmosphere />` component rendered once in
  `BaseLayout` (depth gradients + seeded SVG star field/constellations + grain).
  The site is a fixed dark theme (`<html class="dark">`).
