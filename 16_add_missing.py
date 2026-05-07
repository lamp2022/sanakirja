#!/usr/bin/env python3
"""
Add missing content-word lemmas (noun/verb/adj) from fi_top.csv to data.json.
Pipeline: GT primary + kaikki secondary, same cleaning rules as 13_build_meanings.py.

Resumable via gt_missing_checkpoint.jsonl — append-only.
"""

import json, csv, re, os, time, requests
from utils import atomic_write_json

DATA_FILE      = "data.json"
FREQ_FILE      = "fi_top.csv"
GT_CHECKPOINT  = "gt_missing_checkpoint.jsonl"
KAIKKI_CHECK   = "kaikki_glosses_checkpoint.json"
KAIKKI_FILE    = "kaikki_finnish.jsonl"

ALLOW_POS = {'noun', 'verb', 'adj', 'adv'}


def gt(word):
    url = 'https://translate.googleapis.com/translate_a/single'
    params = {'client': 'gtx', 'sl': 'fi', 'tl': 'en', 'dt': 't', 'q': word}
    r = requests.get(url, params=params, timeout=8)
    return r.json()[0][0][0].strip()


def clean_gloss(raw):
    g = re.sub(r'\[.*?\]', '', raw).strip()
    g = re.sub(r'\(.*?\)', '', g).strip()
    g = g.split(';')[0].strip()
    g = g.split(',')[0].strip()
    g = g.rstrip('.,;:[').strip()
    g = g.lower()
    if len(g.split()) > 4 or len(g) < 2:
        return None
    return g


SKIP = ['nominatiivi','plural of','singular','passive participle','past participle',
        'present participle','connegative','indicative','conditional','imperative',
        'ellipsis of','clipping of','synonym of','frequentative of',
        'finnish surname','given name','former municipality','from southwest',
        'from southeast','from eastern','from western','from northern','from southern',
        'pertaining to','of or relating','squirrel pelt','bath broom','moo-moo',
        'hullabaloo','goblet','iota','callus','stead','swidden','jobber',
        'archaic','dialectal']

def is_english(text):
    low = text.lower()
    return not any(s in low for s in SKIP)


def normalize(s):
    return re.sub(r'^(to |a |an )', '', s.lower().strip())


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)
    fi_in_data = {d['fi'] for d in data}

    # Build candidates: missing content lemmas
    seen = {}
    with open(FREQ_FILE) as f:
        for r in csv.DictReader(f):
            if r['lemma'] not in seen:
                seen[r['lemma']] = (int(r['rank']), r['lemma'], r.get('pos',''))

    candidates = sorted(
        (t for t in seen.values() if t[1] not in fi_in_data and t[2] in ALLOW_POS),
        key=lambda x: x[0]
    )
    print(f"Candidates to add: {len(candidates)}")

    # Load GT checkpoint
    done = {}
    if os.path.exists(GT_CHECKPOINT):
        with open(GT_CHECKPOINT) as f:
            for line in f:
                e = json.loads(line)
                done[e['fi']] = e
        print(f"Resuming: {len(done)} already done")

    # GT scan with append-only checkpoint
    todo = [c for c in candidates if c[1] not in done]
    print(f"GT pending: {len(todo)}")

    with open(GT_CHECKPOINT, 'a') as ck:
        for i, (rank, lemma, pos) in enumerate(todo):
            try:
                en = gt(lemma)
                # Add 'to ' prefix for verbs if missing
                if pos == 'verb' and not en.lower().startswith('to '):
                    en = 'to ' + en.lower()
                entry = {'fi': lemma, 'pos': pos, 'rank': rank, 'en': en}
                ck.write(json.dumps(entry, ensure_ascii=False) + '\n')
                ck.flush()
                done[lemma] = entry
                if (i+1) % 100 == 0:
                    print(f"  GT {i+1}/{len(todo)}")
                time.sleep(0.12)
            except Exception as e:
                print(f"  err {lemma}: {e}")
                time.sleep(2)

    print(f"GT done: {len(done)}")

    # Load kaikki glosses (already cached from 13_build_meanings.py)
    kaikki = {}
    if os.path.exists(KAIKKI_CHECK):
        with open(KAIKKI_CHECK) as f:
            kaikki = json.load(f)
        # Re-filter with current rules
        for k in list(kaikki.keys()):
            kaikki[k] = [g for g in kaikki[k] if is_english(g)]
            if not kaikki[k]:
                del kaikki[k]

    # If many candidates lack kaikki entries, we'd need to rescan kaikki.
    # For now, use cached entries; missing words just get GT-only meaning.

    def get_kaikki(fi):
        out = []
        for k, gl in kaikki.items():
            if k.split('|')[0] == fi.lower():
                for g in gl:
                    if g not in out:
                        out.append(g)
        return out

    # Merge: build entries with primary + secondary
    new_entries = []
    for entry in done.values():
        primary = entry['en']
        primary = re.sub(r' +', ' ', primary).strip()
        meanings = [primary]
        seen_n = {normalize(primary)}
        for g in get_kaikki(entry['fi']):
            if len(meanings) >= 2:
                break
            n = normalize(g)
            if n not in seen_n:
                meanings.append(g)
                seen_n.add(n)

        new_entries.append({
            'fi': entry['fi'],
            'pos': entry['pos'],
            'en': meanings[0] if len(meanings) == 1 else meanings,
        })

    # Merge into data.json
    with open(DATA_FILE) as f:
        data = json.load(f)
    existing = {d['fi'] for d in data}
    added = [e for e in new_entries if e['fi'] not in existing]
    data.extend(added)

    atomic_write_json(DATA_FILE, data)

    print(f"\nAdded {len(added)} entries. data.json now has {len(data)} total.")


if __name__ == "__main__":
    main()
