#!/usr/bin/env python3
"""
51_apply_disagreement_fixes.py

Apply manually-curated primary-translation fixes from disagreement_fixes.json
to en_de.json / en_fr.json / en_it.json.

For each fix:
  - Find the entry by `en` (case-insensitive) AND verify current primary
    matches `old` (sanity check — refuse to swap if file has changed)
  - Replace primary translation with `new`
  - Bump confidence to "manual_review_native" so the override is auditable

Refuses any fix whose 'old' value doesn't match — protects against silent
no-ops if upstream data shifted.
"""

import json
import sys
from collections import Counter


def first_translation(field) -> str:
    if isinstance(field, list):
        return (field[0] if field else "").strip().lower()
    return (field or "").strip().lower()


def apply_lang(lang: str, fixes: list[dict]) -> int:
    en_x_path = f"en_{lang}.json"
    en_x = json.load(open(en_x_path))

    # Build index: (en lowercase) → list of entry refs
    by_en = {}
    for entry in en_x:
        by_en.setdefault(entry.get("en", "").strip().lower(), []).append(entry)

    applied = 0
    skipped = []

    for fix in fixes:
        en_key = fix["en"].strip().lower()
        old = fix["old"].strip().lower()
        new = fix["new"].strip()
        reason = fix["reason"]
        candidates = by_en.get(en_key, [])
        # Find the entry whose current primary matches `old`
        matched = None
        for entry in candidates:
            if first_translation(entry.get(lang)) == old:
                matched = entry
                break
        if not matched:
            skipped.append(f"{en_key}: no entry with primary={old!r} (have {[first_translation(c.get(lang)) for c in candidates]})")
            continue
        field = matched.get(lang)
        if isinstance(field, list):
            # Replace the first element; keep rest as alternatives
            matched[lang] = [new] + [a for a in field[1:] if a != new]
        else:
            matched[lang] = new
        matched["confidence"] = "manual_review_native"
        matched["fix_reason"] = reason
        applied += 1

    with open(en_x_path, "w", encoding="utf-8") as f:
        json.dump(en_x, f, ensure_ascii=False, indent=2)

    print(f"\n=== {lang.upper()} === applied {applied}/{len(fixes)} fixes")
    if skipped:
        print("  skipped:")
        for s in skipped:
            print(f"    - {s}")
    return applied


def main():
    fixes = json.load(open("disagreement_fixes.json"))
    total = 0
    for lang in ("de", "it", "fr"):
        if lang in fixes:
            total += apply_lang(lang, fixes[lang])
    print(f"\nTotal applied: {total}")


if __name__ == "__main__":
    main()
