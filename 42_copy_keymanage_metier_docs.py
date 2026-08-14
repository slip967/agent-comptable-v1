#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)


ROOT = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

DEFAULT_SOURCE_DB = os.getenv("SOURCE_DB", "keymanage_accounting").strip() or "keymanage_accounting"
DEFAULT_TARGET_DB = os.getenv("TARGET_DB", "ayasmine_test2").strip() or "ayasmine_test2"
DEFAULT_REPORT_JSON = "copy_keymanage_metier_docs_report.json"

FILTERABLE_METIERS = {"boulangerie", "boucherie", "restaurant", "transport", "btp"}
PROTECTED_TARGET_DBS = {
    "abt3",
    "abt3fec2",
    "fec_452416191",
    "keymanage_accounting",
    "keymanage_accountings",
}

EXACT_APE_TO_METIERS = {
    "4722Z": ["boucherie"],
    "5610A": ["restaurant"],
    "5610C": ["restaurant"],
    "5621Z": ["restaurant"],
    "5629A": ["restaurant"],
    "1071A": ["boulangerie"],
    "1071C": ["boulangerie"],
    "1071D": ["boulangerie"],
    "4724Z": ["boulangerie"],
    "4932Z": ["transport"],
    "4941A": ["transport"],
    "4941B": ["transport"],
    "5229A": ["transport"],
}
PREFIX_APE_TO_METIERS = {
    "41": ["btp"],
    "42": ["btp"],
    "43": ["btp"],
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def ensure_safe_target(source_db: str, target_db: str, dry_run: bool, allow_production_target: bool) -> None:
    if source_db == target_db:
        raise SystemExit("La base source et la base cible ne doivent pas etre identiques.")
    if dry_run:
        return
    if target_db in PROTECTED_TARGET_DBS and not allow_production_target:
        raise SystemExit(
            f"Refus d'ecriture vers {target_db}. Utilise --target-db {DEFAULT_TARGET_DB}, --dry-run, "
            "ou ajoute --allow-production-target si tu assumes explicitement cette cible."
        )


def couch_request(
    session: requests.Session,
    db_name: str,
    method: str,
    path: str = "",
    *,
    allow_404: bool = False,
    **kwargs,
) -> dict[str, Any]:
    if path:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}"
    response = session.request(method, url, timeout=120, **kwargs)
    if allow_404 and response.status_code == 404:
        return {}
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def iter_find(
    session: requests.Session,
    db_name: str,
    selector: dict[str, Any],
    *,
    fields: list[str] | None = None,
    partition_prefix: str | None = None,
    limit: int = 500,
) -> Any:
    bookmark: str | None = None
    if partition_prefix:
        path = f"_partition/{quote(partition_prefix, safe='')}/_find"
    else:
        path = "_find"

    while True:
        payload: dict[str, Any] = {
            "selector": selector,
            "limit": limit,
        }
        if fields:
            payload["fields"] = fields
        if bookmark:
            payload["bookmark"] = bookmark

        result = couch_request(session, db_name, "POST", path, json=payload)
        chunk = result.get("docs") or []
        if not chunk:
            break
        for doc in chunk:
            yield doc

        next_bookmark = result.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def normalize_ape(value: Any) -> str:
    cleaned = str(value or "").strip().upper().replace(" ", "").replace(".", "")
    return cleaned


def unwrap_doc_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return unwrap_doc_value(value.get("value"))
    return value


def get_nested(obj: Any, path: tuple[str, ...], default: Any = None) -> Any:
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def first_non_empty(obj: dict[str, Any], paths: list[tuple[str, ...]], default: Any = None) -> Any:
    for path in paths:
        value = get_nested(obj, path, default=None)
        if value not in (None, "", [], {}):
            return value
    return default


def extract_partition_prefix(doc_id: str) -> str:
    value = str(doc_id or "").strip()
    if ":" not in value:
        return ""
    return value.split(":", 1)[0]


