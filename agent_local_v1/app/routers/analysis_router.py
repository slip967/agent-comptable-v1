from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from ..config import COUCHDB_DATABASE, ODOO_DB
from ..database import http_session
from ..human_validation_store import list_validation_items, mark_invoice_exported_to_odoo
from ..analysis_batch_service import (  # noqa: PLC2701
    clear_analysis_batch_results,
    get_analysis_batch_job,
    get_analysis_batch_results,
    resume_analysis_batch_job,
    reset_analysis_test_session,
    save_analysis_batch_job,
    start_analysis_batch_job,
    stop_analysis_batch_job,
    subscribe_analysis_batch,
    unsubscribe_analysis_batch,
    batch_event_snapshot,
)
from ..invoice_engine_service import (
    _compute_queue_pdf_status,  # noqa: PLC2701
    _build_control_queue_item,  # noqa: PLC2701
    _count_control_queue_items,  # noqa: PLC2701
    _pdf_status_priority,  # noqa: PLC2701
    _is_invoice_form_invoice,  # noqa: PLC2701
    _normalize_control_queue_doc,  # noqa: PLC2701
    debug_pdf_storage,
    debug_invoice_pdf,
    fetch_analysis_control_queue,
    resolve_invoice_pdf,
)
from ..schemas import AnalysisBatchJob, AnalysisBatchResultsResponse, ControlQueueResponse
from ..services.odoo_service import (
    OdooAuthenticationError,
    OdooConfigurationError,
    OdooExportError,
    export_invoice_to_odoo,
)

COUCHDB_URL = os.getenv("COUCHDB_URL", "https://app.quimanage.info").rstrip("/")
logger = logging.getLogger(__name__)

DB_CANDIDATES = tuple(
    dict.fromkeys(
        filter(
            None,
            [
                COUCHDB_DATABASE,
                os.getenv("COUCHDB_DATABASE", "").strip(),
                "keymanage_accouting",
            ],
        )
    )
)

# Known client dossiers — kept in the router to avoid touching the engine
KNOWN_CLIENTS: dict[str, str] = {
    "BOULANGERIE L'UNIVERS DU PAIN": "880517875",
    "BOUCHERIE DE L'ESPOIR": "821913290",
    "BOUCHERIE IFRI": "892833831",
    "AADHI NAVI (MADRAS KITCHEN)": "948467188",
    "COUSCOUS FACTORY": "930689930",
    "LES TISANES": "849602750",
    "AEF (ARTISAN ENERGIE FRANCE)": "914837463",
    "ASSAINIS": "878523547",
    "DEM BAT": "943297747",
    "IBB INTERMEDIARY BUSINESS BATIMENT": "981565930",
    "IRD BAT": "879788230",
    "IRPCH PLOMBERIE": "951421064",
    "MB CONSTRUCTION": "947858304",
    "MONDIAL BATIMENT": "889860938",
    "PRO MRI45 PRO MAINTENANCE RESEAU": "942879321",
    "SAFTA MENUISERIE": "938751021",
    "TRAVAUX NETTS SARL": "908108012",
    "BS INTERNATIONAL TRANSFERT": "993669621",
    "DAC EXPRESS": "922040506",
    "DELIVERY GREEN": "931479869",
    "HELP DELIVERY": "991148206",
    "MHB TRANSPORTS": "982921744",
    "MMA TRANSPORT": "952192821",
    "MS TRANSPORT": "890852403",
    "PRIM DEMENAGEMENT": "908282098",
    "PROSERVICES AMBULANCES": "891756504",
    "RAF TRANS": "979300076",
}


def _resolve_db(session) -> str:
    for name in DB_CANDIDATES:
        try:
            r = session.get(f"{COUCHDB_URL}/{quote(name, safe='')}", timeout=15)
            if r.status_code == 200:
                print(f"CouchDB database utilisée : {name}")
                return name
        except Exception:
            continue
    raise RuntimeError("CouchDB indisponible ou mal configurée.")


