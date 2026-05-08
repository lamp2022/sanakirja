#!/usr/bin/env python3
"""
29_apply_tier_d_curated.py

Apply user-curated Tier D approvals from EN_FI_REVIEW_TIER_D_TOP50.md.
Two new lemmas added to data.json (varat, pitää päällään); the rest are
EN-list appends to existing FI entries. Idempotent.

Run 14_build_en_fi.py afterwards.
"""

import json
import sys
from utils import atomic_write_json

DATA_FILE = "data.json"

# (en, candidate_fi) — append `en` to candidate_fi's en list in data.json
APPENDS = [
    # 18 score-8 clear approvals
    ("everyone", "kaikki"),
    ("term", "kausi"),
    ("to resist", "kestää"),
    ("to arrange", "asettaa"),
    ("credit", "kunnia"),
    ("marking", "merkki"),
    ("department", "laitos"),
    ("examination", "koe"),
    ("to damage", "pilata"),
    ("commodity", "tavara"),
    ("advertisement", "ilmoitus"),
    ("mastery", "hallinta"),
    ("pattern", "kaava"),
    ("movie", "filmi"),
    ("procedure", "toimenpide"),
    ("shape", "kuvio"),
    ("sequence", "jono"),
    ("to be found", "esiintyä"),
    # 6 borderlines kept after user review
    ("to enter", "merkitä"),
    ("to find", "huomata"),
    ("to dig", "tajuta"),
    ("crazy", "hurja"),
    ("prescription", "määräys"),
    ("hurry", "hätä"),
]

# New data.json entries for FI lemmas not yet present.
# Following the multi-word precedent (ajan mittaan, alla oleva, etc.).
# fi_rank omitted → 14_build_en_fi.py treats as rank 9999 (low-priority secondary).
NEW_ENTRIES = [
    {"fi": "varat",          "en": "fund",    "pos": "noun"},
    {"fi": "pitää päällään", "en": "to wear", "pos": "verb"},
]


def main():
    data = json.load(open(DATA_FILE))
    by_fi = {e["fi"]: e for e in data}

    appended = skipped_already = skipped_missing = 0
    sample = []
    for en, fi in APPENDS:
        entry = by_fi.get(fi)
        if not entry:
            skipped_missing += 1
            print(f"  ! candidate FI not in data.json: {fi}")
            continue
        cur = entry.get("en")
        cur_list = list(cur) if isinstance(cur, list) else [cur]
        if en in cur_list:
            skipped_already += 1
            continue
        cur_list.append(en)
        entry["en"] = cur_list
        appended += 1
        sample.append((fi, en, cur_list))

    new_added = 0
    for new in NEW_ENTRIES:
        if new["fi"] in by_fi:
            print(f"  ! already in data.json, skipping: {new['fi']}")
            continue
        data.append(new)
        by_fi[new["fi"]] = new
        new_added += 1

    print(f"\nAppends: {appended}  (already had: {skipped_already}, "
          f"missing fi: {skipped_missing})")
    print(f"New lemma entries: {new_added}")
    if sample:
        print("\nSample:")
        for fi, en, lst in sample[:8]:
            print(f"  {fi:>15}.en += {en!r:<22} → {lst}")
    if new_added:
        for ne in NEW_ENTRIES:
            print(f"  + {ne}")

    if appended + new_added == 0:
        print("\nNo changes (idempotent re-run).")
        return

    atomic_write_json(DATA_FILE, data)
    print("\nWrote data.json. Run 14_build_en_fi.py.")


if __name__ == "__main__":
    main()
