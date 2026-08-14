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

FILES_BY_METIER = {
    "btp": [
        "base_produits_btp_v1.json",
        "base_produits_btp_v1_with_accounts.json",
    ],
    "boulangerie": [
        "base_produits_boulangerie_v1.json",
        "base_produits_boulangerie_v1_with_accounts.json",
    ],
    "boucherie": [
        "base_produits_boucherie_v1.json",
        "base_produits_boucherie_v1_with_accounts.json",
    ],
    "restaurant": [
        "base_produits_restaurant_v1.json",
        "base_produits_restaurant_v1_with_accounts.json",
    ],
}
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_MD = ROOT / "restauration_sources_selection_metiers_summary.md"
SUMMARY_JSON = ROOT / "restauration_sources_selection_metiers_summary.json"

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


def resolve_path(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct.resolve()
    return (ROOT / name).resolve()


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


def build_partition_registry() -> tuple[dict[str, list[str]], dict[str, str]]:
    payload = load_json(QUALITY_REPORT)
    metier_to_partitions: dict[str, list[str]] = defaultdict(list)
    partition_to_ape: dict[str, str] = {}
    for row in payload.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        ape = str(row.get("client_ape") or "").strip()
        selected = row.get("selected_metiers") or row.get("inferred_metiers") or []
        if partition and ape:
            partition_to_ape[partition] = ape
        for metier in selected:
            metier_name = str(metier or "").strip().lower()
            if partition and metier_name and partition not in metier_to_partitions[metier_name]:
                metier_to_partitions[metier_name].append(partition)
    return metier_to_partitions, partition_to_ape


def needs_restoration(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if not (item.get("ids_factures_sources") or item.get("source_invoice_ids")):
        return True
    if not (item.get("partitions_sources") or item.get("source_partition_ids")):
        return True
    if not (item.get("contexte_ape") or item.get("ape_context")):
        return True
    return False


def item_labels(item: dict) -> list[str]:
    labels = unique_strings(
        [
            normalize_text(str(item.get("article_source") or "")),
            normalize_text(str(item.get("article_canonique") or "")),
        ]
    )
    return [label for label in labels if label]


def collect_wanted_labels(items: list[dict]) -> set[str]:
    labels: set[str] = set()
    for item in items:
        if not needs_restoration(item):
            continue
        labels.update(item_labels(item))
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
                normalized = normalize_text(desc)
                if not normalized or normalized not in wanted_labels:
                    continue
                pair = (normalized, invoice_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                index[normalized].append((invoice_id, invoice_date))

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


def collect_found_rows(
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]],
    partitions: list[str],
    labels: list[str],
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for partition in partitions:
        label_index = partition_indexes.get(partition, {})
        for normalized in labels:
            rows.extend(label_index.get(normalized, []))
    return rows


def restore_item(
    item: dict,
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]],
    partition_to_ape: dict[str, str],
    default_partitions: list[str],
    fallback_partitions: list[str],
    max_ids: int,
) -> tuple[dict, dict]:
    existing_ids = unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
    existing_partitions = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
    existing_ape = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))
    partitions_from_ids = unique_strings([invoice_id.split(":", 1)[0] for invoice_id in existing_ids if ":" in invoice_id])
    labels = item_labels(item)

    preferred_partitions = unique_strings(existing_partitions + partitions_from_ids)
    search_partitions = preferred_partitions or default_partitions
    found_rows = collect_found_rows(partition_indexes, search_partitions, labels)
    if not found_rows and not preferred_partitions and fallback_partitions:
        found_rows = collect_found_rows(partition_indexes, fallback_partitions, labels)

    unique_found: dict[str, str] = {}
    for invoice_id, invoice_date in found_rows:
        previous = unique_found.get(invoice_id)
        if previous is None:
            unique_found[invoice_id] = invoice_date
            continue
        prev_dt = parse_date(previous)
        new_dt = parse_date(invoice_date)
        if new_dt and (not prev_dt or new_dt < prev_dt):
            unique_found[invoice_id] = invoice_date

    sorted_found = sorted(
        unique_found.items(),
        key=lambda row: (parse_date(row[1]) or datetime.max, row[0]),
    )
    found_ids = [row[0] for row in sorted_found]
    merged_ids = unique_strings(existing_ids + found_ids)[:max_ids]

    found_partitions = [invoice_id.split(":", 1)[0] for invoice_id in merged_ids if ":" in invoice_id]
    merged_partitions = unique_strings(existing_partitions + found_partitions)

    if existing_ape:
        merged_ape = existing_ape
    else:
        inferred_ape = [partition_to_ape[p] for p in merged_partitions if partition_to_ape.get(p)]
        merged_ape = unique_strings(inferred_ape)

    ids_added = max(0, len(merged_ids) - len(existing_ids))
    partitions_added = max(0, len(merged_partitions) - len(existing_partitions))
    ape_added = max(0, len(merged_ape) - len(existing_ape))

    item["ids_factures_sources"] = merged_ids
    item["source_invoice_ids"] = merged_ids
    item["partitions_sources"] = merged_partitions
    item["source_partition_ids"] = merged_partitions
    item["contexte_ape"] = merged_ape
    item["ape_context"] = merged_ape

    return reorder_item(item), {
        "ids_added": ids_added,
        "partitions_added": partitions_added,
        "ape_added": ape_added,
        "matched_invoice_ids": len(found_ids),
    }


