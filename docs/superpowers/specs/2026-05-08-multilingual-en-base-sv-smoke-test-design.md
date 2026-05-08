# Multilingual Dictionary — EN-Base Architecture, Swedish Smoke Test

**Date**: 2026-05-08
**Status**: Draft for review

## Context

The current `data.json` (FI-keyed master) carries `sv`, `it`, `fr`, `de`
columns with only 8–14% coverage and unverified quality. That thin layer
isn't useful and isn't backed by a clear pipeline.

We're abandoning it and starting over with English as the pivot language.
For each non-EN target language X, we'll build self-contained per-pair
files (`en_X.json` + `X_en.json`) using the same multi-source agreement
pattern that proved out for FI↔EN.

**This spec covers**: architecture, the cleanup pass, and a one-language
smoke test (Swedish, single-source). Phase 3 (full quality EN↔SV with
authoritative sources) and Phase 4+ (it/de/fr) are scoped out — each gets
its own spec when the smoke test results are in.

## Out of scope

- Modifying `data.json`'s `fi`/`en`/`fi_rank`/`pos` fields. The EN↔FI
  work shipped in commits `f67735f`–`6d8844b` is final and untouched.
- Modifying `en_fi_data.json`. Stays as-is.
- Quality gating in the smoke test (single source by design).
- Authoritative source procurement for SV (Phase 3).
- Site UI changes for multilingual display (Phase 3).
- Any non-Swedish target language (Phase 4+).

## Architecture: per-pair files

For each target language X ∈ {sv, it, de, fr}, two files at the repo root:

| File | Direction | Shape | Built by |
|---|---|---|---|
| `en_X.json` | EN-keyed → X | `[{"en": "stay", "X": "stanna", "rank": 57}, ...]` | source pipeline (Phase 2/3) |
| `X_en.json` | X-keyed → EN | `[{"X": "stanna", "en": "stay", "rank": 57}, ...]` | reverse builder, derived from `en_X.json` |

Same shape as the existing `en_fi_data.json`. Each pair is independent —
adding `it` later doesn't touch `en_sv.json` or anything else.

The website (`index.html`) loads only the language pairs the user
requests. For static hosting, per-pair splitting is preferable to one
big multilingual file.

## Phase 1: Cleanup

**Goal**: drop the thin sv/it/fr/de columns from `data.json`.

### Steps

1. New script `30_strip_other_langs.py`:
   - Loads `data.json`
   - For each entry, removes `sv`, `it`, `fr`, `de` keys (if present)
   - Writes back atomically via `utils.atomic_write_json`
   - Idempotent
2. Update `12_validate_output.py`: drop those four languages from its
   coverage report.
3. `index.html` audit: confirm nothing depends on those fields.
4. Run cleanup, regenerate `en_fi_data.json` (no-op — it never had those
   columns), validate.
5. Commit as a single `chore:` commit.

### Files modified

- `data.json` (sv/it/fr/de keys removed)
- `12_validate_output.py` (coverage report updated)
- `30_strip_other_langs.py` (new)

### Files NOT touched

- `en_fi_data.json`
- Any of `05_*` through `29_*` scripts
- `index.html` unless the audit reveals a real dependency

## Phase 2: Swedish smoke test

**Goal**: validate the per-pair architecture end-to-end with a single
source, get a real feel for kaikki.org's SV coverage.

### Source

`kaikki_english.jsonl` — kaikki.org's parsed dump of English Wiktionary,
including translation tables to all languages. Same JSONL-per-line
format as our existing `kaikki_finnish.jsonl`. Estimated size 600MB–1GB.

Download to `../sanakirja/kaikki_english.jsonl` (sibling folder, not in
git, like other big source caches).

Single source for the smoke test. Quality gating happens in Phase 3.

### Script: `31_build_en_sv.py`

