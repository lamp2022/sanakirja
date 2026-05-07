# tests/test_09.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


# ── Helpers replicated from 09 for testing ────────────────────────────────────

def build_fi_index_from_entries(entries, csc_ranks):
    """Build FI reverse index from a list of mock kaikki entry dicts."""
    fi_idx = defaultdict(list)
    fi_to_en = defaultdict(set)
    seen = set()
    for e in entries:
        pos = e.get("pos", "")
        if not is_content_pos(pos):
            continue
        word = e.get("word", "").strip()
        senses = e.get("senses", [])
        if not senses:
            continue
        first_gloss = (senses[0].get("glosses") or senses[0].get("raw_glosses") or [""])[0]
        if should_skip_gloss(first_gloss):
            continue
        en_token = first_gloss_first_token(first_gloss)
        if not en_token:
            continue
        pos_norm = normalize_pos(pos)
        key = (word, pos_norm)
        if key not in seen:
            seen.add(key)
            csc_rank = csc_ranks.get(word)
            fi_idx[en_token.lower()].append((word, pos_norm, csc_rank))
    for k in fi_idx:
        fi_idx[k].sort(key=lambda x: (x[2] is None, x[2] or 0))
    for en_token, candidates in fi_idx.items():
        for fi_lemma, _, _ in candidates:
            fi_to_en[fi_lemma].add(en_token)
    return dict(fi_idx), dict(fi_to_en)


def bidirectional_confidence(en_token, fi_lemma, fi_idx, fi_to_en):
    candidates = fi_idx.get(en_token.lower(), [])
    if candidates and candidates[0][0] == fi_lemma:
        return "auto"
    if en_token.lower() in fi_to_en.get(fi_lemma, set()):
        return "review"
    return "borderline"


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestFIIndex(unittest.TestCase):

    def setUp(self):
        self.mock_entries = [
            {"word": "talo", "pos": "noun",
             "senses": [{"glosses": ["house (building meant to serve as a human abode)"]}]},
            {"word": "pelata", "pos": "verb",
             "senses": [{"glosses": ["to play (participate in a sport)"]}]},
            {"word": "iso", "pos": "adj",
             "senses": [{"glosses": ["big, large, great (of considerable size)"]}]},
            {"word": "juuri", "pos": "verb",  # inflection — should be skipped
             "senses": [{"glosses": ["inflection of juuria: third-person singular past"]}]},
            {"word": "ei", "pos": "intj",  # non-content POS — should be skipped
             "senses": [{"glosses": ["no (negation)"]}]},
        ]
        self.csc_ranks = {"talo": 75, "pelata": 120, "iso": 29}
        self.fi_idx, self.fi_to_en = build_fi_index_from_entries(self.mock_entries, self.csc_ranks)

    def test_noun_indexed(self):
        self.assertIn("house", self.fi_idx)
        self.assertEqual(self.fi_idx["house"][0][0], "talo")

    def test_verb_indexed_with_to_prefix(self):
        self.assertIn("to play", self.fi_idx)
        self.assertEqual(self.fi_idx["to play"][0][0], "pelata")

    def test_adj_indexed_first_token(self):
        self.assertIn("big", self.fi_idx)
        self.assertEqual(self.fi_idx["big"][0][0], "iso")

    def test_inflection_skipped(self):
        juuri_in_idx = any(
            any(c[0] == "juuri" for c in v)
            for v in self.fi_idx.values()
        )
        self.assertFalse(juuri_in_idx)

    def test_non_content_pos_skipped(self):
        self.assertNotIn("no", self.fi_idx)

    def test_csc_rank_sorted(self):
        candidates = self.fi_idx.get("house", [])
        self.assertEqual(candidates[0][0], "talo")

    def test_fi_to_en_populated(self):
        self.assertIn("house", self.fi_to_en.get("talo", set()))

    def test_raw_glosses_fallback(self):
        entries = [
            {"word": "kävelyä", "pos": "noun",
             "senses": [{"raw_glosses": ["walk (act of walking)"]}]},
        ]
        fi_idx, _ = build_fi_index_from_entries(entries, {})
        self.assertIn("walk", fi_idx)
        self.assertEqual(fi_idx["walk"][0][0], "kävelyä")


