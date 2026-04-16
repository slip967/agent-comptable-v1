#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
from collections import Counter, defaultdict
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


SCRIPT_DIR = Path(__file__).resolve().parent

COUCHDB_URL = DEFAULT_COUCHDB_URL.rstrip("/")
COUCHDB_USER = DEFAULT_COUCHDB_USER
COUCHDB_PASS = DEFAULT_COUCHDB_PASS
CLIENT_CERT = DEFAULT_CLIENT_CERT
CLIENT_KEY = DEFAULT_CLIENT_KEY
CA_CERT = DEFAULT_CA_CERT

SAFE_DEFAULT_DB = "ayasmine_test"
PROTECTED_DBS = {"fec_452416191", "keymanage_accounting"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def unwrap_value(value):
    if isinstance(value, dict) and "value" in value:
        return unwrap_value(value.get("value"))
    return value


def as_text(value) -> str:
    raw = unwrap_value(value)
    if raw is None:
        return ""
    return str(raw).strip()


def load_detail_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload.get("items") or []


def aggregate_invoice_profiles(items: list[dict]) -> dict[str, dict]:
    by_invoice: dict[str, dict] = {}

    for item in items:
        source = item.get("source") or {}
        source_invoices = source.get("source_invoices") or []
        if not source_invoices:
            continue

        article_source = as_text(source.get("article_source"))
        article_canonique = as_text(source.get("article_canonique"))
        categorie = as_text(source.get("categorie"))
        sous_categorie = as_text(source.get("sous_categorie"))
        sous_profil = as_text(source.get("sous_profil"))
        nature_charge = as_text(source.get("nature_charge"))
        profil_facturation = as_text(source.get("profil_facturation"))
        compte_comptable = as_text(source.get("compte_comptable"))
        tva_rate = unwrap_value(source.get("tva_rate"))
        profile_fields = [as_text(field_name) for field_name in (source.get("profil_facturation_champs") or []) if as_text(field_name)]

        for inv in source_invoices:
            invoice_id = as_text(inv.get("invoice_id"))
            if not invoice_id:
                continue

            bucket = by_invoice.setdefault(
                invoice_id,
                {
                    "invoice_id": invoice_id,
                    "invoice_number": as_text(inv.get("invoice_number")),
                    "invoice_date": as_text(inv.get("invoice_date")),
                    "issuer_name": as_text(inv.get("issuer_name")),
                    "issuer_siren": as_text(inv.get("issuer_siren")),
                    "issuer_ape": as_text(inv.get("issuer_ape")),
                    "recipient_name": as_text(inv.get("recipient_name")),
                    "recipient_siren": as_text(inv.get("recipient_siren")),
                    "recipient_ape": as_text(inv.get("recipient_ape")),
                    "sub_profiles": defaultdict(
                        lambda: {
                            "sous_profil": "",
                            "categorie": "",
                            "sous_categorie": "",
                            "nature_charge_counter": Counter(),
                            "profil_facturation_counter": Counter(),
                            "fields": set(),
                            "compte_counter": Counter(),
                            "article_counter": Counter(),
                            "item_ids": set(),
                        }
                    ),
                    "line_examples": [],
                },
            )

            sp = bucket["sub_profiles"][sous_profil]
            sp["sous_profil"] = sous_profil
            sp["categorie"] = categorie
            sp["sous_categorie"] = sous_categorie
            if nature_charge:
                sp["nature_charge_counter"][nature_charge] += 1
            if profil_facturation:
                sp["profil_facturation_counter"][profil_facturation] += 1
            for field_name in profile_fields:
                sp["fields"].add(field_name)
            if compte_comptable:
                sp["compte_counter"][compte_comptable] += 1
            if article_source:
                sp["article_counter"][article_source] += 1
            sp["item_ids"].add(as_text(item.get("item_id")))

            if article_source and len(bucket["line_examples"]) < 12:
                bucket["line_examples"].append(
                    {
                        "article_source": article_source,
                        "article_canonique": article_canonique,
                        "sous_profil": sous_profil,
                        "nature_charge": nature_charge,
                        "compte_comptable": compte_comptable,
                        "tva_rate": tva_rate,
                    }
                )

    return by_invoice


def fetch_docs(session: requests.Session, db: str, doc_ids: list[str]) -> dict[str, dict]:
    if not doc_ids:
        return {}
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_all_docs?include_docs=true"
    response = session.post(url, json={"keys": doc_ids}, timeout=120)
    response.raise_for_status()
    docs: dict[str, dict] = {}
    for row in response.json().get("rows", []):
        doc = row.get("doc")
        if isinstance(doc, dict) and doc.get("_id"):
            docs[str(doc["_id"])] = doc
    return docs


def dominant_label(counter: Counter) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def build_profile_payload(record: dict, core_profile_id: str) -> dict:
    sub_profiles_payload = []
    all_fields: set[str] = set()
    all_accounts: set[str] = set()

    for sous_profil, payload in sorted(record["sub_profiles"].items()):
        accounts = [account for account, _ in payload["compte_counter"].most_common() if account]
        fields = sorted(payload["fields"])
        all_fields.update(fields)
        all_accounts.update(accounts)
        sub_profiles_payload.append(
            {
                "sous_profil": sous_profil,
                "categorie": payload["categorie"],
                "sous_categorie": payload["sous_categorie"],
                "nature_charge": dominant_label(payload["nature_charge_counter"]),
                "profil_facturation": dominant_label(payload["profil_facturation_counter"]),
                "profil_facturation_champs": fields,
                "comptes_comptables": accounts,
                "articles_exemples": [label for label, _ in payload["article_counter"].most_common(5)],
                "items_count": len(payload["item_ids"]),
            }
        )

    recommended_accounts = sorted(account for account in all_accounts if account)
    needs_split = len(sub_profiles_payload) > 1 or len(recommended_accounts) > 1

    return {
        "generated_at": now_iso(),
        "source": "invoice_form_matched_v1",
        "classification": "charge_externe",
        "invoice_number_source": record["invoice_number"],
        "invoice_date_source": record["invoice_date"],
        "core_profile_id": core_profile_id or None,
        "issuer_name": record["issuer_name"] or None,
        "issuer_siren": record["issuer_siren"] or None,
        "issuer_ape": record["issuer_ape"] or None,
        "recipient_name": record["recipient_name"] or None,
        "recipient_siren": record["recipient_siren"] or None,
        "recipient_ape": record["recipient_ape"] or None,
        "sub_profiles_count": len(sub_profiles_payload),
        "sub_profiles": sub_profiles_payload,
        "capture_fields": sorted(all_fields),
        "recommended_charge_accounts": recommended_accounts,
        "recommended_charge_account": recommended_accounts[0] if len(recommended_accounts) == 1 else None,
        "needs_split_review": needs_split,
        "line_examples": record["line_examples"],
    }


def build_invoice_row(record: dict, invoice_doc: dict | None, core_doc: dict | None, status: str) -> dict:
    invoice_number = ""
    invoice_date = ""
    if invoice_doc:
        invoice_number = as_text(invoice_doc.get("invoice_number")) or record["invoice_number"]
        invoice_date = as_text(invoice_doc.get("invoice_date")) or record["invoice_date"]
    else:
        invoice_number = record["invoice_number"]
        invoice_date = record["invoice_date"]

    sub_profiles = sorted(sp for sp in record["sub_profiles"].keys() if sp)
    all_accounts = sorted(
        {
            account
            for payload in record["sub_profiles"].values()
            for account in payload["compte_counter"].keys()
            if account
        }
    )

    return {
        "invoice_id": record["invoice_id"],
        "core_profile_id": as_text((invoice_doc or {}).get("form_common_core_ref", {}).get("id")) or (core_doc or {}).get("_id", ""),
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "issuer_name": record["issuer_name"],
        "issuer_siren": record["issuer_siren"],
        "sub_profiles": " | ".join(sub_profiles),
        "recommended_accounts": " | ".join(all_accounts),
        "needs_split_review": "yes" if len(sub_profiles) > 1 or len(all_accounts) > 1 else "no",
        "status": status,
    }


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


def write_report(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "invoice_id",
        "core_profile_id",
        "invoice_number",
        "invoice_date",
        "issuer_name",
        "issuer_siren",
        "sub_profiles",
        "recommended_accounts",
        "needs_split_review",
        "status",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_safe_target(db: str, dry_run: bool, allow_production_db: bool) -> None:
    db = (db or "").strip()
    if dry_run:
        return
    if db in PROTECTED_DBS and not allow_production_db:
        raise SystemExit(
            f"Refus d'ecriture vers {db}. Utilise --db {SAFE_DEFAULT_DB}, --dry-run, "
            "ou ajoute --allow-production-db si tu assumes explicitement cette cible."
        )


def main():
    parser = argparse.ArgumentParser(
        description="Attach external charge profiles to invoice_form and core_profile docs in CouchDB."
    )
    parser.add_argument(
        "--detail-json",
        default="v1_519665103_profile_charges_externes_detail_v1.json",
        help="Detailed external charges profile JSON generated from script 15.",
    )
    parser.add_argument(
        "--db",
        default=SAFE_DEFAULT_DB,
        help="CouchDB database containing invoice_form/core_profile docs to enrich.",
    )
    parser.add_argument(
        "--report-csv",
        default="v1_519665103_invoice_charge_profiles_report.csv",
        help="CSV report path.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write documents back to CouchDB.")
    parser.add_argument(
        "--allow-production-db",
        action="store_true",
        help="Allow writes to protected production databases like fec_452416191 or keymanage_accounting.",
    )
    args = parser.parse_args()

    ensure_safe_target(args.db, args.dry_run, args.allow_production_db)

    detail_json = (SCRIPT_DIR / args.detail_json).resolve()
    report_csv = (SCRIPT_DIR / args.report_csv).resolve()

    items = load_detail_items(detail_json)
    by_invoice = aggregate_invoice_profiles(items)
    invoice_ids = sorted(by_invoice.keys())

    session = http_session()
    invoice_docs = fetch_docs(session, args.db, invoice_ids)
    core_ids = sorted(
        {
            as_text((invoice_docs.get(invoice_id) or {}).get("form_common_core_ref", {}).get("id"))
            for invoice_id in invoice_ids
        }
    )
    core_ids = [core_id for core_id in core_ids if core_id]
    core_docs = fetch_docs(session, args.db, core_ids)

    invoice_updates = []
    core_updates = []
    report_rows = []
    missing = 0

    for invoice_id in invoice_ids:
        record = by_invoice[invoice_id]
        invoice_doc = invoice_docs.get(invoice_id)
        if not invoice_doc:
            missing += 1
            report_rows.append(build_invoice_row(record, None, None, status="invoice_missing"))
            continue

        core_profile_id = as_text((invoice_doc.get("form_common_core_ref") or {}).get("id"))
        payload = build_profile_payload(record, core_profile_id)

        invoice_before = json.dumps(invoice_doc.get("external_charge_profile_v1"), ensure_ascii=False, sort_keys=True)
        invoice_after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        invoice_status = "already_up_to_date"
        if invoice_before != invoice_after:
            invoice_doc["external_charge_profile_v1"] = payload
            invoice_updates.append(invoice_doc)
            invoice_status = "invoice_updated" if not args.dry_run else "invoice_would_update"

        core_doc = core_docs.get(core_profile_id) if core_profile_id else None
        if core_doc:
            core_before = json.dumps(core_doc.get("external_charge_profile_v1"), ensure_ascii=False, sort_keys=True)
            core_after = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if core_before != core_after:
                core_doc["external_charge_profile_v1"] = payload
                core_updates.append(core_doc)
                if invoice_status == "already_up_to_date":
                    invoice_status = "core_updated" if not args.dry_run else "core_would_update"
                else:
                    invoice_status += "+core"
        else:
            if invoice_status == "already_up_to_date":
                invoice_status = "core_missing"
            else:
                invoice_status += "+core_missing"

        report_rows.append(build_invoice_row(record, invoice_doc, core_doc, status=invoice_status))

    invoice_ok = core_ok = invoice_errors = core_errors = 0
    if not args.dry_run:
        invoice_ok, invoice_errors = bulk_update(session, args.db, invoice_updates)
        core_ok, core_errors = bulk_update(session, args.db, core_updates)

    write_report(report_csv, report_rows)

    print(f"[INFO] invoices_detected={len(invoice_ids)}")
    print(f"[INFO] invoice_docs_found={len(invoice_docs)}")
    print(f"[INFO] core_docs_found={len(core_docs)}")
    print(f"[INFO] missing_invoice_docs={missing}")
    if args.dry_run:
        print(f"[INFO] invoice_docs_to_update={len(invoice_updates)}")
        print(f"[INFO] core_docs_to_update={len(core_updates)}")
    else:
        print(f"[OK] invoice_docs_updated={invoice_ok} errors={invoice_errors}")
        print(f"[OK] core_docs_updated={core_ok} errors={core_errors}")
    print(f"[OK] report={report_csv}")


if __name__ == "__main__":
    main()
