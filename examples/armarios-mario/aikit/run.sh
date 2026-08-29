#!/bin/bash

EXAMPLE_DIR="$(cd "$(dirname "$0")" && pwd)"
AIKIT_ROOT="$(cd "$EXAMPLE_DIR/../../.." && pwd)"

export PYTHONPATH="$AIKIT_ROOT:$EXAMPLE_DIR${PYTHONPATH:+:$PYTHONPATH}"
export AIKIT_CONFIG="$EXAMPLE_DIR/aikit.yaml"
export AIKIT_CATALOGO_CSV="${AIKIT_CATALOGO_CSV:-$EXAMPLE_DIR/../web/catalogo.csv}"
# Secreto de firma de sesion: en produccion debe venir del entorno, no generarse aqui.
export AIKIT_SESSION_SECRET="${AIKIT_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

cd "$EXAMPLE_DIR"

exec uvicorn core.main:app \
	--host 0.0.0.0 \
	--port 8000 \
	--reload \
	--reload-dir "$AIKIT_ROOT" \
	--reload-dir "$EXAMPLE_DIR" \
	--reload-include "*.py" \
	--reload-include "*.yaml"
