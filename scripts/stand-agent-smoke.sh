#!/usr/bin/env bash
set -euo pipefail

container_name="agent-memory-stand-agent-api-1"
smoke_key="sk-genai-local-smoke-test"
response_file=$(mktemp "${TMPDIR:-/tmp}/agent-memory-smoke.XXXXXX")
trap 'rm -f "$response_file"' EXIT

docker exec "$container_name" python -c \
  "from app.apikeys import hash_key; from app.memory.mongo import MongoMemoryStore; from app.memory.models import ApiKey; raw='$smoke_key'; record=ApiKey(key_hash=hash_key(raw), key_prefix='sk-genai-local', user_id='1001', label='local-smoke'); MongoMemoryStore().api_keys.col.update_one({'key_hash': record.key_hash}, {'\u0024set': record.model_dump(mode='json')}, upsert=True)"

curl --fail --silent --show-error --max-time 180 \
  http://localhost:8600/v1/chat/completions \
  -H "Authorization: Bearer $smoke_key" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Ответь одним словом: готов"}],"session_id":"smoke-agent","auth_mode":"vulnerable"}' \
  -o "$response_file"

python3 - "$response_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    payload = json.load(stream)

content = payload["choices"][0]["message"]["content"].strip()
if not content:
    raise SystemExit("Agent returned empty content")
print("Agent smoke test passed.")
PY

