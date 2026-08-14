from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Empty, Queue
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .config import COUCHDB_DATABASE
from .database import http_session
from .history_service import add_history_event, list_history_events
from .human_validation_store import add_validation_item, list_validation_items
from .invoice_engine_service import (  # noqa: PLC2701
    _resolve_invoice_db_name,
    analyze_invoice_by_id,
    determine_invoice_workflow_status,
    fetch_unprocessed_invoices,
    resolve_invoice_pdf,
)


BATCH_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "batch_analysis_results.json"
STORE_LOCK = threading.Lock()
ACTIVE_THREADS: dict[str, threading.Thread] = {}
RUNNING_JOB_STATUSES = {"queued", "running", "stopping"}
BATCH_PARALLEL_WORKERS = 4
BATCH_EVENT_SUBSCRIBERS: dict[str, set[Queue]] = {}
BATCH_EVENT_LOCK = threading.Lock()


def subscribe_analysis_batch(job_id: str) -> Queue:
    event_queue: Queue = Queue()
    with BATCH_EVENT_LOCK:
        BATCH_EVENT_SUBSCRIBERS.setdefault(str(job_id), set()).add(event_queue)
    return event_queue


def unsubscribe_analysis_batch(job_id: str, event_queue: Queue) -> None:
    with BATCH_EVENT_LOCK:
        subscribers = BATCH_EVENT_SUBSCRIBERS.get(str(job_id))
        if not subscribers:
            return
        subscribers.discard(event_queue)
        if not subscribers:
            BATCH_EVENT_SUBSCRIBERS.pop(str(job_id), None)


def publish_analysis_batch_event(job_id: str, event: dict[str, Any]) -> None:
    with BATCH_EVENT_LOCK:
        subscribers = list(BATCH_EVENT_SUBSCRIBERS.get(str(job_id), set()))
    for event_queue in subscribers:
        try:
            event_queue.put_nowait(event)
        except Exception:
            continue


