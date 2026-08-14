from __future__ import annotations

import json
import os
import platform
import random
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from getpass import getuser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

from .account_labels import get_account_label
from .config import COUCHDB_DATABASE
from .database import COUCHDB_URL, get_supplier_memory, get_validation_patterns, http_session
from .schemas import (
    AccountingProposal,
    AccountingProposalLine,
    AccountingProposalSummary,
    ControlQueueCounts,
    ControlQueueItem,
    ControlQueueResponse,
    ControlQueueSummary,
    RandomInvoiceListItem,
    RandomInvoicesResponse,
    StrongAnalysisContext,
    StrongAnalysisResponse,
    StrongAnalysisSummary,
    StrongEnrichmentSuggestion,
    StrongInvoiceHeader,
    StrongLineAnalysis,
    StrongTopCandidate,
)
from .tools import matcher_tool


DB_CANDIDATES = tuple(
    dict.fromkeys(
        [
            COUCHDB_DATABASE,
            os.getenv("COUCHDB_DATABASE", "").strip(),
            "keymanage_accouting",
        ]
    )
)
SUPPLIER_PREFIX_RE = re.compile(r"^\s*(?:fournisseur|emetteur|metteur|vendor)\s*:\s*(.+?)\s*$", re.IGNORECASE)
CLIENT_PREFIX_RE = re.compile(r"^\s*(?:client|destinataire|recipient)\s*:\s*(.+?)\s*$", re.IGNORECASE)
CLIENT_APE_PREFIX_RE = re.compile(r"^\s*(?:ape\s+client|client\s+ape)\s*:\s*(.+?)\s*$", re.IGNORECASE)
SUPPLIER_APE_PREFIX_RE = re.compile(
    r"^\s*(?:ape\s+fournisseur|fournisseur\s+ape|supplier\s+ape)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
METIER_PREFIX_RE = re.compile(r"^\s*(?:metier|activit?|activite)\s*:\s*(.+?)\s*$", re.IGNORECASE)
ARTICLE_PREFIX_RE = re.compile(r"^\s*(?:article|produit|description)\s*:\s*(.+?)\s*$", re.IGNORECASE)
# Match any Unicode letter without relying on fragile encoded accent ranges.
ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)
NON_EXPLOITABLE_TEXT_RE = re.compile(
    r"\b(total|tva|ttc|ht|iban|bic|siret|adresse|email|telephone|paiement|echeance|date|facture|"
    r"conditions|reference|r?f?rence|ref)\b",
    re.IGNORECASE,
)

EXACT_APE_MAP: dict[str, list[str]] = {
    "4722Z": ["boucherie"],
    "5610A": ["restaurant"],
    "5610C": ["restaurant"],
    "5621Z": ["restaurant"],
    "5629A": ["restaurant"],
    "1071A": ["boulangerie"],
    "1071C": ["boulangerie"],
    "1071D": ["boulangerie"],
    "4724Z": ["boulangerie"],
    "4711B": ["epicerie"],
    "4932Z": ["vtc", "transport"],
    "4941A": ["transport"],
    "4941B": ["transport"],
    "5229A": ["transport"],
}
PREFIX_APE_MAP: dict[str, list[str]] = {
    "41": ["btp"],
    "42": ["btp"],
    "43": ["btp"],
}

TELECOM_KEYWORDS = {
    "bouygues",
    "telecom",
    "bbox",
    "byou",
    "byou",
    "livebox",
    "fibre",
    "forfait",
    "telephonie",
    "internet",
    "multi",
    "tv",
    "orange",
    "sfr",
    "free",
}
FUEL_KEYWORDS = {
    "gazole",
    "diesel",
    "carburant",
    "sp98",
    "essence",
    "adblue",
    "lavage",
    "gasoil",
}
FOOD_KEYWORDS = {
    "boeuf",
    "basse",
    "cote",
    "viande",
    "merguez",
    "saucisse",
    "epice",
    "tomate",
    "huile",
    "farine",
    "lait",
    "alimentaire",
    "poulet",
    "colorant",
    "sauce",
}
BTP_KEYWORDS = {
    "peinture",
    "mastic",
    "diluant",
    "filtre",
    "moteur",
    "plaquette",
    "ruban",
    "lame",
    "poncage",
    "vis",
    "support",
    "joint",
    "carrelage",
}
REPAIR_KEYWORDS = {
    "entretien",
    "reparation",
    "r?paration",
    "pneu",
    "amortisseur",
    "vidange",
    "frein",
    "plaquette",
    "huile",
}

QUEUE_DB_CANDIDATES = tuple(
    dict.fromkeys(
        filter(
            None,
            [
                os.getenv("COUCHDB_DATABASE", "").strip(),
                *DB_CANDIDATES,
            ],
        )
    )
)


def _matcher_module():
    return matcher_tool._load_module()  # noqa: SLF001


def _context_to_dict(context: StrongAnalysisContext | dict[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {}
    if isinstance(context, dict):
        return dict(context)
    if hasattr(context, "model_dump"):
        return dict(context.model_dump())
    if hasattr(context, "dict"):
        return dict(context.dict())
    return {}


def _unwrap_value(value: Any) -> Any:
    current = value
    while isinstance(current, dict) and "value" in current:
        current = current.get("value")
    return current


def _text(value: Any) -> str:
    return str(_unwrap_value(value) or "").strip()


def _safe_float(value: Any) -> float | None:
    raw = _unwrap_value(value)
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[^\d,.\-]", "", str(raw))
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_ape(value: str | None) -> str | None:
    ape = str(value or "").strip().upper().replace(" ", "")
    return ape or None


def _normalize_metier(value: str | None) -> str | None:
    metier = str(value or "").strip().lower().replace(" ", "_")
    if not metier:
        return None
    if metier == "global":
        return "charges_externes"
    return metier


def _extract_registration(entity: dict[str, Any] | None, reg_type: str) -> str | None:
    if not entity:
        return None
    for reg in entity.get("company_registrations") or []:
        if _text((reg or {}).get("type")).upper() == reg_type.upper():
            value = _text((reg or {}).get("value"))
            if value:
                return value
    return None


def _extract_entity_name(entity: dict[str, Any] | None) -> str | None:
    if not entity:
        return None
    for key in ("name", "company_name", "label"):
        value = _text(entity.get(key))
        if value:
            return value
    return None


def _extract_entity_ape(entity: dict[str, Any] | None) -> str | None:
    direct = _normalize_ape(_text((entity or {}).get("ape")))
    if direct:
        return direct
    registration = _extract_registration(entity, "APE")
    return _normalize_ape(registration)


def _infer_metiers_from_ape(ape: str | None) -> list[str]:
    normalized = _normalize_ape(ape)
    if not normalized:
        return []
    preferred: list[str] = []
    for metier in EXACT_APE_MAP.get(normalized, []):
        if metier not in preferred:
            preferred.append(metier)
    for prefix, metiers in PREFIX_APE_MAP.items():
        if normalized.startswith(prefix):
            for metier in metiers:
                if metier not in preferred:
                    preferred.append(metier)
    return preferred


def _infer_detected_activity(
    metier_hint: str | None,
    client_ape: str | None,
    supplier_ape: str | None,
    supplier: str | None = None,
    raw_text: str | None = None,
) -> str | None:
    normalized_hint = _normalize_metier(metier_hint)
    if normalized_hint:
        return normalized_hint

    ape_candidates = _infer_metiers_from_ape(client_ape) or _infer_metiers_from_ape(supplier_ape)
    if ape_candidates:
        return ape_candidates[0]

    module = _matcher_module()
    normalized = module.normalize_text(f"{supplier or ''} {raw_text or ''}")
    tokens = set(normalized.split())
    if tokens & TELECOM_KEYWORDS:
        return "charges_externes"
    if tokens & FUEL_KEYWORDS:
        return "transport"
    if tokens & BTP_KEYWORDS:
        return "btp"
    if tokens & FOOD_KEYWORDS:
        return "epicerie"
    return None


def _extract_description(line_item: dict[str, Any]) -> str:
    for key in (
        "description",
        "designation",
        "label",
        "libelle",
        "name",
        "item_name",
        "product_name",
        "product_label",
        "article",
        "article_source",
        "text",
        "raw_text",
        "title",
    ):
        value = _text(line_item.get(key))
        if value:
            return value
    return ""


def _parse_lines_from_ocr_text(ocr_text: str, initial_context: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context = dict(initial_context)
    lines: list[dict[str, Any]] = []
    fallback_lines: list[str] = []

    for raw_line in str(ocr_text or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -:;|")
        if not line:
            continue

        if match := SUPPLIER_PREFIX_RE.match(line):
            context["supplier"] = match.group(1).strip()
            continue
        if match := CLIENT_PREFIX_RE.match(line):
            context["client"] = match.group(1).strip()
            continue
        if match := CLIENT_APE_PREFIX_RE.match(line):
            context["client_ape"] = _normalize_ape(match.group(1))
            continue
        if match := SUPPLIER_APE_PREFIX_RE.match(line):
            context["supplier_ape"] = _normalize_ape(match.group(1))
            continue
        if match := METIER_PREFIX_RE.match(line):
            context["metier_hint"] = _normalize_metier(match.group(1))
            continue
        if match := ARTICLE_PREFIX_RE.match(line):
            lines.append({"raw_text": match.group(1).strip()})
            continue
        if not ALPHA_RE.search(line):
            continue
        if NON_EXPLOITABLE_TEXT_RE.search(line) and not line.lower().startswith("forfait"):
            continue
        fallback_lines.append(line)

    if not lines:
        module = _matcher_module()
        for line in fallback_lines:
            normalized = module.normalize_text(line)
            if len(normalized) < 3:
                continue
            lines.append({"raw_text": line})

    return lines, context


def _extract_context_from_invoice(invoice_doc: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    base_context = dict(context or {})
    invoice_form = _safe_dict(invoice_doc.get("invoice_form"))
    data = _safe_dict(invoice_doc.get("data"))
    document = _safe_dict(invoice_doc.get("document"))
    issuer = (
        _safe_dict(invoice_doc.get("issuer"))
        or _safe_dict(invoice_form.get("issuer"))
        or _safe_dict(data.get("issuer"))
        or _safe_dict(document.get("issuer"))
    )
    recipient = (
        _safe_dict(invoice_doc.get("recipient"))
        or _safe_dict(invoice_form.get("recipient"))
        or _safe_dict(data.get("recipient"))
        or _safe_dict(document.get("recipient"))
    )
    inferred = {
        "supplier": _extract_entity_name(issuer) or _first_non_empty(
            invoice_doc.get("supplier"),
            invoice_form.get("supplier"),
            data.get("supplier"),
            document.get("supplier"),
        ),
        "client": _extract_entity_name(recipient) or _first_non_empty(
            invoice_doc.get("client"),
            invoice_form.get("client"),
            data.get("client"),
            document.get("client"),
        ),
        "client_ape": (
            _extract_entity_ape(recipient)
            or _normalize_ape(_first_non_empty(
                invoice_doc.get("km_ape"),
                invoice_doc.get("client_ape"),
                invoice_form.get("client_ape"),
                data.get("client_ape"),
                document.get("client_ape"),
            ))
        ),
        "supplier_ape": (
            _extract_entity_ape(issuer)
            or _normalize_ape(_first_non_empty(
                invoice_doc.get("supplier_ape"),
                invoice_form.get("supplier_ape"),
                data.get("supplier_ape"),
                document.get("supplier_ape"),
            ))
        ),
        "currency": _first_non_empty(
            invoice_doc.get("currency"),
            invoice_form.get("currency"),
            data.get("currency"),
            document.get("currency"),
        ),
        "invoice_number": _first_non_empty(
            invoice_doc.get("invoice_number"),
            invoice_form.get("invoice_number"),
            data.get("invoice_number"),
            document.get("invoice_number"),
        ),
        "invoice_date": _first_non_empty(
            invoice_doc.get("invoice_date"),
            invoice_form.get("invoice_date"),
            data.get("invoice_date"),
            document.get("invoice_date"),
        ),
        "invoice_id": _text(invoice_doc.get("_id")) or None,
    }
    inferred_metier = _infer_detected_activity(
        base_context.get("metier_hint"),
        inferred.get("client_ape"),
        inferred.get("supplier_ape"),
        inferred.get("supplier"),
    )
    inferred["metier_hint"] = _normalize_metier(base_context.get("metier_hint") or inferred_metier)

    merged = dict(inferred)
    for key, value in base_context.items():
        if value not in (None, ""):
            merged[key] = value
    if not merged.get("metier_hint"):
        merged["metier_hint"] = inferred_metier
    return merged


def _extract_invoice_line_items_with_source(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    invoice_form = _safe_dict(doc.get("invoice_form"))
    data = _safe_dict(doc.get("data"))
    document = _safe_dict(doc.get("document"))
    form = _safe_dict(doc.get("form"))
    fields = _safe_dict(doc.get("fields"))
    extracted = _safe_dict(doc.get("extracted"))
    ocr = _safe_dict(doc.get("ocr"))

    candidates = (
        ("line_items", doc.get("line_items")),
        ("invoice_form.line_items", invoice_form.get("line_items")),
        ("items", doc.get("items")),
        ("lines", doc.get("lines")),
        ("invoice_lines", doc.get("invoice_lines")),
        ("products", doc.get("products")),
        ("form.line_items", form.get("line_items")),
        ("fields.line_items", fields.get("line_items")),
        ("extracted.line_items", extracted.get("line_items")),
        ("ocr.line_items", ocr.get("line_items")),
        ("data.line_items", data.get("line_items")),
        ("document.line_items", document.get("line_items")),
    )

    for source_name, candidate in candidates:
        if isinstance(candidate, list):
            return [line for line in candidate if isinstance(line, dict)], source_name
    return [], "none"


def _build_line_payloads(
    invoice_doc_or_lines: dict[str, Any] | list[dict[str, Any]] | str,
    context: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], str]:
    invoice_meta: dict[str, Any] = {}
    working_context = dict(context)

    if isinstance(invoice_doc_or_lines, str):
        lines, working_context = _parse_lines_from_ocr_text(invoice_doc_or_lines, working_context)
        return lines, working_context, invoice_meta, "ocr_text"

    if isinstance(invoice_doc_or_lines, list):
        payloads: list[dict[str, Any]] = []
        for line_item in invoice_doc_or_lines:
            raw_text = _extract_description(line_item) or _text(line_item.get("description"))
            if not raw_text:
                continue
            payloads.append(
                {
                    "raw_text": raw_text,
                    "quantity": _safe_float(line_item.get("quantity")),
                    "unit_price": _safe_float(line_item.get("unit_price")),
                    "amount_ht": _safe_float(line_item.get("amount_ht") or line_item.get("total_net")),
                    "amount_ttc": _safe_float(line_item.get("amount_ttc") or line_item.get("total_gross")),
                    "tva": _safe_float(line_item.get("tva") or line_item.get("vat_percent")),
                }
            )
        return payloads, working_context, invoice_meta, "input_list"

    if isinstance(invoice_doc_or_lines, dict):
        extracted_line_items, extracted_source = _extract_invoice_line_items_with_source(invoice_doc_or_lines)
        if extracted_line_items:
            invoice_form = _safe_dict(invoice_doc_or_lines.get("invoice_form"))
            data = _safe_dict(invoice_doc_or_lines.get("data"))
            document = _safe_dict(invoice_doc_or_lines.get("document"))
            invoice_meta = {
                "invoice_id": _text(invoice_doc_or_lines.get("_id")) or None,
                "invoice_number": _first_non_empty(
                    invoice_doc_or_lines.get("invoice_number"),
                    invoice_form.get("invoice_number"),
                    data.get("invoice_number"),
                    document.get("invoice_number"),
                ),
                "invoice_date": _first_non_empty(
                    invoice_doc_or_lines.get("invoice_date"),
                    invoice_form.get("invoice_date"),
                    data.get("invoice_date"),
                    document.get("invoice_date"),
                ),
                "currency": _first_non_empty(
                    invoice_doc_or_lines.get("currency"),
                    invoice_form.get("currency"),
                    data.get("currency"),
                    document.get("currency"),
                ),
            }
            working_context = _extract_context_from_invoice(invoice_doc_or_lines, working_context)
            payloads = []
            for line_item in extracted_line_items:
                if not isinstance(line_item, dict):
                    continue
                raw_text = _extract_description(line_item)
                if not raw_text:
                    continue
                payloads.append(
                    {
                        "raw_text": raw_text,
                        "quantity": _safe_float(line_item.get("quantity")),
                        "unit_price": _safe_float(line_item.get("unit_price")),
                        "amount_ht": _safe_float(line_item.get("amount_ht") or line_item.get("total_net")),
                        "amount_ttc": _safe_float(line_item.get("amount_ttc") or line_item.get("total_gross")),
                        "tva": _safe_float(line_item.get("tva") or line_item.get("vat_percent")),
                    }
                )
            return payloads, working_context, invoice_meta, extracted_source

        if invoice_doc_or_lines.get("ocr_text"):
            lines, working_context = _parse_lines_from_ocr_text(
                _text(invoice_doc_or_lines.get("ocr_text")),
                working_context,
            )
            invoice_meta = {
                "invoice_id": _text(invoice_doc_or_lines.get("invoice_id")) or None,
                "invoice_number": _text(invoice_doc_or_lines.get("invoice_number")) or None,
                "invoice_date": _text(invoice_doc_or_lines.get("invoice_date")) or None,
                "currency": _text(invoice_doc_or_lines.get("currency")) or None,
            }
            return lines, working_context, invoice_meta, "ocr_text_field"

    return [], working_context, invoice_meta, "none"


def _is_invoice_form_invoice(doc: dict[str, Any]) -> bool:
    if _text(doc.get("p") or doc.get("type")).lower() != "invoice_form":
        return False
    document_type = _text(
        doc.get("document_type")
        or _safe_dict(doc.get("invoice_form")).get("document_type")
        or _safe_dict(doc.get("data")).get("document_type")
        or _safe_dict(doc.get("document")).get("document_type")
    ).lower()
    if document_type != "invoice":
        return False
    line_items, _ = _extract_invoice_line_items_with_source(doc)
    return bool(line_items)


def _resolve_invoice_db_name(session: requests.Session) -> str:
    for db_name in DB_CANDIDATES:
        try:
            response = session.get(f"{COUCHDB_URL}/{quote(db_name, safe='')}", timeout=30)
            if response.status_code == 200:
                return db_name
        except requests.RequestException:
            continue
    raise RuntimeError("CouchDB indisponible ou mal configur?e.")


def _fetch_invoice_doc(invoice_id: str) -> dict[str, Any]:
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{quote(str(invoice_id), safe='')}",
        timeout=120,
    )
    if response.status_code == 404:
        raise RuntimeError("Facture introuvable dans CouchDB.")
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict) or not _is_invoice_form_invoice(doc):
        raise RuntimeError("Le document demandé n'est pas une invoice_form exploitable.")
    return doc


def _fetch_invoice_doc_with_meta(invoice_id: str) -> tuple[dict[str, Any], str, float]:
    session = http_session()
    started = time.perf_counter()
    db_name = _resolve_invoice_db_name(session)
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{quote(str(invoice_id), safe='')}",
        timeout=120,
    )
    if response.status_code == 404:
        raise RuntimeError(f"Facture introuvable dans {db_name}.")
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict) or not _is_invoice_form_invoice(doc):
        raise RuntimeError("Le document demandé n'est pas une invoice_form exploitable.")
    return doc, db_name, round((time.perf_counter() - started) * 1000, 2)


def _sample_random_invoice_docs(limit: int) -> list[dict[str, Any]]:
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    rng = random.Random()
    chosen: dict[str, dict[str, Any]] = {}

    for _ in range(max(limit * 6, 24)):
        startkey = f"fr_bd_{rng.randint(0, 999999999):09d}"
        response = session.get(
            f"{COUCHDB_URL}/{quote(db_name, safe='')}/_all_docs",
            params={
                "include_docs": "true",
                "startkey": json.dumps(startkey),
                "limit": "120",
            },
            timeout=120,
        )
        response.raise_for_status()
        rows = response.json().get("rows") or []
        for row in rows:
            doc = row.get("doc") or {}
            if not isinstance(doc, dict) or not _is_invoice_form_invoice(doc):
                continue
            doc_id = _text(doc.get("_id"))
            if doc_id:
                chosen[doc_id] = doc
        if len(chosen) >= limit:
            break

    docs = list(chosen.values())
    if len(docs) > limit:
        docs = rng.sample(docs, limit)
    return docs


def _build_random_invoice_list_item(doc: dict[str, Any]) -> tuple[RandomInvoiceListItem, int]:
    context = _extract_context_from_invoice(doc, {})
    line_items, _ = _extract_invoice_line_items_with_source(doc)
    exploitable = 0
    module = _matcher_module()
    for line_item in line_items:
        raw_text = _extract_description(line_item)
        if raw_text and not module.is_non_article_line(raw_text):
            exploitable += 1

    return (
        RandomInvoiceListItem(
            invoice_id=_text(doc.get("_id")),
            invoice_number=_text(doc.get("invoice_number")) or None,
            invoice_date=_text(doc.get("invoice_date")) or None,
            supplier=context.get("supplier"),
            client=context.get("client"),
            client_ape=context.get("client_ape"),
            supplier_ape=context.get("supplier_ape"),
            line_items_count=len(line_items),
            exploitable_lines_count=exploitable,
            status="sans_lignes_exploitables" if exploitable == 0 else "prete_a_analyser",
        ),
        exploitable,
    )


def fetch_unprocessed_invoices(
    limit: int = 50,
    *,
    exclude_invoice_ids: set[str] | None = None,
    startkey: str | None = None,
    max_scan_rows: int | None = None,
) -> tuple[RandomInvoicesResponse, dict[str, Any]]:
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    requested_limit = max(1, min(int(limit or 50), 100))
    excluded_ids = {str(value).strip() for value in (exclude_invoice_ids or set()) if str(value).strip()}
    page_size = max(80, min(200, requested_limit * 10))
    scan_budget = max_scan_rows or min(20000, max(2500, requested_limit * 250))
    selected_items: list[RandomInvoiceListItem] = []
    selected_ids: set[str] = set()
    current_startkey = str(startkey or "").strip()
    wrap_boundary = current_startkey or None
    scanned_rows = 0
    candidates_found = 0
    wrapped = False
    cycle_completed = False
    next_startkey = current_startkey

    while scanned_rows < scan_budget and len(selected_items) < requested_limit:
        params = {
            "include_docs": "true",
            "limit": str(page_size),
        }
        if current_startkey:
            params["startkey"] = json.dumps(current_startkey)

        response = session.get(
            f"{COUCHDB_URL}/{quote(db_name, safe='')}/_all_docs",
            params=params,
            timeout=120,
        )
        response.raise_for_status()
        rows = response.json().get("rows") or []
        if not rows:
            if wrap_boundary and not wrapped:
                wrapped = True
                current_startkey = ""
                next_startkey = ""
                continue
            cycle_completed = True
            break

        stop_after_page = False
        for row in rows:
            row_id = _text(row.get("id"))
            if not row_id:
                continue
            if wrapped and wrap_boundary and row_id >= wrap_boundary:
                cycle_completed = True
                stop_after_page = True
                break

            scanned_rows += 1
            next_startkey = f"{row_id}\ufff0"
            doc = row.get("doc") or {}
            if not isinstance(doc, dict) or not _is_invoice_form_invoice(doc):
                if scanned_rows >= scan_budget:
                    stop_after_page = True
                    break
                continue

            try:
                item, exploitable = _build_random_invoice_list_item(doc)
            except Exception:
                if scanned_rows >= scan_budget:
                    stop_after_page = True
                    break
                continue
            invoice_id = _text(getattr(item, "invoice_id", ""))
            if not invoice_id or exploitable <= 0 or invoice_id in excluded_ids:
                if scanned_rows >= scan_budget:
                    stop_after_page = True
                    break
                continue

            candidates_found += 1
            if invoice_id not in selected_ids and len(selected_items) < requested_limit:
                selected_ids.add(invoice_id)
                selected_items.append(item)

            if scanned_rows >= scan_budget:
                stop_after_page = True
                break

        if stop_after_page:
            break

        if len(rows) < page_size:
            if wrap_boundary and not wrapped:
                wrapped = True
                current_startkey = ""
                next_startkey = ""
                continue
            cycle_completed = True
            break

        current_startkey = next_startkey

    metadata = {
        "database": db_name,
        "selection_strategy": "unprocessed_first",
        "scanned_rows": scanned_rows,
        "candidates_found": candidates_found,
        "selected_count": len(selected_items),
        "next_startkey": next_startkey,
        "cycle_completed": cycle_completed,
    }
    return RandomInvoicesResponse(items=selected_items), metadata


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        text = _text(value)
        if text:
            return text
    return None


def _extract_match_reason(candidate: dict[str, Any]) -> str:
    return _text(candidate.get("raison_match")) or _text(candidate.get("reason"))


def _is_exact_candidate(candidate: dict[str, Any]) -> bool:
    reason = _extract_match_reason(candidate).lower()
    return "match exact article_source" in reason or "match exact article_canonique" in reason


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _normalize_metier(candidate.get("metier")) or _normalize_metier(candidate.get("base_cible")) or "",
        _first_non_empty(candidate.get("article_source_match"), candidate.get("article_source")) or "",
        _text(candidate.get("compte_comptable") or candidate.get("account")),
    )


