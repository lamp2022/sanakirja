# tests/test_utils.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import unittest
from utils import first_gloss_first_token, should_skip_gloss, is_content_pos, normalize_pos


class TestFirstGlossFirstToken(unittest.TestCase):

    def test_simple_noun(self):
        self.assertEqual(first_gloss_first_token("house (building meant to serve as a human abode)"), "house")

    def test_verb_keeps_to_prefix(self):
        self.assertEqual(first_gloss_first_token("to play (participate in a sport)"), "to play")

    def test_comma_list_takes_first(self):
        self.assertEqual(first_gloss_first_token("large, big, great (of considerable size)"), "large")

    def test_semicolon_takes_first(self):
        self.assertEqual(first_gloss_first_token("car; automobile"), "car")

    def test_removes_parenthetical(self):
        self.assertEqual(first_gloss_first_token("cat (Felis catus)"), "cat")

    def test_empty_returns_none(self):
        self.assertIsNone(first_gloss_first_token(""))

    def test_none_returns_none(self):
        self.assertIsNone(first_gloss_first_token(None))

    def test_too_short_returns_none(self):
        self.assertIsNone(first_gloss_first_token("(only used in compounds)"))

    def test_strips_trailing_punctuation(self):
        self.assertEqual(first_gloss_first_token("red."), "red")

    def test_multi_word_verb(self):
        self.assertEqual(first_gloss_first_token("to be able to (used with infinitive)"), "to be able to")


class TestShouldSkipGloss(unittest.TestCase):

    def test_skip_inflection_of(self):
        self.assertTrue(should_skip_gloss("inflection of juuria: third-person singular"))

    def test_skip_plural_of(self):
        self.assertTrue(should_skip_gloss("plural of house"))

    def test_skip_past_participle(self):
        self.assertTrue(should_skip_gloss("past participle of go"))

    def test_skip_third_person(self):
        self.assertTrue(should_skip_gloss("third-person singular present indicative of play"))

    def test_skip_first_person(self):
        self.assertTrue(should_skip_gloss("first-person singular present of être"))

    def test_skip_alternative_form(self):
        self.assertTrue(should_skip_gloss("alternative form of colour"))

    def test_skip_obsolete(self):
        self.assertTrue(should_skip_gloss("obsolete form of go"))

    def test_skip_definite_singular(self):
        self.assertTrue(should_skip_gloss("definite singular of hus"))

    def test_keep_normal_noun(self):
        self.assertFalse(should_skip_gloss("house (building meant to serve as a human abode)"))

    def test_keep_normal_verb(self):
        self.assertFalse(should_skip_gloss("to play (participate in a sport)"))

    def test_skip_empty(self):
        self.assertTrue(should_skip_gloss(""))

    def test_skip_none(self):
        self.assertTrue(should_skip_gloss(None))

    def test_case_insensitive(self):
        self.assertTrue(should_skip_gloss("Inflection of juuria"))


class TestIsContentPos(unittest.TestCase):

    def test_noun(self):
        self.assertTrue(is_content_pos("noun"))

    def test_verb(self):
        self.assertTrue(is_content_pos("verb"))

    def test_adj(self):
        self.assertTrue(is_content_pos("adj"))

    def test_adjective(self):
        self.assertTrue(is_content_pos("adjective"))

    def test_adv(self):
        self.assertTrue(is_content_pos("adv"))

    def test_adverb(self):
        self.assertTrue(is_content_pos("adverb"))

    def test_pron_excluded(self):
        self.assertFalse(is_content_pos("pron"))

    def test_conj_excluded(self):
        self.assertFalse(is_content_pos("conj"))

    def test_article_excluded(self):
        self.assertFalse(is_content_pos("article"))

    def test_particle_excluded(self):
        self.assertFalse(is_content_pos("particle"))

    def test_num_excluded(self):
        self.assertFalse(is_content_pos("num"))

    def test_case_insensitive(self):
        self.assertTrue(is_content_pos("Noun"))


class TestNormalizePos(unittest.TestCase):

    def test_adjective_to_adj(self):
        self.assertEqual(normalize_pos("adjective"), "adj")

    def test_adverb_to_adv(self):
        self.assertEqual(normalize_pos("adverb"), "adv")

    def test_noun_unchanged(self):
        self.assertEqual(normalize_pos("noun"), "noun")

    def test_verb_unchanged(self):
        self.assertEqual(normalize_pos("verb"), "verb")

    def test_unknown_passthrough(self):
        self.assertEqual(normalize_pos("character"), "character")

    def test_case_insensitive(self):
        self.assertEqual(normalize_pos("Adjective"), "adj")


if __name__ == "__main__":
    unittest.main()
