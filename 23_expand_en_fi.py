#!/usr/bin/env python3
"""
23_expand_en_fi.py

Walks single-sense EN entries in en_fi_data.json, reverse-indexes the four
FI→EN source caches, and adds a Finnish secondary translation when at least
4 of 4 content sources agree. Cross-POS candidates are gated: if the EN
entry is a verb form ("to X"), the candidate FI must also be a verb (per
data.json/kaikki/jukka POS info) — kills false positives like "to mark→markka".

Side effect: appends EN word to candidate FI's `en` list in data.json. Run
14_build_en_fi.py afterwards to refresh en_fi_data.json from data.json.

Sources (reverse-indexed EN→{fi}):
  1. kaikki Wiktionary cache          (kaikki_glosses_checkpoint.json)
  2. Jukka enriched dictionary         (jukka_enriched.csv)
  3. Apertium FI-EN dump               (apertium_fin_eng.json)
  4. Wiktionary FI definitions         (wikt_fi_definitions.jsonl)
  5. Google Translate cross-check      (gt_check_results.json) — validation only

Idempotent: re-running on already-applied data is a no-op.
"""

import csv
import json
import os
import re
from collections import defaultdict, Counter
from utils import atomic_write_json

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
KAIKKI = os.path.join(SOURCES_DIR, "kaikki_glosses_checkpoint.json")
JUKKA = os.path.join(SOURCES_DIR, "jukka_enriched.csv")
APERTIUM = os.path.join(SOURCES_DIR, "apertium_fin_eng.json")
WIKT = os.path.join(SOURCES_DIR, "wikt_fi_definitions.jsonl")
GT = os.path.join(SOURCES_DIR, "gt_check_results.json")
RANK_FILE = os.path.join(SOURCES_DIR, "fi_top.csv")

# Map jukka kotus_class strings → coarse POS bucket
JUKKA_POS = {
    "verbi": "verb",
    "substantiivi": "noun",
    "adjektiivi": "adj",
    "adverbi": "adv",
    "pronomini": "pron",
    "lukusana": "num",
    "konjunktio": "conj",
    "interjektio": "intj",
    "partikkeli": "part",
    "postpositio": "adp",
    "prepositio": "adp",
}

MIN_AGREEMENT = 4   # require all 4 content sources to agree (high precision)
RANK_LIMIT = 3000


