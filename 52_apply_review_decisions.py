#!/usr/bin/env python3
"""
52_apply_review_decisions.py

Apply the second-pass review decisions produced by parallel language agents
(review_decisions_<lang>.json) to en_<lang>.json:

  - "fixes": swap primary translation; set confidence="manual_review_native";
    add fix_reason field. Sanity-check that current primary == old.
  - "removals": delete the entry from en_<lang>.json entirely.

Refuses any operation whose `old` value doesn't match — protects against
silent no-ops.
"""

import json


def first_translation(field) -> str:
    if isinstance(field, list):
        return (field[0] if field else "").strip().lower()
    return (field or "").strip().lower()


def apply_lang(lang: str) -> tuple[int, int, list[str]]:
    en_x_path = f"en_{lang}.json"
    decisions_path = f"review_decisions_{lang}.json"
    en_x = json.load(open(en_x_path))
    decisions = json.load(open(decisions_path))

    by_en = {}
    for entry in en_x:
        by_en.setdefault(entry.get("en", "").strip().lower(), []).append(entry)

    skipped = []
    fixes_applied = 0

    for fix in decisions.get("fixes", []):
        en_key = fix["en"].strip().lower()
        old = fix["old"].strip().lower()
        new = fix["new"].strip()
        reason = fix["reason"]
        candidates = by_en.get(en_key, [])
        matched = None
        for entry in candidates:
            if first_translation(entry.get(lang)) == old:
                matched = entry
                break
        if not matched:
            skipped.append(f"FIX {en_key}: no entry with primary={old!r}")
            continue
        field = matched.get(lang)
        if isinstance(field, list):
            matched[lang] = [new] + [a for a in field[1:] if a != new]
        else:
            matched[lang] = new
        matched["confidence"] = "manual_review_native"
        matched["fix_reason"] = reason
        fixes_applied += 1

    # Removals: delete entries from list. Build a removal-key set, filter list.
    removal_keys = set()
    for r in decisions.get("removals", []):
        removal_keys.add((r["en"].strip().lower(), r["old"].strip().lower()))

    new_en_x = []
    removals_applied = 0
    for entry in en_x:
        en_key = entry.get("en", "").strip().lower()
        primary = first_translation(entry.get(lang))
        if (en_key, primary) in removal_keys:
            removals_applied += 1
            continue
        new_en_x.append(entry)

    expected_removals = len(decisions.get("removals", []))
    if removals_applied != expected_removals:
        for r in decisions.get("removals", []):
            key = (r["en"].strip().lower(), r["old"].strip().lower())
            if not any(
                e.get("en", "").strip().lower() == key[0]
                and first_translation(e.get(lang)) == key[1]
                for e in en_x
            ):
                skipped.append(f"REMOVE {r['en']}: not found with primary={r['old']!r}")

    with open(en_x_path, "w", encoding="utf-8") as f:
        json.dump(new_en_x, f, ensure_ascii=False, indent=2)

    print(f"\n=== {lang.upper()} === fixes_applied={fixes_applied}/{len(decisions.get('fixes', []))}  "
          f"removals_applied={removals_applied}/{expected_removals}  "
          f"new_total={len(new_en_x)}")
    if skipped:
        for s in skipped:
            print(f"    SKIPPED: {s}")
    return fixes_applied, removals_applied, skipped


def main():
    total_fixes = 0
    total_removals = 0
    for lang in ("de", "it", "fr"):
        f, r, _ = apply_lang(lang)
        total_fixes += f
        total_removals += r
    print(f"\nTotal: {total_fixes} fixes, {total_removals} removals")


if __name__ == "__main__":
    main()
