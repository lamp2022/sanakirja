#!/usr/bin/env python3
"""40_parse_kaikki_it.py — same logic as 36_parse_kaikki_de.py but for Italian."""

import json
import os
import re
import sys

KAIKKI_FILE = "../sanakirja/kaikki_italian.jsonl"
OUTPUT_FILE = "../sanakirja/kaikki_it_en_it.json"

POS_MAP = {
    "noun": "nn", "verb": "vb", "adj": "jj", "adv": "ab",
    "name": "nn", "num": "rg", "pron": "pn", "prep": "pp",
    "conj": "kn", "intj": "in", "particle": "pc", "det": "jj",
}

PARENS_RE = re.compile(r"\([^)]*\)")
TAG_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")


def clean_gloss(g):
    g = TAG_RE.sub(r"\1", g)
    g = PARENS_RE.sub("", g)
    return g.strip()


def extract_primary_en_terms(gloss):
    g = clean_gloss(gloss).strip(" .,;:")
    if not g:
        return []
    parts = [p.strip() for p in re.split(r"\s*;\s*", g) if p.strip()]
    out = []
    for p in parts[:3]:
        p = re.sub(r"\s*\(.+?\)\s*", "", p).strip()
        if len(p.split()) > 4:
            continue
        if p and any(c.isalpha() for c in p):
            out.append(p.lower())
    return out


def main():
    if not os.path.exists(KAIKKI_FILE):
        print(f"ERROR: {KAIKKI_FILE} missing", file=sys.stderr)
        sys.exit(1)
    print(f"Parsing {KAIKKI_FILE} ({os.path.getsize(KAIKKI_FILE)/1e6:.1f} MB) …")

    en_map = {}
    n_entries = n_kept = 0
    with open(KAIKKI_FILE, encoding="utf-8") as f:
        for line in f:
            n_entries += 1
            if n_entries % 50_000 == 0:
                print(f"  parsed {n_entries:,}, EN keys: {len(en_map):,}")
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            it_lemma = d.get("word", "").strip()
            if not it_lemma:
                continue
            pos = POS_MAP.get(d.get("pos", "").lower(), "")
            for sense in d.get("senses", []) or []:
                for g in sense.get("glosses", []) or []:
                    for en in extract_primary_en_terms(g):
                        slot = en_map.setdefault(en, {})
                        plist = slot.setdefault(pos, [])
                        if it_lemma not in plist:
                            plist.append(it_lemma)
                            n_kept += 1

    print(f"\n  Total IT entries: {n_entries:,}")
    print(f"  EN→IT mappings:   {n_kept:,}")
    print(f"  Unique EN keys:   {len(en_map):,}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(en_map, f, ensure_ascii=False)
    print(f"  Wrote {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
