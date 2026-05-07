#!/usr/bin/env python3
"""
Build multi-meaning entries for all words in data.json.
Sources:
  - gt_check_results.json  (GT primary)
  - kaikki_finnish.jsonl   (Wiktionary glosses → secondary/tertiary)
Output: updates data.json with en as list [primary, secondary?, tertiary?]
Checkpoint: kaikki_glosses_checkpoint.json
"""

import json, re, os
from utils import atomic_write_json

KAIKKI_FILE = "kaikki_finnish.jsonl"
CHECKPOINT  = "kaikki_glosses_checkpoint.json"
DATA_FILE   = "data.json"
GT_FILE     = "gt_check_results.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_gloss(raw):
    """'dog (Canis lupus...)' → 'dog', 'to hold [with partitive]' → 'to hold'"""
    g = raw
    # Strip bracketed usage notes: [with partitive...], [elative...]
    g = re.sub(r'\[.*?\]', '', g).strip()
    # Strip parenthetical Latin/scientific/explanatory notes
    g = re.sub(r'\(.*?\)', '', g).strip()
    # Take first item if semicolon-separated alternatives: 'not full; partial'
    g = g.split(';')[0].strip()
    # Take first item if comma-separated alternatives
    g = g.split(',')[0].strip()
    # Remove trailing punctuation
    g = g.rstrip('.,;:[').strip()
    # Lowercase all kaikki glosses — they're English words, not proper nouns
    g = g.lower()
    # Reject if too many words — it's a definition, not a translation
    if len(g.split()) > 4:
        return None
    return g if len(g) > 1 else None


def is_english(text):
    """Reject grammatical notes, Finnish proper-noun definitions, inflection glosses."""
    skip = [
        # Grammatical / morphological
        'nominatiivi', 'akkusatiivi', 'partitivii', 'genetiivi',
        'plural', 'singular', 'comparative', 'superlative',
        'inflection', 'inflected', 'alternative', 'obsolete', 'dated',
        'eye dialect', 'misspelling', 'abbreviation of', 'short for',
        'genitive of', 'plural of', 'partitive of', 'accusative of',
        'passive participle', 'present participle', 'past participle',
        'connegative', 'indicative', 'conditional', 'imperative',
        'ellipsis of', 'clipping of', 'eye dialect of',
        'of or pertaining to', 'pertaining to',
        # Finnish proper-noun meta
        'finnish surname', 'finnish given name', 'finnish male', 'finnish female',
        'given name', 'male given name', 'female given name',
        'former municipality', 'municipality of', 'a city in', 'a town in',
        'a lake in', 'a river in', 'a region in',
        'places in finland', 'small places', 'municipality in',
        # Geographic/regional origin descriptions
        'from southwest', 'from southeast', 'from eastern', 'from western',
        'from northern', 'from southern', 'from finland', 'from karelia',
        'of or relating to', 'relating to',
        # Reference/cross-reference glosses
        'see also', 'used in', 'used as', 'used to',
        # Archaic / extremely rare meanings not useful for language learning
        'squirrel pelt', 'squirrel skin', 'bath broom', 'sauna whisk',
        'moo-moo', 'hullabaloo', 'goblet', 'burr', 'iota', 'callus',
        'stead', 'swidden', 'jobber',
        # Other noise
        'archaic', 'dialectal', 'colloquial form',
    ]
    low = text.lower()
    return not any(s in low for s in skip) and len(text) < 60


# ── Step 1: scan kaikki → checkpoint ─────────────────────────────────────────

with open(DATA_FILE) as f:
    data = json.load(f)

target_lemmas = {d['fi'].lower() for d in data}

# Load checkpoint
if os.path.exists(CHECKPOINT):
    with open(CHECKPOINT) as f:
        kaikki_glosses = json.load(f)
    print(f"Checkpoint loaded: {len(kaikki_glosses)} lemmas already scanned")
else:
    kaikki_glosses = {}

# Re-apply current filter to checkpoint (cleans up entries built with old filter)
for key in list(kaikki_glosses.keys()):
    kaikki_glosses[key] = [g for g in kaikki_glosses[key] if is_english(g)]
    if not kaikki_glosses[key]:
        del kaikki_glosses[key]

if len(kaikki_glosses) < len(target_lemmas):
    print(f"Scanning kaikki for {len(target_lemmas)} lemmas...")
    lines_read = 0
    with open(KAIKKI_FILE) as f:
        for line in f:
            lines_read += 1
            if lines_read % 500000 == 0:
                print(f"  {lines_read/1e6:.1f}M lines, found {len(kaikki_glosses)}/{len(target_lemmas)}")
                # Save checkpoint periodically
                with open(CHECKPOINT, 'w') as ck:
                    json.dump(kaikki_glosses, ck, ensure_ascii=False)

            entry = json.loads(line)
            lemma = entry.get('word', '').lower()
            if lemma not in target_lemmas:
                continue

            pos = entry.get('pos', '')
            senses = entry.get('senses', [])

            glosses = []
            for sense in senses:
                for g_raw in sense.get('glosses', [])[:1]:  # first gloss per sense
                    g = clean_gloss(g_raw)
                    if g and is_english(g) and g not in glosses:
                        glosses.append(g)

            if glosses:
                key = f"{lemma}|{pos}"
                if key not in kaikki_glosses:
                    kaikki_glosses[key] = glosses

    with open(CHECKPOINT, 'w') as ck:
        json.dump(kaikki_glosses, ck, ensure_ascii=False)
    print(f"Scan complete. {len(kaikki_glosses)} lemma+pos combos found.")
