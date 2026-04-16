#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
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
DEFAULT_DB_FACTURES = os.getenv("DB_FACTURES", "abt3")

DEFAULT_CSV_INPUTS = [
    "invoice_form_519665103_all.csv",
    "invoice_form_519665103_with_line_items.csv",
    "invoice_form_519665103_metier_assignment_template.csv",
]
DEFAULT_JSON_INPUTS = [
    "invoice_form_519665103_all.json",
]


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def normalize_ape(value: str | None) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def extract_siren(party: dict | None) -> str:
    if not isinstance(party, dict):
        return ""

    siren = str(party.get("siren") or "").strip()
    if siren:
        return siren

    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = (reg.get("type") or "").upper()
        reg_value = str(reg.get("value") or "").strip()
        if reg_type == "SIREN" and reg_value:
            return reg_value
        if reg_type == "SIRET" and len(reg_value) >= 9:
            return reg_value[:9]

    return ""


def extract_ape(party: dict | None) -> str:
    if not isinstance(party, dict):
        return ""

    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = (reg.get("type") or "").upper()
        reg_value = normalize_ape(reg.get("value"))
        if reg_type in {"APE", "NAF"} and reg_value:
            return reg_value

    return ""


def infer_partition_prefix_from_csv(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            invoice_id = str(row.get("invoice_id") or "").strip()
            if ":" in invoice_id:
                return invoice_id.split(":", 1)[0]
    return ""


def infer_partition_prefix_from_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return ""
    for row in items:
        if not isinstance(row, dict):
            continue
        invoice_id = str(row.get("invoice_id") or "").strip()
        if ":" in invoice_id:
            return invoice_id.split(":", 1)[0]
    return ""


def resolve_existing_paths(names: list[str]) -> list[Path]:
    paths: list[Path] = []
    for name in names:
        candidate = Path(name)
        if candidate.exists():
            paths.append(candidate.resolve())
            continue
        fallback = SCRIPT_DIR / name
        if fallback.exists():
            paths.append(fallback.resolve())
    return paths


def iter_invoice_forms_minimal(session: requests.Session, db_name: str, partition_prefix: str):
    bookmark = None
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"

    while True:
        payload = {
            "selector": {"p": "invoice_form"},
            "fields": ["_id", "issuer", "recipient"],
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
            yield doc

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def build_invoice_ape_index(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
) -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, int]]:
    invoice_index: dict[str, dict[str, str]] = {}
    siren_to_ape: dict[str, str] = {}
    stats = {
        "invoice_docs_scanned": 0,
        "issuer_ape_direct_hits": 0,
        "recipient_ape_direct_hits": 0,
        "unique_sirens_with_ape": 0,
    }

    for doc in iter_invoice_forms_minimal(session, db_name, partition_prefix):
        stats["invoice_docs_scanned"] += 1

        issuer = doc.get("issuer") or {}
        recipient = doc.get("recipient") or {}

        issuer_siren = extract_siren(issuer)
        recipient_siren = extract_siren(recipient)
        issuer_ape_direct = extract_ape(issuer)
        recipient_ape_direct = extract_ape(recipient)

        if issuer_ape_direct:
            stats["issuer_ape_direct_hits"] += 1
        if recipient_ape_direct:
            stats["recipient_ape_direct_hits"] += 1

        if issuer_siren and issuer_ape_direct and issuer_siren not in siren_to_ape:
            siren_to_ape[issuer_siren] = issuer_ape_direct
        if recipient_siren and recipient_ape_direct and recipient_siren not in siren_to_ape:
            siren_to_ape[recipient_siren] = recipient_ape_direct

        invoice_index[str(doc.get("_id") or "").strip()] = {
            "issuer_siren": issuer_siren,
            "issuer_ape_direct": issuer_ape_direct,
            "recipient_siren": recipient_siren,
            "recipient_ape_direct": recipient_ape_direct,
        }

    stats["unique_sirens_with_ape"] = len(siren_to_ape)
    return invoice_index, siren_to_ape, stats


def output_path_for(path: Path, suffix: str, in_place: bool) -> Path:
    if in_place:
        return path
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def enrich_row(row: dict[str, str], invoice_index: dict[str, dict[str, str]], siren_to_ape: dict[str, str]) -> dict[str, str]:
    invoice_id = str(row.get("invoice_id") or "").strip()
    info = invoice_index.get(invoice_id, {})

    issuer_siren = info.get("issuer_siren", "")
    recipient_siren = info.get("recipient_siren", "")
    issuer_ape_direct = info.get("issuer_ape_direct", "")
    recipient_ape_direct = info.get("recipient_ape_direct", "")

    issuer_ape = issuer_ape_direct or (siren_to_ape.get(issuer_siren) or "")
    recipient_ape = recipient_ape_direct or (siren_to_ape.get(recipient_siren) or "")

    issuer_ape_source = ""
    if issuer_ape_direct:
        issuer_ape_source = "invoice_form"
    elif issuer_ape:
        issuer_ape_source = "siren_map_partition"

    recipient_ape_source = ""
    if recipient_ape_direct:
        recipient_ape_source = "invoice_form"
    elif recipient_ape:
        recipient_ape_source = "siren_map_partition"

    row["issuer_siren"] = issuer_siren
    row["issuer_ape"] = issuer_ape
    row["issuer_ape_source"] = issuer_ape_source
    row["recipient_siren"] = recipient_siren
    row["recipient_ape"] = recipient_ape
    row["recipient_ape_source"] = recipient_ape_source
    return row


