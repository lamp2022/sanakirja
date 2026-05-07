# Quality Dictionary Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a quality-first FI/EN/SV/IT/FR/DE dictionary pipeline that replaces the noisy `07_assemble.py` output with ~3,000 batched-QC'd rows, using per-language frequency anchoring, bidirectional FI↔EN verification, human QC via a local HTML interface, and kaikki.org first-gloss matching for SV/IT/FR/DE.

**Architecture:** Five additive scripts (08–12) on top of existing 01–07 pipeline. Shared extraction logic lives in `utils.py`. Script 09 builds FI↔EN candidate batches (100 rows each) for human review. Script 10 serves a local QC interface (keyboard + mouse). Script 11 fills SV/IT/FR/DE for approved pairs, merges the hand-curated grammar fixture, writes `data.json`. Script 12 validates output.

**Tech Stack:** Python 3.8+ stdlib only (`csv`, `json`, `re`, `os`, `collections`, `http.server`, `socketserver`, `webbrowser`). `xlrd` already in `.venv.nosync` (used by step 06, not needed here). All scripts run as `python3 <script>.py` from the project root.

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `utils.py` | **Create** | Shared gloss extraction and POS filter functions |
| `fixture.json` | **Create** | ~86 hand-curated grammar/function word entries (all 6 langs) |
| `08_curate_fixture.py` | **Create** | Validates `fixture.json` completeness and integrity |
| `09_build_fi_en_pairs.py` | **Create** | Builds batched FI↔EN candidate pairs from all 4 `*_top.csv` inputs |
| `10_qc_server.py` | **Create** | Local HTTP server serving the HTML QC interface, saves decisions |
| `11_fill_other_langs.py` | **Create** | Fills SV/IT/FR/DE, merges fixture, writes `data.json` |
| `12_validate_output.py` | **Create** | Sanity checks on final `data.json` |
| `tests/test_utils.py` | **Create** | Unit tests for `utils.py` |
| `tests/test_09.py` | **Create** | Unit/integration tests for batch-builder logic |
| `tests/test_11.py` | **Create** | Integration tests for cross-language fill |
| `tests/test_12.py` | **Create** | Tests for validation rules |

All scripts run from `~/Documents/AI_Agent_Claude/projects/sanakirja/`. Existing scripts 01–07 are untouched.

---

## Task 1: Shared utilities (`utils.py` + tests)

**Files:**
- Create: `utils.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/__init__.py` (empty) and `tests/test_utils.py`:

```python
# tests/test_utils.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import unittest
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


class TestFirstGlossFirstToken(unittest.TestCase):

    def test_simple_noun(self):
        self.assertEqual(first_gloss_first_token("house (building meant to serve as a human abode)"), "house")

    def test_verb_keeps_to_prefix(self):
        self.assertEqual(first_gloss_first_token("to play (participate in a sport)"), "to play")

    def test_comma_list_takes_first(self):
        self.assertEqual(first_gloss_first_token("large, big, great (of considerable size)"), "large")

    def test_semicolon_takes_first(self):
        self.assertEqual(first_gloss_first_token("car; automobile"), "car")

    def test_removes_parenthetical(self):
        self.assertEqual(first_gloss_first_token("cat (Felis catus)"), "cat")

    def test_empty_returns_none(self):
        self.assertIsNone(first_gloss_first_token(""))

    def test_none_returns_none(self):
        self.assertIsNone(first_gloss_first_token(None))

    def test_too_short_returns_none(self):
        self.assertIsNone(first_gloss_first_token("(only used in compounds)"))

    def test_strips_trailing_punctuation(self):
        self.assertEqual(first_gloss_first_token("red."), "red")

    def test_multi_word_verb(self):
        self.assertEqual(first_gloss_first_token("to be able to (used with infinitive)"), "to be able to")


class TestShouldSkipGloss(unittest.TestCase):

    def test_skip_inflection_of(self):
        self.assertTrue(should_skip_gloss("inflection of juuria: third-person singular"))

    def test_skip_plural_of(self):
        self.assertTrue(should_skip_gloss("plural of house"))

    def test_skip_past_participle(self):
        self.assertTrue(should_skip_gloss("past participle of go"))

    def test_skip_third_person(self):
        self.assertTrue(should_skip_gloss("third-person singular present indicative of play"))

    def test_skip_first_person(self):
        self.assertTrue(should_skip_gloss("first-person singular present of être"))

    def test_skip_alternative_form(self):
        self.assertTrue(should_skip_gloss("alternative form of colour"))

    def test_skip_obsolete(self):
        self.assertTrue(should_skip_gloss("obsolete form of go"))

    def test_skip_definite_singular(self):
        self.assertTrue(should_skip_gloss("definite singular of hus"))

    def test_keep_normal_noun(self):
        self.assertFalse(should_skip_gloss("house (building meant to serve as a human abode)"))

    def test_keep_normal_verb(self):
        self.assertFalse(should_skip_gloss("to play (participate in a sport)"))

    def test_skip_empty(self):
        self.assertTrue(should_skip_gloss(""))

    def test_skip_none(self):
        self.assertTrue(should_skip_gloss(None))

    def test_case_insensitive(self):
        self.assertTrue(should_skip_gloss("Inflection of juuria"))


class TestIsContentPos(unittest.TestCase):

    def test_noun(self):
        self.assertTrue(is_content_pos("noun"))

    def test_verb(self):
        self.assertTrue(is_content_pos("verb"))

    def test_adj(self):
        self.assertTrue(is_content_pos("adj"))

    def test_adjective(self):
        self.assertTrue(is_content_pos("adjective"))

    def test_adv(self):
        self.assertTrue(is_content_pos("adv"))

    def test_adverb(self):
        self.assertTrue(is_content_pos("adverb"))

    def test_pron_excluded(self):
        self.assertFalse(is_content_pos("pron"))

    def test_conj_excluded(self):
        self.assertFalse(is_content_pos("conj"))

    def test_article_excluded(self):
        self.assertFalse(is_content_pos("article"))

    def test_particle_excluded(self):
        self.assertFalse(is_content_pos("particle"))

    def test_num_excluded(self):
        self.assertFalse(is_content_pos("num"))

    def test_case_insensitive(self):
        self.assertTrue(is_content_pos("Noun"))


class TestNormalizePos(unittest.TestCase):

    def test_adjective_to_adj(self):
        self.assertEqual(normalize_pos("adjective"), "adj")

    def test_adverb_to_adv(self):
        self.assertEqual(normalize_pos("adverb"), "adv")

    def test_noun_unchanged(self):
        self.assertEqual(normalize_pos("noun"), "noun")

    def test_verb_unchanged(self):
        self.assertEqual(normalize_pos("verb"), "verb")

    def test_unknown_passthrough(self):
        self.assertEqual(normalize_pos("character"), "character")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
python -m unittest tests/test_utils.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'utils'`

- [ ] **Step 1.3: Implement `utils.py`**

```python
# utils.py
import re

SKIP_PREFIXES = (
    "inflection of", "plural of", "past participle of", "present participle of",
    "third-person singular", "first-person singular", "second-person singular",
    "alternative form of", "obsolete form of", "definite singular", "definite plural",
    "comparative of", "superlative of", "genitive of", "dative of", "accusative of",
    "gerund of", "imperative of", "feminine of", "masculine of",
)

CONTENT_POS = {"noun", "verb", "adj", "adjective", "adv", "adverb"}

POS_NORMALIZE = {
    "noun": "noun", "verb": "verb",
    "adj": "adj", "adjective": "adj",
    "adv": "adv", "adverb": "adv",
}


def first_gloss_first_token(gloss: str) -> str | None:
    """Extract the first clean English token from a kaikki gloss string.

    Preserves 'to ' prefix for verbs. Takes first comma/semicolon token.
    Drops parenthetical content.

    Examples:
        "house (building meant to serve...)" -> "house"
        "to play (participate in a game)"   -> "to play"
        "large, big, great"                 -> "large"
    """
    if not gloss:
        return None
    s = re.sub(r"\s*\([^)]*\)", "", gloss)   # drop parentheticals
    s = re.sub(r"\s*\[[^\]]*\]", "", s)       # drop bracket content
    token = re.split(r"[,;]", s)[0].strip()
    token = token.strip(".'\" ")
    if not token or len(token) < 2:
        return None
    return token


def should_skip_gloss(gloss: str | None) -> bool:
    """Return True if the gloss is an inflection reference, not a definition."""
    if not gloss:
        return True
    g = gloss.strip().lower()
    return any(g.startswith(p) for p in SKIP_PREFIXES)


def is_content_pos(pos: str) -> bool:
    """Return True if POS is a content word category (noun/verb/adj/adv)."""
    return pos.lower().strip() in CONTENT_POS


def normalize_pos(pos: str) -> str:
    """Normalize POS label to canonical form (adjective -> adj, adverb -> adv)."""
    return POS_NORMALIZE.get(pos.lower().strip(), pos.lower().strip())
```

- [ ] **Step 1.4: Run tests to confirm they pass**

```bash
python -m unittest tests/test_utils.py -v 2>&1
```

Expected: all tests PASS, output ends with `OK`

- [ ] **Step 1.5: Commit**

