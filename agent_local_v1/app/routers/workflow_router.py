from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..ai_memory_service import list_memory_items, rebuild_memory_from_validations
from ..history_service import add_history_event, list_history_events, clear_all_history_events


router = APIRouter(tags=["workflow-state"])


def _is_history_event_visible(event: dict[str, Any]) -> bool:
    workflow_status = str(
        event.get("workflow_status")
        or event.get("invoice_status")
        or event.get("status")
        or ""
    ).strip().upper()
    if workflow_status == "A_CONTROLER":
        return False
    return str(event.get("event_type") or "").strip() != "sent_to_human_validation"


@router.get("/history/events")
def get_history_events(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
    invoice_id: str | None = Query(default=None),
) -> dict[str, Any]:
    events = list_history_events(
        limit=limit,
        event_type=event_type,
        invoice_id=invoice_id,
    )
    events = [event for event in events if _is_history_event_visible(event)]
    return {"events": events}


@router.post("/history/events")
def create_history_event(payload: dict[str, Any]) -> dict[str, Any]:
    event = add_history_event(payload)
    return {"ok": True, "event": event}


@router.delete("/history/events")
def clear_history_events() -> dict[str, Any]:
    count = clear_all_history_events()
    return {"ok": True, "cleared_count": count}


@router.get("/ai-memory/items")
def get_ai_memory_items(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    items = list_memory_items(limit=limit)
    summary = {
        "total_items": len(items),
        "candidate_items": sum(1 for item in items if str(item.get("status") or "") == "candidate"),
        "non_comptable_candidates": sum(
            1 for item in items if str(item.get("status") or "") == "non_comptable_candidate"
        ),
        "validated_accounts": len(
            {
                str(item.get("validated_account") or "").strip()
                for item in items
                if str(item.get("validated_account") or "").strip()
            }
        ),
        "corrected_accounts": len(
            {
                str(item.get("validated_account") or "").strip()
                for item in items
                if str(item.get("engine_account") or "").strip()
                and str(item.get("validated_account") or "").strip()
                and str(item.get("engine_account") or "").strip()
                != str(item.get("validated_account") or "").strip()
            }
        ),
        "last_updated_at": max(
            [str(item.get("last_seen_at") or "") for item in items],
            default="",
        ),
    }
    return {"items": items, "summary": summary}


@router.post("/ai-memory/rebuild-from-validations")
def rebuild_ai_memory() -> dict[str, Any]:
    try:
        return rebuild_memory_from_validations()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Impossible de reconstruire la memoire IA depuis les validations.",
        ) from exc

