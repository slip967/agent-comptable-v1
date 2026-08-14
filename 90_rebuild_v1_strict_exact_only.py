#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import unicodedata
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
SOURCE_DB = os.getenv("DB_FACTURES", "abt3").strip() or "abt3"

QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_JSON = ROOT / "strict_exact_only_v1_summary.json"
SUMMARY_MD = ROOT / "strict_exact_only_v1_summary.md"

BASE_TARGETS = [
    "base_produits_boucherie_v1.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
    "base_charges_externes_v1.json",
]
WITH_ACCOUNTS_TARGETS = [name.replace(".json", "_with_accounts.json") for name in BASE_TARGETS]
ALL_TARGETS = BASE_TARGETS + WITH_ACCOUNTS_TARGETS

STOP_WORDS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "a",
    "au",
    "aux",
    "et",
    "en",
    "sur",
    "pour",
    "par",
    "avec",
    "sans",
    "dans",
    "lot",
    "trim",
    "x",
}

FIELD_ORDER = [
    "article_source",
    "article_canonique",
    "mots_cles",
    "ids_factures_sources",
    "source_invoice_ids",
    "invoice_paths_sources",
    "ape_context",
    "partitions_sources",
    "compte_comptable",
    "taux_tva",
    "categorie",
    "sous_categorie",
    "type_fournisseur",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def couch_request(session: requests.Session, db_name: str, method: str, path: str = "", **kwargs) -> dict[str, Any]:
    if path:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}"
    response = session.request(method, url, timeout=180, **kwargs)
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
    path = f"_partition/{quote(partition_prefix, safe='')}/_find" if partition_prefix else "_find"
    while True:
        payload: dict[str, Any] = {"selector": selector, "limit": limit}
        if fields:
            payload["fields"] = fields
        if bookmark:
            payload["bookmark"] = bookmark
        result = couch_request(session, db_name, "POST", path, json=payload)
        docs = result.get("docs") or []
        if not docs:
            break
        for doc in docs:
            yield doc
        next_bookmark = str(result.get("bookmark") or "").strip()
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def unique_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def extract_partition_prefix(doc_id: str) -> str:
    text = str(doc_id or "").strip()
    return text.split(":", 1)[0] if ":" in text else ""


def normalize_ape(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "").replace(".", "")
    if not text:
        return ""
    match = re.search(r"\b\d{4}[A-Z]\b", text)
    if match:
        return match.group(0)
    if re.fullmatch(r"\d{4}[A-Z]", text):
        return text
    return ""


def unwrap_doc_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return unwrap_doc_value(value.get("value"))
    return value


def extract_ape_from_party(party: Any) -> str:
    if not isinstance(party, dict):
        return ""
    direct = normalize_ape(unwrap_doc_value(party.get("ape")) or unwrap_doc_value(party.get("naf")) or "")
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


def extract_ape_from_company_doc(doc: dict[str, Any]) -> str:
    ape = normalize_ape(doc.get("ape") or doc.get("naf") or "")
    if ape:
        return ape
    formality = doc.get("formality") or {}
    etab = formality.get("content") or {}
    etab = etab.get("personneMorale") or etab.get("personnePhysique") or etab
    if isinstance(etab, dict):
        ape = normalize_ape((etab.get("etablissementPrincipal") or {}).get("codeApe") or "")
        if ape:
            return ape
    return extract_ape_from_party(doc)


def extract_siren_from_partition(partition_prefix: str) -> str:
    value = str(partition_prefix or "").strip()
    if not value.startswith("fr_bd_"):
        return ""
    siren = value.replace("fr_bd_", "", 1)
    return siren if siren.isdigit() and len(siren) == 9 else ""


def tokenize_keywords(*values: str) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        for token in normalize_text(value).split():
            if not token or token in STOP_WORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            output.append(token)
    return output[:12]


