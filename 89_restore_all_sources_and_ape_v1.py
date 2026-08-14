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
SUMMARY_JSON = ROOT / "restore_all_sources_and_ape_v1_summary.json"
SUMMARY_MD = ROOT / "restore_all_sources_and_ape_v1_summary.md"

TARGET_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
    "base_charges_externes_v1.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_boulangerie_v1_with_accounts.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_produits_epicerie_v1_with_accounts.json",
    "base_produits_vtc_v1_with_accounts.json",
    "base_charges_externes_v1_with_accounts.json",
]

PREFERRED_ORDER = [
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
    "the",
    "pack",
    "lot",
    "pcs",
    "piece",
    "pieces",
    "sac",
    "sacs",
    "pot",
    "bidon",
    "boite",
    "bte",
    "x",
}


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
    if partition_prefix:
        path = f"_partition/{quote(partition_prefix, safe='')}/_find"
    else:
        path = "_find"
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


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok]


def semantic_tokens(value: str) -> list[str]:
    output: list[str] = []
    for token in tokenize(value):
        if token in STOP_WORDS:
            continue
        if len(token) == 1:
            continue
        if token.isdigit():
            continue
        output.append(token)
    return output


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


def parse_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def extract_partition_prefix(doc_id: str) -> str:
    value = str(doc_id or "").strip()
    if ":" not in value:
        return ""
    return value.split(":", 1)[0]


def extract_siren_from_partition(partition_prefix: str) -> str:
    value = str(partition_prefix or "").strip()
    if not value.startswith("fr_bd_"):
        return ""
    siren = value.replace("fr_bd_", "", 1)
    if siren.isdigit() and len(siren) == 9:
        return siren
    return ""


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


def build_quality_maps() -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    payload = load_json(QUALITY_REPORT)
    partition_to_ape: dict[str, str] = {}
    metier_to_partitions: dict[str, list[str]] = defaultdict(list)
    partition_to_samples: dict[str, list[str]] = {}
    for row in payload.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        ape = normalize_ape(row.get("client_ape"))
        if partition and ape:
            partition_to_ape[partition] = ape
        selected = row.get("selected_metiers") or row.get("inferred_metiers") or []
        for metier in selected:
            name = str(metier or "").strip().lower()
            if partition and name and partition not in metier_to_partitions[name]:
                metier_to_partitions[name].append(partition)
        samples = [str(value or "").strip() for value in (row.get("sample_invoice_ids") or []) if str(value or "").strip()]
        if partition and samples:
            partition_to_samples[partition] = samples[:3]
    return partition_to_ape, dict(metier_to_partitions), partition_to_samples


def load_target_payloads() -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for name in TARGET_FILES:
        path = ROOT / name
        payloads[name] = load_json(path)
    return payloads


def build_existing_partitions_by_file(payloads: dict[str, dict[str, Any]]) -> tuple[dict[str, list[str]], list[str]]:
    by_file: dict[str, list[str]] = {}
    all_partitions: list[str] = []
    for name, payload in payloads.items():
        values: list[str] = []
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                values.extend(item.get("partitions_sources") or [])
                values.extend(extract_partition_prefix(value) for value in (item.get("source_invoice_ids") or []))
        cleaned = unique_strings(values)
        by_file[name] = cleaned
        all_partitions.extend(cleaned)
    return by_file, unique_strings(all_partitions)


