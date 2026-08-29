#!/bin/bash

# Arranca la variante implementada con LangChain.
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"

export AIKIT_CATALOGO_CSV="${AIKIT_CATALOGO_CSV:-$BACKEND_DIR/../web/catalogo.csv}"
export LC_SESSION_SECRET="${LC_SESSION_SECRET:-$(head -c 32 /dev/urandom | base64)}"

cd "$BACKEND_DIR"

exec uvicorn app:app --host 0.0.0.0 --port 8002 --reload
