---
name: Corona Signal
parent: Corona Bloom (../../DESIGN.md)
description: >-
  The agency variant of Corona Bloom for cogisoft.dev. Same somber cosmic
  base, fonts and glow language — but an inverted color grammar: steel-blue
  carries the market noise and structure, coral-clay is reserved for
  confirmed signals (evidence) and the CTA. The atmosphere is a signal field
  read like instruments, not a night sky read like a map.
mode: dark
---

# Corona Signal

The landing for **Cogisoft — a market-first validation studio**. One page:
Hero → Manifesto → Funnel (5 stages) → Contact. Spec:
`docs/superpowers/specs/2026-07-04-cogisoft-landing-design.md`.

## 1. Relation to Corona Bloom

Inherited verbatim (do not fork): base palette (`#04050b` background,
`#0a0c14` card, `#e3e5ee` foreground, `#1a2034` border), the Sora / Hanken
Grotesk / JetBrains Mono triad, radius `0.5rem`, glow variables
(`--glow-blur: 24px`, `--glow-spread: -6px`), HUD discipline (mono uppercase
labels, wide tracking), card panels, the LED indicator and blinking-cursor
rituals.

Changed — the **color grammar is inverted**:

- **Steel-blue `#5f95c2` = market noise & structure.** Section eyebrows,
  stage labels, the signal field's ticks, the funnel rail's cold end. On the
  personal site blue is the counterpoint; here it is the working color.
- **Coral-clay `#f08a72` = evidence only.** The CTA, ignited constellation
  nodes, passed funnel gates, the "You get" (artifact) label, the wordmark
  cursor. Coral is never ambient — it must always mean "the market said
  yes". The page-wide backdrop deliberately has **no warm core** (unlike
  Atmosphere): warmth exists only where evidence ignites.

## 2. Atmosphere: SignalField, not starfield

- `Backdrop.astro` — page-wide fixed layer: cold indigo/steel nebula depth,
  chthonic floor, vertical polarity, grain. No coral очаг.
- `SignalField.astro` — the hero signature (absolute within the hero, not
  fixed): ~170 seeded steel ticks (dots + short vertical dashes — data
  points, not stars), out of which a hand-placed 8-node constellation is
  drawn segment by segment (~0.5s per segment), nodes igniting coral as the
  line reaches them; once complete, the whole pattern warms to coral. The
  animation is the pitch: noise → pattern → evidence.
- The constellation's first two-thirds sit in the viewBox center strip so it
  survives the mobile crop (`preserveAspectRatio: xMidYMid slice`).
- A radial mask calms the field under the hero text (bottom-left).
- `prefers-reduced-motion`: fully static, constellation pre-lit coral.

## 3. The funnel rail

The services/process section is one component (`Funnel.astro`): five stage
cards (`STAGE 00 · DISCOVERY` … `STAGE 04 · MVP`) on a vertical rail.

- Dim rail = `--border`; lit rail = blue→coral gradient whose height extends
  to the last ignited node (IntersectionObserver + height transition).
- Stage nodes ignite coral when the card enters the viewport (gate passed).
- Each card carries a **dot cluster** that densifies down the funnel
  (3 → 26 dots: the audience accumulates) with a growing coral share
  (evidence stacks up); the MVP stage gets a glowing coral core.
- Stage mono labels stay English in both locales — a brand ritual.
- Kill criteria strip closes the section (mono, coral prefix).

## 4. Voice

Market-first, operator-calm, zero agency-speak. Copy rules: every stage is a
hypothesis with a method, an artifact and a gate — never a "service"; coral
period at the end of display headlines; honesty as a differentiator ("an
honest stop that saves you months"). EN is primary, RU is a parallel voice,
not a literal translation.

## 5. Implementation

- Astro + Tailwind v4, static build, no Svelte islands in v1 — interaction
  is CSS animations plus two small vanilla scripts (funnel observer).
- Tokens: `src/styles/global.css` (`:root` + `@theme inline`) — a trimmed
  copy of the personal site's tokens. Extracting a shared theme package into
  `pkgs/ts` is deliberately deferred until this second theme stabilizes.
- i18n mirrors `apps/vvbeliaev`: EN at root, RU under `/ru/`, dictionaries in
  `src/i18n/ui.ts`.
