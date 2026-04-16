#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
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


SCRIPT_DIR = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

DEFAULT_DB = "abt3fec2"
DEFAULT_BASE_FILES = [
    "base_produits_boulangerie_v1.json",
    "base_produits_boucherie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
    "base_produits_boulangerie_v1_with_accounts.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_produits_epicerie_v1_with_accounts.json",
    "base_produits_vtc_v1_with_accounts.json",
]


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def normalize_account(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def is_expense_account(account_number: str) -> bool:
    return bool(account_number) and account_number.isdigit() and account_number.startswith("6")


def resolve_existing_path(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct.resolve()
    fallback = SCRIPT_DIR / name
    if fallback.exists():
        return fallback.resolve()
    return fallback.resolve()


def collect_invoice_ids_from_bases(base_paths: list[Path]) -> set[str]:
    ids: set[str] = set()
    for path in base_paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            for invoice_id in item.get("source_invoice_ids") or []:
                invoice_id = str(invoice_id).strip()
                if invoice_id:
                    ids.add(invoice_id)
    return ids


def iter_relevant_entries(
    session: requests.Session,
    db_name: str,
    target_invoice_ids: set[str],
    limit: int = 500,
):
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_find"
    selector = {
        "p": "entry",
        "invoice": {"$exists": True},
        "_id": {"$regex": "^(?!.*generated).*$"},
    }
    fields = [
        "_id",
        "account_number",
        "label",
        "debit",
        "credit",
        "invoice.invoice_form_id",
    ]

    bookmark = None
    while True:
        payload: dict[str, Any] = {
            "selector": selector,
            "fields": fields,
            "limit": limit,
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
            invoice_form_id = str(((doc.get("invoice") or {}).get("invoice_form_id")) or "").strip()
            if not invoice_form_id:
                continue
            if invoice_form_id not in target_invoice_ids:
                continue
            if "generated" in str(doc.get("_id") or "").lower():
                continue
            yield doc

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def choose_recommended_account(
    counters_by_invoice: dict[str, Counter],
    source_invoice_ids: list[str],
    current_account: str,
    min_confidence: float,
) -> tuple[str, float, int, int, str]:
    aggregate = Counter()
    used_invoice_ids = []
    for invoice_id in source_invoice_ids:
        inv = str(invoice_id).strip()
        if not inv:
            continue
        counter = counters_by_invoice.get(inv)
        if not counter:
            continue
        aggregate.update(counter)
        used_invoice_ids.append(inv)

    if not aggregate:
        return "", 0.0, 0, 0, ""

    ranked = aggregate.most_common()
    top_account, top_votes = ranked[0]
    second_votes = ranked[1][1] if len(ranked) > 1 else 0
    total_votes = sum(aggregate.values())
    confidence = (top_votes / total_votes) if total_votes else 0.0

    # If tie on top, keep current account when possible to avoid unsafe switches.
    top_ties = [acc for acc, votes in ranked if votes == top_votes]
    if len(top_ties) > 1:
        if current_account and current_account in top_ties:
            top_account = current_account
        else:
            top_account = sorted(top_ties)[0]

    # Require a clear signal: either strict lead or enough confidence.
    has_strict_lead = top_votes > second_votes
    if not has_strict_lead and confidence < min_confidence:
        return "", confidence, top_votes, total_votes, ""

    votes_debug = " | ".join(f"{acc}:{votes}" for acc, votes in ranked[:5])
    used_debug = " | ".join(used_invoice_ids[:5])
    reason = f"votes={votes_debug}; confidence={confidence:.2f}; invoices={used_debug}"
    return top_account, confidence, top_votes, total_votes, reason


def align_file_accounts(
    path: Path,
    counters_by_invoice: dict[str, Counter],
    min_confidence: float,
) -> tuple[dict[str, int], list[dict[str, str]], dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"Invalid items format in {path}")

    changed = 0
    unchanged = 0
    no_signal = 0
    rows: list[dict[str, str]] = []

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        source_invoice_ids = [str(v).strip() for v in (item.get("source_invoice_ids") or []) if str(v).strip()]
        if not source_invoice_ids:
            no_signal += 1
            continue

        old = normalize_account(item.get("compte_comptable"))
        rec, confidence, top_votes, total_votes, reason = choose_recommended_account(
            counters_by_invoice=counters_by_invoice,
            source_invoice_ids=source_invoice_ids,
            current_account=old,
            min_confidence=min_confidence,
        )
        if not rec:
            no_signal += 1
            continue
        if rec == old:
            unchanged += 1
            continue

        item["compte_comptable"] = rec
        item["compte_comptable_source"] = "abt3fec2_entry_invoice_block_v1"
        item["compte_comptable_match_score"] = int(round(confidence * 100))
        item["compte_comptable_match_reason"] = reason
        changed += 1

        rows.append(
            {
                "file": str(path),
                "item_index": str(idx),
                "article_source": str(item.get("article_source") or ""),
                "old_account": old,
                "new_account": rec,
                "confidence": f"{confidence:.2f}",
                "top_votes": str(top_votes),
                "total_votes": str(total_votes),
                "source_invoice_ids": " | ".join(source_invoice_ids),
            }
        )

    meta = data.get("meta") or {}
    meta["accounts_alignment_from_abt3fec2"] = {
        "db": DEFAULT_DB,
        "selector": "p=entry + invoice exists + _id not contains generated",
        "changed_items": changed,
        "unchanged_items": unchanged,
        "no_signal_items": no_signal,
        "min_confidence": min_confidence,
    }
    data["meta"] = meta

    stats = {
        "total_items": len(items),
        "changed": changed,
        "unchanged": unchanged,
        "no_signal": no_signal,
    }
    return stats, rows, data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Align compte_comptable in base_produits files from abt3fec2 entry docs "
            "(invoice block required, excluding _id containing generated)."
        )
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Target DB (default: abt3fec2).")
    parser.add_argument("--input", action="append", default=[], help="Input base JSON file (repeatable).")
    parser.add_argument("--apply", action="store_true", help="Write changes to files.")
    parser.add_argument("--min-confidence", type=float, default=0.55, help="Minimum confidence threshold.")
    parser.add_argument(
        "--report-csv",
        default="abt3fec2_product_bases_accounts_alignment_report.csv",
        help="CSV report path.",
    )
    args = parser.parse_args()

    base_names = args.input or DEFAULT_BASE_FILES
    base_paths = [resolve_existing_path(name) for name in base_names if str(name).strip()]
    base_paths = [path for path in base_paths if path.exists()]
    if not base_paths:
        raise SystemExit("Aucun fichier base_produits trouvé.")

    target_invoice_ids = collect_invoice_ids_from_bases(base_paths)
    if not target_invoice_ids:
        raise SystemExit("Aucun source_invoice_ids trouvé dans les bases produits.")

    session = http_session()
    counters_by_invoice: dict[str, Counter] = defaultdict(Counter)
    scanned_entries = 0
    kept_entries = 0

    for doc in iter_relevant_entries(session=session, db_name=args.db, target_invoice_ids=target_invoice_ids):
        scanned_entries += 1
        account = normalize_account(doc.get("account_number"))
        if not is_expense_account(account):
            continue
        invoice_id = str(((doc.get("invoice") or {}).get("invoice_form_id")) or "").strip()
        if not invoice_id:
            continue
        counters_by_invoice[invoice_id][account] += 1
        kept_entries += 1

    report_rows: list[dict[str, str]] = []
    total_changed = 0
    total_unchanged = 0
    total_no_signal = 0
    total_items = 0

    for path in base_paths:
        stats, rows, updated_data = align_file_accounts(
            path=path,
            counters_by_invoice=counters_by_invoice,
            min_confidence=max(0.0, min(1.0, args.min_confidence)),
        )
        total_items += stats["total_items"]
        total_changed += stats["changed"]
        total_unchanged += stats["unchanged"]
        total_no_signal += stats["no_signal"]
        report_rows.extend(rows)

        if args.apply:
            path.write_text(json.dumps(updated_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print(
            "[INFO] file={file} changed={changed} unchanged={unchanged} no_signal={no_signal} total={total}".format(
                file=path.name,
                changed=stats["changed"],
                unchanged=stats["unchanged"],
                no_signal=stats["no_signal"],
                total=stats["total_items"],
            )
        )

    report_path = Path(args.report_csv)
    if not report_path.is_absolute():
        report_path = (SCRIPT_DIR / report_path).resolve()

    if report_rows:
        with report_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "file",
                    "item_index",
                    "article_source",
                    "old_account",
                    "new_account",
                    "confidence",
                    "top_votes",
                    "total_votes",
                    "source_invoice_ids",
                ],
            )
            writer.writeheader()
            writer.writerows(report_rows)

    mode = "apply" if args.apply else "dry_run"
    print(f"[INFO] db={args.db}")
    print(f"[INFO] mode={mode}")
    print(f"[INFO] scanned_entries={scanned_entries}")
    print(f"[INFO] kept_expense_entries={kept_entries}")
    print(f"[INFO] invoice_ids_with_expense_entries={len(counters_by_invoice)}")
    print(f"[INFO] total_items={total_items}")
    print(f"[INFO] total_changed={total_changed}")
    print(f"[INFO] total_unchanged={total_unchanged}")
    print(f"[INFO] total_no_signal={total_no_signal}")
    if report_rows:
        print(f"[OK] report_csv={report_path}")
    else:
        print("[INFO] report_csv=none (no changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
