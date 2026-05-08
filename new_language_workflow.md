# Adding a New Language to the EN→X Pipeline

Follow these steps in order. Each step is independent — you can stop and resume.

## Step 0: Prerequisites

Before starting:

- `en_fi_data.json` — EN keys source (read-only, do NOT modify)
- `../sanakirja/` — data directory for large downloaded files
- `utils.py` — `gt()` helper for Google Translate
- `.venv/` — Python virtualenv with `nltk` and WordNet for POS tagging:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install nltk simplemma
  .venv/bin/python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
  ```

Choose a language code: `de` / `it` / `fr` / `es` / etc.

---

## Step 1: Download frequency list

```bash
LANG=de   # change this
curl -o freq_${LANG}.txt \
  "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/${LANG}/${LANG}_50k.txt"
# Full 50k file → use for pipeline; top 5k already in freq_${LANG}.txt
```

Files: `freq_de.txt`, `freq_it.txt`, `freq_fr.txt` already exist in project root.

---

## Step 2: Download local authoritative source

Choose based on language:

| Language | Source | Command |
|----------|--------|---------|
| **DE** | kaikki.org German dump | `curl -o ../sanakirja/kaikki_german.jsonl 'https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl'` (956MB, may already be on disk) |
| **DE** | dict.cc (preferred secondary) | Download DE-EN CSV from dict.cc bulk download page (free, non-commercial) |
| **IT** | kaikki.org Italian dump | `curl -o ../sanakirja/kaikki_italian.jsonl 'https://kaikki.org/dictionary/Italian/kaikki.org-dictionary-Italian.jsonl'` (~683MB) |
| **FR** | kaikki.org French dump | `curl -o ../sanakirja/kaikki_french.jsonl 'https://kaikki.org/dictionary/French/kaikki.org-dictionary-French.jsonl'` (~496MB) |
| **SV** | Folkets lexikon (done) | already at `../sanakirja/folkets_en_sv.xml` |

Script pattern: create `3N_download_X.py` (e.g. `36_download_de.py`).

---

## Step 3: Run Google Translate checkpoint

Copy the GT checkpoint pattern from `32_build_en_sv.py`. Run it standalone to
pre-fill all 5,246 EN keys before building:

```python
# Checkpoint file: ../sanakirja/gt_en_${LANG}_checkpoint.jsonl
# Pattern: load existing, skip done, call gt(en, "en", LANG), append
```

This takes ~2-3 hours for 5,246 keys. Run once; resumes on interrupt.

---

## Step 4: Get Apertium data (if available)

Check active repos:
- DE: `apertium/apertium-eng-deu` ✓ active
- IT: `apertium/apertium-eng-ita` ✓ active
- FR: `apertium/apertium-eng-fra` ✗ 404 — skip

Parse the `.dix` bilingual dictionary file to extract EN→X translations.
Save as `../sanakirja/apertium_en_${LANG}.json`.

Script: `3N+1_parse_apertium_X.py` (see `35_parse_apertium_sv.py` as template).

---

## Step 5: Build `en_X.json`

Create `3N+2_build_en_X.py` mirroring `32_build_en_sv.py`. Key adaptations:

### Language-specific constants

```python
LANG = "de"          # target language code
LANG_NAME = "German"
FREQ_FILE = f"freq_{LANG}.txt"
GT_LANG = "de"       # Google Translate language code
INFINITIVE_MARKER = "zu "     # DE; "di " IT; "de " FR; "att " SV
```

### Infinitive marker per language

| Language | Infinitive marker | Example |
|----------|-------------------|---------|
| SV | `att ` | att bära |
| DE | bare infinitive (no prefix) or `zu ` | tragen / zu tragen |
| IT | ends in `-are/-ere/-ire` | portare |
| FR | ends in `-er/-ir/-re` | porter |

For DE verb-noun mismatch check: instead of checking `startswith("att ")`,
check that GT returns a bare infinitive form (lowercase, no particle, no article).

### `_norm()` adaptation

```python
# German
def _norm(s):
    s = s.lower().strip()
    if s.startswith("zu "):
        s = s[3:]
    # Strip separable verb particles: an, auf, ab, ein, aus, vor, nach, mit, über, unter, bei
    _DE_PARTICLES = frozenset(["an", "auf", "ab", "ein", "aus", "vor", "nach", "mit", "bei"])
    parts = s.split()
    if len(parts) >= 2 and parts[-1] in _DE_PARTICLES:
        s = " ".join(parts[:-1])
    return s

# Italian
def _norm(s):
    s = s.lower().strip()
    if s.endswith(" si"):    # reflexive suffix
        s = s[:-3]
    return s

# French
def _norm(s):
    s = s.lower().strip()
    if s.startswith("se ") or s.startswith("s'"):
        s = s[3:] if s.startswith("se ") else s[2:]
    return s
