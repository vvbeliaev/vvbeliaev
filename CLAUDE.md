# CLAUDE.md

Instructions for agents working in this repository.

## What this is

The workshop of Vladimir Beliaev (AI Full Stack Engineer · Product Lead ·
Analytics Engineer): the personal site, the experiments around it, and the
non-code material they come from. **Personal work only.** Cogisoft — its site,
its products and the infrastructure — lives in its own private repository, and
client projects get theirs. Neither belongs here, and neither arrives here "for
a moment".

This is also the GitHub profile repository — the root `README.md` renders on the
profile page. The root is a shopfront: keep stray files out of it.

## Tiers

| Where | What it holds | Contract |
| :-- | :-- | :-- |
| `apps/<name>/` | Things that ship | Dockerfile, a workflow with a `paths:` filter, a Coolify app, a domain. In the pnpm workspace (glob `apps/*`). |
| `labs/<name>/` | Experiments | A `README.md` with a status. Nothing else is required — no CI, no deploy. |
| `workspace/` | Non-code | Texts, brand assets, strategy, CV. `assets/` is public, `private/` is never in git. |
| `docs/` | The decision journal | One dated, append-only file per decision. |

The line between `labs/` and `workspace/` is **code versus non-code**, not raw
versus finished. Both are places where work happens; only one is executable.

Promotion `labs/x → apps/x` is a deliberate move (`git mv`, add a Dockerfile,
copy a workflow, create the Coolify app), and `apps/x → labs/x` is allowed and
is not a failure. A project can also leave the repository entirely — `git subtree
split` keeps its history — and its registry row stays behind as `exported → <url>`.

## Core rule: the repo is public

Everything outside `workspace/private/` is published on GitHub. Before writing a
file, ask: is this ready to be seen by anyone? Contacts, phone numbers, internal
assessments, raw thoughts, client/employer details beyond the public portfolio,
tokens and keys — **only** under `workspace/private/` (or in secret managers /
GitHub secrets for CI). When in doubt, put it in `private/`. Never move a private
file into a public path "temporarily".

`.github/workflows/guard.yml` fails a push on leaked secrets (gitleaks), on any
tracked path under `workspace/private/`, on a phone number in a public file, on a
lab missing its README or its registry row, on a profile README whose facts
have drifted from the site config, and on a tracked SQLite database file.

## Core rule: design & frontend

**For any question or task touching design, the theme, styles, UI, or a site's
frontend — READ** [`DESIGN.md`](./DESIGN.md) **FIRST.** It is the source of truth
for palette, glow, fonts, atmosphere, components, voice, and rituals: it holds
both the values and the grammar that says what they mean. The `:root` block in
each app's `global.css` is that palette rendered into CSS, not a second opinion —
if the two disagree, the document wins and the CSS is wrong.

- Root `DESIGN.md` is **Corona Bloom**, the personal site's system.
- Don't introduce colors/fonts/tokens outside that document. Update the
  document in lockstep with the change, and record the rationale in
  the journal in `docs/`.
- Themes are single and fixed dark, with no runtime toggle.

Per-app specifics live in each app's own `CLAUDE.md`.

## Toolchains

- **JS — pnpm.** The workspace glob is `apps/*` only; `labs/` stays out so that
  an experiment carries its own lockfile and survives being split out. Root
  scripts: `pnpm dev` (site), and `pnpm build` / `pnpm check`
  across every app (`-r`), so a forgotten app cannot pass silently.
- **Python — uv.** A workspace at the repo root, one `uv.lock`. Members are the
  Python labs and `apps/almanac`. Membership is an
  explicit list in `pyproject.toml`, not a glob — the labs tier is polyglot and
  uv demands a `pyproject.toml` from every member. Members share one resolution
  and one intersected `requires-python`; a lab with conflicting pins or a
  different Python stays out of the list and locks for itself.
- Node version comes from `.nvmrc`. Fonts are self-hosted via
  `@fontsource-variable/*`.
- `pnpm build` in an app directory is the final source of truth for correctness —
  IDE diagnostics lag.

## How knowledge is stored

Two questions decide where a piece of knowledge belongs: **what kind of
statement it is**, and **what should trigger it**. Get either wrong and it
becomes a copy that rots.

