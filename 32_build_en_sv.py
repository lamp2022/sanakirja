#!/usr/bin/env python3
"""
32_build_en_sv.py

Phase 2 SV smoke test pipeline.
Sources:
  1. Folkets lexikon EN→SV XML (primary, authoritative KTH dictionary)
  2. Live GT EN→SV (secondary, checkpointed)
  3. claude_en_sv.jsonl (Claude inline translations, top 2000 by rank)
  4. Apertium swe-eng bidix (cautious 4th source, 47% EN overlap)

For each EN key in en_fi_data.json:
  - Look up Folkets translation(s)
  - Look up GT translation (resume from checkpoint)
  - Look up Claude translation (if available)
  - Look up Apertium translation (if available)
  - Emit entry with confidence tag

Confidence tags (sources that agree with Folkets primary SV):
  - "4sources": Folkets + GT + Claude + Apertium
  - "3sources": Folkets + GT + Claude (or other 3-source combo)
  - "folkets+gt+apert": Folkets + GT + Apertium
  - "folkets+gt": Folkets and GT agree
  - "folkets+claude": Folkets and Claude agree
  - "folkets+apert": Folkets and Apertium agree
  - "folkets_only": Folkets has it, no secondary agreement
  - "gt+claude": GT and Claude agree, no Folkets
  - "gt_only": GT only
  - "claude_only": Claude only

Run: python3 32_build_en_sv.py
Writes en_sv.json (prototype) and EN_SV_REVIEW_SAMPLE.md.
Long-running (GT calls) — resumable via checkpoint.
"""

import json
import os
import random
import sys
import time
import xml.etree.ElementTree as ET

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
FOLKETS_FILE = os.path.join(SOURCES_DIR, "folkets_en_sv.xml")
GT_CHECKPOINT = os.path.join(SOURCES_DIR, "gt_en_sv_checkpoint.jsonl")
CLAUDE_FILE = os.path.join(SOURCES_DIR, "claude_en_sv.jsonl")
APERTIUM_FILE = os.path.join(SOURCES_DIR, "apertium_en_sv.json")
FREQ_FILE = os.path.join(SOURCES_DIR, "sv_freq_50k.txt")
OUTPUT_FILE = "en_sv.json"
SAMPLE_FILE = "EN_SV_REVIEW_SAMPLE.md"

GT_FREQ_THRESHOLD = 5000   # primary must be rarer than this rank to qualify for GT override
GT_FREQ_RATIO = 2          # GT must be at least this many times more common than primary

GT_DELAY = 0.15  # seconds between GT requests


def load_sv_freq(path: str) -> dict[str, int]:
    """Load Swedish word frequency list. Returns {word: rank} where rank 1 = most common."""
    freq: dict[str, int] = {}
    if not os.path.exists(path):
        return freq
    with open(path) as f:
        for i, line in enumerate(f):
            parts = line.strip().split()
            if len(parts) >= 1:
                freq[parts[0].lower()] = i + 1
    return freq


def load_folkets_en_sv(path: str) -> dict[str, list[str]]:
    """Parse Folkets EN→SV XML. Returns {en_word: [sv_translations]}."""
    print(f"Parsing {path} …")
    tree = ET.parse(path)
    root = tree.getroot()
    lookup: dict[str, list[str]] = {}

    for word_elem in root.iter("word"):
        value = word_elem.get("value", "").strip().lower()
        if not value:
            continue
        translations = []
        for trans in word_elem.iter("translation"):
            tv = trans.get("value", "").strip()
            if tv:
                translations.append(tv.lower())
        if translations:
            if value not in lookup:
                lookup[value] = []
            for t in translations:
                if t not in lookup[value]:
                    lookup[value].append(t)

    print(f"  Folkets EN→SV: {len(lookup):,} EN entries loaded")
    return lookup


def load_jsonl_cache(path: str, key_field: str) -> dict[str, str]:
    """Load a JSONL checkpoint file into a dict keyed by key_field."""
    cache: dict[str, str] = {}
    if not os.path.exists(path):
        return cache
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                k = rec.get(key_field)
                if k:
                    cache[k] = rec
            except json.JSONDecodeError:
                pass
    return cache


def is_lemma(sv: str, max_words: int = 4) -> bool:
    """Return True if sv looks like a lemma (not an example sentence)."""
    sv = sv.strip()
    if not sv:
        return False
    # Sentence indicators: ends with '.', contains full stops mid-string, too many words
    if sv.endswith(".") or len(sv.split()) > max_words:
        return False
    # Contains digits (likely a code or example number)
    if any(c.isdigit() for c in sv):
        return False
    return True


