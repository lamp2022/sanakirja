#!/usr/bin/env python3
"""
25_apply_tier_c.py

Apply the 3/4-source-agreement candidates that were live-GT-confirmed by
24_gt_validate.py (Tier C). Identical apply mechanic to 23_expand_en_fi.py:
appends EN word to candidate FI's `en` list in data.json. Idempotent.

Reject list (REJECT below) skips a small number of false positives the user
flagged after manual review of Tier C.

Run 14_build_en_fi.py afterwards to refresh en_fi_data.json.
"""

import importlib.util
import json
import os
import sys
from collections import defaultdict, Counter

from utils import atomic_write_json

# Import shared loaders from 23
_spec = importlib.util.spec_from_file_location(
    "_expand", os.path.join(os.path.dirname(__file__), "23_expand_en_fi.py"))
_expand = importlib.util.module_from_spec(_spec)
sys.modules["_expand"] = _expand
_spec.loader.exec_module(_expand)

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
GT_LIVE_CHECKPOINT = os.path.join(SOURCES_DIR, "gt_en_fi_checkpoint.jsonl")

# Borderline candidates the user manually rejected after Tier C review.
# Format: (EN, candidate_fi) pairs to skip even if GT-confirmed.
REJECT = {
    ("countryside", "maa"),    # maa = generic land/earth, too broad
    ("soil", "maa"),           # same — over-general
    ("kingdom", "kunta"),      # substring artifact: GT returned 'kuningaskunta';
                               # kunta alone = "municipality", not kingdom
}


def main():
    print("Loading data + sources…")
    data = json.load(open(DATA_FILE))
    enfi = json.load(open(EN_FI_FILE))
    data_pos = {e["fi"]: (e.get("pos") or "").lower() for e in data if e.get("fi")}
    rank = _expand.load_rank(os.path.join(SOURCES_DIR, "fi_top.csv"))
    kaikki, kaikki_pos = _expand.reverse_kaikki(
        os.path.join(SOURCES_DIR, "kaikki_glosses_checkpoint.json"))
    jukka, jukka_pos = _expand.reverse_jukka(
        os.path.join(SOURCES_DIR, "jukka_enriched.csv"))
    apert = _expand.reverse_apertium(
        os.path.join(SOURCES_DIR, "apertium_fin_eng.json"))
    wikt = _expand.reverse_wikt(
        os.path.join(SOURCES_DIR, "wikt_fi_definitions.jsonl"))

    if not os.path.exists(GT_LIVE_CHECKPOINT):
        sys.exit(f"Missing {GT_LIVE_CHECKPOINT} — run 24_gt_validate.py first.")
    gt_results = {}
    with open(GT_LIVE_CHECKPOINT) as f:
        for line in f:
            rec = json.loads(line)
            gt_results[rec["en"]] = rec["fi_gt"]
    print(f"  GT live cache: {len(gt_results)} entries")

    def lookup_pos(fi):
        p = data_pos.get(fi)
        if p:
            return p
        ks = kaikki_pos.get(fi)
        if ks:
            return "verb" if "verb" in ks else next(iter(ks))
        return jukka_pos.get(fi)

    # Generate 3/4 candidates
    candidates = []
    for entry in enfi:
        fi_val = entry["fi"]
        if isinstance(fi_val, list):
            continue
        primary_fi = fi_val
        en = entry["en"]
        en_is_verb = en.lower().startswith("to ")
        en_n = _expand.norm(en)
        fi_votes = defaultdict(set)
        for src_name, src in [("kaikki", kaikki), ("jukka", jukka),
                              ("apertium", apert), ("wikt", wikt)]:
            for fi_cand in src.get(en_n, ()):
                fi_votes[fi_cand].add(src_name)
        for fi_cand, srcs in fi_votes.items():
            if fi_cand == primary_fi:
                continue
            if rank.get(fi_cand, 99999) > 3000:
                continue
            if len(srcs) != 3:
                continue
            if en_is_verb and lookup_pos(fi_cand) != "verb":
                continue
            candidates.append({"en": en, "primary_fi": primary_fi,
                               "candidate_fi": fi_cand})

    # Filter to Tier C: GT confirms (substring or exact match)
    tier_c = []
    for c in candidates:
        fi_gt = gt_results.get(c["en"], "")
        if not fi_gt:
            continue
        if c["candidate_fi"] in fi_gt or fi_gt == c["candidate_fi"]:
            if (c["en"], c["candidate_fi"]) in REJECT:
                continue
            tier_c.append(c)

    print(f"Tier C after reject list: {len(tier_c)}")

    # Apply
    by_fi = {e["fi"]: e for e in data}
    added = 0
    skipped_already = 0
    skipped_missing = 0
    sample = []
    for c in tier_c:
        en = c["en"]
        candidate_fi = c["candidate_fi"]
        entry = by_fi.get(candidate_fi)
        if not entry:
            skipped_missing += 1
            continue
        cur = entry.get("en")
        cur_list = list(cur) if isinstance(cur, list) else [cur]
        if en in cur_list:
            skipped_already += 1
            continue
        cur_list.append(en)
        entry["en"] = cur_list
        added += 1
        if len(sample) < 8:
            sample.append((candidate_fi, en, cur_list))

    print(f"\nApplied:                       {added}")
    print(f"  candidate already had EN:    {skipped_already}")
    print(f"  candidate FI not in data.json: {skipped_missing}")
    if sample:
        print("\nSample additions:")
        for fi, en, en_list in sample:
            print(f"  {fi:>15}.en += {en!r:<22} → {en_list}")

    if added > 0:
        print("\nWriting data.json atomically…")
        atomic_write_json(DATA_FILE, data)
        print("Done. Run 14_build_en_fi.py to refresh en_fi_data.json.")
    else:
        print("\nNo changes (idempotent re-run).")


if __name__ == "__main__":
    main()
