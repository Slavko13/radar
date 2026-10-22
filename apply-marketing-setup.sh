#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="lead-radar"
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.prod.yml}"
BACKUP_DIR="$ROOT_DIR/backups"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/lead-radar-before-marketing-setup-$STAMP.sql.gz"

log() { printf '\n\033[1;32m[Lead Radar]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[Ошибка]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || fail "Запустите скрипт от root."
  exec sudo -E bash "$0" "$@"
fi

[[ -f "$COMPOSE_FILE" ]] || fail "Не найден compose-файл: $COMPOSE_FILE"
command -v gzip >/dev/null 2>&1 || fail "Установите gzip: apt-get install -y gzip"

cd "$ROOT_DIR"
install -d -m 0700 "$BACKUP_DIR"

log "Проверяю сервисы"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d postgres backend

log "Создаю полный резервный снимок базы"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip -9 > "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"

log "Применяю маркетинговую конфигурацию"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T backend \
  python -m app.setup_marketing

printf '\n\033[1;32mНастройка завершена.\033[0m\n'
printf 'Резервная копия: %s\n' "$BACKUP_FILE"
printf 'Telegram, AI-ключи, источники, сообщения и лиды не изменялись.\n'
