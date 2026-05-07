#!/usr/bin/env python3
"""
Apply all manual quality fixes as final overrides on data.json.
Run after 13_build_meanings.py to preserve human corrections.
"""

import json
from utils import atomic_write_json

DATA_FILE = "data.json"

# All fixes accumulated through the QC + audit + Opus review process
OVERRIDES = {
    # Critical GT-confused homographs
    'vaara':  'danger',
    'työ':    'work',
    'häntä':  'tail',
    'pelätä': 'to fear',
    'ala':    'area',
    'jaa':    'well',
    'rakas':  'dear',
    # Confirmed-correct GT overrides (kept "ours is better")
    'voi':    ['butter', 'oh'],
    'kansa':  'people',
    'jota':   ['which', 'whom'],
    'ota':    'take',
    'haloo':  'hello',
    'hanki':  ['snowfield', 'blanket of snow'],
    'vasta':  ['just', 'only'],
    # Primary ordering — noun before adjective
    'talous':       ['economy', 'economic'],
    'teollisuus':   ['industry', 'industrial'],
    'kilpailu':     ['competition', 'competitive'],
    'oikeus':       ['right', 'legal'],
    'vaali':        ['election', 'electoral'],
    'rikos':        ['crime', 'criminal'],
    'maatalous':    ['agriculture', 'agricultural'],
    'viranomainen': ['official', 'authority'],
    'teko':         ['act', 'deed'],
    'sähkö':        ['electricity', 'electric'],
    'merkki':       ['mark', 'sign'],
    'lahti':        ['bay', 'Lahti'],
    'turku':        ['Turku', 'marketplace'],
    'hämäläinen':   'Tavastian',
    'kilpailija':   ['competitor', 'rival'],
    'valkoinen':    'white',
    # Suspicious / proper-name leakage cleaned
    'salo':           'deep forest',
    'mäkinen':        'hilly',
    'aho':            'clearing',
    'kari':           'rock',
    'tamperelainen':  'from Tampere',
    'noita':          'witch',
    'sokea':          'blind',
    'eri':            'different',
    'taas':           'again',
    'ikävä':          'sad',
    'pohjola':        'north',
    'ampua':          'to shoot',
    'oma':            'own',
    'pöytä':          ['table', 'desk'],
    # Earlier QC fixes
    'ilma':    ['air', 'weather'],
    'lista':   'list',
    'muru':    'crumb',
    'koira':   'dog',
    'sääli':   'pity',
    'tuomari': 'judge',
    'silmä':   'eye',
    'ehkä':    'perhaps',
    'poikia':  'to calve',
    'ja':      'and',
    'nyt':     'now',
    'mutta':   'but',
    # Country/language confusion
    'espanja': 'Spain',
    'italia':  'Italy',
    'ranska':  'France',
    'saksa':   'Germany',
    'kiina':   'China',
    'tanska':  'Denmark',
    'norja':   'Norway',
    # Joensuu/proper-noun gloss removals
    'joensuu': 'Joensuu',
    # Bad secondary fixes from earlier rounds
    'syy':     'reason',
    'vika':    'fault',
    'taata':   'to guarantee',
    'kukkia':  'to flower',
    'pieniä':  'to chop',  # but this should be removed (inflected form)
}

# Words to remove entirely (proper names, inflected-only forms)
REMOVE = {
    'seppo', 'jorma', 'harri', 'jussi', 'mikko',  # proper names
    'kesti', 'otin', 'sanoja', 'pieniä', 'kunnon', 'siitä', 'viestin',  # inflected forms
    'ammu',  # imperative of ampua
}


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    before = len(data)
    data = [d for d in data if d['fi'] not in REMOVE]
    removed = before - len(data)

    applied = 0
    for entry in data:
        if entry['fi'] in OVERRIDES:
            entry['en'] = OVERRIDES[entry['fi']]
            applied += 1

    atomic_write_json(DATA_FILE, data)

    print(f"Removed {removed} entries (proper names + inflected forms)")
    print(f"Applied {applied} overrides")
    print(f"Total: {len(data)} entries")


if __name__ == "__main__":
    main()
