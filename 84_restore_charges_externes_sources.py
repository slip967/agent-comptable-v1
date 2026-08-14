#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
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
DEFAULT_DB = os.getenv("DB_FACTURES", "abt3")

BASE_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
CHARGES_PACK = ROOT / "candidate_packs_metier" / "charges_externes_top_500_cleaned_candidates.json"
SUMMARY_MD = ROOT / "restauration_charges_externes_sources_summary.md"
SUMMARY_JSON = ROOT / "restauration_charges_externes_sources_summary.json"

PREFERRED_ORDER = [
    "article_source",
    "article_canonique",
    "mots_cles",
    "ids_factures_sources",
    "source_invoice_ids",
    "contexte_ape",
    "ape_context",
    "partitions_sources",
    "source_partition_ids",
    "compte_comptable",
    "taux_tva",
    "tva_rate",
    "categorie",
    "sous_categorie",
    "type_fournisseur",
    "fournisseur_type",
]

GLOBAL_KEYWORDS = {
    "abonnement",
    "consommation",
    "eau",
    "gaz",
    "electricite",
    "energie",
    "loyer",
    "parking",
    "entretien",
    "maintenance",
    "forfait",
    "mobile",
    "telecom",
    "telephone",
    "internet",
    "bbox",
    "assurance",
    "cotisation",
    "frais",
    "banque",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


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


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def build_partition_registry() -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    payload = load_json(QUALITY_REPORT)
    all_partitions: list[str] = []
    partition_to_ape: dict[str, str] = {}
    ape_to_partitions: dict[str, list[str]] = defaultdict(list)
    for row in payload.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        ape = str(row.get("client_ape") or "").strip()
        if not partition:
            continue
        all_partitions.append(partition)
        if ape:
            partition_to_ape[partition] = ape
            if partition not in ape_to_partitions[ape]:
                ape_to_partitions[ape].append(partition)
    return unique_strings(all_partitions), partition_to_ape, dict(ape_to_partitions)


def build_candidate_partition_map() -> dict[str, list[str]]:
    payload = load_json(CHARGES_PACK)
    mapping: dict[str, list[str]] = {}
    for entry in payload.get("top_all", []):
        key = normalize_text(str(entry.get("article_source") or ""))
        if not key:
            continue
        mapping[key] = unique_strings(list(entry.get("partitions") or []))
    return mapping


def collect_needed_labels(payload: dict) -> set[str]:
    labels: set[str] = set()
    for section in ["items", "a_valider"]:
        for item in payload.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            if (
                item.get("ids_factures_sources") not in ([], None, "")
                and item.get("source_invoice_ids") not in ([], None, "")
                and item.get("contexte_ape") not in ([], None, "")
                and item.get("ape_context") not in ([], None, "")
            ):
                continue
            for raw in [item.get("article_source"), item.get("article_canonique")]:
                key = normalize_text(str(raw or ""))
                if key:
                    labels.add(key)
    return labels


def build_line_item_index(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
    wanted_labels: set[str],
) -> dict[str, list[tuple[str, str]]]:
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
    selector = {"p": "invoice_form"}
    bookmark = None

    index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()

    while True:
        payload = {
            "selector": selector,
            "fields": ["_id", "invoice_date", "line_items"],
            "limit": 500,
        }
        if bookmark:
            payload["bookmark"] = bookmark

        response = session.post(endpoint, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        docs = data.get("docs") or []
        if not docs:
            break

        for doc in docs:
            invoice_id = str(doc.get("_id") or "").strip()
            invoice_date = str(doc.get("invoice_date") or "").strip()
            for line in doc.get("line_items") or []:
                if not isinstance(line, dict):
                    continue
                desc = str(line.get("description") or "").strip()
                key = normalize_text(desc)
                if not key or key not in wanted_labels:
                    continue
                pair = (key, invoice_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                index[key].append((invoice_id, invoice_date))

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark

    return index


def reorder_item(item: dict) -> dict:
    ordered: dict = {}
    for key in PREFERRED_ORDER:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def infer_search_partitions(
    item: dict,
    candidate_partition_map: dict[str, list[str]],
    ape_to_partitions: dict[str, list[str]],
    all_partitions: list[str],
) -> list[str]:
    current_partitions = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
    if current_partitions:
        return current_partitions

    labels = [
        normalize_text(str(item.get("article_source") or "")),
        normalize_text(str(item.get("article_canonique") or "")),
    ]
    candidate_partitions: list[str] = []
    for label in labels:
        candidate_partitions.extend(candidate_partition_map.get(label, []))
    candidate_partitions = unique_strings(candidate_partitions)
    if candidate_partitions:
        return candidate_partitions

    current_apes = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))
    partitions_from_ape: list[str] = []
    for ape in current_apes:
        partitions_from_ape.extend(ape_to_partitions.get(ape, []))
    partitions_from_ape = unique_strings(partitions_from_ape)
    if partitions_from_ape:
        return partitions_from_ape

    words = set(tokenize(str(item.get("article_source") or item.get("article_canonique") or "")))
    if words & GLOBAL_KEYWORDS:
        return all_partitions

    return []


def restore_item(
    item: dict,
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]],
    candidate_partition_map: dict[str, list[str]],
    partition_to_ape: dict[str, str],
    ape_to_partitions: dict[str, list[str]],
    all_partitions: list[str],
    max_ids: int,
) -> tuple[dict, dict]:
    before_ids = unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
    before_apes = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))
    before_partitions = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
    current_apes = before_apes[:]

    labels = unique_strings(
        [
            normalize_text(str(item.get("article_source") or "")),
            normalize_text(str(item.get("article_canonique") or "")),
        ]
    )

    candidate_partitions: list[str] = []
    for label in labels:
        candidate_partitions.extend(candidate_partition_map.get(label, []))
    candidate_partitions = unique_strings(candidate_partitions)

    partitions_from_ape: list[str] = []
    for ape in current_apes:
        partitions_from_ape.extend(ape_to_partitions.get(ape, []))
    partitions_from_ape = unique_strings(partitions_from_ape)

    search_partitions = infer_search_partitions(item, candidate_partition_map, ape_to_partitions, all_partitions)

    matched_rows: list[tuple[str, str, str]] = []
    for partition in search_partitions:
        label_index = partition_indexes.get(partition, {})
        for label in labels:
            for invoice_id, invoice_date in label_index.get(label, []):
                matched_rows.append((partition, invoice_id, invoice_date))

    uniq_dates: dict[str, str] = {}
    matched_partitions: list[str] = []
    for partition, invoice_id, invoice_date in matched_rows:
        if invoice_id not in uniq_dates:
            uniq_dates[invoice_id] = invoice_date
        if partition not in matched_partitions:
            matched_partitions.append(partition)
    sorted_rows = sorted(
        uniq_dates.items(),
        key=lambda row: (parse_date(row[1]) or datetime.max, row[0]),
    )
    found_ids = [row[0] for row in sorted_rows]

    merged_ids = unique_strings(before_ids + found_ids)[:max_ids]
    id_partitions = [invoice_id.split(":", 1)[0] for invoice_id in merged_ids if ":" in invoice_id]
    inferred_partitions = unique_strings(before_partitions + candidate_partitions + partitions_from_ape + matched_partitions + id_partitions)
    inferred_apes = before_apes[:] if before_apes else unique_strings(
        [partition_to_ape[p] for p in inferred_partitions if partition_to_ape.get(p)]
    )

    new_item = dict(item)
    new_item["ids_factures_sources"] = merged_ids
    new_item["source_invoice_ids"] = merged_ids
    new_item["partitions_sources"] = inferred_partitions
    new_item["source_partition_ids"] = inferred_partitions
    new_item["contexte_ape"] = inferred_apes
    new_item["ape_context"] = inferred_apes

    return reorder_item(new_item), {
        "ids_added": max(0, len(merged_ids) - len(before_ids)),
        "partitions_added": max(0, len(inferred_partitions) - len(before_partitions)),
        "ape_added": max(0, len(inferred_apes) - len(before_apes)),
        "search_partitions_count": len(search_partitions),
    }


