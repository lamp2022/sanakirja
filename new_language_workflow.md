# Adding a New Language to the EN→X Pipeline

Follow these steps in order. Each step is independent — you can stop and resume.

## Step 0: Prerequisites

Before starting:

- `en_fi_data.json` — EN keys source (read-only, do NOT modify)
- `../sanakirja/` — data directory for large downloaded files
- `utils.py` — `gt()` helper for Google Translate

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

### Source priority

```python
# DE: kaikki_german → dict.cc → Apertium → GT → Claude
# IT: kaikki_italian → Apertium → GT → Claude
# FR: kaikki_french → GT → Claude  (no Apertium)
```

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

---

## Known issues to watch per language

- **DE**: Nouns are capitalized — `_norm()` must lowercase before comparison
- **DE**: Separable verbs ("aufmachen" splits to "auf" + "machen") — GT may return unseparated form
- **IT**: Articles attach to consonants (l', lo, la) — strip before frequency lookup
- **FR**: Articles attach similarly (l', du, des) — GT returns "le chien" not "chien"
- **All**: `is_lemma(max_words=4)` filter — drop kaikki example sentences before use
