#!/usr/bin/env python3
"""
48_reverse_validate.py

Reverse cross-validate en_X.json against native target-language Wiktionary.

For each (en, X) pair in en_X.json:
  - CONFIRMED   : native_X[X.lower()] contains 'en' in its en_words list
  - DISAGREE    : native_X[X.lower()] exists but lists DIFFERENT EN words
  - UNKNOWN     : X not in native_X (no signal)
  - MULTI_OK    : 'en' is among multiple en_words (still a confirmation)

Output:
  - reverse_validate_<lang>_summary.txt   (counts + breakdown)
  - reverse_validate_<lang>_disagreements.json  (DISAGREE cases for review)
  - reverse_validate_<lang>_confirms.json       (CONFIRMED + MULTI_OK)

Usage:
    python3 48_reverse_validate.py de
    python3 48_reverse_validate.py fr
    python3 48_reverse_validate.py it
"""

import json
import os
import re
import sys
import unicodedata
from collections import Counter

NATIVE_DIR = "/Users/ttt/Documents/AI_Agent_Claude/projects/sanakirja/native_wikt"


SENSE_BRACKET_RE = re.compile(r"\s*[;,]?\s*\[\d+\].*$|\s*;.*$")


def fold(s: str) -> str:
    """Lower + strip diacritics for matching (some Wiktionary entries lack accents)."""
    s = (s or "").lower().strip()
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_en(s: str) -> str:
    """Normalize English headword/translation for matching:
    - lowercase
    - strip leading 'to ' (verb infinitive marker on our side)
    - drop kaikki sense markers like '; [1] arrive'
    - strip diacritics
    """
    s = (s or "").lower().strip()
    s = SENSE_BRACKET_RE.sub("", s).strip()
    if s.startswith("to "):
        s = s[3:].strip()
    return fold(s)


def main(lang: str):
    en_x_path = f"en_{lang}.json"
    native_path = f"{NATIVE_DIR}/native_{lang}_en.json"

    if not os.path.exists(en_x_path):
        print(f"ERROR: {en_x_path} missing", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(native_path):
        print(f"ERROR: {native_path} missing — run 47_parse_native_wikt.py {lang} first", file=sys.stderr)
        sys.exit(1)

    print(f"Loading en_{lang}.json…")
    en_x = json.load(open(en_x_path))
    print(f"  {len(en_x):,} entries")

    print(f"Loading native_{lang}_en.json…")
    native = json.load(open(native_path))
    print(f"  {len(native):,} {lang.upper()} lemmas with EN translations")

    # Build folded → original index for accent-tolerant lookups
    folded_to_orig = {}
    for k, v in native.items():
        folded_to_orig.setdefault(fold(k), []).append((k, v))

    confirms = []
    multi_ok = []
    disagrees = []
    unknowns = []
    confidence_breakdown = Counter()

    for entry in en_x:
        en_word = entry.get("en", "").strip().lower()
        x_field = entry.get(lang)
        # Field may be a string (single translation) or list (alternatives) — validate primary
        if isinstance(x_field, list):
            x_word = (x_field[0] if x_field else "").strip().lower()
        else:
            x_word = (x_field or "").strip().lower()
        conf = entry.get("confidence", "n/a")
        if not en_word or not x_word:
            continue

        # Direct lookup (case-folded)
        candidates = native.get(x_word) or native.get(x_word.replace(" ", ""))
        # Try accent-folded fallback
        if not candidates:
            for orig, v in folded_to_orig.get(fold(x_word), []):
                candidates = v
                break

        if not candidates:
            unknowns.append({"en": en_word, lang: x_word, "confidence": conf})
            confidence_breakdown[(conf, "UNKNOWN")] += 1
            continue

        en_list = [w.lower() for w in candidates.get("en_words", [])]
        en_list_norm = [normalize_en(w) for w in en_list]
        target_norm = normalize_en(en_word)

        if target_norm in en_list_norm:
            verdict = "CONFIRMED" if len(en_list) == 1 else "MULTI_OK"
            (confirms if verdict == "CONFIRMED" else multi_ok).append({
                "en": en_word, lang: x_word, "confidence": conf,
                "native_en_words": en_list[:5],
            })
            confidence_breakdown[(conf, verdict)] += 1
        else:
            disagrees.append({
                "en": en_word, lang: x_word, "confidence": conf,
                "native_en_words": en_list[:5],
            })
            confidence_breakdown[(conf, "DISAGREE")] += 1

    total = len(en_x)
    print(f"\n=== Reverse validation results for EN→{lang.upper()} ===")
    print(f"  CONFIRMED  (sole match)   : {len(confirms):>5} ({100*len(confirms)/total:.1f}%)")
    print(f"  MULTI_OK   (one-of-many)  : {len(multi_ok):>5} ({100*len(multi_ok)/total:.1f}%)")
    print(f"  DISAGREE   (other EN)     : {len(disagrees):>5} ({100*len(disagrees)/total:.1f}%)")
    print(f"  UNKNOWN    (lemma absent) : {len(unknowns):>5} ({100*len(unknowns)/total:.1f}%)")
    print(f"  TOTAL                     : {total:>5}")

    print(f"\nBy original confidence:")
    by_conf = {}
    for (conf, verdict), n in confidence_breakdown.items():
        by_conf.setdefault(conf, {})[verdict] = n
    for conf in sorted(by_conf, key=lambda c: -sum(by_conf[c].values())):
        d = by_conf[conf]
        total_c = sum(d.values())
        line = f"  {conf:<24} ({total_c:>5}): "
        line += "  ".join(f"{v}={d.get(v,0)}" for v in ("CONFIRMED", "MULTI_OK", "DISAGREE", "UNKNOWN"))
        print(line)

    # Write artifacts
    summary_path = f"reverse_validate_{lang}_summary.txt"
    disagree_path = f"reverse_validate_{lang}_disagreements.json"
    confirms_path = f"reverse_validate_{lang}_confirms.json"

    with open(disagree_path, "w", encoding="utf-8") as f:
        json.dump(disagrees, f, ensure_ascii=False, indent=2)
    with open(confirms_path, "w", encoding="utf-8") as f:
        json.dump({"confirms": confirms, "multi_ok": multi_ok}, f, ensure_ascii=False)
    with open(summary_path, "w") as f:
        f.write(f"EN→{lang.upper()} reverse validation summary\n\n")
        f.write(f"Total entries: {total}\n")
        f.write(f"CONFIRMED: {len(confirms)}\n")
        f.write(f"MULTI_OK:  {len(multi_ok)}\n")
        f.write(f"DISAGREE:  {len(disagrees)}\n")
        f.write(f"UNKNOWN:   {len(unknowns)}\n\n")
        f.write("By original confidence tag:\n")
        for conf in sorted(by_conf, key=lambda c: -sum(by_conf[c].values())):
            d = by_conf[conf]
            f.write(f"  {conf}: " + "  ".join(f"{v}={d.get(v,0)}" for v in ("CONFIRMED", "MULTI_OK", "DISAGREE", "UNKNOWN")) + "\n")

    print(f"\nWrote: {summary_path}, {disagree_path}, {confirms_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("de", "fr", "it"):
        print("Usage: 48_reverse_validate.py {de|fr|it}")
        sys.exit(1)
    main(sys.argv[1])
