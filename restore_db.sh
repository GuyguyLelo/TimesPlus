#!/usr/bin/env bash
# Restaure un fichier produit par backup_db.sh. Usage : ./restore_db.sh backups/fichier.sql
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage : $0 backups/gestion_heures_YYYYMMDD_HHMMSS.sql" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
FILE="$1"

if [ ! -f "$FILE" ]; then
  echo "Fichier introuvable : $FILE" >&2
  exit 1
fi

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

USER_NAME="${POSTGRES_USER:-${DB_USER:-gestion_user}}"
DB_NAME="${POSTGRES_DB:-${DB_NAME:-gestion_heures}}"

docker compose exec -T db psql -U "$USER_NAME" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T db psql -U "$USER_NAME" -d "$DB_NAME" < "$FILE"
echo "Restauration terminée depuis $FILE"
