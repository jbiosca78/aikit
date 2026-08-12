#!/bin/bash

# Script para iniciar el servidor FastAPI con autoreload también para YAML.
cd "$(dirname "$0")"
uvicorn core.main:app \
	--host 0.0.0.0 \
	--port 8000 \
	--reload \
	--reload-include "*.py" \
	--reload-include "*.yaml"