_SV_PARTICLES = frozenset(["till", "upp", "av", "ut", "in", "om", "bort", "med", "ihop", "ned", "ner"])


def _norm(s: str) -> str:
    """Normalize SV: lowercase, strip 'att ' prefix, reflexive ' sig', and trailing verbal particles."""
    s = s.lower().strip()
    if s.startswith("att "):
        s = s[4:]
    if s.endswith(" sig"):
        s = s[:-4]
    parts = s.split()
    if len(parts) >= 2 and parts[-1] in _SV_PARTICLES:
        s = " ".join(parts[:-1])
    return s


def consensus_override(folkets_primary: str, sv_gt: str, claude_sv: str,
                       apert_sv_primary: str) -> str | None:
    """Return consensus word (original form, e.g. 'att vinna') if 2+ secondary sources agree
    on a normalized form different from Folkets primary."""
    fp = _norm(folkets_primary)
    raw_candidates = [s for s in [sv_gt, claude_sv, apert_sv_primary] if s]
    if not raw_candidates:
        return None
    # Map normalized form → first raw form seen (GT preferred as first)
    norm_to_raw: dict[str, str] = {}
    counts: dict[str, int] = {}
    for c in raw_candidates:
        nc = _norm(c)
        if nc not in norm_to_raw:
            norm_to_raw[nc] = c
        counts[nc] = counts.get(nc, 0) + 1
    best_norm = max(counts, key=lambda k: counts[k])
    if counts[best_norm] >= 2 and best_norm != fp:
        return norm_to_raw[best_norm]  # return original form (preserves 'att ' prefix)
    return None


def sv_matches(candidate: str, gt_sv: str) -> bool:
    """Check if candidate appears in GT SV translation (substring or exact match)."""
    if not candidate or not gt_sv:
        return False
    c = candidate.lower().strip()
    g = gt_sv.lower().strip()
    return c == g or c in g.split() or c in g


def confidence_tag(has_folkets: bool, gt_agrees: bool, claude_agrees: bool,
                   apert_agrees: bool) -> str:
    agrees = sum([gt_agrees, claude_agrees, apert_agrees])
    if has_folkets and agrees == 3:
        return "4sources"
    if has_folkets and gt_agrees and claude_agrees:
        return "3sources"
    if has_folkets and gt_agrees and apert_agrees:
        return "folkets+gt+apert"
    if has_folkets and claude_agrees and apert_agrees:
        return "folkets+claude+apert"
    if has_folkets and gt_agrees:
        return "folkets+gt"
    if has_folkets and claude_agrees:
        return "folkets+claude"
    if has_folkets and apert_agrees:
        return "folkets+apert"
    if has_folkets:
        return "folkets_only"
    if gt_agrees and claude_agrees:
        return "gt+claude"
    if gt_agrees:
        return "gt_only"
    if claude_agrees:
        return "claude_only"
    return "none"


