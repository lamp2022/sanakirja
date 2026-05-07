#!/usr/bin/env python3
"""
Step 08: Validate fixture.json completeness and integrity.
Run: python3 08_curate_fixture.py
"""
import json, sys
from pathlib import Path

FIXTURE_FILE = Path(__file__).parent / "fixture.json"
REQUIRED_KEYS = {"fi", "fi_pos", "en", "sv", "it", "fr", "de", "fi_rank"}
VALID_POS = {"noun", "verb", "adj", "adv", "pron", "conj", "particle", "num", "intj", "det"}


def validate_fixture(entries):
    errors = []
    seen = {}
    for i, entry in enumerate(entries):
        label = f"entry[{i}] fi={entry.get('fi', '?')}"
        missing = REQUIRED_KEYS - set(entry.keys())
        if missing:
            errors.append(f"{label}: missing keys: {missing}")
        for k in REQUIRED_KEYS - {"fi_rank"}:
            if entry.get(k) == "":
                errors.append(f"{label}: empty string for '{k}'")
        rank = entry.get("fi_rank")
        if not isinstance(rank, int) or rank <= 0:
            errors.append(f"{label}: fi_rank must be a positive int, got {rank!r}")
        pos = entry.get("fi_pos", "")
        if pos not in VALID_POS:
            errors.append(f"{label}: invalid fi_pos '{pos}'")
        key = (entry.get("fi"), entry.get("fi_pos"))
        if key in seen:
            errors.append(f"{label}: duplicate (fi, fi_pos) — also at entry[{seen[key]}]")
        else:
            seen[key] = i
    return errors


def main():
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture = json.load(f)

    errors = validate_fixture(fixture)

    if errors:
        print(f"FIXTURE INVALID — {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"fixture.json OK — {len(fixture)} entries, all valid.")


if __name__ == "__main__":
    main()
