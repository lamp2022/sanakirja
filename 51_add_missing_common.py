#!/usr/bin/env python3
"""
51_add_missing_common.py

Append hand-verified common words absent from the EN base to all six language files:
  en_fi_data.json, en_sv.json, en_de.json, en_it.json, en_fr.json, data.json

Run: python3 51_add_missing_common.py
"""

import json
import subprocess
import sys
from utils import atomic_write_json

SUPPLEMENT = [
    # fmt: off
    # (en, fi, sv, de, it, fr, fi_pos, rank)
    ("phone",    "puhelin",      "telefon",    "Telefon",      "telefono",     "téléphone",   "noun", 5247),
    ("city",     "kaupunki",     "stad",       "Stadt",        "città",        "ville",       "noun", 5248),
    ("headache", "päänsärky",    "huvudvärk",  "Kopfschmerzen","mal di testa", "mal de tête", "noun", 5249),
    ("fever",    "kuume",        "feber",      "Fieber",       "febbre",       "fièvre",      "noun", 5250),
    ("cough",    "yskä",         "hosta",      "Husten",       "tosse",        "toux",        "noun", 5251),
    ("flu",      "flunssa",      "influensa",  "Grippe",       "influenza",    "grippe",      "noun", 5252),
    ("sick",     "sairas",       "sjuk",       "krank",        "malato",       "malade",      "adj",  5253),
    ("hurt",     "sattua",       "göra ont",   "wehtun",       "fare male",    "faire mal",   "verb", 5254),
    ("buy",      "ostaa",        "köpa",       "kaufen",       "comprare",     "acheter",     "verb", 5255),
    ("sell",     "myydä",        "sälja",      "verkaufen",    "vendere",      "vendre",      "verb", 5256),
    ("push",     "työntää",      "trycka",     "drücken",      "spingere",     "pousser",     "verb", 5257),
    ("tennis",   "tennis",       "tennis",     "Tennis",       "tennis",       "tennis",      "noun", 5258),
    ("walk",     "kävellä",      "gå",         "gehen",        "camminare",    "marcher",     "verb", 5259),
    ("sit",      "istua",        "sitta",      "sitzen",       "sedersi",      "s'asseoir",   "verb", 5260),
    ("birthday", "syntymäpäivä", "födelsedag", "Geburtstag",   "compleanno",   "anniversaire","noun", 5261),
    ("gift",     "lahja",        "present",    "Geschenk",     "regalo",       "cadeau",      "noun", 5262),
    # fmt: on
]


def main():
    def load(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    en_fi = load("en_fi_data.json")
    en_sv = load("en_sv.json")
    en_de = load("en_de.json")
    en_it = load("en_it.json")
    en_fr = load("en_fr.json")
    data  = load("data.json")

    existing_en = {e["en"] for e in en_fi}
    existing_fi = {e["fi"] for e in data}

    added = 0
    for en, fi, sv, de, it, fr, pos, rank in SUPPLEMENT:
        if en in existing_en:
            print(f"SKIP {en!r} — already present")
            continue

        en_fi.append({"en": en, "fi": fi, "rank": rank})
        en_sv.append({"en": en, "sv": sv, "rank": rank, "confidence": "curated"})
        en_de.append({"en": en, "de": de, "rank": rank, "confidence": "curated"})
        en_it.append({"en": en, "it": it, "rank": rank, "confidence": "curated"})
        en_fr.append({"en": en, "fr": fr, "rank": rank, "confidence": "curated"})

        if fi not in existing_fi:
            data.append({"fi": fi, "en": en, "fi_rank": rank, "pos": pos})

        print(f"  + {en:12} → fi={fi}, sv={sv}, de={de}, it={it}, fr={fr}")
        added += 1

    if added == 0:
        print("Nothing to add — all entries already present.")
        return

    print(f"\nAdded {added} entries to each file.")
    atomic_write_json("en_fi_data.json", en_fi)
    atomic_write_json("en_sv.json",      en_sv)
    atomic_write_json("en_de.json",      en_de)
    atomic_write_json("en_it.json",      en_it)
    atomic_write_json("en_fr.json",      en_fr)
    atomic_write_json("data.json",       data)
    print("All files written.")

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