class TestBidirectionalConfidence(unittest.TestCase):

    def setUp(self):
        self.fi_idx = {"house": [("talo", "noun", 75)], "home": [("koti", "noun", 90)]}
        self.fi_to_en = {"talo": {"house"}, "koti": {"home", "house"}}

    def test_auto_when_first_match(self):
        conf = bidirectional_confidence("house", "talo", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "auto")

    def test_review_when_indirect_match(self):
        conf = bidirectional_confidence("house", "koti", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "review")

    def test_borderline_when_no_match(self):
        conf = bidirectional_confidence("river", "joki", self.fi_idx, self.fi_to_en)
        self.assertEqual(conf, "borderline")


class TestLookupFiLogic(unittest.TestCase):
    """Tests the lookup_fi POS-preference and fallback logic (using the same logic inline)."""

    def _lookup(self, en_token, pos, fi_idx):
        candidates = fi_idx.get(en_token.lower(), [])
        if not candidates:
            return None, None
        matched = [c for c in candidates if c[1] == pos]
        pool = matched if matched else candidates
        return pool[0][0], pool[0][1]

    def test_pos_match_prefers_matching_pos(self):
        fi_idx = {"house": [("talo", "noun", 75), ("asua", "verb", 10)]}
        lemma, pos = self._lookup("house", "noun", fi_idx)
        self.assertEqual(lemma, "talo")
        self.assertEqual(pos, "noun")

    def test_pos_fallback_uses_top_candidate(self):
        fi_idx = {"house": [("talo", "noun", 75)]}
        lemma, pos = self._lookup("house", "verb", fi_idx)
        self.assertEqual(lemma, "talo")  # no verb match, falls back

    def test_missing_key_returns_none_none(self):
        fi_idx = {}
        lemma, pos = self._lookup("elephant", "noun", fi_idx)
        self.assertIsNone(lemma)
        self.assertIsNone(pos)


class TestConfidenceMerge(unittest.TestCase):
    """Tests that the confidence upgrade logic keeps the best-confidence entry."""

    def _merge(self, master, key, confidence, en_token, source_lang, source_lemma, fi_lemma, fi_pos, csc_ranks):
        """Replicate the main() merge logic for testing."""
        conf_order = {"auto": 0, "review": 1, "borderline": 2}
        fi_rank = csc_ranks.get(fi_lemma)
        if key not in master:
            master[key] = {
                "fi": fi_lemma, "fi_pos": fi_pos, "en": en_token,
                "confidence": confidence, "source_lang": source_lang,
                "source_lemma": source_lemma, "fi_rank": fi_rank,
            }
        else:
            existing = master[key]
            if conf_order[confidence] < conf_order[existing["confidence"]]:
                master[key].update({
                    "en": en_token, "confidence": confidence,
                    "source_lang": source_lang, "source_lemma": source_lemma,
                })
        return master

    def test_better_confidence_overwrites(self):
        master = {}
        key = ("talo", "noun")
        self._merge(master, key, "borderline", "home", "sv", "hem", "talo", "noun", {})
        self._merge(master, key, "auto", "house", "fi", "talo", "talo", "noun", {"talo": 75})
        self.assertEqual(master[key]["confidence"], "auto")
        self.assertEqual(master[key]["en"], "house")

    def test_worse_confidence_does_not_overwrite(self):
        master = {}
        key = ("talo", "noun")
        self._merge(master, key, "auto", "house", "fi", "talo", "talo", "noun", {"talo": 75})
        self._merge(master, key, "borderline", "home", "sv", "hem", "talo", "noun", {})
        self.assertEqual(master[key]["confidence"], "auto")
        self.assertEqual(master[key]["en"], "house")

    def test_same_confidence_keeps_first(self):
        master = {}
        key = ("talo", "noun")
        self._merge(master, key, "review", "house", "fi", "talo", "talo", "noun", {})
        self._merge(master, key, "review", "home", "sv", "hem", "talo", "noun", {})
        self.assertEqual(master[key]["en"], "house")  # first one kept


if __name__ == "__main__":
    unittest.main()
