#!/usr/bin/env python3
"""
45_build_en_fr.py

Build en_fr.json from EN keys + kaikki German + GT EN→FR.

Mirrors 32_build_en_sv.py but adapted for German:
- Source priority: kaikki_german (POS-aware) → GT → Claude (no Apertium per skill)
- Infinitive: German verbs are bare infinitives ending in -en/-rn/-ln (no "att"/"zu" prefix needed)
- Verb-noun override: EN "to X" + DE primary doesn't end in -en → prefer GT if GT does
- Extras merge from en_fr_extras.json at end

Run: python3 45_build_en_fr.py
"""

import json
import os
import re
import sys
import time

EN_FI_FILE = "en_fi_data.json"
KAIKKI_FILE = "../sanakirja/kaikki_fr_en_fr.json"
GT_CHECKPOINT = "../sanakirja/gt_en_fr_checkpoint.jsonl"
CLAUDE_FILE = "claude_en_fr.jsonl"
FREQ_FILE = "../sanakirja/fr_freq_50k.txt"
EXTRAS_FILE = "en_fr_extras.json"
OUTPUT_FILE = "en_fr.json"
REVIEW_FILE = "EN_FR_REVIEW_SAMPLE.md"

GT_DELAY = 0.15
GT_FREQ_THRESHOLD = 5000
GT_FREQ_RATIO = 2

# Cache for WordNet POS lookups
_DOMINANT_POS_CACHE: dict[str, str] = {}


def load_fr_freq(path: str) -> dict[str, int]:
    freq: dict[str, int] = {}
    if not os.path.exists(path):
        return freq
    with open(path) as f:
        for i, line in enumerate(f):
            parts = line.strip().split()
            if parts:
                freq[parts[0].lower()] = i + 1
    return freq


def is_lemma(de: str, max_words: int = 4) -> bool:
    de = de.strip()
    if not de:
        return False
    if de.endswith(".") or len(de.split()) > max_words:
        return False
    if any(c.isdigit() for c in de):
        return False
    return True


def strip_fr_purpose(s: str) -> str:
    """Strip 'pour ' purpose-clause prefix from GT output (French)."""
    s = s.strip()
    if s.lower().startswith("pour "):
        return s[5:]
    return s


def looks_like_fr_verb(s: str) -> bool:
    """French verb infinitives end in -er/-ir/-re. Reflexive 'se '/'s\\'' allowed."""
    s = strip_fr_purpose(s).lower().strip()
    if s.startswith("se "):
        s = s[3:]
    elif s.startswith("s'"):
        s = s[2:]
    if not s or " " in s:
        return False
    return s.endswith("er") or s.endswith("ir") or s.endswith("re")


def _norm(s: str) -> str:
    """Normalize FR for comparison: lowercase, strip leading articles, reflexive 'se '/'s\''."""
    s = s.lower().strip()
    if s.startswith("se "):
        s = s[3:]
    elif s.startswith("s'"):
        s = s[2:]
    for art in ("le ", "la ", "les ", "l'", "un ", "une ", "des ", "du ", "de "):
        if s.startswith(art):
            s = s[len(art):]
            break
    return s


def consensus_override(kaikki_primary: str, fr_gt: str, claude_fr: str) -> str | None:
    """If GT and Claude agree on a normalized form different from kaikki primary, use that.
    Apertium intentionally excluded."""
    fp = _norm(kaikki_primary)
    raw_candidates = [s for s in [fr_gt, claude_fr] if s]
    if not raw_candidates:
        return None
    norm_to_raw: dict[str, str] = {}
    counts: dict[str, int] = {}
    for c in raw_candidates:
        nc = _norm(c)
        if nc not in norm_to_raw:
            norm_to_raw[nc] = c
        counts[nc] = counts.get(nc, 0) + 1
    best_norm = max(counts, key=lambda k: counts[k])
    if counts[best_norm] >= 2 and best_norm != fp:
        return norm_to_raw[best_norm]
    return None


def fr_matches(candidate: str, gt_de: str) -> bool:
    if not candidate or not gt_de:
        return False
    c = candidate.lower().strip()
    g = gt_de.lower().strip()
    if c == g:
        return True
    if c in g.split():
        return len(c) > 4
    return len(c) > 4 and c in g


def confidence_tag(has_kaikki: bool, gt_agrees: bool, claude_agrees: bool) -> str:
    if has_kaikki and gt_agrees and claude_agrees:
        return "3sources"
    if has_kaikki and gt_agrees:
        return "kaikki+gt"
    if has_kaikki and claude_agrees:
        return "kaikki+claude"
    if has_kaikki:
        return "kaikki_only"
    if gt_agrees and claude_agrees:
        return "gt+claude"
    if gt_agrees:
        return "gt_only"
    if claude_agrees:
        return "claude_only"
    return "none"


