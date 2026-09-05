#!/usr/bin/env bash
set -euo pipefail

failed=0

check() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '%-16s %s\n' "$command_name" "ok"
  else
    printf '%-16s %s\n' "$command_name" "missing"
    failed=1
  fi
}

check git
check docker
check uv
check python3
check pdftotext
check pdftoppm

if command -v tesseract >/dev/null 2>&1; then
  printf '%-16s %s\n' "tesseract" "ok (optional until scanned PDFs are found)"
else
  printf '%-16s %s\n' "tesseract" "missing (needed only for scanned PDFs)"
fi

exit "$failed"

