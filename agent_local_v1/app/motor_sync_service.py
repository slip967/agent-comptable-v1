from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

from .config import COUCHDB_DATABASE
from .database import COUCHDB_URL, http_session
from .invoice_engine_service import (  # noqa: PLC2701
    _build_control_queue_item,
    _compute_queue_pdf_status,
    _is_control_queue_invoice,
    _normalize_control_queue_doc,
    _resolve_invoice_db_name,
)


STATUS_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "motor_sync_status.json"
JOBS_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "motor_sync_jobs.json"
ITEMS_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "motor_sync_items.json"
STORE_LOCK = threading.Lock()
ACTIVE_THREADS: dict[str, threading.Thread] = {}
RUNNING_JOB_STATUSES = {"queued", "running"}
FINAL_JOB_STATUSES = {"completed", "failed"}
START_KEY = "fr_bd_000000000"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_db_state(database: str) -> dict[str, Any]:
    return {
        "database": database,
        "last_sync_at": "",
        "total_batches": 0,
        "total_processed": 0,
        "total_with_lines": 0,
        "total_without_lines": 0,
        "total_with_pdf": 0,
        "total_errors": 0,
        "last_duration_ms": 0,
        "has_more": True,
        "next_startkey": START_KEY,
    }


def _default_jobs_store() -> dict[str, Any]:
    return {"jobs": {}, "order": []}


def _default_items_store() -> dict[str, Any]:
    return {"active_database": COUCHDB_DATABASE, "items": {}, "order": []}


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
        "with_lines": 0,
        "without_lines": 0,
        "with_pdf": 0,
        "errors": 0,
        "duration_ms": 0,
        "current_invoice_id": "",
        "message": "Synchronisation en attente",
        "warnings": [],
    }


def _ensure_stores() -> None:
    STATUS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATUS_STORE_PATH.exists():
        STATUS_STORE_PATH.write_text(
            json.dumps({"active_database": COUCHDB_DATABASE, "by_database": {}}, indent=2),
            encoding="utf-8",
        )
    if not JOBS_STORE_PATH.exists():
        JOBS_STORE_PATH.write_text(
            json.dumps(_default_jobs_store(), indent=2),
            encoding="utf-8",
        )
    if not ITEMS_STORE_PATH.exists():
        ITEMS_STORE_PATH.write_text(
            json.dumps(_default_items_store(), indent=2),
            encoding="utf-8",
        )