def extract_client_siren_from_partition(partition_prefix: str) -> str:
    value = str(partition_prefix or "").strip()
    if not value.startswith("fr_bd_"):
        return ""
    siren = value.replace("fr_bd_", "", 1)
    if siren.isdigit() and len(siren) == 9:
        return siren
    return ""


def extract_siren_from_party(party: Any) -> str:
    if not isinstance(party, dict):
        return ""

    direct = str(unwrap_doc_value(party.get("siren")) or "").strip()
    if direct:
        return direct

    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = str(unwrap_doc_value(reg.get("type")) or "").strip().upper()
        reg_value = str(unwrap_doc_value(reg.get("value")) or "").strip()
        if reg_type == "SIREN" and reg_value:
            return reg_value
        if reg_type == "SIRET" and len(reg_value) >= 9:
            return reg_value[:9]

    return ""


def extract_ape_from_party(party: Any) -> str:
    if not isinstance(party, dict):
        return ""

    direct = normalize_ape(
        unwrap_doc_value(party.get("ape")) or unwrap_doc_value(party.get("naf")) or ""
    )
    if direct:
        return direct

    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = str(unwrap_doc_value(reg.get("type")) or "").strip().upper()
        reg_value = normalize_ape(unwrap_doc_value(reg.get("value")))
        if reg_type in {"APE", "NAF"} and reg_value:
            return reg_value

    return ""


def extract_client_ape_from_invoice_form(doc: dict[str, Any]) -> tuple[str, str]:
    for key in ("km_ape", "client_ape", "recipient_ape"):
        value = normalize_ape(doc.get(key))
        if value:
            return value, f"top_level:{key}"

    recipient = first_non_empty(
        doc,
        [
            ("recipient",),
            ("invoice", "recipient"),
            ("data", "recipient"),
        ],
        default={},
    )
    value = extract_ape_from_party(recipient)
    if value:
        return value, "recipient"

    return "", ""


def normalize_metier_label(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "boulangerie": "boulangerie",
        "boucherie": "boucherie",
        "restaurant": "restaurant",
        "restauration": "restaurant",
        "transport": "transport",
        "btp": "btp",
    }
    return mapping.get(raw, "")


