# utils.py
import json
import os
import re
import tempfile
import time

SKIP_PREFIXES = (
    "inflection of", "plural of", "past participle of", "present participle of",
    "third-person singular", "first-person singular", "second-person singular",
    "alternative form of", "obsolete form of", "definite singular", "definite plural",
    "comparative of", "superlative of", "genitive of", "dative of", "accusative of",
    "gerund of", "imperative of", "feminine of", "masculine of",
    "abbreviation of", "initialism of", "acronym of", "synonym of",
    "misspelling of", "common misspelling of", "frequentative of",
    "diminutive of", "augmentative of", "archaic form of", "dated form of",
)

# Catch Finnish/Germanic inflection references anywhere in gloss
SKIP_CONTAINS = (
    "singular of", "plural of", " case of",
    "participle of", "connegative of", " tense of", "potential of",
    "verbal noun of", "infinitive of",
)

# Match "<inflection-prefix> form of …" — distinguishes inflection refs
# like "plural form of dog" from legit phrases like "a form of address".
SKIP_FORM_OF = re.compile(
    r"\b(plural|singular|genitive|partitive|inessive|elative|illative|"
    r"adessive|ablative|allative|essive|translative|abessive|comitative|"
    r"instructive|nominative|accusative|dative|absolute|comparative|"
    r"superlative|past|present|definite|indefinite|construct|alternative|"
    r"obsolete|archaic|dated|written|spoken|colloquial|elliptical) form of\b",
    re.IGNORECASE,
)

POS_NORMALIZE = {
    "noun": "noun", "verb": "verb",
    "adj": "adj", "adjective": "adj",
    "adv": "adv", "adverb": "adv",
}

CONTENT_POS = set(POS_NORMALIZE.keys()) | set(POS_NORMALIZE.values())


def first_gloss_first_token(gloss: str) -> str | None:
    """Extract the first clean English token from a kaikki gloss string.

    Preserves 'to ' prefix if already present in the gloss. Takes first comma/semicolon token.
    Drops parenthetical content. Returns None for empty, None, or too-short input.
    """
    if not gloss:
        return None
    s = re.sub(r"\s*\([^)]*\)", "", gloss)   # drop parentheticals
    s = re.sub(r"\s*\[[^\]]*\]", "", s)       # drop bracket content
    token = re.split(r"[,;]", s)[0].strip()
    token = token.strip(".'\" ")
    if not token or len(token) < 2:
        return None
    # Strip indefinite articles always; strip "the" only before lowercase words
    low = token.lower()
    if low.startswith("a ") or low.startswith("an "):
        token = token.split(" ", 1)[1]
    elif low.startswith("the ") and len(token) > 4 and token[4].islower():
        token = token[4:]
    token = token.strip()
    if not token or len(token) < 2:
        return None
    words = token.split()
    max_words = 4 if token.lower().startswith("to ") else 3
    if len(words) > max_words:
        return None
    return token


def should_skip_gloss(gloss: str | None) -> bool:
    """Return True if the gloss is an inflection reference, not a definition."""
    if not gloss:
        return True
    g = gloss.strip().lower()
    if any(g.startswith(p) for p in SKIP_PREFIXES):
        return True
    if any(p in g for p in SKIP_CONTAINS):
        return True
    if SKIP_FORM_OF.search(g):
        return True
    return False


def is_content_pos(pos: str) -> bool:
    """Return True if POS is a content word category (noun/verb/adj/adv)."""
    return pos.lower().strip() in CONTENT_POS


def normalize_pos(pos: str) -> str:
    """Normalize POS label to canonical form (adjective -> adj, adverb -> adv)."""
    return POS_NORMALIZE.get(pos.lower().strip(), pos.lower().strip())


def atomic_write_json(path: str, data, indent: int = 2) -> None:
    """Write JSON to a unique temp file in the same dir, then os.replace into place.

    Hardened against:
      - symlink attacks: mkstemp uses O_EXCL+O_CREAT, won't follow a pre-placed symlink
      - concurrent process races: each call gets a unique tmp name in the target dir
      - mid-write crashes: target file is only swapped via atomic os.replace
    """
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".sanakirja-tmp-", suffix=".json", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def gt(word: str, sl: str = "fi", tl: str = "en", retries: int = 3) -> str | None:
    """Translate a single word via the unauthenticated Google Translate endpoint.

    Returns the lowercased first translation, or None on failure. Handles:
      - 429 rate-limit / HTML responses (won't crash on .json()[0][0][0])
      - transient network errors (retry with exponential backoff)
      - unexpected response shape (returns None instead of IndexError)

    Caller must still rate-limit (~0.12s between requests is courteous).
    """
    import requests  # lazy: only callers that touch GT pay the import cost
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": sl, "tl": tl, "dt": "t", "q": word}
    headers = {"User-Agent": "sanakirja-builder/1.0 (https://github.com/lamp2022/sanakirja)"}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "")
            if "json" not in ct.lower():
                # Google sometimes returns HTML on rate-limit / blocked
                time.sleep(2 ** attempt)
                continue
            data = r.json()
            return data[0][0][0].strip().lower()
        except (requests.RequestException, ValueError, IndexError, KeyError, TypeError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None
