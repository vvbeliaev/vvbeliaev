# almanac

Rules for working in this app. Repo-wide rules are in the root
[CLAUDE.md](../../CLAUDE.md).

- **The repo is public, the data is not.** Tests, fixtures and `schema/` hold
  invented data only. Nothing from a real almanac database ever enters git.
- **One process, one worker.** The reminder loop and the bot live in process
  memory: two workers mean double reminders. The write lock is not in memory
  but in Postgres (`pg_advisory_xact_lock`, the first statement of `db.write()`),
  so a second process writing to the same database, like the local MCP door, is safe.
- **The assistant is a client, not the core.** `assistant.py` runs a model for the
  owner's Telegram messages through the same MCP door as any other client: no
  private path into `store/`, no rule that lives only in its prompt. Whatever must
  hold is enforced by the server. It never sees forwarded messages, its writes carry
  the client name `agent`, and the bot records the owner's words before calling it,
  so a model failure loses nothing. No `LLM_API_KEY` — no assistant.
- **Writes go through `store/`**, inside `async with db.write()`, and leave a
  `journal` row. The API and the bot never touch tables directly.
- **Refusals are instructions.** A `Refused` message tells the model what to
  fix. Endpoint docstrings are tool descriptions: English, written for a model.
- **One fact, one home.** The catalog, the inbox, the agenda and the item lines
  are projections computed in `tree.py`. Do not store a second copy of them.
- **Every `/api` answer is an object with a response model** (`api/shapes.py`), and a
  list is never the top level: Code Mode would hand a bare list to the script wrapped
  in `result`. A list lives under a name (`entries`, `matches`, `items`, `revisions`);
  every field carries a one-line description, because `get_schema` is built from them.
- **A repeating task is one row** that holds its next occurrence in `due`/`at`. `done`
  moves it to the next one and writes `item_done` to the journal: the journal is the
  history of completions, there is no row per completion.
- **Postgres is strict.** Text longer than its `String(n)`
  column, `\x00` in any text, a number outside `int32`: each is a database error and
  a 500. Whatever lands in a column is checked at the boundary and refused with
  `Refused` (`checks.py`); `clean_input` in `api/deps.py` rejects NUL on every route.
  Columns that SQL sorts by carry `collation="C"`, so order does not depend on the server's locale.
- **Schema changes need a migration.** Autogenerate compares the models with a
  live database, so first bring an empty scratch database on any Postgres to
  head, then generate against it (same `DATABASE_URL` for both):
  `DATABASE_URL=postgresql+asyncpg://…/scratch uv run alembic upgrade head`, then
  `DATABASE_URL=postgresql+asyncpg://…/scratch uv run alembic revision --autogenerate -m "…"`.
  `migrations/env.py` renders `UtcDateTime` as `sa.DateTime(timezone=True)` and the
  template adds the imports a column type needs; read the generated file anyway, and
  drop the scratch database. `tests/test_migrations.py` fails when models and
  migrations drift.
- **The site only reads.** `web/` issues `GET` requests and nothing else. `LOCAL_SITE`
  (`identity.py`) lets a browser on the same machine read without signing in; it never
  covers a write, and the config refuses it on a public `BASE_URL`. It tells the owner's
  browser from a foreign site, not from foreign code: any local process or Docker
  container can read through it, which is why the local database has a password
  (`.env`, written by `make up`). The page renders
  third-party text, so Markdown goes through DOMPurify (`web/src/lib/markdown.ts`) and the
  server sends the site with a strict `Content-Security-Policy` (`SITE_CSP` in `app.py`).
- **The site follows the root `DESIGN.md`** (Corona Bloom). The `:root` block in
  `web/src/app.css` is that palette rendered into CSS; no colors or fonts outside it.
  `web/` is its own pnpm root with its own lockfile: `pnpm check`, `pnpm test`,
  `pnpm build` from `web/`.
- **Secrets**: the owner's password, the bot token and the calendar secret come
  from the environment. Never print them, never put them in a test. The bot
  token must not reach logs or exception texts (`telegram.py`).
- Run from this directory: `uv run pytest -q` (needs Docker: the tests start their
  own Postgres, `postgres:18-alpine`, and never touch the development database),
  `uv run ruff check .`.
