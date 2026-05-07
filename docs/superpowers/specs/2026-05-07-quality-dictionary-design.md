# Quality-First Multilingual Dictionary — Design

**Date:** 2026-05-07
**Project:** sanakirja
**Goal:** Replace the current low-quality `data.json` (1,745 rows from `07_assemble.py` with visible noise like `ja → "lso"`) with a quality-first multilingual dataset of ~3,000 Finnish-anchored rows covering FI/EN/SV/IT/FR/DE.

---

## Problem statement

`07_assemble.py` produced semantically wrong matches for top-frequency words. Sample issues:

| FI | EN | Expected |
|---|---|---|
| `ei` | `be not` | `no` / `not` |
| `ja` | `lso` | `and` |
| `se` | `at` | `it` / `that` |
| `hän` | `one` | `he` / `she` |

Root cause: 07's reverse index uses every gloss token from every sense, so noise tokens like `"used"`, `"to"`, `"one"` collide with valid lemmas. The kaikki source data itself is high quality — the assembler was the problem.

## Quality goals (priority order)

1. **Top function/grammar words must be correct** (covered by hand-curated fixture)
2. **Bulk content words** (noun/verb/adj/adv) must have clean single-form translations
3. Coverage target: ~3,000 FI lemmas, each with as many of EN/SV/IT/FR/DE as automation can find at high confidence
4. No filler — empty fields are preferred over wrong fields
5. No machine translation anywhere

## Anchor strategy

**Per-language union, FI as output anchor.** Each non-FI language contributes its native top-N (by its own quality frequency source) → maps to English via that language's kaikki first gloss → maps to Finnish via FI kaikki reverse index. The union of all derived FI lemmas (plus FI's own top-N) becomes the master list.

Rationale (per user): "in languages they reflect their own culture it is ok that we get more words in finnish this way." So we take the most common 1–2k of each language seriously and translate inward to FI.

Concepts without a Finnish equivalent (e.g. English "the") are dropped — no forced matches.

## Architecture

Five new scripts, additive to existing pipeline 01–07.

```
freq lists  ──┐
              ├─→  09  ──→  fi_en_batch_*.json  ──→  10 (HTML)  ──→  fi_en_approved.json  ──┐
kaikki dumps ─┘                                                                              ├─→ 11 ──→ data.json
                                                              fixture.json (hand-curated) ───┘
                                                                                                 │
                                                                                                 └→ 12 (validate)
```

| File | Purpose |
|---|---|
| `08_curate_fixture.py` | validates `fixture.json` |
| `fixture.json` | hand-curated ~90 grammar/function words with all 6 langs filled |
| `09_build_fi_en_pairs.py` | FI↔EN matching, batch generation |
| `fi_en_batch_NN.json` | pre-QC batches of 100 rows |
| `10_qc_server.py` | local HTML QC interface, keyboard + mouse |
| `fi_en_batch_NN_decisions.json` | per-batch user decisions |
| `fi_en_approved.json` | concatenated decisions across batches |
| `11_fill_other_langs.py` | cross-language SV/IT/FR/DE fill |
| `12_validate_output.py` | sanity checks on final `data.json` |
| `data.json` | final output (overwrites existing `[]`) |

Existing `01–07` are unchanged — they produced the inputs we read (`*_top.csv`, kaikki dumps, freq lists).

## Algorithm — FI ↔ EN matching (core quality piece)

### Step 1 — extract EN equivalent from each non-FI lemma

```
take first sense's first gloss
drop parentheticals: "house (building...)" → "house"
take first token before comma/semicolon: "large, big, great" → "large"
KEEP "to " prefix on verbs (so "pelata" → "to play", not "play")
SKIP if gloss starts with: "inflection of", "plural of", "past participle of",
                          "first/second/third-person", "alternative form of",
                          "obsolete form of", "definite singular", "definite plural"
SKIP if POS ∉ {noun, verb, adj, adv}
```