def enrich_csv_file(path: Path, output_path: Path, invoice_index: dict[str, dict[str, str]], siren_to_ape: dict[str, str]) -> dict[str, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra_fields = [
        "issuer_siren",
        "issuer_ape",
        "issuer_ape_source",
        "recipient_siren",
        "recipient_ape",
        "recipient_ape_source",
    ]
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    stats = {"rows": len(rows), "issuer_ape_filled": 0, "recipient_ape_filled": 0}
    enriched_rows = []
    for row in rows:
        enriched = enrich_row(dict(row), invoice_index, siren_to_ape)
        if enriched.get("issuer_ape"):
            stats["issuer_ape_filled"] += 1
        if enriched.get("recipient_ape"):
            stats["recipient_ape_filled"] += 1
        enriched_rows.append(enriched)

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)

    return stats


def enrich_json_file(path: Path, output_path: Path, invoice_index: dict[str, dict[str, str]], siren_to_ape: dict[str, str], db_name: str, partition_prefix: str, index_stats: dict[str, int]) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        items = data.get("items")
    else:
        items = data

    if not isinstance(items, list):
        raise ValueError(f"JSON format not supported for {path.name}")

    stats = {"rows": 0, "issuer_ape_filled": 0, "recipient_ape_filled": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        stats["rows"] += 1
        enrich_row(item, invoice_index, siren_to_ape)
        if item.get("issuer_ape"):
            stats["issuer_ape_filled"] += 1
        if item.get("recipient_ape"):
            stats["recipient_ape_filled"] += 1

    if isinstance(data, dict):
        meta = data.setdefault("meta", {})
        meta["ape_enrichment"] = {
            "db_factures": db_name,
            "partition_prefix": partition_prefix,
            **index_stats,
        }

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich invoice exports with APE codes from CouchDB invoice_form docs.")
    parser.add_argument("--db-factures", default=DEFAULT_DB_FACTURES, help="CouchDB database containing invoice_form docs.")
    parser.add_argument("--partition-prefix", default="", help="Partition prefix (for example fr_bd_519665103).")
    parser.add_argument("--input-csv", action="append", default=[], help="CSV export to enrich. Can be repeated.")
    parser.add_argument("--input-json", action="append", default=[], help="JSON export to enrich. Can be repeated.")
    parser.add_argument("--output-suffix", default="_with_ape", help="Suffix added to output files when not using --in-place.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input files instead of creating new ones.")
    args = parser.parse_args()

    csv_inputs = resolve_existing_paths(args.input_csv or DEFAULT_CSV_INPUTS)
    json_inputs = resolve_existing_paths(args.input_json or DEFAULT_JSON_INPUTS)
    if not csv_inputs and not json_inputs:
        raise SystemExit("No invoice export files found to enrich.")

    partition_prefix = (args.partition_prefix or "").strip()
    if not partition_prefix and csv_inputs:
        partition_prefix = infer_partition_prefix_from_csv(csv_inputs[0])
    if not partition_prefix and json_inputs:
        partition_prefix = infer_partition_prefix_from_json(json_inputs[0])
    if not partition_prefix:
        raise SystemExit("Unable to infer partition prefix. Pass --partition-prefix explicitly.")

    session = http_session()
    invoice_index, siren_to_ape, index_stats = build_invoice_ape_index(session, args.db_factures, partition_prefix)

    print(
        "[INFO] partition={partition} scanned={scanned} unique_sirens_with_ape={unique}".format(
            partition=partition_prefix,
            scanned=index_stats["invoice_docs_scanned"],
            unique=index_stats["unique_sirens_with_ape"],
        )
    )

    for path in csv_inputs:
        output_path = output_path_for(path, args.output_suffix, args.in_place)
        stats = enrich_csv_file(path, output_path, invoice_index, siren_to_ape)
        print(
            "[OK] csv={path} rows={rows} issuer_ape={issuer} recipient_ape={recipient}".format(
                path=output_path,
                rows=stats["rows"],
                issuer=stats["issuer_ape_filled"],
                recipient=stats["recipient_ape_filled"],
            )
        )

    for path in json_inputs:
        output_path = output_path_for(path, args.output_suffix, args.in_place)
        stats = enrich_json_file(
            path,
            output_path,
            invoice_index,
            siren_to_ape,
            args.db_factures,
            partition_prefix,
            index_stats,
        )
        print(
            "[OK] json={path} rows={rows} issuer_ape={issuer} recipient_ape={recipient}".format(
                path=output_path,
                rows=stats["rows"],
                issuer=stats["issuer_ape_filled"],
                recipient=stats["recipient_ape_filled"],
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
