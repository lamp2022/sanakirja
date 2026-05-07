#!/usr/bin/env python3
"""
Step 11: Fill SV/IT/FR/DE for approved FI<->EN pairs, merge fixture, write data.json.

Prerequisite: all fi_en_batch_NN_decisions.json files saved (via 10_qc_server.py).

Inputs:
  fi_en_batch_NN_decisions.json  (one per batch, output of step 10)
  fixture.json                   (authoritative grammar/function words)
  sv_top.csv, it_top.csv, fr_top.csv
  kaikki_german.jsonl

Output:
  data.json  [{fi, en, sv?, it?, fr?, de?}, ...]  sorted by FI frequency
"""
import csv, json, os, re
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos

FIXTURE_FILE = "fixture.json"
CSC_FILE     = "csc_9996.csv"
OUTPUT       = "data.json"
LANGS_CSVS   = [("sv", "sv_top.csv"), ("it", "it_top.csv"), ("fr", "fr_top.csv")]


def load_approved():
    """Concatenate all batch decisions. Returns {(fi, fi_pos): en_final}."""
    approved = {}
    b = 1
    while True:
        path = f"fi_en_batch_{b:02d}_decisions.json"
        if not os.path.exists(path):
            break
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for dec in data.get("decisions", []):
            if dec.get("action") == "reject":
                continue
            fi, fi_pos, en = dec.get("fi"), dec.get("fi_pos"), dec.get("en_final")
            if fi and fi_pos and en:
                approved[(fi, fi_pos)] = en
        b += 1
    print(f"Loaded {len(approved)} approved pairs from {b - 1} batch files")
    return approved


def build_target_index(csv_path):
    idx = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pos = r.get("pos", "")
            if not is_content_pos(pos):
                continue
            defs = r.get("defs", "")
            first_def = defs.split(" | ")[0] if defs else ""
            if should_skip_gloss(first_def):
                continue
            en_token = first_gloss_first_token(first_def)
            if not en_token:
                continue
            pos_norm = normalize_pos(pos)
            idx[en_token.lower()].append((r["lemma"], pos_norm, int(r.get("rank", 9999))))
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    return dict(idx)


def build_de_index():
    print("Building DE reverse index from kaikki_german.jsonl (~2 min)...")
    idx = defaultdict(list)
    count = 0
    with open("kaikki_german.jsonl", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            pos = e.get("pos", "")
            if not is_content_pos(pos):
                continue
            word = e.get("word", "")
            if not word or not re.match(r"^[a-zäöüßA-ZÄÖÜ\-']+$", word):
                continue
            senses = e.get("senses", [])
            if not senses:
                continue
            first_gloss = (senses[0].get("glosses") or senses[0].get("raw_glosses") or [""])[0]
            if should_skip_gloss(first_gloss):
                continue
            en_token = first_gloss_first_token(first_gloss)
            if not en_token:
                continue
            pos_norm = normalize_pos(pos)
            if len(idx[en_token.lower()]) < 5:
                idx[en_token.lower()].append((word, pos_norm, len(word)))
            count += 1
            if count % 100000 == 0:
                print(f"  {count:,} DE entries")
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    print(f"  Done: {len(idx):,} EN keys in DE index")
    return dict(idx)


def best_target(en, fi_pos, idx):
    search_keys = [en.lower()]
    if en.lower().startswith("to "):
        search_keys.append(en.lower()[3:])
    for key in search_keys:
        candidates = idx.get(key, [])
        if candidates:
            matched = [c for c in candidates if c[1] == fi_pos]
            return (matched[0] if matched else candidates[0])[0]
    return None


def load_csc_ranks():
    ranks = {}
    with open(CSC_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            l, rk = r["lemma"], int(r["rank"])
            if l not in ranks or rk < ranks[l]:
                ranks[l] = rk
    return ranks


def main():
    approved = load_approved()

    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture = json.load(f)
    fixture_fi = {e["fi"] for e in fixture}
    print(f"Fixture: {len(fixture)} entries")

    print("Building target language indexes...")
    target_idx = {}
    for lang_code, csv_path in LANGS_CSVS:
        target_idx[lang_code] = build_target_index(csv_path)
        print(f"  {lang_code}: {len(target_idx[lang_code]):,} EN keys")
    target_idx["de"] = build_de_index()

    csc_ranks = load_csc_ranks()

    rows = []
    for (fi, fi_pos), en in approved.items():
        if fi in fixture_fi:
            continue
        row = {"fi": fi, "en": en}
        for lang in ("sv", "it", "fr", "de"):
            target = best_target(en, fi_pos, target_idx[lang])
            if target:
                row[lang] = target
        rows.append((csc_ranks.get(fi, 99999), fi, row))

    rows.sort(key=lambda x: (x[0], x[1]))

    # Fixture rows go first (already complete), then approved rows
    final = list(fixture)
    seen_fi = {e["fi"] for e in fixture}
    for _, fi, row in rows:
        if fi not in seen_fi:
            final.append(row)
            seen_fi.add(fi)

    total = len(final)
    all6 = sum(1 for r in final if all(k in r for k in ("fi","en","sv","it","fr","de")))
    fi_en_only = sum(1 for r in final if set(r.keys()) <= {"fi","en","fi_pos"})
    per_lang = {l: sum(1 for r in final if l in r) for l in ("en","sv","it","fr","de")}

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\n{OUTPUT}: {os.path.getsize(OUTPUT):,} bytes")
    print(f"  Total rows: {total:,}")
    print(f"  All 6 langs: {all6:,} ({all6*100//total}%)")
    print(f"  FI+EN only: {fi_en_only:,}")
    print(f"  Per-lang: {per_lang}")


if __name__ == "__main__":
    main()
