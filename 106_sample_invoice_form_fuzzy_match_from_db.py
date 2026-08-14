#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

import requests

from couch_config import (
    CA_CERT,
    CLIENT_CERT,
    CLIENT_KEY,
    COUCHDB_PASS,
    COUCHDB_URL,
    COUCHDB_USER,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DB_CANDIDATES = ["keymanage_accouting", "keymanage_accounting"]
FIELDS = [
    "_id",
    "p",
    "document_type",
    "invoice_number",
    "invoice_date",
    "issuer",
    "recipient",
    "line_items",
    "currency",
    "total_net",
    "total_vat",
    "total_gross",
]


def build_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    response = session.request(method, url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def resolve_db_name(session: requests.Session) -> str:
    for name in DB_CANDIDATES:
        try:
            response = session.get(f"{COUCHDB_URL}/{name}", timeout=60)
            if response.status_code == 200:
                return name
        except requests.RequestException:
            continue
    raise RuntimeError(
        f"Aucune base trouvée parmi {', '.join(DB_CANDIDATES)} sur {COUCHDB_URL}."
    )


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_generator(module):
    obj = module.AccountingEntryGenerator.__new__(module.AccountingEntryGenerator)
    obj.verbose = False
    obj._activity_by_pair = {}
    obj._external_charge_matcher_module = None
    obj._external_charge_refs = None
    obj._product_metier_refs = None
    obj._external_charge_matcher_error = None
    obj._scope_metier_by_client = None
    obj.stats = {}
    obj._log = lambda *args, **kwargs: None
    return obj


def unwrap_value(value: Any) -> Any:
    current = value
    while isinstance(current, dict) and "value" in current:
        current = current.get("value")
    return current


def extract_registration(entity: dict[str, Any] | None, reg_type: str) -> str | None:
    if not entity:
        return None
    for reg in entity.get("company_registrations") or []:
        if str(unwrap_value(reg.get("type")) or "").strip().upper() == reg_type.upper():
            value = str(unwrap_value(reg.get("value")) or "").strip()
            if value:
                return value
    return None


def extract_siren(entity: dict[str, Any] | None) -> str | None:
    if not entity:
        return None
    direct = str(unwrap_value(entity.get("siren")) or "").strip()
    if direct.isdigit() and len(direct) == 9:
        return direct
    reg = extract_registration(entity, "SIREN")
    if reg:
        digits = "".join(ch for ch in reg if ch.isdigit())
        if len(digits) >= 9:
            return digits[:9]
    siret = extract_registration(entity, "SIRET")
    if siret:
        digits = "".join(ch for ch in siret if ch.isdigit())
        if len(digits) >= 9:
            return digits[:9]
    return None


def extract_ape(entity: dict[str, Any] | None) -> str | None:
    if not entity:
        return None
    value = str(unwrap_value(entity.get("ape")) or "").strip().upper()
    if value:
        return value
    reg = extract_registration(entity, "APE")
    if reg:
        return str(reg).strip().upper()
    return None


def extract_entity_name(entity: dict[str, Any] | None) -> str:
    if not entity:
        return ""
    for key in ("name", "company_name", "label"):
        value = str(unwrap_value(entity.get(key)) or "").strip()
        if value:
            return value
    return ""


def extract_line_item_text(line_item: dict[str, Any], generator) -> str:
    raw = generator._extract_line_item_text(line_item)  # noqa: SLF001
    if raw:
        return raw
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
        value = unwrap_value(line_item.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_float(value: Any) -> float | None:
    raw = unwrap_value(value)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def is_invoice_form_invoice(doc: dict[str, Any]) -> bool:
    if str(doc.get("p") or "").strip() != "invoice_form":
        return False
    document_type = str(doc.get("document_type") or "").strip().lower()
    if document_type != "invoice":
        return False
    line_items = doc.get("line_items") or []
    return isinstance(line_items, list) and len(line_items) > 0


def random_window_sample_invoice_forms(
    session: requests.Session,
    db_name: str,
    *,
    sample_size: int,
    seed: int,
    window_limit: int = 200,
    max_attempts: int = 60,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    chosen: dict[str, dict[str, Any]] = {}
    scanned_rows = 0

    for _ in range(max_attempts):
        startkey = f"fr_bd_{rng.randint(0, 999999999):09d}"
        response = session.get(
            f"{COUCHDB_URL}/{db_name}/_all_docs",
            params={
                "include_docs": "true",
                "startkey": json.dumps(startkey),
                "limit": str(window_limit),
            },
            timeout=120,
        )
        response.raise_for_status()
        rows = response.json().get("rows") or []
        scanned_rows += len(rows)

        for row in rows:
            doc = row.get("doc") or {}
            if not isinstance(doc, dict) or not is_invoice_form_invoice(doc):
                continue
            chosen[str(doc.get("_id") or row.get("id"))] = doc

        if len(chosen) >= sample_size:
            break

    if not chosen:
        raise RuntimeError("Aucune invoice_form de type Invoice avec line_items n'a été trouvée.")

    docs = list(chosen.values())
    if len(docs) > sample_size:
        docs = rng.sample(docs, sample_size)

    return docs, {
        "sampling_mode": "random_all_docs_windows",
        "scanned_rows": scanned_rows,
        "window_limit": window_limit,
        "attempts": max_attempts,
        "sample_pool_size": len(chosen),
        "document_type_filter": "Invoice",
        "seed": seed,
        "sample_size": len(docs),
    }


def summarize_match(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metier": row.get("metier"),
        "base_cible": row.get("base_cible"),
        "article_source_match": row.get("article_source_match"),
        "compte_comptable": row.get("compte_comptable"),
        "compte_comptable_libelle": row.get("compte_comptable_libelle") or row.get("account_label"),
        "score_confiance": row.get("score_confiance"),
        "decision_finale": row.get("decision_finale"),
        "metier_coherence": row.get("metier_coherence"),
        "tva_coherence": row.get("tva_coherence"),
        "raison_match": row.get("raison_match"),
        "source_invoice_ids_count": len(row.get("source_invoice_ids") or []),
        "invoice_paths_sources_count": len(row.get("invoice_paths_sources") or []),
        "ape_context": row.get("ape_context") or [],
    }


def analyze_invoice(
    invoice: dict[str, Any],
    *,
    matcher_module,
    refs,
    generator,
) -> dict[str, Any]:
    issuer = invoice.get("issuer") or {}
    recipient = invoice.get("recipient") or {}
    issuer_name = extract_entity_name(issuer)
    recipient_name = extract_entity_name(recipient)
    client_siren = extract_siren(recipient)
    client_ape = extract_ape(recipient) or str(unwrap_value(invoice.get("km_ape")) or "").strip().upper() or None
    supplier_ape = extract_ape(issuer) or str(unwrap_value(invoice.get("supplier_ape")) or "").strip().upper() or None
    preferred_metiers = generator._preferred_metiers_for_context(client_siren or "", client_ape)  # noqa: SLF001
    metier_hint = preferred_metiers[0] if preferred_metiers else None

    line_results: list[dict[str, Any]] = []
    for idx, line_item in enumerate(invoice.get("line_items") or [], start=1):
        line_text = extract_line_item_text(line_item, generator)
        if not line_text:
            continue
        tva_hint = extract_float(line_item.get("vat_percent"))

        matches = matcher_module.match_text(
            refs=refs,
            text=line_text,
            fournisseur_hint=str(issuer_name or "").strip() or None,
            metier=metier_hint,
            client_ape_hint=client_ape,
            supplier_ape_hint=supplier_ape,
            top_n=3,
            tva_hint=tva_hint,
            include_charges=False,
        )
        line_results.append(
            {
                "line_index": idx,
                "line_text": line_text,
                "vat_percent": tva_hint,
                "top_matches": [summarize_match(row) for row in matches],
            }
        )

    return {
        "invoice_id": invoice.get("_id"),
        "document_type": invoice.get("document_type"),
        "invoice_number": unwrap_value(invoice.get("invoice_number")),
        "invoice_date": unwrap_value(invoice.get("invoice_date")),
        "issuer_name": issuer_name,
        "recipient_name": recipient_name,
        "client_siren": client_siren,
        "client_ape": client_ape,
        "supplier_ape": supplier_ape,
        "preferred_metiers": preferred_metiers,
        "metier_hint_used": metier_hint,
        "line_items_count": len(invoice.get("line_items") or []),
        "matched_line_items_count": len([row for row in line_results if row.get("top_matches")]),
        "line_matches": line_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sample 10 invoice_form docs of type Invoice from CouchDB and fuzzy-match their line_items against the 8 JSON knowledge bases."
    )
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260525)
    parser.add_argument(
        "--out-json",
        default="random_invoice_form_fuzzy_match_report.json",
        help="Output report JSON path.",
    )
    args = parser.parse_args()

    matcher_module = load_module("match_reference_v1_module_sample", SCRIPT_DIR / "10_match_reference_v1.py")
    refs = matcher_module.load_references()

    generator_module = load_module("generated_entries_module_sample", SCRIPT_DIR / "05_generated_entries.py")
    generator = build_generator(generator_module)

    session = build_session()
    db_name = resolve_db_name(session)
    sample_docs, sample_meta = random_window_sample_invoice_forms(
        session,
        db_name,
        sample_size=args.sample_size,
        seed=args.seed,
    )

    analyses = [
        analyze_invoice(doc, matcher_module=matcher_module, refs=refs, generator=generator)
        for doc in sample_docs
    ]

    report = {
        "db_name_used": db_name,
        "sample_meta": sample_meta,
        "references_loaded": len(refs),
        "invoice_forms": analyses,
    }

    out_path = Path(args.out_json)
    if not out_path.is_absolute():
        out_path = (SCRIPT_DIR / out_path).resolve()
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] db={db_name}")
    print(f"[INFO] sampling_mode={sample_meta['sampling_mode']}")
    print(f"[INFO] scanned_rows={sample_meta['scanned_rows']}")
    print(f"[INFO] sample_pool_size={sample_meta['sample_pool_size']}")
    print(f"[INFO] sample_size={sample_meta['sample_size']}")
    print(f"[INFO] references_loaded={len(refs)}")
    print(f"[OK] report={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