def dominant_en_pos(en_word: str) -> str:
    if en_word in _DOMINANT_POS_CACHE:
        return _DOMINANT_POS_CACHE[en_word]
    try:
        from nltk.corpus import wordnet as wn
    except ImportError:
        _DOMINANT_POS_CACHE[en_word] = ""
        return ""
    lookup = en_word.split()[-1] if " " in en_word else en_word
    try:
        def lc(pos):
            return sum(l.count() for s in wn.synsets(lookup, pos=pos)
                       for l in s.lemmas() if l.name().lower() == lookup)
        n, v, a, r = lc("n"), lc("v"), lc("a"), lc("r")
        if n + v + a + r == 0:
            n = len(wn.synsets(lookup, pos="n"))
            v = len(wn.synsets(lookup, pos="v"))
            a = len(wn.synsets(lookup, pos="a"))
            r = len(wn.synsets(lookup, pos="r"))
    except LookupError:
        _DOMINANT_POS_CACHE[en_word] = ""
        return ""
    counts = {"nn": n, "vb": v, "jj": a, "ab": r}
    best = max(counts, key=lambda k: counts[k])
    if counts[best] == 0:
        result = ""
    else:
        sorted_counts = sorted(counts.values(), reverse=True)
        result = best if sorted_counts[0] != sorted_counts[1] else ""
    _DOMINANT_POS_CACHE[en_word] = result
    return result


def _prefer_single_word(translations: list[str]) -> list[str]:
    single = [t for t in translations if " " not in t.strip()]
    multi = [t for t in translations if " " in t.strip()]
    return single + multi


def select_kaikki_by_pos(entry: dict, en_word: str, fr_freq: dict) -> list[str]:
    """Pick kaikki DE translations matching dominant EN POS, prefer common ones."""
    if not entry:
        return []
    en_lc = en_word.lower().strip()
    if en_lc.startswith("to ") and "vb" in entry:
        cands = list(entry["vb"])
    else:
        pos = dominant_en_pos(en_lc[3:] if en_lc.startswith("to ") else en_lc)
        if pos and pos in entry:
            cands = list(entry[pos])
        else:
            seen = set()
            cands = []
            for tlist in entry.values():
                for t in tlist:
                    if t not in seen:
                        seen.add(t)
                        cands.append(t)
    # Sort by freq rank (more common first), preferring single-word
    def sort_key(w):
        single = " " not in w.strip()
        rank = fr_freq.get(w.lower(), 99999)
        return (0 if single else 1, rank)
    return sorted(cands, key=sort_key)


def load_jsonl_cache(path: str, key_field: str) -> dict[str, str]:
    cache: dict[str, str] = {}
    if not os.path.exists(path):
        return cache
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                k = rec.get(key_field, "").strip()
                if k:
                    cache[k] = rec.get("fr_gt") or rec.get("fr") or ""
            except json.JSONDecodeError:
                pass
    return cache


