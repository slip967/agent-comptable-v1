from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_local_v1.app.memory import (
    backfill_analysis_record_signals,
    build_memory_decision,
    ensure_analysis_record_signals,
    persist_analysis_signal_backfill,
)
from agent_local_v1.app.schemas import AnalysisHistoryRecord, CandidateLine, HumanValidationRecord
from agent_local_v1.app.signal_ranker import build_memory_signal_package, rebuild_signal_package


ROOT_DIR = Path(__file__).resolve().parents[1]
MATCHER_PATH = ROOT_DIR / "10_match_reference_v1.py"


def _load_matcher_module():
    spec = importlib.util.spec_from_file_location("match_reference_v1_test", MATCHER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SignalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matcher = _load_matcher_module()

    def test_memory_signal_package_with_supplier_is_normalized(self) -> None:
        package = build_memory_signal_package(fournisseur_hint="EDF")

        self.assertEqual(package["final_score"], 100.0)
        self.assertEqual([signal["key"] for signal in package["signals"]], ["human_validation", "supplier_memory"])
        self.assertEqual(
            [signal["contribution"] for signal in package["signals"]],
            [70.0, 30.0],
        )

    def test_memory_decision_carries_backend_signals(self) -> None:
        record = HumanValidationRecord(
            article_source="Electricite mars 2025",
            fournisseur_hint="EDF",
            metier_hint="boulangerie",
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=20.0,
            decision_humaine="valider",
            compte_comptable_final="6061",
            categorie_finale="charges_externes",
            sous_categorie_finale="energie",
            commentaire=None,
            recommandation_ia=None,
            article_source_normalized="electricite mars 2025",
            lookup_key="electricite mars 2025::boulangerie::edf",
            created_at="2026-04-23T00:00:00+00:00",
        )

        decision = build_memory_decision("Electricite mars 2025", record)

        self.assertEqual(decision.source, "memory")
        self.assertEqual(decision.score_confiance, 100.0)
        self.assertEqual([signal.key for signal in decision.signals], ["human_validation", "supplier_memory"])

    def test_rebuild_signal_package_recomputes_weighted_score(self) -> None:
        package = rebuild_signal_package(
            [
                {"key": "text_similarity", "value": 0.8, "explanation": "texte"},
                {"key": "tva_coherence", "value": 1.0, "explanation": "tva"},
                {"key": "metier_coherence", "value": 1.0, "explanation": "metier"},
            ]
        )

        self.assertAlmostEqual(package["final_score"], 90.0, places=2)
        self.assertEqual(
            {signal["key"] for signal in package["signals"]},
            {"text_similarity", "tva_coherence", "metier_coherence"},
        )

    def test_ensure_analysis_record_signals_backfills_memory_history(self) -> None:
        record = AnalysisHistoryRecord(
            article_source="Electricite mars 2025",
            article_source_normalized="electricite mars 2025",
            lookup_key="electricite mars 2025::::edf",
            fournisseur_hint="EDF",
            metier_hint=None,
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=20.0,
            include_charges=True,
            categorie="charges_externes",
            sous_categorie="energie",
            compte_comptable="6061",
            score_confiance=100.0,
            decision="auto_ok",
            explication="memoire",
            source="memory",
            signals=[],
            candidats=[],
            created_at="2026-04-23T00:00:00+00:00",
        )

        updated = ensure_analysis_record_signals(record)

        self.assertEqual([signal.key for signal in updated.signals], ["human_validation", "supplier_memory"])

    def test_ensure_analysis_record_signals_backfills_engine_history_from_selected_candidate(self) -> None:
        selected_candidate = CandidateLine(
            base_cible="base.json",
            metier="boulangerie",
            article_source_match="Farine T55",
            article_canonique="Farine",
            categorie="achats",
            sous_categorie="matieres_premieres",
            compte_comptable="6011",
            score_confiance=91.0,
            final_score=91.0,
            score_texte=89.0,
            raison_match="test",
            tva_coherence="coherente",
            metier_coherence="coherente",
            decision="auto_ok",
            alertes=[],
            source_invoice_ids=[],
            signals=[
                {
                    "key": "human_validation",
                    "label": "Validation humaine precedente",
                    "family": "fort",
                    "weight": 0.2,
                    "value": 0.8,
                    "contribution": 20.0,
                    "explanation": "pattern humain",
                }
            ],
        )
        other_candidate = CandidateLine(
            base_cible="base.json",
            metier="boulangerie",
            article_source_match="Sucre",
            article_canonique="Sucre",
            categorie="achats",
            sous_categorie="matieres_premieres",
            compte_comptable="6012",
            score_confiance=70.0,
            final_score=70.0,
            score_texte=75.0,
            raison_match="test",
            tva_coherence="coherente",
            metier_coherence="coherente",
            decision="validation_humaine",
            alertes=[],
            source_invoice_ids=[],
            signals=[],
        )
        record = AnalysisHistoryRecord(
            article_source="Farine T55",
            article_source_normalized="farine t55",
            lookup_key="farine t55::boulangerie::",
            fournisseur_hint=None,
            metier_hint="boulangerie",
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=5.5,
            include_charges=True,
            categorie="achats",
            sous_categorie="matieres_premieres",
            compte_comptable="6011",
            score_confiance=91.0,
            decision="auto_ok",
            explication="engine",
            source="engine",
            signals=[],
            candidats=[other_candidate, selected_candidate],
            created_at="2026-04-23T00:00:00+00:00",
        )

        updated = ensure_analysis_record_signals(record)

        self.assertEqual(len(updated.signals), 1)
        self.assertEqual(updated.signals[0].key, "human_validation")

    def test_backfill_analysis_record_signals_returns_only_patched_records(self) -> None:
        already_complete = AnalysisHistoryRecord(
            article_source="Ligne complete",
            article_source_normalized="ligne complete",
            lookup_key="ligne complete::::",
            fournisseur_hint=None,
            metier_hint=None,
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=None,
            include_charges=True,
            categorie="charges_externes",
            sous_categorie="charges_generales",
            compte_comptable="6281",
            score_confiance=75.0,
            decision="validation_humaine",
            explication="ok",
            source="engine",
            signals=[],
            candidats=[
                CandidateLine(
                    base_cible="base.json",
                    metier="global",
                    article_source_match="Ligne complete",
                    article_canonique="Ligne complete",
                    categorie="charges_externes",
                    sous_categorie="charges_generales",
                    compte_comptable="6281",
                    score_confiance=75.0,
                    final_score=75.0,
                    score_texte=70.0,
                    raison_match="ok",
                    tva_coherence="coherente",
                    metier_coherence="a_verifier",
                    decision="validation_humaine",
                    alertes=[],
                    source_invoice_ids=[],
                    signals=[
                        {
                            "key": "text_similarity",
                            "label": "Similarite texte",
                            "family": "faible",
                            "weight": 0.15,
                            "value": 0.7,
                            "contribution": 100.0,
                            "explanation": "ok",
                        }
                    ],
                )
            ],
            created_at="2026-04-23T00:00:00+00:00",
        )
        already_complete = ensure_analysis_record_signals(already_complete)

        missing_signals = AnalysisHistoryRecord(
            article_source="Electricite mars 2025",
            article_source_normalized="electricite mars 2025",
            lookup_key="electricite mars 2025::::edf",
            fournisseur_hint="EDF",
            metier_hint=None,
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=20.0,
            include_charges=True,
            categorie="charges_externes",
            sous_categorie="energie",
            compte_comptable="6061",
            score_confiance=100.0,
            decision="auto_ok",
            explication="memoire",
            source="memory",
            signals=[],
            candidats=[],
            created_at="2026-04-23T00:00:00+00:00",
        )

        updated_records, patched_records = backfill_analysis_record_signals(
            [already_complete, missing_signals]
        )

        self.assertEqual(len(updated_records), 2)
        self.assertEqual(len(patched_records), 1)
        self.assertEqual(patched_records[0].article_source, "Electricite mars 2025")

    def test_persist_analysis_signal_backfill_uses_bulk_upsert(self) -> None:
        record = AnalysisHistoryRecord(
            article_source="Electricite mars 2025",
            article_source_normalized="electricite mars 2025",
            lookup_key="electricite mars 2025::::edf",
            fournisseur_hint="EDF",
            metier_hint=None,
            client_ape_hint=None,
            supplier_ape_hint=None,
            tva_hint=20.0,
            include_charges=True,
            categorie="charges_externes",
            sous_categorie="energie",
            compte_comptable="6061",
            score_confiance=100.0,
            decision="auto_ok",
            explication="memoire",
            source="memory",
            signals=[],
            candidats=[],
            created_at="2026-04-23T00:00:00+00:00",
        )
        updated = ensure_analysis_record_signals(record)

        with patch("agent_local_v1.app.memory.upsert_analysis_history_records") as mocked_upsert:
            persist_analysis_signal_backfill([updated])

        mocked_upsert.assert_called_once()

    def test_supplier_post_signal_downgrades_unseen_account(self) -> None:
        rows = [
            {
                "compte_comptable": "6281",
                "score_confiance": 92.0,
                "final_score": 92.0,
                "score_texte": 92.0,
                "tva_coherence": "coherente",
                "metier_coherence": "coherente",
                "decision_initiale": "auto_ok",
                "decision_finale": "auto_ok",
                "decision": "auto_ok",
                "signals": [
                    {"key": "text_similarity", "value": 0.92, "explanation": "texte"},
                    {"key": "tva_coherence", "value": 1.0, "explanation": "tva"},
                    {"key": "metier_coherence", "value": 1.0, "explanation": "metier"},
                ],
                "alertes": [],
            }
        ]
        supplier_stats = {
            "6011": {
                "count": 5,
                "share": 0.83,
                "total_matches": 6,
                "is_dominant": True,
                "latest_validation_at": "2026-04-23T00:00:00+00:00",
            },
            "607": {
                "count": 1,
                "share": 0.17,
                "total_matches": 6,
                "is_dominant": False,
                "latest_validation_at": "2026-04-22T00:00:00+00:00",
            },
        }

        updated = self.matcher.apply_supplier_account_signal(rows, supplier_stats)[0]

        self.assertEqual(updated["decision"], "validation_humaine")
        self.assertLess(updated["final_score"], 92.0)
        self.assertIn("historique_fournisseur_a_verifier", updated["alertes"])
        supplier_signal = next(signal for signal in updated["signals"] if signal["key"] == "supplier_memory")
        self.assertEqual(supplier_signal["value"], 0.6)

    def test_supplier_post_signal_keeps_known_account_stable(self) -> None:
        rows = [
            {
                "compte_comptable": "6011",
                "score_confiance": 94.0,
                "final_score": 94.0,
                "score_texte": 88.0,
                "tva_coherence": "coherente",
                "metier_coherence": "coherente",
                "decision_initiale": "auto_ok",
                "decision_finale": "auto_ok",
                "decision": "auto_ok",
                "signals": [
                    {"key": "text_similarity", "value": 0.88, "explanation": "texte"},
                    {"key": "supplier_memory", "value": 0.9, "explanation": "fournisseur"},
                ],
                "alertes": [],
            }
        ]
        supplier_stats = {
            "6011": {
                "count": 4,
                "share": 0.8,
                "total_matches": 5,
                "is_dominant": True,
                "latest_validation_at": "2026-04-23T00:00:00+00:00",
            }
        }

        updated = self.matcher.apply_supplier_account_signal(rows, supplier_stats)[0]

        self.assertEqual(updated["final_score"], 94.0)
        self.assertEqual(updated["decision"], "auto_ok")
        self.assertEqual(updated["alertes"], [])


if __name__ == "__main__":
    unittest.main()
