#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
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


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def get_path(obj: dict, path: tuple[str, ...], default=None):
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def first_non_none(obj: dict, paths: list[tuple[str, ...]], default=None):
    for path in paths:
        value = get_path(obj, path, default=None)
        if value is not None:
            return value
    return default


def normalize_invoice_doc(doc: dict) -> dict:
    invoice_id = str(doc.get("_id") or "")
    line_items = first_non_none(
        doc,
        paths=[
            ("line_items",),
            ("invoice", "line_items"),
            ("data", "line_items"),
            ("normalized", "line_items"),
        ],
        default=[],
    )
    if not isinstance(line_items, list):
        line_items = []

    invoice = {
        "_id": invoice_id,
        "invoice_number": first_non_none(
            doc,
            paths=[
                ("invoice_number",),
                ("invoice", "invoice_number"),
                ("data", "invoice_number"),
            ],
            default="",
        ),
        "invoice_date": first_non_none(
            doc,
            paths=[
                ("invoice_date",),
                ("invoice", "invoice_date"),
                ("data", "invoice_date"),
            ],
            default="",
        ),
        "issuer": first_non_none(
            doc,
            paths=[
                ("issuer",),
                ("invoice", "issuer"),
                ("data", "issuer"),
            ],
            default={},
        ),
        "recipient": first_non_none(
            doc,
            paths=[
                ("recipient",),
                ("invoice", "recipient"),
                ("data", "recipient"),
            ],
            default={},
        ),
        "line_items": line_items,
        "vat": first_non_none(
            doc,
            paths=[
                ("vat",),
                ("invoice", "vat"),
                ("data", "vat"),
            ],
            default=[],
        ),
        "total_net": first_non_none(
            doc,
            paths=[
                ("total_net",),
                ("invoice", "total_net"),
                ("data", "total_net"),
            ],
            default=None,
        ),
        "total_vat": first_non_none(
            doc,
            paths=[
                ("total_vat",),
                ("invoice", "total_vat"),
                ("data", "total_vat"),
            ],
            default=None,
        ),
        "total_gross": first_non_none(
            doc,
            paths=[
                ("total_gross",),
                ("invoice", "total_gross"),
                ("data", "total_gross"),
            ],
            default=None,
        ),
        "currency": first_non_none(
            doc,
            paths=[
                ("currency",),
                ("invoice", "currency"),
                ("data", "currency"),
            ],
            default="EUR",
        ),
    }
    return invoice


def safe_filename_from_invoice_id(invoice_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", invoice_id).strip("_")
    return value or "invoice_form"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export one invoice_form doc from CouchDB (read-only) for local engine tests."
    )
    parser.add_argument("--invoice-id", required=True, help="Full invoice doc id (ex: fr_bd_...:uuid).")
    parser.add_argument("--db", default=DEFAULT_DB_FACTURES, help="CouchDB source database (default: abt3).")
    parser.add_argument("--out-json", default="", help="Output file path.")
    parser.add_argument(
        "--full-doc",
        action="store_true",
        help="Export full CouchDB doc instead of normalized invoice payload.",
    )
    args = parser.parse_args()

    invoice_id = str(args.invoice_id or "").strip()
    if not invoice_id:
        raise SystemExit("Missing --invoice-id.")

    session = http_session()
    url = f"{COUCHDB_URL}/{quote(args.db, safe='')}/{quote(invoice_id, safe='')}"
    response = session.get(url, timeout=60)
    if response.status_code == 404:
        raise SystemExit(f"Invoice not found: {invoice_id}")
    response.raise_for_status()
    doc = response.json()

    payload = doc if args.full_doc else normalize_invoice_doc(doc)
    line_items_count = len((payload.get("line_items") or [])) if isinstance(payload, dict) else 0

    out_path = Path(args.out_json) if args.out_json else Path(
        f"{safe_filename_from_invoice_id(invoice_id)}{'_full' if args.full_doc else ''}.json"
    )
    if not out_path.is_absolute():
        out_path = (SCRIPT_DIR / out_path).resolve()

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] db={args.db}")
    print(f"[INFO] invoice_id={invoice_id}")
    if not args.full_doc:
        print(f"[INFO] line_items={line_items_count}")
    print(f"[OK] json={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
