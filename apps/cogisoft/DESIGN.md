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

The site for **Cogisoft — project and contract work: build the demand system,
then run it**. Two page types:

- **Root** (`/`, `/ru/`) — the hub: RootHero → Phases → Offers → Cases →
  NotFor → Who → Contact. Its signature is `SolutionLoop`, not SignalField —
  the two heroes never run the same effect.
- **Offer** (`/offers/<slug>`) — one offer, argued in full. Currently
  `signals` (the original landing, kept as a proto-offer): Hero → Manifesto →
  Funnel (5 stages) → Contact.

`Cases` renders nothing until `CASES` has entries — pages follow cases, never
the other way round. Original spec (single-page era):
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
- `SignalField.astro` — the signature of the **offer** hero only (absolute
  within the hero, not fixed): ~170 seeded steel ticks (dots + short vertical
  dashes — data points, not stars), out of which one region turns out to be
  dense. 26 cluster points ignite coral from the centre outward (~1.5s), then
  a warm halo settles under them and the cluster breathes. The animation is
  the pitch: noise → density → evidence.
- **Never a line.** An earlier version drew a rising 8-node polyline; it read
  as a stock chart ("number go up") — the most generic startup visual there
  is, and the opposite of the thesis. The pattern is expressed as
  **concentration**: no axis, no trend, only "here is where the demand is".
  `Manifesto.astro` follows the same rule — its "edge" panel answers the
  uniform grid with a cluster, not a trend.
- The cluster sits near the viewBox centre so it survives the mobile crop
  (`preserveAspectRatio: xMidYMid slice`).
- A radial mask calms the field under the hero text (bottom-left).
- The hero is **not** full-viewport: `min-h-svh` left the top empty on tall
  windows and hid the next section. It now ends above the fold so the
  manifesto peeks.
- `prefers-reduced-motion`: fully static, cluster and halo pre-lit coral.

### SolutionLoop — the root signature

`SolutionLoop.astro` states the business in one picture: **what gets built
varies and it ends; how it is run is always the same and it doesn't.**

On the left, four kinds of thing — funnel, app, internal tool, optimisation —
converge through a fan into a single junction. On the right, one ring turns
with a pulse that never stops: watch → report → repair. That gap between a
finite, varied left and an infinite, uniform right IS the offer.

**The split is carried by grammar, not only by shape.** The left half is
NOUNS — things, and a thing ends. The right half is VERBS in the first person
— actions, and an action repeats. Keep it that way when editing: an earlier
pass used "Alive" on the ring, an adjective among nouns, and it read as a
status light rather than as work being done. The ring's three verbs are the
same three the hero subtitle uses, word for word, so sentence and picture
agree.

Each half is tagged with its contract phase and a caption ("built once" /
"run as long as needed"), which needs no legend and makes the diagram a map
of the Phases section further down the page.

Grammar: steel is structure — the thing being assembled. The ring is coral
because it carries the numbers that keep proving the thing works; its stroke
stays faint (55%) so coral never becomes ambient, and the travelling pulse is
the bright part.

Two dead ends, kept here so they are not re-walked:

- **A rising polyline.** Read as a stock chart. Same rejection as SignalField:
  never a trend, never an axis.
- **A single funnel ring** (Traffic → Page → Lead → Qualification → CRM). Too
  narrow — the business builds any kind of tech, not one lead funnel — and
  every node was a Phase-1 artifact, so the diagram promised "build and run"
  while showing only "build". Worse, it terminated on the client's CRM, i.e.
  on a handoff, which is precisely the opposite of the thesis.

Geometry note: the ring's labels sit at `r + 30` along their own radius and the
viewBox runs to 440; at tighter values the lower-left label rendered on top of
the ring stroke.

## 3. Section grammar (root)

`Section.astro` pins the mono label in a narrow left gutter and runs content in
the wide column beside it, identically for every root section. It replaced a
stack of centred blocks that left the right half of a `max-w-6xl` container
empty — the page now reads as one annotated instrument, and quiet stops looking
like unfinished.

## 4. The funnel rail

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

## 5. Voice

Market-first, operator-calm, zero agency-speak. **First person singular** —
there is no team, and "we" collapses on the first call; contractors get named
as contractors once they exist. The word "studio" is retired: it reads as a
competing organisation and it is not what this is.

Copy rules: every stage is a hypothesis with a method, an artifact and a gate
— never a "service"; every offer names an audience, a pain and a measurable
promise, and says out loud what it excludes; honesty as a differentiator ("an
honest stop that saves you months", plus an explicit "not for you if"
section). EN is primary, RU is a parallel voice, not a literal translation.

The **terminal mark** on display headlines is drawn, not typed: the
`full-stop` / `full-stop-accent` utilities in `global.css`. Sora's full stop
is squarish, and at display sizes the coral glyph stopped reading as
punctuation and no longer matched the white periods in the same headline.

## 6. Implementation

- Astro + Tailwind v4, static build, no Svelte islands in v1 — interaction
  is CSS animations plus two small vanilla scripts (funnel observer).
- Tokens: `src/styles/global.css` (`:root` + `@theme inline`) — a trimmed
  copy of the personal site's tokens. Extracting a shared theme package into
  `pkgs/ts` is deliberately deferred until this second theme stabilizes.
- i18n mirrors `apps/vvbeliaev`: EN at root, RU under `/ru/`, dictionaries in
  `src/i18n/ui.ts`. Offer/case copy is locale-keyed in `src/lib/config.ts`
  (`Record<Lang, string>`), since it is data rather than UI chrome.
- The primary CTA points at Telegram, not `hello@cogisoft.dev` — that mailbox
  is unverified (see the TODO in `config.ts`) and a dead CTA is worse than
  none.
