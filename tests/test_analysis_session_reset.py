from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

from agent_local_v1.app import analysis_batch_service


class AnalysisSessionResetTests(unittest.TestCase):
    def test_reset_clears_only_local_session_stores(self) -> None:
        batch_payload = analysis_batch_service._default_store()  # noqa: SLF001
        batch_payload.update(
            {
                "jobs": {"job-1": {"job_id": "job-1", "status": "completed"}},
                "order": ["job-1"],
                "results": {"invoice-1": {"invoice_id": "invoice-1"}},
                "results_order": ["invoice-1"],
            }
        )
        batch_payload["selection_state"]["next_startkey"] = "invoice-2"
        written_stores: list[dict] = []
        couch_guard = AssertionError("CouchDB must not be accessed during session reset")

        with (
            patch.object(
                analysis_batch_service,
                "_read_store_unlocked",
                side_effect=lambda: deepcopy(batch_payload),
            ),
            patch.object(
                analysis_batch_service,
                "_write_store_unlocked",
                side_effect=lambda payload: written_stores.append(deepcopy(payload)),
            ),
            patch.object(analysis_batch_service, "clear_all_validation_items", return_value=1),
            patch.object(
                analysis_batch_service,
                "list_validation_items",
                return_value=[
                    {
                        "validation_id": "validation-1",
                        "status": "validated",
                        "workflow_status": "COMPTABILISEE",
                    }
                ],
            ),
            patch.object(analysis_batch_service, "clear_all_history_events", return_value=1),
            patch.object(analysis_batch_service, "_resolve_invoice_db_name", side_effect=couch_guard),
            patch.object(analysis_batch_service, "fetch_unprocessed_invoices", side_effect=couch_guard),
            patch.object(analysis_batch_service, "analyze_invoice_by_id", side_effect=couch_guard),
            patch.object(analysis_batch_service, "resolve_invoice_pdf", side_effect=couch_guard),
        ):
            result = analysis_batch_service.reset_analysis_test_session()

        reset_batch = written_stores[-1]
        self.assertTrue(result["success"])
        self.assertTrue(result["couchdb_untouched"])
        self.assertEqual(result["batch_jobs_cleared"], 1)
        self.assertEqual(result["batch_results_cleared"], 1)
        self.assertEqual(result["validation_items_cleared"], 1)
        self.assertEqual(result["validated_entries_cleared"], 1)
        self.assertEqual(result["history_events_cleared"], 1)
        self.assertEqual(reset_batch["jobs"], {})
        self.assertEqual(reset_batch["results"], {})
        self.assertEqual(reset_batch["selection_state"]["next_startkey"], "")


if __name__ == "__main__":
    unittest.main()