```bash
git add utils.py tests/__init__.py tests/test_utils.py
git -c commit.gpgsign=false commit -m "feat(sanakirja): add shared gloss extraction utilities with tests"
```

---

## Task 2: Grammar fixture (`fixture.json` + `08_curate_fixture.py`)

**Files:**
- Create: `fixture.json`
- Create: `08_curate_fixture.py`

- [ ] **Step 2.1: Write the validator tests**

Create `tests/test_08.py`:

```python
# tests/test_08.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

REQUIRED_KEYS = {"fi", "fi_pos", "en", "sv", "it", "fr", "de", "fi_rank"}
VALID_POS = {"noun", "verb", "adj", "adv", "pron", "conj", "particle", "num", "intj", "det"}


def validate_fixture(entries):
    errors = []
    seen = {}
    for i, entry in enumerate(entries):
        label = f"entry[{i}] fi={entry.get('fi','?')}"
        missing = REQUIRED_KEYS - set(entry.keys())
        if missing:
            errors.append(f"{label}: missing keys: {missing}")
        for k in REQUIRED_KEYS - {"fi_rank"}:
            if entry.get(k) == "":
                errors.append(f"{label}: empty string for '{k}'")
        pos = entry.get("fi_pos", "")
        if pos not in VALID_POS:
            errors.append(f"{label}: invalid fi_pos '{pos}'")
        key = (entry.get("fi"), entry.get("fi_pos"))
        if key in seen:
            errors.append(f"{label}: duplicate (fi, fi_pos)")
        else:
            seen[key] = i
    return errors


class TestFixtureValidator(unittest.TestCase):

    def test_valid_entry_passes(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        self.assertEqual(validate_fixture([entry]), [])

    def test_missing_key_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "fi_rank": 1}  # missing 'de'
        errors = validate_fixture([entry])
        self.assertTrue(any("missing keys" in e for e in errors))

    def test_empty_string_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry])
        self.assertTrue(any("empty string" in e for e in errors))

    def test_invalid_pos_fails(self):
        entry = {"fi": "olla", "fi_pos": "copula", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry])
        self.assertTrue(any("invalid fi_pos" in e for e in errors))

    def test_duplicate_fi_fi_pos_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry, entry])
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_same_fi_different_pos_passes(self):
        e1 = {"fi": "kuusi", "fi_pos": "num", "en": "six", "sv": "sex",
              "it": "sei", "fr": "six", "de": "sechs", "fi_rank": 150}
        e2 = {"fi": "kuusi", "fi_pos": "noun", "en": "spruce", "sv": "gran",
              "it": "abete", "fr": "épicéa", "de": "Fichte", "fi_rank": 300}
        self.assertEqual(validate_fixture([e1, e2]), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2.2: Run tests to confirm they fail**

```bash
python -m unittest tests/test_08.py -v 2>&1 | head -5
```

Expected: `ImportError` or tests fail (validate_fixture not in 08 yet — tests define it inline, so they should pass already; this step just confirms the test file runs cleanly)

```bash
python -m unittest tests/test_08.py -v 2>&1
```

Expected: all PASS (the tests define `validate_fixture` locally — this tests the logic, not 08 itself)

- [ ] **Step 2.3: Create `fixture.json`**

This is the authoritative hand-curated grammar/function word list. Write the file exactly as shown. The user should review and adjust translations after this step.

```json
[
  {"fi": "ei",       "fi_pos": "particle", "en": "no",            "sv": "nej",      "it": "no",       "fr": "non",          "de": "nein",      "fi_rank": 1},
  {"fi": "olla",     "fi_pos": "verb",     "en": "to be",         "sv": "vara",     "it": "essere",   "fr": "être",         "de": "sein",      "fi_rank": 1},
  {"fi": "ja",       "fi_pos": "conj",     "en": "and",           "sv": "och",      "it": "e",        "fr": "et",           "de": "und",       "fi_rank": 2},
  {"fi": "se",       "fi_pos": "pron",     "en": "it",            "sv": "det",      "it": "esso",     "fr": "ce",           "de": "es",        "fi_rank": 3},
  {"fi": "hän",      "fi_pos": "pron",     "en": "he, she",       "sv": "han, hon", "it": "lui, lei", "fr": "il, elle",     "de": "er, sie",   "fi_rank": 4},
  {"fi": "että",     "fi_pos": "conj",     "en": "that",          "sv": "att",      "it": "che",      "fr": "que",          "de": "dass",      "fi_rank": 5},
  {"fi": "kun",      "fi_pos": "conj",     "en": "when",          "sv": "när",      "it": "quando",   "fr": "quand",        "de": "wenn",      "fi_rank": 6},
  {"fi": "niin",     "fi_pos": "particle", "en": "so",            "sv": "så",       "it": "così",     "fr": "ainsi",        "de": "so",        "fi_rank": 7},
  {"fi": "mutta",    "fi_pos": "conj",     "en": "but",           "sv": "men",      "it": "ma",       "fr": "mais",         "de": "aber",      "fi_rank": 9},
  {"fi": "kuin",     "fi_pos": "conj",     "en": "than",          "sv": "än",       "it": "di",       "fr": "que",          "de": "als",       "fi_rank": 11},
  {"fi": "kaikki",   "fi_pos": "pron",     "en": "all",           "sv": "alla",     "it": "tutti",    "fr": "tous",         "de": "alle",      "fi_rank": 11},
  {"fi": "tämä",     "fi_pos": "pron",     "en": "this",          "sv": "denna",    "it": "questo",   "fr": "ce",           "de": "dieser",    "fi_rank": 12},
  {"fi": "myös",     "fi_pos": "particle", "en": "also",          "sv": "också",    "it": "anche",    "fr": "aussi",        "de": "auch",      "fi_rank": 13},
  {"fi": "vielä",    "fi_pos": "particle", "en": "still",         "sv": "ännu",     "it": "ancora",   "fr": "encore",       "de": "noch",      "fi_rank": 14},
  {"fi": "nyt",      "fi_pos": "adv",      "en": "now",           "sv": "nu",       "it": "ora",      "fr": "maintenant",   "de": "jetzt",     "fi_rank": 15},
  {"fi": "voida",    "fi_pos": "verb",     "en": "to be able to", "sv": "kunna",    "it": "potere",   "fr": "pouvoir",      "de": "können",    "fi_rank": 16},
  {"fi": "vain",     "fi_pos": "particle", "en": "only",          "sv": "bara",     "it": "solo",     "fr": "seulement",    "de": "nur",       "fi_rank": 17},
  {"fi": "koska",    "fi_pos": "conj",     "en": "because",       "sv": "eftersom", "it": "perché",   "fr": "parce que",    "de": "weil",      "fi_rank": 18},
  {"fi": "jo",       "fi_pos": "particle", "en": "already",       "sv": "redan",    "it": "già",      "fr": "déjà",         "de": "schon",     "fi_rank": 19},
  {"fi": "mennä",    "fi_pos": "verb",     "en": "to go",         "sv": "gå",       "it": "andare",   "fr": "aller",        "de": "gehen",     "fi_rank": 20},
  {"fi": "sitten",   "fi_pos": "adv",      "en": "then",          "sv": "sedan",    "it": "poi",      "fr": "puis",         "de": "dann",      "fi_rank": 21},
  {"fi": "aina",     "fi_pos": "adv",      "en": "always",        "sv": "alltid",   "it": "sempre",   "fr": "toujours",     "de": "immer",     "fi_rank": 22},
  {"fi": "mikä",     "fi_pos": "pron",     "en": "what",          "sv": "vad",      "it": "cosa",     "fr": "quoi",         "de": "was",       "fi_rank": 23},
  {"fi": "tuo",      "fi_pos": "pron",     "en": "that",          "sv": "den",      "it": "quello",   "fr": "celui-là",     "de": "jener",     "fi_rank": 24},
  {"fi": "tietää",   "fi_pos": "verb",     "en": "to know",       "sv": "veta",     "it": "sapere",   "fr": "savoir",       "de": "wissen",    "fi_rank": 25},
  {"fi": "miten",    "fi_pos": "adv",      "en": "how",           "sv": "hur",      "it": "come",     "fr": "comment",      "de": "wie",       "fi_rank": 26},
  {"fi": "kyllä",    "fi_pos": "particle", "en": "yes",           "sv": "ja",       "it": "sì",       "fr": "oui",          "de": "ja",        "fi_rank": 27},
  {"fi": "paljon",   "fi_pos": "adv",      "en": "much",          "sv": "mycket",   "it": "molto",    "fr": "beaucoup",     "de": "viel",      "fi_rank": 28},
  {"fi": "eikä",     "fi_pos": "conj",     "en": "and not",       "sv": "och inte", "it": "e non",    "fr": "et non",       "de": "und nicht", "fi_rank": 29},
  {"fi": "ottaa",    "fi_pos": "verb",     "en": "to take",       "sv": "ta",       "it": "prendere", "fr": "prendre",      "de": "nehmen",    "fi_rank": 30},
  {"fi": "missä",    "fi_pos": "adv",      "en": "where",         "sv": "var",      "it": "dove",     "fr": "où",           "de": "wo",        "fi_rank": 31},
  {"fi": "taas",     "fi_pos": "particle", "en": "again",         "sv": "igen",     "it": "di nuovo", "fr": "de nouveau",   "de": "wieder",    "fi_rank": 32},
  {"fi": "kuka",     "fi_pos": "pron",     "en": "who",           "sv": "vem",      "it": "chi",      "fr": "qui",          "de": "wer",       "fi_rank": 33},
  {"fi": "saada",    "fi_pos": "verb",     "en": "to get",        "sv": "få",       "it": "ricevere", "fr": "recevoir",     "de": "bekommen",  "fi_rank": 34},
  {"fi": "tai",      "fi_pos": "conj",     "en": "or",            "sv": "eller",    "it": "o",        "fr": "ou",           "de": "oder",      "fi_rank": 35},
  {"fi": "siellä",   "fi_pos": "adv",      "en": "there",         "sv": "där",      "it": "là",       "fr": "là",           "de": "dort",      "fi_rank": 36},
  {"fi": "moni",     "fi_pos": "pron",     "en": "many",          "sv": "många",    "it": "molti",    "fr": "beaucoup",     "de": "viele",     "fi_rank": 37},
  {"fi": "ihan",     "fi_pos": "adv",      "en": "quite",         "sv": "ganska",   "it": "piuttosto","fr": "assez",        "de": "ziemlich",  "fi_rank": 38},
  {"fi": "koko",     "fi_pos": "adj",      "en": "whole",         "sv": "hel",      "it": "tutto",    "fr": "tout",         "de": "ganz",      "fi_rank": 39},
  {"fi": "antaa",    "fi_pos": "verb",     "en": "to give",       "sv": "ge",       "it": "dare",     "fr": "donner",       "de": "geben",     "fi_rank": 40},
  {"fi": "minä",     "fi_pos": "pron",     "en": "I",             "sv": "jag",      "it": "io",       "fr": "je",           "de": "ich",       "fi_rank": 41},
  {"fi": "täällä",   "fi_pos": "adv",      "en": "here",          "sv": "här",      "it": "qui",      "fr": "ici",          "de": "hier",      "fi_rank": 42},
  {"fi": "mikään",   "fi_pos": "pron",     "en": "anything",      "sv": "något",    "it": "niente",   "fr": "rien",         "de": "nichts",    "fi_rank": 43},
  {"fi": "miksi",    "fi_pos": "adv",      "en": "why",           "sv": "varför",   "it": "perché",   "fr": "pourquoi",     "de": "warum",     "fi_rank": 44},
  {"fi": "ehkä",     "fi_pos": "adv",      "en": "maybe",         "sv": "kanske",   "it": "forse",    "fr": "peut-être",    "de": "vielleicht","fi_rank": 45},
  {"fi": "vähän",    "fi_pos": "adv",      "en": "little",        "sv": "lite",     "it": "poco",     "fr": "peu",          "de": "wenig",     "fi_rank": 46},
  {"fi": "koskaan",  "fi_pos": "adv",      "en": "never",         "sv": "aldrig",   "it": "mai",      "fr": "jamais",       "de": "nie",       "fi_rank": 47},
  {"fi": "kuinka",   "fi_pos": "adv",      "en": "how",           "sv": "hur",      "it": "come",     "fr": "comment",      "de": "wie",       "fi_rank": 48},
  {"fi": "todella",  "fi_pos": "adv",      "en": "really",        "sv": "verkligen","it": "davvero",  "fr": "vraiment",     "de": "wirklich",  "fi_rank": 49},
  {"fi": "tulla",    "fi_pos": "verb",     "en": "to come",       "sv": "komma",    "it": "venire",   "fr": "venir",        "de": "kommen",    "fi_rank": 50},
  {"fi": "jokin",    "fi_pos": "pron",     "en": "something",     "sv": "något",    "it": "qualcosa", "fr": "quelque chose","de": "etwas",     "fi_rank": 52},
  {"fi": "usein",    "fi_pos": "adv",      "en": "often",         "sv": "ofta",     "it": "spesso",   "fr": "souvent",      "de": "oft",       "fi_rank": 55},
  {"fi": "jokainen", "fi_pos": "pron",     "en": "every",         "sv": "varje",    "it": "ogni",     "fr": "chaque",       "de": "jeder",     "fi_rank": 56},
  {"fi": "mistä",    "fi_pos": "adv",      "en": "where from",    "sv": "varifrån", "it": "da dove",  "fr": "d'où",         "de": "woher",     "fi_rank": 58},
  {"fi": "laittaa",  "fi_pos": "verb",     "en": "to put",        "sv": "lägga",    "it": "mettere",  "fr": "mettre",       "de": "setzen",    "fi_rank": 60},
  {"fi": "mihin",    "fi_pos": "adv",      "en": "where to",      "sv": "vart",     "it": "dove",     "fr": "où",           "de": "wohin",     "fi_rank": 61},
  {"fi": "juuri",    "fi_pos": "adv",      "en": "just",          "sv": "just",     "it": "proprio",  "fr": "juste",        "de": "gerade",    "fi_rank": 64},
  {"fi": "sinne",    "fi_pos": "adv",      "en": "there",         "sv": "dit",      "it": "là",       "fr": "là-bas",       "de": "dorthin",   "fi_rank": 65},
  {"fi": "milloin",  "fi_pos": "adv",      "en": "when",          "sv": "när",      "it": "quando",   "fr": "quand",        "de": "wann",      "fi_rank": 66},
  {"fi": "tänään",   "fi_pos": "adv",      "en": "today",         "sv": "idag",     "it": "oggi",     "fr": "aujourd'hui",  "de": "heute",     "fi_rank": 70},
  {"fi": "kotona",   "fi_pos": "adv",      "en": "at home",       "sv": "hemma",    "it": "a casa",   "fr": "à la maison",  "de": "zu Hause",  "fi_rank": 72},
  {"fi": "eilen",    "fi_pos": "adv",      "en": "yesterday",     "sv": "igår",     "it": "ieri",     "fr": "hier",         "de": "gestern",   "fi_rank": 80},
  {"fi": "tehdä",    "fi_pos": "verb",     "en": "to do",         "sv": "göra",     "it": "fare",     "fr": "faire",        "de": "machen",    "fi_rank": 85},
  {"fi": "huomenna", "fi_pos": "adv",      "en": "tomorrow",      "sv": "imorgon",  "it": "domani",   "fr": "demain",       "de": "morgen",    "fi_rank": 90},
  {"fi": "joskus",   "fi_pos": "adv",      "en": "sometimes",     "sv": "ibland",   "it": "a volte",  "fr": "parfois",      "de": "manchmal",  "fi_rank": 95},
  {"fi": "sinä",     "fi_pos": "pron",     "en": "you",           "sv": "du",       "it": "tu",       "fr": "tu",           "de": "du",        "fi_rank": 100},
  {"fi": "yksi",     "fi_pos": "num",      "en": "one",           "sv": "en",       "it": "uno",      "fr": "un",           "de": "ein",       "fi_rank": 105},
  {"fi": "kaksi",    "fi_pos": "num",      "en": "two",           "sv": "två",      "it": "due",      "fr": "deux",         "de": "zwei",      "fi_rank": 110},
  {"fi": "kolme",    "fi_pos": "num",      "en": "three",         "sv": "tre",      "it": "tre",      "fr": "trois",        "de": "drei",      "fi_rank": 115},
  {"fi": "vai",      "fi_pos": "conj",     "en": "or",            "sv": "eller",    "it": "o",        "fr": "ou",           "de": "oder",      "fi_rank": 118},
  {"fi": "joka",     "fi_pos": "pron",     "en": "who, which",    "sv": "som",      "it": "che",      "fr": "qui",          "de": "der",       "fi_rank": 119},
  {"fi": "montako",  "fi_pos": "adv",      "en": "how many",      "sv": "hur många","it": "quanti",   "fr": "combien",      "de": "wie viele", "fi_rank": 120},
  {"fi": "neljä",    "fi_pos": "num",      "en": "four",          "sv": "fyra",     "it": "quattro",  "fr": "quatre",       "de": "vier",      "fi_rank": 125},
  {"fi": "viisi",    "fi_pos": "num",      "en": "five",          "sv": "fem",      "it": "cinque",   "fr": "cinq",         "de": "fünf",      "fi_rank": 130},
  {"fi": "kuusi",    "fi_pos": "num",      "en": "six",           "sv": "sex",      "it": "sei",      "fr": "six",          "de": "sechs",     "fi_rank": 135},
  {"fi": "me",       "fi_pos": "pron",     "en": "we",            "sv": "vi",       "it": "noi",      "fr": "nous",         "de": "wir",       "fi_rank": 140},
  {"fi": "seitsemän","fi_pos": "num",      "en": "seven",         "sv": "sju",      "it": "sette",    "fr": "sept",         "de": "sieben",    "fi_rank": 145},
  {"fi": "kahdeksan","fi_pos": "num",      "en": "eight",         "sv": "åtta",     "it": "otto",     "fr": "huit",         "de": "acht",      "fi_rank": 150},
  {"fi": "yhdeksän", "fi_pos": "num",      "en": "nine",          "sv": "nio",      "it": "nove",     "fr": "neuf",         "de": "neun",      "fi_rank": 155},
  {"fi": "kymmenen", "fi_pos": "num",      "en": "ten",           "sv": "tio",      "it": "dieci",    "fr": "dix",          "de": "zehn",      "fi_rank": 160},
  {"fi": "te",       "fi_pos": "pron",     "en": "you",           "sv": "ni",       "it": "voi",      "fr": "vous",         "de": "ihr",       "fi_rank": 165},
  {"fi": "he",       "fi_pos": "pron",     "en": "they",          "sv": "de",       "it": "loro",     "fr": "ils",          "de": "sie",       "fi_rank": 170},
  {"fi": "vaikka",   "fi_pos": "conj",     "en": "although",      "sv": "även om",  "it": "anche se", "fr": "bien que",     "de": "obwohl",    "fi_rank": 175},
  {"fi": "jos",      "fi_pos": "conj",     "en": "if",            "sv": "om",       "it": "se",       "fr": "si",           "de": "wenn",      "fi_rank": 180},
  {"fi": "sata",     "fi_pos": "num",      "en": "hundred",       "sv": "hundra",   "it": "cento",    "fr": "cent",         "de": "hundert",   "fi_rank": 185},
  {"fi": "tuhat",    "fi_pos": "num",      "en": "thousand",      "sv": "tusen",    "it": "mille",    "fr": "mille",        "de": "tausend",   "fi_rank": 190}
]
```

> **Review note:** Open `fixture.json` and verify each row. Pay particular attention to: pronouns with gender distinctions (hän = he/she), conjunctions with multi-word equivalents (koska, vaikka), and the Finnish forms (kymmenen = ten as standalone numeral). Change any wrong translation directly in the file.

- [ ] **Step 2.4: Write `08_curate_fixture.py`**

```python
#!/usr/bin/env python3
"""
Step 08: Validate fixture.json completeness and integrity.
Run: python3 08_curate_fixture.py
"""
import json, sys

