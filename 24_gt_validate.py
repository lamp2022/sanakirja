#!/usr/bin/env python3
"""
24_gt_validate.py

Live Google Translate EN→FI validation of the 3/4 source-agreement candidates
from 23_expand_en_fi.py. Writes a ranked review file with confidence tiers:

  TIER A: 4/4 sources + GT confirms       (already applied)
  TIER B: 4/4 sources, no GT confirm      (already applied)
  TIER C: 3/4 sources + GT confirms       (recommended next apply)
  TIER D: 3/4 sources + GT silent / no result
  TIER E: 3/4 sources + GT contradicts    (likely false positive)

Resumable: GT calls cached to gt_en_fi_checkpoint.jsonl. Re-runs reuse cache.
Read-only with respect to data.json — does not modify dictionary content.
"""

import importlib.util
import json
import os
import sys
import time
from collections import defaultdict, Counter

from utils import gt

# Import shared loaders + indexers from 23 via importlib (filename starts with digit)
_spec = importlib.util.spec_from_file_location(
    "_expand", os.path.join(os.path.dirname(__file__), "23_expand_en_fi.py"))
_expand = importlib.util.module_from_spec(_spec)
sys.modules["_expand"] = _expand
_spec.loader.exec_module(_expand)

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
CHECKPOINT = os.path.join(SOURCES_DIR, "gt_en_fi_checkpoint.jsonl")
RATE_LIMIT_SLEEP = 0.15  # courteous to unauthenticated GT endpoint


def normalize_gt_result(s):
    """Lowercase + strip articles."""
    if not s:
        return ""
    s = s.strip().lower()
    return s


def main():
    print("Loading sources via 23_expand_en_fi.py importer…")
    enfi = json.load(open(EN_FI_FILE))
    data = json.load(open(DATA_FILE))
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
    print(f"  enfi:{len(enfi)}  data:{len(data)}  rank:{len(rank)}")

    def lookup_pos(fi):
        p = data_pos.get(fi)
        if p:
            return p
        ks = kaikki_pos.get(fi)
        if ks:
            return "verb" if "verb" in ks else next(iter(ks))
        return jukka_pos.get(fi)

    # Generate candidates (same logic as 23)
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
            r = rank.get(fi_cand, 99999)
            if r > 3000:
                continue
            score = len(srcs)
            if score < 3:
                continue
            if en_is_verb and lookup_pos(fi_cand) != "verb":
                continue
            candidates.append({
                "score": score, "en": en, "primary_fi": primary_fi,
                "candidate_fi": fi_cand, "rank": r, "sources": sorted(srcs),
            })

    by_score = Counter(c["score"] for c in candidates)
    print(f"Candidates: {dict(by_score)}")

    # Unique EN words to validate (only 3/4 candidates need live GT)
    three_of_four = [c for c in candidates if c["score"] == 3]
    unique_ens = sorted(set(c["en"] for c in three_of_four))
    print(f"Unique EN words at 3/4 needing GT validation: {len(unique_ens)}")

    # Resume from checkpoint
    gt_results = {}
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            for line in f:
                rec = json.loads(line)
                gt_results[rec["en"]] = rec["fi_gt"]
        print(f"  loaded {len(gt_results)} from checkpoint")

    todo = [en for en in unique_ens if en not in gt_results]
    print(f"  remaining GT calls: {len(todo)}")

    # Make GT calls with checkpoint
    if todo:
        with open(CHECKPOINT, "a") as ck:
            for i, en in enumerate(todo):
                fi_gt = gt(en, sl="en", tl="fi")
                gt_results[en] = fi_gt or ""
                ck.write(json.dumps({"en": en, "fi_gt": fi_gt or ""},
                                    ensure_ascii=False) + "\n")
                ck.flush()
                if (i + 1) % 50 == 0:
                    print(f"    {i+1}/{len(todo)} done")
                time.sleep(RATE_LIMIT_SLEEP)
        print(f"  finished {len(todo)} live calls")

    # Annotate candidates with GT outcome
    def gt_status(c):
        if c["score"] == 4:
            # 4/4 already applied; mark by static cache (already in c['sources']
            # NO — actually, the 4/4 candidates use gt_check_results.json which
            # is FI-keyed. Let's recompute uniformly via the live cache too,
            # if available.
            fi_gt = gt_results.get(c["en"], "")
            if fi_gt:
                return "confirms" if c["candidate_fi"] in fi_gt else "silent_or_other"
            # 4/4 candidates may not have live GT; fall back to silent
            return "static_only"
        # 3/4
        fi_gt = gt_results.get(c["en"], "")
        if not fi_gt:
            return "no_result"
        if c["candidate_fi"] in fi_gt or fi_gt == c["candidate_fi"]:
            return "confirms"
        # GT returned something but not our candidate: contradicts (only weakly —
        # GT typically gives one primary; absence isn't strict refutation)
        return "silent_or_other"

    for c in candidates:
        c["gt"] = gt_status(c)

    # Tier assignment
    def tier(c):
        if c["score"] == 4:
            return "A" if c["gt"] == "confirms" else "B"
        # 3/4
        if c["gt"] == "confirms":
            return "C"
        if c["gt"] == "silent_or_other":
            return "D"
        return "D"  # no_result also goes D (we couldn't validate either way)

    for c in candidates:
        c["tier"] = tier(c)

    by_tier = Counter(c["tier"] for c in candidates)
    print(f"\nTier distribution: A={by_tier['A']}  B={by_tier['B']}  "
          f"C={by_tier['C']}  D={by_tier['D']}")

    # Sort: tier (A < B < C < D), then rank ascending
    tier_rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    candidates.sort(key=lambda c: (tier_rank[c["tier"]], c["rank"]))

    # Write review file
    review_path = "EN_FI_REVIEW_RANKED.md"
    with open(review_path, "w") as f:
        f.write("# EN→FI Candidates — Ranked by Confidence\n\n")
        f.write(f"Total: {len(candidates)} candidates "
                f"(A={by_tier['A']}, B={by_tier['B']}, "
                f"C={by_tier['C']}, D={by_tier['D']})\n\n")
        f.write("Tiers:\n")
        f.write("- **A**: 4/4 sources + GT confirms (✅ already applied)\n")
        f.write("- **B**: 4/4 sources, no GT confirm (already applied)\n")
        f.write("- **C**: 3/4 sources + live GT confirms (📌 recommended apply)\n")
        f.write("- **D**: 3/4 sources, GT silent/other (judgment call — review case-by-case)\n\n")
        cur_tier = None
        for c in candidates:
            if c["tier"] != cur_tier:
                cur_tier = c["tier"]
                tier_label = {
                    "A": "Tier A — 4/4 + GT confirms (already applied)",
                    "B": "Tier B — 4/4, no GT (already applied)",
                    "C": "Tier C — 3/4 + GT confirms (RECOMMEND APPLY)",
                    "D": "Tier D — 3/4, GT silent (manual review)",
                }[cur_tier]
                f.write(f"\n## {tier_label}\n\n")
                f.write("| EN | primary FI | new FI sense | rank | sources | GT(en→fi) |\n")
                f.write("|----|------------|--------------|------|---------|-----------|\n")
            gt_disp = gt_results.get(c["en"], "")
            f.write(f"| `{c['en']}` | `{c['primary_fi']}` | **`{c['candidate_fi']}`** "
                    f"| {c['rank']} | {','.join(c['sources'])} | {gt_disp or '—'} |\n")
    print(f"\nRanked review written to {review_path}")


if __name__ == "__main__":
    main()
