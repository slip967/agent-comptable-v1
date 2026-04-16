#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
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

COUCHDB_URL = DEFAULT_COUCHDB_URL.rstrip("/")
COUCHDB_USER = DEFAULT_COUCHDB_USER
COUCHDB_PASS = DEFAULT_COUCHDB_PASS
CLIENT_CERT = DEFAULT_CLIENT_CERT
CLIENT_KEY = DEFAULT_CLIENT_KEY
CA_CERT = DEFAULT_CA_CERT


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def load_doc_ids(report_csv: Path) -> list[str]:
    doc_ids: list[str] = []
    with report_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            invoice_id = (row.get("invoice_id") or "").strip()
            core_profile_id = (row.get("core_profile_id") or "").strip()
            if invoice_id:
                doc_ids.append(invoice_id)
            if core_profile_id:
                doc_ids.append(core_profile_id)
    seen: set[str] = set()
    ordered: list[str] = []
    for doc_id in doc_ids:
        if doc_id and doc_id not in seen:
            ordered.append(doc_id)
            seen.add(doc_id)
    return ordered


def fetch_docs(session: requests.Session, db: str, doc_ids: list[str]) -> list[dict]:
    if not doc_ids:
        return []
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_all_docs?include_docs=true"
    response = session.post(url, json={"keys": doc_ids}, timeout=120)
    response.raise_for_status()
    docs: list[dict] = []
    for row in response.json().get("rows", []):
        doc = row.get("doc")
        if isinstance(doc, dict) and doc.get("_id"):
            docs.append(doc)
    return docs


def bulk_update(session: requests.Session, db: str, docs: list[dict]) -> tuple[int, int]:
    if not docs:
        return 0, 0
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_bulk_docs"
    response = session.post(url, json={"docs": docs}, timeout=120)
    response.raise_for_status()
    ok = 0
    errors = 0
    for row in response.json():
        if row.get("ok"):
            ok += 1
        else:
            errors += 1
    return ok, errors


def write_report(path: Path, rows: list[dict]) -> None:
    fieldnames = ["doc_id", "doc_type", "had_external_charge_profile_v1", "status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove external_charge_profile_v1 from invoice_form/core_profile docs listed in a report CSV."
    )
    parser.add_argument(
        "--db",
        default="keymanage_accounting",
        help="Target CouchDB database to revert.",
    )
    parser.add_argument(
        "--report-csv",
        default="v1_519665103_invoice_charge_profiles_report.csv",
        help="CSV report generated during the invoice/core_profile enrichment.",
    )
    parser.add_argument(
        "--out-report-csv",
        default="v1_519665103_invoice_charge_profiles_revert_report.csv",
        help="CSV audit report for the revert operation.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to CouchDB.")
    args = parser.parse_args()

    report_csv = (SCRIPT_DIR / args.report_csv).resolve()
    out_report_csv = (SCRIPT_DIR / args.out_report_csv).resolve()

    doc_ids = load_doc_ids(report_csv)
    session = http_session()
    docs = fetch_docs(session, args.db, doc_ids)

    to_update: list[dict] = []
    report_rows: list[dict] = []

    docs_by_id = {str(doc.get("_id")): doc for doc in docs if doc.get("_id")}
    for doc_id in doc_ids:
        doc = docs_by_id.get(doc_id)
        if not doc:
            report_rows.append(
                {
                    "doc_id": doc_id,
                    "doc_type": "",
                    "had_external_charge_profile_v1": "unknown",
                    "status": "missing",
                }
            )
            continue

        had_field = "external_charge_profile_v1" in doc
        status = "already_clean"
        if had_field:
            doc.pop("external_charge_profile_v1", None)
            to_update.append(doc)
            status = "would_remove" if args.dry_run else "removed"

        report_rows.append(
            {
                "doc_id": doc_id,
                "doc_type": doc.get("p", ""),
                "had_external_charge_profile_v1": "yes" if had_field else "no",
                "status": status,
            }
        )

    ok = errors = 0
    if not args.dry_run:
        ok, errors = bulk_update(session, args.db, to_update)

    write_report(out_report_csv, report_rows)

    print(f"[INFO] doc_ids_listed={len(doc_ids)}")
    print(f"[INFO] docs_found={len(docs)}")
    if args.dry_run:
        print(f"[INFO] docs_to_update={len(to_update)}")
    else:
        print(f"[OK] docs_updated={ok} errors={errors}")
    print(f"[OK] report={out_report_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
