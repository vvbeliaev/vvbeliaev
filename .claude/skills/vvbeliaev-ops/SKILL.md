---
name: vvbeliaev-ops
description: Use when working with vvbeliaev deploy or production — красный CI, деплой не доехал, vvbeliaev.dev лежит или отдаёт ошибку, нужны логи приложения, состояние сервера small-ubuntu, Coolify, GHCR, Cloudflare Tunnel / DNS vvbeliaev.dev, нужно добавить новое приложение монорепы в деплой.
---

# vvbeliaev ops: деплой, CI, прод

## Карта деплоя

Push в `main` → GitHub Actions собирает образ → GHCR (`ghcr.io/vvbeliaev/<app>`,
пакет публичный: репо публичное, лимитов нет) → Coolify тянет готовый образ.
**На сервере не билдим никогда** — сервер только тянет. Приложения в Coolify —
типа Docker Image.

| Приложение | Workflow | Сервер | Домен | Coolify |
|---|---|---|---|---|
| vvbeliaev (`apps/vvbeliaev`, Astro static + Caddy :8080) | `.github/workflows/vvbeliaev.yml` | small-ubuntu-4gb-fsn1-2 | https://vvbeliaev.dev | проект `portfolio` / `production` |

Внутри workflow: `check` (astro check + build) → `build` (buildx → GHCR,
теги `latest` + `sha-<full>`) → `deploy` (`POST /api/v1/deploy` в Coolify).
Красный `check` — образ не собирается, Coolify не дёргается, прод остаётся на
старой версии. На PR деплоя нет.

Секреты репозитория (`gh secret list -R vvbeliaev/vvbeliaev`): `COOLIFY_URL`,
`COOLIFY_TOKEN`, `COOLIFY_VVBELIAEV_APP_UUID` — у каждого приложения монорепы
свой UUID-секрет.

## Сеть: Cloudflare Tunnel

Публичных портов у сайта нет. Трафик: Cloudflare edge (TLS, proxied CNAME
`vvbeliaev.dev` → `<tunnel>.cfargotunnel.com`) → туннель `vvbeliaev-01` →
`cloudflared` (Coolify-сервис `cloudflared-vvbeliaev-01`, проект `net`,
`network_mode: host` на том же сервере) → `https://localhost:443` (Traefik
`coolify-proxy`, `noTLSVerify`) → контейнер приложения. Зона: SSL `Full`,
Always Use HTTPS. Traefik не может получить Let's Encrypt (порт 80 снаружи не
нужен) и отдаёт self-signed внутрь туннеля — это норма, в логах Caddy видны
`acme-challenge` от LE, игнорируй.

Cloudflare-аккаунт `vvbeliaev` (MCP `cloudflare-api`): туннель и DNS правятся
через API, конфиг туннеля — remotely-managed (`cfd_tunnel/<id>/configurations`).

## Дисциплина CI

1. Перед push — `pnpm --filter vvbeliaev check && pnpm --filter vvbeliaev build`
   локально; образ можно прогнать `docker build -f apps/vvbeliaev/Dockerfile .`
   из корня.
2. После push — `gh run watch --exit-status`, дождись зелёного. Ушёл, не
   дождавшись — считай, что не пушил.
3. Красный CI — `gh run view <id> --log-failed`, чини сразу.

Ловушка монорепы: peer-зависимости (vite и т. п.) pnpm подтягивает на самую
свежую версию по всему воркспейсу. Если у соседнего приложения мажор новее —
пиновать нужную версию в devDependencies своего приложения (см. `vite@^7` в
`apps/vvbeliaev/package.json`).

## Диагностика прода

Прод один, стейджа нет. **Читать — свободно. Менять — только по явной просьбе
владельца** (vvbeliaev), с подтверждением, что задет нужный ресурс. «Менять» —
любые мутации любым каналом: deploy/restart/stop/env/удаление в Coolify, правки
туннеля и DNS в Cloudflare, запуск и перезапуск деплой-workflow (`gh workflow
run`, `gh run rerun`) — это тот же деплой. Откат — тоже мутация (деплой
предыдущего `sha-*` тега), сам не делаешь.

