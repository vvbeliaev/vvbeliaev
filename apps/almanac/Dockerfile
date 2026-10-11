# syntax=docker/dockerfile:1
# Образ almanac. Контекст сборки — корень монорепы: оттуда общий `uv.lock`.
#
#     docker build -f apps/almanac/Dockerfile -t almanac .
#
# Настройки приходят окружением контейнера (`almanac.config.Settings`); `.env` в образ не едет.
# Данные — том `/data`: база и её копии. Том обязателен, и объявлять его здесь нельзя:
# с `VOLUME /data` забытый том молча заменяется анонимным, и каждая выкладка стартует
# на пустой базе. Вместо этого `python -m almanac.migrate` отказывается стартовать,
# если `/data` не смонтирован (`DATA_MOUNT`).

FROM python:3.13-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1

FROM base AS deps
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
WORKDIR /repo
# Сначала только зависимости: правка кода не пересобирает этот слой.
COPY pyproject.toml uv.lock ./
COPY labs labs
COPY apps/almanac/pyproject.toml apps/almanac/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package almanac --no-install-project
COPY apps/almanac apps/almanac
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package almanac

FROM base AS runtime
RUN useradd --create-home --uid 1000 almanac \
    && mkdir /data && chown almanac:almanac /data
COPY --from=deps --chown=almanac:almanac /repo /repo
ENV PATH=/repo/.venv/bin:$PATH \
    DATABASE_URL=sqlite+aiosqlite:////data/almanac.db \
    BACKUP_DIR=/data/backups \
    DATA_MOUNT=/data
WORKDIR /repo/apps/almanac
USER almanac
EXPOSE 8000
# HEALTHCHECK намеренно нет. Проверка здоровья заставляет платформу катить контейнеры
# внахлёст: пока старый ещё жив, стартует новый. Два живых процесса на одной базе — это
# двойные напоминания и миграция под работающим приложением. Старый должен остановиться
# раньше, чем стартует новый. `/healthz` остаётся для ручной проверки.
# Один воркер: замок записи, цикл напоминаний и бот живут в памяти процесса.
# Без журнала доступа: секрет ленты и коды OAuth лежат в адресах запросов.
# Сначала `almanac.migrate`: проверка тома, копия базы перед обновлением, `alembic upgrade head`.
CMD ["sh", "-c", "python -m almanac.migrate && exec uvicorn almanac.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --no-access-log --timeout-graceful-shutdown 5"]