Rationale for keeping "to " on verbs: it's the lemma form throughout (FI `pelata` → EN `to play` → SV `att spela` etc., though SV/IT/FR/DE kaikki entries don't always include their infinitive marker — handled per-language in Step 2). This matches the existing app's display and the validation rule below.

### Step 2 — for each (lang, lemma, pos, EN), find FI candidate

Build FI reverse index (once at script start):

```
For each FI entry in kaikki_finnish.jsonl:
    fi_en := first_gloss_first_token(senses)        # same algorithm as Step 1
    SKIP per same rules as Step 1
    csc_rank := lookup in csc_9996.csv (or None)
    idx[fi_en].append((fi_lemma, fi_pos, csc_rank))
For each fi_en, sort by csc_rank ascending (None last)
```

Lookup:

```
candidates = idx.get(EN, [])
filter to candidates where fi_pos == source_pos    # if source_pos known
pick first (lowest csc_rank wins)
```

### Step 3 — bidirectional verification

After picking `fi_lemma`, recompute its first-gloss-first-token:

| Result | Confidence | Flow |
|---|---|---|
| Equals original `EN` | `auto` | green row, default-approve |
| Differs but `EN` appears in FI's gloss tokens | `review` | yellow row, surface for QC |
| `EN` not in FI's glosses at all | `borderline` | red row, surface for QC, prompt for correction |

### Step 4 — union and dedup

Master FI list = union of `(fi_lemma, fi_pos)` tuples from:
- Each non-FI top-N's derived FI lookups
- FI's own top-N pass (FI lemma → first-gloss → EN, identity-mapped)

Dedup by `(fi_lemma, fi_pos)`. If same `(fi_lemma, fi_pos)` arrives from multiple source langs with conflicting EN candidates, surface to QC for user pick.

Sort by best CSC rank ascending. Lemmas not in CSC sort last (`fi_rank: null`).

### Step 5 — batch into 100-row chunks

`fi_en_batch_01.json` … `fi_en_batch_NN.json`. Each row:

```json
{
  "id": 42,
  "fi": "talo",
  "fi_pos": "noun",
  "en": "house",
  "confidence": "auto",
  "source_lang": "sv",
  "source_lemma": "hus",
  "fi_rank": 75
}
```

Within a batch, order rows by confidence (borderline → review → auto) so the user sees the suspicious cases first.

## QC interface (`10_qc_server.py`)

stdlib `http.server`, ~80 LOC + embedded HTML/JS. Run:

```
python3 10_qc_server.py 1     # opens batch 01 at localhost:8000
```

### Layout

```
Sanakirja FI↔EN QC — Batch 1/N        [reviewed: 0/100]   [Save]

#    FI            POS    EN              source     conf      action
1    olla          verb   [to be       ]  fi         auto      [✓] [✗]
2    talo          noun   [house       ]  sv→hus     auto      [✓] [✗]
3    pelata        verb   [to play     ]  sv→spela   auto      [✓] [✗]
4    juuri         noun   [root        ]  fi         review    [✓] [✗]
5    omituinen     adj    [strange     ]  fi         borderline [✓] [✗]
```

Confidence color-codes the row (auto=green, review=yellow, borderline=red). The EN cell is a pre-filled `<input>`.

### Keyboard

| Key | Effect |
|---|---|
| `Tab` / `Enter` | save current row, advance |
| `Shift+Tab` | go back |
| empty + Enter | approve as-is (default) |
| edit + Enter | record correction |
| `-` + Enter | reject (no FI↔EN equivalent) |

### Mouse

| Action | Effect |
|---|---|
| `[✓]` button | approve as-is (resets input to original) |
| `[✗]` button | reject (clears input, marks `en_final = null`) |
| Click row | focus its input |
| Click input | edit |

Status badges appear after action: green ✓ / red ✗ / blue ✎ (edited).

### Persistence

- Every input change → `localStorage` (survives refresh)
- `Save` button → POST `/save` → server writes `fi_en_batch_NN_decisions.json`
- After save, server prints to stdout: `Approved 87, Edited 9, Rejected 4`

