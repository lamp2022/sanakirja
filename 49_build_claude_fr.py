#!/usr/bin/env python3
"""Generate Claude EN→FR checkpoint. After running: python3 45_build_en_fr.py"""
from _claude_checkpoint import run_checkpoint

SYSTEM = (
    "You are a precise English-French bilingual dictionary. "
    "For each English word or phrase, give exactly one French lemma/translation. "
    "Use the infinitive for verbs — no pronoun prefix (acheter not s'acheter). "
    "Use singular indefinite for nouns — no article (maison not la maison). "
    "Use masculine singular for adjectives. "
    "Output only JSON, no commentary."
)

PROMPT = """\
Translate these English words/phrases to French.
Output a JSON object mapping each English input to its French translation.
Use lowercase French. Only one translation per word.

Words:
{words}

Output format: {{"word1": "fr1", "word2": "fr2", ...}}"""

if __name__ == "__main__":
    run_checkpoint("fr", SYSTEM, PROMPT, "45_build_en_fr.py")
