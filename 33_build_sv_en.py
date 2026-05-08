#!/usr/bin/env python3
"""
33_build_sv_en.py

Build sv_en.json from en_sv.json (reverse view).
Mirrors the logic of 14_build_en_fi.py:
  - Primary EN (lowest rank) wins the top slot.
  - Secondary ENs get rank+5000 penalty.
  - Top-3 ENs per SV kept.
  - Single-item lists are unwrapped to a string.

Run: python3 33_build_sv_en.py
Reads en_sv.json. Writes sv_en.json.
"""

import json

EN_SV_FILE = "en_sv.json"
OUTPUT_FILE = "sv_en.json"


def main():
    data = json.load(open(EN_SV_FILE, encoding="utf-8"))
    print(f"Loaded {len(data):,} entries from {EN_SV_FILE}")

    # Build SV → [(rank, en, is_primary)] mapping
    sv_to_entries: dict[str, list] = {}

    for entry in data:
        en = entry["en"]
        rank = entry.get("rank", 9999)
        sv_val = entry.get("sv")

        if not sv_val:
            continue

        raw_sv = sv_val if isinstance(sv_val, list) else [sv_val]
        # Only use the primary SV (first) as a reverse key — don't explode secondaries
        sv_list = raw_sv[:1]
        for i, sv in enumerate(sv_list):
            sv = sv.lower().strip()
            if not sv:
                continue
            # Primary SV (index 0) uses original rank; secondaries get +5000 penalty
            eff_rank = rank if i == 0 else rank + 5000
            if sv not in sv_to_entries:
                sv_to_entries[sv] = []
            sv_to_entries[sv].append((eff_rank, en))

    # Build output: for each SV, top-3 ENs by effective rank
    results = []
    for sv, entries in sv_to_entries.items():
        entries.sort(key=lambda x: x[0])
        top = entries[:3]
        en_list = [e[1] for e in top]
        best_rank = top[0][0]  # primary rank (no penalty)

        results.append({
            "sv": sv,
            "en": en_list[0] if len(en_list) == 1 else en_list,
            "rank": best_rank,
        })

    # Sort by rank ascending (most common SV words first)
    results.sort(key=lambda e: e["rank"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    multi = sum(1 for r in results if isinstance(r["en"], list))
    print(f"Wrote {OUTPUT_FILE}: {len(results):,} SV entries")
    print(f"  Single EN: {len(results)-multi:,}  Multi-EN: {multi:,}")


if __name__ == "__main__":
    main()
