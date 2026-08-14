from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..invoice_engine_service import fetch_analysis_control_queue
from ..schemas import ControlQueueResponse


router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/control-queue", response_model=ControlQueueResponse)
def get_analysis_control_queue(
    status: str = Query(default="all"),
    limit: int = Query(default=12, ge=1, le=50),
    supplier: str | None = Query(default=None),
    client: str | None = Query(default=None),
    ape: str | None = Query(default=None),
) -> ControlQueueResponse:
    try:
        return fetch_analysis_control_queue(
            status=status,
            limit=limit,
            supplier=supplier,
            client=client,
            ape=ape,
        )
    except Exception as exc:  # pragma: no cover - defensive API surface
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de charger les factures depuis CouchDB. {exc}",
        ) from exc