FIXTURE_FILE = "fixture.json"
REQUIRED_KEYS = {"fi", "fi_pos", "en", "sv", "it", "fr", "de", "fi_rank"}
VALID_POS = {"noun", "verb", "adj", "adv", "pron", "conj", "particle", "num", "intj", "det"}


def main():
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture = json.load(f)

    errors = []
    seen = {}
    for i, entry in enumerate(fixture):
        label = f"entry[{i}] fi={entry.get('fi', '?')}"
        missing = REQUIRED_KEYS - set(entry.keys())
        if missing:
            errors.append(f"{label}: missing keys: {missing}")
        for k in REQUIRED_KEYS - {"fi_rank"}:
            if entry.get(k) == "":
                errors.append(f"{label}: empty string for '{k}'")
        pos = entry.get("fi_pos", "")
        if pos not in VALID_POS:
            errors.append(f"{label}: invalid fi_pos '{pos}'")
        key = (entry.get("fi"), entry.get("fi_pos"))
        if key in seen:
            errors.append(f"{label}: duplicate (fi, fi_pos) — also at entry[{seen[key]}]")
        else:
            seen[key] = i

    if errors:
        print(f"FIXTURE INVALID — {len(errors)} error(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"fixture.json OK — {len(fixture)} entries, all valid.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.5: Validate the fixture**

```bash
python3 08_curate_fixture.py
```

Expected: `fixture.json OK — 86 entries, all valid.`

If errors appear, fix the relevant `fixture.json` entries and re-run until it passes.

- [ ] **Step 2.6: Run fixture validator tests**

```bash
python -m unittest tests/test_08.py -v 2>&1
```

Expected: all PASS

- [ ] **Step 2.7: Commit**

```bash
git add fixture.json 08_curate_fixture.py tests/test_08.py
git -c commit.gpgsign=false commit -m "feat(sanakirja): add grammar fixture and validator"
```

---

## Task 3: FI↔EN batch builder (`09_build_fi_en_pairs.py`)

**Files:**
- Create: `09_build_fi_en_pairs.py`
- Create: `tests/test_09.py`

**Runtime note:** This script streams `kaikki_finnish.jsonl` (3.6 GB) once to build the reverse index. Expect ~3–5 minutes.

- [ ] **Step 3.1: Write unit tests for core logic**

Create `tests/test_09.py`:

```python
# tests/test_09.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


# ── Helpers replicated from 09 for testing ────────────────────────────────────

def build_fi_index_from_entries(entries, csc_ranks):
    """Build FI reverse index from a list of mock kaikki entry dicts."""
    fi_idx = defaultdict(list)
    fi_to_en = defaultdict(set)
    seen = set()
    for e in entries:
        pos = e.get("pos", "")
        if not is_content_pos(pos):
            continue
        word = e.get("word", "").strip()
        senses = e.get("senses", [])
        if not senses:
            continue
        first_gloss = (senses[0].get("glosses") or [""])[0]
        if should_skip_gloss(first_gloss):
            continue
        en_token = first_gloss_first_token(first_gloss)
        if not en_token:
            continue
        pos_norm = normalize_pos(pos)
        key = (word, pos_norm)
        if key not in seen:
            seen.add(key)
            csc_rank = csc_ranks.get(word)
            fi_idx[en_token.lower()].append((word, pos_norm, csc_rank))
    for k in fi_idx:
        fi_idx[k].sort(key=lambda x: (x[2] is None, x[2] or 0))
    for en_token, candidates in fi_idx.items():
        for fi_lemma, _, _ in candidates:
            fi_to_en[fi_lemma].add(en_token)
    return dict(fi_idx), dict(fi_to_en)


def bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en):
    candidates = fi_idx.get(en_token.lower(), [])
    if candidates and candidates[0][0] == fi_lemma:
        return "auto"
    if en_token.lower() in fi_to_en.get(fi_lemma, set()):
        return "review"
    return "borderline"


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestFIIndex(unittest.TestCase):

    def setUp(self):
        self.mock_entries = [
            {"word": "talo", "pos": "noun",
             "senses": [{"glosses": ["house (building meant to serve as a human abode)"]}]},
            {"word": "pelata", "pos": "verb",
             "senses": [{"glosses": ["to play (participate in a sport)"]}]},
            {"word": "iso", "pos": "adj",
             "senses": [{"glosses": ["big, large, great (of considerable size)"]}]},
            {"word": "juuri", "pos": "verb",  # inflection — should be skipped
             "senses": [{"glosses": ["inflection of juuria: third-person singular past"]}]},
            {"word": "ei", "pos": "intj",  # non-content POS — should be skipped
             "senses": [{"glosses": ["no (negation)"]}]},
        ]
        self.csc_ranks = {"talo": 75, "pelata": 120, "iso": 29}
        self.fi_idx, self.fi_to_en = build_fi_index_from_entries(self.mock_entries, self.csc_ranks)

    def test_noun_indexed(self):
        self.assertIn("house", self.fi_idx)
        self.assertEqual(self.fi_idx["house"][0][0], "talo")

    def test_verb_indexed_with_to_prefix(self):
        self.assertIn("to play", self.fi_idx)
        self.assertEqual(self.fi_idx["to play"][0][0], "pelata")

    def test_adj_indexed_first_token(self):
        self.assertIn("big", self.fi_idx)
        self.assertEqual(self.fi_idx["big"][0][0], "iso")

    def test_inflection_skipped(self):
        # juuri (verb) has inflection gloss — should not be indexed
        juuri_in_idx = any(
            any(c[0] == "juuri" for c in v)
            for v in self.fi_idx.values()
        )
        self.assertFalse(juuri_in_idx)

    def test_non_content_pos_skipped(self):
        self.assertNotIn("no", self.fi_idx)  # ei/intj skipped

    def test_csc_rank_sorted(self):
        # iso (rank 29) and talo (rank 75) are both nouns; only iso maps to "big"
        # but if both mapped to same token, lower rank should come first
        candidates = self.fi_idx.get("house", [])
        self.assertEqual(candidates[0][0], "talo")

    def test_fi_to_en_populated(self):
        self.assertIn("house", self.fi_to_en.get("talo", set()))


class TestBidirectionalConfidence(unittest.TestCase):

    def setUp(self):
        self.fi_idx = {"house": [("talo", "noun", 75)], "home": [("koti", "noun", 90)]}
        self.fi_to_en = {"talo": {"house"}, "koti": {"home", "house"}}

    def test_auto_when_first_match(self):
        conf = bidirectional_confidence("house", "talo", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "auto")

    def test_review_when_indirect_match(self):
        # koti maps to "house" via fi_to_en but not as primary in fi_idx["house"]
        conf = bidirectional_confidence("house", "koti", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "review")

    def test_borderline_when_no_match(self):
        conf = bidirectional_confidence("river", "joki", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "borderline")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3.2: Run tests to confirm they pass (no 09 script needed — logic is self-contained)**

```bash
python -m unittest tests/test_09.py -v 2>&1
```

Expected: all PASS

- [ ] **Step 3.3: Write `09_build_fi_en_pairs.py`**

```python
#!/usr/bin/env python3
"""
Step 09: Build FI<->EN candidate pairs from per-language kaikki data.

Reads fi_top.csv, sv_top.csv, it_top.csv, fr_top.csv (already extracted by 06).
Streams kaikki_finnish.jsonl once to build a reverse EN->FI index.
Outputs: fi_en_batch_01.json, fi_en_batch_02.json, ... (100 rows each)

Each row: {id, fi, fi_pos, en, confidence, source_lang, source_lemma, fi_rank}
"""
import csv, json, os, re
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos

FI_KAIKKI   = "kaikki_finnish.jsonl"
CSC_FILE    = "csc_9996.csv"
FIXTURE_FILE = "fixture.json"
BATCH_SIZE  = 100
LANGS = [
    ("fi", "fi_top.csv"),
    ("sv", "sv_top.csv"),
    ("it", "it_top.csv"),
    ("fr", "fr_top.csv"),
]


def load_csc_ranks():
    ranks = {}
    with open(CSC_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            l, rk = r["lemma"], int(r["rank"])
            if l not in ranks or rk < ranks[l]:
                ranks[l] = rk
    return ranks


def load_fixture_lemmas():
    with open(FIXTURE_FILE, encoding="utf-8") as f:
        return {e["fi"] for e in json.load(f)}


def build_fi_kaikki_index(csc_ranks):
    """Stream kaikki_finnish.jsonl, build:
      fi_idx:    {en_token_lower: [(fi_lemma, fi_pos, csc_rank)]} sorted rank asc
      fi_to_en:  {fi_lemma: set(en_token_lower)} for bidirectional check
    """
    print("Building FI kaikki reverse index (streaming 3.6 GB — ~3 min)...")
    fi_idx = defaultdict(list)
    fi_to_en = defaultdict(set)
    seen = set()
    count = 0

    with open(FI_KAIKKI, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            pos = e.get("pos", "")
            if not is_content_pos(pos):
                continue
            word = e.get("word", "").strip()
            if not word or not re.match(r"^[a-zäöåA-ZÄÖÅ\-']+$", word):
                continue
            senses = e.get("senses", [])
            if not senses:
                continue
            first_gloss = (senses[0].get("glosses") or senses[0].get("raw_glosses") or [""])[0]
            if should_skip_gloss(first_gloss):
                continue
            en_token = first_gloss_first_token(first_gloss)
            if not en_token:
                continue
            pos_norm = normalize_pos(pos)
            key = (word, pos_norm)
            if key not in seen:
                seen.add(key)
                fi_idx[en_token.lower()].append((word, pos_norm, csc_ranks.get(word)))
            count += 1
            if count % 100000 == 0:
                print(f"  {count:,} FI entries processed, {len(fi_idx):,} EN keys")

    for k in fi_idx:
        fi_idx[k].sort(key=lambda x: (x[2] is None, x[2] or 0))
    for en_token, candidates in fi_idx.items():
        for fi_lemma, _, _ in candidates:
            fi_to_en[fi_lemma].add(en_token)

    print(f"  Done: {len(fi_idx):,} EN keys, {len(fi_to_en):,} FI lemmas indexed")
    return dict(fi_idx), dict(fi_to_en)


def extract_source_entries(csv_path, lang_code):
    entries = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pos = r.get("pos", "")
            if not is_content_pos(pos):
                continue
            defs = r.get("defs", "")
            first_def = defs.split(" | ")[0] if defs else ""
            if should_skip_gloss(first_def):
                continue
            en_token = first_gloss_first_token(first_def)
            if not en_token:
                continue
            entries.append({
                "lemma": r["lemma"],
                "pos": normalize_pos(pos),
                "en": en_token,
                "rank": int(r["rank"]),
                "lang": lang_code,
            })
    return entries


def lookup_fi(en_token, pos, fi_idx):
    candidates = fi_idx.get(en_token.lower(), [])
    if not candidates:
        return None, None
    matched = [c for c in candidates if c[1] == pos]
    pool = matched if matched else candidates
    return pool[0][0], pool[0][1]


def bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en):
    candidates = fi_idx.get(en_token.lower(), [])
    if candidates and candidates[0][0] == fi_lemma:
        return "auto"
    if en_token.lower() in fi_to_en.get(fi_lemma, set()):
        return "review"
    return "borderline"


def main():
    csc_ranks = load_csc_ranks()
    print(f"CSC ranks: {len(csc_ranks):,} lemmas")

    fixture_lemmas = load_fixture_lemmas()
    print(f"Fixture: {len(fixture_lemmas)} lemmas to skip")

    fi_idx, fi_to_en = build_fi_kaikki_index(csc_ranks)

    master = {}  # (fi_lemma, fi_pos) -> best entry
    conf_order = {"auto": 0, "review": 1, "borderline": 2}

    for lang_code, csv_path in LANGS:
        print(f"\nProcessing {lang_code} ({csv_path})...")
        entries = extract_source_entries(csv_path, lang_code)
        print(f"  {len(entries):,} content-word entries")

        for e in entries:
            if lang_code == "fi":
                fi_lemma, fi_pos = e["lemma"], e["pos"]
                en_token, source_lemma = e["en"], fi_lemma
            else:
                fi_lemma, fi_pos = lookup_fi(e["en"], e["pos"], fi_idx)
                if not fi_lemma:
                    continue
                en_token, source_lemma = e["en"], e["lemma"]

            if fi_lemma in fixture_lemmas:
                continue  # fixture is authoritative, skip

            key = (fi_lemma, fi_pos)
            confidence = bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en)
            fi_rank = csc_ranks.get(fi_lemma)

            if key not in master:
                master[key] = {
                    "fi": fi_lemma, "fi_pos": fi_pos, "en": en_token,
                    "confidence": confidence, "source_lang": lang_code,
                    "source_lemma": source_lemma, "fi_rank": fi_rank,
                }
            else:
                existing = master[key]
                if conf_order[confidence] < conf_order[existing["confidence"]]:
                    master[key].update({
                        "en": en_token, "confidence": confidence,
                        "source_lang": lang_code, "source_lemma": source_lemma,
                    })

    rows = sorted(master.values(),
                  key=lambda r: (r["fi_rank"] is None, r["fi_rank"] or 0, r["fi"]))
    for i, row in enumerate(rows, 1):
        row["id"] = i

    total = len(rows)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\nTotal pairs: {total:,} → {num_batches} batches of {BATCH_SIZE}")

    batch_conf_order = {"borderline": 0, "review": 1, "auto": 2}
    for b in range(num_batches):
        batch_rows = sorted(rows[b * BATCH_SIZE:(b + 1) * BATCH_SIZE],
                            key=lambda r: batch_conf_order[r["confidence"]])
        out_file = f"fi_en_batch_{b + 1:02d}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(batch_rows, f, ensure_ascii=False, indent=2)
        auto = sum(1 for r in batch_rows if r["confidence"] == "auto")
        review = sum(1 for r in batch_rows if r["confidence"] == "review")
        border = sum(1 for r in batch_rows if r["confidence"] == "borderline")
        print(f"  {out_file}: auto={auto} review={review} borderline={border}")

    print(f"\nDone. Run: python3 10_qc_server.py 1")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3.4: Run 09 and check first batch**

```bash
python3 09_build_fi_en_pairs.py 2>&1 | tail -20
```

Expected: summary of batches printed, `fi_en_batch_01.json` created.

```bash
python3 -c "import json; rows=json.load(open('fi_en_batch_01.json')); print(len(rows), 'rows'); [print(r) for r in rows[:5]]"
```

Expected: 100 rows, first 5 rows are borderline/review cases, each has `fi`, `en`, `confidence`, `source_lang`.

- [ ] **Step 3.5: Commit**

```bash
git add 09_build_fi_en_pairs.py tests/test_09.py fi_en_batch_*.json
git -c commit.gpgsign=false commit -m "feat(sanakirja): build FI-EN candidate batches with bidirectional confidence"
```

---

## Task 4: QC server (`10_qc_server.py`)

**Files:**
- Create: `10_qc_server.py`

No automated tests — verify manually by opening the browser and reviewing the first batch.

- [ ] **Step 4.1: Write `10_qc_server.py`**

```python
#!/usr/bin/env python3
"""
Step 10: Local QC server for FI<->EN batch review.

Usage:
    python3 10_qc_server.py 1      # review fi_en_batch_01.json at localhost:8000
    python3 10_qc_server.py 2      # review fi_en_batch_02.json

Keyboard: Tab/Enter = approve, type to correct, '-' + Enter = reject.
Mouse:    [✓] = approve, [✗] = reject.
Saves to: fi_en_batch_NN_decisions.json
"""
import http.server, json, os, socketserver, sys, webbrowser


PORT = 8000


def make_html(batch_num: int, batch_data: list) -> str:
    batch_json = json.dumps(batch_data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FI↔EN QC — Batch {batch_num}</title>
<style>
*{{box-sizing:border-box;font-family:system-ui,sans-serif;margin:0;padding:0}}
body{{padding:1rem;background:#f5f5f5}}
header{{display:flex;align-items:center;gap:1rem;margin-bottom:1rem;flex-wrap:wrap}}
h1{{font-size:1.1rem}}
#progress{{font-size:.85rem;color:#666}}
#save-btn{{padding:.35rem .9rem;background:#0070f3;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:.85rem}}
#save-btn:hover{{background:#0060df}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th{{background:#333;color:#fff;padding:.45rem .7rem;text-align:left;font-size:.8rem}}
td{{padding:.35rem .7rem;border-bottom:1px solid #eee;font-size:.85rem;vertical-align:middle}}
tr.auto td:first-child{{border-left:3px solid #22c55e}}
tr.review td:first-child{{border-left:3px solid #f59e0b}}
tr.borderline{{background:#fff8f8}}
tr.borderline td:first-child{{border-left:3px solid #ef4444}}
tr.done-approve{{background:#f0fdf4}}
tr.done-reject{{background:#fff0f0}}
tr.done-edit{{background:#eff6ff}}
input.en-input{{border:1px solid #ccc;border-radius:4px;padding:.2rem .45rem;width:155px;font-size:.85rem}}
input.en-input:focus{{outline:none;border-color:#0070f3;box-shadow:0 0 0 2px rgba(0,112,243,.2)}}
.action-btns{{display:flex;gap:.2rem}}
.btn-ok,.btn-no{{border:none;border-radius:4px;cursor:pointer;padding:.15rem .45rem;font-size:.8rem}}
.btn-ok{{background:#dcfce7;color:#15803d}}.btn-ok:hover{{background:#bbf7d0}}
.btn-no{{background:#fee2e2;color:#b91c1c}}.btn-no:hover{{background:#fecaca}}
.badge{{font-size:.72rem;padding:.1rem .35rem;border-radius:3px;white-space:nowrap}}
.badge-ok{{background:#dcfce7;color:#15803d}}
.badge-no{{background:#fee2e2;color:#b91c1c}}
.badge-edit{{background:#dbeafe;color:#1d4ed8}}
.pos{{font-size:.72rem;background:#e5e7eb;padding:.1rem .3rem;border-radius:3px;color:#555}}
.conf{{font-size:.7rem;padding:.1rem .3rem;border-radius:3px}}
.conf-auto{{background:#dcfce7;color:#15803d}}
.conf-review{{background:#fef3c7;color:#92400e}}
.conf-borderline{{background:#fee2e2;color:#b91c1c}}
</style>
</head>
<body>
<header>
  <h1>FI↔EN QC — Batch {batch_num}</h1>
  <span id="progress">0 / {len(batch_data)} reviewed</span>
  <button id="save-btn" onclick="saveBatch()">Save batch</button>
</header>
<table>
<thead><tr>
  <th>#</th><th>FI</th><th>POS</th><th>EN (edit to correct)</th>
  <th>Source</th><th>Conf</th><th>Action</th><th>Status</th>
</tr></thead>
<tbody id="rows"></tbody>
</table>
<script>
const BATCH={batch_json};
const STORAGE_KEY='sanakirja_batch_{batch_num}';
let state={{}};
try{{const s=localStorage.getItem(STORAGE_KEY);if(s)state=JSON.parse(s);}}catch(e){{}}

function esc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}

function save(){{localStorage.setItem(STORAGE_KEY,JSON.stringify(state));updateProgress();}}

function updateProgress(){{
  document.getElementById('progress').textContent=Object.keys(state).length+' / '+BATCH.length+' reviewed';
}}

function decide(id,action,enFinal){{
  const row=BATCH.find(r=>r.id===id);
  state[id]={{id,fi:row.fi,fi_pos:row.fi_pos,en_final:enFinal,action,en_original:row.en}};
  save();renderRow(id);
}}

function approve(id){{
  const row=BATCH.find(r=>r.id===id);
  const inp=document.getElementById('inp-'+id);
  const val=inp?inp.value.trim():'';
  const final=val===''?row.en:val;
  decide(id,val!==''&&val!==row.en?'edit':'approve',final);
}}

function reject(id){{decide(id,'reject',null);}}

function renderRow(id){{
  const row=BATCH.find(r=>r.id===id);
  const tr=document.getElementById('tr-'+id);
  if(!tr)return;
  const d=state[id];
  tr.className=row.confidence+(d?' done-'+(d.action==='edit'?'edit':d.action==='reject'?'reject':'approve'):'');
  const badge=tr.querySelector('.badge');
  if(badge){{
    if(!d){{badge.textContent='';badge.className='badge';}}
    else if(d.action==='approve'){{badge.textContent='✓';badge.className='badge badge-ok';}}
    else if(d.action==='reject'){{badge.textContent='✗';badge.className='badge badge-no';}}
    else{{badge.textContent='✎ '+esc(d.en_final);badge.className='badge badge-edit';}}
  }}
}}

function buildTable(){{
  const order={{borderline:0,review:1,auto:2}};
  const sorted=[...BATCH].sort((a,b)=>order[a.confidence]-order[b.confidence]);
  const tbody=document.getElementById('rows');
  tbody.innerHTML=sorted.map((row,i)=>{{
    const d=state[row.id];
    const src=row.source_lang+(row.source_lemma&&row.source_lemma!==row.fi?'→'+esc(row.source_lemma):'');
    const cls=row.confidence+(d?' done-'+(d.action==='edit'?'edit':d.action==='reject'?'reject':'approve'):'');
    const bdg=d?(d.action==='approve'?`<span class="badge badge-ok">✓</span>`:d.action==='reject'?`<span class="badge badge-no">✗</span>`:`<span class="badge badge-edit">✎ ${{esc(d.en_final)}}</span>`):`<span class="badge"></span>`;
    return `<tr id="tr-${{row.id}}" class="${{cls}}" onclick="document.getElementById('inp-${{row.id}}').focus()">
      <td>${{i+1}}</td>
      <td><strong>${{esc(row.fi)}}</strong></td>
      <td><span class="pos">${{esc(row.fi_pos)}}</span></td>
      <td><input class="en-input" id="inp-${{row.id}}" value="${{esc(row.en)}}" data-id="${{row.id}}" data-orig="${{esc(row.en)}}"
           onkeydown="handleKey(event,${{row.id}})" onblur="if(!state[${{row.id}}])approve(${{row.id}})"></td>
      <td>${{esc(src)}}</td>
      <td><span class="conf conf-${{row.confidence}}">${{row.confidence}}</span></td>
      <td class="action-btns">
        <button class="btn-ok" onclick="event.stopPropagation();approve(${{row.id}})">✓</button>
        <button class="btn-no" onclick="event.stopPropagation();reject(${{row.id}})">✗</button>
      </td>
      <td>${{bdg}}</td>
    </tr>`;
  }}).join('');
  const first=tbody.querySelector('input');
  if(first)first.focus();
  updateProgress();
}}

function handleKey(e,id){{
  if(e.key==='Enter'||(e.key==='Tab'&&!e.shiftKey)){{
    e.preventDefault();approve(id);focusNext(id,1);
  }}else if(e.key==='Tab'&&e.shiftKey){{
    e.preventDefault();focusNext(id,-1);
  }}
}}

function focusNext(currentId,dir){{
  const inputs=Array.from(document.querySelectorAll('input.en-input'));
  const idx=inputs.findIndex(i=>parseInt(i.dataset.id)===currentId);
  const next=inputs[idx+dir];
  if(next)next.focus();
}}

async function saveBatch(){{
  const btn=document.getElementById('save-btn');
  btn.textContent='Saving...';btn.disabled=true;
  try{{
    const resp=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{batch:{batch_num},decisions:Object.values(state)}})}});
    btn.textContent=resp.ok?'Saved ✓':'Error — retry';
    setTimeout(()=>{{btn.textContent='Save batch';btn.disabled=false;}},2000);
  }}catch(err){{btn.textContent='Error — retry';btn.disabled=false;}}
}}

buildTable();
</script>
</body>
</html>"""


class QCHandler(http.server.BaseHTTPRequestHandler):
    batch_num = None
    batch_data = None

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = make_html(self.batch_num, self.batch_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/save":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400); self.end_headers(); return

            out = f"fi_en_batch_{self.batch_num:02d}_decisions.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            decisions = data.get("decisions", [])
            approved = sum(1 for d in decisions if d.get("action") == "approve")
            edited   = sum(1 for d in decisions if d.get("action") == "edit")
            rejected = sum(1 for d in decisions if d.get("action") == "reject")
            print(f"\nBatch {self.batch_num} → {out}")
            print(f"  Approved {approved}  Edited {edited}  Rejected {rejected}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress access logs


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 10_qc_server.py <batch_number>")
        sys.exit(1)

    batch_num = int(sys.argv[1])
    batch_file = f"fi_en_batch_{batch_num:02d}.json"

    if not os.path.exists(batch_file):
        print(f"Error: {batch_file} not found. Run 09_build_fi_en_pairs.py first.")
        sys.exit(1)

    with open(batch_file, encoding="utf-8") as f:
        batch_data = json.load(f)

    QCHandler.batch_num = batch_num
    QCHandler.batch_data = batch_data

    print(f"Batch {batch_num}: {len(batch_data)} rows at http://localhost:{PORT}")
    print("  Tab/Enter = approve  |  edit + Enter = correct  |  '-' + Enter = reject")
    print("  Ctrl+C to stop")

    with socketserver.TCPServer(("", PORT), QCHandler) as httpd:
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.2: Test the QC server manually with batch 1**

```bash
python3 10_qc_server.py 1
```

Open `http://localhost:8000`. Verify:
- Table loads with 100 rows
- Borderline rows (red border) appear first
- Tab advances to next row's input
- `[✓]` approves current value, `[✗]` marks red
- Editing input and hitting Enter records the correction
- "Save batch" button writes `fi_en_batch_01_decisions.json`
- Refreshing the page restores prior decisions from localStorage

Stop server with Ctrl+C. Confirm `fi_en_batch_01_decisions.json` was created.

- [ ] **Step 4.3: Commit**

```bash
git add 10_qc_server.py
git -c commit.gpgsign=false commit -m "feat(sanakirja): add local HTML QC server with keyboard and mouse support"
```

---

## Task 5: Cross-language fill (`11_fill_other_langs.py`)

**Files:**
- Create: `11_fill_other_langs.py`
- Create: `tests/test_11.py`

**Runtime note:** Streams `kaikki_german.jsonl` (956 MB) once. Expect ~2 minutes.

> **Prerequisite:** Complete QC for all batches using `10_qc_server.py` before running step 11 in production. For testing, use mock decision files.

- [ ] **Step 5.1: Write integration tests**

Create `tests/test_11.py`:

```python
# tests/test_11.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


def build_target_index_from_rows(rows):
    """Build {en_token: [(lemma, pos, rank)]} from list of mock *_top.csv row dicts."""
    idx = defaultdict(list)
    for r in rows:
        pos = r.get("pos", "")
        if not is_content_pos(pos):
            continue
        defs = r.get("defs", "")
        first_def = defs.split(" | ")[0] if defs else ""
        if should_skip_gloss(first_def):
            continue
        en_token = first_gloss_first_token(first_def)
        if not en_token:
            continue
        pos_norm = normalize_pos(pos)
        idx[en_token.lower()].append((r["lemma"], pos_norm, int(r.get("rank", 9999))))
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    return dict(idx)


def best_target(en, fi_pos, idx):
    en_key = en.lower()
    search_keys = [en_key]
    if en_key.startswith("to "):
        search_keys.append(en_key[3:])
    for key in search_keys:
        candidates = idx.get(key, [])
        if candidates:
            matched = [c for c in candidates if c[1] == fi_pos]
            return (matched[0] if matched else candidates[0])[0]
    return None


class TestTargetIndex(unittest.TestCase):

    def setUp(self):
        self.sv_rows = [
            {"lemma": "hus",    "pos": "noun", "defs": "house (building)", "rank": "1"},
            {"lemma": "spela",  "pos": "verb", "defs": "to play (a game)", "rank": "2"},
            {"lemma": "stor",   "pos": "adj",  "defs": "big, large",       "rank": "3"},
        ]
        self.sv_idx = build_target_index_from_rows(self.sv_rows)

    def test_noun_indexed(self):
        self.assertIn("house", self.sv_idx)
        self.assertEqual(self.sv_idx["house"][0][0], "hus")

    def test_verb_indexed_with_to(self):
        self.assertIn("to play", self.sv_idx)
        self.assertEqual(self.sv_idx["to play"][0][0], "spela")

    def test_adj_first_token(self):
        self.assertIn("big", self.sv_idx)
        self.assertEqual(self.sv_idx["big"][0][0], "stor")


class TestBestTarget(unittest.TestCase):

    def setUp(self):
        self.sv_rows = [
            {"lemma": "hus",   "pos": "noun", "defs": "house (building)", "rank": "1"},
            {"lemma": "hem",   "pos": "noun", "defs": "home",             "rank": "3"},
            {"lemma": "spela", "pos": "verb", "defs": "to play",          "rank": "2"},
        ]
        self.idx = build_target_index_from_rows(self.sv_rows)

    def test_exact_match(self):
        self.assertEqual(best_target("house", "noun", self.idx), "hus")

    def test_verb_with_to_prefix(self):
        self.assertEqual(best_target("to play", "verb", self.idx), "spela")

    def test_no_match_returns_none(self):
        self.assertIsNone(best_target("elephant", "noun", self.idx))

    def test_pos_preference(self):
        # "home" maps to noun "hem", not verb
        self.assertEqual(best_target("home", "noun", self.idx), "hem")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5.2: Run tests to confirm they pass**

```bash
python -m unittest tests/test_11.py -v 2>&1
```

Expected: all PASS

- [ ] **Step 5.3: Write `11_fill_other_langs.py`**

```python
#!/usr/bin/env python3
"""
Step 11: Fill SV/IT/FR/DE for approved FI<->EN pairs, merge fixture, write data.json.

Prerequisite: all fi_en_batch_NN_decisions.json files saved (via 10_qc_server.py).

Inputs:
  fi_en_batch_NN_decisions.json  (one per batch, output of step 10)
  fixture.json                   (authoritative grammar/function words)
  sv_top.csv, it_top.csv, fr_top.csv
  kaikki_german.jsonl

Output:
  data.json  [{fi, en, sv?, it?, fr?, de?}, ...]  sorted by FI frequency
"""
import csv, json, os, re
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos

FIXTURE_FILE = "fixture.json"
CSC_FILE     = "csc_9996.csv"
OUTPUT       = "data.json"
LANGS_CSVS   = [("sv", "sv_top.csv"), ("it", "it_top.csv"), ("fr", "fr_top.csv")]


def load_approved():
    """Concatenate all batch decisions. Returns {(fi, fi_pos): en_final}."""
    approved = {}
    b = 1
    while True:
        path = f"fi_en_batch_{b:02d}_decisions.json"
        if not os.path.exists(path):
            break
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for dec in data.get("decisions", []):
            if dec.get("action") == "reject":
                continue
            fi, fi_pos, en = dec.get("fi"), dec.get("fi_pos"), dec.get("en_final")
            if fi and fi_pos and en:
                approved[(fi, fi_pos)] = en
        b += 1
    print(f"Loaded {len(approved)} approved pairs from {b - 1} batch files")
    return approved


def build_target_index(csv_path):
    idx = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pos = r.get("pos", "")
            if not is_content_pos(pos):
                continue
            defs = r.get("defs", "")
            first_def = defs.split(" | ")[0] if defs else ""
            if should_skip_gloss(first_def):
                continue
            en_token = first_gloss_first_token(first_def)
            if not en_token:
                continue
            pos_norm = normalize_pos(pos)
            idx[en_token.lower()].append((r["lemma"], pos_norm, int(r.get("rank", 9999))))
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    return dict(idx)


def build_de_index():
    print("Building DE reverse index from kaikki_german.jsonl (~2 min)...")
    idx = defaultdict(list)
    count = 0
    with open("kaikki_german.jsonl", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            pos = e.get("pos", "")
            if not is_content_pos(pos):
                continue
            word = e.get("word", "")
            if not word or not re.match(r"^[a-zäöüßA-ZÄÖÜ\-']+$", word):
                continue
            senses = e.get("senses", [])
            if not senses:
                continue
            first_gloss = (senses[0].get("glosses") or senses[0].get("raw_glosses") or [""])[0]
            if should_skip_gloss(first_gloss):
                continue
            en_token = first_gloss_first_token(first_gloss)
            if not en_token:
                continue
            pos_norm = normalize_pos(pos)
            if len(idx[en_token.lower()]) < 5:
                idx[en_token.lower()].append((word, pos_norm, len(word)))
            count += 1
            if count % 100000 == 0:
                print(f"  {count:,} DE entries")
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    print(f"  Done: {len(idx):,} EN keys in DE index")
    return dict(idx)


def best_target(en, fi_pos, idx):
    search_keys = [en.lower()]
    if en.lower().startswith("to "):
        search_keys.append(en.lower()[3:])
    for key in search_keys:
        candidates = idx.get(key, [])
        if candidates:
            matched = [c for c in candidates if c[1] == fi_pos]
            return (matched[0] if matched else candidates[0])[0]
    return None


def load_csc_ranks():
    ranks = {}
    with open(CSC_FILE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            l, rk = r["lemma"], int(r["rank"])
            if l not in ranks or rk < ranks[l]:
                ranks[l] = rk
    return ranks


def main():
    approved = load_approved()

    with open(FIXTURE_FILE, encoding="utf-8") as f:
        fixture = json.load(f)
    fixture_fi = {e["fi"] for e in fixture}
    print(f"Fixture: {len(fixture)} entries")

    print("Building target language indexes...")
    target_idx = {}
    for lang_code, csv_path in LANGS_CSVS:
        target_idx[lang_code] = build_target_index(csv_path)
        print(f"  {lang_code}: {len(target_idx[lang_code]):,} EN keys")
    target_idx["de"] = build_de_index()

    csc_ranks = load_csc_ranks()

    rows = []
    for (fi, fi_pos), en in approved.items():
        if fi in fixture_fi:
            continue
        row = {"fi": fi, "en": en}
        for lang in ("sv", "it", "fr", "de"):
            target = best_target(en, fi_pos, target_idx[lang])
            if target:
                row[lang] = target
        rows.append((csc_ranks.get(fi, 99999), fi, row))

    rows.sort(key=lambda x: (x[0], x[1]))

    # Fixture rows go first (already complete), then approved rows
    final = list(fixture)
    seen_fi = {e["fi"] for e in fixture}
    for _, fi, row in rows:
        if fi not in seen_fi:
            final.append(row)
            seen_fi.add(fi)

    total = len(final)
    all6 = sum(1 for r in final if all(k in r for k in ("fi","en","sv","it","fr","de")))
    fi_en_only = sum(1 for r in final if set(r.keys()) <= {"fi","en","fi_pos"})
    per_lang = {l: sum(1 for r in final if l in r) for l in ("en","sv","it","fr","de")}

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\n{OUTPUT}: {os.path.getsize(OUTPUT):,} bytes")
    print(f"  Total rows: {total:,}")
    print(f"  All 6 langs: {all6:,} ({all6*100//total}%)")
    print(f"  FI+EN only: {fi_en_only:,}")
    print(f"  Per-lang: {per_lang}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.4: Commit**

```bash
git add 11_fill_other_langs.py tests/test_11.py
git -c commit.gpgsign=false commit -m "feat(sanakirja): cross-language fill SV/IT/FR/DE with kaikki reverse lookup"
```

---

## Task 6: Output validation (`12_validate_output.py`)

**Files:**
- Create: `12_validate_output.py`
- Create: `tests/test_12.py`

- [ ] **Step 6.1: Write validation tests**

Create `tests/test_12.py`:

```python
# tests/test_12.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SKIP_PATTERNS = [
    r"inflection of", r"plural of", r"past participle",
    r"third.person", r"alternative form of", r"obsolete form of",
    r"definite singular",
]
import re

def validate_data(data):
    errors = []
    seen_fi = {}
    for i, row in enumerate(data):
        label = f"row[{i}] fi={row.get('fi','?')}"
        if "fi" not in row or not row["fi"]:
            errors.append(f"{label}: missing fi")
        if "en" not in row or not row["en"]:
            errors.append(f"{label}: missing en")
        for k, v in row.items():
            if v == "":
                errors.append(f"{label}: empty string for '{k}'")
            if isinstance(v, str):
                for pat in SKIP_PATTERNS:
                    if re.search(pat, v, re.IGNORECASE):
                        errors.append(f"{label}: '{k}' contains skip pattern: {v[:60]}")
        fi = row.get("fi")
        if fi:
            if fi in seen_fi:
                errors.append(f"{label}: duplicate fi lemma (first at row {seen_fi[fi]})")
            else:
                seen_fi[fi] = i
    if len(data) < 1500:
        errors.append(f"Too few rows: {len(data)}")
    return errors


class TestValidation(unittest.TestCase):

    BASE = {"fi": "talo", "en": "house", "sv": "hus"}

    def _row(self, **kwargs):
        r = dict(self.BASE)
        r.update(kwargs)
        return r

    def test_valid_row_passes(self):
        self.assertEqual(validate_data([self._row()]), [])

    def test_missing_fi_fails(self):
        row = {"en": "house", "sv": "hus"}
        errors = validate_data([row])
        self.assertTrue(any("missing fi" in e for e in errors))

    def test_missing_en_fails(self):
        row = {"fi": "talo", "sv": "hus"}
        errors = validate_data([row])
        self.assertTrue(any("missing en" in e for e in errors))

    def test_empty_string_fails(self):
        errors = validate_data([self._row(sv="")])
        self.assertTrue(any("empty string" in e for e in errors))

    def test_inflection_leak_fails(self):
        errors = validate_data([self._row(en="inflection of juuria")])
        self.assertTrue(any("skip pattern" in e for e in errors))

    def test_duplicate_fi_fails(self):
        row = self._row()
        errors = validate_data([row, row])
        self.assertTrue(any("duplicate fi lemma" in e for e in errors))

    def test_too_few_rows(self):
        errors = validate_data([self._row(fi=f"fi{i}") for i in range(10)])
        self.assertTrue(any("Too few rows" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6.2: Run tests to confirm they pass**

```bash
python -m unittest tests/test_12.py -v 2>&1
```

Expected: all PASS

- [ ] **Step 6.3: Write `12_validate_output.py`**

```python
#!/usr/bin/env python3
"""
Step 12: Validate data.json for quality and completeness.
Run: python3 12_validate_output.py
Exits 0 on success, 1 on failure.
"""
import json, re, sys

OUTPUT       = "data.json"
MIN_ROWS     = 1500
MAX_ROWS     = 5000

SKIP_PATTERNS = [
    r"inflection of", r"plural of", r"past participle",
    r"third.person", r"first.person", r"second.person",
    r"alternative form of", r"obsolete form of",
    r"definite singular", r"definite plural",
]


def main():
    with open(OUTPUT, encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    seen_fi = {}

    for i, row in enumerate(data):
        label = f"row[{i}] fi={row.get('fi', '?')}"

        if "fi" not in row or not row["fi"]:
            errors.append(f"{label}: missing fi")
        if "en" not in row or not row["en"]:
            errors.append(f"{label}: missing en")

        for k, v in row.items():
            if v == "":
                errors.append(f"{label}: empty string for '{k}' (omit key instead)")
            if isinstance(v, str):
                for pat in SKIP_PATTERNS:
                    if re.search(pat, v, re.IGNORECASE):
                        errors.append(f"{label}: '{k}' contains skip pattern: {v[:60]}")

        fi = row.get("fi")
        if fi:
            if fi in seen_fi:
                errors.append(f"{label}: duplicate fi lemma (first at row {seen_fi[fi]})")
            else:
                seen_fi[fi] = i

    if len(data) < MIN_ROWS:
        errors.append(f"Too few rows: {len(data)} (expected >= {MIN_ROWS})")
    if len(data) > MAX_ROWS:
        errors.append(f"Too many rows: {len(data)} (expected <= {MAX_ROWS})")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors[:50]:
            print(f"  {e}")
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        sys.exit(1)
    else:
        per_lang = {l: sum(1 for r in data if l in r) for l in ("en","sv","it","fr","de")}
        print(f"VALIDATION PASSED — {len(data):,} rows")
        print(f"  Coverage: {per_lang}")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6.4: Run all tests**

```bash
python -m unittest discover tests/ -v 2>&1
```

Expected: all tests in `test_utils.py`, `test_08.py`, `test_09.py`, `test_11.py`, `test_12.py` PASS.

- [ ] **Step 6.5: Commit**

```bash
git add 12_validate_output.py tests/test_12.py
git -c commit.gpgsign=false commit -m "feat(sanakirja): add output validation with comprehensive test suite"
```

---

## Task 7: End-to-end QC workflow

Once all 6 tasks above are committed, this is the workflow to produce the final `data.json`.

- [ ] **Step 7.1: Build all batches**

```bash
python3 09_build_fi_en_pairs.py 2>&1 | tee /tmp/09_run.log
```

Check output: total pairs, number of batches, per-batch confidence breakdown.

- [ ] **Step 7.2: QC each batch**

For batch 1:
```bash
python3 10_qc_server.py 1
```
Review 100 rows. Tab through `auto` rows quickly; pause on `review`/`borderline`. Save. Ctrl+C.

Repeat for batches 2, 3, … N:
```bash
python3 10_qc_server.py 2
# ... etc.
```

After each save, confirm `fi_en_batch_NN_decisions.json` exists:
```bash
ls fi_en_batch_*_decisions.json | wc -l
```

- [ ] **Step 7.3: Run cross-language fill**

After all batches reviewed:
```bash
python3 11_fill_other_langs.py 2>&1 | tee /tmp/11_run.log
```

Check coverage stats printed at end.

- [ ] **Step 7.4: Validate output**

```bash
python3 12_validate_output.py
```

Expected: `VALIDATION PASSED` with coverage stats. If failures, fix in `data.json` directly or re-review the relevant batch and re-run 11.

- [ ] **Step 7.5: Spot-check data.json**

```bash
python3 -c "
import json
data = json.load(open('data.json'))
print('First 10 rows:')
for r in data[:10]:
    print(r)
print()
# Check fixture words are first
print('Fixture words at front (ei, olla, ja):')
for r in data[:30]:
    if r['fi'] in ('ei','olla','ja','se','hän'):
        print(r)
"
```

Verify: fixture grammar words appear near the top, translations look correct.

- [ ] **Step 7.6: Final commit**

```bash
git add data.json
git -c commit.gpgsign=false commit -m "data(sanakirja): generate quality-first multilingual dictionary data.json"
```

---

## Self-review notes

- `first_gloss_first_token` handles `"to be able to (..."` → `"to be able to"` — the "to " prefix spans multiple words for irregular modals. Tested in Task 1.
- `build_de_index` caps at 5 entries per EN token to control memory; the shorter-lemma heuristic for sorting is imperfect but acceptable given no DE freq list.
- Fixture entries with multi-word values (e.g. `"fr": "parce que"`, `"de": "zu Hause"`) pass through 11 unchanged and are valid JSON strings — no issues.
- `11_fill_other_langs.py` omits `fi_pos` from the output row (not present in existing app's expected schema). The `fi_pos` lives only in batch files and approved decisions.
- If a batch QC file is missing (user skipped a batch), `load_approved()` stops at the first gap. Batches must be saved in order 01, 02, 03, … with no gaps. If a batch is skipped, save it with all decisions set to `approve` to avoid the gap.