def batch_event_snapshot(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        job = _get_job_unlocked(payload, str(job_id))
        if not job:
            raise KeyError(job_id)
        results = _collect_job_results_unlocked(
            payload,
            str(job_id),
            limit=max(20, int(job.get("limit") or 50)),
        )
        return {
            "type": "BATCH_SNAPSHOT",
            "job": _public_job(job),
            "results": results,
        }


def _publish_invoice_result(job_id: str, result: dict[str, Any], job: dict[str, Any]) -> None:
    result_type = "INVOICE_PROCESSED" if str(result.get("status") or "").lower() == "completed" else "INVOICE_ERROR"
    publish_analysis_batch_event(
        job_id,
        {
            "type": result_type,
            "invoice": _public_result(result),
            "progress": {
                "current": int(job.get("processed") or 0),
                "total": int(job.get("sampled_count") or job.get("selected_count") or job.get("limit") or 0),
                "success": int(job.get("success") or 0),
                "failed": int(job.get("failed") or 0),
            },
        },
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store() -> dict[str, Any]:
    return {
        "active_database": COUCHDB_DATABASE,
        "jobs": {},
        "order": [],
        "results": {},
        "results_order": [],
        "selection_state": {
            "database": COUCHDB_DATABASE,
            "next_startkey": "",
        },
    }


def _default_job(job_id: str, database: str, limit: int) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "database": database,
        "status": "queued",
        "limit": int(limit),
        "created_at": _now_iso(),
        "started_at": "",
        "finished_at": "",
        "processed": 0,
        "success": 0,
        "failed": 0,
        "sampled_count": 0,
        "current_invoice_id": "",
        "current_invoice_label": "",
        "duration_ms": 0,
        "message": "Lot en attente",
        "warnings": [],
        "selection_strategy": "unprocessed_first",
        "already_analyzed_count": 0,
        "candidates_found": 0,
        "selected_count": 0,
        "stop_requested": False,
        "saved_count": 0,
        "pending_save_count": 0,
        "last_saved_at": "",
        "sampled_items": [],
    }


def _default_result(result_id: str, job_id: str, invoice_id: str, database: str) -> dict[str, Any]:
    return {
        "result_id": result_id,
        "job_id": job_id,
        "invoice_id": invoice_id,
        "database": database,
        "status": "failed",
        "analysis_status": "error",
        "created_at": _now_iso(),
        "finished_at": "",
        "duration_ms": 0,
        "invoice_number": "",
        "invoice_date": "",
        "supplier": "",
        "client": "",
        "client_ape": "",
        "supplier_ape": "",
        "line_items_count": 0,
        "exploitable_lines_count": 0,
        "total_lines": 0,
        "auto_ok": 0,
        "validation_humaine": 0,
        "rejeter": 0,
        "non_comptable": 0,
        "unknown": 0,
        "articles_absents_referentiel": 0,
        "average_confidence": 0.0,
        "proposal_status": "partial",
        "auto_ok_lines": 0,
        "human_validation_lines": 0,
        "rejected_lines": 0,
        "pdf_status": "unknown",
        "pdf_message": "",
        "error_message": "",
        "workflow_status": "A_CONTROLER",
        "destination": "validation_humaine",
        "routing_reasons": [],
        "all_lines_exact_auto": False,
        "amounts_balanced": False,
        "is_duplicate": False,
        "global_decision": "",
        "global_risk_level": "",
        "can_validate_accounting": True,
        "analyzed_at": "",
        "analysis_payload": None,
        "persisted": False,
    }


def _resolve_pdf_status(invoice_id: str) -> tuple[str, str]:
    try:
        resolve_invoice_pdf(invoice_id)
        return "available", "PDF disponible"
    except FileNotFoundError as exc:
        message = str(exc).strip()
        lower = message.lower()
        if "inaccessible" in lower or "chemin source" in lower:
            return "inaccessible", "Acces reseau KO"
        if "absent" in lower or "introuvable" in lower:
            return "missing_file", "PDF absent"
        if "sans" in lower and "pdf" in lower:
            return "no_path", "Sans PDF"
        return "missing_file", message or "PDF absent"
    except RuntimeError as exc:
        message = str(exc).strip()
        lower = message.lower()
        if "inaccessible" in lower:
            return "inaccessible", "Acces reseau KO"
        if "sans" in lower and "pdf" in lower:
            return "no_path", "Sans PDF"
        return "unknown", message or "PDF inconnu"
    except Exception:
        return "unknown", "PDF inconnu"


def _ensure_store() -> None:
    BATCH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not BATCH_STORE_PATH.exists():
        BATCH_STORE_PATH.write_text(json.dumps(_default_store(), indent=2), encoding="utf-8")


def _read_store_unlocked() -> dict[str, Any]:
    _ensure_store()
    try:
        payload = json.loads(BATCH_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = _default_store()
    if not isinstance(payload, dict):
        payload = _default_store()
    payload.setdefault("active_database", COUCHDB_DATABASE)
    payload.setdefault("jobs", {})
    payload.setdefault("order", [])
    payload.setdefault("results", {})
    payload.setdefault("results_order", [])
    payload.setdefault(
        "selection_state",
        {
            "database": COUCHDB_DATABASE,
            "next_startkey": "",
        },
    )
    if not isinstance(payload["jobs"], dict):
        payload["jobs"] = {}
    if not isinstance(payload["order"], list):
        payload["order"] = []
    if not isinstance(payload["results"], dict):
        payload["results"] = {}
    if not isinstance(payload["results_order"], list):
        payload["results_order"] = []
    if not isinstance(payload["selection_state"], dict):
        payload["selection_state"] = {
            "database": COUCHDB_DATABASE,
            "next_startkey": "",
        }
    return payload


def _write_store_unlocked(payload: dict[str, Any]) -> None:
    _ensure_store()
    BATCH_STORE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_job_unlocked(payload: dict[str, Any], job: dict[str, Any]) -> None:
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        return
    payload["jobs"][job_id] = job
    order = [item for item in payload.get("order", []) if item != job_id]
    order.insert(0, job_id)
    payload["order"] = order[:50]


def _get_job_unlocked(payload: dict[str, Any], job_id: str) -> dict[str, Any] | None:
    job = payload.get("jobs", {}).get(job_id)
    return job if isinstance(job, dict) else None


def _find_running_job_unlocked(payload: dict[str, Any]) -> dict[str, Any] | None:
    for job_id in payload.get("order", []):
        job = _get_job_unlocked(payload, str(job_id))
        if job and str(job.get("status") or "").strip() in RUNNING_JOB_STATUSES:
            return job
    for job in payload.get("jobs", {}).values():
        if isinstance(job, dict) and str(job.get("status") or "").strip() in RUNNING_JOB_STATUSES:
            return job
    return None


def _reconcile_orphan_running_jobs_unlocked(payload: dict[str, Any]) -> int:
    """Mark persisted running jobs as failed when their worker thread no longer exists."""
    reconciled = 0
    for job in payload.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        status = str(job.get("status") or "").strip()
        if status not in RUNNING_JOB_STATUSES:
            continue
        job_id = str(job.get("job_id") or "").strip()
        thread = ACTIVE_THREADS.get(job_id)
        if thread is not None and thread.is_alive():
            continue
        ACTIVE_THREADS.pop(job_id, None)
        job["status"] = "failed"
        job["stop_requested"] = False
        job["finished_at"] = job.get("finished_at") or _now_iso()
        job["message"] = (
            "Lot interrompu avant la fin. Relancez un nouveau lot pour continuer."
        )
        warnings = list(job.get("warnings") or [])
        if "Job orphelin detecte apres redemarrage FastAPI." not in warnings:
            warnings.append("Job orphelin detecte apres redemarrage FastAPI.")
        job["warnings"] = warnings
        reconciled += 1
    return reconciled


def _set_result_unlocked(payload: dict[str, Any], result: dict[str, Any]) -> None:
    result_id = str(result.get("result_id") or "").strip()
    if not result_id:
        return
    payload["results"][result_id] = result
    order = [item for item in payload.get("results_order", []) if item != result_id]
    order.insert(0, result_id)
    payload["results_order"] = order[:1000]



def _serialize_sampled_item(item: Any) -> dict[str, Any]:
    invoice_id = str(getattr(item, "invoice_id", "") or getattr(item, "id", "") or "").strip()
    return {
        "invoice_id": invoice_id,
        "invoice_number": str(getattr(item, "invoice_number", "") or "").strip(),
        "supplier": str(getattr(item, "supplier", "") or "").strip(),
        "client": str(getattr(item, "client", "") or "").strip(),
    }


def _get_job_results_unlocked(payload: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result_id in payload.get("results_order", []):
        result = payload.get("results", {}).get(result_id)
        if not isinstance(result, dict):
            continue
        if str(result.get("job_id") or "") != job_id:
            continue
        items.append(result)
    return items


def _get_unsaved_job_results_unlocked(payload: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    return [
        result
        for result in _get_job_results_unlocked(payload, job_id)
        if not bool(result.get("persisted") or False)
    ]


def _dict_to_namespace(value: Any) -> Any:
    from types import SimpleNamespace
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_dict_to_namespace(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return value


def _save_job_results_unlocked(payload: dict[str, Any], job_id: str) -> tuple[int, int]:
    saved_count = 0
    failed_count = 0
    for result in _get_unsaved_job_results_unlocked(payload, job_id):
        status = str(result.get("status") or "").strip().lower()
        if status == "completed":
            analysis_payload = result.get("analysis_payload")
            if isinstance(analysis_payload, dict):
                response = _dict_to_namespace(analysis_payload)
                _apply_invoice_workflow_status(response, result)
            saved_count += 1
        else:
            failed_count += 1
        result["persisted"] = True
    return saved_count, failed_count


def _reconcile_persisted_batch_results_unlocked(payload: dict[str, Any]) -> int:
    """Persist legacy completed batch results before exposing the recorded list."""
    reconciled_count = 0
    for job_id in list(payload.get("order", [])):
        job = _get_job_unlocked(payload, str(job_id))
        if not job:
            continue

        status = str(job.get("status") or "").strip().lower()
        success_count = int(job.get("success") or 0)
        if status not in {"completed", "failed"} or success_count <= 0:
            continue

        unsaved_results = _get_unsaved_job_results_unlocked(payload, str(job_id))
        if not unsaved_results:
            continue

        saved_now, failed_now = _save_job_results_unlocked(payload, str(job_id))
        persisted_now = saved_now + failed_now
        if persisted_now <= 0:
            continue

        job["saved_count"] = int(job.get("saved_count") or 0) + persisted_now
        job["pending_save_count"] = len(_get_unsaved_job_results_unlocked(payload, str(job_id)))
        job["last_saved_at"] = _now_iso()
        if status == "failed" and job["pending_save_count"] == 0 and int(job.get("failed") or 0) == 0:
            job["status"] = "completed"
            job["message"] = "Lot termine: resultats recuperes et enregistres."
        _set_job_unlocked(payload, job)
        reconciled_count += persisted_now
    return reconciled_count


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": str(job.get("job_id") or ""),
        "database": str(job.get("database") or COUCHDB_DATABASE),
        "status": str(job.get("status") or "queued"),
        "limit": int(job.get("limit") or 0),
        "created_at": str(job.get("created_at") or ""),
        "started_at": str(job.get("started_at") or ""),
        "finished_at": str(job.get("finished_at") or ""),
        "processed": int(job.get("processed") or 0),
        "success": int(job.get("success") or 0),
        "failed": int(job.get("failed") or 0),
        "sampled_count": int(job.get("sampled_count") or 0),
        "current_invoice_id": str(job.get("current_invoice_id") or ""),
        "current_invoice_label": str(job.get("current_invoice_label") or ""),
        "duration_ms": int(job.get("duration_ms") or 0),
        "message": str(job.get("message") or ""),
        "warnings": list(job.get("warnings") or []),
        "selection_strategy": str(job.get("selection_strategy") or "unprocessed_first"),
        "already_analyzed_count": int(job.get("already_analyzed_count") or 0),
        "candidates_found": int(job.get("candidates_found") or 0),
        "selected_count": int(job.get("selected_count") or 0),
        "stop_requested": bool(job.get("stop_requested") or False),
        "saved_count": int(job.get("saved_count") or 0),
        "pending_save_count": int(job.get("pending_save_count") or 0),
        "last_saved_at": str(job.get("last_saved_at") or ""),
    }


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "result_id": str(result.get("result_id") or ""),
        "job_id": str(result.get("job_id") or ""),
        "invoice_id": str(result.get("invoice_id") or ""),
        "database": str(result.get("database") or COUCHDB_DATABASE),
        "status": str(result.get("status") or "failed"),
        "analysis_status": str(result.get("analysis_status") or "error"),
        "created_at": str(result.get("created_at") or ""),
        "finished_at": str(result.get("finished_at") or ""),
        "duration_ms": int(result.get("duration_ms") or 0),
        "invoice_number": str(result.get("invoice_number") or ""),
        "invoice_date": str(result.get("invoice_date") or ""),
        "supplier": str(result.get("supplier") or ""),
        "client": str(result.get("client") or ""),
        "client_ape": str(result.get("client_ape") or ""),
        "supplier_ape": str(result.get("supplier_ape") or ""),
        "line_items_count": int(result.get("line_items_count") or 0),
        "exploitable_lines_count": int(result.get("exploitable_lines_count") or 0),
        "total_lines": int(result.get("total_lines") or 0),
        "auto_ok": int(result.get("auto_ok") or 0),
        "validation_humaine": int(result.get("validation_humaine") or 0),
        "rejeter": int(result.get("rejeter") or 0),
        "non_comptable": int(result.get("non_comptable") or 0),
        "unknown": int(result.get("unknown") or 0),
        "articles_absents_referentiel": int(result.get("articles_absents_referentiel") or 0),
        "average_confidence": float(result.get("average_confidence") or 0.0),
        "proposal_status": str(result.get("proposal_status") or "partial"),
        "auto_ok_lines": int(result.get("auto_ok_lines") or 0),
        "human_validation_lines": int(result.get("human_validation_lines") or 0),
        "rejected_lines": int(result.get("rejected_lines") or 0),
        "pdf_status": str(result.get("pdf_status") or "unknown"),
        "pdf_message": str(result.get("pdf_message") or ""),
        "error_message": str(result.get("error_message") or ""),
        "workflow_status": str(result.get("workflow_status") or "A_CONTROLER"),
        "destination": str(result.get("destination") or "validation_humaine"),
        "routing_reasons": list(result.get("routing_reasons") or []),
        "all_lines_exact_auto": bool(result.get("all_lines_exact_auto") or False),
        "amounts_balanced": bool(result.get("amounts_balanced") or False),
        "is_duplicate": bool(result.get("is_duplicate") or False),
        "global_decision": str(result.get("global_decision") or ""),
        "global_risk_level": str(result.get("global_risk_level") or ""),
        "can_validate_accounting": bool(result.get("can_validate_accounting") if result.get("can_validate_accounting") is not None else True),
        "invoice_label": str(result.get("invoice_label") or ""),
        "analyzed_at": str(result.get("analyzed_at") or result.get("finished_at") or ""),
        "analysis_payload": result.get("analysis_payload"),
        "persisted": bool(result.get("persisted") or False),
    }


def _collect_job_results_unlocked(
    payload: dict[str, Any],
    job_id: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    max_items = max(1, min(int(limit or 500), 500))
    for result_id in payload.get("results_order", []):
        result = payload.get("results", {}).get(result_id)
        if not isinstance(result, dict):
            continue
        if str(result.get("job_id") or "") != job_id:
            continue
        items.append(_public_result(result))
        if len(items) >= max_items:
            break
    return items


def _invoice_label(item: Any) -> str:
    supplier = str(getattr(item, "supplier", "") or "").strip()
    invoice_number = str(getattr(item, "invoice_number", "") or "").strip()
    invoice_id = str(getattr(item, "invoice_id", "") or getattr(item, "id", "") or "").strip()
    parts = [part for part in [supplier, invoice_number, invoice_id] if part]
    return " ? ".join(parts[:3]) if parts else invoice_id


def _build_result_from_response(
    *,
    job_id: str,
    database: str,
    invoice_id: str,
    invoice_label: str,
    response: Any,
    duration_ms: int,
    existing_invoice_ids: set[str] | None = None,
) -> dict[str, Any]:
    invoice = getattr(response, "invoice", None)
    summary = getattr(response, "summary", None)
    proposal = getattr(response, "accounting_proposal", None)
    pdf_status, pdf_message = _resolve_pdf_status(invoice_id)
    if hasattr(response, "model_dump"):
        analysis_payload = response.model_dump()  # pydantic v2
    elif hasattr(response, "dict"):
        analysis_payload = response.dict()  # pragma: no cover - pydantic v1 fallback
    else:
        analysis_payload = None

    result_id = f"{job_id}:{invoice_id}"
    result = _default_result(result_id, job_id, invoice_id, database)
    routing = determine_invoice_workflow_status(
        response,
        existing_invoice_ids=existing_invoice_ids,
        invoice_id=invoice_id,
    )
    workflow_status = str(routing.get("workflow_status") or "A_CONTROLER")
    if invoice is not None:
        try:
            invoice.status = workflow_status
        except Exception:
            pass
    result.update(
        {
            "status": "completed",
            "analysis_status": "success",
            "finished_at": _now_iso(),
            "duration_ms": int(duration_ms),
            "invoice_number": str(getattr(invoice, "invoice_number", "") or ""),
            "invoice_date": str(getattr(invoice, "invoice_date", "") or ""),
            "supplier": str(getattr(invoice, "supplier", "") or ""),
            "client": str(getattr(invoice, "client", "") or ""),
            "client_ape": str(getattr(invoice, "client_ape", "") or ""),
            "supplier_ape": str(getattr(invoice, "supplier_ape", "") or ""),
            "line_items_count": int(getattr(invoice, "total_lines", 0) or 0),
            "exploitable_lines_count": int(getattr(invoice, "exploitable_lines", 0) or 0),
            "total_lines": int(getattr(summary, "total_lines", 0) or 0),
            "auto_ok": int(getattr(summary, "auto_ok", 0) or 0),
            "validation_humaine": int(getattr(summary, "validation_humaine", 0) or 0),
            "rejeter": int(getattr(summary, "rejeter", 0) or 0),
            "non_comptable": int(getattr(summary, "non_comptable", 0) or 0),
            "unknown": int(getattr(summary, "unknown", 0) or 0),
            "articles_absents_referentiel": int(getattr(summary, "articles_absents_referentiel", 0) or 0),
            "average_confidence": float(getattr(summary, "average_confidence", 0.0) or 0.0),
            "proposal_status": str(getattr(proposal, "proposal_status", "partial") or "partial"),
            "auto_ok_lines": int(getattr(summary, "auto_ok", 0) or 0),
            "human_validation_lines": int(getattr(summary, "validation_humaine", 0) or 0),
            "rejected_lines": int(getattr(summary, "rejeter", 0) or 0),
            "pdf_status": pdf_status,
            "pdf_message": pdf_message,
            "error_message": "",
            "workflow_status": workflow_status,
            "destination": str(routing.get("destination") or "validation_humaine"),
            "routing_reasons": list(routing.get("routing_reasons") or []),
            "all_lines_exact_auto": bool(routing.get("all_lines_exact_auto") or False),
            "amounts_balanced": bool(routing.get("amounts_balanced") or False),
            "is_duplicate": bool(routing.get("is_duplicate") or False),
            "global_decision": str(routing.get("global_decision") or ""),
            "global_risk_level": str(routing.get("global_risk_level") or ""),
            "can_validate_accounting": bool(routing.get("can_validate_accounting") if routing.get("can_validate_accounting") is not None else True),
            "invoice_label": invoice_label,
            "analyzed_at": _now_iso(),
            "analysis_payload": analysis_payload,
        }
    )
    return result


def _line_confidence(line: Any) -> float:
    try:
        return float(getattr(line, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _history_event_exists(invoice_id: str, event_type: str, line_id: str = "") -> bool:
    if not invoice_id:
        return False
    events = list_history_events(limit=10000, invoice_id=invoice_id)
    for event in events:
        if str(event.get("event_type") or "").strip() != event_type:
            continue
        if line_id and str(event.get("line_id") or "").strip() != line_id:
            continue
        return True
    return False


def _validation_item_exists(invoice_id: str, line_id: str) -> bool:
    if not invoice_id or not line_id:
        return False
    items = list_validation_items(limit=10000)
    for item in items:
        if str(item.get("invoice_id") or "").strip() != invoice_id:
            continue
        if str(item.get("line_id") or "").strip() != line_id:
            continue
        return True
    return False



def _line_requires_human_validation(line: Any) -> bool:
    decision = str(getattr(line, "decision", "") or "").strip().lower()
    referential_status = str(getattr(line, "referential_status", "") or "").strip().lower()
    evidence_status = str(getattr(line, "evidence_status", "") or "").strip().lower()
    confidence = _line_confidence(line)
    if decision == "non_comptable" or referential_status == "non_comptable":
        return False
    return (
        referential_status != "found_exact"
        or decision != "auto_ok"
        or confidence < 90.0
        or evidence_status == "missing"
    )

def _route_controlled_invoice_to_validation(response: Any, result: dict[str, Any]) -> None:
    invoice = getattr(response, "invoice", None)
    lines = list(getattr(response, "lines", []) or [])
    invoice_id = str(result.get("invoice_id") or "").strip()
    invoice_number = str(getattr(invoice, "invoice_number", "") or "")
    supplier = str(getattr(invoice, "supplier", "") or "")
    client = str(getattr(invoice, "client", "") or "")

    candidate_lines = [
        (index, line)
        for index, line in enumerate(lines, start=1)
        if _line_requires_human_validation(line)
    ]
    if not candidate_lines:
        candidate_lines = [
            (index, line)
            for index, line in enumerate(lines, start=1)
            if str(getattr(line, "decision", "") or "").strip().lower() != "non_comptable"
            and str(getattr(line, "referential_status", "") or "").strip().lower() != "non_comptable"
        ]

    for index, line in candidate_lines:
        confidence = _line_confidence(line)

        line_id = f"line_{index}"
        if _validation_item_exists(invoice_id, line_id):
            continue

        payload = {
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "supplier": supplier,
            "client": client,
            "line_id": line_id,
            "raw_text": str(getattr(line, "raw_text", "") or ""),
            "cleaned_text": str(getattr(line, "cleaned_text", "") or ""),
            "amount_ht": getattr(line, "amount_ht", None),
            "amount_ttc": getattr(line, "amount_ttc", None),
            "tva": getattr(line, "tva", None),
            "referential_status": str(getattr(line, "referential_status", "") or ""),
            "recommended_account": str(getattr(line, "recommended_account", "") or ""),
            "recommended_account_label": str(getattr(line, "recommended_account_label", "") or ""),
            "confidence": confidence,
            "risk_level": str(getattr(line, "risk_level", "") or ""),
            "decision": str(getattr(line, "decision", "") or ""),
            "decision_reason": str(getattr(line, "decision_reason", "") or ""),
            "evidence_status": str(getattr(line, "evidence_status", "") or ""),
            "quality_status": str(getattr(line, "quality_status", "") or "a_controler"),
            "source_invoice_ids": list(getattr(line, "source_invoice_ids", []) or []),
            "invoice_paths_sources": list(getattr(line, "invoice_paths_sources", []) or []),
            "partitions_sources": list(getattr(line, "partitions_sources", []) or []),
            "ape_context": list(getattr(line, "ape_context", []) or []),
            "taux_tva": getattr(line, "taux_tva", None),
            "categorie": getattr(line, "categorie", None),
            "sous_categorie": getattr(line, "sous_categorie", None),
            "type_fournisseur": getattr(line, "type_fournisseur", None),
            "top_candidates": _json_safe(list(getattr(line, "top_candidates", []) or [])),
            "status": "pending_validation",
            "source": "analysis_batch",
            "workflow_status": "A_CONTROLER",
            "invoice_average_confidence": float(result.get("average_confidence") or 0.0),
            "invoice_global_decision": str(result.get("global_decision") or ""),
            "invoice_global_risk_level": str(result.get("global_risk_level") or ""),
            "can_validate_accounting": bool(result.get("can_validate_accounting") if result.get("can_validate_accounting") is not None else True),
            "routing_reasons": list(result.get("routing_reasons") or []),
            "amounts_balanced": bool(result.get("amounts_balanced") or False),
            "all_lines_exact_auto": bool(result.get("all_lines_exact_auto") or False),
            "is_duplicate": bool(result.get("is_duplicate") or False),
        }
        add_validation_item(_json_safe(payload))
        if not _history_event_exists(invoice_id, "sent_to_human_validation", line_id):
            add_history_event(
                {
                    "event_type": "sent_to_human_validation",
                    "source": "analysis_batch",
                    "invoice_id": invoice_id,
                    "invoice_number": invoice_number,
                    "supplier": supplier,
                    "client": client,
                    "line_id": line_id,
                    "raw_text": str(getattr(line, "raw_text", "") or ""),
                    "engine_account": str(getattr(line, "recommended_account", "") or ""),
                    "message": "Ligne envoyee en validation humaine apres analyse du lot.",
                }
            )


def _apply_invoice_workflow_status(response: Any, result: dict[str, Any]) -> None:
    workflow_status = str(result.get("workflow_status") or "A_CONTROLER").strip().upper()
    if workflow_status in {"VALIDE_AUTO", "COMPTABILISEE", "COMPTABILIS?E"}:
        return
    _route_controlled_invoice_to_validation(response, result)


def _build_failed_result(
    *,
    job_id: str,
    database: str,
    invoice_id: str,
    invoice_label: str,
    duration_ms: int,
    error_message: str,
) -> dict[str, Any]:
    result_id = f"{job_id}:{invoice_id}"
    pdf_status, pdf_message = _resolve_pdf_status(invoice_id)
    result = _default_result(result_id, job_id, invoice_id, database)
    result.update(
        {
            "status": "failed",
            "analysis_status": "error",
            "finished_at": _now_iso(),
            "duration_ms": int(duration_ms),
            "pdf_status": pdf_status,
            "pdf_message": pdf_message,
            "error_message": error_message,
            "invoice_label": invoice_label,
            "analyzed_at": _now_iso(),
            "analysis_payload": None,
        }
    )
    return result


def _update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        job = _get_job_unlocked(payload, job_id)
        if not job:
            return None
        job.update(fields)
        _set_job_unlocked(payload, job)
        _write_store_unlocked(payload)
        return job


def stop_analysis_batch_job(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        job = _get_job_unlocked(payload, job_id)
        if not job:
            raise KeyError(job_id)
        status = str(job.get("status") or "").strip()
        if status not in RUNNING_JOB_STATUSES:
            return _public_job(job)
        job["stop_requested"] = True
        job["status"] = "stopping"
        job["message"] = "Arret demande. Le lot va se terminer apres la facture en cours."
        _set_job_unlocked(payload, job)
        _write_store_unlocked(payload)
        return _public_job(job)


def get_analysis_batch_job(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        if _reconcile_orphan_running_jobs_unlocked(payload):
            _write_store_unlocked(payload)
        job = _get_job_unlocked(payload, job_id)
        if not job:
            raise KeyError(job_id)
        response = _public_job(job)
        response["results"] = _collect_job_results_unlocked(
            payload,
            job_id,
            limit=max(20, int(job.get("limit") or 50)),
        )
        response["result_count"] = len(response["results"])
        return response


def _get_analyzed_invoice_ids_unlocked(payload: dict[str, Any]) -> set[str]:
    """Return the set of invoice_ids already saved definitively."""
    ids: set[str] = set()
    for result in payload.get("results", {}).values():
        if not isinstance(result, dict):
            continue
        if not bool(result.get("persisted") or False):
            continue
        invoice_id = str(result.get("invoice_id") or "").strip()
        if invoice_id:
            ids.add(invoice_id)
    return ids


def _get_selection_state_unlocked(payload: dict[str, Any], database: str) -> dict[str, Any]:
    state = payload.get("selection_state")
    if not isinstance(state, dict):
        state = {}
    if str(state.get("database") or "").strip() != database:
        state = {
            "database": database,
            "next_startkey": "",
        }
    state.setdefault("database", database)
    state.setdefault("next_startkey", "")
    payload["selection_state"] = state
    return state



def save_analysis_batch_job(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        job = _get_job_unlocked(payload, job_id)
        if not job:
            raise KeyError(job_id)
        status = str(job.get("status") or "").strip()
        if status != "stopped":
            return _public_job(job)
        saved_now, failed_now = _save_job_results_unlocked(payload, job_id)
        job["saved_count"] = int(job.get("saved_count") or 0) + saved_now + failed_now
        job["pending_save_count"] = len(_get_unsaved_job_results_unlocked(payload, job_id))
        job["last_saved_at"] = _now_iso()
        job["message"] = (
            f"Analyse partielle enregistr?e: {saved_now + failed_now} facture(s) sauvegard?e(s). "
            "Vous pouvez continuer l'analyse sur les factures restantes."
        )
        _set_job_unlocked(payload, job)
        _write_store_unlocked(payload)
        return _public_job(job)


def resume_analysis_batch_job(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        payload = _read_store_unlocked()
        if _reconcile_orphan_running_jobs_unlocked(payload):
            _write_store_unlocked(payload)
        running_job = _find_running_job_unlocked(payload)
        if running_job and str(running_job.get("job_id") or "") != job_id:
            response = _public_job(running_job)
            response["status"] = "already_running"
            response["message"] = "Un autre lot d'analyse est deja en cours"
            return response
        job = _get_job_unlocked(payload, job_id)
        if not job:
            raise KeyError(job_id)
        status = str(job.get("status") or "").strip()
        if status != "stopped":
            return _public_job(job)
        if int(job.get("processed") or 0) >= int(job.get("sampled_count") or 0):
            job["status"] = "completed"
            job["message"] = "Le lot est deja termine."
            _set_job_unlocked(payload, job)
            _write_store_unlocked(payload)
            return _public_job(job)
        job["status"] = "running"
        job["stop_requested"] = False
        job["finished_at"] = ""
        job["message"] = "Reprise du traitement des factures restantes..."
        _set_job_unlocked(payload, job)
        _write_store_unlocked(payload)

    thread = threading.Thread(
        target=_run_analysis_batch_job,
        args=(job_id,),
        name=f"analysis-batch-{job_id}",
        daemon=True,
    )
    ACTIVE_THREADS[job_id] = thread
    thread.start()
    print(f"[analysis-batch] job resumed job_id={job_id}")
    return _public_job(job)


def clear_analysis_batch_results() -> dict[str, Any]:
    """Remove all stored batch results from disk (keeps job history intact)."""
    with STORE_LOCK:
        payload = _read_store_unlocked()
        cleared_count = len(payload.get("results", {}))
        payload["results"] = {}
        payload["results_order"] = []
        _write_store_unlocked(payload)
    return {
        "cleared": cleared_count,
        "message": f"{cleared_count} r?sultat(s) supprim?(s) de la liste locale.",
    }


def get_analysis_batch_results(limit: int = 500, job_id: str | None = None) -> dict[str, Any]:
    requested_limit = max(1, min(int(limit or 500), 500))
    requested_job_id = str(job_id or "").strip()

    with STORE_LOCK:
        payload = _read_store_unlocked()
        reconciled_count = _reconcile_persisted_batch_results_unlocked(payload)
        if reconciled_count:
            _write_store_unlocked(payload)
        items: list[dict[str, Any]] = []
        seen_invoice_ids: set[str] = set()
        for result_id in payload.get("results_order", []):
            result = payload.get("results", {}).get(result_id)
            if not isinstance(result, dict):
                continue
            if requested_job_id and str(result.get("job_id") or "") != requested_job_id:
                continue
            if not bool(result.get("persisted") or False):
                continue
            invoice_id = str(result.get("invoice_id") or "").strip()
            if not requested_job_id and invoice_id:
                if invoice_id in seen_invoice_ids:
                    continue
                seen_invoice_ids.add(invoice_id)
            items.append(_public_result(result))
            if len(items) >= requested_limit:
                break

    return {
        "database": str(payload.get("active_database") or COUCHDB_DATABASE),
        "job_id": requested_job_id or None,
        "count": len(items),
        "items": items,
    }


def _analyze_batch_item(job_id: str, database: str, item: dict[str, Any], existing_invoice_ids: set[str] | None = None) -> dict[str, Any]:
    invoice_id = str((item or {}).get("invoice_id") or "").strip()
    invoice_label = " - ".join(
        [
            part
            for part in [
                str((item or {}).get("supplier") or "").strip(),
                str((item or {}).get("invoice_number") or "").strip(),
                invoice_id,
            ]
            if part
        ]
    ) or invoice_id

    if not invoice_id:
        return {
            "ok": False,
            "result": None,
            "invoice_id": "",
            "invoice_label": "Facture sans identifiant",
            "warning": "Facture sans identifiant ignoree.",
        }

    item_started = time.perf_counter()
    try:
        response = analyze_invoice_by_id(invoice_id)
        duration_ms = int((time.perf_counter() - item_started) * 1000)
        result = _build_result_from_response(
            job_id=job_id,
            database=database,
            invoice_id=invoice_id,
            invoice_label=invoice_label,
            response=response,
            duration_ms=duration_ms,
            existing_invoice_ids=existing_invoice_ids,
        )
        return {
            "ok": True,
            "result": result,
            "invoice_id": invoice_id,
            "invoice_label": invoice_label,
            "warning": "",
        }
    except Exception as exc:  # pragma: no cover - operational safety
        duration_ms = int((time.perf_counter() - item_started) * 1000)
        result = _build_failed_result(
            job_id=job_id,
            database=database,
            invoice_id=invoice_id,
            invoice_label=invoice_label,
            duration_ms=duration_ms,
            error_message=str(exc) or "Erreur pendant l'analyse de la facture.",
        )
        return {
            "ok": False,
            "result": result,
            "invoice_id": invoice_id,
            "invoice_label": invoice_label,
            "warning": f"{invoice_id}: {str(exc) or 'erreur inconnue'}",
        }

def _run_analysis_batch_job(job_id: str) -> None:
    started = time.perf_counter()

    with STORE_LOCK:
        payload = _read_store_unlocked()
        job = _get_job_unlocked(payload, job_id)
        if not job:
            return
        job_limit = int(job.get("limit") or 0)
        database = str(job.get("database") or COUCHDB_DATABASE).strip() or COUCHDB_DATABASE
        selection_state = _get_selection_state_unlocked(payload, database)
        selection_startkey = str(selection_state.get("next_startkey") or "").strip()
        already_analyzed_ids = _get_analyzed_invoice_ids_unlocked(payload)
        already_analyzed_count = len(already_analyzed_ids)
        sampled_items = list(job.get("sampled_items") or [])
        processed = int(job.get("processed") or 0)
        success = int(job.get("success") or 0)
        failed = int(job.get("failed") or 0)
        saved_count = int(job.get("saved_count") or 0)
        _write_store_unlocked(payload)

    candidates_found = int(job.get("candidates_found") or 0)
    selected_count = int(job.get("selected_count") or len(sampled_items))
    next_startkey = selection_startkey
    selection_strategy = str(job.get("selection_strategy") or "unprocessed_first")

    if not sampled_items:
        try:
            sample_response, selection_meta = fetch_unprocessed_invoices(
                job_limit,
                exclude_invoice_ids=already_analyzed_ids,
                startkey=selection_startkey,
            )
            raw_items = list(getattr(sample_response, "items", []) or [])
            sampled_items = [_serialize_sampled_item(item) for item in raw_items]
            candidates_found = int(selection_meta.get("candidates_found") or 0)
            selected_count = int(selection_meta.get("selected_count") or len(sampled_items))
            next_startkey = str(selection_meta.get("next_startkey") or "").strip()
            selection_strategy = str(selection_meta.get("selection_strategy") or "unprocessed_first")
        except Exception as exc:
            _update_job(
                job_id,
                status="failed",
                finished_at=_now_iso(),
                duration_ms=int((time.perf_counter() - started) * 1000),
                message=str(exc) or "Impossible de charger un lot de factures.",
                current_invoice_id="",
                current_invoice_label="",
                selection_strategy="unprocessed_first",
                already_analyzed_count=already_analyzed_count,
            )
            print(f"[analysis-batch] job failed during sampling job_id={job_id} error={exc}")
            ACTIVE_THREADS.pop(job_id, None)
            return

        with STORE_LOCK:
            payload = _read_store_unlocked()
            state = _get_selection_state_unlocked(payload, database)
            state["next_startkey"] = next_startkey
            payload["selection_state"] = state
            job = _get_job_unlocked(payload, job_id)
            if job is not None:
                job["sampled_items"] = sampled_items
                job["candidates_found"] = candidates_found
                job["selected_count"] = selected_count
                job["selection_strategy"] = selection_strategy
                _set_job_unlocked(payload, job)
            _write_store_unlocked(payload)

        print(
            f"[motor-batch] already_analyzed_count={already_analyzed_count} "
            f"candidates_found={candidates_found} selected_for_batch={selected_count} "
            f"selection_strategy={selection_strategy}"
        )

    if not sampled_items:
        _update_job(
            job_id,
            status="failed",
            finished_at=_now_iso(),
            duration_ms=int((time.perf_counter() - started) * 1000),
            message="Aucune nouvelle facture ? analyser pour le moment.",
            current_invoice_id="",
            current_invoice_label="",
            sampled_count=0,
            selection_strategy=selection_strategy,
            already_analyzed_count=already_analyzed_count,
            candidates_found=candidates_found,
            selected_count=0,
        )
        ACTIVE_THREADS.pop(job_id, None)
        return

    sampled_count = len(sampled_items)
    _update_job(
        job_id,
        status="running",
        sampled_count=sampled_count,
        message=f"Lot charge: {sampled_count} facture(s) nouvelle(s) a analyser",
        selection_strategy=selection_strategy,
        already_analyzed_count=already_analyzed_count,
        candidates_found=candidates_found,
        selected_count=selected_count,
        pending_save_count=max(processed - saved_count, 0),
    )

    warnings: list[str] = list(job.get("warnings") or []) if isinstance(job, dict) else []
    interrupted = False

    remaining_items = sampled_items[processed:]
    for chunk_start in range(0, len(remaining_items), BATCH_PARALLEL_WORKERS):
        with STORE_LOCK:
            payload = _read_store_unlocked()
            live_job = _get_job_unlocked(payload, job_id)
            if not live_job:
                interrupted = True
                break
            if bool(live_job.get("stop_requested") or False):
                interrupted = True
                break
            saved_count = int(live_job.get("saved_count") or 0)

        chunk = remaining_items[chunk_start : chunk_start + BATCH_PARALLEL_WORKERS]
        valid_chunk = [item for item in chunk if str((item or {}).get("invoice_id") or "").strip()]
        invalid_count = len(chunk) - len(valid_chunk)
        if invalid_count:
            failed += invalid_count
            processed += invalid_count

        if not valid_chunk:
            continue

        chunk_labels = [
            " - ".join(
                [
                    part
                    for part in [
                        str((item or {}).get("supplier") or "").strip(),
                        str((item or {}).get("invoice_number") or "").strip(),
                        str((item or {}).get("invoice_id") or "").strip(),
                    ]
                    if part
                ]
            )
            for item in valid_chunk
        ]
        _update_job(
            job_id,
            status="running",
            current_invoice_id=str((valid_chunk[0] or {}).get("invoice_id") or "").strip(),
            current_invoice_label=chunk_labels[0] if chunk_labels else "",
            processed=processed,
            success=success,
            failed=failed,
            message=f"Analyse {processed + 1}-{min(processed + len(valid_chunk), sampled_count)}/{sampled_count}: paquet de {len(valid_chunk)} facture(s)",
            pending_save_count=max(processed - saved_count, 0),
        )

        print(
            f"[analysis-batch] parallel chunk job_id={job_id} "
            f"size={len(valid_chunk)} workers={min(BATCH_PARALLEL_WORKERS, len(valid_chunk))} "
            f"progress={processed}/{sampled_count}"
        )
        with ThreadPoolExecutor(max_workers=min(BATCH_PARALLEL_WORKERS, len(valid_chunk))) as executor:
            futures = [executor.submit(_analyze_batch_item, job_id, database, item, already_analyzed_ids) for item in valid_chunk]
            for future in as_completed(futures):
                try:
                    outcome = future.result()
                except Exception as exc:  # pragma: no cover - defensive safety
                    outcome = {
                        "ok": False,
                        "result": _build_failed_result(
                            job_id=job_id,
                            database=database,
                            invoice_id="",
                            invoice_label="Facture inconnue",
                            duration_ms=0,
                            error_message=str(exc) or "Erreur pendant l'analyse de la facture.",
                        ),
                        "invoice_id": "",
                        "invoice_label": "Facture inconnue",
                        "warning": str(exc) or "erreur inconnue",
                    }

                result = outcome.get("result")
                invoice_id = str(outcome.get("invoice_id") or "").strip()
                invoice_label = str(outcome.get("invoice_label") or invoice_id or "Facture inconnue")
                if bool(outcome.get("ok")):
                    success += 1
                else:
                    failed += 1
                    warning = str(outcome.get("warning") or "").strip()
                    if warning:
                        warnings.append(warning)

                processed += 1
                if result is not None:
                    with STORE_LOCK:
                        payload = _read_store_unlocked()
                        _set_result_unlocked(payload, result)
                        live_job = _get_job_unlocked(payload, job_id)
                        if live_job is not None:
                            saved_count = int(live_job.get("saved_count") or 0)
                            live_job["pending_save_count"] = max(processed - saved_count, 0)
                            _set_job_unlocked(payload, live_job)
                        _write_store_unlocked(payload)

                _update_job(
                    job_id,
                    status="running",
                    processed=processed,
                    success=success,
                    failed=failed,
                    current_invoice_id=invoice_id,
                    current_invoice_label=invoice_label,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    message=f"{processed}/{sampled_count} facture(s) traitee(s)",
                    warnings=list(warnings),
                    pending_save_count=max(processed - saved_count, 0),
                )

        with STORE_LOCK:
            payload = _read_store_unlocked()
            live_job = _get_job_unlocked(payload, job_id)
            if live_job and bool(live_job.get("stop_requested") or False):
                interrupted = True
                break
    duration_ms = int((time.perf_counter() - started) * 1000)
    if interrupted:
        with STORE_LOCK:
            payload = _read_store_unlocked()
            live_job = _get_job_unlocked(payload, job_id)
            pending_save_count = len(_get_unsaved_job_results_unlocked(payload, job_id))
            if live_job is not None:
                live_job["pending_save_count"] = pending_save_count
                _set_job_unlocked(payload, live_job)
            _write_store_unlocked(payload)
        _update_job(
            job_id,
            status="stopped",
            finished_at=_now_iso(),
            processed=processed,
            success=success,
            failed=failed,
            current_invoice_id="",
            current_invoice_label="",
            duration_ms=duration_ms,
            message="Lot interrompu. Enregistrez l'analyse courante ou continuez avec les factures restantes.",
            warnings=list(warnings),
            stop_requested=False,
            pending_save_count=pending_save_count,
        )
        print(
            "[analysis-batch] job stopped "
            f"job_id={job_id} database={database} requested_limit={job_limit} sampled={sampled_count} "
            f"processed={processed} success={success} failed={failed} duration_ms={duration_ms} "
            f"selection_strategy={selection_strategy}"
        )
        ACTIVE_THREADS.pop(job_id, None)
        return

    with STORE_LOCK:
        payload = _read_store_unlocked()
        saved_now, failed_now = _save_job_results_unlocked(payload, job_id)
        live_job = _get_job_unlocked(payload, job_id)
        final_saved = int((live_job or {}).get("saved_count") or 0) + saved_now + failed_now
        if live_job is not None:
            live_job["saved_count"] = final_saved
            live_job["pending_save_count"] = 0
            live_job["last_saved_at"] = _now_iso()
            _set_job_unlocked(payload, live_job)
        _write_store_unlocked(payload)

    _update_job(
        job_id,
        status="completed",
        finished_at=_now_iso(),
        processed=processed,
        success=success,
        failed=failed,
        current_invoice_id="",
        current_invoice_label="",
        duration_ms=duration_ms,
        message=f"Lot termine: {processed} facture(s), {success} succes, {failed} echec(s).",
        warnings=list(warnings),
        stop_requested=False,
        saved_count=final_saved,
        pending_save_count=0,
        last_saved_at=_now_iso(),
    )
    print(
        "[analysis-batch] job done "
        f"job_id={job_id} database={database} requested_limit={job_limit} sampled={sampled_count} "
        f"processed={processed} success={success} failed={failed} duration_ms={duration_ms} "
        f"selection_strategy={selection_strategy}"
    )
    ACTIVE_THREADS.pop(job_id, None)


def start_analysis_batch_job(limit: int = 50) -> dict[str, Any]:
    batch_limit = max(1, min(int(limit or 50), 100))
    session = http_session()
    try:
        database = _resolve_invoice_db_name(session)
    except requests.RequestException as exc:  # pragma: no cover
        raise RuntimeError("CouchDB indisponible ou mal configur?e.") from exc

    with STORE_LOCK:
        payload = _read_store_unlocked()
        if _reconcile_orphan_running_jobs_unlocked(payload):
            _write_store_unlocked(payload)
        running_job = _find_running_job_unlocked(payload)
        if running_job:
            response = _public_job(running_job)
            response["status"] = "already_running"
            response["message"] = "Un lot d'analyse est deja en cours"
            print(
                "[analysis-batch] job start refused "
                f"requested_limit={batch_limit} running_job_id={response['job_id']}"
            )
            return response

        job_id = f"analysis-batch-{uuid.uuid4().hex[:12]}"
        job = _default_job(job_id, database, batch_limit)
        job["status"] = "running"
        job["started_at"] = _now_iso()
        job["message"] = "Chargement du lot d'analyse"
        _set_job_unlocked(payload, job)
        payload["active_database"] = database
        _write_store_unlocked(payload)

    thread = threading.Thread(
        target=_run_analysis_batch_job,
        args=(job_id,),
        name=f"analysis-batch-{job_id}",
        daemon=True,
    )
    ACTIVE_THREADS[job_id] = thread
    thread.start()

    print(f"[analysis-batch] job created job_id={job_id} database={database} limit={batch_limit}")
    return _public_job(job)







