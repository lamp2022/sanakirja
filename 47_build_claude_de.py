#!/usr/bin/env python3
"""Generate Claude EN→DE checkpoint. After running: python3 37_build_en_de.py"""
from _claude_checkpoint import run_checkpoint

SYSTEM = (
    "You are a precise English-German bilingual dictionary. "
    "For each English word or phrase, give exactly one German lemma/translation. "
    "Use the infinitive for verbs — no separable verb particles, no 'zu' prefix. "
    "Use singular indefinite for nouns — no article (Haus not das Haus). "
    "Use masculine singular for adjectives. "
    "Output only JSON, no commentary."
)

PROMPT = """\
Translate these English words/phrases to German.
Output a JSON object mapping each English input to its German translation.
Use lowercase German EXCEPT nouns (which are always capitalized in German).
Only one translation per word.

Words:
{words}

Output format: {{"word1": "de1", "word2": "de2", ...}}"""

if __name__ == "__main__":
    run_checkpoint("de", SYSTEM, PROMPT, "37_build_en_de.py", lowercase=False)
