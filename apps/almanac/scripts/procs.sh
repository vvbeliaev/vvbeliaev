#!/usr/bin/env bash
# almanac на своей машине: база в Docker, сервер — процесс на хосте.
#
#   scripts/procs.sh up|down|restart|status|logs|migrate|dump
#
# Сервер опознаётся по командной строке, а не по pid-файлу: так виден и поднятый
# руками или из другой копии репозитория. Второй сервер рядом с первым — это два
# опроса одного бота Telegram и напоминания дважды, поэтому `up` не поднимает сервер,
# пока жив другой или занят порт. Проверка идёт до запуска: uvicorn запускает бота
# раньше, чем занимает порт, и проигравший успел бы опросить Telegram.
set -euo pipefail
# Журнал, .env и дампы — личное: всё, что создаёт скрипт, читает только владелец.
umask 077

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
RUN_DIR="$APP_DIR/.run"
LOG="$RUN_DIR/server.log"
PORT="${PORT:-8910}"
BACKUPS="$HOME/almanac-backups"
COMPOSE=(docker compose -f "$APP_DIR/compose.yml")
UV=(uv run --package almanac)

die() { echo "$*" >&2; exit 1; }

# Адрес, под которым сервер знает себя сам: из него строятся адреса OAuth и с ним
# сверяется Origin формы входа. Свой BASE_URL — из окружения или из .env — старше.
if [ -z "${BASE_URL:-}" ] && ! grep -qs '^BASE_URL=' .env; then
  export BASE_URL="http://127.0.0.1:$PORT"
  # Такой сервер виден только с этой машины, поэтому сайт читает без входа (только читает).
  # Выключить: LOCAL_SITE=0 в .env.
  if [ -z "${LOCAL_SITE:-}" ] && ! grep -qs '^LOCAL_SITE=' .env; then
    export LOCAL_SITE=1
  fi
fi

# .env читают сервер, локальная дверь MCP и compose. Скрипт только дописывает то, чего в нём
# нет, и ничего не меняет.
#   OWNER_TZ — пояс этой машины: без него «сегодня» и время напоминаний считались бы по UTC.
#   POSTGRES_PASSWORD, DATABASE_URL — пароль локальной базы; он нигде не печатается.
ensure_env() {
  local zone secret
  if [ ! -e .env ]; then
    zone="$(readlink /etc/localtime 2> /dev/null | sed 's|.*/zoneinfo/||' || true)"
    printf 'OWNER_TZ=%s\n' "${zone:-UTC}" > .env
    echo ".env: создан, OWNER_TZ=${zone:-UTC}"
  fi
  if ! grep -qs '^POSTGRES_PASSWORD=' .env; then
    # Последняя строка без перевода — дописанное приклеилось бы к ней.
    [ -z "$(tail -c 1 .env)" ] || echo >> .env
    secret="$(openssl rand -hex 24)"
    printf 'POSTGRES_PASSWORD=%s\n' "$secret" >> .env
    grep -qs '^DATABASE_URL=' .env \
      || printf 'DATABASE_URL=postgresql+asyncpg://almanac:%s@127.0.0.1:5434/almanac\n' "$secret" >> .env
    echo ".env: добавлен пароль локальной базы"
  fi
}

# pid самого python-процесса: обёртки caffeinate и uv выходят вслед за ним.
# ps, а не pgrep: pgrep из песочницы агента не видит чужих процессов.
# shellcheck disable=SC2009
pids() {
  ps -axo pid=,command= \
    | grep -E "bin/python[0-9.]* .*uvicorn almanac\.app:create_app" \
    | awk '{print $1}' || true
}

# Ревизия, с которой сервер поднят этим скриптом; «?» — поднят иначе.
started_rev() {
  local file="$RUN_DIR/server.up" pid rev
  [ -f "$file" ] || { echo "?"; return; }
  read -r pid rev < "$file"
  if ps -o command= -p "$pid" 2> /dev/null | grep -q "almanac\.app:create_app"; then echo "$rev"; else echo "?"; fi
}

db_up() {
  docker info > /dev/null 2>&1 || die "Docker не запущен"
  if [ -z "$("${COMPOSE[@]}" ps -q --status running db 2> /dev/null)" ]; then
    echo "база: поднимаю"
    "${COMPOSE[@]}" up -d db
  fi
  # По TCP, а не через сокет: при первом запуске образ сначала поднимает временный
  # сервер для инициализации, и тот слушает только сокет.
  local i=0
  until "${COMPOSE[@]}" exec -T db pg_isready -q -h 127.0.0.1 -U almanac -d almanac; do
    i=$((i + 1))
    [ "$i" -lt 30 ] || die "база не отвечает 30 с"
    sleep 1
  done
}

at_head() {
  case "$("${UV[@]}" alembic current 2> /dev/null || true)" in
    *"(head)"*) return 0 ;;
    *) return 1 ;;
  esac
}

# В дампе всё личное: каталог и файл — только владельцу.
dump() {
  local label="$1" file
  mkdir -p "$BACKUPS"
  chmod 700 "$BACKUPS"
  file="$BACKUPS/$label-$(date +%Y%m%d-%H%M%S).dump"
  "${COMPOSE[@]}" exec -T db pg_dump -U almanac -Fc almanac > "$file"
  [ -s "$file" ] || die "дамп пустой — дальше не иду: $file"
  echo "дамп: $file"
}

upgrade() {
  local head
  head="$("${UV[@]}" alembic heads 2> /dev/null | awk 'NR == 1 {print $1}')"
  dump "before-$head"
  "${UV[@]}" alembic upgrade head
}

