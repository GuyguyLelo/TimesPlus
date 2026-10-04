#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

import psycopg

host = os.environ.get("DB_HOST") or os.environ.get("POSTGRES_HOST") or "db"
port = os.environ.get("DB_PORT") or os.environ.get("POSTGRES_PORT") or "5432"
user = os.environ.get("DB_USER") or os.environ.get("POSTGRES_USER") or "gestion_user"
password = os.environ.get("DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD") or ""
dbname = os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB") or "gestion_heures"

for attempt in range(60):
    try:
        with psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            connect_timeout=3,
        ):
            break
    except Exception:
        time.sleep(1)
else:
    print("Base de données inaccessible.", file=sys.stderr)
    sys.exit(1)
PY

python manage.py collectstatic --noinput
exec "$@"
