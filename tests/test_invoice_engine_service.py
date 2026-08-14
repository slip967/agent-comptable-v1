from __future__ import annotations

import unittest

from agent_local_v1.app.invoice_engine_service import analyze_invoice_lines_strong


class InvoiceEngineServiceTests(unittest.TestCase):
    def _analyze(self, description: str, **context):
        tva = context.pop("tva", None)
        response = analyze_invoice_lines_strong(
            [{"description": description, "tva": tva}],
            context=context,
        )
        self.assertEqual(len(response.lines), 1)
        return response.lines[0]

    def test_basse_cote_boeuf_boucherie_is_found_exact_auto_ok(self) -> None:
        line = self._analyze(
            "BASSE COTE BOEUF",
            client_ape="4722Z",
            metier_hint="boucherie",
            tva=5.5,
        )

        self.assertEqual(line.referential_status, "found_exact")
        self.assertEqual(line.recommended_account, "6011")
        self.assertEqual(line.decision, "auto_ok")

    def test_basse_cote_boeuf_transport_context_is_not_auto_ok(self) -> None:
        line = self._analyze(
            "BASSE COTE BOEUF",
            client_ape="4932Z",
            metier_hint="transport",
            tva=5.5,
        )

        self.assertEqual(line.referential_status, "found_exact")
        self.assertNotEqual(line.decision, "auto_ok")

    def test_non_comptable_line_is_filtered(self) -> None:
        line = self._analyze("Option pour le paiement de la taxe d'apres les debits")

        self.assertEqual(line.referential_status, "non_comptable")
        self.assertEqual(line.decision, "non_comptable")

    def test_forfait_byou_stays_analysable(self) -> None:
        line = self._analyze(
            "Forfait B&You 260Go 5G",
            supplier="BOUYGUES TELECOM",
        )

        self.assertNotEqual(line.referential_status, "non_comptable")
        self.assertNotEqual(line.decision, "non_comptable")

    def test_bouygues_unknown_line_becomes_missing_candidate(self) -> None:
        line = self._analyze(
            "Pack entreprise corporate X9",
            supplier="BOUYGUES TELECOM",
        )

        self.assertEqual(line.referential_status, "missing_candidate")
        self.assertEqual(line.decision, "validation_humaine")

    def test_total_unknown_line_stays_unknown(self) -> None:
        line = self._analyze("ZXQ WLL 8891")

        self.assertEqual(line.referential_status, "unknown")
        self.assertEqual(line.decision, "rejeter")

    def test_lame_a_ruban_is_not_auto_ok_when_not_referential_exact(self) -> None:
        line = self._analyze(
            "LAME A RUBAN 1740X16 MM 4TPI",
            supplier="COUTELLERIE HALLES DE RUNGIS",
            client_ape="4722Z",
            metier_hint="boucherie",
        )

        self.assertIn(line.referential_status, {"found_fuzzy", "missing_candidate"})
        self.assertNotEqual(line.decision, "auto_ok")


if __name__ == "__main__":
    unittest.main()
