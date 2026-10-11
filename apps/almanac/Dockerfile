# syntax=docker/dockerfile:1
# Образ almanac. Контекст сборки — корень монорепы: оттуда общий `uv.lock`.
#
#     docker build -f apps/almanac/Dockerfile -t almanac .
#
# Настройки приходят окружением контейнера (`almanac.config.Settings`); `.env` в образ не едет.
# Данные — том `/data`: база и её копии.

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
    BACKUP_DIR=/data/backups
WORKDIR /repo/apps/almanac
USER almanac
VOLUME /data
EXPOSE 8000
# Один воркер: замок записи, цикл напоминаний и бот живут в памяти процесса.
# Без журнала доступа: секрет ленты и коды OAuth лежат в адресах запросов.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn almanac.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --no-access-log"]
