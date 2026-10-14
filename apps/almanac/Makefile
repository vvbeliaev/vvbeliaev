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
#   make bench     живой замер собеседника на настоящей модели (платно; ключ и цепочка — evals/README.md)
#   make bench-report  сводка последнего прогона и сравнение с базовой линией BASELINE
#   make bench-accept  принять последний прогон базовой линией BASELINE
#
# Порт сервера: PORT=8920 make up.

.DEFAULT_GOAL := status
.PHONY: up down restart status logs migrate dump test web web-dev bench bench-report bench-accept

BENCH_OUT ?= .bench/bench.jsonl
BASELINE ?= evals/baseline/prod.json

up down restart status logs migrate dump:
	@scripts/procs.sh $@

test:
	uv run --package almanac ruff check .
	uv run --package almanac pytest -q

web:
	cd web && pnpm install --frozen-lockfile && pnpm build

web-dev:
	cd web && pnpm install --frozen-lockfile && pnpm dev

bench:
	BENCH_OUT=$(BENCH_OUT) uv run --package almanac pytest -q -p no:cacheprovider tests/bench_live.py

bench-report:
	uv run --package almanac python -m evals.core.report $(BENCH_OUT) --baseline $(BASELINE)

bench-accept:
	uv run --package almanac python -m evals.core.report $(BENCH_OUT) --save $(BASELINE)
