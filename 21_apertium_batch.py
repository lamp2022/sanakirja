#!/usr/bin/env python3
"""
Add Apertium FI-EN entries in batches with GT cross-verification.
Only adds when Apertium AND GT agree (high confidence).
Flags disagreements for user review (no auto-add).

Usage:
    python3 21_apertium_batch.py [batch_num]    # default batch 1
"""

import json, csv, re, time, sys, os
from utils import atomic_write_json, gt

DATA_FILE     = "data.json"
APERTIUM_FILE = "apertium/fin-eng.dix"
FREQ_FILE     = "fi_top.csv"
CHECKPOINT    = "apertium_verify_checkpoint.jsonl"
BATCH_SIZE    = 150


def normalize(s):
    return re.sub(r'^(to |a |an )', '', s.lower().strip())


def load_apertium():
    with open(APERTIUM_FILE) as f:
        content = f.read()
    entries = re.findall(r'<e[^>]*>\s*<p>\s*<l>(.*?)</l>\s*<r>(.*?)</r>\s*</p>\s*</e>',
                          content, re.DOTALL)
    def clean(s):
        s = re.sub(r'<b\s*/>', ' ', s)
        s = re.sub(r'<[^>]+>', '', s)
        return re.sub(r'\s+', ' ', s).strip()
    apertium = {}
    for l, r in entries:
        fi, en = clean(l), clean(r)
        if not (fi and en and len(fi) > 1 and len(en) > 1):
            continue
        if fi not in apertium:
            apertium[fi] = en
    return apertium


SKIP_REMOVED = {
    'seppo', 'jorma', 'harri', 'jussi', 'mikko',
    'kesti', 'otin', 'sanoja', 'pieniä', 'kunnon', 'siitä', 'viestin',
    'ammu', 'aivo',
    'outokumpu', 'bosnia', 'kemi', 'mikkeli', 'liperi',
    'oh', 'in', 'min', 'cup', 'show', 'anti', 'lana', 'house',
    'lienee', 'paranee', 'kerrottava', 'oikeaan', 'paikalle',
    'liikkeelle', 'kylään', 'periksi', 'kahden', 'varaan',
    'viereen', 'perään', 'päähän', 'lasta', 'maista',
    'aaltonen', 'haavisto', 'kankkunen', 'nurminen', 'lehtinen',
    'tauno', 'sergei', 'sari', 'donna', 'diana', 'maya', 'jin',
    'putin', 'penny', 'tom', 'mm', 'em', 'ay', 'ii', 'su', 'to',
    'cd', 'la', 'just', 'sit',
    'miksei', 'muttei', 'vaikkei',  # contractions
}


def main():
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    with open(DATA_FILE) as f:
        data = json.load(f)
    fi_in_data = {d['fi'] for d in data}

    # Remove any of the wrongly-re-added entries from previous bug
    before = len(data)
    data = [d for d in data if d['fi'] not in SKIP_REMOVED]
    if before != len(data):
        print(f"Removed {before - len(data)} previously re-added bad entries")
        atomic_write_json(DATA_FILE, data)
        fi_in_data = {d['fi'] for d in data}

    apertium = load_apertium()
    print(f"Apertium: {len(apertium)} lemmas")

    freq = {}
    with open(FREQ_FILE) as f:
        for row in csv.DictReader(f):
            if row['lemma'] not in freq:
                freq[row['lemma']] = (int(row['rank']), row.get('pos', ''))

    # Filter: Apertium ∩ fi_top, not in data, not weird
    SKIP_POS = {'pron', 'intj', 'postp', 'prep', 'conj', 'det', 'name',
                'punct', 'particle', 'aux', 'sym', 'num'}

    candidates = []
    for fi, ap_en in apertium.items():
        if fi in fi_in_data or fi in SKIP_REMOVED:
            continue
        if fi[0].isupper() or ap_en[0].isupper():
            continue
        if len(fi) > 25 or len(fi) < 3:
            continue
        # Multi-word Finnish: skip (not lemmas)
        if ' ' in fi:
            continue
        # Apertium compound prefixes/suffixes — not real lemmas
        if fi.startswith('-') or fi.endswith('-'):
            continue
        if ap_en.startswith('-') or ap_en.endswith('-'):
            continue
        # POS from frequency list if available, else infer
        if fi in freq:
            rank, pos = freq[fi]
            if pos in SKIP_POS:
                continue
        else:
            # Not in frequency list — use Apertium's natural ordering as proxy
            # Only accept words with simple single-word English (likely common)
            rank = 99999
            pos = ''
            if len(ap_en.split()) > 2:  # multi-word translation = specialized
                continue
        candidates.append((rank, fi, ap_en, pos))

    candidates.sort()
    print(f"Candidates after filter: {len(candidates)}")

    start = (batch_num - 1) * BATCH_SIZE
    end = start + BATCH_SIZE
    batch = candidates[start:end]
    print(f"Batch {batch_num}: entries {start+1}-{min(end, len(candidates))} ({len(batch)})")

    done_keys = set()
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            for line in f:
                done_keys.add(json.loads(line)['fi'])

    auto_add = []
    flagged = []

    with open(CHECKPOINT, 'a') as ck:
        for i, (rank, fi, ap_en, pos) in enumerate(batch):
            if fi in done_keys:
                continue
            try:
                gt_en = gt(fi)
                # Match if first words overlap (ignoring 'to ', 'a ', 'an ')
                n_ap = normalize(ap_en)
                n_gt = normalize(gt_en)
                match = bool(
                    n_ap == n_gt or
                    n_ap in n_gt or
                    n_gt in n_ap or
                    (set(n_ap.split()[:1]) & set(n_gt.split()))
                )
                # 'to ' for verbs
                final_en = ap_en
                if pos == 'verb' and not final_en.lower().startswith('to '):
                    final_en = 'to ' + final_en.lower()

                rec = {'fi': fi, 'rank': rank, 'pos': pos,
                       'en_apertium': final_en, 'en_gt': gt_en, 'match': match}
                ck.write(json.dumps(rec, ensure_ascii=False) + '\n')
                ck.flush()

                if match:
                    auto_add.append(rec)
                else:
                    flagged.append(rec)
                if (i+1) % 25 == 0:
                    print(f"  {i+1}/{len(batch)} (matches: {len(auto_add)}, flags: {len(flagged)})")
                time.sleep(0.12)
            except Exception as e:
                print(f"  err {fi}: {e}")
                time.sleep(1)

    # Auto-add only matches
    for r in auto_add:
        data.append({'fi': r['fi'], 'en': r['en_apertium'], 'pos': r['pos']})
    atomic_write_json(DATA_FILE, data)

    print(f"\n=== Batch {batch_num} ===")
    print(f"Auto-added (Apertium+GT agree): {len(auto_add)}")
    print(f"Flagged for review:             {len(flagged)}")
    print(f"Total entries now:              {len(data)}")
    print()
    print("=== Flagged for your review ===")
    print(f"{'FI':<22} {'Apertium':<25} {'GT'}")
    print("-" * 70)
    for r in flagged:
        print(f"{r['fi']:<22} {r['en_apertium'][:23]:<25} {r['en_gt']}")


if __name__ == "__main__":
    main()