def build_partition_and_ape_maps(session: requests.Session) -> tuple[dict[str, str], dict[str, list[str]]]:
    quality = load_json(QUALITY_REPORT)
    partition_to_ape: dict[str, str] = {}
    metier_to_partitions: dict[str, list[str]] = defaultdict(list)
    for row in quality.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        ape = normalize_ape(row.get("client_ape"))
        if partition and ape:
            partition_to_ape[partition] = ape
        for metier in (row.get("selected_metiers") or row.get("inferred_metiers") or []):
            name = str(metier or "").strip().lower()
            if partition and name and partition not in metier_to_partitions[name]:
                metier_to_partitions[name].append(partition)

    company_ape_by_siren: dict[str, str] = {}
    for doc in iter_find(session, SOURCE_DB, {"p": "company"}, fields=["_id", "siren", "ape", "naf", "company_registrations", "formality"], limit=300):
        doc_id = str(doc.get("_id") or "").strip()
        siren = str(doc.get("siren") or "").strip()
        if not siren and doc_id.startswith("company:"):
            siren = doc_id.split("company:", 1)[1].strip()
        if not siren:
            continue
        ape = extract_ape_from_company_doc(doc)
        if ape:
            company_ape_by_siren[siren] = ape

    for partition in set(partition_to_ape) | {f"fr_bd_{siren}" for siren in company_ape_by_siren}:
        if partition_to_ape.get(partition):
            continue
        ape = company_ape_by_siren.get(extract_siren_from_partition(partition), "")
        if ape:
            partition_to_ape[partition] = ape

    return partition_to_ape, dict(metier_to_partitions)


def load_local_pdf_exact_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    exact_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    path_by_source_id: dict[str, str] = {}
    for path in sorted(ROOT.glob("base_*_clean_v2.json")):
        payload = load_json(path)
        meta = payload.get("meta") or {}
        source_folder = ""
        pdf_lookup: dict[str, str] = {}
        for value in meta.values():
            if not isinstance(value, dict):
                continue
            if value.get("source_folder") and isinstance(value.get("pdfs"), list):
                source_folder = str(value.get("source_folder") or "").strip()
                for pdf in value.get("pdfs") or []:
                    if not isinstance(pdf, dict):
                        continue
                    relative_path = str(pdf.get("relative_path") or "").strip()
                    if not relative_path:
                        continue
                    token = relative_path
                    normalized = unicodedata.normalize("NFKD", token)
                    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
                    normalized = re.sub(r"[^0-9A-Za-z]+", "_", normalized).strip("_")
                    normalized = re.sub(r"_+", "_", normalized)
                    pdf_lookup[f"pdf_{normalized}"] = str(Path(source_folder) / Path(relative_path))
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                source_ids = [str(value or "").strip() for value in (item.get("source_invoice_ids") or []) if ":pdf_" in str(value or "")]
                if not source_ids:
                    continue
                raw_source = str(item.get("article_source") or "").strip()
                normalized_values = unique_strings(
                    [
                        normalize_text(raw_source),
                        normalize_text(str(item.get("article_canonique") or "")),
                    ]
                )
                for source_id in source_ids:
                    suffix = source_id.split(":", 1)[1]
                    if suffix in pdf_lookup:
                        path_by_source_id[source_id] = pdf_lookup[suffix]
                for normalized in normalized_values:
                    if not normalized:
                        continue
                    exact_index[normalized].append(
                        {
                            "raw_source": raw_source,
                            "source_ids": source_ids[:3],
                        }
                    )
    return exact_index, path_by_source_id