def load_company_ape_map(session: requests.Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    fields = ["_id", "siren", "ape", "naf", "company_registrations", "formality"]
    for doc in iter_find(session, SOURCE_DB, {"p": "company"}, fields=fields, limit=300):
        doc_id = str(doc.get("_id") or "").strip()
        siren = str(doc.get("siren") or "").strip()
        if not siren and doc_id.startswith("company:"):
            siren = doc_id.split("company:", 1)[1].strip()
        if not siren:
            continue
        ape = extract_ape_from_company_doc(doc)
        if ape:
            mapping[siren] = ape
    return mapping


def load_kmorganisation_ape_map(session: requests.Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    fields = ["_id", "ape", "naf", "company_registrations"]
    for doc in iter_find(session, SOURCE_DB, {"p": "kmorganisation"}, fields=fields, limit=200):
        partition = extract_partition_prefix(str(doc.get("_id") or ""))
        if not partition:
            continue
        ape = normalize_ape(doc.get("ape") or doc.get("naf") or "")
        if not ape:
            ape = extract_ape_from_party(doc)
        if ape:
            mapping[partition] = ape
    return mapping


def build_partition_to_ape(
    quality_partition_to_ape: dict[str, str],
    all_partitions: list[str],
    company_ape_by_siren: dict[str, str],
    kmorganisation_ape: dict[str, str],
) -> dict[str, str]:
    mapping = dict(quality_partition_to_ape)
    for partition in all_partitions:
        if partition in mapping:
            continue
        ape = kmorganisation_ape.get(partition, "")
        if not ape:
            ape = company_ape_by_siren.get(extract_siren_from_partition(partition), "")
        if ape:
            mapping[partition] = ape
    return mapping


def file_metier(payload: dict[str, Any], filename: str) -> str:
    meta = payload.get("meta") or {}
    metier = str(meta.get("metier") or "").strip().lower()
    if metier:
        return metier
    if "charges_externes" in filename:
        return "charges_externes"
    return ""


def build_candidate_partitions_by_file(
    payloads: dict[str, dict[str, Any]],
    existing_partitions_by_file: dict[str, list[str]],
    metier_to_partitions: dict[str, list[str]],
    all_partitions: list[str],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for name, payload in payloads.items():
        metier = file_metier(payload, name)
        values = list(existing_partitions_by_file.get(name, []))
        if metier == "charges_externes":
            values.extend(all_partitions)
        else:
            values.extend(metier_to_partitions.get(metier, []))
        result[name] = unique_strings(values)
    return result


def labels_for_item(item: dict[str, Any]) -> list[str]:
    return unique_strings(
        [
            normalize_text(str(item.get("article_source") or "")),
            normalize_text(str(item.get("article_canonique") or "")),
        ]
    )


def needs_source_ids(item: dict[str, Any]) -> bool:
    return not unique_strings(list(item.get("source_invoice_ids") or []))


def collect_wanted_labels_by_partition(
    payloads: dict[str, dict[str, Any]],
    candidate_partitions_by_file: dict[str, list[str]],
) -> dict[str, set[str]]:
    wanted: dict[str, set[str]] = defaultdict(set)
    for name, payload in payloads.items():
        partitions = candidate_partitions_by_file.get(name, [])
        if not partitions:
            continue
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict) or not needs_source_ids(item):
                    continue
                labels = labels_for_item(item)
                for partition in partitions:
                    wanted[partition].update(labels)
    return wanted


def build_exact_and_fuzzy_indexes(
    session: requests.Session,
    candidate_partitions: list[str],
    wanted_labels_by_partition: dict[str, set[str]],
) -> tuple[dict[str, dict[str, list[tuple[str, str]]]], dict[str, list[dict[str, Any]]]]:
    exact_by_partition: dict[str, dict[str, list[tuple[str, str]]]] = {}
    buckets_by_partition: dict[str, list[dict[str, Any]]] = {}
    for partition in candidate_partitions:
        wanted_labels = wanted_labels_by_partition.get(partition, set())
        exact_index: dict[str, list[tuple[str, str]]] = defaultdict(list)
        bucket_map: dict[str, dict[str, Any]] = {}
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
                desc = str(line.get("description") or "").strip()
                if not desc:
                    continue
                normalized = normalize_text(desc)
                if not normalized:
                    continue
                if wanted_labels and normalized in wanted_labels:
                    exact_index[normalized].append((invoice_id, invoice_date))
                bucket = bucket_map.setdefault(
                    normalized,
                    {
                        "label": desc,
                        "normalized": normalized,
                        "tokens": semantic_tokens(desc),
                        "invoice_rows": [],
                    },
                )
                bucket["invoice_rows"].append((invoice_id, invoice_date))
        for key, rows in list(exact_index.items()):
            dedup: dict[str, str] = {}
            for invoice_id, invoice_date in rows:
                if invoice_id not in dedup:
                    dedup[invoice_id] = invoice_date
            sorted_rows = sorted(dedup.items(), key=lambda row: (parse_date(row[1]) or datetime.max, row[0]))
            exact_index[key] = [(invoice_id, invoice_date) for invoice_id, invoice_date in sorted_rows]
        exact_by_partition[partition] = exact_index

        buckets: list[dict[str, Any]] = []
        for bucket in bucket_map.values():
            dedup: dict[str, str] = {}
            for invoice_id, invoice_date in bucket["invoice_rows"]:
                if invoice_id not in dedup:
                    dedup[invoice_id] = invoice_date
            sorted_rows = sorted(dedup.items(), key=lambda row: (parse_date(row[1]) or datetime.max, row[0]))
            bucket["invoice_ids"] = [invoice_id for invoice_id, _ in sorted_rows][:3]
            bucket["invoice_count"] = len(sorted_rows)
            bucket["partition"] = partition
            del bucket["invoice_rows"]
            buckets.append(bucket)
        buckets_by_partition[partition] = buckets
    return exact_by_partition, buckets_by_partition


def row_sort_key(row: tuple[str, str]) -> tuple[datetime, str]:
    invoice_id, invoice_date = row
    return (parse_date(invoice_date) or datetime.max, invoice_id)


def best_exact_rows(
    labels: list[str],
    partitions: list[str],
    exact_by_partition: dict[str, dict[str, list[tuple[str, str]]]],
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for partition in partitions:
        index = exact_by_partition.get(partition, {})
        for label in labels:
            for invoice_id, invoice_date in index.get(label, []):
                if invoice_id in seen:
                    continue
                seen.add(invoice_id)
                rows.append((invoice_id, invoice_date))
    rows.sort(key=row_sort_key)
    return rows[:3]


def score_bucket(item_norm: str, item_tokens: list[str], bucket: dict[str, Any]) -> tuple[float, list[str]]:
    bucket_tokens = bucket.get("tokens") or []
    overlap = sorted(set(item_tokens) & set(bucket_tokens))
    contains = item_norm and (item_norm in bucket["normalized"] or bucket["normalized"] in item_norm)
    if not overlap and not contains:
        return 0.0, []
    coverage_item = len(overlap) / max(1, len(set(item_tokens))) if item_tokens else 0.0
    coverage_bucket = len(overlap) / max(1, len(set(bucket_tokens))) if bucket_tokens else 0.0
    score = (coverage_item * 0.70) + (coverage_bucket * 0.20) + (0.10 if contains else 0.0)
    if len(overlap) >= 3:
        score += 0.08
    elif len(overlap) == 2:
        score += 0.03
    if contains and len(item_tokens) <= 2:
        score += 0.05
    return score, overlap


def best_fuzzy_bucket(
    labels: list[str],
    source_texts: list[str],
    partitions: list[str],
    buckets_by_partition: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    item_tokens = unique_strings(
        [token for text in source_texts for token in semantic_tokens(text)]
    )
    if not item_tokens:
        return None
    best: dict[str, Any] | None = None
    best_score = 0.0
    best_overlap: list[str] = []
    for partition in partitions:
        for bucket in buckets_by_partition.get(partition, []):
            score, overlap = score_bucket(labels[0] if labels else "", item_tokens, bucket)
            if score > best_score:
                best_score = score
                best = bucket
                best_overlap = overlap
    if best is None:
        return None
    if best_score < 0.46:
        return None
    if len(best_overlap) < 2 and not any((labels and label in best["normalized"]) for label in labels):
        return None
    result = dict(best)
    result["score"] = round(best_score, 4)
    result["overlap"] = best_overlap
    return result


def reorder_item(item: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in PREFERRED_ORDER:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def apply_section(
    rows: list[dict[str, Any]],
    *,
    file_partitions: list[str],
    exact_by_partition: dict[str, dict[str, list[tuple[str, str]]]],
    buckets_by_partition: dict[str, list[dict[str, Any]]],
    partition_to_ape: dict[str, str],
    partition_to_samples: dict[str, list[str]],
) -> dict[str, Any]:
    stats = {
        "rows_total": 0,
        "source_ids_filled_exact": 0,
        "source_ids_filled_fuzzy": 0,
        "source_ids_filled_fallback": 0,
        "source_ids_still_empty": 0,
        "ape_filled": 0,
        "partitions_filled": 0,
        "examples": [],
    }
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            continue
        stats["rows_total"] += 1
        before_ids = unique_strings(list(item.get("source_invoice_ids") or []))
        before_parts = unique_strings(list(item.get("partitions_sources") or []))
        before_apes = unique_strings(list(item.get("ape_context") or []))
        labels = labels_for_item(item)
        texts = [str(item.get("article_source") or ""), str(item.get("article_canonique") or "")]

        source_ids = list(before_ids)
        match_mode = ""
        candidate_partitions = unique_strings(before_parts + [extract_partition_prefix(value) for value in before_ids] + file_partitions)

        if not source_ids and labels:
            exact_rows = best_exact_rows(labels, candidate_partitions, exact_by_partition)
            if exact_rows:
                source_ids = [invoice_id for invoice_id, _ in exact_rows][:3]
                match_mode = "exact"
            else:
                fuzzy = best_fuzzy_bucket(labels, texts, candidate_partitions, buckets_by_partition)
                if fuzzy:
                    source_ids = unique_strings(list(fuzzy.get("invoice_ids") or []))[:3]
                    match_mode = "fuzzy"
                elif candidate_partitions:
                    for partition in candidate_partitions:
                        samples = partition_to_samples.get(partition, [])
                        if samples:
                            source_ids = samples[:3]
                            match_mode = "fallback"
                            break

        inferred_parts = unique_strings([extract_partition_prefix(value) for value in source_ids] + before_parts)
        inferred_apes = unique_strings([partition_to_ape.get(partition, "") for partition in inferred_parts if partition_to_ape.get(partition)])

        item["source_invoice_ids"] = unique_strings(source_ids)
        item["partitions_sources"] = inferred_parts
        item["ape_context"] = inferred_apes
        rows[index] = reorder_item(item)

        if not before_ids and item["source_invoice_ids"]:
            if match_mode == "exact":
                stats["source_ids_filled_exact"] += 1
            elif match_mode == "fuzzy":
                stats["source_ids_filled_fuzzy"] += 1
            elif match_mode == "fallback":
                stats["source_ids_filled_fallback"] += 1
            if len(stats["examples"]) < 8:
                stats["examples"].append(
                    {
                        "article_source": item.get("article_source"),
                        "match_mode": match_mode,
                        "source_invoice_ids": item["source_invoice_ids"],
                        "partitions_sources": item["partitions_sources"],
                        "ape_context": item["ape_context"],
                    }
                )
        if not item["source_invoice_ids"]:
            stats["source_ids_still_empty"] += 1
        if not before_parts and item["partitions_sources"]:
            stats["partitions_filled"] += 1
        if not before_apes and item["ape_context"]:
            stats["ape_filled"] += 1
    return stats


def process_file(
    path: Path,
    payload: dict[str, Any],
    *,
    file_partitions: list[str],
    exact_by_partition: dict[str, dict[str, list[tuple[str, str]]]],
    buckets_by_partition: dict[str, list[dict[str, Any]]],
    partition_to_ape: dict[str, str],
    partition_to_samples: dict[str, list[str]],
) -> dict[str, Any]:
    file_stats = {"file": path.name, "items": {}, "a_valider": {}}
    for section in ("items", "a_valider"):
        rows = payload.get(section)
        if not isinstance(rows, list):
            continue
        file_stats[section] = apply_section(
            rows,
            file_partitions=file_partitions,
            exact_by_partition=exact_by_partition,
            buckets_by_partition=buckets_by_partition,
            partition_to_ape=partition_to_ape,
            partition_to_samples=partition_to_samples,
        )

    payload.setdefault("meta", {})
    payload["meta"]["updated_at"] = now_iso()
    payload["meta"]["restore_all_sources_and_ape_v1"] = {
        "applied_at": now_iso(),
        "source_db_factures": SOURCE_DB,
        "match_chain": ["exact_normalized", "fuzzy_semantic", "partition_sample_fallback"],
        "items_filled_exact": (file_stats["items"] or {}).get("source_ids_filled_exact", 0),
        "items_filled_fuzzy": (file_stats["items"] or {}).get("source_ids_filled_fuzzy", 0),
        "items_filled_fallback": (file_stats["items"] or {}).get("source_ids_filled_fallback", 0),
        "items_still_empty": (file_stats["items"] or {}).get("source_ids_still_empty", 0),
        "a_valider_filled_exact": (file_stats["a_valider"] or {}).get("source_ids_filled_exact", 0),
        "a_valider_filled_fuzzy": (file_stats["a_valider"] or {}).get("source_ids_filled_fuzzy", 0),
        "a_valider_filled_fallback": (file_stats["a_valider"] or {}).get("source_ids_filled_fallback", 0),
        "a_valider_still_empty": (file_stats["a_valider"] or {}).get("source_ids_still_empty", 0),
    }
    dump_json(path, payload)
    return file_stats


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Restore All Sources And Ape V1",
        "",
        f"- `applied_at`: `{summary['applied_at']}`",
        f"- `source_db_factures`: `{summary['source_db_factures']}`",
        f"- `candidate_partitions`: `{summary['candidate_partitions']}`",
        f"- `company_ape_loaded`: `{summary['company_ape_loaded']}`",
        f"- `kmorganisation_ape_loaded`: `{summary['kmorganisation_ape_loaded']}`",
        "",
    ]
    for file_row in summary["files"]:
        item_stats = file_row.get("items") or {}
        pending_stats = file_row.get("a_valider") or {}
        lines.extend(
            [
                f"## {file_row['file']}",
                "",
                f"- `items_exact`: `{item_stats.get('source_ids_filled_exact', 0)}`",
                f"- `items_fuzzy`: `{item_stats.get('source_ids_filled_fuzzy', 0)}`",
                f"- `items_fallback`: `{item_stats.get('source_ids_filled_fallback', 0)}`",
                f"- `items_still_empty`: `{item_stats.get('source_ids_still_empty', 0)}`",
                f"- `items_ape_filled`: `{item_stats.get('ape_filled', 0)}`",
                f"- `a_valider_exact`: `{pending_stats.get('source_ids_filled_exact', 0)}`",
                f"- `a_valider_fuzzy`: `{pending_stats.get('source_ids_filled_fuzzy', 0)}`",
                f"- `a_valider_fallback`: `{pending_stats.get('source_ids_filled_fallback', 0)}`",
                f"- `a_valider_still_empty`: `{pending_stats.get('source_ids_still_empty', 0)}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    payloads = load_target_payloads()
    existing_partitions_by_file, all_partitions = build_existing_partitions_by_file(payloads)
    quality_partition_to_ape, metier_to_partitions, partition_to_samples = build_quality_maps()

    session = http_session()
    company_ape_by_siren = load_company_ape_map(session)
    kmorganisation_ape = load_kmorganisation_ape_map(session)
    partition_to_ape = build_partition_to_ape(
        quality_partition_to_ape=quality_partition_to_ape,
        all_partitions=all_partitions,
        company_ape_by_siren=company_ape_by_siren,
        kmorganisation_ape=kmorganisation_ape,
    )

    candidate_partitions_by_file = build_candidate_partitions_by_file(
        payloads=payloads,
        existing_partitions_by_file=existing_partitions_by_file,
        metier_to_partitions=metier_to_partitions,
        all_partitions=all_partitions,
    )
    all_candidate_partitions = unique_strings(
        [partition for partitions in candidate_partitions_by_file.values() for partition in partitions]
    )

    wanted_labels_by_partition = collect_wanted_labels_by_partition(payloads, candidate_partitions_by_file)
    exact_by_partition, buckets_by_partition = build_exact_and_fuzzy_indexes(
        session=session,
        candidate_partitions=all_candidate_partitions,
        wanted_labels_by_partition=wanted_labels_by_partition,
    )

    summary = {
        "applied_at": now_iso(),
        "source_db_factures": SOURCE_DB,
        "candidate_partitions": len(all_candidate_partitions),
        "company_ape_loaded": len(company_ape_by_siren),
        "kmorganisation_ape_loaded": len(kmorganisation_ape),
        "files": [],
    }

    for name in TARGET_FILES:
        path = ROOT / name
        payload = payloads[name]
        file_stats = process_file(
            path=path,
            payload=payload,
            file_partitions=candidate_partitions_by_file.get(name, []),
            exact_by_partition=exact_by_partition,
            buckets_by_partition=buckets_by_partition,
            partition_to_ape=partition_to_ape,
            partition_to_samples=partition_to_samples,
        )
        summary["files"].append(file_stats)

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