def _resolve_siren(client_name: str) -> str | None:
    if client_name in KNOWN_CLIENTS:
        return KNOWN_CLIENTS[client_name]
    upper = client_name.strip().upper()
    for k, v in KNOWN_CLIENTS.items():
        if k.upper() == upper:
            return v
    for k, v in KNOWN_CLIENTS.items():
        if upper in k.upper():
            return v
    return None


def _fetch_partition_invoices(
    siren: str,
    limit: int,
    *,
    session=None,
    db_name: str | None = None,
    request_timeout: int = 20,
) -> list[dict]:
    session = session or http_session()
    db = db_name or _resolve_db(session)
    partition = f"fr_bd_{siren}"
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_partition/{quote(partition, safe='')}/_all_docs"
    matches: list[dict] = []
    startkey = f"{partition}:"
    page_size = max(10, min(40, limit * 8))

    while len(matches) < limit:
        r = session.get(
            url,
            params={
                "include_docs": "true",
                "startkey": json.dumps(startkey),
                "limit": str(page_size),
            },
            timeout=request_timeout,
        )
        r.raise_for_status()
        rows = r.json().get("rows") or []
        if not rows:
            break
        for row in rows:
            doc = row.get("doc") or {}
            if isinstance(doc, dict) and _is_invoice_form_invoice(doc):
                matches.append(doc)
                if len(matches) >= limit:
                    break
        if len(rows) < page_size:
            break
        last_id = str(rows[-1].get("id") or "").strip()
        if not last_id:
            break
        startkey = last_id + "\ufff0"

    return matches


router = APIRouter(prefix="/analysis", tags=["analysis"])
odoo_router = APIRouter(prefix="/odoo", tags=["odoo"])


def _validate_invoice_id(invoice_id: str) -> None:
    if not invoice_id or len(invoice_id) > 256 or "/" in invoice_id or "\\" in invoice_id:
        raise HTTPException(status_code=400, detail="Identifiant de facture invalide.")


@router.get("/control-queue", response_model=ControlQueueResponse)
def get_analysis_control_queue(
    status: str = Query(default="all"),
    limit: int = Query(default=15, ge=1, le=15),
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
    except RuntimeError as exc:
        message = str(exc).strip() or "CouchDB indisponible ou mal configurée."
        if "CouchDB indisponible ou mal configurée." in message:
            raise HTTPException(
                status_code=503,
                detail="CouchDB indisponible ou mal configurée.",
            ) from exc
        raise HTTPException(status_code=503, detail=message) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=503,
            detail="CouchDB indisponible ou mal configurée.",
        ) from exc


