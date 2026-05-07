#!/bin/bash
# Download per-language kaikki.org Wiktionary dumps.
# Includes Finnish (3.7 GB) — even though we have API data, kaikki.org
# is more comprehensive and useful for cross-validation.

set -e
cd "$(dirname "$0")"

declare -a LANGS=(
  "Swedish:333"
  "French:492"
  "Italian:681"
  "German:955"
  "Finnish:3698"
)

for entry in "${LANGS[@]}"; do
  lang="${entry%:*}"
  size_mb="${entry#*:}"
  lower=$(echo "$lang" | tr '[:upper:]' '[:lower:]')
  out="kaikki_${lower}.jsonl"
  url="https://kaikki.org/dictionary/${lang}/kaikki.org-dictionary-${lang}.jsonl"
  echo ""
  echo "=== ${lang} (~${size_mb} MB) ==="
  if [ -f "$out" ]; then
    cur=$(stat -f%z "$out" 2>/dev/null || stat -c%s "$out")
    cur_mb=$((cur / 1024 / 1024))
    echo "  Already have $cur_mb MB at $out — skipping"
    continue
  fi
  curl -sL -A "Mozilla/5.0" --progress-bar -o "$out" "$url"
  ls -lh "$out"
done
echo ""
echo "All downloads complete."
