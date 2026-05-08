#!/usr/bin/env python3
"""
38_build_de_en.py

Build de_en.json from en_de.json (reverse view).
Mirrors 33_build_sv_en.py pattern:
- Primary DE (lowest rank EN) wins top slot
- Top-3 ENs per DE
"""

import json

EN_DE_FILE = "en_de.json"
OUTPUT_FILE = "de_en.json"


def main():
    data = json.load(open(EN_DE_FILE, encoding="utf-8"))
    print(f"Loaded {len(data):,} entries from {EN_DE_FILE}")

    de_to_entries: dict[str, list] = {}
    for entry in data:
        en = entry["en"]
        rank = entry.get("rank", 9999)
        de_val = entry.get("de")
        if not de_val:
            continue
        raw_de = de_val if isinstance(de_val, list) else [de_val]
        de_list = raw_de[:1]  # primary only as reverse key
        for i, de in enumerate(de_list):
            de = de.lower().strip()
            if not de:
                continue
            eff_rank = rank if i == 0 else rank + 5000
            de_to_entries.setdefault(de, []).append((eff_rank, en))

    results = []
    for de, entries in de_to_entries.items():
        entries.sort(key=lambda x: x[0])
        top = entries[:3]
        en_list = [e[1] for e in top]
        best_rank = top[0][0]
        results.append({
            "de": de,
            "en": en_list[0] if len(en_list) == 1 else en_list,
            "rank": best_rank,
        })

    results.sort(key=lambda e: e["rank"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    multi = sum(1 for r in results if isinstance(r["en"], list))
    print(f"Wrote {OUTPUT_FILE}: {len(results):,} DE entries")
    print(f"  Single EN: {len(results)-multi:,}  Multi-EN: {multi:,}")


if __name__ == "__main__":
    main()
