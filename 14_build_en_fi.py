#!/usr/bin/env python3
"""
Derive EN→FI dataset from data.json (FI→EN master).
No data duplication — pure transformation.
Output: en_fi_data.json — list of {en, fi: [...], rank}
"""

import json, csv, os, re

DATA_FILE   = "data.json"
SOURCES_DIR = "../sanakirja"
FREQ_FILE   = os.path.join(SOURCES_DIR, "fi_top.csv")
OUTPUT_FILE = "en_fi_data.json"

# Words where the Finnish primary is misleading and should not win EN→FI tiebreaks
SECONDARY_BOOST = {'kenraali'}

NOISE_PATTERNS = [
    'used when', 'the finnish', 'a finnish', 'understating', 'let us',
    'indicative', 'connegative', 'intensifier', 'synonym of', 'frequentative',
    'any private',
]


def normalize(s):
    # Strip indefinite articles only — keep 'to ' so verb/noun homographs
    # ('to lock' vs 'lock') stay as separate EN→FI entries.
    return re.sub(r'^(a |an )', '', s.lower().strip())


def is_bad_en(s):
    return (any(p in s.lower() for p in NOISE_PATTERNS)
            or s.startswith('-')
            or len(s) < 2)


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    freq = {}
    with open(FREQ_FILE) as f:
        for row in csv.DictReader(f):
            freq[row['lemma']] = int(row['rank'])

    # Collect candidates per English key
    # Tiebreaker: primary meanings rank higher (lower effective rank) than secondaries
    en_to_fi = {}
    for entry in data:
        fi = entry['fi']
        en = entry['en']
        rank = freq.get(fi, 9999)
        meanings = en if isinstance(en, list) else [en]
        for i, meaning in enumerate(meanings):
            if is_bad_en(meaning):
                continue
            key = normalize(meaning)
            if len(key) < 2:
                continue
            is_secondary = (i > 0) or (fi in SECONDARY_BOOST)
            eff_rank = rank if not is_secondary else rank + 5000
            en_to_fi.setdefault(key, []).append((eff_rank, rank, fi, meaning))

    # Build entries: max 3 Finnish options per English, sorted by effective rank
    entries = []
    for cands in en_to_fi.values():
        cands.sort()
        best_en = cands[0][3]
        best_rank = cands[0][1]
        fi_list = []
        for _, _, fi, _ in cands:
            if fi not in fi_list:
                fi_list.append(fi)
            if len(fi_list) == 3:
                break
        entries.append({
            'en': best_en,
            'fi': fi_list[0] if len(fi_list) == 1 else fi_list,
            'rank': best_rank,
        })

    entries.sort(key=lambda e: (e['rank'], e['en']))

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    multi = sum(1 for e in entries if isinstance(e['fi'], list))
    single = sum(1 for e in entries if isinstance(e['fi'], str))
    print(f"Wrote {len(entries)} EN→FI entries to {OUTPUT_FILE}")
    print(f"  Single FI:  {single}")
    print(f"  Multiple FI: {multi}")


if __name__ == "__main__":
    main()
