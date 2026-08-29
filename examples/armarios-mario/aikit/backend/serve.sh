#!/bin/bash

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
AIKIT_ROOT="$(cd "$BACKEND_DIR/../../../.." && pwd)"

export PYTHONPATH="$AIKIT_ROOT:$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"
export AIKIT_CONFIG="$BACKEND_DIR/aikit.yaml"
export AIKIT_CATALOGO_CSV="${AIKIT_CATALOGO_CSV:-$BACKEND_DIR/../web/catalogo.csv}"
# Secreto de firma de sesion: en produccion debe venir del entorno, no generarse aqui.
export AIKIT_SESSION_SECRET="${AIKIT_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

cd "$BACKEND_DIR"

exec uvicorn aikit.core.main:app \
	--host 0.0.0.0 \
	--port 8000 \
	--reload \
	--reload-dir "$AIKIT_ROOT" \
	--reload-dir "$BACKEND_DIR" \
	--reload-include "*.py" \
	--reload-include "*.yaml"