```

### Source priority (Apertium DROPPED — see SKILL.md)

```python
# DE: kaikki_german → dict.cc → GT → Claude
# IT: kaikki_italian → GT → Claude
# FR: kaikki_french → GT → Claude
```

Apertium is never used as a translation source. Its swe-eng dump produced
archaic/concatenated junk (`accurately→ackurat`, `gig→harpun`,
`somehow→påettellerannatsätt`). Same risk applies to eng-deu and eng-ita.

### POS-aware lookup (Level 0, before override chain)

The local source (kaikki/dict.cc) tags entries with POS. Use NLTK + WordNet
to determine the dominant English POS, then filter the local source to that
class. Within the chosen POS list, prefer single-word lemmas over multi-word
phrases. See `multilingual-quality-control` skill for the `dominant_en_pos()`
and `select_local_by_pos()` helpers — they're language-agnostic, only the
local source POS class names need adapting (kaikki uses `noun`/`verb`/`adj`,
Folkets uses `nn`/`vb`/`jj`).

### Extras file (`en_X_extras.json`)

Create alongside the main pipeline. Merge at the end of the build:

```json
{
  "extras": [
    {"en": "not", "X": "<not-in-target-lang>", "rank": 25},
    {"en": "from", "X": "<from-in-target-lang>", "rank": 70}
  ],
  "overrides": [{"en": "no", "X": "<correct-form>"}]
}
```

Only add entries you are 100% certain about. Articles, generic determiners,
and context-dependent particles must be skipped.

### Irregular lemma map (`X_irregular_lemmas.json`)

Hand-curated inflection→lemma map for the target language's top irregulars.
Used by site-side search to resolve inflected forms back to dictionary entries.
NOT used during pipeline build. See `sv_irregular_lemmas.json` as template.

Coverage target: top-30 irregular verbs (all conjugated forms), pronoun
object/possessive forms, irregular noun plurals.

### Stats to print

```
Total EN keys:              5246
Has local source match:     XXXX
GT agrees with primary:     XXXX
Claude agrees w/ primary:   XXXX
Apertium agrees w/ primary: XXXX
Consensus override applied: XXXX
GT-secondary promotion:     XXXX
GT-frequency override:      XXXX
Verb-noun mismatch fixed:   XXXX
No match at all:               0
Total emitted:              5246
```

Healthy SV numbers for reference: consensus ~1000, GT-freq ~500, verb-noun ~480.

---

## Step 6: Build `X_en.json` (reverse view)

Copy `33_build_sv_en.py`, change `sv` → language code throughout.
Run: `python3 3N+3_build_X_en.py`

---

## Step 7: Quality check

```bash
# Spot-check 50 entries across rank buckets
python3 -c "
import json, random
data = json.load(open('en_X.json'))
buckets = [e for e in data if e['rank'] <= 100][:10]
buckets += [e for e in data if 100 < e['rank'] <= 500][:10]
buckets += [e for e in data if 500 < e['rank'] <= 2000][:15]
buckets += [e for e in data if e['rank'] > 2000][:15]
for e in buckets:
    print(f'{e[\"rank\"]:>4}  {e[\"en\"]:25} → {str(e.get(\"X\",\"\"))[:30]:30}  [{e[\"confidence\"]}]')
" > EN_X_REVIEW_SAMPLE.md
```

Run frequency validation (from `multilingual-quality-control` skill):
- Target: no common EN words (rank ≤ 200) mapping to absent/rank > 10,000 word

---

## Step 8: Commit

```bash
git add en_X.json X_en.json freq_X.txt
git commit -m "feat: add EN→X pipeline (kaikki/folkets + GT + Apertium)"
git push
```

---

## Script numbering convention

| Scripts | Language |
|---------|----------|
| 30–35 | SV (done) |
| 36–39 | DE (next) |
| 40–43 | IT |
| 44–47 | FR |

## Files to create per new language

| File | Purpose |
|------|---------|
| `freq_X.txt` | Top-5000 freq word list (download from hermitdave/FrequencyWords) |
| `en_X.json` | Built EN→X dictionary |
| `X_en.json` | Reverse view |
| `en_X_extras.json` | High-confidence common-word additions/overrides |
| `X_irregular_lemmas.json` | Hand-curated inflection→lemma map for site search |
| `3N_download_X.py` | Download local source |
| `3N+1_build_en_X.py` | Main pipeline |
| `3N+2_build_X_en.py` | Reverse view |
| `3N+3_write_claude_X.py` | Claude inline data for top-2000 |

---

## Known issues to watch per language

- **DE**: Nouns are capitalized — `_norm()` must lowercase before comparison
- **DE**: Separable verbs ("aufmachen" splits to "auf" + "machen") — GT may return unseparated form
- **IT**: Articles attach to consonants (l', lo, la) — strip before frequency lookup
- **FR**: Articles attach similarly (l', du, des) — GT returns "le chien" not "chien"
- **All**: `is_lemma(max_words=4)` filter — drop kaikki example sentences before use
