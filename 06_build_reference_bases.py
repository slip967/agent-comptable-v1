#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build V1 reference bases from invoice documents.

Output:
- reference_base_charges_externes_v1.json
- reference_base_exploitation_v1.json
- reference_base_a_revoir_v1.json
"""

import argparse
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, UTC
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


COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

DB_FACTURES = os.getenv("DB_FACTURES", "abt3")
LIMIT = int(os.getenv("REF_LIMIT", "5000"))


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    s = requests.Session()
    s.auth = (COUCHDB_USER, COUCHDB_PASS)
    s.cert = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return s


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def canonical_label(description: str) -> str:
    text = normalize_text(description)
    stop = {
        "periode",
        "facturee",
        "du",
        "au",
        "unite",
        "mois",
        "service",
        "prestation",
        "pack",
        "offre",
    }
    words = [w for w in text.split() if w not in stop and not re.fullmatch(r"\d+", w)]
    if not words:
        return text
    return " ".join(words[:6])


def parse_ape(party: dict | None) -> str | None:
    if not isinstance(party, dict):
        return None
    regs = party.get("company_registrations") or []
    if not isinstance(regs, list):
        return None
    for it in regs:
        if not isinstance(it, dict):
            continue
        typ = (it.get("type") or "").upper()
        if typ in {"APE", "NAF"}:
            v = (it.get("value") or "").strip().upper().replace(" ", "")
            if v:
                return v
    return None


def tva_hint(vat_percent: float | int | None, account: str) -> str:
    if vat_percent is None:
        return "unknown"
    try:
        rate = float(vat_percent)
    except Exception:
        return "unknown"
    if abs(rate - 5.5) < 0.01:
        return "likely_food"
    if abs(rate - 20.0) < 0.01:
        return "likely_service"
    if abs(rate) < 0.01:
        return "no_vat_or_exempt"
    return "check_required"


def classify_reference(account: str) -> str:
    account = (account or "").strip()
    # Generic external charges (as in meeting notes: rent, insurance, telecom, etc.)
    external_prefixes = (
        "613",
        "614",
        "615",
        "616",
        "617",
        "618",
        "619",
        "620",
        "621",
        "622",
        "623",
        "624",
        "625",
        "626",
        "627",
        "628",
    )
    if account.startswith(external_prefixes):
        return "charges_externes"
    # Business-specific exploitation purchases
    if account.startswith(("60", "601", "602", "603", "604", "605", "606", "607", "608", "609")):
        return "exploitation_metier"
    return "a_revoir"


def iter_invoice_forms(sess: requests.Session, db_name: str, partition_prefix: str | None = None):
    bookmark = None
    total = 0
    if partition_prefix:
        base_endpoint = f"{COUCHDB_URL}/{db_name}/_partition/{quote(partition_prefix, safe='')}/_find"
        selector = {"p": "invoice_form"}
    else:
        base_endpoint = f"{COUCHDB_URL}/{db_name}/_find"
        selector = {"p": "invoice_form"}

    while True:
        payload = {
            "selector": selector,
            "fields": [
                "_id",
                "p",
                "invoice_date",
                "invoice_number",
                "issuer",
                "recipient",
                "line_items",
                "accounting_summary",
                "vat",
                "total_net",
                "total_vat",
                "total_gross",
                "currency",
            ],
            "limit": LIMIT,
        }
        if bookmark:
            payload["bookmark"] = bookmark

        r = sess.post(base_endpoint, json=payload, timeout=120)
        r.raise_for_status()
        j = r.json()
        docs = j.get("docs", [])
        if not docs:
            break
        for doc in docs:
            total += 1
            yield doc

        new_bookmark = j.get("bookmark")
        if not new_bookmark or new_bookmark == bookmark:
            break
        bookmark = new_bookmark

    if partition_prefix:
        print(f"[INFO] invoice_form scanned (partition {partition_prefix}): {total}")
    else:
        print(f"[INFO] invoice_form scanned: {total}")


def build_reference_bases(db_name: str, partition_prefix: str | None = None):
    sess = http_session()
    references: dict[str, dict] = {}
    by_bucket = defaultdict(list)
    stats = Counter()

    for inv in iter_invoice_forms(sess, db_name, partition_prefix=partition_prefix):
        issuer = inv.get("issuer") or {}
        recipient = inv.get("recipient") or {}
        ape_supplier = parse_ape(issuer)
        ape_client = parse_ape(recipient)
        invoice_date = inv.get("invoice_date")
        invoice_number = inv.get("invoice_number")
        currency = inv.get("currency")

        line_items = inv.get("line_items") or []
        if not isinstance(line_items, list):
            line_items = []

        if not line_items:
            for row in inv.get("accounting_summary") or []:
                if not isinstance(row, dict):
                    continue
                account = str(row.get("accounting_account") or "").strip()
                if not account:
                    continue
                desc = str(row.get("accounting_account_label") or account).strip()
                vat_percent = None
                vat_rows = inv.get("vat") or []
                if isinstance(vat_rows, list) and vat_rows:
                    vat_percent = vat_rows[0].get("vat_percent")
                line_items.append(
                    {
                        "description": desc,
                        "accounting_account": account,
                        "vat_percent": vat_percent,
                        "total_net": row.get("total_net"),
                        "total_gross": row.get("total_gross"),
                    }
                )

        for li in line_items:
            if not isinstance(li, dict):
                continue
            description = str(li.get("description") or "").strip()
            account = str(li.get("accounting_account") or "").strip()
            if not description or not account:
                continue

            canonical = canonical_label(description)
            key = f"{canonical}|{account}"
            bucket = classify_reference(account)
            stats[f"line_items_{bucket}"] += 1

            vat_percent = li.get("vat_percent")
            if vat_percent is None:
                vat_rows = inv.get("vat") or []
                if isinstance(vat_rows, list) and vat_rows:
                    vat_percent = vat_rows[0].get("vat_percent")

            if key not in references:
                references[key] = {
                    "canonical_label": canonical,
                    "source_labels": Counter(),
                    "proposed_account": account,
                    "category": bucket,
                    "tva_rates": Counter(),
                    "tva_hint": Counter(),
                    "ape_client": Counter(),
                    "ape_supplier": Counter(),
                    "examples": [],
                    "occurrences": 0,
                }

            ref = references[key]
            ref["occurrences"] += 1
            ref["source_labels"][description] += 1
            if vat_percent is not None:
                ref["tva_rates"][str(vat_percent)] += 1
            ref["tva_hint"][tva_hint(vat_percent, account)] += 1
            if ape_client:
                ref["ape_client"][ape_client] += 1
            if ape_supplier:
                ref["ape_supplier"][ape_supplier] += 1

            if len(ref["examples"]) < 5:
                ref["examples"].append(
                    {
                        "invoice_id": inv.get("_id"),
                        "invoice_number": invoice_number,
                        "invoice_date": invoice_date,
                        "description": description,
                        "total_net": li.get("total_net"),
                        "total_gross": li.get("total_gross"),
                        "currency": currency,
                    }
                )

    finalized = []
    for ref in references.values():
        row = {
            "canonical_label": ref["canonical_label"],
            "source_labels_top": ref["source_labels"].most_common(8),
            "proposed_account": ref["proposed_account"],
            "category": ref["category"],
            "tva_rates_top": ref["tva_rates"].most_common(4),
            "tva_hint_top": ref["tva_hint"].most_common(4),
            "ape_client_top": ref["ape_client"].most_common(5),
            "ape_supplier_top": ref["ape_supplier"].most_common(5),
            "occurrences": ref["occurrences"],
            "examples": ref["examples"],
        }
        finalized.append(row)
        by_bucket[row["category"]].append(row)

    for bucket in by_bucket:
        by_bucket[bucket].sort(key=lambda x: x["occurrences"], reverse=True)

    return by_bucket, stats, len(finalized)


def main():
    parser = argparse.ArgumentParser(description="Build V1 reference bases from invoice_form documents.")
    parser.add_argument("--db-factures", default=DB_FACTURES, help="CouchDB database containing invoice_form docs.")
    parser.add_argument(
        "--partition-prefix",
        default=os.getenv("V1_PARTITION_PREFIX", "").strip(),
        help="Optional partition prefix (example: fr_bd_519665103) to scope V1 to one client.",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Output directory for JSON files.",
    )
    parser.add_argument(
        "--output-prefix",
        default="",
        help="Optional filename prefix for generated files (example: v1_519665103_).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    partition_prefix = (args.partition_prefix or "").strip() or None

    by_bucket, stats, total_refs = build_reference_bases(args.db_factures, partition_prefix=partition_prefix)

    generated_at = now_iso()
    meta = {
        "generated_at": generated_at,
        "db_factures": args.db_factures,
        "partition_prefix": partition_prefix,
        "total_unique_references": total_refs,
        "stats": dict(stats),
    }

    mapping = {
        "charges_externes": "reference_base_charges_externes_v1.json",
        "exploitation_metier": "reference_base_exploitation_v1.json",
        "a_revoir": "reference_base_a_revoir_v1.json",
    }

    for bucket, filename in mapping.items():
        payload = {
            "meta": meta,
            "category": bucket,
            "items": by_bucket.get(bucket, []),
        }
        path = out_dir / f"{args.output_prefix}{filename}"
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[OK] {bucket}: {len(payload['items'])} -> {path}")


if __name__ == "__main__":
    main()