def update_meta(meta: dict, metier: str, partitions_used: list[str], summary: dict) -> None:
    meta["restauration_sources_factures_v2"] = {
        "applied_at": now_iso(),
        "metier": metier,
        "source_db_factures": DEFAULT_DB,
        "match_rule": "invoice_form.line_items.description == article_source/article_canonique (normalise, exact)",
        "partitions_scanned": partitions_used,
        "files_updated": summary["files_updated"],
        "items_changed": summary["items_changed"],
        "invoice_ids_added": summary["invoice_ids_added"],
        "partitions_filled": summary["partitions_filled"],
        "ape_filled": summary["ape_filled"],
    }


def process_file(
    path: Path,
    metier: str,
    partition_indexes: dict[str, dict[str, list[tuple[str, str]]]],
    partition_to_ape: dict[str, str],
    default_partitions: list[str],
    fallback_partitions: list[str],
    max_ids: int,
    dry_run: bool,
) -> dict:
    payload = load_json(path)
    meta = payload.get("meta") or {}
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []

    changed = 0
    invoice_ids_added = 0
    partitions_filled = 0
    ape_filled = 0
    examples: list[dict] = []
    new_items: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            new_items.append(item)
            continue
        before_ids = unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
        before_parts = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
        before_ape = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))

        new_item, stats = restore_item(
            dict(item),
            partition_indexes=partition_indexes,
            partition_to_ape=partition_to_ape,
            default_partitions=default_partitions,
            fallback_partitions=fallback_partitions,
            max_ids=max_ids,
        )

        after_ids = unique_strings(list(new_item.get("ids_factures_sources") or []))
        after_parts = unique_strings(list(new_item.get("partitions_sources") or []))
        after_ape = unique_strings(list(new_item.get("contexte_ape") or []))

        if after_ids != before_ids or after_parts != before_parts or after_ape != before_ape:
            changed += 1
            invoice_ids_added += stats["ids_added"]
            partitions_filled += stats["partitions_added"]
            ape_filled += stats["ape_added"]
            if len(examples) < 5:
                examples.append(
                    {
                        "article_source": item.get("article_source"),
                        "before_ids": before_ids,
                        "after_ids": after_ids,
                        "before_partitions": before_parts,
                        "after_partitions": after_parts,
                        "before_ape": before_ape,
                        "after_ape": after_ape,
                    }
                )

        new_items.append(new_item)

    payload["items"] = new_items
    meta["updated_at"] = now_iso()
    payload["meta"] = meta

    if not dry_run:
        dump_json(path, payload)

    return {
        "file": path.name,
        "metier": metier,
        "items_total": len(items),
        "items_changed": changed,
        "invoice_ids_added": invoice_ids_added,
        "partitions_filled": partitions_filled,
        "ape_filled": ape_filled,
        "examples": examples,
    }


