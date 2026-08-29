#!/bin/bash

# Arranca el backend de aikit con la configuracion y los servicios de este ejemplo.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
AIKIT_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"

export PYTHONPATH="$AIKIT_ROOT:$DEMO_DIR${PYTHONPATH:+:$PYTHONPATH}"
export AIKIT_CONFIG="$DEMO_DIR/aikit.yaml"
export AIKIT_SESSION_SECRET="${AIKIT_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

cd "$DEMO_DIR"

exec uvicorn aikit.core.main:app \
	--host 0.0.0.0 \
	--port 8000 \
	--reload \
	--reload-dir "$AIKIT_ROOT" \
	--reload-dir "$DEMO_DIR" \
	--reload-include "*.py" \
	--reload-include "*.yaml"
