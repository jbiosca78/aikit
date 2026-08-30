#!/bin/bash

# Arranca el backend del asistente para administradores de sistemas.
set -euo pipefail

EJEMPLO_DIR="$(cd "$(dirname "$0")" && pwd)"
AIKIT_ROOT="$(cd "$EJEMPLO_DIR/../.." && pwd)"

export PYTHONPATH="$AIKIT_ROOT:$EJEMPLO_DIR${PYTHONPATH:+:$PYTHONPATH}"
export AIKIT_CONFIG="$EJEMPLO_DIR/aikit.yaml"
export AIKIT_SESSION_SECRET="${AIKIT_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

# Directorios que el asistente podra consultar. Cualquier ruta fuera de estos se rechaza.
export AIKIT_RUTAS_PERMITIDAS="${AIKIT_RUTAS_PERMITIDAS:-/var/log:/etc}"

cd "$EJEMPLO_DIR"

exec uvicorn aikit.core.main:app \
	--host 127.0.0.1 \
	--port 8000 \
	--reload \
	--reload-dir "$AIKIT_ROOT" \
	--reload-dir "$EJEMPLO_DIR" \
	--reload-include "*.py" \
	--reload-include "*.yaml"
