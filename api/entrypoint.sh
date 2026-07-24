#!/bin/sh
# Entrypoint de la API: aplica migraciones y arranca el comando (CMD).
set -e

echo "[entrypoint] Esperando y aplicando migraciones Alembic..."
alembic upgrade head

echo "[entrypoint] Iniciando proceso: $*"
exec "$@"
