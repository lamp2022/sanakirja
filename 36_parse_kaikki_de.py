#!/usr/bin/env python3
"""
36_parse_kaikki_de.py

Parse kaikki German JSONL dump → EN→DE lookup.

Strategy:
- kaikki German has German lemmas with English glosses in senses[].glosses
- Each sense's first gloss term (split on ;) is treated as the primary EN equivalent
- POS comes from the German entry's "pos" field, mapped to Folkets-style codes for
  cross-language consistency (noun→nn, verb→vb, adj→jj, adv→ab)
- Multiple German lemmas may map to the same EN; we keep all and let the build
  script pick the best one (frequency-weighted)

Output: ../sanakirja/kaikki_de_en_de.json
Shape: {"<en_word>": {"<pos_class>": ["<de_lemma1>", "<de_lemma2>", ...]}}
"""

import json
import os
import re
import sys

KAIKKI_FILE = "../sanakirja/kaikki_german.jsonl"
OUTPUT_FILE = "../sanakirja/kaikki_de_en_de.json"

POS_MAP = {
    "noun": "nn",
    "verb": "vb",
    "adj": "jj",
    "adv": "ab",
    "name": "nn",
    "num": "rg",
    "pron": "pn",
    "prep": "pp",
    "conj": "kn",
    "intj": "in",
    "particle": "pc",
    "article": "article",
    "det": "jj",
}

# Strip wiktionary-style annotations from gloss
PARENS_RE = re.compile(r"\([^)]*\)")
TAG_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")  # [[link|text]] → text


def clean_gloss(g: str) -> str:
    g = TAG_RE.sub(r"\1", g)
    g = PARENS_RE.sub("", g)
    return g.strip()


def extract_primary_en_terms(gloss: str) -> list[str]:
    """A gloss like 'free; unenslaved; unimprisoned' → ['free', 'unenslaved', 'unimprisoned'].
    Take only top 3 terms per gloss to avoid pulling in long synonym lists."""
    g = clean_gloss(gloss).strip(" .,;:")
    if not g:
        return []
    # Split on ;  (semicolons separate distinct EN equivalents)
    parts = [p.strip() for p in re.split(r"\s*;\s*", g) if p.strip()]
    out = []
    for p in parts[:3]:
        # Strip trailing parenthetical, leading "to ", "a/an "
        p = re.sub(r"\s*\(.+?\)\s*", "", p).strip()
        # Skip overly long phrases (likely a definition not a translation)
        if len(p.split()) > 4:
            continue
        # Skip empty / non-alphabetic-only
        if p and any(c.isalpha() for c in p):
            out.append(p.lower())
    return out


def main():
    if not os.path.exists(KAIKKI_FILE):
        print(f"ERROR: {KAIKKI_FILE} not found. Wait for download to finish.", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {KAIKKI_FILE} …")
    fsize = os.path.getsize(KAIKKI_FILE)
    print(f"  File size: {fsize / 1e6:.1f} MB")

    en_map: dict[str, dict[str, list[str]]] = {}
    n_entries = 0
    n_kept = 0

    with open(KAIKKI_FILE, encoding="utf-8") as f:
        for line in f:
            n_entries += 1
            if n_entries % 50_000 == 0:
                print(f"  parsed {n_entries:,} German entries, EN keys so far: {len(en_map):,}")
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            de_lemma = d.get("word", "").strip()
            if not de_lemma:
                continue
            pos_raw = d.get("pos", "").lower()
            pos = POS_MAP.get(pos_raw, "")
            senses = d.get("senses", []) or []
            for sense in senses:
                glosses = sense.get("glosses", []) or []
                for g in glosses:
                    for en in extract_primary_en_terms(g):
                        slot = en_map.setdefault(en, {})
                        plist = slot.setdefault(pos, [])
                        if de_lemma not in plist:
                            plist.append(de_lemma)
                            n_kept += 1

    print(f"\n  Total German entries scanned: {n_entries:,}")
    print(f"  Total EN→DE mappings emitted: {n_kept:,}")
    print(f"  Unique EN keys covered:       {len(en_map):,}")

    print(f"\nWriting {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(en_map, f, ensure_ascii=False)
    print(f"  Done. {os.path.getsize(OUTPUT_FILE)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