def norm(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"^(a |an |to )", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def load_rank(path):
    rank = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            rank[row["lemma"]] = int(row["rank"])
    return rank


def split_glosses(s):
    """Jukka and wikt sometimes pack multiple senses into one string with
    commas or semicolons. Split conservatively."""
    if not s:
        return []
    parts = re.split(r"[;,]", s)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # drop parenthetical qualifiers
        p = re.sub(r"\s*\([^)]*\)\s*", " ", p).strip()
        if p:
            out.append(p)
    return out


def reverse_kaikki(path):
    """kaikki_glosses_checkpoint.json: { 'fi|pos': [en, en, ...] } → en→{fi}
    Also returns kaikki_pos: fi → set(pos)."""
    rev = defaultdict(set)
    pos_idx = defaultdict(set)
    d = json.load(open(path))
    for key, glosses in d.items():
        parts = key.split("|")
        fi = parts[0]
        pos = parts[1] if len(parts) > 1 else ""
        if pos:
            pos_idx[fi].add(pos)
        for g in glosses:
            for piece in split_glosses(g):
                if piece.startswith("synonym of"):
                    continue
                rev[norm(piece)].add(fi)
    return rev, pos_idx


def reverse_jukka(path):
    """jukka_enriched.csv: fi,en,kotus_class → en→{fi}
    Also returns jukka_pos: fi → pos."""
    rev = defaultdict(set)
    pos_idx = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            fi = row["fi"]
            kc = row.get("kotus_class", "").strip()
            if kc and fi not in pos_idx:
                p = JUKKA_POS.get(kc)
                if p:
                    pos_idx[fi] = p
            for piece in split_glosses(row["en"]):
                rev[norm(piece)].add(fi)
    return rev, pos_idx


def reverse_apertium(path):
    """apertium_fin_eng.json: { fi: [en, en, ...] } → en→{fi}"""
    rev = defaultdict(set)
    d = json.load(open(path))
    for fi, ens in d.items():
        if isinstance(ens, list):
            for en in ens:
                rev[norm(en)].add(fi)
    return rev


def reverse_wikt(path):
    """wikt_fi_definitions.jsonl: { fi, defs_by_pos: {pos: [defs...]} } → en→{fi}"""
    rev = defaultdict(set)
    NOISY = re.compile(r"\{\{|^[A-Z]+$|^used |^the |^a |^an ")
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            fi = d.get("fi")
            if not fi or not d.get("found"):
                continue
            defs = d.get("defs_by_pos", {})
            for pos, glosses in defs.items():
                for g in glosses:
                    # skip wiki-template noise
                    if "{{" in g or "}}" in g:
                        continue
                    for piece in split_glosses(g):
                        # very short, very long, all-caps → skip
                        if len(piece) < 2 or len(piece) > 40:
                            continue
                        if piece.isupper():
                            continue
                        rev[norm(piece)].add(fi)
    return rev


def reverse_gt(path):
    """gt_check_results.json: list of {fi, en_gt} → en→{fi} (validation source)"""
    rev = defaultdict(set)
    d = json.load(open(path))
    for entry in d:
        fi = entry.get("fi")
        en_gt = entry.get("en_gt", "")
        if fi and en_gt:
            for piece in split_glosses(en_gt):
                rev[norm(piece)].add(fi)
    return rev


def main():
    print("Loading en_fi_data.json…")
    enfi = json.load(open(EN_FI_FILE))
    print(f"  {len(enfi)} entries")

    print("Loading data.json (canonical POS)…")
    data = json.load(open(DATA_FILE))
    data_pos = {e["fi"]: (e.get("pos") or "").lower() for e in data if e.get("fi")}
    print(f"  {len(data_pos)} fi lemmas with POS")

    print("Loading rank…")
    rank = load_rank(RANK_FILE)

    print("Reverse-indexing sources…")
    kaikki, kaikki_pos = reverse_kaikki(KAIKKI)
    print(f"  kaikki:   {len(kaikki):>6} EN keys, {len(kaikki_pos)} fi w/ POS")
    jukka, jukka_pos = reverse_jukka(JUKKA)
    print(f"  jukka:    {len(jukka):>6} EN keys, {len(jukka_pos)} fi w/ POS")
    apert = reverse_apertium(APERTIUM)
    print(f"  apertium: {len(apert):>6} EN keys")
    wikt = reverse_wikt(WIKT)
    print(f"  wikt:     {len(wikt):>6} EN keys")
    gt = reverse_gt(GT)
    print(f"  gt:       {len(gt):>6} EN keys (validation only)")
    print()

    sources = [("kaikki", kaikki), ("jukka", jukka), ("apertium", apert),
               ("wikt", wikt), ("gt", gt)]

    def lookup_pos(fi):
        """Layered POS lookup: data.json first (canonical), then kaikki, then jukka."""
        p = data_pos.get(fi)
        if p:
            return p
        ks = kaikki_pos.get(fi)
        if ks:
            # prefer 'verb' if present, else any
            return "verb" if "verb" in ks else next(iter(ks))
        return jukka_pos.get(fi)

    rejected_pos = 0
    # Walk single-sense EN entries
    candidates = []  # (score, gt_confirms, en, primary_fi, fi_candidate, src_set)
    for entry in enfi:
        fi_val = entry["fi"]
        if isinstance(fi_val, list):
            continue  # already multi-sense
        primary_fi = fi_val
        en = entry["en"]
        en_is_verb = en.lower().startswith("to ")
        en_n = norm(en)

        # gather candidate FI lemmas across the four content sources
        fi_votes = defaultdict(set)  # fi_lemma -> {source_name}
        for src_name, src in [("kaikki", kaikki), ("jukka", jukka),
                              ("apertium", apert), ("wikt", wikt)]:
            for fi_cand in src.get(en_n, ()):
                fi_votes[fi_cand].add(src_name)

        for fi_cand, srcs in fi_votes.items():
            if fi_cand == primary_fi:
                continue
            # Frequency gate: candidate must be a known lemma (top 3000 ish)
            r = rank.get(fi_cand, 99999)
            if r > RANK_LIMIT:
                continue
            score = len(srcs)
            if score < MIN_AGREEMENT:
                continue
            # POS gate: if EN is "to X" (verb), candidate must be a verb.
            # If candidate POS is unknown, reject conservatively.
            if en_is_verb:
                cand_pos = lookup_pos(fi_cand)
                if cand_pos != "verb":
                    rejected_pos += 1
                    continue
            gt_confirms = fi_cand in gt.get(en_n, set())
            candidates.append((score, gt_confirms, en, primary_fi,
                               fi_cand, sorted(srcs), r))

    print(f"Rejected by POS filter (to-verb requires verb candidate): {rejected_pos}")
    print(f"Total candidates at {MIN_AGREEMENT}/4 source agreement: {len(candidates)}")

    # Apply: append the EN word to the candidate FI lemma's `en` list in data.json
    by_fi = {e["fi"]: e for e in data}
    added = 0
    skipped_already = 0
    skipped_missing_in_data = 0
    sample_added = []
    for c in candidates:
        en, candidate_fi = c[2], c[4]
        entry = by_fi.get(candidate_fi)
        if not entry:
            skipped_missing_in_data += 1
            continue
        cur = entry.get("en")
        cur_list = list(cur) if isinstance(cur, list) else [cur]
        if en in cur_list:
            skipped_already += 1
            continue
        cur_list.append(en)
        entry["en"] = cur_list
        added += 1
        if len(sample_added) < 10:
            sample_added.append((en, candidate_fi, cur_list))

    print()
    print(f"Applied:                       {added}")
    print(f"  candidate already had EN:    {skipped_already} (idempotent re-run)")
    print(f"  candidate FI not in data.json: {skipped_missing_in_data}")
    if sample_added:
        print("\nSample additions:")
        for en, fi, en_list in sample_added:
            print(f"  {fi:>15}.en += {en!r:<15}  → {en_list}")

    if added > 0:
        print("\nWriting data.json atomically…")
        atomic_write_json(DATA_FILE, data)
        print("Done. Now run 14_build_en_fi.py to refresh en_fi_data.json.")
    else:
        print("\nNo changes to write (idempotent re-run on already-applied data).")

    # Always refresh the review file for transparency
    review_path = "EN_FI_REVIEW_4of4.md"
    full4 = sorted(candidates, key=lambda t: (-int(t[1]), t[6]))
    with open(review_path, "w") as f:
        f.write("# EN→FI 4/4 Source-Agreement Candidates\n\n")
        f.write(f"Total: {len(full4)} candidates\n")
        f.write(f"GT-confirmed: {sum(1 for c in full4 if c[1])}\n\n")
        f.write("| GT | EN | primary FI | new FI sense | rank | sources |\n")
        f.write("|----|----|-----------|--------------|------|---------|\n")
        for c in full4:
            score, gt_ok, en, primary, cand, srcs, r = c
            gt_mark = "✓" if gt_ok else " "
            f.write(f"| {gt_mark} | `{en}` | `{primary}` | **`{cand}`** "
                    f"| {r} | {','.join(srcs)} |\n")


if __name__ == "__main__":
    main()
