#!/usr/bin/env python3
"""
49_promote_confidence.py

Apply native target-language Wiktionary confirmations as confidence-tag
promotions in en_de.json / en_fr.json / en_it.json.

Reads reverse_validate_<lang>_confirms.json and updates the matching
entries in en_<lang>.json with an upgraded `confidence` tag. The actual
translation values are NOT touched.

Promotion rules (conservative — only adds "+native" when an independent
native-language Wiktionary entry confirms the primary translation):
    gt_only          → gt+native
    kaikki_only      → kaikki+native
    kaikki+gt        → kaikki+gt+native
    extras           → extras+native
    extras_override  → extras_override+native
    none             → native
    (anything else)  → "<orig>+native"

Usage:
    python3 49_promote_confidence.py            # all three langs
    python3 49_promote_confidence.py de         # one lang only
"""

import json
import os
import sys
from collections import Counter


def promote(orig: str) -> str:
    if not orig:
        return "native"
    if "+native" in orig:
        return orig  # idempotent
    return f"{orig}+native"


def first_translation(field) -> str:
    if isinstance(field, list):
        return (field[0] if field else "").strip().lower()
    return (field or "").strip().lower()


def run(lang: str) -> tuple[int, int]:
    en_x_path = f"en_{lang}.json"
    confirms_path = f"reverse_validate_{lang}_confirms.json"
    if not os.path.exists(confirms_path):
        print(f"  SKIP {lang}: {confirms_path} missing", file=sys.stderr)
        return (0, 0)

    en_x = json.load(open(en_x_path))
    confirms_blob = json.load(open(confirms_path))
    confirmed_keys = set()
    for bucket in ("confirms", "multi_ok"):
        for c in confirms_blob.get(bucket, []):
            confirmed_keys.add((c["en"].strip().lower(), c[lang].strip().lower()))

    promoted = 0
    before_counts = Counter()
    after_counts = Counter()

    for entry in en_x:
        before_counts[entry.get("confidence", "n/a")] += 1
        en_word = entry.get("en", "").strip().lower()
        x_word = first_translation(entry.get(lang))
        if (en_word, x_word) in confirmed_keys:
            new_conf = promote(entry.get("confidence", ""))
            if new_conf != entry.get("confidence"):
                entry["confidence"] = new_conf
                promoted += 1
        after_counts[entry.get("confidence", "n/a")] += 1

    with open(en_x_path, "w", encoding="utf-8") as f:
        json.dump(en_x, f, ensure_ascii=False, indent=2)

    print(f"\n=== {lang.upper()} ===  promoted {promoted} entries")
    print(f"  before: {dict(before_counts.most_common())}")
    print(f"  after:  {dict(after_counts.most_common())}")

    return (len(en_x), promoted)


def main():
    langs = sys.argv[1:] if len(sys.argv) > 1 else ["de", "it", "fr"]
    for L in langs:
        if L not in ("de", "fr", "it"):
            print(f"unknown lang: {L}", file=sys.stderr)
            sys.exit(1)
    total_promoted = 0
    for L in langs:
        _, p = run(L)
        total_promoted += p
    print(f"\nTotal entries promoted: {total_promoted}")


if __name__ == "__main__":
    main()
