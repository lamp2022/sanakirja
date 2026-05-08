#!/usr/bin/env python3
"""
27_apply_tier_d_bidir.py

Apply the Tier D candidates that 26_gt_bidir.py promoted via bidirectional
GT confirmation. Same append mechanic as 23/25. Idempotent.

Run 14_build_en_fi.py afterwards to refresh en_fi_data.json.
"""

import json
import os
import sys
from utils import atomic_write_json

DATA_FILE = "data.json"
PROMOTED_FILE = "tier_d_promoted.json"

# Per-pair reject list. Empty unless user flags borderline cases.
REJECT = set()


def main():
    if not os.path.exists(PROMOTED_FILE):
        sys.exit(f"Missing {PROMOTED_FILE} — run 26_gt_bidir.py first.")

    promoted = json.load(open(PROMOTED_FILE))
    promoted = [c for c in promoted
                if (c["en"], c["candidate_fi"]) not in REJECT]
    print(f"Applying {len(promoted)} bidirectionally-confirmed Tier D candidates")

    data = json.load(open(DATA_FILE))
    by_fi = {e["fi"]: e for e in data}

    added = skipped_already = skipped_missing = 0
    sample = []
    for c in promoted:
        en, candidate_fi = c["en"], c["candidate_fi"]
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