def load_scope_metier_map() -> dict[str, str]:
    scope_map: dict[str, str] = {}
    for path in sorted(ROOT.glob("v1_scope_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        scope = payload.get("v1_scope") or {}
        if not isinstance(scope, dict):
            continue
        siren = str(scope.get("client_siren") or "").strip()
        metier = normalize_metier_label(scope.get("metier_pilote"))
        if siren and metier:
            scope_map[siren] = metier
    return scope_map


def load_kmorganisation_context(session: requests.Session, source_db: str) -> tuple[dict[str, dict[str, str]], dict[str, int]]:
    fields = ["_id", "ape", "naf", "company_registrations"]
    context: dict[str, dict[str, str]] = {}
    stats = {
        "kmorganisation_scanned": 0,
        "kmorganisation_with_ape": 0,
    }

    for doc in iter_find(session, source_db, {"p": "kmorganisation"}, fields=fields, limit=200):
        stats["kmorganisation_scanned"] += 1
        doc_id = str(doc.get("_id") or "").strip()
        partition_prefix = extract_partition_prefix(doc_id)
        if not partition_prefix:
            continue
        ape = normalize_ape(doc.get("ape") or doc.get("naf") or "")
        if not ape:
            ape = extract_ape_from_party(doc)
        context[partition_prefix] = {
            "doc_id": doc_id,
            "ape": ape,
        }
        if ape:
            stats["kmorganisation_with_ape"] += 1

    return context, stats


def extract_ape_from_company_doc(doc: dict[str, Any]) -> str:
    ape = normalize_ape(doc.get("ape") or doc.get("naf") or "")
    if ape:
        return ape

    formality = ((doc.get("formality") or {}).get("content") or {}).get("personneMorale") or {}
    etab = (formality.get("etablissementPrincipal") or {}).get("descriptionEtablissement") or {}
    ape = normalize_ape(etab.get("codeApe") or "")
    if ape:
        return ape

    return extract_ape_from_party(doc)


def load_company_ape_map(session: requests.Session, source_db: str) -> tuple[dict[str, str], dict[str, int]]:
    fields = ["_id", "siren", "ape", "naf", "company_registrations", "formality"]
    company_ape_by_siren: dict[str, str] = {}
    stats = {
        "company_scanned": 0,
        "company_with_ape": 0,
    }

    for doc in iter_find(session, source_db, {"p": "company"}, fields=fields, limit=300):
        stats["company_scanned"] += 1
        siren = str(doc.get("siren") or "").strip()
        if not siren:
            doc_id = str(doc.get("_id") or "").strip()
            if doc_id.startswith("company:"):
                siren = doc_id.split("company:", 1)[1].strip()
        if not siren:
            continue

        ape = extract_ape_from_company_doc(doc)
        if ape:
            company_ape_by_siren[siren] = ape
            stats["company_with_ape"] += 1

    return company_ape_by_siren, stats


def infer_metiers(client_siren: str, client_ape: str, scope_map: dict[str, str]) -> list[str]:
    ordered: list[str] = []
    ape = normalize_ape(client_ape)

    for metier in EXACT_APE_TO_METIERS.get(ape, []):
        if metier not in ordered:
            ordered.append(metier)

    for prefix, metiers in PREFIX_APE_TO_METIERS.items():
        if ape.startswith(prefix):
            for metier in metiers:
                if metier not in ordered:
                    ordered.append(metier)

    scope_metier = scope_map.get(str(client_siren or "").strip())
    if scope_metier and scope_metier not in ordered:
        ordered.append(scope_metier)

    return ordered


def scan_source_partitions(
    session: requests.Session,
    source_db: str,
    allowed_metiers: set[str],
    forced_partitions: set[str],
    scope_map: dict[str, str],
    kmorganisation_context: dict[str, dict[str, str]],
    company_ape_by_siren: dict[str, str],
    limit_partitions: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = [
        "_id",
        "recipient",
        "invoice",
        "data",
        "km_ape",
        "client_ape",
        "recipient_ape",
    ]
    invoice_docs = iter_find(session, source_db, {"p": "invoice_form"}, fields=fields, limit=500)

    by_partition: dict[str, dict[str, Any]] = {}
    invoice_forms_scanned = 0

    for doc in invoice_docs:
        invoice_forms_scanned += 1
        doc_id = str(doc.get("_id") or "").strip()
        partition_prefix = extract_partition_prefix(doc_id)
        if not partition_prefix:
            continue
        if forced_partitions and partition_prefix not in forced_partitions:
            continue

        bucket = by_partition.setdefault(
            partition_prefix,
            {
                "partition_prefix": partition_prefix,
                "client_siren": extract_client_siren_from_partition(partition_prefix),
                "kmorganisation_doc_id": str((kmorganisation_context.get(partition_prefix) or {}).get("doc_id") or ""),
                "kmorganisation_ape": str((kmorganisation_context.get(partition_prefix) or {}).get("ape") or ""),
                "invoice_form_docs_seen": 0,
                "client_ape_counter": Counter(),
                "client_ape_sources": Counter(),
                "sample_invoice_ids": [],
            },
        )
        bucket["invoice_form_docs_seen"] += 1
        if len(bucket["sample_invoice_ids"]) < 3:
            bucket["sample_invoice_ids"].append(doc_id)

        ape_value, ape_source = extract_client_ape_from_invoice_form(doc)
        if ape_value:
            bucket["client_ape_counter"][ape_value] += 1
            if ape_source:
                bucket["client_ape_sources"][ape_source] += 1

        if not bucket["client_siren"]:
            recipient = first_non_empty(
                doc,
                [
                    ("recipient",),
                    ("invoice", "recipient"),
                    ("data", "recipient"),
                ],
                default={},
            )
            bucket["client_siren"] = extract_siren_from_party(recipient)

    selected: list[dict[str, Any]] = []
    for partition_prefix, payload in by_partition.items():
        client_ape = ""
        if payload["client_ape_counter"]:
            client_ape = str(payload["client_ape_counter"].most_common(1)[0][0])
            client_ape_source = (
                payload["client_ape_sources"].most_common(1)[0][0]
                if payload["client_ape_sources"]
                else ""
            )
        else:
            client_ape = str(payload.get("kmorganisation_ape") or "")
            client_ape_source = "kmorganisation" if client_ape else ""
            if not client_ape:
                client_ape = str(company_ape_by_siren.get(str(payload.get("client_siren") or "").strip()) or "")
                client_ape_source = "company" if client_ape else ""

        inferred_metiers = infer_metiers(payload["client_siren"], client_ape, scope_map)
        matched_metiers = [metier for metier in inferred_metiers if metier in allowed_metiers]

        if forced_partitions:
            keep_partition = partition_prefix in forced_partitions
        else:
            keep_partition = bool(matched_metiers)

        if not keep_partition:
            continue

        record = {
            "partition_prefix": partition_prefix,
            "client_siren": payload["client_siren"],
            "client_ape": client_ape,
            "client_ape_source": client_ape_source,
            "kmorganisation_doc_id": payload.get("kmorganisation_doc_id") or "",
            "invoice_form_docs_seen": int(payload["invoice_form_docs_seen"]),
            "inferred_metiers": inferred_metiers,
            "selected_metiers": matched_metiers,
            "sample_invoice_ids": payload["sample_invoice_ids"],
        }
        selected.append(record)

    selected.sort(
        key=lambda row: (
            ",".join(row.get("selected_metiers") or row.get("inferred_metiers") or []),
            -int(row.get("invoice_form_docs_seen") or 0),
            str(row.get("partition_prefix") or ""),
        )
    )
    if limit_partitions > 0:
        selected = selected[:limit_partitions]

    scan_stats = {
        "invoice_forms_scanned": invoice_forms_scanned,
        "partitions_seen": len(by_partition),
        "partitions_selected": len(selected),
    }
    return selected, scan_stats


def unwrap_ocr_value(value: Any) -> Any:
    return unwrap_doc_value(value)


def clean_text(value: Any) -> str:
    return str(unwrap_ocr_value(value) or "").strip()


def clean_amount(value: Any) -> str:
    raw = unwrap_ocr_value(value)
    if raw in (None, "", []):
        return ""
    try:
        return f"{float(raw):.2f}"
    except Exception:
        return str(raw).strip()


def extract_invoice_duplicate_key(doc: dict[str, Any]) -> tuple[str, str, str, str, str] | None:
    issuer = first_non_empty(
        doc,
        [
            ("issuer",),
            ("invoice", "issuer"),
            ("data", "issuer"),
        ],
        default={},
    )
    supplier_siren = extract_siren_from_party(issuer)
    invoice_number = clean_text(doc.get("invoice_number"))
    invoice_date = clean_text(doc.get("invoice_date"))
    total_gross = clean_amount(doc.get("total_gross")) or clean_amount(doc.get("total_net"))
    document_type = clean_text(doc.get("document_type"))

    if not supplier_siren or not invoice_number or not invoice_date:
        return None
    return supplier_siren, invoice_number.upper(), invoice_date, total_gross, document_type.upper()


def extract_line_item_accounts(doc: dict[str, Any]) -> list[str]:
    raw_items = first_non_empty(
        doc,
        [
            ("line_items",),
            ("invoice", "line_items"),
            ("data", "line_items"),
        ],
        default=[],
    )
    if not isinstance(raw_items, list):
        return []

    accounts: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        account = clean_text(item.get("accounting_account"))
        if account and account not in accounts:
            accounts.append(account)
    return accounts


def extract_entry_invoice_form_id(doc: dict[str, Any]) -> str:
    invoice = doc.get("invoice") or {}
    if not isinstance(invoice, dict):
        return ""
    return str(invoice.get("invoice_form_id") or "").strip()


def extract_entry_business_account(doc: dict[str, Any]) -> str:
    account = str(doc.get("account_number") or "").strip()
    if not account:
        return ""
    if account.startswith(("401", "411", "445", "512", "53", "58")):
        return ""
    if account.startswith(("2", "6")):
        return account
    return ""


def fetch_existing_revs(session: requests.Session, db_name: str, ids: list[str]) -> dict[str, str]:
    revs: dict[str, str] = {}
    if not ids:
        return revs
    result = couch_request(session, db_name, "POST", "_all_docs", json={"keys": ids})
    for row in result.get("rows") or []:
        doc_id = str(row.get("id") or "").strip()
        value = row.get("value") or {}
        rev = str(value.get("rev") or "").strip()
        if doc_id and rev:
            revs[doc_id] = rev
    return revs


def bulk_upsert_docs(session: requests.Session, db_name: str, docs: list[dict[str, Any]]) -> None:
    if not docs:
        return
    result = couch_request(session, db_name, "POST", "_bulk_docs", json={"docs": docs})
    errors = [row for row in (result or []) if isinstance(row, dict) and row.get("error")]
    if errors:
        raise RuntimeError(f"_bulk_docs errors on {db_name}: {errors[:5]}")


def save_chunk(
    session: requests.Session,
    target_db: str,
    docs: list[dict[str, Any]],
    dry_run: bool,
) -> tuple[int, int]:
    if not docs:
        return 0, 0

    ids = [str(doc.get("_id") or "").strip() for doc in docs if str(doc.get("_id") or "").strip()]
    revs = fetch_existing_revs(session, target_db, ids) if not dry_run else {}

    created = 0
    updated = 0
    payloads: list[dict[str, Any]] = []
    for doc in docs:
        doc_id = str(doc.get("_id") or "").strip()
        if not doc_id:
            continue
        payload = dict(doc)
        payload.pop("_rev", None)
        target_rev = revs.get(doc_id)
        if target_rev:
            payload["_rev"] = target_rev
            updated += 1
        else:
            created += 1
        payloads.append(payload)

    if not dry_run:
        bulk_upsert_docs(session, target_db, payloads)

    return created, updated


def copy_partition_docs(
    session: requests.Session,
    source_db: str,
    target_db: str,
    partition_prefix: str,
    batch_size: int,
    dry_run: bool,
    exclude_generated_entries: bool,
) -> dict[str, int]:
    selector_kmorganisation = {"p": "kmorganisation"}
    selector_invoice = {"p": "invoice_form"}
    selector_entry: dict[str, Any] = {
        "p": "entry",
        "invoice": {"$exists": True},
    }
    if exclude_generated_entries:
        selector_entry["_id"] = {"$regex": "^(?!.*generated).*$"}

    kmorganisation_docs = iter_find(
        session,
        source_db,
        selector_kmorganisation,
        partition_prefix=partition_prefix,
        limit=batch_size,
    )
    invoice_docs = iter_find(
        session,
        source_db,
        selector_invoice,
        partition_prefix=partition_prefix,
        limit=batch_size,
    )
    entry_docs = iter_find(
        session,
        source_db,
        selector_entry,
        partition_prefix=partition_prefix,
        limit=batch_size,
    )

    stats = {
        "kmorganisation_copied": 0,
        "invoice_form_copied": 0,
        "entry_copied": 0,
        "created": 0,
        "updated": 0,
        "duplicate_invoice_keys_count": 0,
        "duplicate_invoice_docs_count": 0,
        "ambiguous_line_account_invoice_count": 0,
        "ambiguous_entry_account_invoice_count": 0,
    }
    duplicate_counter: Counter[tuple[str, str, str, str, str]] = Counter()
    duplicate_examples: dict[tuple[str, str, str, str, str], list[str]] = {}
    ambiguous_line_examples: list[dict[str, Any]] = []
    ambiguous_line_count = 0
    entry_accounts_by_invoice: dict[str, set[str]] = defaultdict(set)
    entry_account_examples: dict[str, dict[str, Any]] = {}

    for docs, label in (
        (kmorganisation_docs, "kmorganisation_copied"),
        (invoice_docs, "invoice_form_copied"),
        (entry_docs, "entry_copied"),
    ):
        chunk: list[dict[str, Any]] = []
        for doc in docs:
            if label == "invoice_form_copied":
                duplicate_key = extract_invoice_duplicate_key(doc)
                if duplicate_key:
                    duplicate_counter[duplicate_key] += 1
                    duplicate_examples.setdefault(duplicate_key, []).append(str(doc.get("_id") or ""))

                line_accounts = extract_line_item_accounts(doc)
                if len(line_accounts) > 1:
                    ambiguous_line_count += 1
                    if len(ambiguous_line_examples) < 10:
                        ambiguous_line_examples.append(
                            {
                                "invoice_form_id": str(doc.get("_id") or ""),
                                "accounts": line_accounts,
                                "invoice_number": clean_text(doc.get("invoice_number")),
                            }
                        )

            if label == "entry_copied":
                invoice_form_id = extract_entry_invoice_form_id(doc)
                business_account = extract_entry_business_account(doc)
                if invoice_form_id and business_account:
                    entry_accounts_by_invoice[invoice_form_id].add(business_account)
                    entry_account_examples.setdefault(
                        invoice_form_id,
                        {
                            "invoice_form_id": invoice_form_id,
                            "accounts": set(),
                            "sample_entry_ids": [],
                        },
                    )
                    entry_account_examples[invoice_form_id]["accounts"].add(business_account)
                    if len(entry_account_examples[invoice_form_id]["sample_entry_ids"]) < 5:
                        entry_account_examples[invoice_form_id]["sample_entry_ids"].append(str(doc.get("_id") or ""))

            chunk.append(doc)
            if len(chunk) >= batch_size:
                created, updated = save_chunk(session, target_db, chunk, dry_run)
                stats[label] += len(chunk)
                stats["created"] += created
                stats["updated"] += updated
                chunk = []
        if chunk:
            created, updated = save_chunk(session, target_db, chunk, dry_run)
            stats[label] += len(chunk)
            stats["created"] += created
            stats["updated"] += updated

    duplicate_groups = [
        (key, count)
        for key, count in duplicate_counter.items()
        if count > 1
    ]
    stats["duplicate_invoice_keys_count"] = len(duplicate_groups)
    stats["duplicate_invoice_docs_count"] = sum(count for _, count in duplicate_groups)
    stats["duplicate_invoice_examples"] = [
        {
            "supplier_siren": key[0],
            "invoice_number": key[1],
            "invoice_date": key[2],
            "total_amount": key[3],
            "document_type": key[4],
            "count": count,
            "invoice_form_ids": duplicate_examples.get(key, [])[:5],
        }
        for key, count in duplicate_groups[:10]
    ]

    stats["ambiguous_line_account_invoice_count"] = ambiguous_line_count
    stats["ambiguous_line_account_examples"] = ambiguous_line_examples

    ambiguous_entry_ids = [
        invoice_form_id
        for invoice_form_id, accounts in entry_accounts_by_invoice.items()
        if len(accounts) > 1
    ]
    stats["ambiguous_entry_account_invoice_count"] = len(ambiguous_entry_ids)
    stats["ambiguous_entry_account_examples"] = [
        {
            "invoice_form_id": invoice_form_id,
            "accounts": sorted(entry_account_examples[invoice_form_id]["accounts"]),
            "sample_entry_ids": entry_account_examples[invoice_form_id]["sample_entry_ids"],
        }
        for invoice_form_id in ambiguous_entry_ids[:10]
    ]

    return stats


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copie depuis une base source (ex: keymanage_accounting) les docs p=kmorganisation, "
            "p=invoice_form et les docs p=entry lies aux factures vers ayasmine_test2, en filtrant les partitions "
            "selon l'APE client pour les metiers produits (boulangerie, boucherie, restaurant, transport, btp)."
        )
    )
    parser.add_argument("--source-db", default=DEFAULT_SOURCE_DB, help="Base source CouchDB.")
    parser.add_argument("--target-db", default=DEFAULT_TARGET_DB, help="Base cible CouchDB.")
    parser.add_argument(
        "--metier",
        nargs="*",
        default=["boulangerie", "boucherie", "restaurant", "transport", "btp", "charges_externes"],
        help=(
            "Metiers a retenir. Note: charges_externes n'ajoute pas de partitions a lui seul; "
            "les charges externes sont copiees automatiquement avec les partitions metier retenues."
        ),
    )
    parser.add_argument(
        "--partition-prefix",
        nargs="*",
        default=[],
        help="Force la copie de certaines partitions fr_bd_xxx, meme si l'APE est absent.",
    )
    parser.add_argument(
        "--limit-partitions",
        type=int,
        default=0,
        help="Option de debug: limite le nombre de partitions retenues apres tri (0 = toutes).",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="Taille des batches _bulk_docs.")
    parser.add_argument("--dry-run", action="store_true", help="Analyse sans ecrire dans la base cible.")
    parser.add_argument(
        "--allow-production-target",
        action="store_true",
        help="Autorise l'ecriture vers une base protegee.",
    )
    parser.add_argument(
        "--include-generated-entries",
        action="store_true",
        help="Inclut aussi les entry generees (par defaut elles sont exclues).",
    )
    parser.add_argument(
        "--report-json",
        default=DEFAULT_REPORT_JSON,
        help="Chemin du rapport JSON de synthese.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_db = str(args.source_db or "").strip()
    target_db = str(args.target_db or "").strip()
    ensure_safe_target(source_db, target_db, args.dry_run, args.allow_production_target)

    requested_metiers = [normalize_metier_label(value) or str(value or "").strip().lower() for value in (args.metier or [])]
    requested_metiers = [value for value in requested_metiers if value]
    allowed_metiers = {value for value in requested_metiers if value in FILTERABLE_METIERS}
    forced_partitions = {str(value or "").strip() for value in (args.partition_prefix or []) if str(value or "").strip()}
    scope_map = load_scope_metier_map()

    if not allowed_metiers and not forced_partitions:
        raise SystemExit(
            "Aucun metier filtrable fourni. Utilise au moins un de: "
            + ", ".join(sorted(FILTERABLE_METIERS))
            + " ou force des partitions avec --partition-prefix."
        )

    session = http_session()
    kmorganisation_context, kmorganisation_scan_stats = load_kmorganisation_context(session, source_db)
    company_ape_by_siren, company_scan_stats = load_company_ape_map(session, source_db)
    selected_partitions, scan_stats = scan_source_partitions(
        session,
        source_db,
        allowed_metiers=allowed_metiers,
        forced_partitions=forced_partitions,
        scope_map=scope_map,
        kmorganisation_context=kmorganisation_context,
        company_ape_by_siren=company_ape_by_siren,
        limit_partitions=int(args.limit_partitions or 0),
    )
    scan_stats.update(kmorganisation_scan_stats)
    scan_stats.update(company_scan_stats)

    if not selected_partitions:
        print("[INFO] Aucune partition retenue apres scan.")
        report = {
            "generated_at": now_iso(),
            "source_db": source_db,
            "target_db": target_db,
            "dry_run": bool(args.dry_run),
            "requested_metiers": requested_metiers,
            "scan_stats": scan_stats,
            "partitions": [],
        }
        report_path = Path(args.report_json)
        if not report_path.is_absolute():
            report_path = (ROOT / report_path).resolve()
        write_report(report_path, report)
        print(f"[OK] report={report_path}")
        return 0

    print(f"[INFO] source_db={source_db}")
    print(f"[INFO] target_db={target_db}")
    print(f"[INFO] dry_run={bool(args.dry_run)}")
    print(f"[INFO] metiers demandes={', '.join(requested_metiers)}")
    print(
        "[INFO] partitions retenues={count} | invoice_forms_scanned={scanned} | partitions_seen={seen}".format(
            count=len(selected_partitions),
            scanned=scan_stats["invoice_forms_scanned"],
            seen=scan_stats["partitions_seen"],
        )
    )

    report_partitions: list[dict[str, Any]] = []
    total_kmorganisation = 0
    total_invoice_form = 0
    total_entry = 0
    total_created = 0
    total_updated = 0
    total_duplicate_keys = 0
    total_duplicate_docs = 0
    total_ambiguous_line_invoices = 0
    total_ambiguous_entry_invoices = 0

    for index, partition in enumerate(selected_partitions, start=1):
        prefix = str(partition["partition_prefix"])
        print(
            "[{idx}/{total}] partition={prefix} client_ape={ape} metiers={metiers} invoice_forms_seen={seen}".format(
                idx=index,
                total=len(selected_partitions),
                prefix=prefix,
                ape=partition.get("client_ape") or "",
                metiers=",".join(partition.get("selected_metiers") or partition.get("inferred_metiers") or []),
                seen=partition.get("invoice_form_docs_seen") or 0,
            )
        )

        copy_stats = copy_partition_docs(
            session,
            source_db=source_db,
            target_db=target_db,
            partition_prefix=prefix,
            batch_size=max(int(args.batch_size or 200), 20),
            dry_run=bool(args.dry_run),
            exclude_generated_entries=not bool(args.include_generated_entries),
        )

        total_kmorganisation += copy_stats["kmorganisation_copied"]
        total_invoice_form += copy_stats["invoice_form_copied"]
        total_entry += copy_stats["entry_copied"]
        total_created += copy_stats["created"]
        total_updated += copy_stats["updated"]
        total_duplicate_keys += copy_stats["duplicate_invoice_keys_count"]
        total_duplicate_docs += copy_stats["duplicate_invoice_docs_count"]
        total_ambiguous_line_invoices += copy_stats["ambiguous_line_account_invoice_count"]
        total_ambiguous_entry_invoices += copy_stats["ambiguous_entry_account_invoice_count"]

        report_row = dict(partition)
        report_row.update(copy_stats)
        report_partitions.append(report_row)

        print(
            "      kmorganisation={kmorganisation} | invoice_form={invoice_form} | entry={entry} | doublons={duplicates} | ligne_ambigue={line_ambiguous} | entry_ambigue={entry_ambiguous} | created={created} | updated={updated}".format(
                kmorganisation=copy_stats["kmorganisation_copied"],
                invoice_form=copy_stats["invoice_form_copied"],
                entry=copy_stats["entry_copied"],
                duplicates=copy_stats["duplicate_invoice_keys_count"],
                line_ambiguous=copy_stats["ambiguous_line_account_invoice_count"],
                entry_ambiguous=copy_stats["ambiguous_entry_account_invoice_count"],
                created=copy_stats["created"],
                updated=copy_stats["updated"],
            )
        )

    report = {
        "generated_at": now_iso(),
        "source_db": source_db,
        "target_db": target_db,
        "dry_run": bool(args.dry_run),
        "requested_metiers": requested_metiers,
        "scan_stats": scan_stats,
        "copy_stats": {
            "kmorganisation_copied": total_kmorganisation,
            "invoice_form_copied": total_invoice_form,
            "entry_copied": total_entry,
            "created": total_created,
            "updated": total_updated,
            "duplicate_invoice_keys_count": total_duplicate_keys,
            "duplicate_invoice_docs_count": total_duplicate_docs,
            "ambiguous_line_account_invoice_count": total_ambiguous_line_invoices,
            "ambiguous_entry_account_invoice_count": total_ambiguous_entry_invoices,
        },
        "partitions": report_partitions,
    }

    report_path = Path(args.report_json)
    if not report_path.is_absolute():
        report_path = (ROOT / report_path).resolve()
    write_report(report_path, report)

    print(
        "[OK] kmorganisation={kmorganisation} invoice_form={invoice_form} entry={entry} doublons={duplicates} ligne_ambigue={line_ambiguous} entry_ambigue={entry_ambiguous} created={created} updated={updated}".format(
            kmorganisation=total_kmorganisation,
            invoice_form=total_invoice_form,
            entry=total_entry,
            duplicates=total_duplicate_keys,
            line_ambiguous=total_ambiguous_line_invoices,
            entry_ambiguous=total_ambiguous_entry_invoices,
            created=total_created,
            updated=total_updated,
        )
    )
    print(f"[OK] report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
