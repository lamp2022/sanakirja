#!/usr/bin/env python3
"""
35_parse_apertium_swe.py

Parse Apertium swe-eng.dix and extract EN↔SV lemma pairs.
Writes two JSON files:
  ../sanakirja/apertium_en_sv.json  — {en_lemma: [sv_lemmas]}
  ../sanakirja/apertium_sv_en.json  — {sv_lemma: [en_lemmas]}

The .dix format is bidirectional XML:
  <e><p><l>sv_word<s n="n"/></l><r>en_word<s n="n"/></r></p></e>
Left (l) = Swedish, right (r) = English in this file.

Run: python3 35_parse_apertium_swe.py
"""

import json
import os
import xml.etree.ElementTree as ET
from collections import defaultdict

DIX_FILE = "../sanakirja/apertium_swe_eng.dix"
OUT_EN_SV = "../sanakirja/apertium_en_sv.json"
OUT_SV_EN = "../sanakirja/apertium_sv_en.json"

# POS tags that indicate verbs in the dix
VERB_POS = {"vblex", "vbmod", "vbser", "vbhaver", "vbdo"}


def extract_lemma(elem) -> str:
    """Extract lemma text from a <l> or <r> element (strips <s> tags)."""
    text = elem.text or ""
    for child in elem:
        if child.tag == "s":
            break  # stop at first symbol tag — symbols mark inflection
        if child.tail:
            text += child.tail
    return text.strip().lower()


def extract_pos(elem) -> str | None:
    """Extract first <s n=...> POS tag from element."""
    for child in elem:
        if child.tag == "s":
            return child.get("n", "")
    return None


def is_verb_pos(pos: str | None) -> bool:
    return pos in VERB_POS if pos else False


def main():
    print(f"Parsing {DIX_FILE} …")
    tree = ET.parse(DIX_FILE)
    root = tree.getroot()

    en_sv: dict[str, list[str]] = defaultdict(list)
    sv_en: dict[str, list[str]] = defaultdict(list)

    parsed = 0
    skipped = 0

    # entries are in <section> elements containing <e> elements
    for section in root.iter("section"):
        for entry in section.iter("e"):
            pair = entry.find("p")
            if pair is None:
                continue
            l_elem = pair.find("l")
            r_elem = pair.find("r")
            if l_elem is None or r_elem is None:
                continue

            sv = extract_lemma(l_elem)
            en = extract_lemma(r_elem)
            sv_pos = extract_pos(l_elem)

            if not sv or not en:
                skipped += 1
                continue

            # For verb entries in English, prefix with "to "
            if is_verb_pos(sv_pos) and not en.startswith("to "):
                en = "to " + en

            if sv not in en_sv.get(en, []) and en:
                if en not in en_sv or sv not in en_sv[en]:
                    en_sv[en].append(sv)
            if en not in sv_en.get(sv, []) and sv:
                if sv not in sv_en or en not in sv_en[sv]:
                    sv_en[sv].append(en)

            parsed += 1

    print(f"  Parsed: {parsed:,} entries, skipped: {skipped:,}")
    print(f"  Unique EN keys: {len(en_sv):,}")
    print(f"  Unique SV keys: {len(sv_en):,}")

    # Sort for determinism
    en_sv_sorted = {k: v for k, v in sorted(en_sv.items())}
    sv_en_sorted = {k: v for k, v in sorted(sv_en.items())}

    with open(OUT_EN_SV, "w", encoding="utf-8") as f:
        json.dump(en_sv_sorted, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {OUT_EN_SV}")

    with open(OUT_SV_EN, "w", encoding="utf-8") as f:
        json.dump(sv_en_sorted, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {OUT_SV_EN}")

    # Sanity check: a few expected entries
    checks = [("dog", "hund"), ("book", "bok"), ("red", "röd"), ("car", "bil")]
    print("\nSanity checks:")
    for en, sv_expected in checks:
        svs = en_sv.get(en, [])
        hit = sv_expected in svs
        print(f"  {'✓' if hit else '✗'} {en} → {svs[:3]} (expected {sv_expected!r})")


if __name__ == "__main__":
    main()
