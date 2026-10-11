# almanac на своей машине одной командой; логика — в scripts/procs.sh.
#
#   make up        база, миграции (с дампом, если база отстаёт) и сервер на 127.0.0.1:8910
#   make down      остановить сервер, дождавшись выхода; база остаётся
#   make restart   down + up
#   make status    идёт ли сервер и с какого коммита, /healthz, ревизия базы
#   make logs      хвост журнала .run/server.log
#   make migrate   дамп в ~/almanac-backups, затем alembic upgrade head
#   make dump      дамп базы в ~/almanac-backups сейчас
#   make test      ruff и pytest; тесты поднимают свой Postgres и рабочую базу не трогают
#   make web       пересобрать сайт (web/dist); сервер отдаёт его с корня
#   make web-dev   сайт с горячей перезагрузкой на http://127.0.0.1:5173; нужен make up
#
# Порт сервера: PORT=8920 make up.

.DEFAULT_GOAL := status
.PHONY: up down restart status logs migrate dump test web web-dev

up down restart status logs migrate dump:
	@scripts/procs.sh $@

test:
	uv run --package almanac ruff check .
	uv run --package almanac pytest -q

web:
	cd web && pnpm install --frozen-lockfile && pnpm build

web-dev:
	cd web && pnpm install --frozen-lockfile && pnpm dev
