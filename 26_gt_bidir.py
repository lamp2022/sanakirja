#!/usr/bin/env python3
"""
26_gt_bidir.py

Bidirectional GT validation of Tier D (3/4 sources, EN→FI GT didn't confirm).
Strategy: for each unique candidate_fi, call GT(fi, sl='fi', tl='en'). If the
target EN word appears in the GT result (whole-word or stem match), the
candidate is bidirectionally confirmed and promoted.

Existing FI→EN GT cache (gt_check_results.json, 1403 entries) is consulted
first — only cache misses trigger live calls. New results append to
gt_fi_en_checkpoint.jsonl for resumability.

Read-only with respect to data.json — only writes a review file. Apply via
27_apply_tier_d_bidir.py if results look good.
"""

import importlib.util
import json
import os
import re
import sys
import time
from collections import defaultdict, Counter

from utils import gt

# Import shared loaders from 23
_spec = importlib.util.spec_from_file_location(
    "_expand", os.path.join(os.path.dirname(__file__), "23_expand_en_fi.py"))
_expand = importlib.util.module_from_spec(_spec)
sys.modules["_expand"] = _expand
_spec.loader.exec_module(_expand)

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
GT_FI_EN_STATIC = os.path.join(SOURCES_DIR, "gt_check_results.json")  # FI→EN cache
GT_EN_FI_LIVE = os.path.join(SOURCES_DIR, "gt_en_fi_checkpoint.jsonl")  # from 24
GT_FI_EN_LIVE = os.path.join(SOURCES_DIR, "gt_fi_en_checkpoint.jsonl")  # this script
RATE_LIMIT_SLEEP = 0.15


def stem(s):
    """Crude Finnish stem — strip common suffix to detect inflected matches."""
    s = s.lower().strip()
    for suf in ("issa", "issä", "ille", "illa", "illä", "ina", "inä",
                "issä", "iksi", "isiin", "ssa", "ssä", "sta", "stä",
                "lla", "llä", "lle", "ksi", "tta", "ttä", "ksen",
                "ttaa", "ttää", "tää", "vat", "vät", "ja", "jä",
                "en", "in", "an", "än", "on", "un", "yn",
                "a", "ä", "n", "t"):
        if len(s) > len(suf) + 2 and s.endswith(suf):
            return s[:-len(suf)]
    return s


def en_match(en_target, gt_result):
    """Does the EN word appear in the GT result string?"""
    if not gt_result:
        return False
    g = gt_result.lower().strip()
    e = en_target.lower().strip()
    # exact
    if g == e:
        return True
    # whole-word boundary in multi-word GT result
    if re.search(rf"\b{re.escape(e)}\b", g):
        return True
    # GT result is the EN with "to " prefix or vice versa
    e_no_to = e.removeprefix("to ").strip()
    g_no_to = g.removeprefix("to ").strip()
    if e_no_to == g_no_to:
        return True
    return False


def load_static_gt_fi_en(path):
    """gt_check_results.json: list of {fi, en_gt, ...} → {fi: en_gt}"""
    cache = {}
    d = json.load(open(path))
    for entry in d:
        fi = entry.get("fi")
        en_gt = entry.get("en_gt")
        if fi and en_gt:
            cache[fi] = en_gt.lower().strip()
    return cache


def load_jsonl_cache(path, key_field):
    """Load a JSONL cache. key_field: 'en' for EN→FI cache, 'fi' for FI→EN cache."""
    if not os.path.exists(path):
        return {}
    cache = {}
    val_field = "fi_gt" if key_field == "en" else "en_gt"
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            cache[rec[key_field]] = rec.get(val_field, "")
    return cache


