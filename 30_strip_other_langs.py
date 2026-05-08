#!/usr/bin/env python3
"""
30_strip_other_langs.py

Drop sv/it/fr/de columns from data.json. The thin (8–14%) coverage of those
columns wasn't backed by a quality pipeline; multilingual support is being
rebuilt as per-pair files (en_X.json + X_en.json) anchored on EN with
locally authoritative sources, starting with Swedish.

EN↔FI fields (fi, en, fi_rank, pos) are untouched. Idempotent.
"""

import json

from utils import atomic_write_json

DATA_FILE = "data.json"
DROP = ("sv", "it", "fr", "de")


def main():
    data = json.load(open(DATA_FILE))
    touched = 0
    for entry in data:
        any_dropped = False
        for k in DROP:
            if k in entry:
                del entry[k]
                any_dropped = True
        if any_dropped:
            touched += 1

    if touched == 0:
        print(f"No changes — {len(data)} entries already clean.")
        return

    atomic_write_json(DATA_FILE, data)
    print(f"Stripped {DROP} from {touched} of {len(data)} entries.")


if __name__ == "__main__":
    main()
