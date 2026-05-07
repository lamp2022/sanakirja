# tests/test_12.py
import sys, os, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

SKIP_PATTERNS = [
    r"inflection of", r"plural of", r"past participle",
    r"third.person", r"first.person", r"second.person",
    r"alternative form of", r"obsolete form of",
    r"definite singular", r"definite plural",
]
import re

def validate_data(data):
    errors = []
    seen_fi = {}
    for i, row in enumerate(data):
        label = f"row[{i}] fi={row.get('fi','?')}"
        if "fi" not in row or not row["fi"]:
            errors.append(f"{label}: missing fi")
        if "en" not in row or not row["en"]:
            errors.append(f"{label}: missing en")
        for k, v in row.items():
            if v == "":
                errors.append(f"{label}: empty string for '{k}'")
            if isinstance(v, str):
                for pat in SKIP_PATTERNS:
                    if re.search(pat, v, re.IGNORECASE):
                        errors.append(f"{label}: '{k}' contains skip pattern: {v[:60]}")
        fi = row.get("fi")
        if fi:
            if fi in seen_fi:
                errors.append(f"{label}: duplicate fi lemma (first at row {seen_fi[fi]})")
            else:
                seen_fi[fi] = i
    if len(data) < 1500:
        errors.append(f"Too few rows: {len(data)}")
    if len(data) > 5000:
        errors.append(f"Too many rows: {len(data)}")
    return errors


class TestValidation(unittest.TestCase):

    BASE = {"fi": "talo", "en": "house", "sv": "hus"}

    def _row(self, **kwargs):
        r = dict(self.BASE)
        r.update(kwargs)
        return r

    def test_valid_row_passes(self):
        rows = [self._row(fi=f"fi{i}", en=f"en{i}") for i in range(1500)]
        self.assertEqual(validate_data(rows), [])

    def test_missing_fi_fails(self):
        row = {"en": "house", "sv": "hus"}
        errors = validate_data([row])
        self.assertTrue(any("missing fi" in e for e in errors))

    def test_missing_en_fails(self):
        row = {"fi": "talo", "sv": "hus"}
        errors = validate_data([row])
        self.assertTrue(any("missing en" in e for e in errors))

    def test_empty_string_fails(self):
        errors = validate_data([self._row(sv="")])
        self.assertTrue(any("empty string" in e for e in errors))

    def test_inflection_leak_fails(self):
        errors = validate_data([self._row(en="inflection of juuria")])
        self.assertTrue(any("skip pattern" in e for e in errors))

    def test_duplicate_fi_fails(self):
        row = self._row()
        errors = validate_data([row, row])
        self.assertTrue(any("duplicate fi lemma" in e for e in errors))

    def test_too_few_rows(self):
        errors = validate_data([self._row(fi=f"fi{i}") for i in range(10)])
        self.assertTrue(any("Too few rows" in e for e in errors))

    def test_too_many_rows(self):
        errors = validate_data([self._row(fi=f"fi{i}", en=f"word{i}") for i in range(5001)])
        self.assertTrue(any("Too many rows" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
