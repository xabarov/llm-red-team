#!/usr/bin/env bash
set -euo pipefail

limit_bytes=32768
failed=0

for context_file in AGENTS.md .codex/project-memory.md tasks/active/README.md docs/brief.md; do
  if [[ ! -f "$context_file" ]]; then
    printf '%-32s %s\n' "$context_file" "missing"
    failed=1
    continue
  fi

  file_bytes=$(wc -c < "$context_file" | tr -d ' ')
  printf '%-32s %7s bytes\n' "$context_file" "$file_bytes"
  if (( file_bytes > limit_bytes )); then
    printf '  exceeds %s-byte context budget\n' "$limit_bytes"
    failed=1
  fi
done

exit "$failed"

