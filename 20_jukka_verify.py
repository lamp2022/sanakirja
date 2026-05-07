#!/usr/bin/env python3
"""
Add Jukka dictionary entries with GT 3-way verification.
Batches of 500. Auto-add if GT and Jukka agree; flag disagreements for user review.

Usage:
    python3 20_jukka_verify.py [batch_num]    # default batch 1
"""

import json, csv, re, time, requests, sys, os

DATA_FILE      = "data.json"
JUKKA_FILE     = "jukka_enriched.csv"
CHECKPOINT     = "jukka_verify_checkpoint.jsonl"
BATCH_SIZE     = 500


KOTUS_TO_POS = {
    'substantiivi': 'noun',
    'verbi': 'verb',
    'adjektiivi': 'adj',
    'adverbi': 'adv',
    'pronomini': 'pron',
    'numeraali': 'num',
    'interjektio': 'intj',
    'konjunktio': 'conj',
    'partikkeli': 'particle',
    'postpositio': 'postp',
    'prepositio': 'prep',
}


def first_meaning(jukka_en):
    """Get the first comma-separated meaning."""
    return jukka_en.split(',')[0].strip()


def normalize(s):
    return re.sub(r'^(to |a |an )', '', s.lower().strip())


def gt(word):
    url = 'https://translate.googleapis.com/translate_a/single'
    params = {'client': 'gtx', 'sl': 'fi', 'tl': 'en', 'dt': 't', 'q': word}
    return requests.get(url, params=params, timeout=8).json()[0][0][0].strip().lower()


def main():
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    with open(DATA_FILE) as f:
        data = json.load(f)
    fi_in_data = {d['fi'] for d in data}

    # Load Jukka, filter to missing entries
    with open(JUKKA_FILE) as f:
        jukka = list(csv.DictReader(f))
    missing = [j for j in jukka if j['fi'] not in fi_in_data]

    # Skip suspicious entries up front
    SKIP_MARKERS = ['archaic', 'obsolete', 'dated', 'dialectal', 'dialect',
                    'rare', 'rarely', 'colloquial slang', 'old-fashioned',
                    'biblical', 'poetic']
    def usable(j):
        fi = j['fi']
        en = j['en'].strip().lower()
        kotus = j.get('kotus_class', '').lower()
        if not fi or not en or len(fi) < 2:
            return False
        if fi[0].isupper():                              # proper-name leakage
            return False
        if 'erisnimi' in kotus or 'paikannimi' in kotus:  # proper noun / place name
            return False
        # Markers in the gloss (archaic, dialectal, etc.)
        for m in SKIP_MARKERS:
            if m in en:
                return False
        # Capitalized translation usually = proper noun (e.g. country, name)
        first_word = j['en'].split(',')[0].strip()
        if first_word and first_word[0].isupper() and first_word not in (
            'I', 'English', 'Finnish'):
            return False
        return True

    missing = [j for j in missing if usable(j)]
    missing.sort(key=lambda x: x['fi'])

    start = (batch_num - 1) * BATCH_SIZE
    end = start + BATCH_SIZE
    batch = missing[start:end]

    print(f"Total missing: {len(missing)}")
    print(f"Batch {batch_num}: entries {start+1}-{min(end, len(missing))} ({len(batch)} entries)")
    print()

    # Check checkpoint to skip already-processed
    done_keys = set()
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            for line in f:
                e = json.loads(line)
                done_keys.add(e['fi'])

    # Verify with GT
    auto_add = []
    flagged = []

    with open(CHECKPOINT, 'a') as ck:
        for i, j in enumerate(batch):
            if j['fi'] in done_keys:
                continue
            try:
                jukka_first = first_meaning(j['en'])
                gt_en = gt(j['fi'])

                # Match if first words overlap (ignoring 'to ', 'a ' prefix)
                n_jukka = normalize(jukka_first)
                n_gt = normalize(gt_en)
                match = (n_jukka == n_gt or
                         n_jukka in n_gt or
                         n_gt in n_jukka or
                         any(w in n_gt.split() for w in n_jukka.split()[:1]))

                pos = KOTUS_TO_POS.get(j['kotus_class'].split(',')[0].strip(), '')

                # For verbs, ensure 'to ' prefix
                if pos == 'verb' and not jukka_first.lower().startswith('to '):
                    jukka_first = 'to ' + jukka_first.lower()

                rec = {
                    'fi': j['fi'],
                    'en_jukka': jukka_first,
                    'en_gt': gt_en,
                    'pos': pos,
                    'match': match,
                }
                ck.write(json.dumps(rec, ensure_ascii=False) + '\n')
                ck.flush()

                if match:
                    auto_add.append(rec)
                else:
                    flagged.append(rec)

                if (i+1) % 50 == 0:
                    print(f"  GT {i+1}/{len(batch)} (matches: {len(auto_add)}, flags: {len(flagged)})")
                time.sleep(0.12)
            except Exception as e:
                print(f"  err {j['fi']}: {e}")
                time.sleep(1)

    # Auto-add the matches to data.json
    for r in auto_add:
        data.append({'fi': r['fi'], 'en': r['en_jukka'], 'pos': r['pos']})

    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n=== Batch {batch_num} summary ===")
    print(f"Auto-added (GT+Jukka agree): {len(auto_add)}")
    print(f"Flagged for review:          {len(flagged)}")
    print(f"Total entries now:           {len(data)}")

    # Show flagged for user review
    print(f"\n=== {len(flagged)} flagged disagreements ===")
    print(f"{'FI':<22} {'Jukka':<28} {'GT'}")
    print("-" * 80)
    for r in flagged:
        print(f"{r['fi']:<22} {r['en_jukka'][:26]:<28} {r['en_gt']}")


if __name__ == "__main__":
    main()