def main():
    # Load EN base
    enfi = json.load(open(EN_FI_FILE))
    # Sort by rank for ordering (rank field is on each entry)
    enfi_by_rank = sorted(enfi, key=lambda e: e.get("rank", 9999))
    en_keys = [e["en"] for e in enfi_by_rank if isinstance(e.get("en"), str)]
    en_to_rank = {e["en"]: e.get("rank", 9999) for e in enfi if isinstance(e.get("en"), str)}
    print(f"EN base: {len(en_keys):,} keys from {EN_FI_FILE}")

    # Load Swedish frequency list (for GT-only quality override)
    sv_freq = load_sv_freq(FREQ_FILE)
    print(f"SV freq list: {len(sv_freq):,} words" if sv_freq else "SV freq list: not found (GT-freq override disabled)")

    # Load Folkets
    if not os.path.exists(FOLKETS_FILE):
        print(f"ERROR: {FOLKETS_FILE} not found. Run 31_download_folkets.py first.")
        sys.exit(1)
    folkets = load_folkets_en_sv(FOLKETS_FILE)

    # Load GT checkpoint
    gt_cache = load_jsonl_cache(GT_CHECKPOINT, "en")
    print(f"GT cache: {len(gt_cache):,} entries already done")

    # Load Claude translations
    claude_cache: dict[str, str] = {}
    if os.path.exists(CLAUDE_FILE):
        with open(CLAUDE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    en = rec.get("en", "").lower().strip()
                    sv = rec.get("sv", "").lower().strip()
                    if en and sv:
                        claude_cache[en] = sv
                except json.JSONDecodeError:
                    pass
        print(f"Claude cache: {len(claude_cache):,} entries")
    else:
        print(f"Claude cache: not found ({CLAUDE_FILE})")

    # Load Apertium EN→SV lookup (cautious 4th source)
    apertium_cache: dict[str, list[str]] = {}
    if os.path.exists(APERTIUM_FILE):
        with open(APERTIUM_FILE, encoding="utf-8") as f:
            apertium_cache = json.load(f)
        print(f"Apertium cache: {len(apertium_cache):,} EN entries")
    else:
        print(f"Apertium cache: not found ({APERTIUM_FILE})")

    # Run GT for EN keys not yet cached
    from utils import gt
    todo_gt = [en for en in en_keys if en not in gt_cache]
    if todo_gt:
        print(f"\nRunning GT EN→SV for {len(todo_gt):,} keys …")
        with open(GT_CHECKPOINT, "a") as ckpt:
            for i, en in enumerate(todo_gt):
                sv_gt = gt(en, sl="en", tl="sv")
                rec = {"en": en, "sv_gt": sv_gt or ""}
                ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                ckpt.flush()
                gt_cache[en] = rec
                if (i + 1) % 100 == 0:
                    print(f"  GT: {i+1}/{len(todo_gt)} done")
                time.sleep(GT_DELAY)
        print(f"  GT done: {len(todo_gt):,} calls")

    # Build output
    results = []
    stats: dict[str, int] = {"total": len(en_keys), "has_folkets": 0,
                              "gt_agrees": 0, "claude_agrees": 0, "apert_agrees": 0}

    for en in en_keys:
        en_norm = en.lower().strip()
        # Strip "to " prefix for Folkets lookup (verb forms stored as "run" not "to run")
        folkets_key = en_norm
        if folkets_key.startswith("to "):
            folkets_key = folkets_key[3:]

        # Filter Folkets to lemmas only (drop example sentences), cap at 3
        raw_folkets = folkets.get(folkets_key, [])
        folkets_svs = [sv for sv in raw_folkets if is_lemma(sv)][:3]
        has_folkets = bool(folkets_svs)
        if has_folkets:
            stats["has_folkets"] += 1

        gt_rec = gt_cache.get(en, {})
        sv_gt = gt_rec.get("sv_gt", "") if isinstance(gt_rec, dict) else ""

        claude_sv = claude_cache.get(en_norm, "")

        apert_svs = apertium_cache.get(en_norm, [])
        apert_sv_primary = apert_svs[0] if apert_svs else ""

        # Determine primary SV translation
        if has_folkets:
            primary_sv = folkets_svs[0]
            sv_all = folkets_svs
            # Consensus override: if 2+ secondary sources agree on a different word, prefer it
            override = consensus_override(primary_sv, sv_gt, claude_sv, apert_sv_primary)
            if override:
                primary_sv = override
                sv_all = [override]
                stats["consensus_overridden"] = stats.get("consensus_overridden", 0) + 1
            # GT-frequency override: if primary is absent/rare AND GT's root verb is significantly
            # more common, prefer GT (fixes Folkets archaic/wrong primary cases, handles phrasal verbs)
            elif sv_gt and sv_freq:
                prim_n = _norm(primary_sv).rstrip("!-").strip()
                gt_n = _norm(sv_gt).rstrip("!-").strip()
                gt_root = gt_n.split()[0] if gt_n else ""  # handle residual multi-word
                if gt_root and ' ' not in prim_n:
                    prim_rank = sv_freq.get(prim_n, 99999)
                    gt_rank = sv_freq.get(gt_root, 99999)
                    if prim_rank > GT_FREQ_THRESHOLD and gt_rank * GT_FREQ_RATIO < prim_rank:
                        # Store clean form: reconstruct "att X" for verb entries
                        if sv_gt.startswith("att ") and gt_root != gt_n:
                            stored = "att " + gt_root
                        elif sv_gt.startswith("att "):
                            stored = sv_gt
                        else:
                            stored = gt_root
                        primary_sv = stored
                        sv_all = [stored]
                        stats["gt_freq_overridden"] = stats.get("gt_freq_overridden", 0) + 1
            # GT-in-secondary promotion: if GT matches a Folkets secondary (not primary), promote it
            if sv_gt and len(folkets_svs) > 1 and primary_sv == folkets_svs[0]:
                gt_n = _norm(sv_gt)
                folkets_secondaries_norm = [_norm(s) for s in folkets_svs[1:]]
                if gt_n in folkets_secondaries_norm and gt_n != _norm(primary_sv):
                    idx = folkets_secondaries_norm.index(gt_n)
                    promoted = folkets_svs[1 + idx]
                    primary_sv = promoted
                    sv_all = [promoted] + [s for s in folkets_svs if s != promoted][:2]
                    stats["gt_secondary_promoted"] = stats.get("gt_secondary_promoted", 0) + 1
        elif apert_sv_primary:
            primary_sv = apert_sv_primary
            sv_all = apert_svs[:2]
        elif sv_gt:
            primary_sv = sv_gt
            sv_all = [sv_gt]
        elif claude_sv:
            primary_sv = claude_sv
            sv_all = [claude_sv]
        else:
            continue  # no translation found at all

        gt_agrees = sv_matches(primary_sv, sv_gt)
        claude_agrees = sv_matches(primary_sv, claude_sv)
        apert_agrees = has_folkets and bool(apert_svs) and sv_matches(primary_sv, apert_sv_primary)

        if gt_agrees:
            stats["gt_agrees"] += 1
        if claude_agrees:
            stats["claude_agrees"] += 1
        if apert_agrees:
            stats["apert_agrees"] += 1

        tag = confidence_tag(has_folkets, gt_agrees, claude_agrees, apert_agrees)
        stats[tag] = stats.get(tag, 0) + 1

        entry = {
            "en": en,
            "sv": sv_all if len(sv_all) > 1 else primary_sv,
            "rank": en_to_rank.get(en, 9999),
            "confidence": tag,
        }
        if sv_gt and sv_gt != primary_sv:
            entry["sv_gt"] = sv_gt
        if claude_sv and claude_sv != primary_sv:
            entry["sv_claude"] = claude_sv
        if apert_sv_primary and apert_sv_primary != primary_sv:
            entry["sv_apert"] = apert_sv_primary
        results.append(entry)

    print(f"\n--- Coverage stats ---")
    print(f"Total EN keys:              {stats['total']:>6}")
    print(f"Has Folkets match:          {stats['has_folkets']:>6}  ({stats['has_folkets']/stats['total']*100:.1f}%)")
    print(f"GT agrees with primary:     {stats['gt_agrees']:>6}")
    print(f"Claude agrees with primary: {stats['claude_agrees']:>6}")
    print(f"Apertium agrees w/ primary: {stats['apert_agrees']:>6}")
    print(f"Consensus override applied: {stats.get('consensus_overridden',0):>6}")
    print(f"GT-secondary promotion:     {stats.get('gt_secondary_promoted',0):>6}")
    print(f"GT-frequency override:      {stats.get('gt_freq_overridden',0):>6}")
    print(f"4-source agreement:         {stats.get('4sources',0):>6}")
    print(f"3-source agreement:         {stats.get('3sources',0):>6}")
    no_match = stats["total"] - len(results)
    print(f"No match at all:            {no_match:>6}")
    print(f"Total emitted:              {len(results):>6}")

    # Sort by rank for final output
    results.sort(key=lambda e: e["rank"])

    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT_FILE} ({len(results):,} entries)")

    # Write review sample
    write_review_sample(results, en_to_rank)


