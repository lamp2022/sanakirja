# tests/test_08.py
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the canonical validate_fixture — no duplication
import importlib.util
spec = importlib.util.spec_from_file_location(
    "curate_fixture",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "08_curate_fixture.py")
)
mod = importlib.util.load_from_spec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
validate_fixture = mod.validate_fixture


class TestFixtureValidator(unittest.TestCase):

    def _valid(self, **overrides):
        base = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        base.update(overrides)
        return base

    def test_valid_entry_passes(self):
        self.assertEqual(validate_fixture([self._valid()]), [])

    def test_missing_key_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "fi_rank": 1}  # missing 'de'
        errors = validate_fixture([entry])
        self.assertTrue(any("missing keys" in e for e in errors))

    def test_empty_string_fails(self):
        errors = validate_fixture([self._valid(en="")])
        self.assertTrue(any("empty string" in e for e in errors))

    def test_invalid_pos_fails(self):
        errors = validate_fixture([self._valid(fi_pos="copula")])
        self.assertTrue(any("invalid fi_pos" in e for e in errors))

    def test_duplicate_fi_fi_pos_fails(self):
        e = self._valid()
        errors = validate_fixture([e, e])
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_same_fi_different_pos_passes(self):
        e1 = {"fi": "kuusi", "fi_pos": "num", "en": "six", "sv": "sex",
              "it": "sei", "fr": "six", "de": "sechs", "fi_rank": 135}
        e2 = {"fi": "kuusi", "fi_pos": "noun", "en": "spruce", "sv": "gran",
              "it": "abete", "fr": "épicéa", "de": "Fichte", "fi_rank": 300}
        self.assertEqual(validate_fixture([e1, e2]), [])

    def test_fi_rank_must_be_positive_int(self):
        errors = validate_fixture([self._valid(fi_rank="high")])
        self.assertTrue(any("fi_rank must be a positive int" in e for e in errors))

    def test_fi_rank_zero_fails(self):
        errors = validate_fixture([self._valid(fi_rank=0)])
        self.assertTrue(any("fi_rank must be a positive int" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
