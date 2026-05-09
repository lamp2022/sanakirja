# Sanakirja — Project Notes for Claude

## Pending: Claude checkpoint generation for DE/IT/FR

**Must be run on local machine** (needs `ANTHROPIC_API_KEY` + raw kaikki source files in `../sanakirja/`).

```bash
# Step 1 — generate checkpoints (resumable, ~25 min each)
python3 47_build_claude_de.py
python3 48_build_claude_it.py
python3 49_build_claude_fr.py

# Step 2 — rebuild dictionaries to promote gt_only → gt+claude
python3 37_build_en_de.py
python3 41_build_en_it.py
python3 45_build_en_fr.py
```

Expected result: ~850–1,050 GT-only entries per language upgraded to multi-source confidence.
Remove this section once done.

---

## Project Overview

Multilingual dictionary published at https://lamp2022.github.io/sanakirja/

**Language pairs:** FI ↔ EN, EN ↔ SV, EN ↔ DE, EN ↔ IT, EN ↔ FR

**Pipeline scripts** are numbered (05–51). Run in order when rebuilding from scratch.
Large source files (kaikki dumps, GT/Claude checkpoints) live in `../sanakirja/` — not in git.

**Key files:**
- `data.json` — FI-anchored master (4,796 rows, served by index.html)
- `en_fi_data.json` — EN→FI base with frequency ranks (5,262 entries)
- `en_sv/de/it/fr.json` — per-pair EN→X dictionaries (5,252–5,262 entries each)
- `fixture.json` — 86 hand-curated grammar/function words
- `utils.py` — shared helpers (`atomic_write_json`, `first_gloss_first_token`, `gt`)
- `12_validate_output.py` — run before publishing; must pass
- `qc_audit.py <lang>` — quality audit per language (needs `../sanakirja/<lang>_freq_50k.txt`)

**Confidence tiers** (best → weakest): `4sources` > `3sources` > `folkets+gt+apert` >
`kaikki+gt` > `folkets+gt` > `gt+claude` > `kaikki_only` > `folkets_only` > `gt_only` > `curated`

**Before pushing to main:** run `python3 12_validate_output.py` — must pass.
