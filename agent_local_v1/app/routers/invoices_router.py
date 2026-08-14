from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..config import COUCHDB_DATABASE
from ..database import _couch_request, http_session


router = APIRouter(prefix="/invoices", tags=["invoices"])


_PROTECTED_DATABASE_NAMES = {
    "keymanage accounting",
    "keymanage_accounting",
    "keymanage_accouting",
}


def _assert_invoice_database_is_safe() -> str:
    database = str(COUCHDB_DATABASE or "").strip()
    normalized = database.lower().replace("-", "_").replace(" ", "_")
    protected = {
        name.replace("-", "_").replace(" ", "_")
        for name in _PROTECTED_DATABASE_NAMES
    }
    if normalized in protected or ("keymanage" in normalized and "accounting" in normalized):
        raise HTTPException(
            status_code=403,
            detail="Suppression interdite : la base keymanage accounting est protégée.",
        )
    if not database:
        raise HTTPException(status_code=503, detail="Base CouchDB des factures non configurée.")
    return database

def _is_invoice_document(document: dict[str, Any]) -> bool:
    if not isinstance(document, dict):
        return False
    if str(document.get("_id", "")).startswith("_design/"):
        return False
    values = (document.get("type"), document.get("document_type"), document.get("doc_type"))
    normalized = {str(value or "").strip().lower() for value in values}
    if normalized.intersection({"invoice", "invoice_form", "invoice form"}):
        return True
    return "invoice_form" in document


def _nested_dicts(document: dict[str, Any]) -> list[dict[str, Any]]:
    result = [document]
    for key in ("invoice_form", "data", "document", "form", "fields", "extracted", "ocr"):
        value = document.get(key)
        if isinstance(value, dict):
            result.append(value)
    return result


def _raw_date(document: dict[str, Any]) -> Any:
    keys = (
        "date", "invoice_date", "emission_date", "createdAt", "created_at",
        "timestamp", "updatedAt", "updated_at",
    )
    for candidate in _nested_dicts(document):
        for key in keys:
            value = candidate.get(key)
            if value not in (None, ""):
                return value
    return None


def _sort_date(value: Any) -> tuple[int, float, str]:
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    text = str(value or "").strip()
    if not text:
        return (1, float("inf"), "")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (0, parsed.timestamp(), text)
    except ValueError:
        for pattern in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text[:10], pattern).replace(tzinfo=timezone.utc)
                return (0, parsed.timestamp(), text)
            except ValueError:
                continue
    return (1, float("inf"), text)


def _invoice_sort_key(document: dict[str, Any]) -> tuple[int, float, str]:
    date_key = _sort_date(_raw_date(document))
    return (date_key[0], date_key[1], str(document.get("_id", "")))


@router.delete("/purge-oldest")
def purge_oldest_invoices(
    keep: int = Query(50, ge=0, le=100000),
    confirm: bool = Query(False),
) -> dict[str, Any]:
    """Delete only the oldest invoice documents after explicit confirmation."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation requise pour supprimer les factures les plus anciennes.",
        )

    _assert_invoice_database_is_safe()

    try:
        with http_session() as session:
            payload = _couch_request(session, COUCHDB_DATABASE, "GET", "_all_docs?include_docs=true")
            rows = payload.get("rows", []) if isinstance(payload, dict) else []
            invoices = [
                row.get("doc")
                for row in rows
                if isinstance(row, dict) and _is_invoice_document(row.get("doc") or {})
            ]
            invoices = [document for document in invoices if document.get("_id") and document.get("_rev")]
            ordered = sorted(invoices, key=_invoice_sort_key)
            print(
                f"[invoices-purge] database={COUCHDB_DATABASE} scanned={len(rows)} "
                f"invoices={len(ordered)} keep={keep}"
            )
            targets = ordered[:-keep] if keep else ordered
            survivors = ordered[-keep:] if keep else []

            if targets:
                result = _couch_request(
                    session,
                    COUCHDB_DATABASE,
                    "POST",
                    "_bulk_docs",
                    json={
                        "docs": [
                            {"_id": document["_id"], "_rev": document["_rev"], "_deleted": True}
                            for document in targets
                        ]
                    },
                )
                failures = [
                    item for item in (result if isinstance(result, list) else [])
                    if isinstance(item, dict) and item.get("error")
                ]
                if failures:
                    raise HTTPException(
                        status_code=502,
                        detail=f"CouchDB a refuse {len(failures)} suppression(s).",
                    )
    except HTTPException:
        raise
    except Exception as error:
        print(f"[invoices-purge] database={COUCHDB_DATABASE} error={error}")
        raise HTTPException(status_code=503, detail="CouchDB indisponible ou mal configuree.") from error

    return {
        "deletedCount": len(targets),
        "remainingCount": len(survivors),
        "remainingInvoiceIds": [document["_id"] for document in survivors],
        "database": COUCHDB_DATABASE,
    }

@router.delete("/saved/purge")
def purge_all_saved_invoices(
    confirm: bool = Query(False),
) -> dict[str, Any]:
    """Permanently delete every saved invoice document from the active invoice DB."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation explicite requise pour supprimer définitivement les factures.",
        )

    database = _assert_invoice_database_is_safe()
    try:
        with http_session() as session:
            payload = _couch_request(session, database, "GET", "_all_docs?include_docs=true")
            rows = payload.get("rows", []) if isinstance(payload, dict) else []
            documents = [
                row.get("doc")
                for row in rows
                if isinstance(row, dict) and _is_invoice_document(row.get("doc") or {})
            ]
            targets = [
                document for document in documents
                if document.get("_id") and document.get("_rev")
                and not str(document.get("_id")).startswith("_design/")
            ]

            deleted_count = 0
            failures: list[dict[str, Any]] = []
            for offset in range(0, len(targets), 500):
                chunk = targets[offset : offset + 500]
                response = _couch_request(
                    session,
                    database,
                    "POST",
                    "_bulk_docs",
                    json={
                        "docs": [
                            {"_id": document["_id"], "_rev": document["_rev"], "_deleted": True}
                            for document in chunk
                        ]
                    },
                )
                results = response if isinstance(response, list) else []
                for item in results:
                    if isinstance(item, dict) and item.get("error"):
                        failures.append(item)
                    else:
                        deleted_count += 1

            if failures:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "message": f"CouchDB a refusé {len(failures)} suppression(s).",
                        "deletedCount": deleted_count,
                    },
                )

            print(
                f"[invoices-saved-purge] database={database} "
                f"scanned={len(rows)} deleted={deleted_count}"
            )
            return {
                "success": True,
                "count": deleted_count,
                "deletedCount": deleted_count,
                "database": database,
            }
    except HTTPException:
        raise
    except Exception as error:
        print(f"[invoices-saved-purge] database={database} error={error}")
        raise HTTPException(
            status_code=503,
            detail="CouchDB indisponible ou mal configurée.",
        ) from error