def write_reports(results: dict, dry_run: bool) -> None:
    SUMMARY_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Restauration Sources Manquantes V1",
        "",
        f"- dry_run: `{str(dry_run).lower()}`",
        f"- generated_at: `{results['generated_at']}`",
        f"- source_db_factures: `{results['source_db_factures']}`",
        "",
    ]
    for metier_summary in results["metiers"]:
        lines.append(f"## {metier_summary['metier']}")
        lines.append(f"- partitions_scanned: `{len(metier_summary['partitions_scanned'])}`")
        lines.append(f"- items_changed: `{metier_summary['items_changed']}`")
        lines.append(f"- invoice_ids_added: `{metier_summary['invoice_ids_added']}`")
        lines.append(f"- partitions_filled: `{metier_summary['partitions_filled']}`")
        lines.append(f"- ape_filled: `{metier_summary['ape_filled']}`")
        for file_summary in metier_summary["files"]:
            lines.append(
                f"- {file_summary['file']}: changed=`{file_summary['items_changed']}` "
                f"ids_added=`{file_summary['invoice_ids_added']}` "
                f"partitions_filled=`{file_summary['partitions_filled']}` "
                f"ape_filled=`{file_summary['ape_filled']}`"
            )
        if metier_summary["examples"]:
            lines.append("")
            lines.append("Exemples :")
            for example in metier_summary["examples"][:5]:
                lines.append(f"- `{example['article_source']}`")
                lines.append(f"  avant_ids=`{example['before_ids']}`")
                lines.append(f"  apres_ids=`{example['after_ids']}`")
                lines.append(f"  avant_partitions=`{example['before_partitions']}`")
                lines.append(f"  apres_partitions=`{example['after_partitions']}`")
                lines.append(f"  avant_ape=`{example['before_ape']}`")
                lines.append(f"  apres_ape=`{example['after_ape']}`")
        lines.append("")

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restaure les ids_factures_sources, partitions_sources et contexte_ape manquants sur btp/boulangerie/boucherie/restaurant."
    )
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--max-ids", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    metier_to_partitions, partition_to_ape = build_partition_registry()
    session = http_session()

    global_results = {
        "generated_at": now_iso(),
        "source_db_factures": args.db_factures,
        "dry_run": args.dry_run,
        "metiers": [],
    }

    for metier, names in FILES_BY_METIER.items():
        paths = [resolve_path(name) for name in names]
        payloads = [load_json(path) for path in paths]
        wanted_labels: set[str] = set()
        meta_partitions: list[str] = []
        for payload in payloads:
            items = payload.get("items") or []
            wanted_labels.update(collect_wanted_labels(items))
            partition_prefix = str((payload.get("meta") or {}).get("partition_prefix") or "").strip()
            if partition_prefix:
                meta_partitions.append(partition_prefix)

        report_partitions = unique_strings(metier_to_partitions.get(metier) or [])
        partitions_scanned = unique_strings(report_partitions + meta_partitions)
        partition_indexes: dict[str, dict[str, list[tuple[str, str]]]] = {}
        for partition in partitions_scanned:
            partition_indexes[partition] = build_line_item_index(
                session=session,
                db_name=args.db_factures,
                partition_prefix=partition,
                wanted_labels=wanted_labels,
            )

        if metier == "restaurant":
            default_partitions = unique_strings(meta_partitions)
            fallback_partitions = [p for p in report_partitions if p not in default_partitions]
        elif metier == "btp":
            default_partitions = report_partitions
            fallback_partitions = []
        else:
            default_partitions = unique_strings(report_partitions or meta_partitions)
            fallback_partitions = []

        file_results = []
        metier_changed = 0
        metier_ids = 0
        metier_partitions = 0
        metier_ape = 0
        metier_examples: list[dict] = []

        for path in paths:
            result = process_file(
                path=path,
                metier=metier,
                partition_indexes=partition_indexes,
                partition_to_ape=partition_to_ape,
                default_partitions=default_partitions,
                fallback_partitions=fallback_partitions,
                max_ids=max(1, int(args.max_ids)),
                dry_run=args.dry_run,
            )
            file_results.append(result)
            metier_changed += result["items_changed"]
            metier_ids += result["invoice_ids_added"]
            metier_partitions += result["partitions_filled"]
            metier_ape += result["ape_filled"]
            for example in result["examples"]:
                if len(metier_examples) < 5:
                    metier_examples.append(example)

        if not args.dry_run:
            for path in paths:
                payload = load_json(path)
                update_meta(
                    payload.setdefault("meta", {}),
                    metier=metier,
                    partitions_used=partitions_scanned,
                    summary={
                        "files_updated": [p.name for p in paths],
                        "items_changed": metier_changed,
                        "invoice_ids_added": metier_ids,
                        "partitions_filled": metier_partitions,
                        "ape_filled": metier_ape,
                    },
                )
                dump_json(path, payload)

        global_results["metiers"].append(
            {
                "metier": metier,
                "partitions_scanned": partitions_scanned,
                "files": file_results,
                "items_changed": metier_changed,
                "invoice_ids_added": metier_ids,
                "partitions_filled": metier_partitions,
                "ape_filled": metier_ape,
                "examples": metier_examples,
            }
        )

    write_reports(global_results, dry_run=args.dry_run)
    print(json.dumps(global_results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
