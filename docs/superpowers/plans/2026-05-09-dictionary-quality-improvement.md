# Dictionary Quality Improvement — Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply four quality improvements: backfill fi_rank, add 16 missing common words,
fix 4 known bad translation entries, and generate Claude cross-validation checkpoints for
DE/IT/FR so the build scripts can promote gt_only entries to multi-source tiers.

**Status:** Steps 1–4 are complete (done 2026-05-09). Step 5 (Claude checkpoint generation)
requires running with an Anthropic API key and rebuild of the three language files.

---

## File Map

| Path | Action | Status |
|---|---|---|
| `50_backfill_fi_rank.py` | Created | ✅ Done |
| `51_add_missing_common.py` | Created | ✅ Done |
| `47_build_claude_de.py` | Created | ✅ Done |
| `48_build_claude_it.py` | Created | ✅ Done |
| `49_build_claude_fr.py` | Created | ✅ Done |
| `data.json` | fi_rank backfilled | ✅ Done |
| `en_fi_data.json` | 16 words appended | ✅ Done |
| `en_sv.json` | 16 words appended | ✅ Done |
| `en_de.json` | 16 words + overrides applied | ✅ Done |
| `en_it.json` | 16 words + override applied | ✅ Done |
| `en_fr.json` | 16 words + overrides applied | ✅ Done |
| `en_de_extras.json` | "house" override added | ✅ Done |
| `en_fr_extras.json` | "dog" + "can" overrides added | ✅ Done |
| `en_it_extras.json` | "run" override added | ✅ Done |
| `../sanakirja/claude_en_de.jsonl` | Generate with 47 | 🔲 Pending |
| `../sanakirja/claude_en_it.jsonl` | Generate with 48 | 🔲 Pending |
| `../sanakirja/claude_en_fr.jsonl` | Generate with 49 | 🔲 Pending |

---

## Completed Tasks

- [x] **Step 1: Backfill fi_rank**
  Run: `python3 50_backfill_fi_rank.py`
  Result: 4,715 filled, 34 defaulted to 9999, validation passed (4,796 rows)

- [x] **Step 2: Add 16 missing common words**
  Run: `python3 51_add_missing_common.py`
  Result: phone/puhelin, city/kaupunki, headache/päänsärky and 13 more added to all files.
  Validation passed (4,796 rows).

- [x] **Step 3: Fix bad entries in extras files**
  - `en_de_extras.json`: added override `"house" → "Haus"`
  - `en_fr_extras.json`: added overrides `"dog" → "chien"`, `"can" → "pouvoir"`
  - `en_it_extras.json`: added override `"run" → "correre"`
  Applied directly to built JSON files (rebuild not possible without raw kaikki sources).

- [x] **Step 4: Create Claude checkpoint scripts**
  Created: `47_build_claude_de.py`, `48_build_claude_it.py`, `49_build_claude_fr.py`
  Same pattern as `34_build_claude_sv.py`. Language-specific system prompts.

---

## Remaining Tasks

- [ ] **Step 5: Generate Claude checkpoints + rebuild**

  Requires `ANTHROPIC_API_KEY` in environment and raw kaikki source files in `../sanakirja/`.

  ```bash
  # Generate checkpoints (resumable — safe to interrupt and restart)
  python3 47_build_claude_de.py   # ~25 min for 1000 words
  python3 48_build_claude_it.py
  python3 49_build_claude_fr.py

  # Rebuild dictionaries (needs ../sanakirja/kaikki_de_en_de.json etc.)
  python3 37_build_en_de.py
  python3 41_build_en_it.py
  python3 45_build_en_fr.py
  ```

- [ ] **Step 6: Run qc_audit.py**

  Download full 50k frequency lists and verify:
  ```bash
  for LANG in de it fr sv; do
    curl -o ../sanakirja/${LANG}_freq_50k.txt \
      "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/${LANG}/${LANG}_50k.txt"
  done
  python3 qc_audit.py de
  python3 qc_audit.py it
  python3 qc_audit.py fr
  python3 qc_audit.py sv
  ```

  Expected: gt_only count drops by ~850–1,050 per language.
  Any new issues from audit → add to extras overrides and rebuild.

---

## Verification

After step 5:
1. `python3 12_validate_output.py` — must pass
2. Confidence distribution: `gt_only` count should drop significantly for DE/IT/FR
3. Spot-check: `headache` → päänsärky/hlavvärk/Kopfschmerzen present in all files
4. Spot-check fixed entries: house→DE=Haus, dog→FR=chien, can→FR=pouvoir, run→IT=correre