def main():
    print("Loading sources…")
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

    en_to_fi_gt = load_jsonl_cache(GT_EN_FI_LIVE, "en")
    static_fi_to_en = load_static_gt_fi_en(GT_FI_EN_STATIC)
    live_fi_to_en = load_jsonl_cache(GT_FI_EN_LIVE, "fi")
    print(f"  EN→FI cache:  {len(en_to_fi_gt)}")
    print(f"  FI→EN static: {len(static_fi_to_en)}")
    print(f"  FI→EN live:   {len(live_fi_to_en)}")

    def lookup_pos(fi):
        p = data_pos.get(fi)
        if p:
            return p
        ks = kaikki_pos.get(fi)
        if ks:
            return "verb" if "verb" in ks else next(iter(ks))
        return jukka_pos.get(fi)

    def gt_fi_en(fi):
        if fi in static_fi_to_en:
            return static_fi_to_en[fi]
        if fi in live_fi_to_en:
            return live_fi_to_en[fi]
        return None

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
                               "candidate_fi": fi_cand, "rank": rank.get(fi_cand, 99999),
                               "sources": sorted(srcs)})

    print(f"Total 3/4 candidates: {len(candidates)}")

    # Filter to Tier D: EN→FI GT did NOT confirm
    def en_fi_confirms(c):
        fi_gt = en_to_fi_gt.get(c["en"], "")
        if not fi_gt:
            return False
        return c["candidate_fi"] in fi_gt

    tier_d = [c for c in candidates if not en_fi_confirms(c)]
    print(f"Tier D (EN→FI did NOT confirm): {len(tier_d)}")

    # Bidirectional check: gather unique candidate_fi needing GT
    fis_needed = sorted(set(c["candidate_fi"] for c in tier_d))
    fis_to_call = [fi for fi in fis_needed
                   if fi not in static_fi_to_en and fi not in live_fi_to_en]
    print(f"Unique candidate_fi: {len(fis_needed)}  ({len(fis_to_call)} need live calls)")

    if fis_to_call:
        with open(GT_FI_EN_LIVE, "a") as ck:
            for i, fi in enumerate(fis_to_call):
                en_gt = gt(fi, sl="fi", tl="en")
                live_fi_to_en[fi] = en_gt or ""
                ck.write(json.dumps({"fi": fi, "en_gt": en_gt or ""},
                                    ensure_ascii=False) + "\n")
                ck.flush()
                if (i + 1) % 50 == 0:
                    print(f"    {i+1}/{len(fis_to_call)} done")
                time.sleep(RATE_LIMIT_SLEEP)
        print(f"  finished {len(fis_to_call)} live FI→EN calls")

    # Promote: candidate is bidirectionally confirmed if FI→EN GT contains the EN
    promoted = []
    for c in tier_d:
        gt_en = gt_fi_en(c["candidate_fi"]) or ""
        if en_match(c["en"], gt_en):
            promoted.append({**c, "gt_fi_en": gt_en})

    print(f"\nPromoted (bidirectional GT confirms): {len(promoted)}")

    # Write review file
    review_path = "EN_FI_REVIEW_TIER_D_BIDIR.md"
    promoted.sort(key=lambda c: c["rank"])
    with open(review_path, "w") as f:
        f.write("# Tier D — Bidirectionally GT-Confirmed Promotions\n\n")
        f.write(f"Total promoted: {len(promoted)} of {len(tier_d)} Tier D candidates\n\n")
        f.write("Strategy: GT(candidate_fi → en) contains the target English word.\n\n")
        f.write("| EN | primary FI | new FI sense | rank | sources | GT(fi→en) |\n")
        f.write("|----|------------|--------------|------|---------|-----------|\n")
        for c in promoted:
            f.write(f"| `{c['en']}` | `{c['primary_fi']}` | "
                    f"**`{c['candidate_fi']}`** | {c['rank']} | "
                    f"{','.join(c['sources'])} | {c['gt_fi_en']} |\n")
    print(f"Review written to {review_path}")

    # Also write the promoted candidates as JSON for the apply script
    out_json = "tier_d_promoted.json"
    with open(out_json, "w") as f:
        json.dump(promoted, f, ensure_ascii=False, indent=2)
    print(f"Promotion list written to {out_json}")


if __name__ == "__main__":
    main()
