#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

if [[ "${1:-}" == "--pull" ]]; then
  git pull --ff-only
fi

docker compose -p lead-radar -f docker-compose.prod.yml up -d --build
docker compose -p lead-radar -f docker-compose.prod.yml ps