start() {
  local rev
  mkdir -p "$RUN_DIR"
  rev="$(git rev-parse --short HEAD)"
  echo "--- up $(date -u +%Y-%m-%dT%H:%M:%SZ) $rev" >> "$LOG"
  # В журнал при ошибке базы попадает текст запроса: каталог и файл — только владельцу,
  # в том числе созданные раньше с правами пошире.
  chmod 700 "$RUN_DIR"
  chmod 600 "$LOG"
  # Своя сессия (setsid) и nohup: сервер не зависит ни от терминала, ни от того, кто
  # его поднял. caffeinate -i не даёт маку уснуть, пока сервер жив: спящая машина
  # напоминаний не шлёт. SIGINT и SIGQUIT — снова по умолчанию: фоновая команда
  # неинтерактивной оболочки получает их игнорируемыми, и `down` мог бы остановить
  # сервер только TERM — без закрытия соединений.
  # Один воркер: бот и цикл напоминаний живут в процессе. Без журнала доступа:
  # секрет ленты и коды OAuth лежат в адресах запросов.
  # shellcheck disable=SC2016
  PYTHONUNBUFFERED=1 nohup perl -MPOSIX -e '$SIG{INT} = $SIG{QUIT} = "DEFAULT"; POSIX::setsid(); exec @ARGV or die "exec: $!"' \
    caffeinate -i "${UV[@]}" uvicorn almanac.app:create_app --factory \
    --host 127.0.0.1 --port "$PORT" --workers 1 --no-access-log --timeout-graceful-shutdown 5 \
    >> "$LOG" 2>&1 < /dev/null &
  echo "$! $rev" > "$RUN_DIR/server.up"
  echo "сервер: поднимаю ($rev)"
}

healthy() { curl -fs --max-time 2 "http://127.0.0.1:$PORT/healthz" > /dev/null; }

port_free() { ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN > /dev/null 2>&1; }

check_started() {
  local i
  for ((i = 0; i < 30; i++)); do
    if healthy; then
      echo "сервер: http://127.0.0.1:$PORT"
      return 0
    fi
    sleep 1
  done
  echo "сервер не поднялся, хвост журнала:" >&2
  tail -n 12 "$LOG" >&2
  return 1
}

stop() {
  local running i
  running="$(pids)"
  [ -n "$running" ] || { echo "сервер: не идёт"; return 0; }
  # shellcheck disable=SC2086
  kill -INT $running 2> /dev/null || true
  for ((i = 0; i < 20; i++)); do
    [ -z "$(pids)" ] && { echo "сервер: остановлен"; return 0; }
    sleep 1
  done
  # shellcheck disable=SC2046
  kill -TERM $(pids) 2> /dev/null || true
  sleep 5
  [ -z "$(pids)" ] && { echo "сервер: остановлен (TERM)"; return 0; }
  echo "сервер: не остановился — pid $(pids | tr "\n" " ")" >&2
  return 1
}

# Сайт сервер отдаёт из web/dist. Здесь он собирается только в первый раз; после правок — make web.
site_built() {
  [ -f web/dist/index.html ] && return 0
  if command -v pnpm > /dev/null 2>&1; then
    echo "сайт: собираю"
    (cd web && pnpm install --frozen-lockfile && pnpm build) > /dev/null || echo "сайт не собрался — make web покажет почему" >&2
  else
    echo "сайт: не собран, pnpm не найден — сервер поднимется без него"
  fi
}

up() {
  local running
  running="$(pids)"
  if [ -n "$running" ]; then
    echo "сервер: уже идёт (pid $(tr "\n" " " <<< "$running"))"
    return 0
  fi
  port_free || die "порт $PORT занят другим процессом — сервер не поднимаю. Другой порт: PORT=8920 make up"
  ensure_env
  site_built
  db_up
  at_head || upgrade
  start
  check_started
}

status() {
  local running pid head rev
  running="$(pids)"
  if [ -z "$running" ]; then
    echo "сервер  стоит"
  else
    pid="$(echo "$running" | head -n 1)"
    head="$(git rev-parse --short HEAD)"
    rev="$(started_rev)"
    if [ "$rev" != "$head" ] && [ "$rev" != "?" ]; then
      if git diff --quiet "$rev" HEAD -- src migrations ../../uv.lock 2> /dev/null; then
        rev="$rev (код = HEAD)"
      else
        rev="$rev (код изменился в HEAD $head — make restart)"
      fi
    fi
    printf 'сервер  идёт  pid %-6s %11s  %s\n' "$pid" "$(ps -o etime= -p "$pid" | tr -d ' ')" "$rev"
    if healthy; then echo "        http://127.0.0.1:$PORT отвечает"; else echo "        http://127.0.0.1:$PORT не отвечает"; fi
  fi
  if docker info > /dev/null 2>&1 && [ -n "$("${COMPOSE[@]}" ps -q --status running db 2> /dev/null)" ]; then
    echo "база    идёт  ревизия: $("${UV[@]}" alembic current 2> /dev/null | tail -n 1 || true)"
  else
    echo "база    стоит"
  fi
}

case "${1:-status}" in
  up) up ;;
  down) stop ;;
  restart)
    stop || die "сервер не остановился — новый не поднимаю"
    up
    ;;
  status) status ;;
  logs)
    mkdir -p "$RUN_DIR"
    touch "$LOG"
    exec tail -n 40 -F "$LOG"
    ;;
  migrate)
    [ -z "$(pids)" ] || die "сервер идёт — сначала make down"
    ensure_env
    db_up
    if at_head; then echo "база уже на последней миграции"; else upgrade; fi
    ;;
  dump)
    ensure_env
    db_up
    dump manual
    ;;
  *) die "действие: up | down | restart | status | logs | migrate | dump" ;;
esac
