#!/usr/bin/env python3
"""
Step 09: Build FI<->EN candidate pairs from per-language kaikki data.

Reads fi_top.csv, sv_top.csv, it_top.csv, fr_top.csv (already extracted by 06).
Streams kaikki_finnish.jsonl once to build a reverse EN->FI index.
Outputs: fi_en_batch_01.json, fi_en_batch_02.json, ... (100 rows each)

Each row: {id, fi, fi_pos, en, confidence, source_lang, source_lemma, fi_rank}
"""
import csv, json, os, re
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos

FI_KAIKKI   = "kaikki_finnish.jsonl"
CSC_FILE    = "csc_9996.csv"
FIXTURE_FILE = "fixture.json"
BATCH_SIZE  = 100
LANGS = [
    ("fi", "fi_top.csv"),
    ("sv", "sv_top.csv"),
    ("it", "it_top.csv"),
    ("fr", "fr_top.csv"),
]


def load_csc_ranks():
    ranks = {}
    with open(CSC_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            l, rk = r["lemma"], int(r["rank"])
            if l not in ranks or rk < ranks[l]:
                ranks[l] = rk
    return ranks


def load_fixture_lemmas():
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        return {e["fi"] for e in json.load(f)}


def build_fi_kaikki_index(csc_ranks):
    """Stream kaikki_finnish.jsonl, build:
      fi_idx:    {en_token_lower: [(fi_lemma, fi_pos, csc_rank)]} sorted rank asc
      fi_to_en:  {fi_lemma: set(en_token_lower)} for bidirectional check
    """
    print("Building FI kaikki reverse index (streaming 3.6 GB — ~3 min)...")
    fi_idx = defaultdict(list)
    fi_to_en = defaultdict(set)
    seen = set()
    count = 0

    with open(FI_KAIKKI, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            pos = e.get("pos", "")
            if not is_content_pos(pos):
                continue
            word = e.get("word", "").strip()
            if not word or not re.match(r"^[a-zäöåA-ZÄÖÅ\-']+$", word):
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
            key = (word, pos_norm)
            if key not in seen:
                seen.add(key)
                fi_idx[en_token.lower()].append((word, pos_norm, csc_ranks.get(word)))
            count += 1
            if count % 100000 == 0:
                print(f"  {count:,} FI entries processed, {len(fi_idx):,} EN keys")

    for k in fi_idx:
        fi_idx[k].sort(key=lambda x: (x[2] is None, x[2] or 0))
    for en_token, candidates in fi_idx.items():
        for fi_lemma, _, _ in candidates:
            fi_to_en[fi_lemma].add(en_token)

    print(f"  Done: {len(fi_idx):,} EN keys, {len(fi_to_en):,} FI lemmas indexed")
    return dict(fi_idx), dict(fi_to_en)


def extract_source_entries(csv_path, lang_code):
    entries = []
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
            entries.append({
                "lemma": r["lemma"],
                "pos": normalize_pos(pos),
                "en": en_token,
                "rank": int(r["rank"]),
                "lang": lang_code,
            })
    return entries


def lookup_fi(en_token, pos, fi_idx):
    # Returns (fi_lemma, fi_pos_of_candidate). When POS match fails,
    # falls back to top-ranked candidate; returned fi_pos is candidate's pos, not requested pos.
    candidates = fi_idx.get(en_token.lower(), [])
    if not candidates:
        return None, None
    matched = [c for c in candidates if c[1] == pos]
    pool = matched if matched else candidates
    return pool[0][0], pool[0][1]


def bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en):
    candidates = fi_idx.get(en_token.lower(), [])
    if candidates and candidates[0][0] == fi_lemma:
        return "auto"
    if en_token.lower() in fi_to_en.get(fi_lemma, set()):
        return "review"
    return "borderline"


def main():
    csc_ranks = load_csc_ranks()
    print(f"CSC ranks: {len(csc_ranks):,} lemmas")

    fixture_lemmas = load_fixture_lemmas()
    print(f"Fixture: {len(fixture_lemmas)} lemmas to skip")

    fi_idx, fi_to_en = build_fi_kaikki_index(csc_ranks)

    master = {}  # (fi_lemma, fi_pos) -> best entry
    conf_order = {"auto": 0, "review": 1, "borderline": 2}

    for lang_code, csv_path in LANGS:
        print(f"\nProcessing {lang_code} ({csv_path})...")
        entries = extract_source_entries(csv_path, lang_code)
        print(f"  {len(entries):,} content-word entries")

        for e in entries:
            if lang_code == "fi":
                fi_lemma, fi_pos = e["lemma"], e["pos"]
                en_token, source_lemma = e["en"], fi_lemma
            else:
                fi_lemma, fi_pos = lookup_fi(e["en"], e["pos"], fi_idx)
                if not fi_lemma:
                    continue
                en_token, source_lemma = e["en"], e["lemma"]

            if fi_lemma in fixture_lemmas:
                continue

            key = (fi_lemma, fi_pos)
            confidence = bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en)
            fi_rank = csc_ranks.get(fi_lemma)

            if key not in master:
                master[key] = {
                    "fi": fi_lemma, "fi_pos": fi_pos, "en": en_token,
                    "confidence": confidence, "source_lang": lang_code,
                    "source_lemma": source_lemma, "fi_rank": fi_rank,
                }
            else:
                existing = master[key]
                if conf_order[confidence] < conf_order[existing["confidence"]]:
                    master[key].update({
                        "en": en_token, "confidence": confidence,
                        "source_lang": lang_code, "source_lemma": source_lemma,
                    })

    rows = sorted(master.values(),
                  key=lambda r: (r["fi_rank"] is None, r["fi_rank"] or 0, r["fi"]))
    for i, row in enumerate(rows, 1):
        row["id"] = i

    total = len(rows)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nTotal pairs: {total:,} → {num_batches} batches of {BATCH_SIZE}")

    batch_conf_order = {"borderline": 0, "review": 1, "auto": 2}
    for b in range(num_batches):
        batch_rows = sorted(rows[b * BATCH_SIZE:(b + 1) * BATCH_SIZE],
                            key=lambda r: batch_conf_order[r["confidence"]])
        out_file = f"fi_en_batch_{b + 1:02d}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(batch_rows, f, ensure_ascii=False, indent=2)
        auto = sum(1 for r in batch_rows if r["confidence"] == "auto")
        review = sum(1 for r in batch_rows if r["confidence"] == "review")
        border = sum(1 for r in batch_rows if r["confidence"] == "borderline")
        print(f"  {out_file}: auto={auto} review={review} borderline={border}")

    print(f"\nDone. Run: python3 10_qc_server.py 1")


if __name__ == "__main__":
    main()
