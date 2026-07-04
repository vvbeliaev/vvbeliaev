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

- `apps/vvbeliaev` — the personal site and blog. Astro + Svelte 5 + shadcn-svelte,
Tailwind v4, content via Astro Content Collections + MDX, static build (SSG).
- `workspace` — the "kitchen": everything raw and non-buildable. Astro never
looks here; nothing ships from here directly. Holds article drafts
(`workspace/drafts/`) and résumés (`workspace/cv/`). See `workspace/README.md`.
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
- Tokens live in `:root` in `apps/vvbeliaev/src/styles/global.css`, mapped to Tailwind
via `@theme inline`. The atmosphere is the `apps/vvbeliaev/src/components/Atmosphere.astro`
component.
- On any significant theme change, update `DESIGN.md` in lockstep and record the
context/rationale in `docs/design-notes.md`.

## Articles: the writing pipeline

Articles move from a raw "kitchen" (`workspace/`, not built) to the "storefront"
(`apps/vvbeliaev/src/content/blog`, built and schema-checked). The full convention lives
in `workspace/README.md` — read it before working on article drafts or publishing.

Stages: `ideas.md` (one-line idea) → `drafts/<slug>/main.md` (loose Russian draft,
no schema) → `blog/note-NN-slug/ru.mdx` (RU shaped into the schema, `draft: true`)
→ `blog/note-NN-slug/en.mdx` (English translation, `translatedFrom: "ru"`) →
drop `draft: true` to publish.

- **Russian is written first; English is a translation of it.** Mark the EN file
with `translatedFrom: "ru"`; the UI shows a "Translated from Russian" note.
- **Folder per article** in the storefront (`note-NN-slug/ru.mdx` + `en.mdx`),
with the article's cover/assets in the same folder.
- **RU↔EN are linked by a shared `articleNumber`** — no separate translation key.
- "Publishing" is a deliberate promotion (draft → collection + schema), not just
flipping a flag.

## Internationalization (i18n)

- Two locales: **English (default)** and **Russian**.
- UI strings live in `apps/vvbeliaev/src/i18n/` (one dictionary per locale); use the
`useTranslations(lang)` / `getLangFromUrl(url)` helpers rather than hardcoding
copy in components.
- English is served at the root (`/`, `/blog`); Russian is prefixed (`/ru/`,
`/ru/blog`).
- Blog content carries a `lang` field; keep posts paired across locales where it
makes sense, but a post may exist in only one language.



## Build / verification

- From `apps/vvbeliaev`: `pnpm build` — the static build (and the final source of truth
for correctness; IDE diagnostics may lag).
- Fonts are self-hosted via `@fontsource-variable/*`.

