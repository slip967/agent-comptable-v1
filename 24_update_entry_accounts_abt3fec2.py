#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
from collections import Counter
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
ACCOUNT_KEYS = {
    "account",
    "account_number",
    "account_code",
    "compte",
    "compte_comptable",
    "code_compte",
    "num_compte",
    "debit_account",
    "credit_account",
    "debit_account_number",
    "credit_account_number",
}


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def parse_mapping(replace_values: list[str], mapping_json: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in replace_values or []:
        if "=" not in value:
            raise SystemExit(f"Format invalide pour --replace: {value} (attendu OLD=NEW)")
        old, new = value.split("=", 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise SystemExit(f"Remplacement invalide: {value}")
        mapping[old] = new

    if mapping_json:
        path = Path(mapping_json)
        if not path.is_absolute():
            path = (SCRIPT_DIR / path).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit("--mapping-json doit contenir un objet JSON {\"old\":\"new\"}.")
        for old, new in payload.items():
            old_s = str(old).strip()
            new_s = str(new).strip()
            if old_s and new_s:
                mapping[old_s] = new_s
    return mapping


def iter_entries(
    session: requests.Session,
    db_name: str,
    require_invoice_link: bool = True,
    invoice_link_mode: str = "invoice_block",
    exclude_generated: bool = True,
    limit: int = 500,
):
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_find"
    selector: dict[str, Any] = {"p": "entry"}
    if require_invoice_link:
        if invoice_link_mode == "top_level":
            selector["invoice_form"] = {"$exists": True}
        elif invoice_link_mode == "nested_id":
            selector["invoice.invoice_form_id"] = {"$exists": True}
        elif invoice_link_mode == "invoice_block":
            selector["invoice"] = {"$exists": True}
        else:
            selector["$or"] = [
                {"invoice_form": {"$exists": True}},
                {"invoice.invoice_form_id": {"$exists": True}},
                {"invoice": {"$exists": True}},
            ]
    if exclude_generated:
        selector["_id"] = {"$regex": "^(?!.*generated).*$"}

    bookmark = None
    while True:
        payload: dict[str, Any] = {
            "selector": selector,
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
            yield doc

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def has_invoice_link(doc: dict, mode: str) -> bool:
    top_level = doc.get("invoice_form")
    nested = (doc.get("invoice") or {}).get("invoice_form_id")
    invoice_block = doc.get("invoice")
    top_ok = top_level not in (None, "", {}, [])
    nested_ok = nested not in (None, "", {}, [])
    invoice_ok = invoice_block not in (None, "", {}, [])
    if mode == "top_level":
        return top_ok
    if mode == "nested_id":
        return nested_ok
    if mode == "invoice_block":
        return invoice_ok
    return top_ok or nested_ok or invoice_ok


def collect_key_paths(obj: Any, prefix: str = "") -> Counter:
    out: Counter = Counter()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out[path] += 1
            out.update(collect_key_paths(value, path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            path = f"{prefix}[{idx}]"
            out.update(collect_key_paths(value, path))
    return out


def looks_like_account(value: str) -> bool:
    raw = value.strip()
    return raw.isdigit() and 2 <= len(raw) <= 12


def find_account_candidates(obj: Any, path: str = "") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            current = f"{path}.{key}" if path else key
            key_l = str(key).strip().lower()
            if isinstance(value, str) and key_l in ACCOUNT_KEYS and looks_like_account(value):
                found.append({"path": current, "value": value})
            found.extend(find_account_candidates(value, current))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            current = f"{path}[{idx}]"
            found.extend(find_account_candidates(value, current))
    return found


def replace_accounts_recursive(obj: Any, mapping: dict[str, str], path: str = "") -> tuple[Any, list[dict[str, str]]]:
    changes: list[dict[str, str]] = []
    if isinstance(obj, dict):
        updated = {}
        for key, value in obj.items():
            current = f"{path}.{key}" if path else key
            key_l = str(key).strip().lower()
            if isinstance(value, str) and key_l in ACCOUNT_KEYS:
                old = value.strip()
                if old in mapping and mapping[old] != old:
                    updated[key] = mapping[old]
                    changes.append({"path": current, "old": old, "new": mapping[old]})
                else:
                    updated[key] = value
            else:
                child, child_changes = replace_accounts_recursive(value, mapping, current)
                updated[key] = child
                changes.extend(child_changes)
        return updated, changes

    if isinstance(obj, list):
        updated_list = []
        for idx, value in enumerate(obj):
            current = f"{path}[{idx}]"
            child, child_changes = replace_accounts_recursive(value, mapping, current)
            updated_list.append(child)
            changes.extend(child_changes)
        return updated_list, changes

    return obj, changes


def bulk_save(session: requests.Session, db_name: str, docs: list[dict]) -> list[dict]:
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_bulk_docs"
    response = session.post(endpoint, json={"docs": docs}, timeout=120)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or update account numbers in entry docs from abt3fec2, "
            "restricted to docs with invoice link block and excluding _id containing generated."
        )
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Target DB (default: abt3fec2).")
    parser.add_argument("--inspect-only", action="store_true", help="Only inspect docs, do not apply replacements.")
    parser.add_argument("--inspect-sample", type=int, default=20, help="Number of sample docs for inspection output.")
    parser.add_argument("--max-docs", type=int, default=0, help="Optional max docs to process (0 = all).")
    parser.add_argument(
        "--allow-missing-invoice-form",
        action="store_true",
        help="Disable invoice link requirement in query (for schema inspection).",
    )
    parser.add_argument(
        "--invoice-link-mode",
        default="invoice_block",
        choices=["invoice_block", "nested_id", "top_level", "either"],
        help="How to detect invoice link on entry docs.",
    )
    parser.add_argument("--replace", action="append", default=[], help="Replacement rule OLD=NEW (repeatable).")
    parser.add_argument("--mapping-json", default="", help="JSON file with mapping {\"old\":\"new\"}.")
    parser.add_argument("--apply", action="store_true", help="Write changes to CouchDB. Without this flag: dry-run.")
    parser.add_argument(
        "--report-csv",
        default="abt3fec2_entry_account_updates_report.csv",
        help="CSV report path for changed docs.",
    )
    parser.add_argument(
        "--inspect-json",
        default="abt3fec2_entry_invoice_form_inspect.json",
        help="JSON report path for inspection mode.",
    )
    args = parser.parse_args()

    mapping = parse_mapping(args.replace, args.mapping_json)
    if not args.inspect_only and not mapping:
        raise SystemExit("Aucune règle de remplacement fournie. Utilise --replace ou --mapping-json.")

    report_csv = Path(args.report_csv)
    if not report_csv.is_absolute():
        report_csv = (SCRIPT_DIR / report_csv).resolve()

    inspect_json = Path(args.inspect_json)
    if not inspect_json.is_absolute():
        inspect_json = (SCRIPT_DIR / inspect_json).resolve()

    session = http_session()

    scanned = 0
    skipped_generated_guard = 0
    skipped_no_invoice_form_guard = 0
    touched_docs = 0
    total_field_changes = 0
    bulk_batch: list[dict] = []
    csv_rows: list[dict[str, str]] = []
    key_counter: Counter = Counter()
    account_path_counter: Counter = Counter()
    account_value_counter: Counter = Counter()
    sample_docs: list[dict[str, Any]] = []

    require_invoice_link = not args.allow_missing_invoice_form

    for doc in iter_entries(
        session=session,
        db_name=args.db,
        require_invoice_link=require_invoice_link,
        invoice_link_mode=args.invoice_link_mode,
    ):
        scanned += 1
        if args.max_docs > 0 and scanned > args.max_docs:
            break

        doc_id = str(doc.get("_id") or "")
        if "generated" in doc_id.lower():
            skipped_generated_guard += 1
            continue
        if require_invoice_link:
            if not has_invoice_link(doc, args.invoice_link_mode):
                skipped_no_invoice_form_guard += 1
                continue

        key_counter.update(collect_key_paths(doc))
        candidates = find_account_candidates(doc)
        for candidate in candidates:
            account_path_counter[candidate["path"]] += 1
            account_value_counter[candidate["value"]] += 1

        if len(sample_docs) < max(0, args.inspect_sample):
            sample_docs.append(
                {
                    "_id": doc_id,
                    "top_keys": list(doc.keys())[:30],
                    "invoice": doc.get("invoice"),
                    "account_candidates": candidates[:20],
                }
            )

        if args.inspect_only:
            continue

        updated_doc, changes = replace_accounts_recursive(doc, mapping)
        if not changes:
            continue

        touched_docs += 1
        total_field_changes += len(changes)
        for change in changes:
            csv_rows.append(
                {
                    "_id": doc_id,
                    "old_account": change["old"],
                    "new_account": change["new"],
                    "path": change["path"],
                }
            )

        if args.apply:
            bulk_batch.append(updated_doc)
            if len(bulk_batch) >= 200:
                results = bulk_save(session=session, db_name=args.db, docs=bulk_batch)
                errors = [row for row in results if row.get("error")]
                if errors:
                    raise RuntimeError(f"_bulk_docs errors: {errors[:5]}")
                bulk_batch = []

    if args.apply and bulk_batch:
        results = bulk_save(session=session, db_name=args.db, docs=bulk_batch)
        errors = [row for row in results if row.get("error")]
        if errors:
            raise RuntimeError(f"_bulk_docs errors: {errors[:5]}")

    if csv_rows:
        with report_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["_id", "old_account", "new_account", "path"])
            writer.writeheader()
            writer.writerows(csv_rows)

    inspect_payload = {
        "db": args.db,
        "invoice_link_mode": args.invoice_link_mode,
        "scanned": scanned,
        "skipped_generated_guard": skipped_generated_guard,
        "skipped_no_invoice_form_guard": skipped_no_invoice_form_guard,
        "touched_docs": touched_docs,
        "total_field_changes": total_field_changes,
        "mode": "inspect_only" if args.inspect_only else ("apply" if args.apply else "dry_run"),
        "mapping": mapping,
        "top_account_values": account_value_counter.most_common(30),
        "top_account_paths": account_path_counter.most_common(30),
        "top_key_paths": key_counter.most_common(40),
        "sample_docs": sample_docs,
        "report_csv": str(report_csv),
    }
    inspect_json.write_text(json.dumps(inspect_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] db={args.db}")
    print(f"[INFO] scanned={scanned}")
    print(f"[INFO] skipped_generated_guard={skipped_generated_guard}")
    print(f"[INFO] skipped_no_invoice_form_guard={skipped_no_invoice_form_guard}")
    print(f"[INFO] mode={inspect_payload['mode']}")
    print(f"[INFO] touched_docs={touched_docs}")
    print(f"[INFO] total_field_changes={total_field_changes}")
    print(f"[OK] inspect_json={inspect_json}")
    if csv_rows:
        print(f"[OK] report_csv={report_csv}")
    else:
        print("[INFO] report_csv=none (no changes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
