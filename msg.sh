#!/bin/bash
msg="$*"
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$msg\"}" | jq
