#!/usr/bin/env python3
"""
34_build_claude_sv.py

Generate Claude inline EN→SV translations for the top 1000 EN keys (by rank).
Uses claude-haiku-4-5 for speed — mechanical translation task.
Saves results to ../sanakirja/claude_en_sv.jsonl (resumable checkpoint).

Run: python3 34_build_claude_sv.py
Reads en_fi_data.json for the EN key list. Appends to checkpoint, skips done.
"""

import json
import os
import sys
import time

SOURCES_DIR = "../sanakirja"
EN_FI_FILE = "en_fi_data.json"
CHECKPOINT = os.path.join(SOURCES_DIR, "claude_en_sv.jsonl")
TOP_N = 1000
BATCH_SIZE = 20  # words per API call
DELAY = 0.5      # seconds between batches


SYSTEM = (
    "You are a precise English-Swedish bilingual dictionary. "
    "For each English word or phrase, give exactly one Swedish lemma/translation. "
    "Use the infinitive for verbs (e.g. 'springa', not 'springer'). "
    "Use the singular indefinite for nouns. "
    "Output only JSON, no commentary."
)

PROMPT_TEMPLATE = """\
Translate these English words/phrases to Swedish.
Output a JSON object mapping each English input to its Swedish translation.
Use lowercase Swedish. Only one translation per word.

Words:
{words}

Output format: {{"word1": "sv1", "word2": "sv2", ...}}"""


def call_claude(words: list[str]) -> dict[str, str]:
    """Call Claude Haiku to translate a batch of words. Returns {en: sv}."""
    import anthropic
    client = anthropic.Anthropic()

    words_str = "\n".join(f"- {w}" for w in words)
    prompt = PROMPT_TEMPLATE.format(words=words_str)

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()

    # Extract JSON object from response
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in response: {text[:200]}")
    return json.loads(text[start:end])


def main():
    # Load EN base, take top 1000 by rank
    enfi = json.load(open(EN_FI_FILE, encoding="utf-8"))
    enfi_sorted = sorted(enfi, key=lambda e: e.get("rank", 9999))
    top_en = [
        e["en"] for e in enfi_sorted
        if isinstance(e.get("en"), str)
    ][:TOP_N]
    print(f"Top {TOP_N} EN keys loaded ({len(top_en)} valid)")

    # Load existing checkpoint
    done: dict[str, str] = {}
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done[rec["en"]] = rec["sv"]
                except (json.JSONDecodeError, KeyError):
                    pass
        print(f"Already done: {len(done):,}")

    todo = [en for en in top_en if en not in done]
    if not todo:
        print("All done — nothing to translate.")
        return

    print(f"Translating {len(todo):,} words in batches of {BATCH_SIZE} …")

    errors = 0
    total_done = len(done)
    with open(CHECKPOINT, "a") as ckpt:
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i : i + BATCH_SIZE]
            try:
                translations = call_claude(batch)
                for en in batch:
                    sv = translations.get(en, "").lower().strip()
                    if not sv:
                        # Try without "to " prefix for verbs
                        en_bare = en[3:] if en.lower().startswith("to ") else en
                        sv = translations.get(en_bare, "").lower().strip()
                    if sv:
                        rec = {"en": en, "sv": sv}
                        ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        ckpt.flush()
                        total_done += 1
                    else:
                        print(f"  WARN: no SV for '{en}'")
            except Exception as e:
                errors += 1
                print(f"  ERROR batch {i//BATCH_SIZE}: {e}")
                if errors > 5:
                    print("Too many errors — aborting.")
                    sys.exit(1)

            done_count = i + len(batch)
            if done_count % 100 == 0 or done_count >= len(todo):
                print(f"  {done_count}/{len(todo)} processed")
            time.sleep(DELAY)

    print(f"\nDone. {total_done:,} total translations in {CHECKPOINT}")


if __name__ == "__main__":
    main()