@router.get("/dossier-queue", response_model=ControlQueueResponse)
def get_dossier_queue(
    siren: str | None = Query(default=None),
    client_name: str | None = Query(default=None),
    limit: int = Query(default=15, ge=1, le=15),
) -> ControlQueueResponse:
    """
    Load the invoice queue for a specific client dossier using CouchDB partition queries.
    Much faster than the generic control-queue scan for known clients.
    Pass either siren (9-digit SIREN) or client_name (exact or partial match against known clients).
    """
    resolved_siren = siren
    if not resolved_siren and client_name:
        resolved_siren = _resolve_siren(client_name.strip())
        if not resolved_siren:
            raise HTTPException(
                status_code=404,
                detail=f"Client « {client_name} » non trouvé dans les dossiers connus. "
                       f"Utilisez GET /api/analysis/known-clients pour voir la liste.",
            )
    if not resolved_siren:
        raise HTTPException(
            status_code=400,
            detail="Paramètre siren ou client_name requis.",
        )

    try:
        docs = _fetch_partition_invoices(resolved_siren, limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Erreur CouchDB lors du chargement du dossier.") from exc

    session = http_session()
    db_name = _resolve_db(session)
    items = []
    for doc in docs:
        try:
            normalized = _normalize_control_queue_doc(doc)
            pdf_status, pdf_message, has_pdf = _compute_queue_pdf_status(
                session=session,
                db_name=db_name,
                invoice_doc=doc,
            )
            normalized["has_pdf"] = has_pdf
            normalized["pdf_status"] = pdf_status
            normalized["pdf_message"] = pdf_message
            items.append(_apply_strict_pdf_status(_build_control_queue_item(normalized)))
        except Exception:
            continue

    counts = _count_control_queue_items(items)
    return ControlQueueResponse(
        items=items,
        counts=counts,
        count=len(items),
        database=db_name,
        pdf_available_count=sum(1 for item in items if item.pdf_status == "available"),
        pdf_missing_count=sum(1 for item in items if item.pdf_status != "available"),
    )


DEMO_DOSSIERS: list[tuple[str, str]] = [
    ("BOUCHERIE IFRI",               "892833831"),
    ("ASSAINIS",                     "878523547"),
    ("BOULANGERIE L'UNIVERS DU PAIN", "880517875"),
    ("PROSERVICES AMBULANCES",       "891756504"),
    ("PRIM DEMENAGEMENT",            "908282098"),
]


def _strict_pdf_status_for_item(item) -> tuple[str, str, bool]:
    item_id = str(getattr(item, "id", "") or "").strip()
    if not item_id:
        return "no_path", "Sans identifiant facture", False
    if str(getattr(item, "pdf_status", "") or "").strip().lower() == "available":
        return "available", "PDF disponible", True
    try:
        resolve_invoice_pdf(item_id)
        return "available", "PDF disponible", True
    except FileNotFoundError as exc:
        message = str(exc).strip().lower()
        if bool(getattr(item, "has_pdf", False)):
            if "inaccessible" in message or "chemin source" in message:
                return "inaccessible", "Acces reseau KO", True
            return "missing_file", "PDF absent", True
        return "no_path", "Sans PDF", False
    except RuntimeError:
        if bool(getattr(item, "has_pdf", False)):
            return "inaccessible", "Acces reseau KO", True
        return "unknown", "PDF inconnu", False
    except Exception:
        if bool(getattr(item, "has_pdf", False)):
            return "inaccessible", "Acces reseau KO", True
        return "unknown", "PDF inconnu", False


def _apply_strict_pdf_status(item):
    if str(getattr(item, "pdf_status", "") or "").strip().lower() == "available":
        return item
    pdf_status, pdf_message, has_pdf = _strict_pdf_status_for_item(item)
    item.pdf_status = pdf_status
    item.pdf_message = pdf_message
    item.has_pdf = has_pdf
    return item


def _demo_client_key(item) -> str:
    return (
        str(getattr(item, "client", "") or "").strip()
        or str(getattr(item, "supplier", "") or "").strip()
        or "INCONNU"
    )


def _select_demo_items(candidates, max_total: int = 15, max_per_client: int = 3):
    selected = []
    selected_ids: set[str] = set()
    per_client_counts: dict[str, int] = {}
    ordered = sorted(
        candidates,
        key=lambda item: (
            _pdf_status_priority(getattr(item, "pdf_status", "unknown")),
            -(int(getattr(item, "exploitable_lines_count", 0) or 0)),
            str(getattr(item, "client", "") or ""),
            str(getattr(item, "supplier", "") or ""),
        ),
    )
    for item in ordered:
        item_id = str(getattr(item, "id", "") or "").strip()
        if not item_id or item_id in selected_ids:
            continue
        if int(getattr(item, "line_count", 0) or 0) <= 0:
            continue
        if int(getattr(item, "exploitable_lines_count", 0) or 0) <= 0:
            continue
        client_key = _demo_client_key(item)
        if per_client_counts.get(client_key, 0) >= max_per_client:
            continue
        selected.append(item)
        selected_ids.add(item_id)
        per_client_counts[client_key] = per_client_counts.get(client_key, 0) + 1
        if len(selected) >= max_total:
            break
    return selected


@router.get("/demo-folder-sample", response_model=ControlQueueResponse)
def get_demo_folder_sample(
    per_folder: int = Query(default=2, ge=1, le=10),
) -> ControlQueueResponse:
    """
    Load a small mixed sample from the 5 demo dossiers using partition queries.
    Returns at most per_folder invoices per dossier (default 3), merged into one queue.
    """
    started = time.perf_counter()
    max_total = 15
    max_per_client = 3
    requested_per_folder = max(1, min(per_folder, max_per_client))
    folder_scan_limit = min(max(requested_per_folder * 4, 12), 20)
    warnings: list[str] = []
    clients_found: list[str] = []
    candidates = []
    tested_exploitable = 0
    tested_with_pdf_path = 0

    try:
        session = http_session()
        db_name = _resolve_db(session)
        print(f"CouchDB database utilisée : {db_name}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Erreur CouchDB lors du chargement de l'échantillon: {exc}") from exc

    try:
        storage_ready = bool(debug_pdf_storage().get("drive_z_visible"))
    except Exception:
        storage_ready = False

    def _load_demo_folder(name: str, siren: str):
        folder_session = http_session()
        folder_items = []
        folder_tested = 0
        folder_with_pdf_path = 0
        try:
            docs = _fetch_partition_invoices(
                siren,
                folder_scan_limit,
                session=folder_session,
                db_name=db_name,
                request_timeout=4,
            )
        except Exception as exc:
            return name, [], 0, 0, f"{name}: indisponible ({exc})"

        for doc in docs:
            try:
                normalized = _normalize_control_queue_doc(doc)
                pdf_status, pdf_message, has_pdf = _compute_queue_pdf_status(
                    session=folder_session,
                    db_name=db_name,
                    invoice_doc=doc,
                )
                normalized["has_pdf"] = has_pdf
                normalized["pdf_status"] = pdf_status
                normalized["pdf_message"] = pdf_message
                item = _build_control_queue_item(normalized)
                if int(getattr(item, "line_count", 0) or 0) <= 0:
                    continue
                if int(getattr(item, "exploitable_lines_count", 0) or 0) <= 0:
                    continue
                folder_tested += 1
                if has_pdf:
                    folder_with_pdf_path += 1
                folder_items.append(_apply_strict_pdf_status(item))
            except Exception:
                continue
        return name, folder_items, folder_tested, folder_with_pdf_path, None

    with ThreadPoolExecutor(max_workers=min(len(DEMO_DOSSIERS), 5)) as executor:
        futures = [
            executor.submit(_load_demo_folder, name, siren)
            for name, siren in DEMO_DOSSIERS
        ]
        for future in as_completed(futures):
            name, folder_items, folder_tested, folder_with_pdf_path, warning = future.result()
            if warning:
                warnings.append(warning)
                continue
            candidates.extend(folder_items)
            tested_exploitable += folder_tested
            tested_with_pdf_path += folder_with_pdf_path
            if folder_items and name not in clients_found:
                clients_found.append(name)

    selected_items = _select_demo_items(candidates, max_total=max_total, max_per_client=max_per_client)

    pdf_available_count = sum(1 for item in selected_items if item.pdf_status == "available")
    pdf_missing_count = sum(1 for item in selected_items if item.pdf_status != "available")
    if selected_items and pdf_available_count == 0:
        warnings.append(
            "Diagnostic PDF: "
            f"{tested_exploitable} factures exploitables testees, "
            f"{tested_with_pdf_path} avec chemin PDF, 0 PDF disponible."
        )
        if storage_ready:
            warnings.append(
                "Aucune facture avec PDF disponible dans cet echantillon. "
                "WireGuard est actif, mais les fichiers sources de ces factures ne sont pas accessibles sur le stockage."
            )
        else:
            warnings.append(
                "Aucune facture avec PDF disponible dans cet echantillon. "
                "Le backend FastAPI ne voit pas actuellement le stockage source Z:/e."
            )
    if not selected_items:
        warnings.append(
            "Diagnostic PDF: "
            f"{tested_exploitable} factures exploitables testees, "
            f"{tested_with_pdf_path} avec chemin PDF, 0 fichier present ou accessible."
        )
        warnings.append(f"Aucune facture avec document source disponible dans cet échantillon {db_name}.")

    counts = _count_control_queue_items(selected_items)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ControlQueueResponse(
        items=selected_items,
        counts=counts,
        count=len(selected_items),
        database=db_name,
        clients_found=clients_found,
        pdf_available_count=pdf_available_count,
        pdf_missing_count=pdf_missing_count,
        warnings=warnings,
        duration_ms=duration_ms,
    )


@router.post("/batch-run", response_model=AnalysisBatchJob, status_code=status.HTTP_202_ACCEPTED)
def run_analysis_batch(
    limit: int = Query(default=50, ge=1, le=100),
    sort_strategy: str = Query(default="DUE_DATE"),
) -> dict:
    print(f"[api/analysis/batch-run] run requested limit={limit} sort_strategy={sort_strategy}")
    try:
        payload = start_analysis_batch_job(limit=limit, sort_strategy=sort_strategy)
        print(
            "[api/analysis/batch-run] response "
            f"limit={limit} job_id={payload.get('job_id', '')} status={payload.get('status', '')}"
        )
        return payload
    except RuntimeError as exc:
        print(f"[api/analysis/batch-run] runtime error limit={limit} detail={exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        print(f"[api/analysis/batch-run] unexpected error limit={limit} detail={exc}")
        raise HTTPException(
            status_code=500,
            detail="Le lot d'analyse a echoue. L'analyse unitaire reste disponible.",
        ) from exc


@router.post("/batch-jobs/{job_id}/stop", response_model=AnalysisBatchJob)
def stop_analysis_batch_job_endpoint(job_id: str) -> dict:
    print(f"[api/analysis/batch-jobs] stop requested job_id={job_id}")
    try:
        return stop_analysis_batch_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job d'analyse introuvable.") from exc


@router.post("/batch-jobs/{job_id}/save", response_model=AnalysisBatchJob)
def save_analysis_batch_job_endpoint(job_id: str) -> dict:
    print(f"[api/analysis/batch-jobs] save requested job_id={job_id}")
    try:
        return save_analysis_batch_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job d'analyse introuvable.") from exc


@router.post("/batch-jobs/{job_id}/resume", response_model=AnalysisBatchJob)
def resume_analysis_batch_job_endpoint(job_id: str) -> dict:
    print(f"[api/analysis/batch-jobs] resume requested job_id={job_id}")
    try:
        return resume_analysis_batch_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job d'analyse introuvable.") from exc



def _encode_sse_event(event: dict) -> str:
    event_type = str(event.get("type") or "message")
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.get("/batch-jobs/{job_id}/stream")
def stream_analysis_batch_job(job_id: str):
    event_queue = subscribe_analysis_batch(job_id)

    def event_generator():
        try:
            try:
                snapshot = batch_event_snapshot(job_id)
            except KeyError as exc:
                yield _encode_sse_event(
                    {"type": "BATCH_ERROR", "message": "Job d'analyse introuvable."}
                )
                return

            yield _encode_sse_event(snapshot)
            while True:
                try:
                    event = event_queue.get(timeout=15)
                except Exception:
                    yield ": keep-alive\n\n"
                    continue
                yield _encode_sse_event(event)
                if str(event.get("type") or "") in {"BATCH_COMPLETED", "BATCH_FAILED"}:
                    return
        finally:
            unsubscribe_analysis_batch(job_id, event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/batch-jobs/{job_id}", response_model=AnalysisBatchJob)
def get_analysis_batch_job_endpoint(job_id: str) -> dict:
    print(f"[api/analysis/batch-jobs] job requested job_id={job_id}")
    try:
        return get_analysis_batch_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job d'analyse introuvable.") from exc


@router.get("/batch-results", response_model=AnalysisBatchResultsResponse)
def get_analysis_batch_results_endpoint(
    limit: int = Query(default=500, ge=1, le=500),
    job_id: str | None = Query(default=None),
) -> dict:
    print(f"[api/analysis/batch-results] results requested limit={limit} job_id={job_id or ''}")
    return get_analysis_batch_results(limit=limit, job_id=job_id)


@router.delete("/batch-results", status_code=200)
def delete_analysis_batch_results() -> dict:
    """Clear all persisted batch results from local storage (keeps job history)."""
    print("[api/analysis/batch-results] clear requested")
    return clear_analysis_batch_results()


@router.post("/reset-session", status_code=200)
def reset_analysis_session(confirm: bool = Query(False)) -> dict:
    """Reset batch, validation, validated-entry and history state locally.

    This endpoint delegates only to JSON/in-memory session stores and never
    opens a CouchDB session.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation explicite requise pour réinitialiser la session de test.",
        )
    print("[api/analysis/reset-session] local test-session reset requested")
    try:
        return reset_analysis_test_session()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/known-clients")
def get_known_clients() -> dict:
    """Return the list of known client dossiers with their SIRENs."""
    return {
        "clients": [
            {"name": name, "siren": siren}
            for name, siren in sorted(KNOWN_CLIENTS.items())
        ]
    }




_WORD_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".docm", ".rtf", ".odt"}
_WORD_CONVERSION_LOCK = threading.Lock()


def _prepare_inline_invoice_document(
    file_path: str,
    invoice_id: str,
    media_type: str,
    filename: str,
) -> tuple[str, str, str]:
    """Convert Word-compatible sources to a cached PDF suitable for an iframe."""
    source = Path(file_path)
    if source.suffix.lower() not in _WORD_DOCUMENT_EXTENSIONS:
        return str(source), media_type, filename

    try:
        source_stat = source.stat()
    except OSError as exc:
        raise RuntimeError("Le document source est inaccessible pour la conversion PDF.") from exc

    cache_key = hashlib.sha256(
        f"{source}|{source_stat.st_mtime_ns}|{source_stat.st_size}".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = Path(tempfile.gettempdir()) / "keymanage_invoice_pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"invoice_{cache_key}.pdf"

    with _WORD_CONVERSION_LOCK:
        if target.exists() and target.stat().st_size > 0:
            return str(target), "application/pdf", f"facture_{cache_key}.pdf"

        word = None
        document = None
        pythoncom = None
        try:
            import pythoncom as pythoncom_module
            import win32com.client

            pythoncom = pythoncom_module
            pythoncom.CoInitialize()
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            try:
                word.AutomationSecurity = 3
            except Exception:
                pass
            document = word.Documents.Open(
                str(source),
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Visible=False,
                OpenAndRepair=True,
            )
            document.ExportAsFixedFormat(
                OutputFileName=str(target),
                ExportFormat=17,
                OpenAfterExport=False,
                OptimizeFor=0,
                Range=0,
                Item=0,
                IncludeDocProps=True,
                KeepIRM=True,
                CreateBookmarks=0,
                DocStructureTags=True,
                BitmapMissingFonts=True,
                UseISO19005_1=False,
            )
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise RuntimeError(
                "Impossible de convertir le document Word en PDF pour l’aperçu intégré."
            ) from exc
        finally:
            if document is not None:
                try:
                    document.Close(False)
                except Exception:
                    pass
            if word is not None:
                try:
                    word.Quit(False)
                except Exception:
                    pass
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError("La conversion du document Word en PDF a échoué.")
    return str(target), "application/pdf", f"facture_{cache_key}.pdf"

@router.get("/invoice-pdf/{invoice_id}")
def get_invoice_pdf(invoice_id: str):
    """Serve the source document associated with an invoice stored in CouchDB."""
    _validate_invoice_id(invoice_id)
    try:
        kind, payload = resolve_invoice_pdf(invoice_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="Erreur interne lors de la récupération du PDF."
        ) from exc

    if kind == "disk":
        file_path = payload.get("path") if isinstance(payload, dict) else payload
        media_type = (
            payload.get("media_type")
            if isinstance(payload, dict)
            else "application/pdf"
        ) or "application/octet-stream"
        filename = (
            payload.get("filename")
            if isinstance(payload, dict)
            else f"facture_{invoice_id}.pdf"
        ) or f"facture_{invoice_id}"
        file_path, media_type, filename = _prepare_inline_invoice_document(
            str(file_path), invoice_id, str(media_type), str(filename)
        )
        response = FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )
        response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    if kind == "couch_attachment":
        session, att_url, att_name, media_type = payload
        couch_resp = session.get(att_url, stream=True, timeout=120)
        if couch_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Document source absent du serveur CouchDB.")
        couch_resp.raise_for_status()

        def _stream():
            for chunk in couch_resp.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk

        return StreamingResponse(
            _stream(),
            media_type=media_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'inline; filename="{att_name}"',
            },
        )

    raise HTTPException(status_code=500, detail="Erreur interne lors de la récupération du document source.")  # pragma: no cover



def _load_invoice_pdf_payload(invoice_id: str) -> tuple[bytes, str, str]:
    """Load the original source as PDF bytes with its filename and source location."""
    kind, payload = resolve_invoice_pdf(invoice_id)
    if kind == "disk":
        file_path = payload.get("path") if isinstance(payload, dict) else payload
        media_type = payload.get("media_type") if isinstance(payload, dict) else "application/pdf"
        filename = payload.get("filename") if isinstance(payload, dict) else Path(str(file_path)).name
        converted_path, _converted_type, converted_name = _prepare_inline_invoice_document(
            str(file_path), invoice_id, str(media_type or ""), str(filename or "")
        )
        pdf_bytes = Path(converted_path).read_bytes()
        pdf_filename = str(converted_name or Path(converted_path).name)
        pdf_source = str(file_path)
    elif kind == "couch_attachment":
        session, attachment_url, attachment_name, _media_type = payload
        attachment_response = session.get(attachment_url, timeout=120)
        attachment_response.raise_for_status()
        pdf_bytes = attachment_response.content
        pdf_filename = str(attachment_name or f"facture_{invoice_id}.pdf")
        pdf_source = str(attachment_url)
    else:
        raise RuntimeError("Format de document source non pris en charge.")

    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("Le document source n’a pas pu être converti en PDF.")
    return pdf_bytes, pdf_filename, pdf_source


def _load_invoice_pdf_bytes(invoice_id: str) -> bytes:
    """Load a source document as PDF bytes without exposing a downloadable Word file."""
    pdf_bytes, _filename, _source = _load_invoice_pdf_payload(invoice_id)
    return pdf_bytes


def _validated_invoice_for_odoo(invoice_id: str) -> dict:
    expected_id = str(invoice_id or "").strip()
    matching_lines = []
    for item in list_validation_items(limit=10000):
        item_id = str(item.get("invoice_group_id") or item.get("invoice_id") or "").strip()
        if item_id != expected_id:
            continue
        workflow_status = str(
            item.get("workflow_status") or item.get("accounting_status") or ""
        ).upper()
        item_status = str(item.get("status") or "").lower()
        if item_status == "validated" or workflow_status in {
            "COMPTABILISEE",
            "VALIDE_AUTO",
            "VALIDE",
        }:
            matching_lines.append(item)
    if not matching_lines:
        raise HTTPException(
            status_code=404,
            detail="Facture validée introuvable pour l'export Odoo.",
        )

    first = matching_lines[0]
    existing_move_id = None
    for line in matching_lines:
        exports = line.get("odoo_exports") if isinstance(line.get("odoo_exports"), list) else []
        matching_export = next(
            (
                export
                for export in exports
                if isinstance(export, dict)
                and str(export.get("database") or "").strip() == ODOO_DB
                and str(export.get("move_id") or "").isdigit()
            ),
            None,
        )
        if matching_export:
            existing_move_id = int(matching_export["move_id"])
            break
        line_database = str(line.get("odoo_database") or "").strip()
        legacy_matches = not line_database and ODOO_DB == "keymanage_db"
        if (line_database == ODOO_DB or legacy_matches) and str(
            line.get("odoo_move_id") or ""
        ).isdigit():
            existing_move_id = int(line["odoo_move_id"])
            break
    supplier_details = first.get("issuer") if isinstance(first.get("issuer"), dict) else {}
    return {
        **first,
        "invoice_id": expected_id,
        "supplier": first.get("supplier") or first.get("supplier_name") or supplier_details.get("name"),
        "vat_siret": (
            first.get("vat_siret")
            or first.get("supplier_siret")
            or first.get("supplier_vat")
            or first.get("siret")
            or supplier_details.get("siret")
            or supplier_details.get("vat_number")
        ),
        "lines": matching_lines,
        "odoo_move_id": existing_move_id,
    }


@odoo_router.post("/export/{invoice_id}")
def export_validated_invoice_to_odoo(invoice_id: str) -> dict:
    """Export one locally validated invoice as an Odoo vendor bill."""
    _validate_invoice_id(invoice_id)
    invoice_data = _validated_invoice_for_odoo(invoice_id)
    existing_move_id = invoice_data.get("odoo_move_id")
    if existing_move_id:
        return {
            "success": True,
            "invoice_id": invoice_id,
            "move_id": int(existing_move_id),
            "already_exported": True,
            "message": f"Facture déjà exportée vers Odoo #{existing_move_id}.",
        }

    try:
        pdf_bytes, pdf_filename, pdf_source = _load_invoice_pdf_payload(invoice_id)
        invoice_data["pdf_bytes"] = pdf_bytes
        invoice_data["pdf_filename"] = pdf_filename
        invoice_data["pdf_source"] = pdf_source
        logger.info(
            "Export Odoo : PDF source résolu pour la facture %s depuis %s.",
            invoice_id,
            pdf_source,
        )
    except Exception as exc:  # The Odoo bill must remain exportable without its PDF.
        invoice_data["pdf_error"] = str(exc)
        logger.warning(
            "Export Odoo : PDF inaccessible pour la facture %s : %s",
            invoice_id,
            exc,
        )

    try:
        result = export_invoice_to_odoo(invoice_data)
    except (OdooConfigurationError, OdooAuthenticationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OdooExportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    move_id = int(result["move_id"])
    mark_invoice_exported_to_odoo(invoice_id, move_id, ODOO_DB)
    attachment_created = bool(result.get("attachment_id"))
    message = f"Facture exportée vers Odoo #{move_id}."
    if not attachment_created:
        message = (
            f"Facture exportée vers Odoo #{move_id}, mais la pièce jointe PDF "
            "n'a pas pu être ajoutée."
        )
    missing_account_codes = result.get("missing_account_codes") or []
    if missing_account_codes:
        message += " Comptes Odoo introuvables : " + ", ".join(missing_account_codes) + "."
    unmapped_account_codes = result.get("unmapped_account_codes") or []
    if unmapped_account_codes:
        message += " Mapping Odoo non défini pour : " + ", ".join(unmapped_account_codes) + "."
    return {
        "success": True,
        "invoice_id": invoice_id,
        **result,
        "already_exported": False,
        "message": message,
    }


@router.get("/invoice-pdf-preview/{invoice_id}")
def get_invoice_pdf_preview(invoice_id: str) -> dict:
    """Return preview metadata; pages are rendered as images inside the application."""
    _validate_invoice_id(invoice_id)
    try:
        import fitz

        pdf_bytes = _load_invoice_pdf_bytes(invoice_id)
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page_count = document.page_count
        finally:
            document.close()
        return {"invoice_id": invoice_id, "page_count": page_count}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible de préparer l’aperçu de la facture.") from exc


@router.get("/invoice-pdf-preview/{invoice_id}/pages/{page_number}")
def get_invoice_pdf_preview_page(invoice_id: str, page_number: int):
    """Render one PDF page as PNG so the browser never downloads the source file."""
    _validate_invoice_id(invoice_id)
    try:
        import fitz

        pdf_bytes = _load_invoice_pdf_bytes(invoice_id)
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page_number < 1 or page_number > document.page_count:
                raise HTTPException(status_code=404, detail="Page PDF introuvable.")
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            png_bytes = pixmap.tobytes("png")
        finally:
            document.close()
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=300"},
        )
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Impossible d’afficher cette page de facture.") from exc

@router.get("/debug-invoice-pdf/{invoice_id}")
def get_invoice_pdf_debug(invoice_id: str) -> dict:
    """Diagnostic endpoint — returns PDF path candidates for an invoice (no full paths)."""
    _validate_invoice_id(invoice_id)
    try:
        return debug_invoice_pdf(invoice_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="Erreur interne lors du diagnostic PDF."
        ) from exc


@router.get("/debug-pdf-storage")
def get_pdf_storage_debug() -> dict:
    """Diagnostic endpoint — returns backend disk visibility for PDF storage paths."""
    try:
        return debug_pdf_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="Erreur interne lors du diagnostic du stockage PDF."
        ) from exc

