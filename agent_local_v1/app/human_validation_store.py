from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "human_validation_queue.json"
_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text("[]", encoding="utf-8")


def _read_items_unlocked() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _write_items_unlocked(items: list[dict[str, Any]]) -> None:
    _ensure_store()
    STORE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_validation_item(payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        items = _read_items_unlocked()
        item = deepcopy(payload)
        validation_id = str(item.get("validation_id") or uuid.uuid4())
        item["validation_id"] = validation_id
        item["created_at"] = str(item.get("created_at") or _now_iso())
        item["source"] = str(item.get("source") or "analyse_ia")
        item["status"] = str(item.get("status") or "pending_validation")
        item.setdefault("human_validation_result", None)
        items.insert(0, item)
        _write_items_unlocked(items)
        return item


def upsert_validation_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace one workflow line using its invoice/line identity."""
    with _LOCK:
        items = _read_items_unlocked()
        incoming = deepcopy(payload)
        invoice_id = str(incoming.get("invoice_id") or "").strip()
        line_id = str(incoming.get("line_id") or "").strip()
        matched_index = next(
            (
                index
                for index, existing in enumerate(items)
                if invoice_id
                and line_id
                and str(existing.get("invoice_id") or "").strip() == invoice_id
                and str(existing.get("line_id") or "").strip() == line_id
            ),
            None,
        )

        if matched_index is None:
            return_item = incoming
            return_item["validation_id"] = str(return_item.get("validation_id") or uuid.uuid4())
            return_item["created_at"] = str(return_item.get("created_at") or _now_iso())
            return_item["source"] = str(return_item.get("source") or "analyse_ia")
            return_item["status"] = str(return_item.get("status") or "pending_validation")
            return_item.setdefault("human_validation_result", None)
            items.insert(0, return_item)
        else:
            existing = items[matched_index]
            return_item = {**existing, **incoming}
            return_item["validation_id"] = str(
                incoming.get("validation_id") or existing.get("validation_id") or uuid.uuid4()
            )
            return_item["created_at"] = str(existing.get("created_at") or incoming.get("created_at") or _now_iso())
            return_item["updated_at"] = _now_iso()
            items[matched_index] = return_item

        _write_items_unlocked(items)
        return return_item


def list_validation_items(
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with _LOCK:
        items = _read_items_unlocked()

    if status:
        items = [item for item in items if str(item.get("status") or "") == status]

    return items[:limit]


def delete_validation_item(validation_id: str) -> dict[str, Any]:
    expected_id = str(validation_id or "").strip()
    if not expected_id:
        raise KeyError("Ligne de validation introuvable.")
    with _LOCK:
        items = _read_items_unlocked()
        for index, item in enumerate(items):
            if str(item.get("validation_id") or "").strip() == expected_id:
                deleted_item = items.pop(index)
                _write_items_unlocked(items)
                return deleted_item
    raise KeyError("Ligne de validation introuvable.")


def delete_pending_validation_items_for_invoice(invoice_id: str) -> int:
    """Remove stale review lines after the invoice has been auto-validated."""
    expected_invoice_id = str(invoice_id or "").strip()
    if not expected_invoice_id:
        return 0
    terminal_statuses = {"validated", "corrected", "non_comptable", "rejected"}
    with _LOCK:
        items = _read_items_unlocked()
        kept_items = [
            item
            for item in items
            if str(item.get("invoice_id") or "").strip() != expected_invoice_id
            or str(item.get("status") or "pending_validation").strip().lower() in terminal_statuses
        ]
        removed_count = len(items) - len(kept_items)
        if removed_count:
            _write_items_unlocked(kept_items)
        return removed_count


def clear_all_validation_items() -> int:
    """Clear the local test-session queue without accessing CouchDB."""
    with _LOCK:
        items = _read_items_unlocked()
        count = len(items)
        _write_items_unlocked([])
        return count


def mark_invoice_exported_to_odoo(invoice_id: str, move_id: int) -> int:
    """Persist the Odoo move identifier on every stored line of an invoice."""
    expected_id = str(invoice_id or "").strip()
    if not expected_id:
        return 0
    updated = 0
    with _LOCK:
        items = _read_items_unlocked()
        for item in items:
            item_invoice_id = str(
                item.get("invoice_group_id") or item.get("invoice_id") or ""
            ).strip()
            if item_invoice_id != expected_id:
                continue
            item["odoo_move_id"] = int(move_id)
            item["odoo_exported_at"] = _now_iso()
            updated += 1
        if updated:
            _write_items_unlocked(items)
    return updated


def save_validation_decision(
    validation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip()
    status_map = {
        "validate": "validated",
        "correct_account": "corrected",
        "mark_non_comptable": "non_comptable",
        "reject": "rejected",
        "propose_enrichment": "enrichment_proposed",
    }
    new_status = status_map.get(action)
    if not new_status:
        raise ValueError("Action de validation inconnue.")

    with _LOCK:
        items = _read_items_unlocked()
        for index, item in enumerate(items):
            if str(item.get("validation_id") or "") != validation_id:
                continue

            result = {
                "original_account": item.get("recommended_account"),
                "corrected_account": payload.get("corrected_account"),
                "corrected_account_label": payload.get("corrected_account_label"),
                "action": action,
                "comment": payload.get("comment"),
                "validated_by": payload.get("validated_by") or "human_user",
                "validated_at": _now_iso(),
            }
            item.setdefault("raw_line_text", item.get("raw_text") or "")
            for field in ("label", "description", "cleaned_text"):
                if payload.get(field) is not None:
                    item[field] = str(payload.get(field) or "").strip()
            item["status"] = new_status
            item["human_validation_result"] = result
            if action == "validate":
                item["workflow_status"] = "COMPTABILISEE"
                item["accounting_status"] = "COMPTABILISEE"
                item["destination"] = "ecritures_validees"
                item["validated_entries_destination"] = "ecritures_validees"
                item["validated_entry_id"] = str(item.get("validated_entry_id") or validation_id)
                item["auto_validated"] = False
                item["human_intervention"] = True
            items[index] = item
            _write_items_unlocked(items)
            return item

    raise KeyError("Ligne de validation introuvable.")
