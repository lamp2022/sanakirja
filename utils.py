# utils.py
import re

SKIP_PREFIXES = (
    "inflection of", "plural of", "past participle of", "present participle of",
    "third-person singular", "first-person singular", "second-person singular",
    "alternative form of", "obsolete form of", "definite singular", "definite plural",
    "comparative of", "superlative of", "genitive of", "dative of", "accusative of",
    "gerund of", "imperative of", "feminine of", "masculine of",
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
    return token


def should_skip_gloss(gloss: str | None) -> bool:
    """Return True if the gloss is an inflection reference, not a definition."""
    if not gloss:
        return True
    g = gloss.strip().lower()
    return any(g.startswith(p) for p in SKIP_PREFIXES)


def is_content_pos(pos: str) -> bool:
    """Return True if POS is a content word category (noun/verb/adj/adv)."""
    return pos.lower().strip() in CONTENT_POS


def normalize_pos(pos: str) -> str:
    """Normalize POS label to canonical form (adjective -> adj, adverb -> adv)."""
    return POS_NORMALIZE.get(pos.lower().strip(), pos.lower().strip())
