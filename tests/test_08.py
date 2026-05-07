# tests/test_08.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

REQUIRED_KEYS = {"fi", "fi_pos", "en", "sv", "it", "fr", "de", "fi_rank"}
VALID_POS = {"noun", "verb", "adj", "adv", "pron", "conj", "particle", "num", "intj", "det"}


def validate_fixture(entries):
    errors = []
    seen = {}
    for i, entry in enumerate(entries):
        label = f"entry[{i}] fi={entry.get('fi','?')}"
        missing = REQUIRED_KEYS - set(entry.keys())
        if missing:
            errors.append(f"{label}: missing keys: {missing}")
        for k in REQUIRED_KEYS - {"fi_rank"}:
            if entry.get(k) == "":
                errors.append(f"{label}: empty string for '{k}'")
        pos = entry.get("fi_pos", "")
        if pos not in VALID_POS:
            errors.append(f"{label}: invalid fi_pos '{pos}'")
        key = (entry.get("fi"), entry.get("fi_pos"))
        if key in seen:
            errors.append(f"{label}: duplicate (fi, fi_pos)")
        else:
            seen[key] = i
    return errors


class TestFixtureValidator(unittest.TestCase):

    def test_valid_entry_passes(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        self.assertEqual(validate_fixture([entry]), [])

    def test_missing_key_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "fi_rank": 1}  # missing 'de'
        errors = validate_fixture([entry])
        self.assertTrue(any("missing keys" in e for e in errors))

    def test_empty_string_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry])
        self.assertTrue(any("empty string" in e for e in errors))

    def test_invalid_pos_fails(self):
        entry = {"fi": "olla", "fi_pos": "copula", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry])
        self.assertTrue(any("invalid fi_pos" in e for e in errors))

    def test_duplicate_fi_fi_pos_fails(self):
        entry = {"fi": "olla", "fi_pos": "verb", "en": "to be", "sv": "vara",
                 "it": "essere", "fr": "être", "de": "sein", "fi_rank": 1}
        errors = validate_fixture([entry, entry])
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_same_fi_different_pos_passes(self):
        e1 = {"fi": "kuusi", "fi_pos": "num", "en": "six", "sv": "sex",
              "it": "sei", "fr": "six", "de": "sechs", "fi_rank": 150}
        e2 = {"fi": "kuusi", "fi_pos": "noun", "en": "spruce", "sv": "gran",
              "it": "abete", "fr": "épicéa", "de": "Fichte", "fi_rank": 300}
        self.assertEqual(validate_fixture([e1, e2]), [])


if __name__ == "__main__":
    unittest.main()
