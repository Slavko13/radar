#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="lead-radar"
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
SESSION_VOLUME="${PROJECT_NAME}_telegram_sessions"
DATABASE_VOLUME="${PROJECT_NAME}_postgres_data"
ARCHIVE="${1:-}"

log() { printf '\n\033[1;32m[Lead Radar]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[Ошибка]\033[0m %s\n' "$*" >&2; exit 1; }
read_env() { sed -n "s/^$1=//p" "$2" | tail -n 1; }
set_env() {
  local key="$1" value="$2" file="$3" temporary
  temporary="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    index($0, key "=") == 1 { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$file" > "$temporary"
  cat "$temporary" > "$file"
  rm -f -- "$temporary"
}

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || fail "Запустите скрипт от root."
  exec sudo -E bash "$0" "$@"
fi

[[ -n "$ARCHIVE" ]] || fail "Укажите архив: sudo bash restore.sh /root/lead-radar-full.tar.gz"
ARCHIVE="$(realpath "$ARCHIVE")"
[[ -f "$ARCHIVE" ]] || fail "Архив не найден: $ARCHIVE"
[[ -f "$COMPOSE_FILE" ]] || fail "Сначала клонируйте Lead Radar и выполните install.sh."
command -v docker >/dev/null 2>&1 || fail "Docker не установлен."
command -v gzip >/dev/null 2>&1 || fail "Установите gzip: apt-get install -y gzip"

unexpected="$(tar -tzf "$ARCHIVE" | grep -Ev '^(\./)?$|^(\./)?(\.env|database\.sql\.gz|telegram_sessions\.tar\.gz)/?$' || true)"
[[ -z "$unexpected" ]] || fail "Архив содержит неожиданные файлы и не будет восстановлен."

if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  [[ -t 0 ]] || fail "Для запуска без терминала добавьте RESTORE_CONFIRM=YES."
  printf '\nЭто полностью заменит базу и Telegram-сессию на этом сервере.\n'
  printf 'Для продолжения напишите ВОССТАНОВИТЬ: '
  read -r confirmation
  [[ "$confirmation" == "ВОССТАНОВИТЬ" ]] || fail "Восстановление отменено."
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf -- "$WORK_DIR"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK_DIR"
[[ -s "$WORK_DIR/.env" && -s "$WORK_DIR/database.sql.gz" && \
   -s "$WORK_DIR/telegram_sessions.tar.gz" ]] || fail "Бэкап неполный или повреждён."

current_site=""
current_cors=""
current_secure=""
if [[ -f "$ROOT_DIR/.env" ]]; then
  current_site="$(read_env SITE_ADDRESS "$ROOT_DIR/.env")"
  current_cors="$(read_env CORS_ORIGINS "$ROOT_DIR/.env")"
  current_secure="$(read_env SECURE_COOKIES "$ROOT_DIR/.env")"
  install -m 0600 "$ROOT_DIR/.env" "$ROOT_DIR/.env.before-restore"
fi

log "Останавливаю приложение и подготавливаю чистые volumes"
cd "$ROOT_DIR"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" down
install -m 0600 "$WORK_DIR/.env" "$ROOT_DIR/.env"
[[ -n "$current_site" ]] && set_env SITE_ADDRESS "$current_site" "$ROOT_DIR/.env"
[[ -n "$current_cors" ]] && set_env CORS_ORIGINS "$current_cors" "$ROOT_DIR/.env"
[[ -n "$current_secure" ]] && set_env SECURE_COOKIES "$current_secure" "$ROOT_DIR/.env"

for volume in "$DATABASE_VOLUME" "$SESSION_VOLUME"; do
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    docker volume rm "$volume" >/dev/null || fail "Не удалось удалить volume $volume"
  fi
done
docker volume create "$SESSION_VOLUME" >/dev/null
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d postgres

ready=false
for _ in $(seq 1 30); do
  if docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
[[ "$ready" == true ]] || fail "PostgreSQL не запустился. Проверьте docker compose logs postgres."

log "Восстанавливаю базу и подключения"
gzip -dc "$WORK_DIR/database.sql.gz" | \
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker run --rm \
  -v "$SESSION_VOLUME:/data" \
  -v "$WORK_DIR:/backup:ro" \
  postgres:16-alpine \
  sh -c 'tar xzf /backup/telegram_sessions.tar.gz -C /data'

log "Собираю и запускаю Lead Radar"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps

log "Восстановление завершено"
printf 'Адрес нового сервера сохранён из его предыдущего .env.\n'
printf 'Резервная копия предыдущей конфигурации: %s/.env.before-restore\n' "$ROOT_DIR"