**Coolify** — `https://coolify.vvbeliaev.dev` (control plane на mgmt-01; до
2026-08-16 назывался `coolify.cogisoft.dev` — старое имя отдаёт 503, ищи его в
секретах при непонятных отказах деплоя), MCP-сервер **`coolify`** (без
суффикса — это личная команда). `coolify-th` и `coolify-gleb` — чужие команды на
том же инстансе, туда не ходим. Читающие вызовы: `diagnose_app` (статус + логи +
деплои одним вызовом), `logs`, `list_deployments`, `get_service` (для
cloudflared), `server_resources`, `get_infrastructure_overview`. UUID не
хардкодим — берём через `projects` / `list_applications` по месту.

**Сервер** `small-ubuntu-4gb-fsn1-2`: Hetzner fsn1, 2 vCPU / 4 ГБ, Ubuntu 24.04,
tailnet `100.64.0.1`, SSH `root@100.64.0.1` из tailnet. Живёт: vvbeliaev,
cloudflared-vvbeliaev-01, calisthenics (чужое для этой репы — не трогать).
Дежурные команды: `docker ps --format 'table {{.Names}}\t{{.Status}}'`,
`docker logs --tail 100 <container>`, `free -m`, `df -h`. Имена контейнеров
Coolify содержат uuid приложения.

Частые симптомы:

| Симптом | Значит | Первый шаг |
|---|---|---|
| Cloudflare 530 / 1033 | Туннель без коннектов: cloudflared упал или токен протух | Cloudflare API `cfd_tunnel/<id>` → `status`, `connections`; Coolify `get_service` cloudflared |
| Cloudflare 502 / 521 | Туннель жив, Traefik не ответил на :443 | `server_resources`, `docker ps | grep coolify-proxy` |
| «no available server» / 404 от Traefik | Роут домена не совпал с приложением | FQDN приложения в Coolify = `https://vvbeliaev.dev`; `diagnose_app` |
| Деплой `finished`, сайт старый | Coolify стянул старый `latest` (кэш) или пакет GHCR стал приватным | Проверить `docker pull ghcr.io/vvbeliaev/vvbeliaev:latest` без логина; redeploy с `force=true` |
| `deploy` в CI → 401 | `COOLIFY_TOKEN` пуст/протух | Новый токен в Coolify (Keys & Tokens), `gh secret set COOLIFY_TOKEN` |
| `deploy` в CI → 503 `no available server` | Секрет `COOLIFY_URL` указывает на старое имя control plane (Traefik роут есть, бэкенда нет) | `curl -sI https://coolify.vvbeliaev.dev/api/health`, затем `gh secret set COOLIFY_URL`. Сайт при этом жив — контейнер работает без Coolify |

## Добавить приложение монорепы в деплой

1. `apps/<app>/Dockerfile` рядом с кодом, контекст сборки — корень монорепы
   (манифесты отдельным слоем, `pnpm --filter <app> build`). Статику раздаёт
   Caddy на 8080 (см. `apps/vvbeliaev/Caddyfile`).
2. `.github/workflows/<app>.yml` — копия `vvbeliaev.yml` с заменой имени и
   paths; секрет `COOLIFY_<APP>_APP_UUID`.
3. Coolify: приложение Docker Image (`ghcr.io/vvbeliaev/<app>:latest`, порт,
   FQDN) в проекте `portfolio` через MCP `application create_dockerimage`.
4. Cloudflare: hostname в ingress туннеля `vvbeliaev-01` + proxied CNAME на
   `<tunnel>.cfargotunnel.com` (тот же cloudflared обслуживает все хосты).
5. Спека-первоисточник: `docs/superpowers/specs/2026-08-15-vvbeliaev-deploy-design.md`.
