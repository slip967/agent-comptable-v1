from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..ai_memory_service import upsert_memory_from_validation_item
from ..history_service import add_history_event, delete_validation_history_events
from ..human_validation_store import (
    add_validation_item,
    delete_validation_item,
    list_validation_items,
    save_validation_decision,
)


router = APIRouter(prefix="/human-validation", tags=["human-validation"])


_AUTO_ROUTED_STATUSES = {
    "VALIDE_AUTO",
    "VALIDE",
    "COMPTABILISEE",
}


def _workflow_status(item: dict[str, Any]) -> str:
    return str(
        item.get("workflow_status")
        or item.get("invoice_status")
        or item.get("status")
        or ""
    ).strip().upper()


def _belongs_in_human_queue(item: dict[str, Any]) -> bool:
    # Legacy items without a workflow status remain visible for review.
    return _workflow_status(item) not in _AUTO_ROUTED_STATUSES


def _event_payload_from_validation_item(
    item: dict[str, Any],
    *,
    event_type: str,
    source: str,
    message: str,
    human_account: str = "",
    comment: str = "",
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "source": source,
        "invoice_id": str(item.get("invoice_id") or "").strip(),
        "invoice_number": str(item.get("invoice_number") or "").strip(),
        "supplier": str(item.get("supplier") or "").strip(),
        "client": str(item.get("client") or "").strip(),
        "line_id": str(item.get("line_id") or "").strip(),
        "raw_text": str(item.get("raw_text") or "").strip(),
        "engine_account": str(item.get("recommended_account") or "").strip(),
        "human_account": str(human_account or "").strip(),
        "message": message,
        "comment": str(comment or "").strip(),
    }


@router.post("/items")
def create_human_validation_item(payload: dict[str, Any]) -> dict[str, Any]:
    item = add_validation_item(payload)
    add_history_event(
        _event_payload_from_validation_item(
            item,
            event_type="sent_to_human_validation",
            source="analyse_ia",
            message="Ligne envoyee en validation humaine.",
        )
    )
    return {
        "ok": True,
        "validation_id": item["validation_id"],
        "message": "Ligne ajoutee a la file de validation humaine.",
        "item": item,
    }


@router.get("/items")
def get_human_validation_items(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=2000),
) -> dict[str, Any]:
    stored_items = list_validation_items(limit=10000)
    expected_status = str(status or "").strip().lower()
    if expected_status == "validated":
        all_items = [
            item
            for item in stored_items
            if str(item.get("status") or "").strip().lower() == "validated"
            or _workflow_status(item) in _AUTO_ROUTED_STATUSES
        ]
    else:
        all_items = [item for item in stored_items if _belongs_in_human_queue(item)]
    if expected_status:
        all_items = [
            item
            for item in all_items
            if expected_status == "validated"
            or str(item.get("status") or "pending_validation").strip().lower() == expected_status
        ]
    items = all_items[:limit]
    counts = {
        "pending_validation": 0,
        "validated": 0,
        "corrected": 0,
        "non_comptable": 0,
        "rejected": 0,
        "enrichment_proposed": 0,
    }
    for item in all_items:
        item_status = str(item.get("status") or "pending_validation")
        counts[item_status] = counts.get(item_status, 0) + 1
    return {"items": items, "counts": counts}


@router.delete("/items/{validation_id}")
def remove_human_validation_item(validation_id: str) -> dict[str, Any]:
    try:
        item = delete_validation_item(validation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    deleted_history_events = delete_validation_history_events(
        str(item.get("invoice_id") or ""),
        str(item.get("line_id") or ""),
    )
    return {
        "ok": True,
        "validation_id": validation_id,
        "deleted_history_events": deleted_history_events,
    }


@router.post("/items/{validation_id}/decision")
def decide_human_validation_item(
    validation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        item = save_validation_decision(validation_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = item.get("human_validation_result") or {}
    action = str(result.get("action") or "").strip()
    comment = str(result.get("comment") or "").strip()
    human_account = ""
    event_type = ""
    message = ""

    if action == "validate":
        human_account = str(item.get("recommended_account") or "").strip()
        event_type = "human_validated"
        message = "Compte moteur valide par un humain."
    elif action == "correct_account":
        human_account = str(result.get("corrected_account") or "").strip()
        event_type = "human_corrected"
        message = "Compte corrige par validation humaine."
    elif action == "mark_non_comptable":
        event_type = "marked_non_comptable"
        message = "Ligne marquee comme non comptable."
    elif action == "reject":
        event_type = "rejected"
        message = "Ligne rejetee apres revue humaine."
    elif action == "propose_enrichment":
        human_account = str(
            result.get("corrected_account") or item.get("recommended_account") or ""
        ).strip()
        event_type = "enrichment_proposed"
        message = "Proposition d'enrichissement preparee pour revue humaine."

    if event_type:
        add_history_event(
            _event_payload_from_validation_item(
                item,
                event_type=event_type,
                source="validation_humaine",
                message=message,
                human_account=human_account,
                comment=comment,
            )
        )

    if action in {"validate", "correct_account", "mark_non_comptable", "propose_enrichment"}:
        upsert_memory_from_validation_item(item)

    return {
        "ok": True,
        "validation_id": validation_id,
        "status": item["status"],
        "human_validation_result": item.get("human_validation_result"),
        "item": item,
    }
