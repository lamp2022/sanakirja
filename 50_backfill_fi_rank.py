#!/usr/bin/env python3
"""
50_backfill_fi_rank.py

Populate fi_rank in data.json for entries missing it.
Uses en_fi_data.json as the rank source (keyed by FI word, minimum rank wins).

Run: python3 50_backfill_fi_rank.py
"""

import json
import subprocess
import sys
from utils import atomic_write_json

EN_FI_FILE = "en_fi_data.json"
DATA_FILE = "data.json"
FALLBACK_RANK = 9999


def build_fi_rank_map(en_fi: list) -> dict:
    """Build {fi_word: rank} from en_fi_data.json. Handles list fi values."""
    rank_map = {}
    for entry in en_fi:
        rank = entry.get("rank", FALLBACK_RANK)
        fi_val = entry.get("fi")
        if not fi_val:
            continue
        fi_words = fi_val if isinstance(fi_val, list) else [fi_val]
        for word in fi_words:
            if word not in rank_map or rank < rank_map[word]:
                rank_map[word] = rank
    return rank_map


def main():
    en_fi = json.load(open(EN_FI_FILE, encoding="utf-8"))
    data = json.load(open(DATA_FILE, encoding="utf-8"))

    rank_map = build_fi_rank_map(en_fi)
    print(f"Rank map built: {len(rank_map):,} FI words")

    filled = 0
    defaulted = 0
    already_had = 0

    for entry in data:
        if entry.get("fi_rank") is not None:
            already_had += 1
            continue
        fi_word = entry.get("fi", "")
        if fi_word in rank_map:
            entry["fi_rank"] = rank_map[fi_word]
            filled += 1
        else:
            entry["fi_rank"] = FALLBACK_RANK
            defaulted += 1

    print(f"Already had fi_rank : {already_had:,}")
    print(f"Filled from map     : {filled:,}")
    print(f"Defaulted to {FALLBACK_RANK}  : {defaulted:,}")

    atomic_write_json(DATA_FILE, data)
    print(f"Written {DATA_FILE}")

    result = subprocess.run(
        [sys.executable, "12_validate_output.py"],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
