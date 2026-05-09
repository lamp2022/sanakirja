#!/usr/bin/env python3
"""Generate Claude EN→IT checkpoint. After running: python3 41_build_en_it.py"""
from _claude_checkpoint import run_checkpoint

SYSTEM = (
    "You are a precise English-Italian bilingual dictionary. "
    "For each English word or phrase, give exactly one Italian lemma/translation. "
    "Use the infinitive for verbs — no reflexive suffix (correre not corrersi). "
    "Use singular indefinite for nouns — no article (casa not la casa). "
    "Use masculine singular for adjectives. "
    "Output only JSON, no commentary."
)

PROMPT = """\
Translate these English words/phrases to Italian.
Output a JSON object mapping each English input to its Italian translation.
Use lowercase Italian. Only one translation per word.

Words:
{words}

Output format: {{"word1": "it1", "word2": "it2", ...}}"""

if __name__ == "__main__":
    run_checkpoint("it", SYSTEM, PROMPT, "41_build_en_it.py")