### Decision file

```json
{
  "batch": 1,
  "saved_at": "2026-05-07T11:00:00Z",
  "decisions": [
    {"id": 1, "fi": "olla",      "fi_pos": "verb", "en_final": "be",      "action": "approve"},
    {"id": 5, "fi": "omituinen", "fi_pos": "adj",  "en_final": "weird",   "action": "edit", "en_original": "strange"},
    {"id": 7, "fi": "outo",      "fi_pos": "adj",  "en_final": null,      "action": "reject"}
  ]
}
```

## Hand-curated fixture (`fixture.json`)

~90 entries covering pure grammar/function words and highly irregular content words where automation can't infer the right gloss.

### Coverage

| Category | Count | Examples |
|---|---|---|
| Pronouns | 10 | minä, sinä, hän, me, te, he, se, tämä, tuo, joka |
| Numbers 1–10, 100, 1000 | 12 | yksi, kaksi, kolme, neljä, viisi, kuusi, seitsemän, kahdeksan, yhdeksän, kymmenen, sata, tuhat |
| Conjunctions | 10 | ja, tai, vai, mutta, koska, että, jos, kun, kuin, vaikka |
| Negation/affirmation | 4 | ei, kyllä, niin, ehkä |
| Particles | 10 | myös, vain, jo, vielä, taas, sitten, juuri, eikä, ihan, todella |
| Irregular verbs | 10 | olla, voida, saada, tehdä, tulla, mennä, tietää, antaa, ottaa, panna |
| Adverbs of time | 8 | nyt, eilen, huomenna, tänään, aina, koskaan, usein, joskus |
| Adverbs of place | 6 | täällä, siellä, missä, mihin, mistä, kotona |
| Question words | 8 | kuka, mikä, miksi, milloin, missä, miten, kuinka, montako |
| Quantifiers | 8 | kaikki, jokin, jokainen, mikään, moni, koko, paljon, vähän |

### Format

`fixture.json` — flat JSON list of dicts:

```json
[
  {"fi": "ja",  "fi_pos": "conj",     "en": "and",   "sv": "och",  "it": "e",      "fr": "et",   "de": "und",  "fi_rank": 2},
  {"fi": "ei",  "fi_pos": "particle", "en": "no",    "sv": "nej",  "it": "no",     "fr": "non",  "de": "nein", "fi_rank": 1},
  {"fi": "olla","fi_pos": "verb",     "en": "to be", "sv": "vara", "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
]
```

### Process

1. Claude drafts `fixture.json` from FI top-100 grammar/function/highly-irregular words
2. User reviews the file in editor — flat list, easy to scan
3. Edit any cell, save
4. Run `python3 08_curate_fixture.py` to validate (missing langs, dupes, invalid POS)
5. Commit to git

### Integration with `11_fill_other_langs.py`

- Fixture rows are *authoritative*: if `(fi, fi_pos)` appears in both `fixture.json` and `fi_en_approved.json`, fixture wins
- Fixture entries skip the SV/IT/FR/DE auto-fill step (they already have all 6 langs)

## Cross-language fill (`11_fill_other_langs.py`)

Runs after all batches are QC'd and `fi_en_approved.json` is concatenated.

### Reverse-index construction (once at script start)

```
For each lang in {sv, it, fr}:
    Read <lang>_top.csv
    For each row:
        en_clean := first_gloss_first_token(defs)   # same algorithm as Step 1 above
        SKIP if "inflection of" / "plural of" / etc.
        SKIP if pos ∉ {noun, verb, adj, adv}
        idx[lang][en_clean].append((lemma, pos, rank))
    Sort each idx[lang][en_clean] by rank ascending

For DE: stream kaikki_german.jsonl directly (no top.csv exists)
    Same filtering rules
    No native rank — sort candidates by lemma length ascending (shorter ≈ more common heuristic)
```

### Per-row fill

