#!/usr/bin/env python3
"""
22_expand_meanings.py

Expand single-sense entries in data.json to 2-3 senses where ≥2 of 4
independent sources agree on a candidate secondary/tertiary English gloss.

Sources:
  1. kaikki Wiktionary cache  (kaikki_glosses_checkpoint.json)
  2. Jukka enriched dictionary (jukka_enriched.csv)
  3. GT cross-check record    (gt_check_results.json)
  4. Wiktionary FI definitions (wikt_fi_definitions.jsonl)

Gating:
  - lemma must rank ≤ 3000 in fi_top.csv
  - lemma's POS must be content (noun/verb/adj/adv)
  - candidate must pass utils.should_skip_gloss
  - candidate must not normalize to existing primary
  - source POS must match entry POS where available
  - hard cap of 3 total senses per entry

Idempotent: re-running on already-expanded data is a no-op.
"""

import csv
import json
import os
import re
from collections import Counter
from utils import (atomic_write_json, first_gloss_first_token,
                   should_skip_gloss, normalize_pos, is_content_pos)

# Inputs live in the user's local working folder, sibling to sanakirja-clone
SOURCES_DIR = "../sanakirja"
DATA_FILE = "data.json"
RANK_FILE = os.path.join(SOURCES_DIR, "fi_top.csv")
KAIKKI_CACHE = os.path.join(SOURCES_DIR, "kaikki_glosses_checkpoint.json")
JUKKA_FILE = os.path.join(SOURCES_DIR, "jukka_enriched.csv")
GT_FILE = os.path.join(SOURCES_DIR, "gt_check_results.json")
WIKT_FILE = os.path.join(SOURCES_DIR, "wikt_fi_definitions.jsonl")

RANK_LIMIT = 3000
MIN_SOURCE_AGREEMENT = 2
MAX_SENSES = 3


def normalize_for_dedup(s: str) -> str:
    """Lowercase, strip leading articles, collapse whitespace.
    Used to detect duplicate candidates against the existing primary."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"^(a |an )", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def is_morphological_variant(primary: str, secondary: str) -> bool:
    """True if secondary differs from primary only by a trailing morphological
    suffix (s, es, ing, ed, er, est, ?). Catches sale/sales, sometime/sometimes,
    how many / how many?, etc.
    """
    p = normalize_for_dedup(primary).rstrip("?!.")
    s = normalize_for_dedup(secondary).rstrip("?!.")
    if not p or not s or p == s:
        return p == s  # exact match also counts
    # Check both directions
    for short, long in ((p, s), (s, p)):
        if not long.startswith(short):
            continue
        suffix = long[len(short):]
        if suffix in {"", "s", "es", "ing", "ed", "er", "est", "ly"}:
            return True
    return False


def is_proper_noun_leak(primary: str, secondary: str) -> bool:
    """True if secondary looks like a proper noun (starts uppercase) while
    primary is lowercase. Catches `salo: deep forest → Salo`, `lahti: bay → Lahti`.
    """
    if not primary or not secondary:
        return False
    return secondary[0].isupper() and primary[0].islower()


def clean_candidate(raw: str, entry_pos: str):
    """Run a raw gloss through utils filtering. Returns cleaned string or None.

    Enforces POS consistency: verb entries only accept 'to X' forms, non-verb
    entries reject 'to X' forms.
    """
    if not raw:
        return None
    if should_skip_gloss(raw):
        return None
    cleaned = first_gloss_first_token(raw)
    if not cleaned:
        return None
    starts_to = cleaned.lower().startswith("to ")
    if entry_pos == "verb":
        if not starts_to:
            cleaned = "to " + cleaned
    else:
        if starts_to:
            return None
    return cleaned


def load_rank(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[row["lemma"]] = int(row["rank"])
            except (KeyError, ValueError):
                continue
    return out


def load_kaikki(path):
    """Return fi -> {pos -> [glosses]}."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for key, glosses in data.items():
        if "|" not in key:
            continue
        lemma, pos = key.split("|", 1)
        out.setdefault(lemma, {}).setdefault(normalize_pos(pos), []).extend(glosses)
    return out


def load_jukka(path):
    """Return fi -> [en, ...] (multiple rows aggregated)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fi = row.get("fi", "").strip()
            en = row.get("en", "").strip()
            if fi and en:
                out.setdefault(fi, []).append(en)
    return out


def load_gt(path):
    """Return fi -> en_gt (single string per lemma)."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for r in data:
        fi = r.get("fi")
        en_gt = r.get("en_gt")
        if fi and en_gt:
            out[fi] = en_gt
    return out


