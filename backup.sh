#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="lead-radar"
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
BACKUP_ROOT="$ROOT_DIR/backups"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="$BACKUP_ROOT/lead-radar-full-$STAMP.tar.gz"
LATEST="$BACKUP_ROOT/lead-radar-latest.tar.gz"
SESSION_VOLUME="${PROJECT_NAME}_telegram_sessions"

log() { printf '\n\033[1;32m[Lead Radar]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[Ошибка]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || fail "Запустите скрипт от root."
  exec sudo -E bash "$0" "$@"
fi

[[ -f "$COMPOSE_FILE" && -f "$ROOT_DIR/.env" ]] || \
  fail "Не найдены docker-compose.prod.yml или .env. Запускайте скрипт из установленного Lead Radar."
command -v docker >/dev/null 2>&1 || fail "Docker не установлен."
command -v gzip >/dev/null 2>&1 || fail "Установите gzip: apt-get install -y gzip"

install -d -m 0700 "$BACKUP_ROOT"
WORK_DIR="$(mktemp -d "$BACKUP_ROOT/.backup-$STAMP-XXXXXX")"
backend_was_running=false

finish() {
  rm -rf -- "$WORK_DIR"
  if [[ "$backend_was_running" == true ]]; then
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" start backend >/dev/null 2>&1 || true
  fi
}
trap finish EXIT

cd "$ROOT_DIR"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d postgres >/dev/null
if [[ -n "$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps -q --status running backend)" ]]; then
  backend_was_running=true
  log "На время снимка приостанавливаю backend"
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" stop backend >/dev/null
fi

log "Сохраняю базу, ключ шифрования и Telegram-сессию"
install -m 0600 "$ROOT_DIR/.env" "$WORK_DIR/.env"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > "$WORK_DIR/database.sql.gz"

docker volume inspect "$SESSION_VOLUME" >/dev/null 2>&1 || \
  fail "Не найден Docker volume $SESSION_VOLUME"
docker run --rm \
  -v "$SESSION_VOLUME:/data:ro" \
  -v "$WORK_DIR:/backup" \
  postgres:16-alpine \
  sh -c 'tar czf /backup/telegram_sessions.tar.gz -C /data .'

tar -czf "$ARCHIVE" -C "$WORK_DIR" .
chmod 600 "$ARCHIVE"
ln -sfn "$(basename "$ARCHIVE")" "$LATEST"

if [[ "$backend_was_running" == true ]]; then
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" start backend >/dev/null
  backend_was_running=false
fi

log "Бэкап готов"
printf 'Файл: %s\n' "$ARCHIVE"
printf 'Скачать: scp root@IP_СЕРВЕРА:%s .\n' "$LATEST"
printf '\nАрхив содержит секреты. Храните его как пароль.\n'
