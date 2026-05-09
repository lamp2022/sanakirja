# Dictionary Quality Improvement — Design

**Date:** 2026-05-09
**Project:** sanakirja
**Goal:** Three targeted improvements: (1) backfill missing `fi_rank` in `data.json`,
(2) add 16 common everyday words absent from the EN base, (3) generate Claude
cross-validation checkpoints for DE/IT/FR to reduce the 35–36% GT-only tier.

---

## Problem Statement

After auditing all language dictionaries:

### 1. fi_rank gap in data.json
`data.json` (the FI-anchored master, 4,790 entries) had `fi_rank` populated in only
41 entries (0.9%). The other 4,749 lacked it, meaning the website's unfiltered browse
view was unsorted. The rank data exists in `en_fi_data.json` — it just wasn't written
back to `data.json` during the pipeline.

### 2. Missing common words
16 everyday words are absent from the EN base (`en_fi_data.json`) and thus from all
language pairs. Examples: `phone`/puhelin, `city`/kaupunki, `headache`/päänsärky,
`fever`/kuume, `buy`/ostaa, `walk`/kävellä, `birthday`/syntymäpäivä.
These words are missing because the EN key list was derived from Finnish frequency data
and some compound/specific Finnish words (like päänsärky) didn't map back from that
frequency pivot.

### 3. GT-only translations for DE/IT/FR (35–36%)
- DE: 1,853 entries gt_only (35.3%), including rank-1 core verbs
- IT: 1,884 entries gt_only (35.8%), including rank-1 "be" and "to have"
- FR: 1,829 entries gt_only (34.8%), including rank-1 "be" and "to have"

The build scripts (`37_build_en_de.py`, `41_build_en_it.py`, `45_build_en_fr.py`) already
have `CLAUDE_FILE` support wired in but the checkpoint files have never been generated.
Running Claude over the top-1000 words and rebuilding will promote most gt_only entries
to `gt+claude` or `kaikki+claude` automatically.

Also found: three specific bad entries across DE/IT/FR:
- DE "house" → had `[Haus, Vater-Mutter-Kind]` (nonsense second item)
- FR "can" → had `peut` (conjugated form) and `fr_gt = "può"` (Italian word — language mixing bug)
- FR "dog" → list included `iench` (non-standard/corrupted)
- IT "run" → had `[punto, mandata, montata]` (all noun senses, verb sense missing)

---

## Architecture

### Fix 1: fi_rank backfill
`50_backfill_fi_rank.py` — standalone, safe to re-run.
- Builds `{fi_word: rank}` from `en_fi_data.json` (handles list `fi` values)
- Writes `fi_rank` for entries where fi word is in map; 9999 for 34 unfillable entries
  (suffix markers like `näköinen`, adverbs like `ainoastaan` not in EN key list)
- Uses `utils.atomic_write_json`, runs `12_validate_output.py` at end

### Fix 2: vocabulary supplement
`51_add_missing_common.py` — hardcoded list of 16 hand-verified entries.
- Appends to all six files: `en_fi_data.json`, `en_{sv,de,it,fr}.json`, `data.json`
- Confidence = `curated`, ranks 5247–5262 (continuing the sequence)
- Idempotent: skips words already present

### Fix 3: bad entries
Applied directly via `atomic_write_json` to the built JSON files, using overrides already
defined in `en_de_extras.json`, `en_fr_extras.json`, `en_it_extras.json`.

### Fix 4: Claude checkpoints for DE/IT/FR
Three scripts mirroring `34_build_claude_sv.py`:
- `47_build_claude_de.py` → `../sanakirja/claude_en_de.jsonl`
- `48_build_claude_it.py` → `../sanakirja/claude_en_it.jsonl`
- `49_build_claude_fr.py` → `../sanakirja/claude_en_fr.jsonl`

All three: resumable JSONL checkpoint, top-1000 EN words by rank, claude-haiku-4-5-20251001,
batch 20 words/call, 0.5 s delay. After each, rebuild the corresponding `en_X.json` with
the existing build script.

---

## Checkpoint storage

All `.jsonl` checkpoint files go to `../sanakirja/` (sibling of the git repo root) —
same convention as kaikki dumps and GT checkpoints. Never committed to git.
Only the built output (`en_*.json`) is committed.

---

## Quality Impact After Fix 4

| Language | GT-only before | Expected after rebuild |
|---|---|---|
| DE | 1,853 (35.3%) | ~800–1,000 remain |
| IT | 1,884 (35.8%) | ~800–1,000 remain |
| FR | 1,829 (34.8%) | ~800–1,000 remain |

Entries where Claude agrees with GT → `gt+claude`
Entries where kaikki+gt and Claude all agree → `3sources`

---

## Follow-up (not in scope here)

- Run `qc_audit.py de/it/fr/sv` after rebuild (needs `../sanakirja/<lang>_freq_50k.txt` files)
- Further vocabulary expansion beyond the 16 words (systematic FI frequency gap analysis)
- Swedish has no equivalent issue — already at 76.8% multi-source coverage
