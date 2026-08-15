# Деплой vvbeliaev.dev: CI → GHCR → Coolify за Cloudflare Tunnel

Дата: 2026-08-15. Статус: реализован 2026-08-15 (сайт в проде).

## Цель

Сайт `apps/vvbeliaev` (Astro, статика) публикуется на `https://vvbeliaev.dev`
автоматически при push в `main`. Сборка — в GitHub Actions, сервер только
тянет готовый образ. Сервер не светит публичные порты — трафик идёт через
Cloudflare Tunnel.

## Контекст

- Cloudflare-зона `vvbeliaev.dev` (аккаунт `vvbeliaev`), DNS пустой, туннелей нет.
- Coolify — инстанс `https://coolify.cogisoft.dev`, личная команда, MCP-сервер
  `coolify` (без суффикса). Проект `portfolio`, окружение `production` — уже
  созданы, пустые.
- Сервер `small-ubuntu-4gb-fsn1-2` (Hetzner fsn1, 2 vCPU / 4 ГБ, tailnet
  `100.64.0.1`). Живёт calisthenics; порты 80/443 не трогаем.
- Репозиторий `vvbeliaev/vvbeliaev` публичный → образ в GHCR публичный,
  без лимитов и логина при pull.

## Архитектура

```
push main ──► GitHub Actions
              check: pnpm install, astro check, astro build
              build: buildx → ghcr.io/vvbeliaev/vvbeliaev:{latest,sha-<full>}
              deploy: POST {COOLIFY_URL}/api/v1/deploy?uuid=<app>
                                │
Coolify (small-ubuntu) ◄────────┘  pull image, restart container
   Traefik :443 (localhost)  ◄──── cloudflared (Coolify-сервис, host network, туннель vvbeliaev-01)
                                          ▲
Cloudflare edge (TLS, proxied CNAME) ◄────┘
```

### 1. Сеть

- Туннель `vvbeliaev-01` создаётся через Cloudflare API (remotely-managed).
- Ingress: `vvbeliaev.dev` → `https://localhost:443`, `noTLSVerify: true`;
  catch-all → `http_status:404`. Схема из документации Coolify: Traefik
  сохраняет https-роутер и редирект http→https, петли нет.
- Cloudflared — сервис Coolify из шаблона `cloudflared`
  (`cloudflared-vvbeliaev-01`, проект `net`, окружение `production`) на том же
  сервере. Шаблон использует `network_mode: host`, поэтому origin — `localhost`,
  а не `coolify-proxy`. Токен туннеля — env `CLOUDFLARE_TUNNEL_TOKEN`.
- DNS: proxied CNAME `vvbeliaev.dev` → `<tunnel-id>.cfargotunnel.com`.
  Зона: SSL mode `Full`. `www` — не в v1.

### 2. Образ

- `apps/vvbeliaev/Dockerfile`, контекст сборки — корень монорепы (паттерн
  traffhub: манифесты отдельным слоем, `pnpm install --frozen-lockfile`,
  `pnpm --filter vvbeliaev build`).
- Рантайм: `caddy:2-alpine`, `dist/` в `/srv`, `Caddyfile`:
  `:8080`, `file_server`, `encode zstd gzip`, `handle_errors` → `/404.html`,
  `Cache-Control: immutable` для `/_astro/*`.
- Корневой `.dockerignore`: `node_modules`, `dist`, `.git`, `workspace/`,
  `docs/`, `.env*`.

### 3. Workflow `.github/workflows/vvbeliaev.yml`

- Триггер: push в `main` по paths `apps/vvbeliaev/**`, корневые манифесты,
  сам workflow; плюс `workflow_dispatch`. Concurrency по ref, cancel-in-progress.
- Джобы `check` → `build` → `deploy`, как в traffhub `site.yml`.
- `build`: `docker/login-action` в `ghcr.io` с `GITHUB_TOKEN`
  (`permissions: packages: write`), `docker/metadata-action` теги
  `latest` + `sha,format=long`, `docker/build-push-action` с gha-кэшем.
- `deploy`: `curl --fail-with-body -X POST` в Coolify API. Секреты репозитория:
  `COOLIFY_URL`, `COOLIFY_TOKEN`, `COOLIFY_VVBELIAEV_APP_UUID`.
- Красный `check` — образ не собирается, Coolify не дёргается.

### 4. Coolify-приложение

- Тип Docker Image: `ghcr.io/vvbeliaev/vvbeliaev:latest`, порт `8080`,
  FQDN `https://vvbeliaev.dev`, проект `portfolio` / `production`,
  сервер `small-ubuntu-4gb-fsn1-2`. Создаётся через MCP `coolify`.
- Healthcheck — HTTP `GET /` на 8080.

### 5. Правки в репозитории

- `astro.config.mjs`: `site: "https://vvbeliaev.dev"` (была опечатка `vbeliaev`).
- Ops-скилл `.claude/skills/vvbeliaev-ops/SKILL.md` по образцу traffhub-ops:
  карта деплоя, дисциплина CI, «читать свободно / менять по явной просьбе»,
  MCP `coolify` без суффикса, туннель, симптомы. Раздел «Деплой и ops»
  в `CLAUDE.md` со ссылкой на скилл. Пишутся в конце, по факту.

## Что делает владелец руками

- Создать API-токен Coolify (UI → Keys & Tokens) и положить в GH-секрет
  `COOLIFY_TOKEN`. Остальные секреты и ресурсы создаёт агент.

## Вне скоупа v1

Превью на PR, `www`, закрытие портов 80/443 на сервере, чистка старых
`sha-*` тегов в GHCR, свой registry (появится при приватном коде или тяжёлых
образах — переезд одной строкой `IMAGE`).

## Проверка готовности

1. `gh run watch` — все три джоба зелёные.
2. `docker pull ghcr.io/vvbeliaev/vvbeliaev:latest` работает без логина.
3. `curl -sI https://vvbeliaev.dev` → 200, `server: cloudflare`;
   `/ru/` → 200; несуществующий путь → 404 с сайтовой страницей.
4. Coolify: приложение `running:healthy`.
