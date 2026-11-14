#!/bin/sh
# Démarre en root, adopte le propriétaire du dossier /data (ton compte du NAS),
# puis lance l'appli avec ses droits. Aucun UID/GID à configurer.
set -eu

DATA="${SCRIPTORIUM_DATA:-/data}"
mkdir -p "$DATA"

PUID="$(stat -c %u "$DATA")"
PGID="$(stat -c %g "$DATA")"
echo "scriptorium : exécution avec UID=$PUID GID=$PGID (propriétaire de $DATA)"

export HOME="$DATA"
cd /app
exec gosu "$PUID:$PGID" uvicorn app.main:app --app-dir /app --host 0.0.0.0 --port "${SCRIPTORIUM_PORT:-8091}" --proxy-headers --no-access-log
