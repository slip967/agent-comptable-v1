from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "history_events.json"
_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text("[]", encoding="utf-8")


def _read_events_unlocked() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        payload = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = []
    return payload if isinstance(payload, list) else []


def _write_events_unlocked(events: list[dict[str, Any]]) -> None:
    _ensure_store()
    STORE_PATH.write_text(
        json.dumps(events, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_history_event(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        events = _read_events_unlocked()
        event = deepcopy(payload)
        event["event_id"] = str(event.get("event_id") or uuid.uuid4())
        event["created_at"] = str(event.get("created_at") or _now_iso())
        event["event_type"] = str(event.get("event_type") or "invoice_analyzed")
        event["source"] = str(event.get("source") or "analyse_ia")
        event["invoice_id"] = str(event.get("invoice_id") or "").strip()
        event["invoice_number"] = str(event.get("invoice_number") or "").strip()
        event["supplier"] = str(event.get("supplier") or "").strip()
        event["client"] = str(event.get("client") or "").strip()
        event["line_id"] = str(event.get("line_id") or "").strip()
        event["raw_text"] = str(event.get("raw_text") or "").strip()
        event["engine_account"] = str(event.get("engine_account") or "").strip()
        event["human_account"] = str(event.get("human_account") or "").strip()
        event["message"] = str(event.get("message") or "").strip()
        event["comment"] = str(event.get("comment") or "").strip()
        events.insert(0, event)
        _write_events_unlocked(events)
        return event


def list_history_events(
    *,
    limit: int = 50,
    event_type: str | None = None,
    invoice_id: str | None = None,
) -> list[dict[str, Any]]:
    with _LOCK:
        events = _read_events_unlocked()

    filtered = events
    if event_type:
        expected_type = str(event_type).strip()
        filtered = [
            event
            for event in filtered
            if str(event.get("event_type") or "").strip() == expected_type
        ]
    if invoice_id:
        expected_invoice_id = str(invoice_id).strip()
        filtered = [
            event
            for event in filtered
            if str(event.get("invoice_id") or "").strip() == expected_invoice_id
        ]

    return filtered[: max(int(limit or 50), 1)]


def delete_validation_history_events(invoice_id: str, line_id: str = "") -> int:
    expected_invoice_id = str(invoice_id or "").strip()
    expected_line_id = str(line_id or "").strip()
    validation_event_types = {
        "sent_to_human_validation", "human_validated", "human_corrected",
        "marked_non_comptable", "rejected", "enrichment_proposed",
    }
    if not expected_invoice_id:
        return 0
    with _LOCK:
        events = _read_events_unlocked()
        kept_events = []
        deleted_count = 0
        for event in events:
            same_invoice = str(event.get("invoice_id") or "").strip() == expected_invoice_id
            same_line = not expected_line_id or str(event.get("line_id") or "").strip() == expected_line_id
            is_validation_event = str(event.get("event_type") or "").strip() in validation_event_types
            if same_invoice and same_line and is_validation_event:
                deleted_count += 1
            else:
                kept_events.append(event)
        if deleted_count:
            _write_events_unlocked(kept_events)
        return deleted_count


def clear_all_history_events() -> int:
    with _LOCK:
        events = _read_events_unlocked()
        count = len(events)
        _write_events_unlocked([])
        return count