def _merge_matches(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    module = _matcher_module()
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for group in groups:
        for candidate in group:
            key = _candidate_key(candidate)
            current = by_key.get(key)
            if current is None:
                by_key[key] = candidate
                continue

            current_score = float(current.get("score_confiance") or 0.0)
            next_score = float(candidate.get("score_confiance") or 0.0)
            current_exact = _is_exact_candidate(current)
            next_exact = _is_exact_candidate(candidate)
            if next_exact and not current_exact:
                by_key[key] = candidate
            elif next_score > current_score:
                by_key[key] = candidate

    merged = list(by_key.values())
    merged.sort(
        key=lambda row: (
            -float(row.get("score_confiance") or 0.0),
            0 if _is_exact_candidate(row) else 1,
            -(module.decision_rank(_text(row.get("decision_finale") or row.get("decision")))),
            -(module.coherence_rank(_text(row.get("metier_coherence")))),
        )
    )
    return merged[:3]


def _build_evidence_status(
    account: str | None,
    source_invoice_ids: list[str],
    invoice_paths_sources: list[str],
    partitions_sources: list[str],
    ape_context: list[str],
) -> str:
    has_account = bool(_text(account))
    has_invoice_ids = bool(source_invoice_ids)
    has_paths = bool(invoice_paths_sources)
    has_context = bool(partitions_sources or ape_context)
    if has_account and has_invoice_ids and has_paths and has_context:
        return "complete"
    if has_account and (has_invoice_ids or has_paths or has_context):
        return "partial"
    return "missing"


def _quality_from_line(
    referential_status: str,
    evidence_status: str,
    decision: str,
) -> str:
    if referential_status == "non_comptable":
        return "fiable"
    if referential_status == "found_exact" and evidence_status in {"complete", "partial"} and decision != "rejeter":
        return "fiable"
    return "a_controler"


def _to_top_candidate(candidate: dict[str, Any]) -> StrongTopCandidate:
    source_invoice_ids = list(candidate.get("source_invoice_ids") or [])
    invoice_paths_sources = list(candidate.get("invoice_paths_sources") or [])
    partitions_sources = list(candidate.get("partitions_sources") or [])
    ape_context = list(candidate.get("ape_context") or [])
    return StrongTopCandidate(
        account=_text(candidate.get("compte_comptable") or candidate.get("account")) or None,
        account_label=_first_non_empty(
            candidate.get("compte_comptable_libelle"),
            candidate.get("account_label"),
            get_account_label(candidate.get("compte_comptable") or candidate.get("account")),
        ),
        article_source=_first_non_empty(candidate.get("article_source_match"), candidate.get("article_source")),
        article_canonique=_text(candidate.get("article_canonique")) or None,
        base=_normalize_metier(candidate.get("metier")) or _normalize_metier(candidate.get("base_cible")),
        score=round(float(candidate.get("score_confiance") or candidate.get("score") or 0.0), 2),
        reason=_extract_match_reason(candidate),
        decision=_text(candidate.get("decision_finale") or candidate.get("decision")) or None,
        evidence_status=_build_evidence_status(
            _text(candidate.get("compte_comptable") or candidate.get("account")),
            source_invoice_ids,
            invoice_paths_sources,
            partitions_sources,
            ape_context,
        ),
        categorie=_text(candidate.get("categorie")) or None,
        sous_categorie=_text(candidate.get("sous_categorie")) or None,
        taux_tva=_safe_float(candidate.get("taux_tva") or candidate.get("tva_rate")),
        type_fournisseur=_text(candidate.get("type_fournisseur")) or None,
        source_invoice_ids=source_invoice_ids,
        invoice_paths_sources=invoice_paths_sources,
        partitions_sources=partitions_sources,
        ape_context=ape_context,
    )



def _amount_value(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _line_amounts_balanced(line: Any, *, tolerance: float = 0.02) -> bool:
    amount_ht = _amount_value(getattr(line, "amount_ht", None))
    amount_ttc = _amount_value(getattr(line, "amount_ttc", None))
    if amount_ht is None or amount_ttc is None:
        return False

    vat_amount = _amount_value(getattr(line, "vat_amount", None))
    if vat_amount is None:
        tva = _amount_value(getattr(line, "tva", None))
        if tva is None:
            tva = _amount_value(getattr(line, "taux_tva", None))
        vat_amount = amount_ht * (tva / 100.0) if tva is not None else None

    if vat_amount is None:
        return False
    return abs((amount_ht + vat_amount) - amount_ttc) <= tolerance


def _routing_lines(response: Any) -> list[Any]:
    lines = list(getattr(response, "lines", []) or [])
    return [
        line
        for line in lines
        if str(getattr(line, "decision", "") or "").strip().lower() != "non_comptable"
        and str(getattr(line, "referential_status", "") or "").strip().lower() != "non_comptable"
    ]


def determine_invoice_workflow_status(
    response: Any,
    *,
    existing_invoice_ids: set[str] | None = None,
    invoice_id: str | None = None,
) -> dict[str, Any]:
    """Central secure routing rule for batch and manual invoice analysis."""
    invoice = getattr(response, "invoice", None)
    resolved_invoice_id = str(
        invoice_id
        or getattr(invoice, "invoice_id", "")
        or getattr(response, "invoice_id", "")
        or ""
    ).strip()
    existing_ids = existing_invoice_ids or set()
    is_duplicate = bool(resolved_invoice_id and resolved_invoice_id in existing_ids)
    lines = _routing_lines(response)
    reasons: list[str] = []

    if not lines:
        reasons.append("aucune_ligne_comptable_exploitable")

    line_checks: list[bool] = []
    amount_checks: list[bool] = []
    confidences: list[float] = []
    for line in lines:
        try:
            confidence = float(getattr(line, "confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidences.append(confidence)
        referential_status = str(getattr(line, "referential_status", "") or "").strip().lower()
        decision = str(getattr(line, "decision", "") or "").strip().lower()
        evidence_status = str(getattr(line, "evidence_status", "") or "").strip().lower()
        line_checks.append(
            referential_status == "found_exact"
            and decision == "auto_ok"
            and confidence >= 90.0
            and evidence_status in {"complete", "partial"}
        )
        amount_checks.append(_line_amounts_balanced(line))

    all_lines_exact_auto = bool(lines) and all(line_checks)
    amounts_balanced = bool(lines) and all(amount_checks)
    average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    if not all_lines_exact_auto:
        reasons.append("ligne_non_exacte_ou_non_auto_ok")
    if not amounts_balanced:
        reasons.append("equation_montants_non_verifiee")
    if is_duplicate:
        reasons.append("invoice_id_deja_present")

    can_auto_validate = all_lines_exact_auto and amounts_balanced and not is_duplicate
    if can_auto_validate:
        return {
            "workflow_status": "VALIDE_AUTO",
            "destination": "ecritures_validees",
            "routing_reasons": ["criteres_haute_confiance_valides"],
            "all_lines_exact_auto": True,
            "amounts_balanced": True,
            "is_duplicate": False,
            "average_confidence": average_confidence,
            "global_decision": "Valid?e automatiquement",
            "global_risk_level": "Faible",
            "can_validate_accounting": True,
        }

    rejected = average_confidence < 50.0
    return {
        "workflow_status": "A_CONTROLER",
        "destination": "validation_humaine",
        "routing_reasons": reasons or ["controle_humain_requis"],
        "all_lines_exact_auto": all_lines_exact_auto,
        "amounts_balanced": amounts_balanced,
        "is_duplicate": is_duplicate,
        "average_confidence": average_confidence,
        "global_decision": "Rejet?e" if rejected else "? valider",
        "global_risk_level": "?lev?" if rejected else "Moyen",
        "can_validate_accounting": not rejected,
    }

def _build_contextual_hypothesis(cleaned_text: str, context: dict[str, Any]) -> dict[str, Any] | None:
    module = _matcher_module()
    normalized = module.normalize_text(f"{context.get('supplier') or ''} {cleaned_text}")
    tokens = set(normalized.split())
    detected_activity = _infer_detected_activity(
        context.get("metier_hint"),
        context.get("client_ape"),
        context.get("supplier_ape"),
        context.get("supplier"),
        cleaned_text,
    )

    if tokens & TELECOM_KEYWORDS:
        account = "6261" if {"fibre", "bbox", "byou", "b&you", "forfait", "telephonie", "internet"} & tokens else "626"
        return {
            "base": "charges_externes",
            "account": account,
            "account_label": get_account_label(account),
            "score": 68.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le contexte fournisseur / t?l?com sugg?re une charge de t?l?communications.",
            "detected_activity": detected_activity or "charges_externes",
        }

    if tokens & FUEL_KEYWORDS:
        account = "6063"
        base = detected_activity if detected_activity in {"transport", "vtc"} else "charges_externes"
        return {
            "base": base,
            "account": account,
            "account_label": get_account_label(account),
            "score": 66.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le libell? ?voque du carburant ou un consommable mobilit?.",
            "detected_activity": detected_activity or base,
        }

    if (
        {"lame", "ruban", "coutellerie", "couteau"} & tokens
        or "coutellerie" in normalized
    ) and detected_activity in {"boucherie", "restaurant", "charges_externes", None}:
        account = "6063"
        return {
            "base": detected_activity or "charges_externes",
            "account": account,
            "account_label": get_account_label(account),
            "score": 63.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le contexte ?voque un mat?riel / consommable m?tier ? faire valider.",
            "detected_activity": detected_activity or "charges_externes",
        }

    if tokens & BTP_KEYWORDS and (
        detected_activity == "btp"
        or _normalize_ape(context.get("client_ape") or "").startswith(("41", "42", "43"))
    ):
        account = "6068"
        if {"filtre", "moteur", "plaquette"} & tokens:
            account = "6063"
        return {
            "base": "btp",
            "account": account,
            "account_label": get_account_label(account),
            "score": 64.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le contexte BTP oriente vers un consommable / mat?riel d'atelier.",
            "detected_activity": "btp",
        }

    if tokens & FOOD_KEYWORDS:
        metier = detected_activity or "epicerie"
        account = "607"
        if metier == "boucherie":
            account = "6011"
        elif metier in {"restaurant", "boulangerie"}:
            account = "601"
        return {
            "base": metier,
            "account": account,
            "account_label": get_account_label(account),
            "score": 65.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le contexte alimentaire permet une hypoth?se prudente ? valider.",
            "detected_activity": metier,
        }

    if tokens & REPAIR_KEYWORDS and detected_activity in {"transport", "vtc"}:
        account = "615"
        if "huile" in tokens:
            account = "6063"
        return {
            "base": detected_activity,
            "account": account,
            "account_label": get_account_label(account),
            "score": 64.0,
            "reason": "Article absent du r?f?rentiel valid?, mais le contexte mobilit? ?voque un entretien / consommable v?hicule.",
            "detected_activity": detected_activity,
        }

    return None


def _build_enrichment_suggestion(
    referential_status: str,
    hypothesis: dict[str, Any] | None,
    top_candidate: StrongTopCandidate | None,
) -> StrongEnrichmentSuggestion:
    if referential_status == "found_exact":
        return StrongEnrichmentSuggestion(
            should_enrich=False,
            reason="Ligne d?j? couverte par un r?f?rentiel valid?.",
        )

    if referential_status == "non_comptable":
        return StrongEnrichmentSuggestion(
            should_enrich=False,
            reason="Ligne non comptable ? ignorer dans le r?f?rentiel produit.",
        )

    suggested_base = None
    suggested_account = None
    suggested_label = None
    reason = "Article absent ou proche du r?f?rentiel valid?."

    if hypothesis:
        suggested_base = hypothesis.get("base")
        suggested_account = hypothesis.get("account")
        suggested_label = hypothesis.get("account_label")
        reason = hypothesis.get("reason") or reason
    elif top_candidate is not None:
        suggested_base = top_candidate.base
        suggested_account = top_candidate.account
        suggested_label = top_candidate.account_label
        reason = top_candidate.reason or reason

    return StrongEnrichmentSuggestion(
        should_enrich=referential_status in {"found_fuzzy", "missing_candidate", "unknown"},
        suggested_base=suggested_base,
        suggested_account=suggested_account,
        suggested_label=suggested_label,
        reason=reason,
        requires_expert_validation=True,
    )


def _build_decision_reason(
    referential_status: str,
    top_candidate: StrongTopCandidate | None,
    hypothesis: dict[str, Any] | None,
    context: dict[str, Any],
    decision: str,
) -> str:
    supplier = context.get("supplier") or "fournisseur inconnu"
    client_ape = context.get("client_ape") or "APE client absent"

    if referential_status == "non_comptable":
        return "Ligne non comptable d?tect?e (remise, taxe, p?riode, paiement ou m?tadonn?e), donc ignor?e par le moteur."

    if top_candidate and referential_status == "found_exact":
        proof_count = len(top_candidate.source_invoice_ids)
        return (
            f"Match exact avec le r?f?rentiel valid? ({top_candidate.article_source or 'article connu'}), "
            f"compte {top_candidate.account or 'non renseign?'} propos? avec {proof_count} facture(s) source et contexte {client_ape}."
        )

    if top_candidate and referential_status == "found_fuzzy":
        return (
            f"Article proche d'une r?f?rence connue ({top_candidate.article_source or 'r?f?rence voisine'}) "
            f"avec un score de {round(top_candidate.score, 1)}. Validation humaine requise."
        )

    if hypothesis and referential_status == "missing_candidate":
        return (
            f"Article absent du r?f?rentiel valid?. Hypoth?se contextuelle construite depuis {supplier} "
            f"et l'activit? d?tect?e, sans auto-validation."
        )

    if decision == "rejeter":
        return "Article absent du r?f?rentiel et aucun candidat assez fiable n'a ?t? retenu. Enrichissement futur ? ?tudier."

    return "D?cision prudente : contexte ou r?f?rentiel insuffisant, validation humaine requise."


def _risk_from_decision(
    referential_status: str,
    confidence: float,
    decision: str,
    evidence_status: str,
) -> str:
    if referential_status == "non_comptable":
        return "faible"
    if decision == "auto_ok" and confidence >= 90.0 and evidence_status != "missing":
        return "faible"
    if decision == "validation_humaine":
        return "moyen"
    if confidence < 50.0 or referential_status in {"missing_candidate", "unknown"}:
        return "eleve"
    return "moyen"


def _score_to_referential_status(
    top_matches: list[dict[str, Any]],
    hypothesis: dict[str, Any] | None,
) -> str:
    if top_matches:
        top = top_matches[0]
        score = float(top.get("score_confiance") or 0.0)
        if _is_exact_candidate(top):
            return "found_exact"
        if score >= 50.0:
            return "found_fuzzy"
    if hypothesis:
        return "missing_candidate"
    return "unknown"


def _decision_from_status(
    referential_status: str,
    top_match: dict[str, Any] | None,
    hypothesis: dict[str, Any] | None,
) -> str:
    if referential_status == "non_comptable":
        return "non_comptable"
    if referential_status == "found_exact":
        return "auto_ok"
    if referential_status == "found_fuzzy":
        score = float((top_match or {}).get("score_confiance") or 0.0)
        if score >= 90.0:
            return "auto_ok"
        return "validation_humaine" if score >= 50.0 else "rejeter"
    if referential_status == "missing_candidate":
        score = float((hypothesis or {}).get("score") or 0.0)
        return "validation_humaine" if hypothesis and score >= 50.0 else "rejeter"
    return "rejeter"


def _non_comptable_line_analysis(line_payload: dict[str, Any], context: dict[str, Any]) -> StrongLineAnalysis:
    module = _matcher_module()
    cleaned_text = module.normalize_text(line_payload.get("raw_text") or "")
    return StrongLineAnalysis(
        raw_text=line_payload.get("raw_text") or "",
        cleaned_text=cleaned_text,
        quantity=line_payload.get("quantity"),
        unit_price=line_payload.get("unit_price"),
        amount_ht=line_payload.get("amount_ht"),
        amount_ttc=line_payload.get("amount_ttc"),
        tva=line_payload.get("tva"),
        supplier=context.get("supplier"),
        client=context.get("client"),
        client_ape=context.get("client_ape"),
        supplier_ape=context.get("supplier_ape"),
        metier_hint=context.get("metier_hint"),
        detected_activity=_infer_detected_activity(
            context.get("metier_hint"),
            context.get("client_ape"),
            context.get("supplier_ape"),
            context.get("supplier"),
            line_payload.get("raw_text"),
        ),
        referential_status="non_comptable",
        recommended_account=None,
        recommended_account_label=None,
        confidence=0.0,
        risk_level="faible",
        decision="non_comptable",
        decision_reason="Ligne non comptable d?tect?e : elle n'est pas envoy?e au moteur de recommandation.",
        evidence_status="missing",
        quality_status="fiable",
    )


def _failed_line_analysis(
    line_payload: dict[str, Any],
    context: dict[str, Any],
    exc: Exception,
) -> StrongLineAnalysis:
    raw_text = _text(line_payload.get("raw_text")) or "Ligne invalide"
    cleaned_text = _matcher_module().normalize_text(raw_text)
    reason = (
        "Erreur moteur pendant l'analyse de cette ligne. "
        f"Ligne conserv?e mais rejet?e par prudence ({exc.__class__.__name__}: {exc})."
    )
    return StrongLineAnalysis(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        quantity=line_payload.get("quantity"),
        unit_price=line_payload.get("unit_price"),
        amount_ht=line_payload.get("amount_ht"),
        amount_ttc=line_payload.get("amount_ttc"),
        tva=line_payload.get("tva"),
        supplier=context.get("supplier"),
        client=context.get("client"),
        client_ape=context.get("client_ape"),
        supplier_ape=context.get("supplier_ape"),
        metier_hint=context.get("metier_hint"),
        detected_activity=_infer_detected_activity(
            context.get("metier_hint"),
            context.get("client_ape"),
            context.get("supplier_ape"),
            context.get("supplier"),
            raw_text,
        ),
        referential_status="unknown",
        recommended_account=None,
        recommended_account_label=None,
        confidence=0.0,
        risk_level="eleve",
        decision="rejeter",
        decision_reason=reason,
        evidence_status="missing",
        quality_status="a_controler",
        enrichment_suggestion=StrongEnrichmentSuggestion(
            should_enrich=False,
            reason=reason,
            requires_expert_validation=True,
        ),
    )


def _analyze_single_line(line_payload: dict[str, Any], context: dict[str, Any]) -> StrongLineAnalysis:
    raw_text = _text(line_payload.get("raw_text"))
    module = _matcher_module()
    cleaned_text = module.normalize_text(raw_text)

    if not cleaned_text or module.is_non_article_line(raw_text):
        return _non_comptable_line_analysis(line_payload, context)

    supplier_account_stats = context.get("_supplier_account_stats")
    if "_supplier_account_stats" not in context:
        try:
            supplier_account_stats = get_supplier_memory(
                fournisseur_hint=context.get("supplier"),
                metier_hint=context.get("metier_hint"),
            )
        except Exception:
            supplier_account_stats = None

    validation_pattern_cache = context.get("_validation_pattern_cache")
    cache_key = (
        raw_text,
        context.get("supplier"),
        context.get("metier_hint"),
    )
    try:
        if isinstance(validation_pattern_cache, dict) and cache_key in validation_pattern_cache:
            validation_pattern_stats = validation_pattern_cache.get(cache_key)
        else:
            validation_pattern_stats = get_validation_patterns(
                article_source=raw_text,
                fournisseur_hint=context.get("supplier"),
                metier_hint=context.get("metier_hint"),
            )
            if isinstance(validation_pattern_cache, dict):
                validation_pattern_cache[cache_key] = validation_pattern_stats
    except Exception:
        validation_pattern_stats = None
    primary_matches = matcher_tool.match_line(
        article_source=raw_text,
        fournisseur_hint=context.get("supplier"),
        metier_hint=context.get("metier_hint"),
        client_ape_hint=context.get("client_ape"),
        supplier_ape_hint=context.get("supplier_ape"),
        tva_hint=line_payload.get("tva"),
        top_n=3,
        include_charges=True,
        supplier_account_stats=supplier_account_stats,
        validation_pattern_stats=validation_pattern_stats,
    )
    broad_matches: list[dict[str, Any]] = []
    if context.get("metier_hint"):
        broad_matches = matcher_tool.match_line(
            article_source=raw_text,
            fournisseur_hint=context.get("supplier"),
            metier_hint=None,
            client_ape_hint=context.get("client_ape"),
            supplier_ape_hint=context.get("supplier_ape"),
            tva_hint=line_payload.get("tva"),
            top_n=3,
            include_charges=True,
            supplier_account_stats=supplier_account_stats,
            validation_pattern_stats=validation_pattern_stats,
        )
    top_matches = _merge_matches(primary_matches, broad_matches)

    hypothesis = _build_contextual_hypothesis(cleaned_text, context)
    referential_status = _score_to_referential_status(top_matches, hypothesis)
    top_match = top_matches[0] if top_matches else None
    decision = _decision_from_status(referential_status, top_match, hypothesis)

    top_candidates = [_to_top_candidate(candidate) for candidate in top_matches]
    if hypothesis and referential_status == "missing_candidate":
        top_candidates.insert(
            0,
            StrongTopCandidate(
                account=hypothesis.get("account"),
                account_label=hypothesis.get("account_label"),
                article_source=raw_text,
                article_canonique=cleaned_text,
                base=hypothesis.get("base"),
                score=float(hypothesis.get("score") or 0.0),
                reason=hypothesis.get("reason") or "",
                decision="validation_humaine",
                evidence_status="missing",
            ),
        )

    selected_candidate = top_candidates[0] if top_candidates else None
    if referential_status == "found_exact" and top_candidates:
        selected_candidate = top_candidates[0]
    elif referential_status == "found_fuzzy" and top_candidates:
        selected_candidate = top_candidates[0]
    elif referential_status == "missing_candidate" and top_candidates:
        selected_candidate = top_candidates[0]

    recommended_account = selected_candidate.account if selected_candidate else hypothesis.get("account") if hypothesis else None
    recommended_label = (
        selected_candidate.account_label
        if selected_candidate
        else hypothesis.get("account_label") if hypothesis else None
    )
    evidence_status = (
        selected_candidate.evidence_status if selected_candidate else "missing"
    )
    confidence = round(
        float(selected_candidate.score if selected_candidate else hypothesis.get("score") if hypothesis else 0.0),
        2,
    )
    if referential_status == "found_exact":
        confidence = max(confidence, 92.0)
    risk_level = _risk_from_decision(referential_status, confidence, decision, evidence_status)
    decision_reason = _build_decision_reason(
        referential_status,
        selected_candidate,
        hypothesis,
        context,
        decision,
    )
    quality_status = _quality_from_line(referential_status, evidence_status, decision)

    return StrongLineAnalysis(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        quantity=line_payload.get("quantity"),
        unit_price=line_payload.get("unit_price"),
        amount_ht=line_payload.get("amount_ht"),
        amount_ttc=line_payload.get("amount_ttc"),
        tva=line_payload.get("tva"),
        supplier=context.get("supplier"),
        client=context.get("client"),
        client_ape=context.get("client_ape"),
        supplier_ape=context.get("supplier_ape"),
        metier_hint=context.get("metier_hint"),
        detected_activity=selected_candidate.base if selected_candidate and selected_candidate.base else _infer_detected_activity(
            context.get("metier_hint"),
            context.get("client_ape"),
            context.get("supplier_ape"),
            context.get("supplier"),
            raw_text,
        ),
        referential_status=referential_status,
        recommended_account=recommended_account,
        recommended_account_label=recommended_label,
        confidence=confidence,
        risk_level=risk_level,
        decision=decision,
        decision_reason=decision_reason,
        evidence_status=evidence_status,
        quality_status=quality_status,
        source_invoice_ids=list(selected_candidate.source_invoice_ids if selected_candidate else []),
        invoice_paths_sources=list(selected_candidate.invoice_paths_sources if selected_candidate else []),
        partitions_sources=list(selected_candidate.partitions_sources if selected_candidate else []),
        ape_context=list(selected_candidate.ape_context if selected_candidate else []),
        taux_tva=selected_candidate.taux_tva if selected_candidate else None,
        categorie=selected_candidate.categorie if selected_candidate else None,
        sous_categorie=selected_candidate.sous_categorie if selected_candidate else None,
        type_fournisseur=selected_candidate.type_fournisseur if selected_candidate else None,
        top_candidates=top_candidates[:3],
        enrichment_suggestion=_build_enrichment_suggestion(
            referential_status,
            hypothesis,
            selected_candidate,
        ),
    )


def _build_invoice_header(
    context: dict[str, Any],
    invoice_meta: dict[str, Any],
    total_lines: int,
    exploitable_lines: int,
) -> StrongInvoiceHeader:
    return StrongInvoiceHeader(
        invoice_id=invoice_meta.get("invoice_id"),
        invoice_number=invoice_meta.get("invoice_number"),
        invoice_date=invoice_meta.get("invoice_date"),
        supplier=context.get("supplier"),
        client=context.get("client"),
        client_ape=context.get("client_ape"),
        supplier_ape=context.get("supplier_ape"),
        metier_hint=context.get("metier_hint"),
        currency=context.get("currency") or invoice_meta.get("currency") or "EUR",
        total_lines=total_lines,
        exploitable_lines=exploitable_lines,
        status="sans_lignes_exploitables" if exploitable_lines == 0 else "prete_a_analyser",
    )


def _build_summary(lines: list[StrongLineAnalysis]) -> StrongAnalysisSummary:
    total_lines = len(lines)
    auto_ok = sum(1 for line in lines if line.decision == "auto_ok")
    validation_humaine = sum(1 for line in lines if line.decision == "validation_humaine")
    rejeter = sum(1 for line in lines if line.decision == "rejeter")
    non_comptable = sum(1 for line in lines if line.decision == "non_comptable")
    unknown = sum(1 for line in lines if line.referential_status == "unknown")
    absent_referential = sum(
        1
        for line in lines
        if line.referential_status in {"missing_candidate", "unknown"}
    )
    average_confidence = round(
        sum(float(line.confidence or 0.0) for line in lines) / total_lines,
        2,
    ) if total_lines else 0.0
    return StrongAnalysisSummary(
        total_lines=total_lines,
        auto_ok=auto_ok,
        validation_humaine=validation_humaine,
        rejeter=rejeter,
        non_comptable=non_comptable,
        unknown=unknown,
        articles_absents_referentiel=absent_referential,
        average_confidence=average_confidence,
    )


def _build_accounting_proposal(
    invoice_header: StrongInvoiceHeader,
    lines: list[StrongLineAnalysis],
) -> AccountingProposal:
    """Build a structured accounting proposal from already-computed analysis lines.

    No scoring, matching or decision logic is touched here ? this is a pure
    projection of existing results into a bookkeeping-ready format.
    """
    proposal_lines: list[AccountingProposalLine] = []

    for idx, line in enumerate(lines):
        line_id = f"line_{idx + 1}"
        is_non_comptable = line.decision == "non_comptable"

        # --- can_auto_post ---
        can_auto_post = (
            not is_non_comptable
            and line.decision == "auto_ok"
            and line.referential_status == "found_exact"
            and line.evidence_status != "missing"
            and float(line.confidence or 0.0) >= 90.0
        )

        # --- requires_human_validation ---
        if is_non_comptable:
            requires_human_validation = False
        else:
            requires_human_validation = (
                line.decision == "validation_humaine"
                or line.referential_status != "found_exact"
                or line.evidence_status in ("missing", "partial")
                or line.risk_level in ("moyen", "eleve")
            )

        proposal_lines.append(AccountingProposalLine(
            line_id=line_id,
            raw_text=line.raw_text,
            cleaned_text=line.cleaned_text,
            amount_ht=line.amount_ht,
            amount_ttc=line.amount_ttc,
            tva=line.tva,
            recommended_account=None if is_non_comptable else line.recommended_account,
            account_label=None if is_non_comptable else line.recommended_account_label,
            confidence=float(line.confidence or 0.0),
            risk_level=line.risk_level,
            decision=line.decision,
            referential_status=line.referential_status,
            evidence_status=line.evidence_status,
            reason=line.decision_reason,
            can_auto_post=can_auto_post,
            requires_human_validation=requires_human_validation,
        ))

    # --- summary ---
    comptable_lines = [pl for pl in proposal_lines if pl.decision != "non_comptable"]
    total = len(proposal_lines)
    auto_ok_count = sum(1 for pl in proposal_lines if pl.decision == "auto_ok")
    validation_count = sum(1 for pl in proposal_lines if pl.decision == "validation_humaine")
    rejected_count = sum(1 for pl in proposal_lines if pl.decision == "rejeter")
    non_comptable_count = sum(1 for pl in proposal_lines if pl.decision == "non_comptable")
    avg_conf = round(
        sum(pl.confidence for pl in proposal_lines) / total, 2
    ) if total else 0.0

    # --- proposal_status ---
    if not comptable_lines:
        proposal_status: str = "rejected"
    elif all(pl.can_auto_post for pl in comptable_lines):
        proposal_status = "auto_ok"
    elif any(pl.requires_human_validation for pl in comptable_lines):
        proposal_status = "validation_required"
    elif all(pl.decision == "rejeter" for pl in comptable_lines):
        proposal_status = "rejected"
    else:
        proposal_status = "partial"

    return AccountingProposal(
        invoice_id=invoice_header.invoice_id,
        invoice_number=invoice_header.invoice_number,
        supplier=invoice_header.supplier,
        client=invoice_header.client,
        proposal_status=proposal_status,  # type: ignore[arg-type]
        summary=AccountingProposalSummary(
            total_lines=total,
            auto_ok=auto_ok_count,
            validation_humaine=validation_count,
            rejected=rejected_count,
            non_comptable=non_comptable_count,
            average_confidence=avg_conf,
        ),
        lines=proposal_lines,
    )


def analyze_invoice_lines_strong(
    invoice_doc_or_lines: dict[str, Any] | list[dict[str, Any]] | str,
    context: StrongAnalysisContext | dict[str, Any] | None = None,
) -> StrongAnalysisResponse:
    total_started = time.perf_counter()
    context_dict = _context_to_dict(context)
    line_payloads, working_context, invoice_meta, line_source = _build_line_payloads(invoice_doc_or_lines, context_dict)

    if not working_context.get("metier_hint"):
        working_context["metier_hint"] = _infer_detected_activity(
            working_context.get("metier_hint"),
            working_context.get("client_ape"),
            working_context.get("supplier_ape"),
            working_context.get("supplier"),
        )

    try:
        working_context["_supplier_account_stats"] = get_supplier_memory(
            fournisseur_hint=working_context.get("supplier"),
            metier_hint=working_context.get("metier_hint"),
        )
    except Exception:
        working_context["_supplier_account_stats"] = None
    working_context["_validation_pattern_cache"] = {}

    line_analysis_started = time.perf_counter()
    analyzed_lines: list[StrongLineAnalysis] = [None] * len(line_payloads)  # type: ignore[list-item]
    max_workers = 1 if len(line_payloads) <= 1 else min(6, max(2, len(line_payloads)))

    def analyze_one(idx: int, payload: dict[str, Any]) -> StrongLineAnalysis:
        try:
            return _analyze_single_line(payload, working_context)
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            print(
                f"[analysis/strong-lines] warning line_index={idx} raw_text={_text(payload.get('raw_text'))!r} "
                f"error={exc.__class__.__name__}: {exc}"
            )
            traceback.print_exc()
            return _failed_line_analysis(payload, working_context, exc)

    if max_workers == 1:
        analyzed_lines = [analyze_one(idx, payload) for idx, payload in enumerate(line_payloads)]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_one, idx, payload): idx
                for idx, payload in enumerate(line_payloads)
            }
            for future in as_completed(futures):
                idx = futures[future]
                analyzed_lines[idx] = future.result()

    line_analysis_ms = round((time.perf_counter() - line_analysis_started) * 1000, 2)
    exploitable_lines = sum(1 for line in analyzed_lines if line.decision != "non_comptable")

    invoice_header = _build_invoice_header(working_context, invoice_meta, len(line_payloads), exploitable_lines)
    proposal_started = time.perf_counter()
    accounting_proposal = _build_accounting_proposal(invoice_header, analyzed_lines)
    proposal_ms = round((time.perf_counter() - proposal_started) * 1000, 2)
    total_ms = round((time.perf_counter() - total_started) * 1000, 2)
    print(
        f"[analysis/strong-lines] source={line_source} line_count={len(line_payloads)} "
        f"workers={max_workers} line_analysis_ms={line_analysis_ms} "
        f"proposal_ms={proposal_ms} total_ms={total_ms}"
    )
    return StrongAnalysisResponse(
        invoice=invoice_header,
        summary=_build_summary(analyzed_lines),
        lines=analyzed_lines,
        accounting_proposal=accounting_proposal,
    )


def analyze_invoice_by_id(invoice_id: str) -> StrongAnalysisResponse:
    total_started = time.perf_counter()
    print(f"[analysis/strong-invoice] start invoice_id={invoice_id}")
    try:
        invoice_doc, db_name, fetch_ms = _fetch_invoice_doc_with_meta(invoice_id)
        line_items, line_source = _extract_invoice_line_items_with_source(invoice_doc)
        print(
            f"[analysis/strong-invoice] db={db_name} invoice_id={invoice_id} "
            f"fetch_ms={fetch_ms} found=yes doc_type={_text(invoice_doc.get('document_type') or _safe_dict(invoice_doc.get('invoice_form')).get('document_type'))} "
            f"p={_text(invoice_doc.get('p') or invoice_doc.get('type'))} "
            f"line_source={line_source} line_count={len(line_items)} "
            f"keys={sorted(list(invoice_doc.keys()))[:20]}"
        )
        analysis_started = time.perf_counter()
        response = analyze_invoice_lines_strong(invoice_doc)
        analysis_ms = round((time.perf_counter() - analysis_started) * 1000, 2)
        total_ms = round((time.perf_counter() - total_started) * 1000, 2)
        print(
            f"[analysis/strong-invoice] done invoice_id={invoice_id} db={db_name} "
            f"lines={response.summary.total_lines} analysis_ms={analysis_ms} total_ms={total_ms}"
        )
        return response
    except Exception as exc:
        total_ms = round((time.perf_counter() - total_started) * 1000, 2)
        print(
            f"[analysis/strong-invoice] error invoice_id={invoice_id} total_ms={total_ms} "
            f"error={exc.__class__.__name__}: {exc}"
        )
        traceback.print_exc()
        raise


def fetch_random_invoices(limit: int = 10) -> RandomInvoicesResponse:
    docs = _sample_random_invoice_docs(limit)
    items: list[RandomInvoiceListItem] = []

    for doc in docs:
        item, _ = _build_random_invoice_list_item(doc)
        items.append(item)

    return RandomInvoicesResponse(items=items)


def _pluralize_fr(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count <= 1 else plural}"


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _preview_from_line_items(line_items: list[dict[str, Any]]) -> str | None:
    preview_parts: list[str] = []
    module = _matcher_module()
    for line_item in line_items:
        text = _extract_description(line_item)
        if not text or module.is_non_article_line(text):
            continue
        preview_parts.append(text)
        if len(preview_parts) >= 2:
            break

    if not preview_parts:
        return None
    return ", ".join(preview_parts)


def _is_control_queue_invoice(doc: dict[str, Any]) -> bool:
    invoice_form = _safe_dict(doc.get("invoice_form"))
    raw_type = _text(doc.get("type") or doc.get("p")).lower()
    document_type = _text(
        doc.get("document_type")
        or invoice_form.get("document_type")
        or _safe_dict(doc.get("data")).get("document_type")
        or _safe_dict(doc.get("document")).get("document_type")
    ).lower()

    return bool(
        document_type == "invoice"
        or raw_type in {"invoice", "invoice_form"}
        or isinstance(doc.get("invoice_form"), dict)
    )


def _extract_queue_line_items(doc: dict[str, Any]) -> list[dict[str, Any]]:
    lines, _ = _extract_invoice_line_items_with_source(doc)
    return lines


def _normalize_control_queue_doc(doc: dict[str, Any]) -> dict[str, Any]:
    invoice_form = _safe_dict(doc.get("invoice_form"))
    data = _safe_dict(doc.get("data"))
    document = _safe_dict(doc.get("document"))

    normalized = {
        "_id": _text(doc.get("_id")) or _text(invoice_form.get("_id")),
        "p": _first_non_empty(doc.get("p"), doc.get("type"), invoice_form.get("p"), invoice_form.get("type")),
        "document_type": _first_non_empty(
            doc.get("document_type"),
            invoice_form.get("document_type"),
            data.get("document_type"),
            document.get("document_type"),
        ),
        "issuer": (
            _safe_dict(invoice_form.get("issuer"))
            or _safe_dict(doc.get("issuer"))
            or _safe_dict(document.get("issuer"))
            or _safe_dict(data.get("issuer"))
        ),
        "recipient": (
            _safe_dict(invoice_form.get("recipient"))
            or _safe_dict(doc.get("recipient"))
            or _safe_dict(document.get("recipient"))
            or _safe_dict(data.get("recipient"))
        ),
        "invoice_number": _first_non_empty(
            invoice_form.get("invoice_number"),
            doc.get("invoice_number"),
            doc.get("reference"),
            doc.get("number"),
            data.get("invoice_number"),
            document.get("invoice_number"),
        ),
        "invoice_date": _first_non_empty(
            invoice_form.get("invoice_date"),
            doc.get("invoice_date"),
            doc.get("date"),
            data.get("invoice_date"),
            document.get("invoice_date"),
        ),
        "supplier": _first_non_empty(
            invoice_form.get("supplier"),
            doc.get("supplier"),
            doc.get("supplier_name"),
            data.get("supplier"),
        ),
        "client": _first_non_empty(
            invoice_form.get("client"),
            doc.get("client"),
            doc.get("client_name"),
            data.get("client"),
        ),
        "client_ape": _first_non_empty(
            invoice_form.get("client_ape"),
            doc.get("client_ape"),
            doc.get("km_ape"),
            data.get("client_ape"),
        ),
        "supplier_ape": _first_non_empty(
            invoice_form.get("supplier_ape"),
            doc.get("supplier_ape"),
            data.get("supplier_ape"),
        ),
        "line_items": _extract_queue_line_items(doc),
        "summary": (
            _safe_dict(doc.get("analysis_summary"))
            or _safe_dict(doc.get("summary"))
            or _safe_dict(invoice_form.get("analysis_summary"))
            or _safe_dict(invoice_form.get("summary"))
            or _safe_dict(data.get("analysis_summary"))
        ),
        "analysis_lines": (
            doc.get("analysis_lines")
            or doc.get("analysis")
            or invoice_form.get("analysis_lines")
            or invoice_form.get("analysis")
            or []
        ),
        "has_pdf": (
            bool(_extract_pdf_path_from_doc(doc))
            or _doc_has_pdf_attachment(doc)
            # form_common_core_ref points to a core_profile which stores the PDF path;
            # we set has_pdf=True here to avoid an expensive extra CouchDB lookup per invoice.
            or bool(doc.get("form_common_core_ref"))
            or bool(invoice_form.get("form_common_core_ref"))
        ),
    }
    return normalized


def _queue_doc_matches_filters(
    normalized_doc: dict[str, Any],
    supplier_filter: str | None,
    client_filter: str | None,
    ape_filter: str | None,
) -> bool:
    context = _extract_context_from_invoice(
        normalized_doc,
        {
            "supplier": normalized_doc.get("supplier"),
            "client": normalized_doc.get("client"),
            "client_ape": normalized_doc.get("client_ape"),
            "supplier_ape": normalized_doc.get("supplier_ape"),
        },
    )
    supplier_query = _text(supplier_filter).lower()
    client_query = _text(client_filter).lower()
    ape_query = _normalize_ape(ape_filter)

    supplier_value = _text(context.get("supplier")).lower()
    client_value = _text(context.get("client")).lower()
    client_ape = _normalize_ape(context.get("client_ape"))
    supplier_ape = _normalize_ape(context.get("supplier_ape"))

    if supplier_query and supplier_query not in supplier_value:
        return False
    if client_query and client_query not in client_value:
        return False
    if ape_query and ape_query not in {client_ape, supplier_ape}:
        return False
    return True


def _coerce_control_queue_summary(mapping: dict[str, Any] | None) -> ControlQueueSummary | None:
    if not isinstance(mapping, dict):
        return None

    interesting_keys = {
        "auto_ok",
        "validation_humaine",
        "rejeter",
        "non_comptable",
        "missing_candidate",
        "unknown",
        "found_exact",
        "found_fuzzy",
        "average_confidence",
    }
    if not any(key in mapping for key in interesting_keys):
        return None

    return ControlQueueSummary(
        auto_ok=max(int(mapping.get("auto_ok") or 0), 0),
        validation_humaine=max(int(mapping.get("validation_humaine") or 0), 0),
        rejeter=max(int(mapping.get("rejeter") or 0), 0),
        non_comptable=max(int(mapping.get("non_comptable") or 0), 0),
        missing_candidate=max(int(mapping.get("missing_candidate") or 0), 0),
        unknown=max(int(mapping.get("unknown") or 0), 0),
        found_exact=max(int(mapping.get("found_exact") or 0), 0),
        found_fuzzy=max(int(mapping.get("found_fuzzy") or 0), 0),
        average_confidence=float(mapping.get("average_confidence") or 0.0),
    )


def _control_queue_summary_from_analysis_lines(lines: Any) -> ControlQueueSummary | None:
    if not isinstance(lines, list):
        return None

    summary = ControlQueueSummary()
    confidences: list[float] = []
    has_any_signal = False

    for line in lines:
        if not isinstance(line, dict):
            continue
        decision = _text(line.get("decision")).lower()
        referential_status = _text(line.get("referential_status")).lower()
        confidence = _safe_float(line.get("confidence"))

        if decision in {"auto_ok", "validation_humaine", "rejeter", "non_comptable"}:
            setattr(summary, decision, getattr(summary, decision) + 1)
            has_any_signal = True
        if referential_status in {"missing_candidate", "unknown", "found_exact", "found_fuzzy"}:
            setattr(summary, referential_status, getattr(summary, referential_status) + 1)
            has_any_signal = True
        if confidence is not None:
            confidences.append(float(confidence))

    if not has_any_signal:
        return None

    if confidences:
        summary.average_confidence = round(sum(confidences) / len(confidences), 2)
    return summary


def _extract_control_queue_summary(normalized_doc: dict[str, Any]) -> ControlQueueSummary | None:
    direct_summary = _coerce_control_queue_summary(normalized_doc.get("summary"))
    if direct_summary is not None:
        return direct_summary
    return _control_queue_summary_from_analysis_lines(normalized_doc.get("analysis_lines"))


def _queue_status_from_summary(
    line_count: int,
    summary: ControlQueueSummary | None,
) -> tuple[str, str]:
    if line_count <= 0:
        return "no_lines", "not_analyzed"
    if summary is None:
        return "not_analyzed", "not_analyzed"
    if summary.missing_candidate > 0 or summary.unknown > 0:
        return "new_articles", "analyzed"
    if summary.validation_humaine > 0 or summary.found_fuzzy > 0:
        return "to_control", "analyzed"
    if (
        summary.auto_ok > 0
        and summary.auto_ok >= line_count
        and summary.found_exact >= line_count
        and summary.validation_humaine == 0
        and summary.missing_candidate == 0
        and summary.unknown == 0
        and summary.found_fuzzy == 0
        and summary.rejeter == 0
    ):
        return "low_risk", "analyzed"
    return "not_analyzed", "analyzed"


def _queue_badges_from_item(
    queue_status: str,
    analysis_status: str,
    summary: ControlQueueSummary | None,
) -> list[str]:
    if queue_status == "no_lines":
        return ["Sans lignes"]
    if analysis_status != "analyzed" or summary is None:
        return ["Non analysee"]

    badges: list[str] = []
    if summary.validation_humaine > 0:
        badges.append(
            _pluralize_fr(summary.validation_humaine, "ligne a valider", "lignes a valider")
        )
    new_articles_total = summary.missing_candidate + summary.unknown
    if new_articles_total > 0:
        badges.append(
            _pluralize_fr(new_articles_total, "nouvel article", "nouveaux articles")
        )
    if not badges and queue_status == "low_risk":
        badges.append("Faible risque")
    if not badges:
        badges.append("Prete analyse")
    return badges


def _matches_requested_queue_status(item: ControlQueueItem, status: str | None) -> bool:
    selected = _text(status).lower() or "all"
    if selected in {"", "all"}:
        return True
    if selected == "not_analyzed":
        return item.queue_status == "not_analyzed"
    if selected == "to_control":
        return item.queue_status == "to_control"
    if selected == "new_articles":
        return item.queue_status == "new_articles"
    if selected == "low_risk":
        return item.queue_status == "low_risk"
    if selected == "no_lines":
        return item.queue_status == "no_lines"
    return True


def _count_control_queue_items(items: list[ControlQueueItem]) -> ControlQueueCounts:
    counts = ControlQueueCounts()
    counts.all = len(items)
    for item in items:
        if item.queue_status == "new_articles":
            counts.new_articles += 1
            counts.to_control += 1
        elif item.queue_status == "to_control":
            counts.to_control += 1
        elif item.queue_status == "low_risk":
            counts.low_risk += 1
        elif item.queue_status == "not_analyzed":
            counts.not_analyzed += 1
        elif item.queue_status == "no_lines":
            counts.high_risk += 1
    return counts


def _pdf_status_priority(value: str | None) -> int:
    return {
        "available": 0,
        "missing_file": 1,
        "no_path": 2,
        "inaccessible": 3,
        "unknown": 4,
    }.get(str(value or "unknown").strip().lower(), 4)


def _compute_queue_pdf_status(
    *,
    session: Any,
    db_name: str,
    invoice_doc: dict[str, Any],
) -> tuple[str, str, bool]:
    """Return a lightweight source-document availability status for queue cards."""
    if _doc_has_pdf_attachment(invoice_doc):
        return "available", "PDF disponible", True

    direct_raw_path, _field_used = _extract_pdf_path_from_doc_with_field(invoice_doc)
    if direct_raw_path:
        resolution = _describe_pdf_source_resolution(direct_raw_path)
        if resolution.get("resolved_path"):
            return "available", "PDF disponible", True
        if resolution.get("matched_prefix"):
            return "inaccessible", "Acces reseau KO", True
        return "missing_file", "PDF absent", True

    ref, _ref_field = _extract_form_common_core_ref(invoice_doc)
    if isinstance(ref, dict):
        core_doc = _fetch_core_profile_doc(session, db_name, invoice_doc)
        if isinstance(core_doc, dict):
            core_raw_path, _core_field, _core_error = _extract_pdf_path_from_core_profile(core_doc)
            if core_raw_path:
                resolution = _describe_pdf_source_resolution(core_raw_path)
                if resolution.get("resolved_path"):
                    return "available", "PDF disponible", True
                if resolution.get("matched_prefix"):
                    return "inaccessible", "Acces reseau KO", True
                return "missing_file", "PDF absent", True
        return "no_path", "Sans PDF", False

    return "no_path", "Aucun chemin PDF trouv?", False


def _build_control_queue_item(normalized_doc: dict[str, Any]) -> ControlQueueItem:
    line_items = normalized_doc.get("line_items") or []
    line_count = len(line_items)
    preview = _preview_from_line_items(line_items)
    context = _extract_context_from_invoice(
        normalized_doc,
        {
            "supplier": normalized_doc.get("supplier"),
            "client": normalized_doc.get("client"),
            "client_ape": normalized_doc.get("client_ape"),
            "supplier_ape": normalized_doc.get("supplier_ape"),
        },
    )
    summary = _extract_control_queue_summary(normalized_doc)
    queue_status, analysis_status = _queue_status_from_summary(line_count, summary)
    exploitable_lines = 0
    module = _matcher_module()
    for line_item in line_items:
        raw_text = _extract_description(line_item)
        if raw_text and not module.is_non_article_line(raw_text):
            exploitable_lines += 1

    return ControlQueueItem(
        id=_text(normalized_doc.get("_id")),
        supplier=context.get("supplier"),
        client=context.get("client"),
        date=_text(normalized_doc.get("invoice_date")) or None,
        invoice_number=_text(normalized_doc.get("invoice_number")) or None,
        line_count=line_count,
        exploitable_lines_count=exploitable_lines,
        client_ape=context.get("client_ape"),
        supplier_ape=context.get("supplier_ape"),
        analysis_status=analysis_status,
        queue_status=queue_status,
        summary=summary or ControlQueueSummary(),
        badges=_queue_badges_from_item(queue_status, analysis_status, summary),
        ready=line_count > 0,
        preview=preview,
        has_pdf=bool(normalized_doc.get("has_pdf")),
        pdf_status=_text(normalized_doc.get("pdf_status")) or "unknown",
        pdf_message=_text(normalized_doc.get("pdf_message")) or None,
    )


def _find_control_queue_docs(
    limit: int,
    supplier: str | None,
    client: str | None,
    ape: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    requested_limit = max(int(limit or 20), 1)
    search_limit = max(requested_limit * 8, 160)
    row_limit = max(search_limit * 4, 800)

    docs: list[dict[str, Any]] = []
    # Invoice docs live in partition-like ids such as fr_bd_310496013:<uuid>.
    # Starting there avoids scanning CouchDB design docs and keeps the queue fast.
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/_all_docs",
        params={
            "include_docs": "true",
            "startkey": json.dumps("fr_bd_000000000"),
            "limit": str(row_limit),
        },
        timeout=90,
    )
    if response.status_code == 404:
        raise RuntimeError("CouchDB indisponible ou mal configur?e.")
    response.raise_for_status()
    rows = response.json().get("rows") or []

    for row in rows:
        doc = row.get("doc")
        if not isinstance(doc, dict) or not _is_control_queue_invoice(doc):
            continue
        normalized_doc = _normalize_control_queue_doc(doc)
        if not _queue_doc_matches_filters(normalized_doc, supplier, client, ape):
            continue
        docs.append(doc)
        if len(docs) >= search_limit:
            break
    return db_name, docs


def fetch_analysis_control_queue(
    *,
    status: str | None = None,
    limit: int = 20,
    supplier: str | None = None,
    client: str | None = None,
    ape: str | None = None,
) -> ControlQueueResponse:
    try:
        db_name, docs = _find_control_queue_docs(limit, supplier, client, ape)
    except requests.RequestException as exc:
        raise RuntimeError("CouchDB indisponible ou mal configur?e.") from exc
    except RuntimeError as exc:
        if "CouchDB" in str(exc):
            raise RuntimeError("CouchDB indisponible ou mal configur?e.") from exc
        raise

    requested_limit = max(int(limit or 20), 1)
    base_items: list[ControlQueueItem] = []
    filtered_docs: list[dict[str, Any]] = []
    for doc in docs:
        normalized_doc = _normalize_control_queue_doc(doc)
        base_item = _build_control_queue_item(normalized_doc)
        base_items.append(base_item)
        if _matches_requested_queue_status(base_item, status):
            filtered_docs.append(doc)
            if len(filtered_docs) >= requested_limit:
                break

    counts = _count_control_queue_items(base_items)
    session = http_session()
    items: list[ControlQueueItem] = []
    for doc in filtered_docs:
        normalized_doc = _normalize_control_queue_doc(doc)
        pdf_status, pdf_message, has_pdf = _compute_queue_pdf_status(
            session=session,
            db_name=db_name,
            invoice_doc=doc,
        )
        normalized_doc["has_pdf"] = has_pdf
        normalized_doc["pdf_status"] = pdf_status
        normalized_doc["pdf_message"] = pdf_message
        items.append(_build_control_queue_item(normalized_doc))

    pdf_available_count = sum(1 for item in items if item.pdf_status == "available")
    pdf_missing_count = sum(1 for item in items if item.pdf_status != "available")

    return ControlQueueResponse(
        items=items,
        counts=counts,
        count=len(items),
        database=db_name,
        pdf_available_count=pdf_available_count,
        pdf_missing_count=pdf_missing_count,
    )


# ---------------------------------------------------------------------------
# PDF path resolution
# ---------------------------------------------------------------------------

import logging as _logging

_pdf_logger = _logging.getLogger(__name__)

_SOURCE_MEDIA_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# All top-level doc fields that may contain a local file path to a PDF
_PDF_TOP_FIELDS: tuple[str, ...] = (
    "pdf",
    "pdf_file",
    "pdfPath",
    "pdf_path",
    "path",
    "file",
    "file_path",
    "filename",
    "source",
    "source_path",
    "original_file",
    "original_path",
    "document_path",
    "document",
    "document_url",
    "attachment",
    "attachment_path",
    "invoice_path",
    "source_pdf_path",
    "original_pdf_path",
)

# Nested fields: (parent_key, child_key)
_PDF_NESTED_FIELDS: tuple[tuple[str, str], ...] = (
    ("invoice_form", "pdf"),
    ("invoice_form", "pdf_path"),
    ("invoice_form", "file_path"),
    ("invoice_form", "path"),
    ("invoice_form", "document_path"),
    ("invoice_form", "original_path"),
    ("invoice_form", "file"),
    ("invoice_form", "filename"),
    ("invoice_form", "source"),
    ("invoice_form", "source_path"),
    ("invoice_form", "invoice_path"),
    ("invoice_form", "source_pdf_path"),
    ("metadata", "pdf_path"),
    ("metadata", "file_path"),
    ("metadata", "document_path"),
    ("metadata", "original_path"),
    ("metadata", "pdf"),
    ("metadata", "filename"),
    ("metadata", "source"),
    ("metadata", "source_path"),
    ("data", "pdf"),
    ("data", "pdf_path"),
    ("data", "file_path"),
    ("data", "document_path"),
    ("data", "path"),
    ("document", "pdf"),
    ("document", "pdf_path"),
    ("document", "file_path"),
    ("document", "document_path"),
    ("document", "path"),
)

# List fields ? use first non-empty element only
_PDF_LIST_FIELDS: tuple[str, ...] = (
    "invoice_paths_sources",
    "pdf_sources",
    "documents_pdf",
    "source_pdf_paths",
)

_CORE_PROFILE_PATH_FIELDS: tuple[tuple[str, ...], ...] = (
    ("form_common_core", "ingest", "path"),
    ("form_common_core", "ingest", "origin_path"),
    ("form_common_core", "ingest", "origin_rel_dir"),
    ("form_common_core", "ingest", "file_path"),
    ("form_common_core", "ingest", "full_path"),
    ("form_common_core", "path"),
    ("form_common_core", "file_path"),
    ("ingest", "path"),
    ("ingest", "origin_path"),
    ("ingest", "file_path"),
    ("path",),
    ("file_path",),
    ("pdf_path",),
    ("document_path",),
)


def _looks_like_local_path(val: str) -> bool:
    """Return True when *val* looks like a local filesystem path (not a URL)."""
    if not val or len(val) < 4:
        return False
    v = val.strip()
    if v.startswith(("http://", "https://", "ftp://", "mailto:")):
        return False
    if _guess_media_type_from_name(v):
        return True
    return (
        v.startswith(("/", "./", "../"))
        or (len(v) >= 3 and v[1] == ":" and v[2] in "\\/")  # Windows C:\...
        or "/" in v
        or "\\" in v
    )


def _guess_media_type_from_name(name: str | None) -> str | None:
    from pathlib import Path as _Path

    if not name:
        return None
    suffix = _Path(str(name).strip()).suffix.lower()
    return _SOURCE_MEDIA_TYPES.get(suffix)


def _extract_nested_text(doc: dict[str, Any], *path: str) -> str:
    current: Any = doc
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return _text(current)


def _join_dir_and_filename(raw_dir: str, filename: str) -> str:
    normalised_dir = str(raw_dir or "").replace("\\", "/").rstrip("/")
    clean_name = str(filename or "").replace("\\", "/").split("/")[-1].strip()
    if not normalised_dir or not clean_name:
        return raw_dir
    return f"{normalised_dir}/{clean_name}"


def _extract_candidate_filename(doc: dict[str, Any]) -> tuple[str | None, str | None]:
    filename_fields: tuple[tuple[str, ...], ...] = (
        ("filename",),
        ("original_filename",),
        ("name",),
        ("file_name",),
        ("document_name",),
        ("form_common_core", "ingest", "filename"),
        ("form_common_core", "ingest", "original_filename"),
        ("form_common_core", "filename"),
        ("ingest", "filename"),
        ("ingest", "original_filename"),
    )
    for field_path in filename_fields:
        value = _extract_nested_text(doc, *field_path)
        if value:
            return value, ".".join(field_path)
    return None, None


def _extract_pdf_path_from_core_profile(
    core_doc: dict[str, Any]
) -> tuple[str | None, str | None, str | None]:
    """Extract the best available source path from a core_profile document."""
    fallback_error: str | None = None

    for field_path in _CORE_PROFILE_PATH_FIELDS:
        field_name = ".".join(field_path)
        value = _extract_nested_text(core_doc, *field_path)
        if not value:
            continue

        if field_name.endswith("origin_rel_dir"):
            filename, filename_field = _extract_candidate_filename(core_doc)
            if filename:
                return (
                    _join_dir_and_filename(value, filename),
                    f"{field_name}+{filename_field}",
                    None,
                )
            fallback_error = "Dossier source trouv? mais nom de fichier absent."
            continue

        if _looks_like_local_path(value):
            return value, field_name, None

    return None, None, fallback_error


def _extract_form_common_core_ref(
    invoice_doc: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    top_level_ref = invoice_doc.get("form_common_core_ref")
    if isinstance(top_level_ref, dict):
        return top_level_ref, "form_common_core_ref"

    nested_ref = _safe_dict(invoice_doc.get("invoice_form")).get("form_common_core_ref")
    if isinstance(nested_ref, dict):
        return nested_ref, "invoice_form.form_common_core_ref"

    return None, None


def _fetch_core_profile_doc(
    session: Any, db_name: str, invoice_doc: dict[str, Any]
) -> dict[str, Any] | None:
    """Follow form_common_core_ref.id and return the core_profile doc, or None."""
    ref, _ref_field = _extract_form_common_core_ref(invoice_doc)
    if not isinstance(ref, dict):
        return None
    ref_id = _text(ref.get("id"))
    if not ref_id:
        return None
    try:
        r = session.get(
            f"{COUCHDB_URL}/{quote(db_name, safe='')}/{quote(ref_id, safe='')}",
            timeout=30,
        )
        if r.status_code == 200:
            doc = r.json()
            if isinstance(doc, dict):
                return doc
    except Exception:
        pass
    return None


def _iter_related_doc_ids(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        text = _text(value)
        if text:
            yield text
        return

    if isinstance(value, dict):
        for key in ("id", "_id", "doc_id", "entry_id", "ref", "value"):
            nested = value.get(key)
            if nested is not None:
                yield from _iter_related_doc_ids(nested)
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_related_doc_ids(item)


def _extract_related_doc_refs(invoice_doc: dict[str, Any]) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    seen: set[str] = set()
    current_invoice_id = _text(invoice_doc.get("_id"))

    candidates: tuple[tuple[str, Any], ...] = (
        ("entry_ids", invoice_doc.get("entry_ids")),
        ("invoice_form.entry_ids", _safe_dict(invoice_doc.get("invoice_form")).get("entry_ids")),
        ("metadata.entry_ids", _safe_dict(invoice_doc.get("metadata")).get("entry_ids")),
        ("workflow.entry_ids", _safe_dict(invoice_doc.get("workflow")).get("entry_ids")),
        ("data.entry_ids", _safe_dict(invoice_doc.get("data")).get("entry_ids")),
        ("document.entry_ids", _safe_dict(invoice_doc.get("document")).get("entry_ids")),
    )

    for label, raw_value in candidates:
        if raw_value is None:
            continue
        for doc_id in _iter_related_doc_ids(raw_value):
            if not doc_id or doc_id == current_invoice_id or doc_id in seen:
                continue
            seen.add(doc_id)
            refs.append((label, doc_id))
    return refs


def _fetch_doc_by_id(session: Any, db_name: str, doc_id: str) -> dict[str, Any] | None:
    safe_doc_id = quote(str(doc_id).strip(), safe="")
    try:
        response = session.get(
            f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_doc_id}",
            timeout=30,
        )
        if response.status_code == 200:
            doc = response.json()
            if isinstance(doc, dict):
                return doc
    except Exception:
        pass
    return None


def _resolve_source_from_doc(
    *,
    session: Any,
    db_name: str,
    doc: dict[str, Any],
    doc_id: str,
    invoice_id: str,
    source_label: str,
) -> tuple[tuple[str, Any] | None, dict[str, Any]]:
    debug: dict[str, Any] = {
        "doc_id": doc_id,
        "source_label": source_label,
        "path_field": None,
        "raw_path_preview": None,
        "resolved_pdf_path_preview": None,
        "exists_on_disk": False,
        "attachment_names": [],
        "used_attachment": None,
    }

    raw_path, field_used = _extract_pdf_path_from_doc_with_field(doc)
    extractor_used = "direct"
    error_reason: str | None = None
    if not raw_path:
        core_raw_path, core_field, core_error_reason = _extract_pdf_path_from_core_profile(doc)
        if core_raw_path:
            raw_path = core_raw_path
            field_used = core_field
            extractor_used = "core_profile"
        elif core_error_reason:
            error_reason = core_error_reason

    if raw_path:
        resolution = _describe_pdf_source_resolution(raw_path)
        if not error_reason and not resolution.get("resolved_path"):
            error_reason = (
                "Chemin source detecte mais inaccessible depuis le backend "
                f"({_mask_path(raw_path)})."
            )
        debug.update(
            {
                "path_field": field_used,
                "path_extractor": extractor_used,
                "raw_path_preview": _mask_path(raw_path),
                "resolved_pdf_path_preview": resolution.get("resolved_pdf_path_preview"),
                "exists_on_disk": bool(resolution.get("exists_on_disk")),
                "error_reason": error_reason,
            }
        )
        if resolution.get("resolved_path"):
            resolved_path = str(resolution["resolved_path"])
            filename = Path(resolved_path).name or Path(str(raw_path)).name or f"facture_{invoice_id}"
            media_type = _guess_media_type_from_name(filename) or "application/octet-stream"
            return (
                "disk",
                {
                    "path": resolved_path,
                    "media_type": media_type,
                    "filename": filename,
                },
            ), debug

    attachments = list(_iter_source_attachments(doc))
    debug["attachment_names"] = [att_name for att_name, _att_meta, _media_type in attachments]
    if attachments:
        att_name, _att_meta, media_type = attachments[0]
        debug["used_attachment"] = att_name
        safe_doc_id = quote(str(doc_id).strip(), safe="")
        att_url = (
            f"{COUCHDB_URL}/{quote(db_name, safe='')}"
            f"/{safe_doc_id}/{quote(att_name, safe='')}"
        )
        return ("couch_attachment", (session, att_url, att_name, media_type)), debug

    return None, debug


def _extract_pdf_path_from_doc(doc: dict[str, Any]) -> str | None:
    """Return the first plausible local PDF path found in *doc*, or None."""
    path, _field = _extract_pdf_path_from_doc_with_field(doc)
    return path


def _extract_pdf_path_from_doc_with_field(
    doc: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Return the first plausible local source path found in *doc* with its field."""
    for field in _PDF_TOP_FIELDS:
        val = _text(doc.get(field))
        if val and _looks_like_local_path(val):
            return val, field
    for parent_key, child_key in _PDF_NESTED_FIELDS:
        parent = _safe_dict(doc.get(parent_key))
        val = _text(parent.get(child_key))
        if val and _looks_like_local_path(val):
            return val, f"{parent_key}.{child_key}"
    for list_field in _PDF_LIST_FIELDS:
        items = doc.get(list_field)
        if items and isinstance(items, list):
            val = _text(items[0])
            if val and _looks_like_local_path(val):
                return val, f"{list_field}[0]"
    return None, None


def _iter_source_attachments(doc: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any], str]]:
    """Yield supported source document attachments with a media type."""
    attachments = doc.get("_attachments")
    if not isinstance(attachments, dict):
        return
    for att_name, att_meta in attachments.items():
        if not isinstance(att_meta, dict):
            continue
        ct = str(att_meta.get("content_type") or "").lower()
        media_type = ct or (_guess_media_type_from_name(att_name) or "")
        if media_type in _SOURCE_MEDIA_TYPES.values():
            yield att_name, att_meta, media_type


def _doc_has_pdf_attachment(doc: dict[str, Any]) -> bool:
    """Return True if the doc has at least one CouchDB source document attachment stub."""
    return any(True for _ in _iter_source_attachments(doc))
    return False


def _mask_path(path: str) -> str:
    """Return a safe preview showing only the last 2 path components."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if len(parts) <= 2:
        return path
    return ".../" + "/".join(parts[-2:])


def _extract_all_pdf_candidates(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all PDF path candidates found in *doc* for diagnostic purposes."""
    from pathlib import Path as _Path

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []

    def _add(field: str, val: str) -> None:
        if not val or field in seen:
            return
        seen.add(field)
        try:
            exists = _Path(val).is_file()
        except (OSError, ValueError):
            exists = False
        candidates.append({
            "field": field,
            "value_preview": _mask_path(val),
            "exists_on_disk": exists,
        })

    for field in _PDF_TOP_FIELDS:
        val = _text(doc.get(field))
        if val:
            _add(field, val)
    for parent_key, child_key in _PDF_NESTED_FIELDS:
        parent = _safe_dict(doc.get(parent_key))
        val = _text(parent.get(child_key))
        if val:
            _add(f"{parent_key}.{child_key}", val)
    for list_field in _PDF_LIST_FIELDS:
        items = doc.get(list_field)
        if items and isinstance(items, list):
            val = _text(items[0])
            if val:
                _add(f"{list_field}[0]", val)
    # Catch any remaining top-level key that looks path-like
    for key, raw_val in doc.items():
        if key.startswith("_") or key in _PDF_TOP_FIELDS:
            continue
        if isinstance(raw_val, (dict, list)):
            continue
        val = _text(raw_val)
        if val and _looks_like_local_path(val):
            _add(f"(other){key}", val)
    return candidates


def _preview_prefix(raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    normalised = str(raw_path).replace("\\", "/").strip()
    if not normalised:
        return None
    if len(normalised) >= 3 and normalised[1] == ":" and normalised[2] == "/":
        return normalised[:3]
    if normalised.startswith("//"):
        parts = [part for part in normalised.split("/") if part]
        return "//" + "/".join(parts[:2]) if parts else "//"
    if normalised.startswith("/"):
        parts = [part for part in normalised.split("/") if part]
        if not parts:
            return "/"
        return "/" + "/".join(parts[: min(3, len(parts))])
    return normalised.split("/")[0]


def _nearest_existing_parent(path_value: str | None) -> str | None:
    from pathlib import Path as _Path

    if not path_value:
        return None
    try:
        current = _Path(str(path_value))
    except (OSError, ValueError):
        return None

    seen: set[str] = set()
    while True:
        key = str(current)
        if key in seen:
            return None
        seen.add(key)
        try:
            if current.exists():
                return str(current)
        except (OSError, ValueError):
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _can_list_directory(path_value: str | None) -> tuple[bool, list[str]]:
    from pathlib import Path as _Path

    if not path_value:
        return False, []
    try:
        path_obj = _Path(str(path_value))
        if not path_obj.exists() or not path_obj.is_dir():
            return False, []
        sample = [entry.name for entry in list(path_obj.iterdir())[:5]]
        return True, sample
    except (OSError, ValueError, PermissionError):
        return False, []


def _list_directory_names(path_value: str | None, limit: int = 10) -> list[str]:
    from pathlib import Path as _Path

    if not path_value:
        return []
    try:
        path_obj = _Path(str(path_value))
        if not path_obj.exists() or not path_obj.is_dir():
            return []
        names: list[str] = []
        for entry in path_obj.iterdir():
            names.append(entry.name)
            if len(names) >= max(1, limit):
                break
        return names
    except (OSError, ValueError, PermissionError):
        return []


def _normalize_name_for_match(value: str | None) -> str:
    import unicodedata

    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


def _debug_storage_path(path_value: str | None) -> dict[str, Any]:
    from pathlib import Path as _Path

    path_text = str(path_value or "").strip()
    exists = False
    is_dir = False
    nearest_existing_parent = None
    if path_text:
        try:
            path_obj = _Path(path_text)
            exists = path_obj.exists()
            is_dir = path_obj.is_dir() if exists else False
            nearest_existing_parent = _nearest_existing_parent(path_text)
        except (OSError, ValueError):
            pass
    can_list, sample_files = _can_list_directory(path_text)
    return {
        "path": path_text,
        "exists": exists,
        "is_dir": is_dir,
        "can_list": can_list,
        "sample_files": sample_files,
        "nearest_existing_parent": nearest_existing_parent,
    }


def _guess_runtime_context() -> str:
    if os.getenv("WSL_DISTRO_NAME"):
        return "wsl"
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER"):
        return "docker"
    if os.name == "nt":
        session_name = str(os.getenv("SESSIONNAME") or "").strip().lower()
        if session_name.startswith("service"):
            return "windows-service"
        return "windows-terminal"
    return "unknown"


def debug_pdf_storage() -> dict[str, Any]:
    mappings = _get_pdf_path_mappings()
    tested_paths = [
        "Z:/e",
        "Z:/",
        r"Z:\e",
        r"Z:\e\fichiers_pdf_paris",
        "Z:/e/fichiers_pdf_paris",
        "E:/fichiers_pdf_paris",
    ]

    for _linux_prefix, windows_prefix in mappings:
        if windows_prefix and windows_prefix not in tested_paths:
            tested_paths.append(windows_prefix)
        if windows_prefix:
            nested = windows_prefix.rstrip("/\\") + "/fichiers_pdf_paris"
            if nested not in tested_paths:
                tested_paths.append(nested)
        if windows_prefix.startswith("//") or windows_prefix.startswith("\\\\"):
            if windows_prefix not in tested_paths:
                tested_paths.append(windows_prefix)

    return {
        "cwd": os.getcwd(),
        "python_user": getuser(),
        "os_name": os.name,
        "platform": platform.platform(),
        "python_executable": sys.executable,
        "runtime_context": _guess_runtime_context(),
        "drive_z_visible": _debug_storage_path("Z:/").get("exists", False),
        "env_pdf_path_mappings": os.getenv("PDF_PATH_MAPPINGS", "").strip(),
        "tested_paths": [_debug_storage_path(path_value) for path_value in tested_paths],
    }


def _describe_pdf_source_resolution(raw_path: str | None) -> dict[str, Any]:
    """Describe how a raw source path resolves with the configured mappings."""
    from pathlib import Path as _Path

    description = {
        "matched_prefix": None,
        "resolved_pdf_path_preview": None,
        "exists_on_disk": False,
        "resolved_path": None,
        "unknown_prefix": False,
        "raw_prefix_preview": _preview_prefix(raw_path),
        "file_extension": None,
        "parent_exists": False,
        "nearest_existing_parent": None,
        "checked_path_variants": [],
        "backend_can_access_drive_z": _debug_storage_path("Z:/").get("exists", False),
    }
    if not raw_path:
        return description

    description["file_extension"] = _Path(str(raw_path).strip()).suffix.lower() or None
    mappings = _get_pdf_path_mappings()
    normalised = str(raw_path).replace("\\", "/")
    allowed_roots = {win.rstrip("/") for _, win in mappings}
    matched_mapping = False

    for linux_prefix, win_prefix in mappings:
        if not normalised.startswith(linux_prefix):
            continue
        matched_mapping = True
        description["matched_prefix"] = linux_prefix
        suffix = normalised[len(linux_prefix):]
        candidate_str = win_prefix.rstrip("/") + suffix
        description["resolved_pdf_path_preview"] = _mask_path(candidate_str)
        description["checked_path_variants"].append(
            {
                "path": candidate_str,
                "source": f"mapping:{linux_prefix}",
            }
        )
        candidate_normalised = candidate_str.replace("\\", "/")
        root_ok = any(
            candidate_normalised.startswith(root.replace("\\", "/").rstrip("/") + "/")
            or candidate_normalised == root.replace("\\", "/")
            for root in allowed_roots
        )
        if not root_ok:
            nearest_parent = _nearest_existing_parent(candidate_str)
            description["nearest_existing_parent"] = nearest_parent
            description["parent_exists"] = bool(nearest_parent)
            return description
        try:
            candidate = _Path(candidate_str)
            if candidate.is_file():
                description["exists_on_disk"] = True
                description["resolved_path"] = str(candidate)
        except (OSError, ValueError):
            pass
        nearest_parent = _nearest_existing_parent(candidate_str)
        description["nearest_existing_parent"] = nearest_parent
        description["parent_exists"] = bool(nearest_parent)
        return description

    is_direct_windows_path = (
        len(normalised) >= 3 and normalised[1] == ":" and normalised[2] == "/"
    ) or normalised.startswith("//")
    if not matched_mapping and not is_direct_windows_path:
        description["unknown_prefix"] = True

    try:
        direct = _Path(str(raw_path))
        description["resolved_pdf_path_preview"] = _mask_path(str(direct))
        description["checked_path_variants"].append(
            {
                "path": str(direct),
                "source": "direct",
            }
        )
        if direct.is_file():
            description["exists_on_disk"] = True
            description["resolved_path"] = str(direct)
            if is_direct_windows_path:
                description["matched_prefix"] = "(direct-windows-path)"
    except (OSError, ValueError):
        if description["resolved_pdf_path_preview"] is None:
            description["resolved_pdf_path_preview"] = _mask_path(str(raw_path))
    nearest_parent = _nearest_existing_parent(str(raw_path))
    description["nearest_existing_parent"] = nearest_parent
    description["parent_exists"] = bool(nearest_parent)

    return description


def _get_pdf_path_mappings() -> list[tuple[str, str]]:
    """Parse PDF_PATH_MAPPINGS env var into a list of (linux_prefix, windows_prefix) pairs.

    Format:  /root/windows/e=Z:/e;/mnt/clients/e=Z:/e
    Falls back to PDF_LINUX_PREFIX / PDF_WINDOWS_PREFIX if PDF_PATH_MAPPINGS is not set.
    """
    import os
    raw = os.getenv("PDF_PATH_MAPPINGS", "").strip()
    if raw:
        mappings: list[tuple[str, str]] = []
        for pair in raw.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            linux_part, win_part = pair.split("=", 1)
            linux_part = linux_part.strip()
            win_part = win_part.strip()
            if linux_part and win_part:
                mappings.append((linux_part, win_part))
        if mappings:
            return mappings
    # Legacy fallback
    linux_prefix = os.getenv("PDF_LINUX_PREFIX", "").strip()
    windows_prefix = os.getenv("PDF_WINDOWS_PREFIX", "").strip()
    if linux_prefix and windows_prefix:
        return [(linux_prefix, windows_prefix)]
    return []


def _resolve_pdf_path_with_mappings(raw_path: str) -> "Path | None":
    """Apply PDF_PATH_MAPPINGS to *raw_path* and return a Path if the file exists.

    - Normalises forward-slashes
    - Tries all (linux_prefix ? windows_prefix) substitutions in order
    - Returns the first Path whose .is_file() is True
    - Returns None if no mapping matches or file not found
    """
    from pathlib import Path as _Path

    if not raw_path:
        return None

    normalised = raw_path.replace("\\", "/")
    mappings = _get_pdf_path_mappings()

    # Security: keep a set of allowed Windows root prefixes to block traversal
    allowed_roots = {win.rstrip("/") for _, win in mappings}

    for linux_prefix, win_prefix in mappings:
        if normalised.startswith(linux_prefix):
            suffix = normalised[len(linux_prefix):]
            candidate_str = win_prefix.rstrip("/") + suffix
            # Security: verify the candidate string (pre-resolve) stays inside the
            # allowed Windows prefix ? covers traversal attempts like /../ sequences.
            # We use the raw candidate_str, not Path.resolve(), because resolve() on
            # a mapped network drive (Z:) may return a UNC path that no longer starts
            # with "Z:/e", causing a false-negative security block.
            candidate_normalised = candidate_str.replace("\\", "/")
            root_ok = any(
                candidate_normalised.startswith(r.replace("\\", "/").rstrip("/") + "/")
                or candidate_normalised == r.replace("\\", "/")
                for r in allowed_roots
            )
            if not root_ok:
                _pdf_logger.warning(
                    "[PDF] Path traversal blocked for: %s", _mask_path(candidate_str)
                )
                continue
            try:
                candidate = _Path(candidate_str)
                if candidate.is_file():
                    return candidate
            except (OSError, ValueError):
                continue

    # Also try the raw_path directly (e.g., already a Windows path stored in CouchDB)
    try:
        direct = _Path(raw_path)
        if allowed_roots:
            direct_normalised = raw_path.replace("\\", "/")
            root_ok = any(
                direct_normalised.startswith(r.replace("\\", "/").rstrip("/") + "/")
                for r in allowed_roots
            )
            if root_ok and direct.is_file():
                return direct
        elif direct.is_file():
            return direct
    except (OSError, ValueError):
        pass

    return None


def resolve_invoice_pdf(invoice_id: str) -> tuple[str, Any]:
    """Resolve the source document for a CouchDB invoice.

    Returns one of:
    - ``("disk", {...})`` ? local file on disk
    - ``("couch_attachment", (...))`` ? stream from CouchDB

    Raises ``FileNotFoundError`` with a safe human-readable message on failure.
    Path mapping is driven by PDF_PATH_MAPPINGS (or PDF_LINUX_PREFIX/PDF_WINDOWS_PREFIX).
    """
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        raise FileNotFoundError("PDF source introuvable pour cette facture.")
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        raise FileNotFoundError("Document source introuvable pour cette facture.")

    # 1 ? Try local path fields directly in the invoice doc
    raw_path, field_used = _extract_pdf_path_from_doc_with_field(doc)
    if raw_path:
        resolution = _describe_pdf_source_resolution(raw_path)
        if resolution.get("resolved_path"):
            resolved_path = str(resolution["resolved_path"])
            filename = Path(resolved_path).name or Path(str(raw_path)).name or f"facture_{invoice_id}"
            media_type = _guess_media_type_from_name(filename) or "application/octet-stream"
            return (
                "disk",
                {
                    "path": resolved_path,
                    "media_type": media_type,
                    "filename": filename,
                },
            )
        _pdf_logger.warning(
            "[PDF] invoice_id=%s: direct path field=%s found but absent on disk. masked=%s",
            invoice_id, field_used, _mask_path(raw_path),
        )

    # 1b ? Follow form_common_core_ref ? core_profile
    core_doc = _fetch_core_profile_doc(session, db_name, doc)
    core_error_reason: str | None = None
    if core_doc is not None:
        core_raw_path, core_field, core_error_reason = _extract_pdf_path_from_core_profile(core_doc)
        if core_raw_path:
            resolution = _describe_pdf_source_resolution(core_raw_path)
            if resolution.get("resolved_path"):
                resolved_path = str(resolution["resolved_path"])
                filename = Path(resolved_path).name or Path(str(core_raw_path)).name or f"facture_{invoice_id}"
                media_type = _guess_media_type_from_name(filename) or "application/octet-stream"
                _pdf_logger.info(
                    "[PDF] invoice_id=%s: resolved via core_profile field=%s",
                    invoice_id, core_field,
                )
                return (
                    "disk",
                    {
                        "path": resolved_path,
                        "media_type": media_type,
                        "filename": filename,
                    },
                )
            _pdf_logger.warning(
                "[PDF] invoice_id=%s: core_profile path found (field=%s) but absent on disk. masked=%s",
                invoice_id, core_field, _mask_path(core_raw_path),
            )
        elif core_error_reason:
            _pdf_logger.warning(
                "[PDF] invoice_id=%s: core_profile partial source info. reason=%s",
                invoice_id,
                core_error_reason,
            )

        # Also check core_profile _attachments
        for att_name, _att_meta, media_type in _iter_source_attachments(core_doc):
            core_safe_id = quote(str(core_doc.get("_id", "")).strip(), safe="")
            att_url = (
                f"{COUCHDB_URL}/{quote(db_name, safe='')}"
                f"/{core_safe_id}/{quote(att_name, safe='')}"
            )
            return ("couch_attachment", (session, att_url, att_name, media_type))

    # 2 ? Try CouchDB _attachments stubs on the invoice doc itself
    for att_name, _att_meta, media_type in _iter_source_attachments(doc):
        att_url = (
            f"{COUCHDB_URL}/{quote(db_name, safe='')}"
            f"/{safe_id}/{quote(att_name, safe='')}"
        )
        return ("couch_attachment", (session, att_url, att_name, media_type))

    # Diagnostic log
    doc_top_keys = [k for k in doc.keys() if not k.startswith("_")]
    ref, ref_field = _extract_form_common_core_ref(doc)
    _pdf_logger.warning(
        "[PDF] invoice_id=%s: no source document found. "
        "top_keys=%s | form_common_core_ref_field=%s | form_common_core_ref=%s",
        invoice_id, doc_top_keys, ref_field, ref,
    )
    raise FileNotFoundError(core_error_reason or "Document source introuvable pour cette facture.")


def debug_invoice_pdf(invoice_id: str) -> dict[str, Any]:
    """Return a diagnostic dict for the invoice's source-document resolution."""
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        return {"invoice_id": invoice_id, "error": "Document introuvable dans CouchDB."}
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        return {"invoice_id": invoice_id, "error": "Document non valide."}

    invoice_form = _safe_dict(doc.get("invoice_form"))
    invoice_form_found = bool(invoice_form)
    ref, ref_field = _extract_form_common_core_ref(doc)
    form_common_core_ref_present = isinstance(ref, dict)
    form_common_core_ref_id = _text(ref.get("id")) if isinstance(ref, dict) else None

    raw_attachments = doc.get("_attachments") or {}
    attachment_entries = [
        {
            "name": att_name,
            "content_type": str(_safe_dict(att_meta).get("content_type") or ""),
            "length": int(_safe_dict(att_meta).get("length") or 0),
            "media_type": (
                str(_safe_dict(att_meta).get("content_type") or "").lower()
                or (_guess_media_type_from_name(att_name) or "")
            ),
        }
        for att_name, att_meta in (raw_attachments.items() if isinstance(raw_attachments, dict) else [])
    ]

    # 1. Direct fields in invoice doc
    raw_path, direct_field = _extract_pdf_path_from_doc_with_field(doc)
    field_used: str | None = direct_field
    matched_prefix: str | None = None
    resolved_preview: str | None = None
    exists_on_disk = False
    file_extension: str | None = None
    core_profile_id: str | None = form_common_core_ref_id
    unknown_prefix = False
    raw_prefix_preview = _preview_prefix(raw_path)
    error_reason: str | None = None
    selected_resolution: dict[str, Any] = _describe_pdf_source_resolution(raw_path) if raw_path else {}

    if raw_path:
        direct_resolution = selected_resolution
        matched_prefix = direct_resolution.get("matched_prefix")
        resolved_preview = direct_resolution.get("resolved_pdf_path_preview")
        exists_on_disk = bool(direct_resolution.get("exists_on_disk"))
        file_extension = direct_resolution.get("file_extension")
        unknown_prefix = bool(direct_resolution.get("unknown_prefix"))
        raw_prefix_preview = direct_resolution.get("raw_prefix_preview")

    # 2. Follow core_profile ref
    core_raw_path: str | None = None
    core_field: str | None = None
    core_profile_found = False
    core_file_extension: str | None = None
    if core_profile_id:
        try:
            r2 = session.get(
                f"{COUCHDB_URL}/{quote(db_name, safe='')}/{quote(core_profile_id, safe='')}",
                timeout=20,
            )
            if r2.status_code == 200:
                core_doc = r2.json()
                if isinstance(core_doc, dict):
                    core_profile_found = True
                    core_raw_path, core_field, error_reason = _extract_pdf_path_from_core_profile(core_doc)
        except Exception:
            pass

    if core_raw_path:
        core_resolution = _describe_pdf_source_resolution(core_raw_path)
        core_file_extension = core_resolution.get("file_extension")
        if not field_used or not exists_on_disk or core_resolution.get("exists_on_disk"):
            raw_path = core_raw_path
            field_used = core_field
            selected_resolution = core_resolution
            matched_prefix = core_resolution.get("matched_prefix")
            resolved_preview = core_resolution.get("resolved_pdf_path_preview")
            exists_on_disk = bool(core_resolution.get("exists_on_disk"))
            file_extension = core_resolution.get("file_extension")
            unknown_prefix = bool(core_resolution.get("unknown_prefix"))
            raw_prefix_preview = core_resolution.get("raw_prefix_preview")

    if not file_extension and core_file_extension:
        file_extension = core_file_extension

    return {
        "invoice_id": invoice_id,
        "invoice_form_found": invoice_form_found,
        "form_common_core_ref_present": form_common_core_ref_present,
        "form_common_core_ref_field": ref_field,
        "form_common_core_ref_id": form_common_core_ref_id,
        "core_profile_found": core_profile_found,
        "raw_pdf_path": raw_path,
        "field_used": field_used,
        "core_profile_id": core_profile_id,
        "core_profile_raw_path": core_raw_path,
        "matched_prefix": matched_prefix,
        "resolved_pdf_path_preview": resolved_preview,
        "exists_on_disk": exists_on_disk,
        "file_extension": file_extension,
        "unknown_prefix": unknown_prefix,
        "raw_prefix_preview": raw_prefix_preview,
        "parent_exists": bool(selected_resolution.get("parent_exists")),
        "nearest_existing_parent": selected_resolution.get("nearest_existing_parent"),
        "expected_parent_preview": selected_resolution.get("expected_parent_preview"),
        "nearest_existing_parent_files": selected_resolution.get("nearest_existing_parent_files") or [],
        "expected_filename": selected_resolution.get("expected_filename"),
        "filename_close_matches": selected_resolution.get("filename_close_matches") or [],
        "checked_path_variants": selected_resolution.get("checked_path_variants") or [],
        "backend_can_access_drive_z": bool(selected_resolution.get("backend_can_access_drive_z")),
        "error_reason": error_reason,
        "found_pdf_candidates": _extract_all_pdf_candidates(doc),
        "top_level_keys": [k for k in doc.keys() if not k.startswith("_")],
        "invoice_form_keys": list(invoice_form.keys()),
        "metadata_keys": list(_safe_dict(doc.get("metadata")).keys()),
        "attachments": attachment_entries,
    }


def _override_resolve_source_from_doc(
    *,
    session: Any,
    db_name: str,
    doc: dict[str, Any],
    doc_id: str,
    invoice_id: str,
    source_label: str,
) -> tuple[tuple[str, Any] | None, dict[str, Any]]:
    debug: dict[str, Any] = {
        "doc_id": doc_id,
        "source_label": source_label,
        "path_field": None,
        "path_extractor": None,
        "raw_path": None,
        "raw_path_preview": None,
        "resolved_pdf_path_preview": None,
        "exists_on_disk": False,
        "attachment_names": [],
        "used_attachment": None,
        "error_reason": None,
    }

    raw_path, field_used = _extract_pdf_path_from_doc_with_field(doc)
    extractor_used = "direct"
    error_reason: str | None = None
    if not raw_path:
        core_raw_path, core_field, core_error_reason = _extract_pdf_path_from_core_profile(doc)
        if core_raw_path:
            raw_path = core_raw_path
            field_used = core_field
            extractor_used = "core_profile"
        elif core_error_reason:
            error_reason = core_error_reason

    if raw_path:
        resolution = _describe_pdf_source_resolution(raw_path)
        if not error_reason and not resolution.get("resolved_path"):
            error_reason = (
                "Chemin source detecte mais inaccessible depuis le backend "
                f"({_mask_path(raw_path)})."
            )
        debug.update(
            {
                "path_field": field_used,
                "path_extractor": extractor_used,
                "raw_path": str(raw_path),
                "raw_path_preview": _mask_path(raw_path),
                "resolved_pdf_path_preview": resolution.get("resolved_pdf_path_preview"),
                "exists_on_disk": bool(resolution.get("exists_on_disk")),
                "error_reason": error_reason,
            }
        )
        if resolution.get("resolved_path"):
            resolved_path = str(resolution["resolved_path"])
            filename = Path(resolved_path).name or Path(str(raw_path)).name or f"facture_{invoice_id}"
            media_type = _guess_media_type_from_name(filename) or "application/octet-stream"
            return (
                "disk",
                {
                    "path": resolved_path,
                    "media_type": media_type,
                    "filename": filename,
                },
            ), debug

    attachments = list(_iter_source_attachments(doc))
    debug["attachment_names"] = [att_name for att_name, _att_meta, _media_type in attachments]
    if attachments:
        att_name, _att_meta, media_type = attachments[0]
        debug["used_attachment"] = att_name
        safe_doc_id = quote(str(doc_id).strip(), safe="")
        att_url = (
            f"{COUCHDB_URL}/{quote(db_name, safe='')}"
            f"/{safe_doc_id}/{quote(att_name, safe='')}"
        )
        return ("couch_attachment", (session, att_url, att_name, media_type)), debug

    return None, debug


def _override_fetch_related_doc_debugs(
    session: Any,
    db_name: str,
    invoice_doc: dict[str, Any],
) -> list[dict[str, Any]]:
    related_debugs: list[dict[str, Any]] = []
    for source_label, related_doc_id in _extract_related_doc_refs(invoice_doc):
        related_doc = _fetch_doc_by_id(session, db_name, related_doc_id)
        if not isinstance(related_doc, dict):
            related_debugs.append(
                {
                    "doc_id": related_doc_id,
                    "source_label": source_label,
                    "found": False,
                }
            )
            continue

        _resolved, debug = _override_resolve_source_from_doc(
            session=session,
            db_name=db_name,
            doc=related_doc,
            doc_id=related_doc_id,
            invoice_id=_text(invoice_doc.get("_id")) or related_doc_id,
            source_label=source_label,
        )
        related_debugs.append(
            {
                "doc_id": related_doc_id,
                "source_label": source_label,
                "found": True,
                **debug,
            }
        )
    return related_debugs


def resolve_invoice_pdf(invoice_id: str) -> tuple[str, Any]:
    """Resolve the source document for a CouchDB invoice."""
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        raise FileNotFoundError("Document source non disponible pour cette facture.")
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        raise FileNotFoundError("Document source non disponible pour cette facture.")

    resolved, direct_debug = _override_resolve_source_from_doc(
        session=session,
        db_name=db_name,
        doc=doc,
        doc_id=_text(doc.get("_id")) or invoice_id,
        invoice_id=invoice_id,
        source_label="invoice_doc",
    )
    if resolved is not None:
        return resolved

    core_doc = _fetch_core_profile_doc(session, db_name, doc)
    core_error_reason: str | None = None
    if core_doc is not None:
        resolved, core_debug = _override_resolve_source_from_doc(
            session=session,
            db_name=db_name,
            doc=core_doc,
            doc_id=_text(core_doc.get("_id"))
            or _text((doc.get("form_common_core_ref") or {}).get("id"))
            or invoice_id,
            invoice_id=invoice_id,
            source_label="core_profile",
        )
        if resolved is not None:
            return resolved
        core_error_reason = str(core_debug.get("error_reason") or "").strip() or None

    for source_label, related_doc_id in _extract_related_doc_refs(doc):
        related_doc = _fetch_doc_by_id(session, db_name, related_doc_id)
        if not isinstance(related_doc, dict):
            continue
        resolved, _related_debug = _override_resolve_source_from_doc(
            session=session,
            db_name=db_name,
            doc=related_doc,
            doc_id=related_doc_id,
            invoice_id=invoice_id,
            source_label=source_label,
        )
        if resolved is not None:
            return resolved

    raise FileNotFoundError(core_error_reason or "Document source non disponible pour cette facture.")


def debug_invoice_pdf(invoice_id: str) -> dict[str, Any]:
    """Return an extended diagnostic dict for invoice source-document resolution."""
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        return {"invoice_id": invoice_id, "error": "Document introuvable dans CouchDB."}
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        return {"invoice_id": invoice_id, "error": "Document non valide."}

    invoice_form = _safe_dict(doc.get("invoice_form"))
    invoice_form_found = bool(invoice_form)
    ref, ref_field = _extract_form_common_core_ref(doc)
    form_common_core_ref_present = isinstance(ref, dict)
    form_common_core_ref_id = _text(ref.get("id")) if isinstance(ref, dict) else None

    direct_raw_path, direct_field = _extract_pdf_path_from_doc_with_field(doc)
    selected_resolution = _describe_pdf_source_resolution(direct_raw_path) if direct_raw_path else {}

    core_profile_found = False
    core_raw_path: str | None = None
    core_field: str | None = None
    core_error_reason: str | None = None
    core_doc = _fetch_core_profile_doc(session, db_name, doc)
    if isinstance(core_doc, dict):
        core_profile_found = True
        core_raw_path, core_field, core_error_reason = _extract_pdf_path_from_core_profile(core_doc)
        if core_raw_path:
            selected_resolution = _describe_pdf_source_resolution(core_raw_path)

    raw_attachments = doc.get("_attachments") or {}
    attachment_entries = [
        {
            "name": att_name,
            "content_type": str(_safe_dict(att_meta).get("content_type") or ""),
            "length": int(_safe_dict(att_meta).get("length") or 0),
            "media_type": (
                str(_safe_dict(att_meta).get("content_type") or "").lower()
                or (_guess_media_type_from_name(att_name) or "")
            ),
        }
        for att_name, att_meta in (raw_attachments.items() if isinstance(raw_attachments, dict) else [])
    ]

    related_docs = _override_fetch_related_doc_debugs(session, db_name, doc)
    successful_related = next(
        (
            item for item in related_docs
            if item.get("used_attachment") or item.get("exists_on_disk")
        ),
        None,
    )

    return {
        "invoice_id": invoice_id,
        "invoice_form_found": invoice_form_found,
        "form_common_core_ref_present": form_common_core_ref_present,
        "form_common_core_ref_field": ref_field,
        "form_common_core_ref_id": form_common_core_ref_id,
        "core_profile_found": core_profile_found,
        "raw_pdf_path": core_raw_path or direct_raw_path,
        "field_used": core_field or direct_field,
        "core_profile_id": form_common_core_ref_id,
        "core_profile_raw_path": core_raw_path,
        "matched_prefix": selected_resolution.get("matched_prefix"),
        "resolved_pdf_path_preview": selected_resolution.get("resolved_pdf_path_preview"),
        "exists_on_disk": bool(selected_resolution.get("exists_on_disk")),
        "file_extension": selected_resolution.get("file_extension"),
        "unknown_prefix": bool(selected_resolution.get("unknown_prefix")),
        "raw_prefix_preview": selected_resolution.get("raw_prefix_preview"),
        "parent_exists": bool(selected_resolution.get("parent_exists")),
        "nearest_existing_parent": selected_resolution.get("nearest_existing_parent"),
        "checked_path_variants": selected_resolution.get("checked_path_variants") or [],
        "backend_can_access_drive_z": bool(selected_resolution.get("backend_can_access_drive_z")),
        "error_reason": core_error_reason,
        "found_pdf_candidates": _extract_all_pdf_candidates(doc),
        "top_level_keys": [k for k in doc.keys() if not k.startswith("_")],
        "invoice_form_keys": list(invoice_form.keys()),
        "metadata_keys": list(_safe_dict(doc.get("metadata")).keys()),
        "attachments": attachment_entries,
        "related_docs_checked": related_docs,
        "related_doc_success": successful_related,
    }


def _walk_invoice_source_docs(
    session: Any,
    db_name: str,
    invoice_doc: dict[str, Any],
    invoice_id: str,
    max_depth: int = 4,
) -> list[tuple[str, str, dict[str, Any], int]]:
    walked: list[tuple[str, str, dict[str, Any], int]] = []
    root_doc_id = _text(invoice_doc.get("_id")) or invoice_id
    queue: list[tuple[str, str, dict[str, Any], int]] = [("invoice_doc", root_doc_id, invoice_doc, 0)]
    seen: set[str] = set()

    while queue:
        source_label, doc_id, doc, depth = queue.pop(0)
        if not isinstance(doc, dict):
            continue
        if doc_id in seen:
            continue
        seen.add(doc_id)
        walked.append((source_label, doc_id, doc, depth))

        if depth >= max_depth:
            continue

        core_doc = _fetch_core_profile_doc(session, db_name, doc)
        if isinstance(core_doc, dict):
            core_doc_id = _text(core_doc.get("_id"))
            if core_doc_id and core_doc_id not in seen:
                queue.append((f"{source_label}>core_profile", core_doc_id, core_doc, depth + 1))

        for related_label, related_doc_id in _extract_related_doc_refs(doc):
            if related_doc_id in seen:
                continue
            related_doc = _fetch_doc_by_id(session, db_name, related_doc_id)
            if isinstance(related_doc, dict):
                queue.append((f"{source_label}>{related_label}", related_doc_id, related_doc, depth + 1))

    return walked


def resolve_invoice_pdf(invoice_id: str) -> tuple[str, Any]:
    """Resolve the source document for a CouchDB invoice, following linked docs recursively."""
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        raise FileNotFoundError("Document source non disponible pour cette facture.")
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        raise FileNotFoundError("Document source non disponible pour cette facture.")

    first_error_reason: str | None = None
    for source_label, doc_id, source_doc, _depth in _walk_invoice_source_docs(
        session=session,
        db_name=db_name,
        invoice_doc=doc,
        invoice_id=invoice_id,
    ):
        resolved, debug = _override_resolve_source_from_doc(
            session=session,
            db_name=db_name,
            doc=source_doc,
            doc_id=doc_id,
            invoice_id=invoice_id,
            source_label=source_label,
        )
        if resolved is not None:
            return resolved
        if not first_error_reason:
            reason = str(debug.get("error_reason") or "").strip()
            if reason:
                first_error_reason = reason

    raise FileNotFoundError(first_error_reason or "Document source non disponible pour cette facture.")


def debug_invoice_pdf(invoice_id: str) -> dict[str, Any]:
    """Return an extended diagnostic dict for invoice source-document resolution."""
    session = http_session()
    db_name = _resolve_invoice_db_name(session)
    safe_id = quote(str(invoice_id).strip(), safe="")
    response = session.get(
        f"{COUCHDB_URL}/{quote(db_name, safe='')}/{safe_id}",
        timeout=60,
    )
    if response.status_code == 404:
        return {"invoice_id": invoice_id, "error": "Document introuvable dans CouchDB."}
    response.raise_for_status()
    doc = response.json()
    if not isinstance(doc, dict):
        return {"invoice_id": invoice_id, "error": "Document non valide."}

    invoice_form = _safe_dict(doc.get("invoice_form"))
    invoice_form_found = bool(invoice_form)
    ref, ref_field = _extract_form_common_core_ref(doc)
    form_common_core_ref_present = isinstance(ref, dict)
    form_common_core_ref_id = _text(ref.get("id")) if isinstance(ref, dict) else None

    docs_checked: list[dict[str, Any]] = []
    selected_debug: dict[str, Any] | None = None
    selected_source: str | None = None
    selected_kind: str | None = None
    first_error_reason: str | None = None
    first_raw_path: str | None = None
    first_field_used: str | None = None

    walked = _walk_invoice_source_docs(
        session=session,
        db_name=db_name,
        invoice_doc=doc,
        invoice_id=invoice_id,
    )

    for source_label, doc_id, source_doc, depth in walked:
        resolved, debug = _override_resolve_source_from_doc(
            session=session,
            db_name=db_name,
            doc=source_doc,
            doc_id=doc_id,
            invoice_id=invoice_id,
            source_label=source_label,
        )
        docs_checked.append(
            {
                "doc_id": doc_id,
                "source_label": source_label,
                "depth": depth,
                "top_level_keys": [k for k in source_doc.keys() if not str(k).startswith("_")],
                "has_form_common_core_ref": bool(_extract_form_common_core_ref(source_doc)[0]),
                "related_refs": _extract_related_doc_refs(source_doc),
                "path_field": debug.get("path_field"),
                "path_extractor": debug.get("path_extractor"),
                "raw_path": debug.get("raw_path"),
                "raw_path_preview": debug.get("raw_path_preview"),
                "resolved_pdf_path_preview": debug.get("resolved_pdf_path_preview"),
                "exists_on_disk": bool(debug.get("exists_on_disk")),
                "attachment_names": debug.get("attachment_names") or [],
                "used_attachment": debug.get("used_attachment"),
                "error_reason": debug.get("error_reason"),
                "resolved_kind": resolved[0] if resolved else None,
            }
        )
        if resolved is not None and selected_debug is None:
            selected_debug = debug
            selected_source = source_label
            selected_kind = resolved[0]
        if not first_error_reason:
            reason = str(debug.get("error_reason") or "").strip()
            if reason:
                first_error_reason = reason
        if not first_raw_path:
            maybe_raw = str(debug.get("raw_path") or "").strip()
            if maybe_raw:
                first_raw_path = maybe_raw
                first_field_used = str(debug.get("path_field") or "").strip() or None

    selected_resolution = {}
    selected_raw_path = str((selected_debug or {}).get("raw_path") or "").strip() or first_raw_path
    if selected_raw_path:
        selected_resolution = _describe_pdf_source_resolution(selected_raw_path)

    core_doc = _fetch_core_profile_doc(session, db_name, doc)
    core_profile_found = isinstance(core_doc, dict)

    return {
        "invoice_id": invoice_id,
        "invoice_form_found": invoice_form_found,
        "form_common_core_ref_present": form_common_core_ref_present,
        "form_common_core_ref_field": ref_field,
        "form_common_core_ref_id": form_common_core_ref_id,
        "core_profile_found": core_profile_found,
        "source_selected": selected_source,
        "resolved_kind": selected_kind,
        "raw_pdf_path": selected_raw_path,
        "field_used": (selected_debug or {}).get("path_field") or first_field_used,
        "matched_prefix": selected_resolution.get("matched_prefix"),
        "resolved_pdf_path_preview": selected_resolution.get("resolved_pdf_path_preview"),
        "exists_on_disk": bool(selected_resolution.get("exists_on_disk")),
        "file_extension": selected_resolution.get("file_extension"),
        "unknown_prefix": bool(selected_resolution.get("unknown_prefix")),
        "raw_prefix_preview": selected_resolution.get("raw_prefix_preview"),
        "parent_exists": bool(selected_resolution.get("parent_exists")),
        "nearest_existing_parent": selected_resolution.get("nearest_existing_parent"),
        "expected_parent_preview": selected_resolution.get("expected_parent_preview"),
        "nearest_existing_parent_files": selected_resolution.get("nearest_existing_parent_files") or [],
        "expected_filename": selected_resolution.get("expected_filename"),
        "filename_close_matches": selected_resolution.get("filename_close_matches") or [],
        "checked_path_variants": selected_resolution.get("checked_path_variants") or [],
        "backend_can_access_drive_z": bool(_debug_storage_path("Z:/").get("exists", False)),
        "error_reason": first_error_reason,
        "found_pdf_candidates": _extract_all_pdf_candidates(doc),
        "top_level_keys": [k for k in doc.keys() if not k.startswith("_")],
        "invoice_form_keys": list(invoice_form.keys()),
        "metadata_keys": list(_safe_dict(doc.get("metadata")).keys()),
        "attachments": [
            {
                "name": att_name,
                "content_type": str(_safe_dict(att_meta).get("content_type") or ""),
                "media_type": str(_safe_dict(att_meta).get("content_type") or "").lower()
                or (_guess_media_type_from_name(att_name) or ""),
            }
            for att_name, att_meta in ((_safe_dict(doc.get("_attachments")) or {}).items())
        ],
        "docs_checked": docs_checked,
        "related_docs_checked": [item for item in docs_checked if item.get("depth", 0) > 0],
        "related_doc_success": next(
            (
                item
                for item in docs_checked
                if item.get("used_attachment") or item.get("exists_on_disk") or item.get("resolved_kind")
            ),
            None,
        ),
    }


def _get_windows_drive_remote_path(drive_letter: str) -> str | None:
    if os.name != "nt":
        return None
    letter = str(drive_letter or "").strip().rstrip(":\\/").upper()
    if not letter:
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, fr"Network\{letter}") as key:
            value, _ = winreg.QueryValueEx(key, "RemotePath")
            remote_path = str(value or "").strip()
            return remote_path or None
    except OSError:
        return None


def _describe_pdf_source_resolution(raw_path: str | None) -> dict[str, Any]:
    """Describe how a raw source path resolves with configured mappings and UNC fallbacks."""
    from pathlib import Path as _Path

    description = {
        "matched_prefix": None,
        "resolved_pdf_path_preview": None,
        "exists_on_disk": False,
        "resolved_path": None,
        "unknown_prefix": False,
        "raw_prefix_preview": _preview_prefix(raw_path),
        "file_extension": None,
        "parent_exists": False,
        "nearest_existing_parent": None,
        "expected_parent_preview": None,
        "nearest_existing_parent_files": [],
        "expected_filename": None,
        "filename_close_matches": [],
        "checked_path_variants": [],
        "backend_can_access_drive_z": _debug_storage_path("Z:/").get("exists", False),
    }
    if not raw_path:
        return description

    raw_path_text = str(raw_path).strip()
    description["file_extension"] = _Path(raw_path_text).suffix.lower() or None
    description["expected_filename"] = _Path(raw_path_text).name or None
    mappings = _get_pdf_path_mappings()
    normalised = raw_path_text.replace("\\", "/")
    allowed_roots = {win.rstrip("/") for _, win in mappings}
    matched_mapping = False

    def _finalize_parent_debug(candidate_path: str) -> None:
        expected_parent = str(_Path(candidate_path).parent)
        description["expected_parent_preview"] = _mask_path(expected_parent)
        nearest_parent = _nearest_existing_parent(candidate_path)
        description["nearest_existing_parent"] = nearest_parent
        description["parent_exists"] = bool(nearest_parent)
        if nearest_parent:
            sample_names = _list_directory_names(nearest_parent, limit=10)
            description["nearest_existing_parent_files"] = sample_names
            expected_name = str(description.get("expected_filename") or "").strip()
            expected_norm = _normalize_name_for_match(expected_name)
            if expected_norm and sample_names:
                close_matches = []
                for name in sample_names:
                    norm = _normalize_name_for_match(name)
                    if not norm:
                        continue
                    if norm == expected_norm or expected_norm in norm or norm in expected_norm:
                        close_matches.append(name)
                description["filename_close_matches"] = close_matches[:10]

    def _push_candidate(candidate_path: str, source: str) -> None:
        if description["resolved_pdf_path_preview"] is None:
            description["resolved_pdf_path_preview"] = _mask_path(candidate_path)
        description["checked_path_variants"].append({"path": candidate_path, "source": source})

    relative_tail = ""
    if normalised.startswith(".../"):
        relative_tail = normalised[4:].lstrip("/")

    for linux_prefix, win_prefix in mappings:
        if not normalised.startswith(linux_prefix):
            continue
        matched_mapping = True
        description["matched_prefix"] = linux_prefix
        suffix = normalised[len(linux_prefix):]
        candidate_variants: list[tuple[str, str]] = []

        candidate_str = win_prefix.rstrip("/") + suffix
        candidate_variants.append((candidate_str, f"mapping:{linux_prefix}"))

        drive_prefix = win_prefix[:2] if len(win_prefix) >= 2 and win_prefix[1] == ":" else ""
        if drive_prefix:
            remote_path = _get_windows_drive_remote_path(drive_prefix[0])
            if remote_path:
                tail = candidate_str[2:].replace("/", "\\")
                unc_candidate = remote_path.rstrip("\\/") + tail
                candidate_variants.append((unc_candidate, f"registry:{drive_prefix[0]}"))

        if relative_tail:
            candidate_variants.append((
                win_prefix.rstrip("/") + "/fichiers_pdf_paris/" + relative_tail,
                f"ellipsis:{linux_prefix}:fichiers_pdf_paris",
            ))
            candidate_variants.append((
                win_prefix.rstrip("/") + "/" + relative_tail,
                f"ellipsis:{linux_prefix}:direct",
            ))

        for candidate_path, candidate_source in candidate_variants:
            _push_candidate(candidate_path, candidate_source)
            try:
                if _Path(candidate_path).exists():
                    description["exists_on_disk"] = True
                    description["resolved_path"] = candidate_path
                    description["parent_exists"] = True
                    description["nearest_existing_parent"] = _nearest_existing_parent(candidate_path)
                    return description
            except (OSError, ValueError):
                continue

        _finalize_parent_debug(candidate_str)
        return description

    if relative_tail:
        description["matched_prefix"] = "ellipsis_relative"
        for _linux_prefix, win_prefix in mappings:
            rel_candidates = [
                (win_prefix.rstrip("/") + "/fichiers_pdf_paris/" + relative_tail, "ellipsis_global:fichiers_pdf_paris"),
                (win_prefix.rstrip("/") + "/" + relative_tail, "ellipsis_global:direct"),
            ]
            for candidate_path, source in rel_candidates:
                _push_candidate(candidate_path, source)
                try:
                    if _Path(candidate_path).exists():
                        description["exists_on_disk"] = True
                        description["resolved_path"] = candidate_path
                        description["parent_exists"] = True
                        description["nearest_existing_parent"] = _nearest_existing_parent(candidate_path)
                        return description
                except (OSError, ValueError):
                    continue
        fallback_candidate = mappings[0][1].rstrip("/") + "/fichiers_pdf_paris/" + relative_tail if mappings else relative_tail
        _finalize_parent_debug(fallback_candidate)
        description["unknown_prefix"] = False
        return description

    for allowed_root in allowed_roots:
        if normalised.startswith(allowed_root):
            description["matched_prefix"] = allowed_root
            description["resolved_pdf_path_preview"] = _mask_path(normalised)
            _push_candidate(normalised, "direct_windows")
            try:
                if _Path(normalised).exists():
                    description["exists_on_disk"] = True
                    description["resolved_path"] = normalised
                    description["parent_exists"] = True
                    description["nearest_existing_parent"] = _nearest_existing_parent(normalised)
                    return description
            except (OSError, ValueError):
                pass
            _finalize_parent_debug(normalised)
            return description

    description["unknown_prefix"] = True
    _finalize_parent_debug(raw_path_text)
    return description

