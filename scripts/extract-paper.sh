#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s INPUT.pdf OUTPUT.txt [OCR_LANG]\n' "$0" >&2
  exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage

input_pdf="$1"
output_text="$2"
ocr_lang="${3:-eng}"

[[ -f "$input_pdf" ]] || {
  printf 'Input PDF not found: %s\n' "$input_pdf" >&2
  exit 2
}

for dependency in pdfinfo pdftotext pdftoppm tesseract; do
  command -v "$dependency" >/dev/null 2>&1 || {
    printf 'Missing dependency: %s\n' "$dependency" >&2
    exit 1
  }
done

output_dir=$(dirname "$output_text")
mkdir -p "$output_dir"

scratch_dir=$(mktemp -d "${TMPDIR:-/tmp}/llm-red-team-ocr.XXXXXX")
trap 'rm -rf "$scratch_dir"' EXIT

extracted_text="$scratch_dir/text-layer.txt"
pdftotext -layout "$input_pdf" "$extracted_text"

non_space_chars=$(tr -d '[:space:]' < "$extracted_text" | wc -c | tr -d ' ')
page_count=$(pdfinfo "$input_pdf" | awk '/^Pages:/ {print $2}')
minimum_chars=$(( page_count * 100 ))

if (( non_space_chars >= minimum_chars )); then
  cp "$extracted_text" "$output_text"
  printf 'text-layer pages=%s chars=%s output=%s\n' "$page_count" "$non_space_chars" "$output_text"
  exit 0
fi

pdftoppm -r 300 -png "$input_pdf" "$scratch_dir/page" >/dev/null 2>&1
: > "$output_text"

page_number=0
for page_image in "$scratch_dir"/page-*.png; do
  [[ -e "$page_image" ]] || {
    printf 'No rendered pages were produced\n' >&2
    exit 1
  }
  page_number=$(( page_number + 1 ))
  printf '\n\n--- Page %s ---\n\n' "$page_number" >> "$output_text"
  tesseract "$page_image" stdout -l "$ocr_lang" 2>/dev/null >> "$output_text"
done

printf 'ocr pages=%s lang=%s output=%s\n' "$page_number" "$ocr_lang" "$output_text"

