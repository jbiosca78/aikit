#!/bin/bash

# Arranca la implementacion de referencia sin framework.
set -euo pipefail

BASELINE_DIR="$(cd "$(dirname "$0")" && pwd)"

export AIKIT_CATALOGO_CSV="${AIKIT_CATALOGO_CSV:-$BASELINE_DIR/../web/catalogo.csv}"
export BASELINE_SESSION_SECRET="${BASELINE_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

cd "$BASELINE_DIR"

exec uvicorn app:app --host 0.0.0.0 --port 8001 --reload