**By kind — one statement, one home.** The same claim in two places is not
redundancy, it is a future contradiction.

| Kind | Example | Home |
| :-- | :-- | :-- |
| **Fact** — a value, an inventory | a hex, the lab registry, a version | exactly one file. Every copy that leaves it — another language, another surface, a hand-written list — must be **mechanically checked** against it, or it will diverge. Copies nobody checks are how drift enters |
| **Norm** — what to do | "Russian is written first", "when in doubt, private" | wherever it loads at the moment of the action — see the triggers below |
| **Rationale** — why this, what was rejected | "the gauge was tried on 2026-08-30 and rejected" | the journal in [`docs/`](./docs/) — one dated, append-only file per decision |
| **Intent** — what we are about to do | a spec, before it is built | a temporary document. Once built it collapses into a journal entry and is deleted |

A document earns its place only if it answers something you cannot get by
reading the code. Otherwise it is a copy with a shelf life.

**By trigger — a norm that arrives at the wrong moment is not a norm.**

| Should apply | Put it in |
| :-- | :-- |
| always, everywhere | this file |
| always, when certain files are touched | `.claude/rules/*.md` with `paths:` — fires on the path, cannot misfire |
| when someone decides to do a certain task | a skill — fires on the model matching its description, or on `/name`, and can miss |
| every time, with no judgment allowed | a hook |

`README.md` is none of the above: it is for a person browsing the repository on
GitHub. Description and inventory there; rules and procedures in the files above.

What loads by itself: this file at launch, the nested `CLAUDE.md` files when a
file in their directory is read (`apps/vvbeliaev/`, `apps/almanac/`, `labs/`, `workspace/`), and `.claude/rules/blog.md` whenever an article or a draft is
touched. Only this root file is re-injected after a compaction; the nested ones
return when their directory is read again.

Read on purpose:

| Document | Covers |
| :-- | :-- |
| [DESIGN.md](./DESIGN.md) | The design system — before anything visual |
| [docs/](./docs/) | The decision journal — one dated, append-only file per decision |
| `.claude/skills/vvbeliaev-ops/SKILL.md` | The deploy runbook |

## Deploy & ops

Production: **https://vvbeliaev.dev**. Read the
`vvbeliaev-ops` skill before touching CI, Coolify, Cloudflare, or the server.
Why the pipeline looks like this: `docs/2026-08-15-deploy-pipeline.md`.

`apps/almanac` ships the same way (`.github/workflows/almanac.yml`), with two
differences: its build context is filtered by `apps/almanac/Dockerfile.dockerignore`
(BuildKit prefers it to the root `.dockerignore`), and the `pyproject.toml` of
every `labs/*` member travels into the image, because uv needs each workspace
member's manifest. Its data lives on a Coolify volume, never in this repo.

- **Pipeline:** push to `main` → GitHub Actions (`.github/workflows/<app>.yml`)
  runs `check` → builds the image → pushes to GHCR → triggers Coolify, which
  pulls it. **Nothing is ever built on the server.** Each app has its own
  `apps/<app>/Dockerfile`; the build context is the monorepo root, with
  `workspace/`, `labs/` and `docs/` excluded via `.dockerignore`.
- **Hosting:** Coolify (`https://coolify.vvbeliaev.dev`, MCP server **`coolify`** —
  no suffix; `coolify-th` / `coolify-gleb` are other teams, don't touch them),
  project `portfolio`, server `small-ubuntu-4gb-fsn1-2`. Public traffic arrives
  only through the Cloudflare Tunnel `vvbeliaev-01`; the server exposes no ports.
- **Discipline:** after every push, `gh run watch --exit-status` until green; a
  red `check` means no image and no deploy. Reading prod (logs, status,
  deployments) is free; **any mutation** (deploy/restart/env/tunnel/DNS/re-run of
  a deploy workflow) only on an explicit request from the owner, naming the exact
  resource. Rollback is a mutation too.
- Adding another app to the deploy: the checklist at the end of the ops skill
  (Dockerfile → workflow copy → Coolify Docker Image app → tunnel hostname +
  CNAME).
