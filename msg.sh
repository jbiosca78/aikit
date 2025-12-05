#!/bin/bash
msg="$*"

[[ "$msg" ]] || msg="¿que tengo en el trastero?"

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$msg\"}" | jq