1. Load `en_fi_data.json` to get the existing 5,246 EN keys + ranks.
2. Stream `../sanakirja/kaikki_english.jsonl`. For each English entry,
   extract Swedish glosses from `translations` (filter by
   `lang_code == "sv"` or `lang == "Swedish"`).
3. Build a lookup `{en_word: [sv_translations]}`.
4. For each EN key in `en_fi_data.json`:
   - If kaikki has SV translations, emit `{"en": ..., "sv": str_or_list, "rank": <inherited>}`.
   - If not, omit (smoke test doesn't fabricate).
5. Write `en_sv.json` (uncommitted until reviewed).
6. Sample 50 entries (mix of common ranks and rare ranks) and write to
   `EN_SV_REVIEW_SAMPLE.md` for spot-check.

### Coverage stats to print

- Total EN keys in `en_fi_data.json`: 5,246
- EN keys with kaikki SV translation: N
- Single-sense SV: N
- Multi-sense SV: N
- EN keys with no SV match: N

### Decision gate after smoke test

User reviews `EN_SV_REVIEW_SAMPLE.md` (50 entries). Two outcomes:

- **Quality looks usable** → start Phase 3 (separate spec):
  - Add 2nd/3rd SV source (candidates: Apertium swe-eng, Folkets lexikon,
    kaikki_swedish.jsonl)
  - Apply 2-of-N or 3-of-N agreement, POS-aware where possible
  - Build polished `en_sv.json` (overwrites smoke test output)
  - Build `sv_en.json` reverse view
  - Wire site to consume new files
  - Commit + push
- **Quality is bad** → iterate primary source choice. Folkets lexikon is
  a strong candidate (community-curated EN↔SV, lemma-level).

### Files created in Phase 2

- `31_build_en_sv.py` (new)
- `en_sv.json` (prototype, not committed until review passes)
- `EN_SV_REVIEW_SAMPLE.md` (review artifact, gitignored or untracked)
- `../sanakirja/kaikki_english.jsonl` (downloaded source, not in git)

## Verification

### Phase 1
- `python 12_validate_output.py` passes after cleanup
- `git diff data.json` shows only sv/it/fr/de keys removed; no `en`/`fi`
  changes
- Open the site locally, confirm FI↔EN search still works exactly as
  before push `6d8844b`

### Phase 2
- `python 31_build_en_sv.py` runs to completion without errors
- Coverage stats print plausibly (expect 50–80% match rate; <30% would
  be a red flag for source quality)
- Spot-check the 50-sample review file: at least 40 of 50 are obvious
  correct translations
- A few sanity examples render: `stay → stanna`, `book → bok`,
  `to be → vara`, `dog → hund`, `red → röd`

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `kaikki_english.jsonl` is huge — slow stream parse | Use line-by-line JSON parsing (no full-file load); script writes checkpoint as it goes per CLAUDE.md long-running rule |
| Many EN keys missing from kaikki (only common words have translation tables) | Acceptable for smoke test; Phase 3 fills gaps with additional sources |
| Cleanup deletes data we later wish we'd kept | The four columns were 8–14% coverage and acknowledged low quality; the EN↔FI work isn't affected; recoverable via `git show HEAD~:data.json` if needed |
| Future Phase 3 SV sources don't agree well enough for n-of-N gating | Lower the bar to 2/N initially; the FI↔EN expansion shows that even 3/4 yields ~60% noise on first pass without additional gating |

## Out of scope reminders

- **Don't touch FI/EN pipeline**: scripts 05–29, `data.json`'s
  fi/en/fi_rank/pos, `en_fi_data.json`, the FI side's authoritative
  sources in `../sanakirja/`. The cleanup ONLY removes sv/it/fr/de keys.
- **No expansion of the EN base**: the smoke test covers exactly the
  5,246 EN keys already in `en_fi_data.json`. Adding new English
  headwords is a separate concern (Phase 3+).
- **No new languages other than SV**: Italian/German/French come after
  the SV smoke test passes and Phase 3 is shipped.
