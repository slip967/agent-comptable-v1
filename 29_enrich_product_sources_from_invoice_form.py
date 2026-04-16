#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
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


SCRIPT_DIR = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)
DEFAULT_DB = os.getenv("DB_FACTURES", "abt3")


DEFAULT_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_transport_v1_with_accounts.json",
]


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


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


def date_year(value: str) -> str:
    dt = parse_date(value)
    return str(dt.year) if dt else ""


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def resolve_path(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct.resolve()
    fallback = (SCRIPT_DIR / name).resolve()
    return fallback


def load_base(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_line_item_index(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
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

        response = session.post(endpoint, json=payload, timeout=120)
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
                if not key:
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


def sort_invoice_ids_with_dates(ids_with_dates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return sorted(
        ids_with_dates,
        key=lambda row: (
            parse_date(row[1]) or datetime.max,
            row[0],
        ),
    )


def enrich_file(
    path: Path,
    line_item_index: dict[str, list[tuple[str, str]]],
    year_filter: str,
    max_ids: int,
) -> tuple[int, int]:
    data = load_base(path)
    items = data.get("items") or []
    if not isinstance(items, list):
        return 0, 0

    changed_items = 0
    added_total = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        article = str(item.get("article_source") or "").strip()
        key = normalize_text(article)
        if not key:
            continue

        candidates = sort_invoice_ids_with_dates(line_item_index.get(key, []))
        if year_filter:
            candidates = [row for row in candidates if date_year(row[1]) == year_filter]

        existing = [str(v).strip() for v in (item.get("source_invoice_ids") or []) if str(v).strip()]
        merged = list(existing)
        for invoice_id, _invoice_date in candidates:
            if invoice_id in merged:
                continue
            merged.append(invoice_id)
            if len(merged) >= max_ids:
                break

        if merged != existing:
            item["source_invoice_ids"] = merged[:max_ids]
            changed_items += 1
            added_total += max(0, len(item["source_invoice_ids"]) - len(existing))

    meta = data.get("meta") or {}
    meta["source_invoice_ids_note"] = f"Jusqu a {max_ids} invoice_id source par article_source depuis invoice_form."
    meta["invoice_source_enrichment"] = {
        "db_factures": DEFAULT_DB,
        "match_rule": "invoice_form.line_items.description == article_source (normalise)",
        "year_filter": year_filter or "none",
        "changed_items": changed_items,
        "added_invoice_ids_total": added_total,
    }
    data["meta"] = meta

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed_items, added_total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add more source_invoice_ids to product bases from invoice_form line_items (exact normalized label match)."
    )
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--input", action="append", default=[], help="Base JSON files to enrich.")
    parser.add_argument(
        "--year",
        default="2024",
        help="Keep only invoice IDs from this year for new additions. Use 'all' to keep every year.",
    )
    parser.add_argument("--max-ids", type=int, default=3, help="Max source_invoice_ids per item.")
    args = parser.parse_args()

    files = [resolve_path(name) for name in (args.input or DEFAULT_FILES)]
    files = [p for p in files if p.exists()]
    if not files:
        raise SystemExit("No input base files found.")

    # Group files by partition prefix to query each partition once.
    files_by_partition: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        data = load_base(path)
        partition = str((data.get("meta") or {}).get("partition_prefix") or "").strip()
        if not partition:
            continue
        files_by_partition[partition].append(path)

    if not files_by_partition:
        raise SystemExit("No partition_prefix found in provided files.")

    session = http_session()
    year_filter = str(args.year or "").strip()
    if year_filter.lower() in {"all", "*", "none", "any", "toutes", "tous"}:
        year_filter = ""
    total_changed = 0
    total_added = 0

    for partition_prefix, group in files_by_partition.items():
        index = build_line_item_index(
            session=session,
            db_name=args.db_factures,
            partition_prefix=partition_prefix,
        )
        print(f"[INFO] partition={partition_prefix} unique_line_labels={len(index)}")
        for path in group:
            changed, added = enrich_file(
                path=path,
                line_item_index=index,
                year_filter=year_filter,
                max_ids=max(1, int(args.max_ids)),
            )
            total_changed += changed
            total_added += added
            print(f"[OK] file={path.name} changed_items={changed} added_invoice_ids={added}")

    print(f"[INFO] total_changed_items={total_changed}")
    print(f"[INFO] total_added_invoice_ids={total_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