def main():
    enfi = json.load(open(EN_FI_FILE))
    en_keys = [e["en"] for e in enfi]
    en_to_rank = {e["en"]: e.get("rank", 9999) for e in enfi}
    print(f"EN base: {len(en_keys):,} keys from {EN_FI_FILE}")

    fr_freq = load_fr_freq(FREQ_FILE)
    print(f"DE freq list: {len(fr_freq):,} words")

    if not os.path.exists(KAIKKI_FILE):
        print(f"ERROR: {KAIKKI_FILE} missing — run 36_parse_kaikki_de.py first", file=sys.stderr)
        sys.exit(1)
    kaikki = json.load(open(KAIKKI_FILE))
    print(f"kaikki EN→FR: {len(kaikki):,} EN entries")

    gt_cache = load_jsonl_cache(GT_CHECKPOINT, "en")
    print(f"GT cache: {len(gt_cache):,} entries already done")

    claude_cache: dict[str, str] = {}
    if os.path.exists(CLAUDE_FILE):
        with open(CLAUDE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    en = rec.get("en", "").lower().strip()
                    de = rec.get("fr", "").lower().strip()
                    if en and de:
                        claude_cache[en] = de
                except json.JSONDecodeError:
                    pass
    print(f"Claude cache: {len(claude_cache):,} entries")

    # Run GT for missing
    todo_gt = [en for en in en_keys if en not in gt_cache]
    if todo_gt:
        print(f"\nRunning GT EN→FR for {len(todo_gt):,} new keys (≈{len(todo_gt)*GT_DELAY/60:.1f} min)…")
        from utils import gt
        with open(GT_CHECKPOINT, "a") as ckpt:
            for i, en in enumerate(todo_gt):
                if i % 200 == 0 and i > 0:
                    print(f"  {i:,}/{len(todo_gt):,} done")
                tr = gt(en, sl="en", tl="fr")
                rec = {"en": en, "fr_gt": tr or ""}
                ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                ckpt.flush()
                gt_cache[en] = tr or ""
                time.sleep(GT_DELAY)
        print(f"  GT done: {len(todo_gt):,} calls")

    # Build output
    results = []
    stats: dict[str, int] = {"total": len(en_keys), "has_kaikki": 0,
                             "gt_agrees": 0, "claude_agrees": 0}

    for en in en_keys:
        en_norm = en.lower().strip()
        kaikki_key = en_norm[3:] if en_norm.startswith("to ") else en_norm

        kaikki_entry = kaikki.get(kaikki_key, {})
        raw_kaikki = select_kaikki_by_pos(kaikki_entry, en_norm, fr_freq)
        kaikki_frs = [d for d in raw_kaikki if is_lemma(d)][:3]
        has_kaikki = bool(kaikki_frs)
        if has_kaikki:
            stats["has_kaikki"] += 1

        fr_gt = gt_cache.get(en, "") or ""
        claude_fr = claude_cache.get(en_norm, "")

        if has_kaikki:
            primary_fr = kaikki_frs[0]
            fr_all = kaikki_frs
            # Level 1: consensus override
            override = consensus_override(primary_fr, fr_gt, claude_fr)
            if override:
                primary_fr = override
                fr_all = [override]
                stats["consensus_overridden"] = stats.get("consensus_overridden", 0) + 1
            # Level 3: GT-frequency override
            elif fr_gt and fr_freq:
                prim_n = _norm(primary_fr).rstrip("!-").strip()
                gt_n = _norm(fr_gt).rstrip("!-").strip()
                gt_root = gt_n.split()[0] if gt_n else ""
                if gt_root and " " not in prim_n:
                    prim_rank = fr_freq.get(prim_n, 99999)
                    gt_rank = fr_freq.get(gt_root, 99999)
                    if prim_rank > GT_FREQ_THRESHOLD and gt_rank * GT_FREQ_RATIO < prim_rank:
                        primary_fr = gt_root if " " not in fr_gt else fr_gt
                        fr_all = [primary_fr]
                        stats["gt_freq_overridden"] = stats.get("gt_freq_overridden", 0) + 1
            # Level 4: verb-noun mismatch (EN 'to X', primary not French infinitive).
            # Strip 'pour X' purpose clause from GT before storing.
            if (primary_fr == kaikki_frs[0]
                    and en_norm.startswith("to ")
                    and fr_gt and looks_like_fr_verb(fr_gt)
                    and not looks_like_fr_verb(primary_fr)):
                primary_fr = strip_fr_purpose(fr_gt)
                fr_all = [primary_fr]
                stats["verb_noun_overridden"] = stats.get("verb_noun_overridden", 0) + 1
            # Level 2: GT-secondary promotion
            if fr_gt and len(kaikki_frs) > 1 and primary_fr == kaikki_frs[0]:
                gt_n = _norm(fr_gt)
                secondaries_norm = [_norm(s) for s in kaikki_frs[1:]]
                if gt_n in secondaries_norm and gt_n != _norm(primary_fr):
                    idx = secondaries_norm.index(gt_n)
                    promoted = kaikki_frs[1 + idx]
                    primary_fr = promoted
                    fr_all = [promoted] + [s for s in kaikki_frs if s != promoted][:2]
                    stats["gt_secondary_promoted"] = stats.get("gt_secondary_promoted", 0) + 1
            # Level 5: GT-no-backing override
            if (primary_fr == kaikki_frs[0]
                    and fr_gt and fr_freq and _norm(fr_gt) != _norm(primary_fr)):
                claude_backs = bool(claude_fr) and _norm(claude_fr) == _norm(primary_fr)
                if not claude_backs:
                    fr_gt_clean = strip_fr_purpose(fr_gt)
                    gt_root = _norm(fr_gt_clean).rstrip("!-").strip().split()[0]
                    prim_root = _norm(primary_fr).rstrip("!-").strip().split()[0]
                    if gt_root and prim_root:
                        prim_rank = fr_freq.get(prim_root, 99999)
                        gt_rank = fr_freq.get(gt_root, 99999)
                        if gt_rank < prim_rank:
                            primary_fr = fr_gt_clean
                            fr_all = [fr_gt_clean]
                            stats["gt_no_backing_overridden"] = stats.get("gt_no_backing_overridden", 0) + 1
        elif fr_gt:
            primary_fr = strip_fr_purpose(fr_gt)
            fr_all = [primary_fr]
        elif claude_fr:
            primary_fr = claude_fr
            fr_all = [claude_fr]
        else:
            continue

        gt_agrees = fr_matches(primary_fr, fr_gt)
        claude_agrees = fr_matches(primary_fr, claude_fr)
        if gt_agrees:
            stats["gt_agrees"] += 1
        if claude_agrees:
            stats["claude_agrees"] += 1

        tag = confidence_tag(has_kaikki, gt_agrees, claude_agrees)
        stats[tag] = stats.get(tag, 0) + 1

        entry = {
            "en": en,
            "fr": fr_all if len(fr_all) > 1 else primary_fr,
            "rank": en_to_rank.get(en, 9999),
            "confidence": tag,
        }
        if fr_gt and fr_gt != primary_fr:
            entry["fr_gt"] = fr_gt
        if claude_fr and claude_fr != primary_fr:
            entry["fr_claude"] = claude_fr
        results.append(entry)

    # Merge extras
    if os.path.exists(EXTRAS_FILE):
        extras = json.load(open(EXTRAS_FILE))
        en_to_idx = {e["en"].lower(): i for i, e in enumerate(results)}
        added = overridden = 0
        for x in extras.get("overrides", []):
            key = x["en"].lower()
            if key in en_to_idx:
                results[en_to_idx[key]]["fr"] = x["fr"]
                results[en_to_idx[key]]["confidence"] = "extras_override"
                overridden += 1
        for x in extras.get("extras", []):
            if x["en"].lower() not in en_to_idx:
                results.append({"en": x["en"], "fr": x["fr"],
                                "rank": x.get("rank", 9999), "confidence": "extras"})
                added += 1
        if added or overridden:
            stats["extras_added"] = added
            stats["extras_overridden"] = overridden

    print(f"\n--- Coverage stats ---")
    print(f"Total EN keys:                {stats['total']:>6}")
    print(f"Has kaikki match:             {stats['has_kaikki']:>6}  ({stats['has_kaikki']/stats['total']*100:.1f}%)")
    print(f"GT agrees with primary:       {stats['gt_agrees']:>6}")
    print(f"Claude agrees with primary:   {stats['claude_agrees']:>6}")
    print(f"Consensus override applied:   {stats.get('consensus_overridden',0):>6}")
    print(f"GT-secondary promotion:       {stats.get('gt_secondary_promoted',0):>6}")
    print(f"GT-frequency override:        {stats.get('gt_freq_overridden',0):>6}")
    print(f"GT-no-backing override:       {stats.get('gt_no_backing_overridden',0):>6}")
    print(f"Verb-noun mismatch fixed:     {stats.get('verb_noun_overridden',0):>6}")
    if stats.get("extras_added") or stats.get("extras_overridden"):
        print(f"Extras added:                 {stats.get('extras_added',0):>6}")
        print(f"Extras overrode:              {stats.get('extras_overridden',0):>6}")
    no_match = stats["total"] - len(results) + stats.get("extras_added", 0)
    print(f"No match at all:              {no_match:>6}")
    print(f"Total emitted:                {len(results):>6}")

    results.sort(key=lambda e: e["rank"])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {OUTPUT_FILE} ({len(results):,} entries)")

    write_review_sample(results, en_to_rank)


def write_review_sample(results, en_to_rank):
    """50-entry review sample across rank buckets."""
    by_rank = sorted(results, key=lambda e: e["rank"])
    buckets = [
        [e for e in by_rank if e["rank"] <= 100][:10],
        [e for e in by_rank if 100 < e["rank"] <= 500][:10],
        [e for e in by_rank if 500 < e["rank"] <= 2000][:15],
        [e for e in by_rank if e["rank"] > 2000][:15],
    ]
    sample = [e for b in buckets for e in b]
    lines = ["# EN→FR Review Sample (50 entries)\n",
             "Spot-check: mark wrong translations with `~~strikethrough~~`.\n",
             "| EN | DE (primary) | rank | confidence |",
             "|----|----|----|----|"]
    for e in sample:
        de = e["fr"]
        de_str = " / ".join(de) if isinstance(de, list) else de
        lines.append(f"| `{e['en']}` | {de_str} | {e['rank']} | {e['confidence']} |")
    with open(REVIEW_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {REVIEW_FILE} ({len(sample)} entries)")


if __name__ == "__main__":
    main()
