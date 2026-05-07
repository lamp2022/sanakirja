# tests/test_11.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from collections import defaultdict
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


def build_target_index_from_rows(rows):
    """Build {en_token: [(lemma, pos, rank)]} from list of mock *_top.csv row dicts."""
    idx = defaultdict(list)
    for r in rows:
        pos = r.get("pos", "")
        if not is_content_pos(pos):
            continue
        defs = r.get("defs", "")
        first_def = defs.split(" | ")[0] if defs else ""
        if should_skip_gloss(first_def):
            continue
        en_token = first_gloss_first_token(first_def)
        if not en_token:
            continue
        pos_norm = normalize_pos(pos)
        idx[en_token.lower()].append((r["lemma"], pos_norm, int(r.get("rank", 9999))))
    for k in idx:
        idx[k].sort(key=lambda x: x[2])
    return dict(idx)


def best_target(en, fi_pos, idx):
    en_key = en.lower()
    search_keys = [en_key]
    if en_key.startswith("to "):
        search_keys.append(en_key[3:])
    for key in search_keys:
        candidates = idx.get(key, [])
        if candidates:
            matched = [c for c in candidates if c[1] == fi_pos]
            return (matched[0] if matched else candidates[0])[0]
    return None


class TestTargetIndex(unittest.TestCase):

    def setUp(self):
        self.sv_rows = [
            {"lemma": "hus",    "pos": "noun", "defs": "house (building)", "rank": "1"},
            {"lemma": "spela",  "pos": "verb", "defs": "to play (a game)", "rank": "2"},
            {"lemma": "stor",   "pos": "adj",  "defs": "big, large",       "rank": "3"},
        ]
        self.sv_idx = build_target_index_from_rows(self.sv_rows)

    def test_noun_indexed(self):
        self.assertIn("house", self.sv_idx)
        self.assertEqual(self.sv_idx["house"][0][0], "hus")

    def test_verb_indexed_with_to(self):
        self.assertIn("to play", self.sv_idx)
        self.assertEqual(self.sv_idx["to play"][0][0], "spela")

    def test_adj_first_token(self):
        self.assertIn("big", self.sv_idx)
        self.assertEqual(self.sv_idx["big"][0][0], "stor")


class TestBestTarget(unittest.TestCase):

    def setUp(self):
        self.sv_rows = [
            {"lemma": "hus",   "pos": "noun", "defs": "house (building)", "rank": "1"},
            {"lemma": "hem",   "pos": "noun", "defs": "home",             "rank": "3"},
            {"lemma": "spela", "pos": "verb", "defs": "to play",          "rank": "2"},
        ]
        self.idx = build_target_index_from_rows(self.sv_rows)

    def test_exact_match(self):
        self.assertEqual(best_target("house", "noun", self.idx), "hus")

    def test_verb_with_to_prefix(self):
        self.assertEqual(best_target("to play", "verb", self.idx), "spela")

    def test_no_match_returns_none(self):
        self.assertIsNone(best_target("elephant", "noun", self.idx))

    def test_pos_preference(self):
        self.assertEqual(best_target("home", "noun", self.idx), "hem")

    def test_verb_to_fallback(self):
        # "to play" with fi_pos=verb should match "spela" which is indexed under "to play"
        self.assertEqual(best_target("to play", "verb", self.idx), "spela")


if __name__ == "__main__":
    unittest.main()
