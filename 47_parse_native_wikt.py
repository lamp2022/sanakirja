#!/usr/bin/env python3
"""
47_parse_native_wikt.py

Parse a native target-language Wiktionary kaikki dump (de/fr/it) into
an X→EN reverse lookup for cross-validation against en_X.json.

Each entry in a native dump represents a lemma from that Wiktionary edition.
We keep only entries whose lang_code matches the target language (the dump
also contains entries about foreign words, e.g. dewiktionary describing
Italian lemmas).

Output: one JSON per language with shape:
    {"<lemma>": {"en_words": ["...", ...], "pos": "<pos>"}}

Usage:
    python3 47_parse_native_wikt.py de
    python3 47_parse_native_wikt.py fr
    python3 47_parse_native_wikt.py it
"""

import gzip
import json
import os
import re
import sys

NATIVE_DIR = "/Users/ttt/Documents/AI_Agent_Claude/projects/sanakirja/native_wikt"

PARENS_RE = re.compile(r"\([^)]*\)")
TAG_RE = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]")


def clean(s: str) -> str:
    s = TAG_RE.sub(r"\1", s)
    s = PARENS_RE.sub("", s)
    return s.strip(" .,;:")


def main(lang: str):
    src = f"{NATIVE_DIR}/{lang}wiktionary.jsonl.gz"
    out = f"{NATIVE_DIR}/native_{lang}_en.json"
    if not os.path.exists(src):
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(1)

    fsize = os.path.getsize(src) / 1e6
    print(f"Parsing {src} ({fsize:.0f} MB compressed)…")

    lookup: dict[str, dict] = {}
    n_total = 0
    n_native = 0
    n_with_en = 0

    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            n_total += 1
            if n_total % 100_000 == 0:
                print(f"  scanned {n_total:,} entries  native={n_native:,}  with EN={n_with_en:,}")
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("lang_code") != lang:
                continue
            n_native += 1
            lemma = (d.get("word") or "").strip().lower()
            if not lemma:
                continue
            translations = d.get("translations") or []
            en_words = []
            for t in translations:
                if t.get("lang_code") != "en":
                    continue
                w = clean(t.get("word") or "").lower()
                if not w or len(w) > 60:
                    continue
                # Drop multi-word phrases (unlikely to be primary equivalent)
                if len(w.split()) > 4:
                    continue
                if w not in en_words:
                    en_words.append(w)
            if not en_words:
                continue
            n_with_en += 1
            pos = (d.get("pos") or "").lower()
            slot = lookup.setdefault(lemma, {"en_words": [], "pos_set": set()})
            for w in en_words:
                if w not in slot["en_words"]:
                    slot["en_words"].append(w)
            if pos:
                slot["pos_set"].add(pos)

    # Convert pos_set → sorted list for JSON
    out_data = {
        lemma: {"en_words": v["en_words"], "pos": sorted(v["pos_set"])}
        for lemma, v in lookup.items()
    }

    print(f"\nTotals: scanned={n_total:,} native={n_native:,} with_en={n_with_en:,} unique_lemmas={len(out_data):,}")
    print(f"Writing {out}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False)
    print(f"  Done. {os.path.getsize(out)/1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("de", "fr", "it"):
        print("Usage: 47_parse_native_wikt.py {de|fr|it}")
        sys.exit(1)
    main(sys.argv[1])