def _read_status_store_unlocked() -> dict[str, Any]:
    _ensure_stores()
    try:
        payload = json.loads(STATUS_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {"active_database": COUCHDB_DATABASE, "by_database": {}}
    if not isinstance(payload, dict):
        payload = {"active_database": COUCHDB_DATABASE, "by_database": {}}
    payload.setdefault("active_database", COUCHDB_DATABASE)
    payload.setdefault("by_database", {})
    if not isinstance(payload["by_database"], dict):
        payload["by_database"] = {}
    return payload


def _write_status_store_unlocked(payload: dict[str, Any]) -> None:
    _ensure_stores()
    STATUS_STORE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_jobs_store_unlocked() -> dict[str, Any]:
    _ensure_stores()
    try:
        payload = json.loads(JOBS_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = _default_jobs_store()
    if not isinstance(payload, dict):
        payload = _default_jobs_store()
    payload.setdefault("jobs", {})
    payload.setdefault("order", [])
    if not isinstance(payload["jobs"], dict):
        payload["jobs"] = {}
    if not isinstance(payload["order"], list):
        payload["order"] = []
    return payload


def _write_jobs_store_unlocked(payload: dict[str, Any]) -> None:
    _ensure_stores()
    JOBS_STORE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_items_store_unlocked() -> dict[str, Any]:
    _ensure_stores()
    try:
        payload = json.loads(ITEMS_STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = _default_items_store()
    if not isinstance(payload, dict):
        payload = _default_items_store()
    payload.setdefault("active_database", COUCHDB_DATABASE)
    payload.setdefault("items", {})
    payload.setdefault("order", [])
    if not isinstance(payload["items"], dict):
        payload["items"] = {}
    if not isinstance(payload["order"], list):
        payload["order"] = []
    return payload


def _write_items_store_unlocked(payload: dict[str, Any]) -> None:
    _ensure_stores()
    ITEMS_STORE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _upsert_sync_item_unlocked(payload: dict[str, Any], item: dict[str, Any]) -> None:
    invoice_id = str(item.get("invoice_id") or "").strip()
    if not invoice_id:
        return
    existing = payload["items"].get(invoice_id)
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(item)
    payload["items"][invoice_id] = merged
    order = [current for current in payload.get("order", []) if current != invoice_id]
    order.insert(0, invoice_id)
    payload["order"] = order[:1000]
    database = str(item.get("database") or "").strip()
    if database:
        payload["active_database"] = database


def _get_db_state_unlocked(payload: dict[str, Any], database: str) -> dict[str, Any]:
    current = payload["by_database"].get(database)
    if not isinstance(current, dict):
        current = _default_db_state(database)
        payload["by_database"][database] = current
    merged = _default_db_state(database)
    merged.update(current)
    payload["by_database"][database] = merged
    payload["active_database"] = database
    return merged


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


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "database": str(state.get("database") or COUCHDB_DATABASE),
        "last_sync_at": str(state.get("last_sync_at") or ""),
        "total_batches": int(state.get("total_batches") or 0),
        "total_processed": int(state.get("total_processed") or 0),
        "total_with_lines": int(state.get("total_with_lines") or 0),
        "total_without_lines": int(state.get("total_without_lines") or 0),
        "total_with_pdf": int(state.get("total_with_pdf") or 0),
        "total_errors": int(state.get("total_errors") or 0),
        "last_duration_ms": int(state.get("last_duration_ms") or 0),
        "has_more": bool(state.get("has_more", True)),
    }


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
        "with_lines": int(job.get("with_lines") or 0),
        "without_lines": int(job.get("without_lines") or 0),
        "with_pdf": int(job.get("with_pdf") or 0),
        "errors": int(job.get("errors") or 0),
        "duration_ms": int(job.get("duration_ms") or 0),
        "current_invoice_id": str(job.get("current_invoice_id") or ""),
        "message": str(job.get("message") or ""),
        "warnings": list(job.get("warnings") or []),
    }


def get_motor_sync_status() -> dict[str, Any]:
    with STORE_LOCK:
        status_payload = _read_status_store_unlocked()
        jobs_payload = _read_jobs_store_unlocked()
        database = str(status_payload.get("active_database") or COUCHDB_DATABASE).strip() or COUCHDB_DATABASE
        state = _get_db_state_unlocked(status_payload, database)
        _write_status_store_unlocked(status_payload)
        current_job = _find_running_job_unlocked(jobs_payload)
        print(
            "[motor-sync] status loaded "
            f"database={database} total_processed={int(state.get('total_processed') or 0)} "
            f"has_more={bool(state.get('has_more', True))}"
        )
        response = _public_state(state)
        response["current_job"] = _public_job(current_job) if current_job else None
        return response


def get_motor_sync_job(job_id: str) -> dict[str, Any]:
    with STORE_LOCK:
        jobs_payload = _read_jobs_store_unlocked()
        job = _get_job_unlocked(jobs_payload, job_id)
        if not job:
            raise KeyError(job_id)
        return _public_job(job)


def get_motor_sync_items(
    limit: int = 50,
    *,
    only_with_lines: bool = False,
    pdf_status: str | None = None,
) -> dict[str, Any]:
    requested_limit = max(1, min(int(limit or 50), 200))
    requested_pdf_status = str(pdf_status or "").strip().lower()

    with STORE_LOCK:
        status_payload = _read_status_store_unlocked()
        items_payload = _read_items_store_unlocked()
        database = str(
            status_payload.get("active_database")
            or items_payload.get("active_database")
            or COUCHDB_DATABASE
        ).strip() or COUCHDB_DATABASE

        selected_items: list[dict[str, Any]] = []
        for invoice_id in items_payload.get("order", []):
            item = items_payload.get("items", {}).get(invoice_id)
            if not isinstance(item, dict):
                continue
            if str(item.get("database") or "").strip() != database:
                continue
            if only_with_lines and not bool(item.get("has_lines")):
                continue
            if requested_pdf_status and str(item.get("pdf_status") or "").strip().lower() != requested_pdf_status:
                continue
            selected_items.append(
                {
                    "invoice_id": str(item.get("invoice_id") or ""),
                    "database": str(item.get("database") or database),
                    "client": item.get("client"),
                    "supplier": item.get("supplier"),
                    "invoice_number": item.get("invoice_number"),
                    "date": item.get("date"),
                    "line_count": int(item.get("line_count") or 0),
                    "has_lines": bool(item.get("has_lines")),
                    "pdf_status": str(item.get("pdf_status") or "unknown"),
                    "pdf_message": str(item.get("pdf_message") or ""),
                    "synced_at": str(item.get("synced_at") or ""),
                }
            )
            if len(selected_items) >= requested_limit:
                break

    return {
        "database": database,
        "count": len(selected_items),
        "items": selected_items,
    }


def _update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    with STORE_LOCK:
        jobs_payload = _read_jobs_store_unlocked()
        job = _get_job_unlocked(jobs_payload, job_id)
        if not job:
            return None
        job.update(fields)
        _set_job_unlocked(jobs_payload, job)
        _write_jobs_store_unlocked(jobs_payload)
        return job


def _build_sync_item_summary(
    *,
    database: str,
    item: Any,
    synced_at: str,
) -> dict[str, Any]:
    return {
        "invoice_id": str(getattr(item, "id", "") or ""),
        "database": database,
        "client": getattr(item, "client", None),
        "supplier": getattr(item, "supplier", None),
        "invoice_number": getattr(item, "invoice_number", None),
        "date": getattr(item, "date", None),
        "line_count": int(getattr(item, "line_count", 0) or 0),
        "has_lines": bool(getattr(item, "exploitable_lines_count", 0) or getattr(item, "line_count", 0)),
        "pdf_status": str(getattr(item, "pdf_status", "unknown") or "unknown"),
        "pdf_message": str(getattr(item, "pdf_message", "") or ""),
        "synced_at": synced_at,
    }


def _store_sync_item(summary: dict[str, Any]) -> None:
    with STORE_LOCK:
        items_payload = _read_items_store_unlocked()
        _upsert_sync_item_unlocked(items_payload, summary)
        _write_items_store_unlocked(items_payload)


def _fetch_batch_rows(
    session: requests.Session,
    db_name: str,
    startkey: str,
    page_size: int,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/_all_docs",
        params={
            "include_docs": "true",
            "startkey": json.dumps(startkey),
            "limit": str(page_size),
        },
        timeout=90,
    )
    if response.status_code == 404:
        raise RuntimeError("CouchDB indisponible ou mal configurée.")
    response.raise_for_status()
    rows = response.json().get("rows") or []
    return rows if isinstance(rows, list) else []


def run_motor_sync_batch(
    limit: int = 50,
    *,
    db_name: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    batch_limit = max(1, min(int(limit or 50), 100))
    started = time.perf_counter()
    warnings: list[str] = []

    session = http_session()
    resolved_db_name = db_name
    if not resolved_db_name:
        try:
            resolved_db_name = _resolve_invoice_db_name(session)
        except requests.RequestException as exc:  # pragma: no cover
            raise RuntimeError("CouchDB indisponible ou mal configurée.") from exc

    print(f"[motor-sync] batch start database={resolved_db_name} limit={batch_limit}")

    with STORE_LOCK:
        status_payload = _read_status_store_unlocked()
        state = _get_db_state_unlocked(status_payload, resolved_db_name)

        if not bool(state.get("has_more", True)):
            duration_ms = int((time.perf_counter() - started) * 1000)
            state["last_duration_ms"] = duration_ms
            _write_status_store_unlocked(status_payload)
            result = _public_state(state)
            result.update(
                {
                    "batch_limit": batch_limit,
                    "processed": 0,
                    "with_lines": 0,
                    "without_lines": 0,
                    "with_pdf": 0,
                    "errors": 0,
                    "duration_ms": duration_ms,
                    "has_more": False,
                    "warnings": ["Synchronisation déjà terminée pour cette base."],
                }
            )
            if progress_callback:
                progress_callback(
                    {
                        "processed": 0,
                        "with_lines": 0,
                        "without_lines": 0,
                        "with_pdf": 0,
                        "errors": 0,
                        "current_invoice_id": "",
                        "message": "Synchronisation deja terminee pour cette base.",
                        "warnings": result["warnings"],
                        "duration_ms": duration_ms,
                    }
                )
            return result

        startkey = str(state.get("next_startkey") or START_KEY)

    processed = 0
    with_lines = 0
    without_lines = 0
    with_pdf = 0
    errors = 0
    has_more = True
    next_startkey = startkey
    scanned_rows = 0
    scanned_row_budget = max(batch_limit * 20, 600)
    page_size = max(50, min(batch_limit * 4, 250))

    if progress_callback:
        progress_callback(
            {
                "processed": 0,
                "with_lines": 0,
                "without_lines": 0,
                "with_pdf": 0,
                "errors": 0,
                "current_invoice_id": "",
                "message": f"Traitement 0/{batch_limit}",
                "warnings": [],
                "duration_ms": 0,
            }
        )

    while processed < batch_limit and scanned_rows < scanned_row_budget:
        rows = _fetch_batch_rows(session, resolved_db_name, next_startkey, page_size)
        if not rows:
            has_more = False
            next_startkey = ""
            break

        page_last_id = str(rows[-1].get("id") or "").strip()
        for row in rows:
            scanned_rows += 1
            row_id = str(row.get("id") or "").strip()
            if row_id:
                next_startkey = f"{row_id}\ufff0"

            doc = row.get("doc")
            if not isinstance(doc, dict) or not _is_control_queue_invoice(doc):
                if scanned_rows >= scanned_row_budget:
                    break
                continue

            try:
                normalized_doc = _normalize_control_queue_doc(doc)
                pdf_status, pdf_message, has_pdf_flag = _compute_queue_pdf_status(
                    session=session,
                    db_name=resolved_db_name,
                    invoice_doc=doc,
                )
                normalized_doc["has_pdf"] = has_pdf_flag
                normalized_doc["pdf_status"] = pdf_status
                normalized_doc["pdf_message"] = pdf_message
                item = _build_control_queue_item(normalized_doc)
                processed += 1
                if int(item.exploitable_lines_count or 0) > 0:
                    with_lines += 1
                else:
                    without_lines += 1
                if str(item.pdf_status or "").strip().lower() == "available":
                    with_pdf += 1
                _store_sync_item(
                    _build_sync_item_summary(
                        database=resolved_db_name,
                        item=item,
                        synced_at=_now_iso(),
                    )
                )
            except Exception:
                errors += 1

            if progress_callback:
                progress_callback(
                    {
                        "processed": processed,
                        "with_lines": with_lines,
                        "without_lines": without_lines,
                        "with_pdf": with_pdf,
                        "errors": errors,
                        "current_invoice_id": row_id,
                        "message": f"Traitement {processed}/{batch_limit}",
                        "warnings": list(warnings),
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                    }
                )

            if processed >= batch_limit:
                break
            if scanned_rows >= scanned_row_budget:
                break

        if processed >= batch_limit:
            break
        if scanned_rows >= scanned_row_budget:
            warnings.append(
                "Le lot a atteint sa limite de lecture progressive avant d'atteindre le volume demande."
            )
            break
        if len(rows) < page_size:
            has_more = False
            if page_last_id:
                next_startkey = ""
            break

    duration_ms = int((time.perf_counter() - started) * 1000)

    with STORE_LOCK:
        status_payload = _read_status_store_unlocked()
        state = _get_db_state_unlocked(status_payload, resolved_db_name)
        state["last_sync_at"] = _now_iso()
        state["total_batches"] = int(state.get("total_batches") or 0) + 1
        state["total_processed"] = int(state.get("total_processed") or 0) + processed
        state["total_with_lines"] = int(state.get("total_with_lines") or 0) + with_lines
        state["total_without_lines"] = int(state.get("total_without_lines") or 0) + without_lines
        state["total_with_pdf"] = int(state.get("total_with_pdf") or 0) + with_pdf
        state["total_errors"] = int(state.get("total_errors") or 0) + errors
        state["last_duration_ms"] = duration_ms
        state["has_more"] = has_more
        state["next_startkey"] = next_startkey
        status_payload["active_database"] = resolved_db_name
        status_payload["by_database"][resolved_db_name] = state
        _write_status_store_unlocked(status_payload)

    result = _public_state(state)
    result.update(
        {
            "batch_limit": batch_limit,
            "processed": processed,
            "with_lines": with_lines,
            "without_lines": without_lines,
            "with_pdf": with_pdf,
            "errors": errors,
            "duration_ms": duration_ms,
            "has_more": has_more,
            "warnings": warnings,
        }
    )
    print(
        "[motor-sync] batch done "
        f"database={resolved_db_name} limit={batch_limit} processed={processed} "
        f"with_lines={with_lines} without_lines={without_lines} with_pdf={with_pdf} "
        f"errors={errors} scanned_rows={scanned_rows} has_more={has_more} duration_ms={duration_ms}"
    )
    return result


def _run_motor_sync_job(job_id: str) -> None:
    with STORE_LOCK:
        jobs_payload = _read_jobs_store_unlocked()
        job = _get_job_unlocked(jobs_payload, job_id)
        if not job:
            return
        job_limit = int(job.get("limit") or 0)
        database = str(job.get("database") or COUCHDB_DATABASE).strip() or COUCHDB_DATABASE

    started = time.perf_counter()

    def progress_callback(progress: dict[str, Any]) -> None:
        _update_job(
            job_id,
            status="running",
            processed=int(progress.get("processed") or 0),
            with_lines=int(progress.get("with_lines") or 0),
            without_lines=int(progress.get("without_lines") or 0),
            with_pdf=int(progress.get("with_pdf") or 0),
            errors=int(progress.get("errors") or 0),
            current_invoice_id=str(progress.get("current_invoice_id") or ""),
            message=str(progress.get("message") or f"Traitement 0/{job_limit}"),
            warnings=list(progress.get("warnings") or []),
            duration_ms=int(progress.get("duration_ms") or 0),
        )

    try:
        result = run_motor_sync_batch(
            limit=job_limit,
            db_name=database,
            progress_callback=progress_callback,
        )
        _update_job(
            job_id,
            status="completed",
            finished_at=_now_iso(),
            processed=int(result.get("processed") or 0),
            with_lines=int(result.get("with_lines") or 0),
            without_lines=int(result.get("without_lines") or 0),
            with_pdf=int(result.get("with_pdf") or 0),
            errors=int(result.get("errors") or 0),
            duration_ms=int(result.get("duration_ms") or 0),
            current_invoice_id="",
            message=(
                f"Synchronisation terminee : {int(result.get('processed') or 0)}/{job_limit} "
                "factures traitees."
            ),
            warnings=list(result.get("warnings") or []),
        )
    except Exception as exc:  # pragma: no cover - operational safety
        _update_job(
            job_id,
            status="failed",
            finished_at=_now_iso(),
            duration_ms=int((time.perf_counter() - started) * 1000),
            message=str(exc) or "La synchronisation du lot a echoue.",
            current_invoice_id="",
        )
        print(f"[motor-sync] job failed job_id={job_id} error={exc}")
    finally:
        ACTIVE_THREADS.pop(job_id, None)


def start_motor_sync_job(limit: int = 50) -> dict[str, Any]:
    batch_limit = max(1, min(int(limit or 50), 100))
    session = http_session()
    try:
        database = _resolve_invoice_db_name(session)
    except requests.RequestException as exc:  # pragma: no cover
        raise RuntimeError("CouchDB indisponible ou mal configurée.") from exc

    with STORE_LOCK:
        jobs_payload = _read_jobs_store_unlocked()
        running_job = _find_running_job_unlocked(jobs_payload)
        if running_job:
            response = _public_job(running_job)
            response["status"] = "already_running"
            response["message"] = "Une synchronisation est deja en cours"
            print(
                "[motor-sync] job start refused "
                f"requested_limit={batch_limit} running_job_id={response['job_id']}"
            )
            return response

        job_id = f"motor-sync-{uuid.uuid4().hex[:12]}"
        job = _default_job(job_id, database, batch_limit)
        job["status"] = "running"
        job["started_at"] = _now_iso()
        job["message"] = "Synchronisation lancee en arriere-plan"
        _set_job_unlocked(jobs_payload, job)
        _write_jobs_store_unlocked(jobs_payload)

    thread = threading.Thread(
        target=_run_motor_sync_job,
        args=(job_id,),
        name=f"motor-sync-{job_id}",
        daemon=True,
    )
    ACTIVE_THREADS[job_id] = thread
    thread.start()

    print(
        "[motor-sync] job created "
        f"job_id={job_id} database={database} limit={batch_limit}"
    )
    return _public_job(job)
