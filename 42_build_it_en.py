#!/usr/bin/env python3
"""
38_build_de_en.py

Build it_en.json from en_it.json (reverse view).
Mirrors 33_build_sv_en.py pattern:
- Primary IT (lowest rank EN) wins top slot
- Top-3 ENs per DE
"""

import json

EN_IT_FILE = "en_it.json"
OUTPUT_FILE = "it_en.json"


def main():
    data = json.load(open(EN_IT_FILE, encoding="utf-8"))
    print(f"Loaded {len(data):,} entries from {EN_IT_FILE}")

    it_to_entries: dict[str, list] = {}
    for entry in data:
        en = entry["en"]
        rank = entry.get("rank", 9999)
        it_val = entry.get("it")
        if not it_val:
            continue
        raw_it = it_val if isinstance(it_val, list) else [it_val]
        it_list = raw_it[:1]  # primary only as reverse key
        for i, it in enumerate(it_list):
            it = it.lower().strip()
            if not it:
                continue
            eff_rank = rank if i == 0 else rank + 5000
            it_to_entries.setdefault(it, []).append((eff_rank, en))

    results = []
    for it, entries in it_to_entries.items():
        entries.sort(key=lambda x: x[0])
        top = entries[:3]
        en_list = [e[1] for e in top]
        best_rank = top[0][0]
        results.append({
            "it": it,
            "en": en_list[0] if len(en_list) == 1 else en_list,
            "rank": best_rank,
        })

    results.sort(key=lambda e: e["rank"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    multi = sum(1 for r in results if isinstance(r["en"], list))
    print(f"Wrote {OUTPUT_FILE}: {len(results):,} IT entries")
    print(f"  Single EN: {len(results)-multi:,}  Multi-EN: {multi:,}")


if __name__ == "__main__":
    main()
