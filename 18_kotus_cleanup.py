#!/usr/bin/env python3
"""
Comprehensive cleanup applying:
  - Opus audit findings (mechanical filters + specific fixes)
  - Claude's own Finnish knowledge (validated against Kotus conventions)
  - User-confirmed corrections (e.g. osallistua → to attend)

Run AFTER 17_apply_overrides.py (or as the final step before browse).
"""

import json, re

DATA_FILE = "data.json"

# ── Mechanical filters for kaikki noise ───────────────────────────────────────

NOISE_PATTERNS = [
    re.compile(r'^\s*synonym of\b', re.I),
    re.compile(r'^\s*frequentative of\b', re.I),
    re.compile(r'^\s*verbal noun of\b', re.I),
    re.compile(r'^\s*diminutive of\b', re.I),
    re.compile(r'^\s*clipping of\b', re.I),
    re.compile(r'^\s*ellipsis of\b', re.I),
    re.compile(r'^\s*abbreviation of\b', re.I),
    re.compile(r'^the [a-z]+ language$', re.I),
    re.compile(r'^a person from\s*$', re.I),
    re.compile(r'^the (color|colour) ', re.I),
    re.compile(r'^a (single|young|capable|public|temporary|small|large|'
               r'famous|deep|narrow|good|outstanding|dull|female|male) ', re.I),
    re.compile(r'^any female\b', re.I),
    re.compile(r'^a (point|number|coffee) ', re.I),
    re.compile(r'^an? (urban|outstanding|unemployed|important) ', re.I),
    re.compile(r'^(a |an |the )?\w+ family$', re.I),
    re.compile(r"the (constellation|kurdish|finnish defense) ", re.I),
    re.compile(r'\)\s*$'),                                     # trailing )
    re.compile(r'^-\w'),                                        # affix glosses
    re.compile(r'sister-in-law of', re.I),
    re.compile(r'a male zillennial', re.I),
    re.compile(r'^(black-socked|coffee meeting|lawn|leafy|aaltonen|kankkunen|'
               r'haavisto|nurminen|lehtinen|hyvinkääläinen|helsinkian)$', re.I),
    re.compile(r"^any (?!.*\bother\b).*", re.I),  # "any female ruminant", etc
    re.compile(r"a (very )?hot place", re.I),
    re.compile(r"large (room|hill|belly)", re.I),
    re.compile(r"small (convenience|hill|forest)", re.I),
    re.compile(r"(young|old) (man|woman|tree|person)", re.I),
    re.compile(r"^(savoia|valtiollinen|statal)$", re.I),
    re.compile(r"^the [a-z]+ (constellation|games|council|forces)$", re.I),
]


def is_noise(s):
    if not isinstance(s, str):
        return False
    return any(p.search(s) for p in NOISE_PATTERNS)


def clean_str(s):
    """Mechanical clean: trailing parens, doublespaces, leading 'to to', etc."""
    s = re.sub(r'\s+\)\s*$', '', s)
    s = re.sub(r'^to to ', 'to ', s)
    s = re.sub(r'^to with ', '', s)         # 'to with a smile' → 'with a smile'
    s = re.sub(r'^to in ', '', s)           # 'to in hand' → 'in hand'
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ── Specific fixes from audit + user + Claude's own Finnish knowledge ─────────

