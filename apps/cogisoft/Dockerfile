# Сборка cogisoft из корня монорепы: контекст сборки — корень репозитория,
# путь к этому файлу задаётся отдельно (в CI — `file: apps/cogisoft/Dockerfile`).
# Сайт статический (`output: "static"`), поэтому Node в рантайме не нужен:
# в образ едут только `dist/` и Caddy, который его раздаёт.

FROM node:24-alpine AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /app

# Манифесты отдельным слоем: пока зависимости не менялись, install берётся из кэша.
FROM base AS manifests
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/cogisoft/package.json apps/cogisoft/

FROM manifests AS deps
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

FROM deps AS build
COPY apps/cogisoft apps/cogisoft
RUN pnpm --filter cogisoft build

FROM caddy:2-alpine AS runtime
COPY apps/cogisoft/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/apps/cogisoft/dist /srv

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
	CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
