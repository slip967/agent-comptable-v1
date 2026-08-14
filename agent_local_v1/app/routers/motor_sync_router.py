from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..motor_sync_service import (
    get_motor_sync_job,
    get_motor_sync_items,
    get_motor_sync_status,
    start_motor_sync_job,
)


router = APIRouter(prefix="/motor-sync", tags=["motor-sync"])


@router.get("/status")
def motor_sync_status() -> dict:
    print("[api/motor-sync/status] status requested")
    return get_motor_sync_status()


@router.get("/jobs/{job_id}")
def motor_sync_job(job_id: str) -> dict:
    print(f"[api/motor-sync/jobs] job requested job_id={job_id}")
    try:
        return get_motor_sync_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job de synchronisation introuvable.") from exc


@router.get("/items")
def motor_sync_items(
    limit: int = Query(default=50, ge=1, le=200),
    only_with_lines: bool = Query(default=False),
    pdf_status: str | None = Query(default=None),
) -> dict:
    print(
        "[api/motor-sync/items] items requested "
        f"limit={limit} only_with_lines={only_with_lines} pdf_status={pdf_status or ''}"
    )
    return get_motor_sync_items(
        limit=limit,
        only_with_lines=only_with_lines,
        pdf_status=pdf_status,
    )


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def motor_sync_run(limit: int = Query(default=50, ge=1, le=100)) -> dict:
    print(f"[api/motor-sync/run] run requested limit={limit}")
    try:
        payload = start_motor_sync_job(limit=limit)
        print(
            "[api/motor-sync/run] response "
            f"limit={limit} job_id={payload.get('job_id', '')} status={payload.get('status', '')}"
        )
        return payload
    except RuntimeError as exc:
        print(f"[api/motor-sync/run] runtime error limit={limit} detail={exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        print(f"[api/motor-sync/run] unexpected error limit={limit} detail={exc}")
        raise HTTPException(
            status_code=500,
            detail="La synchronisation du lot a échoué. Aucun impact sur l'analyse IA.",
        ) from exc