def load_wikt(path):
    """Return fi -> {pos -> [defs]}."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            fi = r.get("fi")
            defs_by_pos = r.get("defs_by_pos") or {}
            if fi and defs_by_pos:
                out[fi] = {normalize_pos(p): list(d) for p, d in defs_by_pos.items()}
    return out


def gather_candidates(fi, entry_pos, kaikki_idx, jukka_idx, gt_idx, wikt_idx):
    """Return {cleaned_word: {'norm': ..., 'sources': set(), 'tiebreak_idx': int}}.

    A source is counted at most once per cleaned candidate, regardless of how
    many raw variants it produced.
    """
    raw_by_source = {
        "kaikki": [],
        "jukka": [],
        "gt": [],
        "wikt": [],
    }

    kdata = kaikki_idx.get(fi, {})
    if entry_pos and entry_pos in kdata:
        raw_by_source["kaikki"].extend(kdata[entry_pos])

    raw_by_source["jukka"].extend(jukka_idx.get(fi, []))

    if fi in gt_idx:
        raw_by_source["gt"].append(gt_idx[fi])

    wdata = wikt_idx.get(fi, {})
    if entry_pos and entry_pos in wdata:
        raw_by_source["wikt"].extend(wdata[entry_pos])

    # Map cleaned_word -> {norm, sources, first_seen_index}
    candidates = {}
    next_idx = 0
    for src, raw_list in raw_by_source.items():
        seen_norms_in_src = set()
        for raw in raw_list:
            cleaned = clean_candidate(raw, entry_pos)
            if not cleaned:
                continue
            norm = normalize_for_dedup(cleaned)
            if not norm or norm in seen_norms_in_src:
                continue
            seen_norms_in_src.add(norm)
            existing = None
            # Merge by normalized form so 'to play' and 'to Play' aren't double-counted
            for w, info in candidates.items():
                if info["norm"] == norm:
                    existing = (w, info)
                    break
            if existing:
                existing[1]["sources"].add(src)
            else:
                candidates[cleaned] = {
                    "norm": norm,
                    "sources": {src},
                    "tiebreak_idx": next_idx,
                }
                next_idx += 1
    return candidates


def main():
    print("Loading data.json…")
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  {len(data)} entries loaded")

    print(f"Loading {RANK_FILE}…")
    rank = load_rank(RANK_FILE)
    print(f"  {len(rank)} lemmas with rank")

    print(f"Loading {KAIKKI_CACHE}…")
    kaikki = load_kaikki(KAIKKI_CACHE)
    print(f"  {len(kaikki)} kaikki entries")

    print(f"Loading {JUKKA_FILE}…")
    jukka = load_jukka(JUKKA_FILE)
    print(f"  {len(jukka)} jukka lemmas")

    print(f"Loading {GT_FILE}…")
    gt = load_gt(GT_FILE)
    print(f"  {len(gt)} GT entries")

    print(f"Loading {WIKT_FILE}…")
    wikt = load_wikt(WIKT_FILE)
    print(f"  {len(wikt)} wikt entries")

    processed = 0
    skipped_already_multi = 0
    skipped_no_rank = 0
    skipped_bad_pos = 0
    gained_2nd = 0
    gained_3rd = 0
    agreement_hist = Counter()
    samples = []

    for entry in data:
        en_val = entry.get("en")
        if isinstance(en_val, list):
            skipped_already_multi += 1
            continue
        if not en_val:
            continue
        fi = entry.get("fi")
        if not fi:
            continue
        r = rank.get(fi, 99999)
        if r > RANK_LIMIT:
            skipped_no_rank += 1
            continue
        entry_pos = normalize_pos(entry.get("pos", ""))
        if not is_content_pos(entry_pos):
            skipped_bad_pos += 1
            continue

        primary = en_val
        primary_norm = normalize_for_dedup(primary)
        candidates = gather_candidates(fi, entry_pos, kaikki, jukka, gt, wikt)

        accepted = []
        for word, info in candidates.items():
            if info["norm"] == primary_norm:
                continue
            if is_proper_noun_leak(primary, word):
                continue
            if is_morphological_variant(primary, word):
                continue
            n_sources = len(info["sources"])
            if n_sources >= MIN_SOURCE_AGREEMENT:
                accepted.append((word, info["sources"], n_sources, info["tiebreak_idx"]))

        processed += 1
        if not accepted:
            continue

        # Sort: more-agreement first, then earlier discovery, then shorter
        accepted.sort(key=lambda t: (-t[2], t[3], len(t[0])))

        new_senses = [primary]
        seen_norms = {primary_norm}
        added = 0
        for word, srcs, n, _ in accepted:
            if len(new_senses) >= MAX_SENSES:
                break
            n_form = normalize_for_dedup(word)
            if n_form in seen_norms:
                continue
            seen_norms.add(n_form)
            new_senses.append(word)
            added += 1
            agreement_hist[n] += 1

        if added == 0:
            continue

        entry["en"] = new_senses
        if added >= 1:
            gained_2nd += 1
        if added >= 2:
            gained_3rd += 1
        if len(samples) < 30:
            samples.append({
                "fi": fi, "pos": entry_pos, "rank": r,
                "before": primary, "after": new_senses,
            })

    print()
    print(f"Processed (single-sense, content POS, rank ≤ {RANK_LIMIT}): {processed}")
    print(f"  skipped already multi-sense:   {skipped_already_multi}")
    print(f"  skipped rank > {RANK_LIMIT}:           {skipped_no_rank}")
    print(f"  skipped non-content POS:       {skipped_bad_pos}")
    print(f"Gained 2nd sense: {gained_2nd}")
    print(f"Gained 3rd sense: {gained_3rd}")
    print(f"Agreement histogram (per added candidate): {dict(agreement_hist)}")

    print("\nWriting data.json atomically…")
    atomic_write_json(DATA_FILE, data)

    print("\nSample expansions:")
    for s in samples:
        print(f"  {s['fi']:<14} ({s['pos']:<4} r={s['rank']:>4})  {s['before']!r:<22} → {s['after']}")


if __name__ == "__main__":
    main()
