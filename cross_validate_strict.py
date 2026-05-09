#!/usr/bin/env python3
"""
cross_validate_strict.py — surface ONLY high-confidence corrections.

A correction is high-confidence when ALL of these hold:
1. Our primary is absent from kaikki's translation list (no normalized match)
2. Our primary is also rare/absent in the target-language freq corpus (rank > 5000)
3. kaikki's first translation is common in the freq corpus (rank ≤ 2000)
4. kaikki has at least 1 sense backing the proposed correction

This catches genuine wrong primaries (there→hier, who→oms, back→di rimando)
while filtering out the noise (kaikki listing rare synonyms or senses).

Usage: .venv/bin/python cross_validate_strict.py de it fr sv
"""

import json
import os
import sys

import pyarrow.parquet as pq
import pyarrow.compute as pc

KAIKKI_EN = "../sanakirja/kaikki_english.parquet"
PRIMARY_RANK_THRESHOLD = 5000   # ours must be rare/absent
KAIKKI_RANK_THRESHOLD = 2000    # kaikki's must be common


def load_freq(lang: str) -> dict[str, int]:
    path = f"../sanakirja/{lang}_freq_50k.txt"
    if not os.path.exists(path):
        return {}
    f = {}
    with open(path) as fp:
        for i, line in enumerate(fp):
            parts = line.split()
            if parts:
                f[parts[0].lower()] = i + 1
    return f


def normalize_de(s):
    s = s.lower().strip()
    if s.startswith(("zu ", "der ", "die ", "das ")):
        s = s.split(" ", 1)[1]
    return s


def normalize_it(s):
    s = s.lower().strip()
    for art in ("il ", "la ", "lo ", "i ", "le ", "gli ", "un ", "una ", "uno "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def normalize_fr(s):
    s = s.lower().strip()
    if s.startswith("se "): s = s[3:]
    elif s.startswith("s'"): s = s[2:]
    for art in ("le ", "la ", "les ", "l'", "un ", "une ", "des ", "du ", "de "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def normalize_sv(s):
    s = s.lower().strip()
    if s.startswith("att "):
        s = s[4:]
    return s


NORMS = {"de": normalize_de, "it": normalize_it, "fr": normalize_fr, "sv": normalize_sv}


def build_lookup(parquet_path: str, lang_codes: list[str]) -> dict:
    print(f"Loading {parquet_path}...")
    t = pq.read_table(parquet_path, columns=["word", "translations"])
    has_trans = pc.greater(pc.list_value_length(t["translations"]), 0)
    t = t.filter(has_trans)
    lookup = {}
    for word, tr in zip(t["word"].to_pylist(), t["translations"].to_pylist()):
        if not word:
            continue
        slot = lookup.setdefault(word.lower(), {})
        for one in tr:
            code = (one.get("code") or "").lower()
            w = one.get("word")
            if code in lang_codes and w:
                slot.setdefault(code, []).append(w)
    return lookup


def cross_validate(lang: str, lookup: dict, freq: dict[str, int]):
    en_X = f"en_{lang}.json"
    if not os.path.exists(en_X):
        return
    data = json.load(open(en_X))
    norm = NORMS[lang]

    high_conf_corrections = []  # (rank, en, primary, prim_freq, kaikki_top, kaikki_freq, conf)

    for e in data:
        en = e["en"].lower()
        primary_v = e.get(lang)
        primary = primary_v[0] if isinstance(primary_v, list) else primary_v
        if not primary:
            continue

        k = lookup.get(en) or lookup.get(en[3:] if en.startswith("to ") else "")
        if not k or lang not in k:
            continue
        k_translations = k[lang]
        k_norms = {norm(t) for t in k_translations}
        prim_norm = norm(primary)
        if prim_norm in k_norms:
            continue  # validated

        # Our primary is NOT in kaikki list. Is it rare?
        prim_root = prim_norm.split()[0] if prim_norm else ""
        prim_rank = freq.get(prim_root, 99999) if prim_root else 99999
        if prim_rank <= PRIMARY_RANK_THRESHOLD:
            continue  # ours is common enough to trust

        # Find kaikki's most common translation
        best = None
        best_rank = 99999
        for k_tr in k_translations:
            k_norm = norm(k_tr)
            k_root = k_norm.split()[0] if k_norm else ""
            r = freq.get(k_root, 99999)
            if r < best_rank:
                best_rank = r
                best = k_tr
        if best is None or best_rank > KAIKKI_RANK_THRESHOLD:
            continue  # no common kaikki alternative

        high_conf_corrections.append({
            "rank": e["rank"], "en": e["en"], "old_primary": primary,
            "old_primary_freq_rank": prim_rank,
            "proposed": best, "proposed_freq_rank": best_rank,
            "kaikki_alternatives": k_translations[:5],
            "confidence": e.get("confidence", ""),
        })

    high_conf_corrections.sort(key=lambda x: x["rank"])
    print(f"\n{lang.upper()}: {len(high_conf_corrections)} high-confidence corrections")
    for c in high_conf_corrections[:25]:
        print(f"  #{c['rank']:>4}  {c['en']:25} {c['old_primary']!r:25} (freq #{c['old_primary_freq_rank']:>5}) "
              f"→ {c['proposed']!r:20} (freq #{c['proposed_freq_rank']:>5})")

    out = f"en_{lang}_strict_corrections.json"
    with open(out, "w") as f:
        json.dump({"corrections": high_conf_corrections}, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {out}")


def main():
    langs = sys.argv[1:] if len(sys.argv) > 1 else ["de", "it", "fr", "sv"]
    lookup = build_lookup(KAIKKI_EN, langs)
    print(f"  lookup keys: {len(lookup):,}")
    for lang in langs:
        freq = load_freq(lang)
        cross_validate(lang, lookup, freq)


if __name__ == "__main__":
    main()
