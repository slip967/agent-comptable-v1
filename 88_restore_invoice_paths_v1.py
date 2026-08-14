#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
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

SOURCE_DBS = ["abt3", "keymanage_accounting"]
TARGET_PATTERNS = [
    "base_produits_*_v1.json",
    "base_charges_externes_v1.json",
    "base_produits_*_v1_with_accounts.json",
    "base_charges_externes_v1_with_accounts.json",
]
SUMMARY_JSON = ROOT / "restore_invoice_paths_v1_summary.json"
SUMMARY_MD = ROOT / "restore_invoice_paths_v1_summary.md"

ITEM_KEY_ORDER = [
    "article_source",
    "article_canonique",
    "mots_cles",
    "source_invoice_ids",
    "invoice_paths_sources",
    "ape_context",
    "partitions_sources",
    "compte_comptable",
    "taux_tva",
    "tva_rate",
    "categorie",
    "sous_categorie",
    "type_fournisseur",
    "fournisseur_type",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def couch_request(sess: requests.Session, db: str, method: str, path: str = "", **kwargs) -> dict[str, Any]:
    if path:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}"
    response = sess.request(method, url, timeout=120, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def iter_target_files() -> list[Path]:
    selected: dict[str, Path] = {}
    for pattern in TARGET_PATTERNS:
        for path in sorted(ROOT.glob(pattern)):
            selected[str(path.resolve())] = path
    return list(selected.values())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        val = str(value or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        ordered.append(val)
    return ordered


def normalize_pdf_fragment(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_")
    value = re.sub(r"_+", "_", value)
    return f"pdf_{value}"


def build_local_pdf_path_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in sorted(ROOT.glob("base_*_clean_v2.json")):
        payload = load_json(path)
        meta = payload.get("meta") or {}
        schemes_by_folder: dict[str, str] = {}
        pdfs_by_folder: dict[str, list[dict[str, Any]]] = {}
        for value in meta.values():
            if not isinstance(value, dict):
                continue
            folder = str(value.get("source_folder") or "").strip()
            scheme = str(value.get("source_id_scheme") or "").strip()
            pdfs = value.get("pdfs")
            if folder and scheme:
                schemes_by_folder[folder] = scheme
            if folder and isinstance(pdfs, list):
                pdfs_by_folder[folder] = [entry for entry in pdfs if isinstance(entry, dict)]

        for folder, pdfs in pdfs_by_folder.items():
            scheme = schemes_by_folder.get(folder, "")
            if ":pdf_" not in scheme:
                continue
            prefix = scheme.split(":pdf_", 1)[0]
            for entry in pdfs:
                relative_path = str(entry.get("relative_path") or "").strip()
                if not relative_path:
                    continue
                source_id = f"{prefix}:{normalize_pdf_fragment(relative_path)}"
                full_path = str(PureWindowsPath(folder) / PureWindowsPath(relative_path))
                mapping[source_id] = full_path
    return mapping


def collect_all_source_invoice_ids(paths: list[Path]) -> list[str]:
    ids: list[str] = []
    for path in paths:
        payload = load_json(path)
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                ids.extend(str(value or "").strip() for value in (item.get("source_invoice_ids") or []))
    return unique_keep_order(ids)


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_invoice_to_path_map(invoice_ids: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    invoice_to_core: dict[str, str] = {}
    invoice_to_db: dict[str, str] = {}
    core_to_path: dict[str, str] = {}
    non_pdf_ids = [value for value in invoice_ids if value and ":pdf_" not in value]
    if not non_pdf_ids:
        return {}, {}

    sess = http_session()
    unresolved_ids = list(non_pdf_ids)
    for db_name in SOURCE_DBS:
        if not unresolved_ids:
            break
        next_unresolved: list[str] = []
        for chunk in chunked(unresolved_ids, 200):
            result = couch_request(
                sess,
                db_name,
                "POST",
                "_all_docs?include_docs=true",
                json={"keys": chunk},
            )
            found_ids: set[str] = set()
            for row in result.get("rows", []):
                doc = row.get("doc") or {}
                invoice_id = str(row.get("id") or "").strip()
                if not invoice_id or str(doc.get("p") or "").strip() != "invoice_form":
                    continue
                core_id = str(((doc.get("form_common_core_ref") or {}).get("id")) or "").strip()
                if core_id:
                    invoice_to_core[invoice_id] = core_id
                    invoice_to_db[invoice_id] = db_name
                    found_ids.add(invoice_id)
            for source_id in chunk:
                if source_id not in found_ids:
                    next_unresolved.append(source_id)
        unresolved_ids = next_unresolved

    core_ids_by_db: dict[str, list[str]] = {}
    for invoice_id, core_id in invoice_to_core.items():
        db_name = invoice_to_db.get(invoice_id, "")
        if not db_name:
            continue
        core_ids_by_db.setdefault(db_name, []).append(core_id)

    for db_name, core_ids in core_ids_by_db.items():
        for chunk in chunked(unique_keep_order(core_ids), 200):
            result = couch_request(
                sess,
                db_name,
                "POST",
                "_all_docs?include_docs=true",
                json={"keys": chunk},
            )
            for row in result.get("rows", []):
                doc = row.get("doc") or {}
                core_id = str(row.get("id") or "").strip()
                if not core_id:
                    continue
                form_common_core = doc.get("form_common_core") or {}
                ingest = form_common_core.get("ingest") or {}
                file_node = form_common_core.get("file") or {}
                path_value = str(ingest.get("path") or "").strip()
                if not path_value:
                    path_value = str(file_node.get("file_name") or "").strip()
                if path_value:
                    core_to_path[core_id] = path_value

    invoice_to_path: dict[str, str] = {}
    for invoice_id, core_id in invoice_to_core.items():
        path_value = core_to_path.get(core_id, "")
        if path_value:
            invoice_to_path[invoice_id] = path_value
    return invoice_to_path, invoice_to_core


def reorder_item(item: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in ITEM_KEY_ORDER:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def apply_paths_to_section(
    rows: list[dict[str, Any]],
    invoice_to_path: dict[str, str],
    local_pdf_map: dict[str, str],
) -> dict[str, int]:
    stats = {
        "rows_total": 0,
        "rows_changed": 0,
        "rows_with_paths": 0,
        "paths_added": 0,
        "resolved_source_ids": 0,
        "unresolved_source_ids": 0,
    }
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        stats["rows_total"] += 1
        source_ids = unique_keep_order(list(item.get("source_invoice_ids") or []))
        resolved_paths: list[str] = []
        resolved_count = 0
        unresolved_count = 0
        for source_id in source_ids:
            path_value = invoice_to_path.get(source_id) or local_pdf_map.get(source_id) or ""
            if path_value:
                resolved_count += 1
                if path_value not in resolved_paths:
                    resolved_paths.append(path_value)
            else:
                unresolved_count += 1
        previous_paths = unique_keep_order(list(item.get("invoice_paths_sources") or []))
        item["source_invoice_ids"] = source_ids
        item["invoice_paths_sources"] = unique_keep_order(previous_paths + resolved_paths)
        rows[index] = reorder_item(item)
        if previous_paths != item["invoice_paths_sources"]:
            stats["rows_changed"] += 1
        if item["invoice_paths_sources"]:
            stats["rows_with_paths"] += 1
            stats["paths_added"] += len(item["invoice_paths_sources"])
        stats["resolved_source_ids"] += resolved_count
        stats["unresolved_source_ids"] += unresolved_count
    return stats


def apply_paths_to_file(
    path: Path,
    invoice_to_path: dict[str, str],
    local_pdf_map: dict[str, str],
) -> dict[str, Any]:
    payload = load_json(path)
    file_stats: dict[str, Any] = {
        "file": path.name,
        "items": {},
        "a_valider": {},
    }
    for section in ("items", "a_valider"):
        rows = payload.get(section)
        if not isinstance(rows, list):
            continue
        section_stats = apply_paths_to_section(rows, invoice_to_path, local_pdf_map)
        file_stats[section] = section_stats

    payload.setdefault("meta", {})
    payload["meta"]["restore_invoice_paths_v1"] = {
        "applied_at": now_iso(),
        "source_db_factures": SOURCE_DBS,
        "invoice_form_rule": "invoice_form.form_common_core_ref.id -> core_profile.form_common_core.ingest.path / file.file_name",
        "local_pdf_rule": "source_invoice_ids de type pdf_* resolus via les metadonnees *_clean_v2",
        "items_changed": (file_stats.get("items") or {}).get("rows_changed", 0),
        "a_valider_changed": (file_stats.get("a_valider") or {}).get("rows_changed", 0),
    }
    dump_json(path, payload)
    return file_stats


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Restoration invoice paths v1",
        "",
        f"- `applied_at`: `{summary['applied_at']}`",
        f"- `files_updated`: `{summary['files_updated']}`",
        f"- `source_invoice_ids_total`: `{summary['source_invoice_ids_total']}`",
        f"- `invoice_ids_resolved_remote`: `{summary['invoice_ids_resolved_remote']}`",
        f"- `invoice_ids_resolved_local_pdf`: `{summary['invoice_ids_resolved_local_pdf']}`",
        f"- `invoice_ids_unresolved`: `{summary['invoice_ids_unresolved']}`",
        "",
        "## Files",
        "",
    ]
    for row in summary["files"]:
        item_stats = row.get("items") or {}
        pending_stats = row.get("a_valider") or {}
        lines.extend(
            [
                f"### {row['file']}",
                "",
                f"- `items_changed`: `{item_stats.get('rows_changed', 0)}`",
                f"- `items_with_paths`: `{item_stats.get('rows_with_paths', 0)}`",
                f"- `items_unresolved_source_ids`: `{item_stats.get('unresolved_source_ids', 0)}`",
                f"- `a_valider_changed`: `{pending_stats.get('rows_changed', 0)}`",
                f"- `a_valider_with_paths`: `{pending_stats.get('rows_with_paths', 0)}`",
                f"- `a_valider_unresolved_source_ids`: `{pending_stats.get('unresolved_source_ids', 0)}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    target_files = iter_target_files()
    local_pdf_map = build_local_pdf_path_map()
    all_source_ids = collect_all_source_invoice_ids(target_files)
    invoice_to_path, _invoice_to_core = fetch_invoice_to_path_map(all_source_ids)

    summary: dict[str, Any] = {
        "applied_at": now_iso(),
        "source_db_factures": SOURCE_DBS,
        "files_updated": len(target_files),
        "source_invoice_ids_total": len(all_source_ids),
        "invoice_ids_resolved_remote": len(invoice_to_path),
        "invoice_ids_resolved_local_pdf": len([sid for sid in all_source_ids if sid in local_pdf_map]),
        "invoice_ids_unresolved": len(
            [sid for sid in all_source_ids if sid not in invoice_to_path and sid not in local_pdf_map]
        ),
        "files": [],
    }

    for path in target_files:
        summary["files"].append(apply_paths_to_file(path, invoice_to_path, local_pdf_map))

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
