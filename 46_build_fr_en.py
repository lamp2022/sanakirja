#!/usr/bin/env python3
"""
38_build_de_en.py

Build fr_en.json from en_fr.json (reverse view).
Mirrors 33_build_sv_en.py pattern:
- Primary FR (lowest rank EN) wins top slot
- Top-3 ENs per DE
"""

import json

EN_FR_FILE = "en_fr.json"
OUTPUT_FILE = "fr_en.json"


def main():
    data = json.load(open(EN_FR_FILE, encoding="utf-8"))
    print(f"Loaded {len(data):,} entries from {EN_FR_FILE}")

    fr_to_entries: dict[str, list] = {}
    for entry in data:
        en = entry["en"]
        rank = entry.get("rank", 9999)
        fr_val = entry.get("fr")
        if not fr_val:
            continue
        raw_fr = fr_val if isinstance(fr_val, list) else [fr_val]
        fr_list = raw_fr[:1]  # primary only as reverse key
        for i, fr in enumerate(fr_list):
            fr = fr.lower().strip()
            if not fr:
                continue
            eff_rank = rank if i == 0 else rank + 5000
            fr_to_entries.setdefault(fr, []).append((eff_rank, en))

    results = []
    for fr, entries in fr_to_entries.items():
        entries.sort(key=lambda x: x[0])
        top = entries[:3]
        en_list = [e[1] for e in top]
        best_rank = top[0][0]
        results.append({
            "fr": fr,
            "en": en_list[0] if len(en_list) == 1 else en_list,
            "rank": best_rank,
        })

    results.sort(key=lambda e: e["rank"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    multi = sum(1 for r in results if isinstance(r["en"], list))
    print(f"Wrote {OUTPUT_FILE}: {len(results):,} FR entries")
    print(f"  Single EN: {len(results)-multi:,}  Multi-EN: {multi:,}")


if __name__ == "__main__":
    main()