def build_remote_exact_index(
    session: requests.Session,
    candidate_partitions: list[str],
    wanted_labels_by_partition: dict[str, set[str]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for partition in candidate_partitions:
        wanted = wanted_labels_by_partition.get(partition, set())
        bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if not wanted:
            index[partition] = {}
            continue
        for doc in iter_find(
            session,
            SOURCE_DB,
            {"p": "invoice_form"},
            fields=["_id", "invoice_date", "line_items"],
            partition_prefix=partition,
            limit=500,
        ):
            invoice_id = str(doc.get("_id") or "").strip()
            invoice_date = str(doc.get("invoice_date") or "").strip()
            for line in doc.get("line_items") or []:
                if not isinstance(line, dict):
                    continue
                raw_desc = str(line.get("description") or "").strip()
                normalized = normalize_text(raw_desc)
                if not normalized or normalized not in wanted:
                    continue
                bucket[normalized].append(
                    {
                        "invoice_id": invoice_id,
                        "invoice_date": invoice_date,
                        "raw_source": raw_desc,
                    }
                )
        index[partition] = bucket
    return index


def collect_wanted_labels(payloads: dict[str, dict[str, Any]], candidate_partitions_by_file: dict[str, list[str]]) -> dict[str, set[str]]:
    wanted: dict[str, set[str]] = defaultdict(set)
    for name, payload in payloads.items():
        partitions = candidate_partitions_by_file.get(name, [])
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                labels = unique_strings(
                    [
                        normalize_text(str(item.get("article_source") or "")),
                        normalize_text(str(item.get("article_canonique") or "")),
                    ]
                )
                for partition in partitions:
                    wanted[partition].update(label for label in labels if label)
    return wanted


def fetch_remote_invoice_paths(session: requests.Session, source_ids: list[str]) -> dict[str, str]:
    invoice_ids = [value for value in unique_strings(source_ids) if ":pdf_" not in value]
    invoice_to_core: dict[str, str] = {}
    for start in range(0, len(invoice_ids), 200):
        chunk = invoice_ids[start : start + 200]
        result = couch_request(session, SOURCE_DB, "POST", "_all_docs?include_docs=true", json={"keys": chunk})
        for row in result.get("rows", []):
            doc = row.get("doc") or {}
            if str(doc.get("p") or "").strip() != "invoice_form":
                continue
            invoice_id = str(row.get("id") or "").strip()
            core_id = str(((doc.get("form_common_core_ref") or {}).get("id")) or "").strip()
            if invoice_id and core_id:
                invoice_to_core[invoice_id] = core_id
    core_to_path: dict[str, str] = {}
    core_ids = unique_strings(list(invoice_to_core.values()))
    for start in range(0, len(core_ids), 200):
        chunk = core_ids[start : start + 200]
        result = couch_request(session, SOURCE_DB, "POST", "_all_docs?include_docs=true", json={"keys": chunk})
        for row in result.get("rows", []):
            doc = row.get("doc") or {}
            core_id = str(row.get("id") or "").strip()
            form_common_core = doc.get("form_common_core") or {}
            ingest = form_common_core.get("ingest") or {}
            file_node = form_common_core.get("file") or {}
            path_value = str(ingest.get("path") or "").strip() or str(file_node.get("file_name") or "").strip()
            if core_id and path_value:
                core_to_path[core_id] = path_value
    return {invoice_id: core_to_path.get(core_id, "") for invoice_id, core_id in invoice_to_core.items() if core_to_path.get(core_id)}


def choose_best_raw_source(rows: list[dict[str, Any]]) -> str:
    counter = Counter(str(row.get("raw_source") or "").strip() for row in rows if str(row.get("raw_source") or "").strip())
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def build_strict_item(
    original: dict[str, Any],
    *,
    matched_rows: list[dict[str, Any]],
    pdf_matches: list[dict[str, Any]],
    partition_to_ape: dict[str, str],
    remote_path_by_id: dict[str, str],
    local_pdf_path_by_id: dict[str, str],
) -> dict[str, Any]:
    raw_source = choose_best_raw_source(matched_rows) if matched_rows else ""
    if not raw_source and pdf_matches:
        raw_source = str(pdf_matches[0].get("raw_source") or "").strip()
    source_ids = unique_strings(
        [str(row.get("invoice_id") or "").strip() for row in matched_rows]
        + [source_id for match in pdf_matches for source_id in (match.get("source_ids") or [])]
    )[:3]
    partitions = unique_strings([extract_partition_prefix(value) for value in source_ids])[:3]
    ape_context = unique_strings([partition_to_ape.get(partition, "") for partition in partitions if partition_to_ape.get(partition)])
    invoice_paths = unique_strings(
        [remote_path_by_id.get(source_id, "") for source_id in source_ids if remote_path_by_id.get(source_id)]
        + [local_pdf_path_by_id.get(source_id, "") for source_id in source_ids if local_pdf_path_by_id.get(source_id)]
    )[:3]

    article_source = raw_source or str(original.get("article_source") or "").strip()
    article_canonique = normalize_text(article_source)
    strict_item = {
        "article_source": article_source,
        "article_canonique": article_canonique,
        "mots_cles": tokenize_keywords(article_source, article_canonique),
        "ids_factures_sources": source_ids,
        "source_invoice_ids": source_ids,
        "invoice_paths_sources": invoice_paths,
        "ape_context": ape_context,
        "partitions_sources": partitions,
        "compte_comptable": str(original.get("compte_comptable") or "").strip(),
        "taux_tva": original.get("taux_tva", original.get("tva_rate")),
        "categorie": str(original.get("categorie") or "").strip(),
        "sous_categorie": str(original.get("sous_categorie") or "").strip(),
        "type_fournisseur": str(original.get("type_fournisseur") or original.get("fournisseur_type") or "").strip(),
    }
    ordered: dict[str, Any] = {}
    for key in FIELD_ORDER:
        ordered[key] = strict_item.get(key)
    return ordered


def derive_candidate_partitions(
    name: str,
    payload: dict[str, Any],
    metier_to_partitions: dict[str, list[str]],
) -> list[str]:
    metier = str((payload.get("meta") or {}).get("metier") or "").strip().lower()
    values: list[str] = []
    for section in ("items", "a_valider"):
        for item in payload.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            values.extend(item.get("partitions_sources") or [])
            values.extend(extract_partition_prefix(value) for value in (item.get("source_invoice_ids") or []))
    values.extend(metier_to_partitions.get(metier, []))
    return unique_strings(values)


def process_file(
    path: Path,
    payload: dict[str, Any],
    *,
    candidate_partitions: list[str],
    remote_exact_index: dict[str, dict[str, list[dict[str, Any]]]],
    local_pdf_exact_index: dict[str, list[dict[str, Any]]],
    partition_to_ape: dict[str, str],
    remote_path_by_id: dict[str, str],
    local_pdf_path_by_id: dict[str, str],
) -> dict[str, Any]:
    file_stats = {
        "file": path.name,
        "items_before": len(payload.get("items") or []),
        "items_after": 0,
        "a_valider_before": len(payload.get("a_valider") or []),
        "a_valider_after": 0,
        "dropped_no_exact_match": 0,
        "kept_remote_exact": 0,
        "kept_local_pdf_exact": 0,
        "examples_dropped": [],
    }
    new_sections: dict[str, list[dict[str, Any]]] = {"items": [], "a_valider": []}
    for section in ("items", "a_valider"):
        for item in payload.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            labels = unique_strings(
                [
                    normalize_text(str(item.get("article_source") or "")),
                    normalize_text(str(item.get("article_canonique") or "")),
                ]
            )
            matched_rows: list[dict[str, Any]] = []
            for partition in candidate_partitions:
                bucket = remote_exact_index.get(partition, {})
                for label in labels:
                    matched_rows.extend(bucket.get(label, []))
            pdf_matches: list[dict[str, Any]] = []
            for label in labels:
                pdf_matches.extend(local_pdf_exact_index.get(label, []))

            if not matched_rows and not pdf_matches:
                file_stats["dropped_no_exact_match"] += 1
                if len(file_stats["examples_dropped"]) < 8:
                    file_stats["examples_dropped"].append(str(item.get("article_source") or ""))
                continue

            strict_item = build_strict_item(
                item,
                matched_rows=matched_rows,
                pdf_matches=pdf_matches,
                partition_to_ape=partition_to_ape,
                remote_path_by_id=remote_path_by_id,
                local_pdf_path_by_id=local_pdf_path_by_id,
            )
            new_sections[section].append(strict_item)
            if matched_rows:
                file_stats["kept_remote_exact"] += 1
            elif pdf_matches:
                file_stats["kept_local_pdf_exact"] += 1

    file_stats["items_after"] = len(new_sections["items"])
    file_stats["a_valider_after"] = len(new_sections["a_valider"])

    original_meta = payload.get("meta") or {}
    new_meta = {
        "profile_id": str(original_meta.get("profile_id") or path.stem).strip(),
        "metier": str(original_meta.get("metier") or "").strip().lower(),
        "generated_at": now_iso(),
        "items_count": len(new_sections["items"]),
        "accounts_alignment_from": str(original_meta.get("accounts_alignment_from") or "").strip(),
        "selector": "strict_exact_only: invoice_form.line_items.description == article_source/article_canonique (normalise) or exact local pdf OCR source",
        "source_client": str(original_meta.get("source_client") or original_meta.get("client_siren") or "multi").strip(),
        "updated": now_iso(),
    }

    new_payload: dict[str, Any] = {
        "meta": new_meta,
        "items": new_sections["items"],
    }
    if new_sections["a_valider"]:
        new_payload["a_valider"] = new_sections["a_valider"]
    dump_json(path, new_payload)
    return file_stats


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Strict Exact Only V1",
        "",
        f"- `applied_at`: `{summary['applied_at']}`",
        f"- `source_db_factures`: `{summary['source_db_factures']}`",
        "",
    ]
    for row in summary["files"]:
        lines.extend(
            [
                f"## {row['file']}",
                "",
                f"- `items_before`: `{row['items_before']}`",
                f"- `items_after`: `{row['items_after']}`",
                f"- `a_valider_before`: `{row['a_valider_before']}`",
                f"- `a_valider_after`: `{row['a_valider_after']}`",
                f"- `kept_remote_exact`: `{row['kept_remote_exact']}`",
                f"- `kept_local_pdf_exact`: `{row['kept_local_pdf_exact']}`",
                f"- `dropped_no_exact_match`: `{row['dropped_no_exact_match']}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    payloads = {name: load_json(ROOT / name) for name in ALL_TARGETS}
    session = http_session()
    partition_to_ape, metier_to_partitions = build_partition_and_ape_maps(session)
    local_pdf_exact_index, local_pdf_path_by_id = load_local_pdf_exact_index()
    candidate_partitions_by_file = {
        name: derive_candidate_partitions(name, payload, metier_to_partitions)
        for name, payload in payloads.items()
    }
    wanted_labels_by_partition = collect_wanted_labels(payloads, candidate_partitions_by_file)
    remote_exact_index = build_remote_exact_index(
        session,
        candidate_partitions=unique_strings([part for parts in candidate_partitions_by_file.values() for part in parts]),
        wanted_labels_by_partition=wanted_labels_by_partition,
    )

    all_source_ids: list[str] = []
    for payload in payloads.values():
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if isinstance(item, dict):
                    all_source_ids.extend(item.get("source_invoice_ids") or [])
    remote_path_by_id = fetch_remote_invoice_paths(session, all_source_ids)

    summary = {
        "applied_at": now_iso(),
        "source_db_factures": SOURCE_DB,
        "files": [],
    }
    for name in ALL_TARGETS:
        path = ROOT / name
        summary["files"].append(
            process_file(
                path,
                payloads[name],
                candidate_partitions=candidate_partitions_by_file[name],
                remote_exact_index=remote_exact_index,
                local_pdf_exact_index=local_pdf_exact_index,
                partition_to_ape=partition_to_ape,
                remote_path_by_id=remote_path_by_id,
                local_pdf_path_by_id=local_pdf_path_by_id,
            )
        )

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