else:
    print(f"Using checkpoint ({len(kaikki_glosses)} entries)")

# ── Step 2: load GT results ───────────────────────────────────────────────────

with open(GT_FILE) as f:
    gt_list = json.load(f)
gt_by_fi = {r['fi']: r['en_gt'] for r in gt_list}

# Also load the second GT scan for the 2,755 newly added words
GT_MISSING = "gt_missing_checkpoint.jsonl"
if os.path.exists(GT_MISSING):
    with open(GT_MISSING) as f:
        for line in f:
            e = json.loads(line)
            gt_by_fi.setdefault(e['fi'], e['en'])
    print(f"Merged GT data: {len(gt_by_fi)} entries")

# Words where we know GT was wrong (keep our current translation as primary)
gt_override = {
    'raha', 'tila', 'koko',   # confirmed ours is better
}

# Hard-coded primary overrides (GT and kaikki both fail as primary)
primary_override = {
    'voi': 'butter',   # GT='Oh', kaikki primary also wrong; butter is the noun
}

# ── Step 3: merge ─────────────────────────────────────────────────────────────

def get_kaikki_glosses(fi, pos_hint=''):
    """Collect glosses from kaikki for this lemma, all POS combined."""
    all_glosses = []
    for key, glosses in kaikki_glosses.items():
        k_lemma, k_pos = key.split('|', 1)
        if k_lemma == fi.lower():
            for g in glosses:
                if g not in all_glosses:
                    all_glosses.append(g)
    return all_glosses


def normalize(s):
    return re.sub(r'^(to |a |an )', '', s.lower().strip())


changed = 0
for entry in data:
    fi = entry['fi']
    en_current = entry['en'] if isinstance(entry['en'], str) else entry['en'][0]

    # Primary: hard override → GT → fallback to current
    if fi in primary_override:
        primary = primary_override[fi]
    else:
        gt_primary = gt_by_fi.get(fi, '')
        if fi in gt_override or not gt_primary:
            primary = en_current
        else:
            primary = gt_primary
            # Preserve 'to ' prefix for verbs if GT dropped it
            if entry.get('pos') == 'verb' and not primary.startswith('to ') and not primary.startswith('To '):
                if en_current.startswith('to '):
                    primary = 'to ' + primary

    primary = re.sub(r' +', ' ', primary).strip()

    # Secondary: from kaikki, different from primary
    kaikki = get_kaikki_glosses(fi)
    meanings = [primary]
    seen = {normalize(primary)}
    for g in kaikki:
        if len(meanings) >= 2:
            break
        g = re.sub(r' +', ' ', g).strip()
        n = normalize(g)
        if n not in seen and n != normalize(en_current):
            meanings.append(g)
            seen.add(n)

    old = entry['en']
    entry['en'] = meanings if len(meanings) > 1 else meanings[0]

    if entry['en'] != old:
        changed += 1

# ── Step 4: remove proper-name entries and bad specific meanings ──────────────

# Detect inflected-only entries: all kaikki senses are grammatical, no real gloss.
INFL_PATTERNS = re.compile(r'^(inflection of|.+?\s(of|form of)\s\w)', re.I)

def is_inflected_only(fi):
    """Return True if every kaikki sense for this lemma is just an inflection ref."""
    senses = []
    for key, glosses in kaikki_glosses.items():
        if key.split('|')[0] != fi.lower():
            continue
        senses.extend(glosses)
    if not senses:
        return False
    return all(INFL_PATTERNS.match(s) or 'inflection of' in s.lower() for s in senses)

inflected = {d['fi'] for d in data if is_inflected_only(d['fi'])}
print(f"Inflected-only lemmas detected: {len(inflected)}")

# Words that are Finnish proper names misidentified as common words
remove_words = {'seppo', 'jorma', 'harri', 'jussi', 'mikko'} | inflected

# Per-word meaning overrides (remove specific bad alts)
meaning_overrides = {
    'voi':   ['butter', 'oh'],    # 'poor' is not a translation of voi
    'kansa': ['people'],          # 'callus' is completely wrong
    'jota':  ['which', 'whom'],   # 'iota' is a false cognate
    'ota':   ['take'],            # 'burr' is wrong; ota = imperative of ottaa
    'ammu':  ['to shoot'],        # remove 'moo-moo'
    'haloo': ['hello'],           # remove 'hullabaloo'
    'hanki': ['snowfield', 'blanket of snow'],
    'vasta': ['only', 'just'],    # 'bath broom' removed
}

data = [d for d in data if d['fi'] not in remove_words]

for entry in data:
    fi = entry['fi']
    if fi in meaning_overrides:
        entry['en'] = meaning_overrides[fi]
        if len(entry['en']) == 1:
            entry['en'] = entry['en'][0]

atomic_write_json(DATA_FILE, data)

print(f"\nDone. {changed} entries updated. Removed {len(remove_words)} proper-name entries.")
print("\nSample multi-meaning entries:")
for entry in data:
    if isinstance(entry['en'], list) and len(entry['en']) > 1:
        print(f"  {entry['fi']}: {entry['en']}")
    if sum(1 for e in data if isinstance(e['en'], list)) > 15:
        break

