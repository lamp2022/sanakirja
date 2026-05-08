#!/usr/bin/env python3
"""
28_tier_d_top50.py

Rank the remaining Tier D candidates (3/4 sources, neither EN→FI GT nor
bidirectional FI→EN GT confirms exactly) by composite quality score and
write the top 50 to EN_FI_REVIEW_TIER_D_TOP50.md for manual review.

Score signals:
  + 'kaikki' in sources (well-curated Wiktionary)         → +2
  + 'jukka' in sources (curated dictionary)               → +2
  + 'wikt' in sources                                     → +1
  + POS(candidate) == POS(primary)                        → +2
  + candidate FI is itself in data.json (known lemma)     → +1
  + GT(en→fi) returned a non-empty result                 → +0 (already used in tier split)
  Tiebreaker: rank ascending (more common first).
"""

import importlib.util
import json
import os
import sys
from collections import defaultdict

_spec = importlib.util.spec_from_file_location(
    "_expand", os.path.join(os.path.dirname(__file__), "23_expand_en_fi.py"))
_expand = importlib.util.module_from_spec(_spec)
sys.modules["_expand"] = _expand
_spec.loader.exec_module(_expand)

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
GT_EN_FI_LIVE = os.path.join(SOURCES_DIR, "gt_en_fi_checkpoint.jsonl")
GT_FI_EN_STATIC = os.path.join(SOURCES_DIR, "gt_check_results.json")
GT_FI_EN_LIVE = os.path.join(SOURCES_DIR, "gt_fi_en_checkpoint.jsonl")
PROMOTED_FILE = "tier_d_promoted.json"


def main():
    enfi = json.load(open(EN_FI_FILE))
    data = json.load(open(DATA_FILE))
    data_pos = {e["fi"]: (e.get("pos") or "").lower() for e in data if e.get("fi")}
    data_fi_set = set(data_pos.keys())
    rank = _expand.load_rank(os.path.join(SOURCES_DIR, "fi_top.csv"))
    kaikki, kaikki_pos = _expand.reverse_kaikki(
        os.path.join(SOURCES_DIR, "kaikki_glosses_checkpoint.json"))
    jukka, jukka_pos = _expand.reverse_jukka(
        os.path.join(SOURCES_DIR, "jukka_enriched.csv"))
    apert = _expand.reverse_apertium(
        os.path.join(SOURCES_DIR, "apertium_fin_eng.json"))
    wikt = _expand.reverse_wikt(
        os.path.join(SOURCES_DIR, "wikt_fi_definitions.jsonl"))

    # GT caches
    en_to_fi_gt = {}
    if os.path.exists(GT_EN_FI_LIVE):
        with open(GT_EN_FI_LIVE) as f:
            for line in f:
                rec = json.loads(line)
                en_to_fi_gt[rec["en"]] = rec.get("fi_gt", "")

    fi_to_en_gt = {}
    for entry in json.load(open(GT_FI_EN_STATIC)):
        if entry.get("fi") and entry.get("en_gt"):
            fi_to_en_gt[entry["fi"]] = entry["en_gt"].lower().strip()
    if os.path.exists(GT_FI_EN_LIVE):
        with open(GT_FI_EN_LIVE) as f:
            for line in f:
                rec = json.loads(line)
                fi_to_en_gt[rec["fi"]] = rec.get("en_gt", "")

    # Already-promoted (from 26)
    already_promoted = set()
    if os.path.exists(PROMOTED_FILE):
        for c in json.load(open(PROMOTED_FILE)):
            already_promoted.add((c["en"], c["candidate_fi"]))

    def lookup_pos(fi):
        p = data_pos.get(fi)
        if p:
            return p
        ks = kaikki_pos.get(fi)
        if ks:
            return "verb" if "verb" in ks else next(iter(ks))
        return jukka_pos.get(fi)

    # Generate 3/4 candidates that are CURRENTLY single-sense in en_fi_data.json
    # AND not yet applied to data.json
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
            # Skip already-applied (data.json's en list already includes this)
            d_entry = next((e for e in data if e["fi"] == fi_cand), None)
            if d_entry:
                cur_en = d_entry.get("en")
                cur_list = cur_en if isinstance(cur_en, list) else [cur_en]
                if en in cur_list:
                    continue
            candidates.append({
                "en": en, "primary_fi": primary_fi, "candidate_fi": fi_cand,
                "rank": rank.get(fi_cand, 99999), "sources": sorted(srcs),
            })

    # Tier D = no GT confirmation (neither EN→FI nor bidirectional)
    def en_fi_confirms(c):
        fi_gt = en_to_fi_gt.get(c["en"], "")
        return fi_gt and c["candidate_fi"] in fi_gt

    tier_d = [c for c in candidates if not en_fi_confirms(c)
              and (c["en"], c["candidate_fi"]) not in already_promoted]
    print(f"Tier D remaining (after C and bidir applied): {len(tier_d)}")

    # Score
    for c in tier_d:
        srcs = set(c["sources"])
        score = 0
        if "kaikki" in srcs: score += 2
        if "jukka" in srcs: score += 2
        if "wikt" in srcs: score += 1
        prim_pos = data_pos.get(c["primary_fi"])
        cand_pos = lookup_pos(c["candidate_fi"])
        if prim_pos and cand_pos and prim_pos == cand_pos:
            score += 2
        if c["candidate_fi"] in data_fi_set:
            score += 1
        c["score"] = score
        c["primary_pos"] = prim_pos or "?"
        c["candidate_pos"] = cand_pos or "?"
        c["gt_en_fi"] = en_to_fi_gt.get(c["en"], "")
        c["gt_fi_en"] = fi_to_en_gt.get(c["candidate_fi"], "")

    tier_d.sort(key=lambda c: (-c["score"], c["rank"]))

    top = tier_d[:50]
    out_md = "EN_FI_REVIEW_TIER_D_TOP50.md"
    with open(out_md, "w") as f:
        f.write("# Tier D — Top 50 by quality score\n\n")
        f.write(f"Top 50 of {len(tier_d)} remaining Tier D candidates, "
                f"ranked by composite quality score.\n\n")
        f.write("Score = 2*kaikki + 2*jukka + 1*wikt + 2*POS_match + "
                "1*in_data_json. Max = 8.\n\n")
        f.write("Convention: prepend `~~` to a row to reject it before apply.\n\n")
        f.write("| Score | EN | primary FI (POS) | new FI sense (POS) | rank | sources | GT(en→fi) | GT(fi→en) |\n")
        f.write("|-------|----|------------------|--------------------|------|---------|-----------|-----------|\n")
        for c in top:
            f.write(f"| {c['score']} | `{c['en']}` | "
                    f"`{c['primary_fi']}` ({c['primary_pos']}) | "
                    f"**`{c['candidate_fi']}`** ({c['candidate_pos']}) | "
                    f"{c['rank']} | {','.join(c['sources'])} | "
                    f"{c['gt_en_fi'] or '—'} | {c['gt_fi_en'] or '—'} |\n")
    print(f"Wrote {len(top)} to {out_md}")

    # Also dump as JSON for easy apply
    with open("tier_d_top50.json", "w") as f:
        json.dump(top, f, ensure_ascii=False, indent=2)
    print("JSON: tier_d_top50.json")


if __name__ == "__main__":
    main()
