#!/usr/bin/env bash
# Sauvegarde PostgreSQL (docker compose). Usage : ./backup_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p backups

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="backups/gestion_heures_${STAMP}.sql"
USER_NAME="${POSTGRES_USER:-${DB_USER:-gestion_user}}"
DB_NAME="${POSTGRES_DB:-${DB_NAME:-gestion_heures}}"

docker compose exec -T db pg_dump -U "$USER_NAME" "$DB_NAME" > "$OUT"
echo "Sauvegarde écrite : $OUT"
