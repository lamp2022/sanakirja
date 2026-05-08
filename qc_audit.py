#!/usr/bin/env python3
"""
qc_audit.py LANG

Quality-control pass on en_<lang>.json. Runs:
  1. Coverage stats summary
  2. Top-100 / top-1000 freq corpus coverage (lemma vs inflection-likely)
  3. Probe ~30 known multi-sense / common-bug words
  4. Concatenated-junk detector (long no-space strings absent from freq corpus)
  5. Verb-noun mismatch check (EN 'to X' but X primary doesn't look like a verb)
  6. Empty-target check (entries with no translation)

Usage: .venv/bin/python qc_audit.py de   (or it / fr / sv)
"""

import json
import os
import sys


PROBE_WORDS = [
    "house", "dog", "car", "book", "run", "fall", "fit", "fly", "light",
    "no", "not", "from", "she", "her", "to be", "to have", "to bear",
    "bear", "reason", "pace", "old man", "such as", "somehow", "gig",
    "accurately", "wave", "rock", "fire", "to read", "to write",
]


def lang_verb_check(s, lang):
    """Heuristic: does this look like an infinitive in this language?"""
    s = s.lower().strip()
    if not s or " " in s:
        return False
    if lang == "de":
        return s.endswith(("en", "rn", "ln")) or s in ("sein", "tun")
    if lang == "it":
        return any(s.endswith(suf) for suf in ("are", "ere", "ire", "arsi", "ersi", "irsi", "rsi"))
    if lang == "fr":
        return s.endswith(("er", "ir", "re"))
    if lang == "sv":
        return False  # SV uses 'att X' which is detected separately
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: qc_audit.py LANG (de/it/fr/sv)")
        sys.exit(1)
    lang = sys.argv[1].lower()
    en_x = f"en_{lang}.json"
    freq_path = f"../sanakirja/{lang}_freq_50k.txt"
    if not os.path.exists(en_x):
        print(f"ERROR: {en_x} not found")
        sys.exit(1)
    if not os.path.exists(freq_path):
        print(f"ERROR: {freq_path} not found")
        sys.exit(1)

    data = json.load(open(en_x))
    freq = {}
    with open(freq_path) as f:
        for i, line in enumerate(f):
            parts = line.split()
            if parts:
                freq[parts[0].lower()] = i + 1

    print(f"\n=== QC audit: en_{lang}.json ===")
    print(f"Total entries: {len(data):,}")

    # 1. Confidence breakdown
    conf_counts = {}
    for e in data:
        c = e.get("confidence", "none")
        conf_counts[c] = conf_counts.get(c, 0) + 1
    print("\nConfidence distribution:")
    for k, v in sorted(conf_counts.items(), key=lambda x: -x[1])[:8]:
        print(f"  {k:25} {v:>5}")

    # 2. Reverse coverage: how many of top-N freq words appear in our X primaries?
    x_in_dict = set()
    for e in data:
        v = e.get(lang)
        vs = v if isinstance(v, list) else [v]
        for s in vs:
            if not s:
                continue
            s = s.lower().strip()
            x_in_dict.add(s)
            if " " in s:
                x_in_dict.add(s.split()[0])

    top_words = []
    with open(freq_path) as f:
        for line in f:
            parts = line.split()
            if parts:
                top_words.append(parts[0].lower())

    print("\nReverse coverage (of top common words, % covered as primary or secondary):")
    for n in [100, 500, 1000, 2000, 5000]:
        covered = sum(1 for w in top_words[:n] if w in x_in_dict)
        print(f"  top {n:>5}: {covered:>5} ({covered/n*100:.1f}%)")

    # 3. Probe words
    print("\nProbe word check (multi-sense / known bug patterns):")
    en_to_entry = {e["en"].lower(): e for e in data}
    for w in PROBE_WORDS:
        e = en_to_entry.get(w.lower())
        if not e:
            continue
        v = e.get(lang)
        primary = v[0] if isinstance(v, list) else v
        print(f"  {w:15} → {primary!s:30} [{e.get('confidence', '?')}]")

    # 4. Concatenated junk detector: long no-space strings absent from freq corpus
    print("\nSuspected concatenated junk (>16 chars, no space, absent from freq):")
    junk = []
    for e in data:
        v = e.get(lang)
        vs = v if isinstance(v, list) else [v]
        for s in vs:
            if not s or len(s) < 16 or " " in s or "/" in s:
                continue
            if freq.get(s.lower(), 99999) == 99999:
                junk.append((e["rank"], e["en"], s))
                break
    junk.sort()
    print(f"  found: {len(junk)}")
    for r, en, x in junk[:10]:
        print(f"    #{r:>4}  {en:25} → {x}")

    # 5. Verb-noun mismatch
    print(f"\nVerb-noun mismatches (EN 'to X' but {lang} primary not infinitive):")
    bad_verbs = []
    for e in data:
        en = e["en"].lower()
        if not en.startswith("to "):
            continue
        v = e.get(lang)
        primary = (v[0] if isinstance(v, list) else v) or ""
        # SV uses 'att X' prefix
        if lang == "sv":
            looks_verb = primary.startswith("att ") or " " in primary
        else:
            looks_verb = lang_verb_check(primary, lang) or primary.startswith(("zu ", "se ", "s'"))
        if primary and not looks_verb:
            bad_verbs.append((e["rank"], en, primary, e.get("confidence", "")))
    bad_verbs.sort()
    print(f"  found: {len(bad_verbs)}")
    for r, en, x, c in bad_verbs[:10]:
        print(f"    #{r:>4}  {en:25} → {x:30} [{c}]")

    # 6. Empty translations
    empty = sum(1 for e in data if not e.get(lang))
    print(f"\nEmpty translations: {empty}")


if __name__ == "__main__":
    main()
