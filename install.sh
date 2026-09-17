#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="lead-radar"
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env"

log() { printf '\n\033[1;32m[Lead Radar]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[Ошибка]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  command -v sudo >/dev/null 2>&1 || fail "Запустите установщик от root."
  exec sudo -E bash "$0" "$@"
fi

[[ -f "$COMPOSE_FILE" && -f "$ROOT_DIR/backend/Dockerfile" ]] || \
  fail "Запускайте install.sh из корня склонированного репозитория."

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi
  command -v apt-get >/dev/null 2>&1 || \
    fail "Автоустановка Docker поддерживает Ubuntu/Debian. Установите Docker вручную."
  log "Устанавливаю Docker Engine и Compose plugin"
  apt-get update
  apt-get install -y ca-certificates curl gnupg openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  local distro="${ID:-ubuntu}"
  local codename="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
  if [[ "$distro" != "ubuntu" && "$distro" != "debian" ]]; then
    distro="ubuntu"
  fi
  if [[ "$distro" == "debian" ]]; then
    curl -fsSL https://download.docker.com/linux/debian/gpg \
      -o /etc/apt/keyrings/docker.asc
  fi
  [[ -n "$codename" ]] || fail "Не удалось определить версию Linux."
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' \
    "$(dpkg --print-architecture)" "$distro" "$codename" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

install_docker
command -v openssl >/dev/null 2>&1 || { apt-get update; apt-get install -y openssl; }
cd "$ROOT_DIR"

RECONFIGURE=false
[[ "${1:-}" == "--reconfigure" ]] && RECONFIGURE=true

generated_password=""
if [[ ! -f "$ENV_FILE" || "$RECONFIGURE" == true ]]; then
  default_host="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -t 0 ]]; then
    printf '\nПубличный домен или IP сервера [%s]: ' "$default_host"
    read -r public_host
  else
    public_host="${PUBLIC_HOST:-$default_host}"
  fi
  public_host="${public_host:-$default_host}"
  public_host="${public_host#http://}"
  public_host="${public_host#https://}"
  public_host="${public_host%/}"
  [[ -n "$public_host" ]] || fail "Укажите PUBLIC_HOST."

  if [[ "$public_host" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ || "$public_host" == *:* ]]; then
    site_address="http://$public_host"
    public_url="$site_address"
    secure_cookies="false"
    log "Домен не указан: будет HTTP. Для реального использования настройте домен и HTTPS."
  else
    site_address="$public_host"
    public_url="https://$public_host"
    secure_cookies="true"
    log "Убедитесь, что DNS домена $public_host указывает на этот сервер."
  fi

  admin_password="${ADMIN_PASSWORD:-}"
  if [[ -z "$admin_password" && -t 0 ]]; then
    printf 'Пароль администратора (Enter — сгенерировать): '
    read -rs admin_password
    printf '\n'
  fi
  if [[ -z "$admin_password" ]]; then
    admin_password="$(openssl rand -hex 12)"
    generated_password="$admin_password"
  fi

  postgres_password=""
  app_secret=""
  if [[ -f "$ENV_FILE" ]]; then
    postgres_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$ENV_FILE" | head -n 1)"
    app_secret="$(sed -n 's/^APP_SECRET_KEY=//p' "$ENV_FILE" | head -n 1)"
  fi
  postgres_password="${postgres_password:-$(openssl rand -hex 24)}"
  app_secret="${app_secret:-$(openssl rand -hex 32)}"

  log "Создаю production-конфигурацию"
  umask 077
  cat > "$ENV_FILE" <<EOF
POSTGRES_DB=lead_radar
POSTGRES_USER=lead_radar
POSTGRES_PASSWORD=$postgres_password
DATABASE_URL=postgresql+asyncpg://lead_radar:$postgres_password@postgres:5432/lead_radar

ENVIRONMENT=production
APP_SECRET_KEY=$app_secret
ADMIN_PASSWORD=
ADMIN_PASSWORD_HASH=bootstrap
AUTH_TOKEN_TTL_HOURS=12
SECURE_COOKIES=$secure_cookies
APP_TIMEZONE=Europe/Moscow
CORS_ORIGINS=$public_url

TELEGRAM_SESSION_DIR=/app/data/sessions
TELEGRAM_BOT_TOKEN=
TELEGRAM_NOTIFICATION_CHAT_ID=

AI_PROVIDER=mock
AI_API_KEY=
AI_MODEL=
AI_BASE_URL=https://api.openai.com/v1
AI_TIMEOUT_SECONDS=30
LEAD_SCORE_THRESHOLD=70

VITE_API_URL=
SITE_ADDRESS=$site_address
EOF
  chmod 600 "$ENV_FILE"

  log "Собираю backend и создаю Argon2-хеш пароля"
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" build backend
  export ADMIN_SETUP_PASSWORD="$admin_password"
  admin_hash="$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" run --rm --no-deps \
    -e ADMIN_SETUP_PASSWORD backend python -c \
    'import os; from argon2 import PasswordHasher; print(PasswordHasher().hash(os.environ["ADMIN_SETUP_PASSWORD"]))')"
  unset ADMIN_SETUP_PASSWORD admin_password
  sed -i "s|^ADMIN_PASSWORD_HASH=.*|ADMIN_PASSWORD_HASH='$admin_hash'|" "$ENV_FILE"
else
  log "Использую существующий .env. Для полной перенастройки: sudo bash install.sh --reconfigure"
  public_url="$(sed -n 's|^SITE_ADDRESS=||p' "$ENV_FILE")"
  if [[ "$public_url" != http* ]]; then
    public_url="https://$public_url"
  fi
fi

log "Собираю и запускаю сервисы"
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build

log "Проверяю готовность backend"
ready=false
for _ in $(seq 1 36); do
  if docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" exec -T backend \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" \
    >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 5
done
[[ "$ready" == true ]] || {
  docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=80 backend
  fail "Backend не прошёл healthcheck. Логи показаны выше."
}

printf '\n\033[1;32mУстановка завершена.\033[0m\n'
printf 'Откройте: %s\n' "$public_url"
if [[ -n "$generated_password" ]]; then
  printf '\n\033[1;33mСгенерированный пароль администратора: %s\033[0m\n' "$generated_password"
  printf 'Сохраните его сейчас: повторно он показан не будет.\n'
fi
printf '\nПолезные команды:\n'
printf '  Статус:  docker compose -p %s -f docker-compose.prod.yml ps\n' "$PROJECT_NAME"
printf '  Логи:    docker compose -p %s -f docker-compose.prod.yml logs -f backend\n' "$PROJECT_NAME"
printf '  Обновить: sudo bash update.sh\n'
printf '\nДля HTTPS откройте входящие TCP 80/443 и UDP 443.\n'