```
For each {fi, fi_pos, en} in approved master:
    For each lang in {sv, it, fr, de}:
        candidates = idx[lang].get(en, [])
        prefer candidates where pos == fi_pos
        target = candidates[0] if candidates else None
        if target: row[lang] = target.lemma
```

Fixture rows are passed through unchanged.

## Output schema (`data.json`)

```json
[
  {"fi": "olla", "en": "to be", "sv": "vara", "it": "essere", "fr": "être", "de": "sein"},
  {"fi": "ja",   "en": "and",   "sv": "och",  "it": "e",      "fr": "et",   "de": "und"},
  {"fi": "talo", "en": "house", "sv": "hus",  "it": "casa",   "fr": "maison","de": "Haus"},
  {"fi": "kuka", "en": "who",   "sv": "vem",  "it": "chi",    "fr": "qui",  "de": "wer"}
]
```

- Sort: by FI frequency rank ascending (fixture entries get low ranks ~1–100, then approved rows by CSC)
- Missing target lang → key omitted (no `null`s)
- POS not exposed in output (current app doesn't use it)

### Stats `11` prints

```
Total rows: 2,847
With all 6 langs: 1,932 (68%)
EN+FI only: 312 (11%)
Per-lang: SV 2,103  IT 2,210  FR 2,180  DE 2,453
```

## Validation (`12_validate_output.py`)

Hard checks (script exits non-zero on failure):

- No duplicate FI lemma across rows
- Every row has both `fi` and `en` set
- No "inflection of" / "plural of" / "third-person" / "alternative form of" text leaked into any field
- All verbs have `to ` prefix on EN; non-verb fields don't
- No empty strings (use absence instead)
- File parses cleanly as JSON
- Total row count within expected range (1,500 ≤ N ≤ 5,000)

## Dependencies

Already installed:

- `xlrd` (in `.venv.nosync` from prior session) — used by step 06 for `sv_kelly.xls` and `it_m3.xls`. Not needed by 08–12.

stdlib only for everything else: `csv`, `json`, `re`, `os`, `collections`, `http.server`, `urllib.parse`, `socketserver`.

No new installs.

## Workflow

1. Claude drafts `fixture.json` (~90 entries) — user reviews in editor, validates with 08
2. Run `09_build_fi_en_pairs.py` — produces ~30 batches of 100 rows each
3. For each batch: run `10_qc_server.py N`, review in browser, save → `fi_en_batch_NN_decisions.json`
4. After all batches done: `11_fill_other_langs.py` concatenates decisions, applies fixture, fills SV/IT/FR/DE → `data.json`
5. Run `12_validate_output.py` — must pass before publishing
6. Push `data.json` to `lamp2022/testi` for the GitHub Pages app

## Risks and open questions

- **Batch 0 false-positive rate is unknown** — first batch's QC time will tell us whether `auto` is accurate enough to default-approve, or whether the user needs to read every row. If `auto` accuracy < 80%, we'll need to tighten the bidirectional check before generating remaining batches.
- **DE without freq list** — first-match heuristic may pick obscure lemmas. If quality is too low, fallback options (in priority order): (a) re-run script 04 to get structured `{{t|de|word}}` translation tables, (b) fetch a public DE freq list (Leipzig DeReWo top-1000).
- **Multiple source langs converging on conflicting EN for same FI** — e.g. SV and IT both find `tuo`, but with different glosses. Flagged to QC as `borderline` with all candidates listed.
- **Inflection-of leaks** — the kaikki dumps have many such entries; the SKIP list above is the chokepoint. Validation step 12 catches any that slip through.

## Out of scope for this design

- Audio pronunciation
- Sense disambiguation (multiple meanings per FI lemma stored in separate rows)
- Gender markers for nouns (`der/die/das`, `le/la/l'`, `il/la/lo/l'`) — current app doesn't show them; revisit if needed later
- App-side UI changes (column order, search, etc.) — already handled in prior session
- Resuming script `04` (Wiktionary translation tables) — possible follow-up if SV/IT/FR/DE coverage from kaikki is too sparse
