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
            item["status"] = new_status
            item["human_validation_result"] = result
            items[index] = item
            _write_items_unlocked(items)
            return item

    raise KeyError("Ligne de validation introuvable.")
