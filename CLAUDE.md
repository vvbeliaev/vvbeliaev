# [CLAUDE.md](http://CLAUDE.md)

Instructions for agents working in this repository.

## What this is

A personal-brand monorepo for Vladimir Beliaev (AI Full Stack Engineer · Product
Lead · Analytics Engineer) — a single source of truth for the site, long-form
blog posts, and job-search materials. The brand rests not on a logo but on a
consistent voice and a couple of rituals (numbered "notes", one preview format,
a "by the numbers" rubric).

The site is **bilingual — English and Russian.**

## Structure

- `apps/web` — the personal site and blog. Astro + Svelte 5 + shadcn-svelte,
Tailwind v4, content via Astro Content Collections + MDX, static build (SSG).
- `cv` — résumés for different roles. Standalone artifacts (backbone → reflections
→ pdf), not a workspace package; nothing imports them yet.
- `DESIGN.md` — the site's **design system** (theme "Corona Bloom"). The source
of truth for colors/tokens, fonts, atmosphere, components, and voice.
- `docs/design-notes.md` — the design-decision journal: what was tried, the
forks, and what was rejected.

pnpm workspace (`apps/*`, `pkgs/*`).

## Core rule: design & frontend

**For any question or task touching design, the theme, styles, UI, or the site's
frontend — READ** `[DESIGN.md](./DESIGN.md)` **FIRST.** It is the source of truth for
all visual decisions: palette, glow, fonts, atmosphere (skybox), components,
voice, and rituals.

- Don't introduce new colors/fonts/tokens outside `DESIGN.md` — check it first,
and update the document when needed.
- The theme is **single and fixed dark** (`<html class="dark">`), with no runtime
toggle.
- Tokens live in `:root` in `apps/web/src/styles/global.css`, mapped to Tailwind
via `@theme inline`. The atmosphere is the `apps/web/src/components/Atmosphere.astro`
component.
- On any significant theme change, update `DESIGN.md` in lockstep and record the
context/rationale in `docs/design-notes.md`.

c

## Internationalization (i18n)

- Two locales: **English (default)** and **Russian**.
- UI strings live in `apps/web/src/i18n/` (one dictionary per locale); use the
`useTranslations(lang)` / `getLangFromUrl(url)` helpers rather than hardcoding
copy in components.
- English is served at the root (`/`, `/blog`); Russian is prefixed (`/ru/`,
`/ru/blog`).
- Blog content carries a `lang` field; keep posts paired across locales where it
makes sense, but a post may exist in only one language.



## Build / verification

- From `apps/web`: `pnpm build` — the static build (and the final source of truth
for correctness; IDE diagnostics may lag).
- Fonts are self-hosted via `@fontsource-variable/*`.

