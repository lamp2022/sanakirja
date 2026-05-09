#!/usr/bin/env python3
"""
50_mine_disagreements.py

Filter reverse_validate_<lang>_disagreements.json to high-leverage primary-
translation correction candidates and write a hand-reviewable markdown.

A "high-leverage" candidate has:
  - Original confidence is single-source (gt_only / kaikki_only) OR has 'none'
  - Native Wiktionary lists ≤ 3 EN alternatives (focused, not noisy)
  - Our EN headword is NOT among native's translations (real disagreement, not
    a normalization edge case)

Sort by EN headword rank (most-frequent first) so high-impact cases bubble up.

Output: review_disagree_<lang>.md with one row per candidate:
    | rank | en | ours | native_says | confidence | verdict_box |

The verdict box is intentionally empty — fill in [APPROVE], [REJECT], or
[ALT: <word>] by hand. Then run the sibling apply script (51) to commit.

Usage:
    python3 50_mine_disagreements.py            # all 3 langs
    python3 50_mine_disagreements.py de         # one lang
"""

import json
import os
import sys

WEAK_CONFS = {"gt_only", "kaikki_only", "none"}
MAX_NATIVE_ALTS = 3
TOP_N_PER_LANG = 200  # Cap output size for review tractability


def first_translation(field) -> str:
    if isinstance(field, list):
        return (field[0] if field else "").strip()
    return (field or "").strip()


def run(lang: str) -> int:
    en_x_path = f"en_{lang}.json"
    disagree_path = f"reverse_validate_{lang}_disagreements.json"
    if not os.path.exists(disagree_path):
        print(f"  SKIP {lang}: {disagree_path} missing", file=sys.stderr)
        return 0

    en_x = json.load(open(en_x_path))
    disagrees = json.load(open(disagree_path))

    # Build (en, x) → rank lookup
    rank_lookup = {}
    for entry in en_x:
        en = entry.get("en", "").strip().lower()
        x = first_translation(entry.get(lang)).lower()
        rank_lookup[(en, x)] = entry.get("rank", 99999)

    # Filter
    candidates = []
    for d in disagrees:
        conf = d.get("confidence", "")
        if conf not in WEAK_CONFS:
            continue
        natives = d.get("native_en_words") or []
        if len(natives) > MAX_NATIVE_ALTS:
            continue
        en = d["en"].strip().lower()
        x = d[lang].strip().lower()
        rank = rank_lookup.get((en, x), 99999)
        candidates.append({
            "rank": rank,
            "en": en,
            lang: x,
            "native": natives,
            "confidence": conf,
        })

    # Sort: by rank ascending (most frequent first)
    candidates.sort(key=lambda c: c["rank"])
    candidates = candidates[:TOP_N_PER_LANG]

    out_path = f"review_disagree_{lang}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# EN→{lang.upper()} primary-translation disagreement review\n\n")
        f.write(f"Top {len(candidates)} high-leverage candidates from "
                f"reverse_validate_{lang}_disagreements.json.\n\n")
        f.write("**Filter:** confidence ∈ {gt_only, kaikki_only, none} AND ≤"
                f" {MAX_NATIVE_ALTS} native alternatives.\n\n")
        f.write("**How to use:** scan each row. In the **Verdict** column write one of:\n"
                "  - `KEEP` — our translation is fine\n"
                "  - `<native_word>` — replace primary with the listed native suggestion\n"
                "  - `<custom>` — provide a different translation\n\n")
        f.write("---\n\n")
        f.write("| Rank | EN | Our primary | Native says | Confidence | Verdict |\n")
        f.write("|------|----|------|------|------|------|\n")
        for c in candidates:
            natives_str = ", ".join(c["native"])
            f.write(f"| {c['rank']} | {c['en']} | **{c[lang]}** | {natives_str} | "
                    f"{c['confidence']} |  |\n")

    print(f"  {lang.upper()}: wrote {len(candidates)} candidates to {out_path}")
    return len(candidates)


def main():
    langs = sys.argv[1:] if len(sys.argv) > 1 else ["de", "it", "fr"]
    total = 0
    for L in langs:
        if L not in ("de", "fr", "it"):
            print(f"unknown lang: {L}", file=sys.stderr)
            sys.exit(1)
        total += run(L)
    print(f"\nTotal candidates surfaced: {total}")


if __name__ == "__main__":
    main()
