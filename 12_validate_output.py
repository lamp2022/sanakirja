#!/usr/bin/env python3
"""
Step 12: Validate data.json for quality and completeness.
Run: python3 12_validate_output.py
Exits 0 on success, 1 on failure.
"""
import json, re, sys

OUTPUT       = "data.json"
MIN_ROWS     = 1000
MAX_ROWS     = 5000

SKIP_PATTERNS = [
    r"inflection of", r"plural of", r"past participle",
    r"third.person", r"first.person", r"second.person",
    r"alternative form of", r"obsolete form of",
    r"definite singular", r"definite plural",
]


def main():
    with open(OUTPUT, encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    seen_fi = {}

    for i, row in enumerate(data):
        label = f"row[{i}] fi={row.get('fi', '?')}"

        if "fi" not in row or not row["fi"]:
            errors.append(f"{label}: missing fi")
        if "en" not in row or not row["en"]:
            errors.append(f"{label}: missing en")

        for k, v in row.items():
            if v == "":
                errors.append(f"{label}: empty string for '{k}' (omit key instead)")
            if isinstance(v, str):
                for pat in SKIP_PATTERNS:
                    if re.search(pat, v, re.IGNORECASE):
                        errors.append(f"{label}: '{k}' contains skip pattern: {v[:60]}")

        fi = row.get("fi")
        if fi:
            if fi in seen_fi:
                errors.append(f"{label}: duplicate fi lemma (first at row {seen_fi[fi]})")
            else:
                seen_fi[fi] = i

    if len(data) < MIN_ROWS:
        errors.append(f"Too few rows: {len(data)} (expected >= {MIN_ROWS})")
    if len(data) > MAX_ROWS:
        errors.append(f"Too many rows: {len(data)} (expected <= {MAX_ROWS})")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors[:50]:
            print(f"  {e}")
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        sys.exit(1)
    else:
        per_lang = {l: sum(1 for r in data if l in r) for l in ("en","sv","it","fr","de")}
        print(f"VALIDATION PASSED — {len(data):,} rows")
        print(f"  Coverage: {per_lang}")
        sys.exit(0)


if __name__ == "__main__":
    main()
