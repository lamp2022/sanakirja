"""Shared checkpoint runner for Claude EN→X translation scripts (47/48/49)."""
import json
import os
import sys
import time

EN_FI_FILE = "en_fi_data.json"
SOURCES_DIR = "../sanakirja"
TOP_N = 1000
BATCH_SIZE = 20
DELAY = 0.5


def _call_claude(client, words: list[str], system: str, prompt_template: str) -> dict[str, str]:
    words_str = "\n".join(f"- {w}" for w in words)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt_template.format(words=words_str)}],
    )
    text = msg.content[0].text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in response: {text[:200]}")
    return json.loads(text[start:end])


def run_checkpoint(lang: str, system: str, prompt_template: str, rebuild_script: str, lowercase: bool = True) -> None:
    """Translate top-1000 EN words to `lang`, appending to a resumable JSONL checkpoint.

    prompt_template must contain {words}. Set lowercase=False for German (nouns stay capitalised).
    rebuild_script is printed at the end as the next step — it is not executed.
    """
    import anthropic
    checkpoint = os.path.join(SOURCES_DIR, f"claude_en_{lang}.jsonl")

    with open(EN_FI_FILE, encoding="utf-8") as f:
        enfi = json.load(f)
    enfi_sorted = sorted(enfi, key=lambda e: e.get("rank", 9999))
    top_en = [e["en"] for e in enfi_sorted if isinstance(e.get("en"), str)][:TOP_N]
    print(f"Top {TOP_N} EN keys loaded ({len(top_en)} valid)")

    done: dict[str, str] = {}
    if os.path.exists(checkpoint):
        with open(checkpoint, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done[rec["en"]] = rec[lang]
                except (json.JSONDecodeError, KeyError):
                    pass
        print(f"Already done: {len(done):,}")

    todo = [en for en in top_en if en not in done]
    if not todo:
        print("All done — nothing to translate.")
        return

    print(f"Translating {len(todo):,} words in batches of {BATCH_SIZE} …")
    client = anthropic.Anthropic()
    errors = 0
    written = 0

    with open(checkpoint, "a", encoding="utf-8") as ckpt:
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i: i + BATCH_SIZE]
            try:
                translations = _call_claude(client, batch, system, prompt_template)
                for en in batch:
                    val = translations.get(en, "").strip()
                    if not val:
                        en_bare = en[3:] if en.lower().startswith("to ") else en
                        val = translations.get(en_bare, "").strip()
                    if lowercase:
                        val = val.lower()
                    if val:
                        ckpt.write(json.dumps({"en": en, lang: val}, ensure_ascii=False) + "\n")
                        written += 1
                    else:
                        print(f"  WARN: no {lang.upper()} for '{en}'")
                ckpt.flush()
            except Exception as e:
                errors += 1
                print(f"  ERROR batch {i // BATCH_SIZE}: {e}")
                if errors > 5:
                    print("Too many errors — aborting.")
                    sys.exit(1)

            done_count = i + len(batch)
            if done_count % 100 == 0 or done_count >= len(todo):
                print(f"  {done_count}/{len(todo)} processed")
            time.sleep(DELAY)

    print(f"\nDone. {len(done) + written:,} total in {checkpoint}")
    print(f"Now run: python3 {rebuild_script}")