def process_file(
    path: Path,
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]],
    candidate_partition_map: dict[str, list[str]],
    partition_to_ape: dict[str, str],
    ape_to_partitions: dict[str, list[str]],
    all_partitions: list[str],
    max_ids: int,
    db_factures: str,
    dry_run: bool,
) -> dict:
    payload = load_json(path)
    meta = payload.get("meta") or {}
    file_summary = {
        "file": path.name,
        "items_changed": 0,
        "a_valider_changed": 0,
        "invoice_ids_added": 0,
        "partitions_filled": 0,
        "ape_filled": 0,
        "examples": [],
    }

    for section in ["items", "a_valider"]:
        source_rows = payload.get(section) or []
        updated_rows = []
        for item in source_rows:
            if not isinstance(item, dict):
                updated_rows.append(item)
                continue
            before_ids = unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
            before_apes = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))
            before_partitions = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))

            new_item, stats = restore_item(
                item,
                partition_indexes=partition_indexes,
                candidate_partition_map=candidate_partition_map,
                partition_to_ape=partition_to_ape,
                ape_to_partitions=ape_to_partitions,
                all_partitions=all_partitions,
                max_ids=max_ids,
            )

            after_ids = unique_strings(list(new_item.get("ids_factures_sources") or []))
            after_apes = unique_strings(list(new_item.get("contexte_ape") or []))
            after_partitions = unique_strings(list(new_item.get("partitions_sources") or []))

            changed = after_ids != before_ids or after_apes != before_apes or after_partitions != before_partitions
            if changed:
                if section == "items":
                    file_summary["items_changed"] += 1
                else:
                    file_summary["a_valider_changed"] += 1
                file_summary["invoice_ids_added"] += stats["ids_added"]
                file_summary["partitions_filled"] += stats["partitions_added"]
                file_summary["ape_filled"] += stats["ape_added"]
                if len(file_summary["examples"]) < 8:
                    file_summary["examples"].append(
                        {
                            "section": section,
                            "article_source": item.get("article_source"),
                            "before_ids": before_ids,
                            "after_ids": after_ids,
                            "before_ape": before_apes,
                            "after_ape": after_apes,
                            "before_partitions": before_partitions,
                            "after_partitions": after_partitions,
                        }
                    )

            updated_rows.append(new_item)

        payload[section] = updated_rows

    meta["updated_at"] = now_iso()
    meta["restauration_charges_externes_sources_v2"] = {
        "applied_at": now_iso(),
        "source_db_factures": db_factures,
        "match_rule": "invoice_form.line_items.description == article_source/article_canonique (normalise, exact)",
        "max_ids": max_ids,
        "items_changed": file_summary["items_changed"],
        "a_valider_changed": file_summary["a_valider_changed"],
        "invoice_ids_added": file_summary["invoice_ids_added"],
        "partitions_filled": file_summary["partitions_filled"],
        "ape_filled": file_summary["ape_filled"],
    }
    payload["meta"] = meta

    if not dry_run:
        dump_json(path, payload)

    return file_summary