CRITICAL_FIXES = {
    # Opus-identified critical errors
    'sukupuoli':       ['gender', 'sex'],
    'hymyillä':        'to smile',
    'myhäillä':        'to smile faintly',
    'puhumattakaan':   'let alone',
    'käytettävissä':   'available',
    'varmaan':         ['probably', 'surely'],
    'vastaväittäjä':   ['opponent', 'examiner'],
    'mustasukkainen':  'jealous',
    'jonne':           'where to',
    'firma':           'firm',
    'ulkoministeriö':  'Ministry of Foreign Affairs',
    'te-keskus':       'Employment and Economic Development Office',
    # User-flagged correction
    'osallistua':      ['to participate', 'to attend'],
    # Additional Claude's Finnish-knowledge corrections
    'kuulu':           'famous',          # adjective; verb is kuulua
    'turhan':          'unnecessarily',
    'riittävän':       'sufficiently',
    'paremmin':        'better',
    'parhaiten':       'best',
    'uskaltaa':        'to dare',
    'onneton':         'miserable',
    'itsenäinen':      'independent',
    'itsenäisyys':     'independence',
    'sade':            'rain',
    'avioliitto':      'marriage',
    'toistaa':         'to repeat',
    'kerrata':         'to repeat',
    'pelata':          'to play',
    'asentaa':         'to install',     # was wrongly "synonym of asettaa"
    'peruna':          'potato',          # was wrongly "synonym of päärynä"
    'kasvi':           'plant',           # was bogus "vuosikasvain"
    'sotku':           'mess',            # was wrong "sotilaskoti"
    'keskimääräinen':  'average',         # was wrong "keskinkertainen"
    'reipas':          'brisk',           # was wrong "runsas"
    'kankkunen':       'hangover',        # surname overrode the common word
    'alko':            ['Alko', 'liquor store'],
    'tauno':           None,              # mark for removal
    'nurminen':        None,
    'lehtinen':        None,
    'aaltonen':        None,
    'haavisto':        None,
}

# Removals Opus flagged
REMOVE = {
    # Inflected forms not real lemmas
    'lienee', 'paranee', 'kerrottava', 'oikeaan', 'paikalle', 'liikkeelle',
    'kylään', 'periksi', 'kahden', 'varaan', 'viereen', 'perään', 'päähän',
    'lasta', 'maista',
    # Surnames
    'aaltonen', 'haavisto', 'kankkunen', 'nurminen', 'lehtinen',
    # First names treated as nouns
    'tauno', 'sergei', 'sari', 'donna', 'diana', 'maya', 'jin', 'putin', 'penny',
    'tom',
    # Bare letters / abbreviations
    'mm', 'em', 'ay', 'ii', 'su', 'to', 'cd', 'la',
    # English loanword stub conflicts
    'just', 'sit',
}


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    before = len(data)
    data = [d for d in data if d['fi'] not in REMOVE]
    removed = before - len(data)

    fixed_critical = 0
    cleaned_secondary = 0
    cleaned_primary = 0

    for entry in data:
        fi = entry['fi']

        # Critical fix overrides
        if fi in CRITICAL_FIXES and CRITICAL_FIXES[fi] is not None:
            entry['en'] = CRITICAL_FIXES[fi]
            fixed_critical += 1
            continue

        # Mechanical cleanup of primary + secondaries
        en = entry['en']
        if isinstance(en, str):
            en = clean_str(en)
            if is_noise(en):
                # Primary is noise — try to find any non-noise from data, else drop
                continue
            entry['en'] = en
        else:
            cleaned = []
            for i, m in enumerate(en):
                m_clean = clean_str(m)
                if is_noise(m_clean):
                    if i == 0:
                        cleaned_primary += 1
                    else:
                        cleaned_secondary += 1
                    continue
                cleaned.append(m_clean)
            if not cleaned:
                continue  # All meanings were noise
            # Dedupe (case-insensitive)
            seen = set()
            deduped = []
            for m in cleaned:
                if m.lower() not in seen:
                    seen.add(m.lower())
                    deduped.append(m)
            entry['en'] = deduped[0] if len(deduped) == 1 else deduped[:3]

    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Removed:                 {removed} entries")
    print(f"Critical fixes applied:  {fixed_critical}")
    print(f"Bad primaries cleaned:   {cleaned_primary}")
    print(f"Bad secondaries cleaned: {cleaned_secondary}")
    print(f"Total entries:           {len(data)}")


if __name__ == "__main__":
    main()
