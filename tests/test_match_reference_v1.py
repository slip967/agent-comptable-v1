from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MATCHER_PATH = ROOT_DIR / "10_match_reference_v1.py"


def _load_matcher_module():
    spec = importlib.util.spec_from_file_location("match_reference_v1_test_rules", MATCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MatchReferenceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matcher = _load_matcher_module()
        cls.refs = cls.matcher.load_references()

    def test_normalize_text_applies_common_ocr_fixes(self) -> None:
        normalized = self.matcher.normalize_text("SCEAU B&YOU 10 KGS")

        self.assertEqual(normalized, "seau byou 10 kg")

    def test_non_article_line_is_filtered_before_matching(self) -> None:
        matches = self.matcher.match_text(
            refs=self.refs,
            text="Option pour le paiement de la taxe d'apres les debits",
            fournisseur_hint=None,
            metier=None,
            client_ape_hint=None,
            supplier_ape_hint=None,
            top_n=3,
            tva_hint=20.0,
            include_charges=True,
            supplier_account_stats=None,
            validation_pattern_stats=None,
        )

        self.assertEqual(matches, [])

    def test_activity_context_can_auto_validate_exact_match(self) -> None:
        matches = self.matcher.match_text(
            refs=self.refs,
            text="BASSE COTE BOEUF",
            fournisseur_hint=None,
            metier=None,
            client_ape_hint="4722Z",
            supplier_ape_hint=None,
            top_n=3,
            tva_hint=5.5,
            include_charges=True,
            supplier_account_stats=None,
            validation_pattern_stats=None,
        )

        self.assertTrue(matches)
        top = matches[0]
        self.assertEqual(top["metier"], "boucherie")
        self.assertEqual(top["compte_comptable"], "6011")
        self.assertEqual(top["metier_coherence"], "coherente")
        self.assertEqual(top["decision_finale"], "auto_ok")

    def test_activity_mismatch_now_rejects_even_on_exact_text(self) -> None:
        matches = self.matcher.match_text(
            refs=self.refs,
            text="BASSE COTE BOEUF",
            fournisseur_hint=None,
            metier=None,
            client_ape_hint="4932Z",
            supplier_ape_hint=None,
            top_n=3,
            tva_hint=5.5,
            include_charges=True,
            supplier_account_stats=None,
            validation_pattern_stats=None,
        )

        self.assertTrue(matches)
        top = matches[0]
        self.assertEqual(top["metier"], "boucherie")
        self.assertEqual(top["metier_coherence"], "incoherente")
        self.assertEqual(top["decision_finale"], "rejeter")


if __name__ == "__main__":
    unittest.main()