def write_reports(summary: dict) -> None:
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Restauration Charges Externes Sources",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- dry_run: `{str(summary['dry_run']).lower()}`",
        f"- source_db_factures: `{summary['source_db_factures']}`",
        f"- items_changed: `{summary['items_changed']}`",
        f"- a_valider_changed: `{summary['a_valider_changed']}`",
        f"- invoice_ids_added: `{summary['invoice_ids_added']}`",
        "",
    ]
    for file_summary in summary["files"]:
        lines.append(
            f"- {file_summary['file']}: items_changed=`{file_summary['items_changed']}` "
            f"a_valider_changed=`{file_summary['a_valider_changed']}` "
            f"ids_added=`{file_summary['invoice_ids_added']}` "
            f"ape_filled=`{file_summary['ape_filled']}`"
        )
    lines.append("")
    lines.append("Exemples :")
    for file_summary in summary["files"]:
        for example in file_summary["examples"][:4]:
            lines.append(f"- `{example['article_source']}` ({example['section']})")
            lines.append(f"  avant_ids=`{example['before_ids']}`")
            lines.append(f"  apres_ids=`{example['after_ids']}`")
            lines.append(f"  avant_ape=`{example['before_ape']}`")
            lines.append(f"  apres_ape=`{example['after_ape']}`")
            lines.append(f"  avant_partitions=`{example['before_partitions']}`")
            lines.append(f"  apres_partitions=`{example['after_partitions']}`")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaure ids_factures_sources et contexte_ape sur charges_externes depuis abt3.")
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--max-ids", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidate_partition_map = build_candidate_partition_map()
    all_partitions, partition_to_ape, ape_to_partitions = build_partition_registry()

    wanted_labels: set[str] = set()
    for name in BASE_FILES:
        payload = load_json(ROOT / name)
        wanted_labels.update(collect_needed_labels(payload))

    session = http_session()
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for partition in all_partitions:
        partition_indexes[partition] = build_line_item_index(
            session=session,
            db_name=args.db_factures,
            partition_prefix=partition,
            wanted_labels=wanted_labels,
        )

    file_summaries = []
    total_items_changed = 0
    total_a_valider_changed = 0
    total_invoice_ids_added = 0
    for name in BASE_FILES:
        result = process_file(
            path=ROOT / name,
            partition_indexes=partition_indexes,
            candidate_partition_map=candidate_partition_map,
            partition_to_ape=partition_to_ape,
            ape_to_partitions=ape_to_partitions,
            all_partitions=all_partitions,
            max_ids=max(1, int(args.max_ids)),
            db_factures=args.db_factures,
            dry_run=args.dry_run,
        )
        file_summaries.append(result)
        total_items_changed += result["items_changed"]
        total_a_valider_changed += result["a_valider_changed"]
        total_invoice_ids_added += result["invoice_ids_added"]

    summary = {
        "generated_at": now_iso(),
        "dry_run": args.dry_run,
        "source_db_factures": args.db_factures,
        "files": file_summaries,
        "items_changed": total_items_changed,
        "a_valider_changed": total_a_valider_changed,
        "invoice_ids_added": total_invoice_ids_added,
    }
    write_reports(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
