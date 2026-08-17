from __future__ import annotations

import unittest
import importlib
import threading
import time
from copy import deepcopy
from unittest.mock import patch

from agent_local_v1.app import analysis_batch_service

human_validation_router_module = importlib.import_module(
    "agent_local_v1.app.routers.human_validation_router"
)


class AnalysisSessionResetTests(unittest.TestCase):
    def test_priority_sort_is_applied_before_batch_limit(self) -> None:
        candidates = [
            {"invoice_id": "late", "due_date": "2026-12-31"},
            {"invoice_id": "urgent", "due_date": "2026-08-18"},
            {"invoice_id": "middle", "due_date": "2026-09-01"},
        ]

        selected = analysis_batch_service._select_prioritized_items(  # noqa: SLF001
            candidates,
            "DUE_DATE",
            2,
        )

        self.assertEqual([item["invoice_id"] for item in selected], ["urgent", "middle"])
        self.assertEqual(
            analysis_batch_service._normalize_sort_strategy("urgency"),  # noqa: SLF001
            "DUE_DATE",
        )

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

    def test_twenty_invoices_use_four_parallel_workers(self) -> None:
        state_lock = threading.Lock()
        active_workers = 0
        max_active_workers = 0

        def fake_analyze(*args, **kwargs):
            nonlocal active_workers, max_active_workers
            with state_lock:
                active_workers += 1
                max_active_workers = max(max_active_workers, active_workers)
            try:
                time.sleep(0.05)
                return {"ok": True}
            finally:
                with state_lock:
                    active_workers -= 1

        items = [{"invoice_id": f"invoice-{index}"} for index in range(20)]
        started = time.perf_counter()
        with patch.object(analysis_batch_service, "_analyze_batch_item", side_effect=fake_analyze):
            outcomes = [
                future.result()
                for future in analysis_batch_service._iter_parallel_batch_futures(  # noqa: SLF001
                    "job-1",
                    "protected-couchdb-name",
                    items,
                    set(),
                    [],
                    max_workers=4,
                )
            ]
        duration = time.perf_counter() - started

        self.assertEqual(len(outcomes), 20)
        self.assertGreaterEqual(max_active_workers, 3)
        self.assertLess(duration, 0.65)

    def test_auto_validated_invoice_is_persisted_once_with_all_lines(self) -> None:
        result = {
            "invoice_id": "invoice-auto-1",
            "invoice_number": "AUTO-001",
            "supplier": "ORANGE",
            "client": "DOSSIER TEST",
            "workflow_status": "VALIDE_AUTO",
            "average_confidence": 98.5,
            "global_risk_level": "Faible",
            "amounts_balanced": True,
            "all_lines_exact_auto": True,
            "analysis_payload": {
                "invoice": {
                    "invoice_id": "invoice-auto-1",
                    "invoice_number": "AUTO-001",
                    "invoice_date": "2026-08-17",
                    "supplier": "ORANGE",
                    "client": "DOSSIER TEST",
                },
                "lines": [
                    {
                        "raw_text": "Abonnement mobile",
                        "amount_ht": 20.0,
                        "amount_ttc": 24.0,
                        "tva": 4.0,
                        "recommended_account": "626",
                        "recommended_account_label": "Télécommunications",
                        "confidence": 99.0,
                        "decision": "auto_ok",
                        "referential_status": "found_exact",
                    },
                    {
                        "raw_text": "Fibre",
                        "amount_ht": 30.0,
                        "amount_ttc": 36.0,
                        "tva": 6.0,
                        "recommended_account": "626",
                        "recommended_account_label": "Télécommunications",
                        "confidence": 98.0,
                        "decision": "auto_ok",
                        "referential_status": "found_exact",
                    },
                ],
            },
        }

        with (
            patch.object(analysis_batch_service, "upsert_validation_item") as upsert_item,
            patch.object(
                analysis_batch_service,
                "delete_pending_validation_items_for_invoice",
            ) as delete_pending_items,
            patch.object(analysis_batch_service, "_history_event_exists", return_value=False),
            patch.object(analysis_batch_service, "add_history_event") as add_history,
        ):
            analysis_batch_service._persist_completed_workflow_result(result)  # noqa: SLF001
            analysis_batch_service._persist_completed_workflow_result(result)  # noqa: SLF001

        self.assertEqual(upsert_item.call_count, 2)
        delete_pending_items.assert_called_once_with("invoice-auto-1")
        first_entry = upsert_item.call_args_list[0].args[0]
        self.assertEqual(first_entry["status"], "validated")
        self.assertEqual(first_entry["workflow_status"], "COMPTABILISEE")
        self.assertTrue(first_entry["auto_validated"])
        self.assertFalse(first_entry["human_intervention"])
        self.assertEqual(first_entry["validated_entry_id"], "invoice-auto-1-0")
        add_history.assert_called_once()
        self.assertTrue(result["workflow_persisted"])

    def test_validated_api_returns_auto_and_human_validated_items(self) -> None:
        stored_items = [
            {"validation_id": "auto-1", "status": "validated", "workflow_status": "COMPTABILISEE"},
            {"validation_id": "human-1", "status": "validated", "workflow_status": "COMPTABILISEE"},
            {"validation_id": "pending-1", "status": "pending_validation", "workflow_status": "A_CONTROLER"},
        ]
        with patch.object(human_validation_router_module, "list_validation_items", return_value=stored_items):
            payload = human_validation_router_module.get_human_validation_items(status="validated", limit=50)

        self.assertEqual([item["validation_id"] for item in payload["items"]], ["auto-1", "human-1"])

    def test_legacy_persisted_result_is_backfilled_into_workflow_store(self) -> None:
        result = {
            "result_id": "job-legacy:invoice-auto",
            "job_id": "job-legacy",
            "invoice_id": "invoice-auto",
            "status": "completed",
            "persisted": True,
            "workflow_status": "VALIDE_AUTO",
            "analysis_payload": {"invoice": {"invoice_id": "invoice-auto"}, "lines": [{}]},
        }
        payload = {
            "results": {result["result_id"]: result},
            "results_order": [result["result_id"]],
            "jobs": {},
            "order": [],
        }

        def mark_persisted(item):
            item["workflow_persisted"] = True

        with patch.object(
            analysis_batch_service,
            "_persist_completed_workflow_result",
            side_effect=mark_persisted,
        ) as persist_workflow:
            reconciled = analysis_batch_service._reconcile_persisted_batch_results_unlocked(payload)  # noqa: SLF001

        self.assertEqual(reconciled, 1)
        self.assertTrue(result["workflow_persisted"])
        persist_workflow.assert_called_once_with(result)


if __name__ == "__main__":
    unittest.main()