def write_review_sample(results: list, en_to_rank: dict):
    """Write 50 sampled entries across rank buckets to SAMPLE_FILE."""
    rank_buckets = [
        ("top_100", [r for r in results if r["rank"] <= 100]),
        ("100_500", [r for r in results if 100 < r["rank"] <= 500]),
        ("500_2000", [r for r in results if 500 < r["rank"] <= 2000]),
        ("2000_plus", [r for r in results if r["rank"] > 2000]),
    ]

    sample = []
    targets = [13, 13, 13, 11]  # ~50 total
    for (label, bucket), n in zip(rank_buckets, targets):
        picked = random.sample(bucket, min(n, len(bucket)))
        for p in picked:
            p["_bucket"] = label
        sample.extend(picked)

    sample.sort(key=lambda e: e["rank"])

    with open(SAMPLE_FILE, "w", encoding="utf-8") as f:
        f.write("# EN→SV Review Sample (50 entries)\n\n")
        f.write("Spot-check: mark wrong translations with `~~strikethrough~~`.\n\n")
        f.write("| EN | SV (primary) | rank | confidence | GT | Claude | Apertium |\n")
        f.write("|----|----|----|----|----|----|----|---|\n")
        for e in sample:
            sv = e["sv"]
            if isinstance(sv, list):
                sv_str = " / ".join(sv[:3])
            else:
                sv_str = sv
            gt_col = e.get("sv_gt", "—")
            claude_col = e.get("sv_claude", "—")
            apert_col = e.get("sv_apert", "—")
            f.write(f"| `{e['en']}` | {sv_str} | {e['rank']} | {e['confidence']} | {gt_col} | {claude_col} | {apert_col} |\n")

    print(f"Wrote {SAMPLE_FILE} ({len(sample)} entries)")


if __name__ == "__main__":
    main()
