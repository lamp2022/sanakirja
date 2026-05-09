#!/usr/bin/env python3
"""
cross_validate.py — cross-validate EN→X primaries against kaikki English's
EN-keyed translations. Surfaces high-confidence corrections.

For each entry in en_X.json:
1. Look up the EN word in kaikki_english.parquet
2. Pull all translations for the target language X
3. If our primary is in that list → green (validated)
4. If our primary is NOT in that list AND kaikki has 1+ translations → flag as
   suspicious and propose kaikki's first translation as the correction

Writes:
- DISAGREEMENTS_X.md — human-reviewable list of mismatches
- en_X_kaikki_corrections.json — proposed extras overrides

Usage: .venv/bin/python cross_validate.py de it fr sv
"""

import json
import os
import sys

import pyarrow.parquet as pq
import pyarrow.compute as pc


KAIKKI_EN = "../sanakirja/kaikki_english.parquet"


def normalize_de(s: str) -> str:
    s = s.lower().strip()
    if s.startswith("zu "):
        s = s[3:]
    if s.startswith("um zu "):
        s = s[6:]
    if s.startswith("der ") or s.startswith("die ") or s.startswith("das "):
        s = s[4:]
    return s


def normalize_it(s: str) -> str:
    s = s.lower().strip()
    for art in ("il ", "la ", "lo ", "i ", "le ", "gli ", "un ", "una ", "uno "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def normalize_fr(s: str) -> str:
    s = s.lower().strip()
    if s.startswith("se "):
        s = s[3:]
    elif s.startswith("s'"):
        s = s[2:]
    for art in ("le ", "la ", "les ", "l'", "un ", "une ", "des ", "du ", "de "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def normalize_sv(s: str) -> str:
    s = s.lower().strip()
    if s.startswith("att "):
        s = s[4:]
    return s


NORMALIZE = {"de": normalize_de, "it": normalize_it, "fr": normalize_fr, "sv": normalize_sv}


def build_en_lookup(parquet_path: str, lang_codes: list[str]) -> dict:
    """Build {en_word: {lang: [translations]}} from kaikki English."""
    print(f"Loading {parquet_path} (this may take 10s)...")
    t = pq.read_table(parquet_path, columns=["word", "translations"])
    # Filter to entries with non-empty translations
    has_trans = pc.greater(pc.list_value_length(t["translations"]), 0)
    t = t.filter(has_trans)
    print(f"  {t.num_rows:,} EN entries with translations")

    lookup: dict[str, dict[str, list[str]]] = {}
    words = t["word"].to_pylist()
    trans_list = t["translations"].to_pylist()
    for word, tr in zip(words, trans_list):
        if not word:
            continue
        key = word.lower()
        slot = lookup.setdefault(key, {})
        for one in tr:
            code = (one.get("code") or "").lower()
            if code in lang_codes and one.get("word"):
                slot.setdefault(code, []).append(one["word"])
    print(f"  lookup keys: {len(lookup):,}")
    return lookup


def cross_validate(lang: str, lookup: dict):
    en_X = f"en_{lang}.json"
    if not os.path.exists(en_X):
        print(f"  SKIP {lang}: {en_X} not found")
        return
    data = json.load(open(en_X))
    norm = NORMALIZE[lang]

    validated = 0
    flagged = []  # (rank, en, primary, kaikki_top3)
    no_kaikki = 0

    for e in data:
        en = e["en"].lower()
        primary_v = e.get(lang)
        primary = primary_v[0] if isinstance(primary_v, list) else primary_v
        if not primary:
            continue

        # kaikki entry — try with and without "to " prefix
        k = lookup.get(en) or lookup.get(en[3:] if en.startswith("to ") else "")
        if not k or lang not in k:
            no_kaikki += 1
            continue

        k_translations = k[lang]
        # Normalize all for comparison
        k_norms = {norm(t) for t in k_translations}
        prim_norm = norm(primary)

        if prim_norm in k_norms:
            validated += 1
        else:
            # Pick kaikki top-3 unique
            seen = set()
            top = []
            for t in k_translations:
                ln = norm(t)
                if ln not in seen:
                    seen.add(ln)
                    top.append(t)
                if len(top) >= 3:
                    break
            flagged.append((e["rank"], e["en"], primary, top, e.get("confidence", "")))

    # Sort by rank (most common first)
    flagged.sort(key=lambda x: x[0])

    print(f"\n=== {lang.upper()} ===")
    print(f"  Validated by kaikki EN:   {validated:,}")
    print(f"  Flagged disagreements:    {len(flagged):,}")
    print(f"  Not in kaikki EN:         {no_kaikki:,}")

    # Write report
    report = f"DISAGREEMENTS_{lang.upper()}.md"
    with open(report, "w") as f:
        f.write(f"# EN→{lang.upper()} disagreements with kaikki English\n\n")
        f.write(f"Pipeline primary differs from kaikki English's translation list. "
                f"Lower rank = more common EN word.\n\n")
        f.write(f"Validated: {validated:,} | Flagged: {len(flagged):,} | "
                f"Not in kaikki: {no_kaikki:,}\n\n")
        f.write(f"| Rank | EN | Our primary | kaikki EN top-3 | Confidence |\n")
        f.write(f"|------|----|----|----|----|\n")
        for r, en, prim, top, conf in flagged[:200]:
            top_str = " / ".join(top)
            f.write(f"| {r} | `{en}` | `{prim}` | {top_str} | {conf} |\n")
    print(f"  Wrote {report} ({min(len(flagged), 200)} entries shown of {len(flagged)})")

    # Write proposed extras (high-confidence: rank ≤ 1000 AND kaikki has 2+ matching senses)
    # For now: just dump all flagged with rank ≤ 500 as proposed corrections
    proposals = [
        {"en": en, lang: top[0], "rank": r, "_old_primary": prim,
         "_kaikki_alternatives": top}
        for r, en, prim, top, conf in flagged
        if r <= 500 and top
    ]
    proposals_path = f"en_{lang}_kaikki_corrections.json"
    with open(proposals_path, "w") as f:
        json.dump({"proposals": proposals}, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {proposals_path} ({len(proposals)} top-500-rank corrections proposed)")


def main():
    if len(sys.argv) < 2:
        langs = ["de", "it", "fr", "sv"]
    else:
        langs = sys.argv[1:]
    if not os.path.exists(KAIKKI_EN):
        print(f"ERROR: {KAIKKI_EN} not found")
        sys.exit(1)

    lookup = build_en_lookup(KAIKKI_EN, langs)
    for lang in langs:
        cross_validate(lang, lookup)


if __name__ == "__main__":
    main()
