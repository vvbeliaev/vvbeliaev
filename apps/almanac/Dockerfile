# syntax=docker/dockerfile:1
# Образ almanac. Контекст сборки — корень монорепы: оттуда общий `uv.lock`.
#
#     docker build -f apps/almanac/Dockerfile -t almanac .
#
# Настройки приходят окружением контейнера (`almanac.config.Settings`), прежде всего `DATABASE_URL`:
# адреса базы в образе нет, и `.env` в образ не едет. Данные живут в Postgres, контейнер без состояния:
# тома ему не нужно, образ можно пересоздать в любой момент.

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
RUN useradd --create-home --uid 1000 almanac
COPY --from=deps --chown=almanac:almanac /repo /repo
ENV PATH=/repo/.venv/bin:$PATH
WORKDIR /repo/apps/almanac
USER almanac
EXPOSE 8000
# HEALTHCHECK намеренно нет. Проверка здоровья заставляет платформу катить контейнеры
# внахлёст: пока старый ещё жив, стартует новый. Два живых процесса на одной базе — это
# двойные напоминания и миграция под работающим приложением. Старый должен остановиться
# раньше, чем стартует новый. `/healthz` остаётся для ручной проверки.
# Один экземпляр и один воркер. Замок записи лежит в базе и держит и несколько процессов, но цикл
# напоминаний и бот живут в памяти процесса: второй экземпляр прислал бы каждое напоминание дважды.
# Без журнала доступа: секрет ленты и коды OAuth лежат в адресах запросов.
# Сначала `alembic upgrade head`: схему ведёт миграция, не приложение. Не накатилась — контейнер не стартует.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn almanac.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 1 --no-access-log --timeout-graceful-shutdown 5"]
