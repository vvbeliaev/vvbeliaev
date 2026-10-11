# almanac

Rules for working in this app. Repo-wide rules are in the root
[CLAUDE.md](../../CLAUDE.md).

- **The repo is public, the data is not.** Tests, fixtures and `schema/` hold
  invented data only. Nothing from a real almanac database ever enters git.
- **One process, one worker.** The write lock, the reminder loop and the bot
  live in process memory. Two workers mean double reminders and lost updates.
- **Writes go through `store/`**, inside `async with db.write()`, and leave a
  `journal` row. The API and the bot never touch tables directly.
- **Refusals are instructions.** A `Refused` message tells the model what to
  fix. Endpoint docstrings are tool descriptions: English, written for a model.
- **One fact, one home.** The catalog, the inbox, the agenda and the item lines
  are projections computed in `tree.py`. Do not store a second copy of them.
- **Schema changes need a migration**: `uv run alembic revision --autogenerate`,
  then replace `almanac.models.UtcDateTime()` with `sa.DateTime()` in the file.
  `tests/test_migrations.py` fails when models and migrations drift.
- **Secrets**: the owner's password, the bot token and the calendar secret come
  from the environment. Never print them, never put them in a test. The bot
  token must not reach logs or exception texts (`telegram.py`).
- Run from this directory: `uv run pytest -q`, `uv run ruff check .`.
