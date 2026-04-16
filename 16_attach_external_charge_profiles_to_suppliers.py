#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import hashlib
import json
import re
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

LEGAL_TOKENS = {
    "sas",
    "sarl",
    "sa",
    "sasu",
    "eurl",
    "ltd",
    "company",
    "cie",
}

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


def normalize_label(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [token for token in value.split() if token and token not in LEGAL_TOKENS]
    return " ".join(tokens)


def compact_label(value: str) -> str:
    return normalize_label(value).replace(" ", "")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def display_sub_profile_name(value: str) -> str:
    return (value or "").replace("_", " ").strip().title()


def load_profile_detail(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload.get("items") or []


def aggregate_supplier_profiles(items: list[dict]) -> dict[str, dict]:
    by_supplier: dict[str, dict] = {}

    for item in items:
        source = item.get("source") or {}
        source_invoices = source.get("source_invoices") or []
        issuer_name = ""
        issuer_siren = ""
        issuer_ape = ""
        if source_invoices:
            main = source_invoices[0] or {}
            issuer_name = (main.get("issuer_name") or "").strip()
            issuer_siren = (main.get("issuer_siren") or "").strip()
            issuer_ape = (main.get("issuer_ape") or "").strip()
        if not issuer_name:
            issuer_name = ((source.get("issuer_names_top") or [[None]])[0][0] or "").strip()
        if not issuer_ape:
            issuer_ape = ((source.get("issuer_apes_top") or [[None]])[0][0] or "").strip()
        if not issuer_name:
            continue

        key = normalize_label(issuer_name)
        record = by_supplier.setdefault(
            key,
            {
                "issuer_name": issuer_name,
                "issuer_siren": issuer_siren,
                "issuer_ape": issuer_ape,
                "sub_profiles": defaultdict(
                    lambda: {
                        "sous_profil": "",
                        "profil_facturation": "",
                        "profil_facturation_champs": set(),
                        "nature_charge_counter": Counter(),
                        "compte_counter": Counter(),
                        "articles_counter": Counter(),
                        "invoice_ids": set(),
                        "examples": [],
                    }
                ),
            },
        )

        sous_profil = (source.get("sous_profil") or "").strip()
        profile = record["sub_profiles"][sous_profil]
        profile["sous_profil"] = sous_profil
        profile["profil_facturation"] = (source.get("profil_facturation") or "").strip()
        for field_name in source.get("profil_facturation_champs") or []:
            if field_name:
                profile["profil_facturation_champs"].add(field_name)
        profile["nature_charge_counter"][(source.get("nature_charge") or "").strip()] += 1
        profile["compte_counter"][(source.get("compte_comptable") or "").strip()] += 1
        article_source = (source.get("article_source") or "").strip()
        if article_source:
            profile["articles_counter"][article_source] += 1
        for inv in source_invoices:
            invoice_id = (inv.get("invoice_id") or "").strip()
            if invoice_id:
                profile["invoice_ids"].add(invoice_id)
        if article_source and len(profile["examples"]) < 5 and article_source not in profile["examples"]:
            profile["examples"].append(article_source)

    return by_supplier


def fetch_suppliers(session: requests.Session, db: str, partition_prefix: str) -> list[dict]:
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
    payload = {
        "selector": {"p": "supplier"},
        "fields": ["_id", "_rev", "p", "data", "label", "siren", "sub_profile", "accounts", "created_at", "updated_at"],
        "limit": 1000,
    }
    response = session.post(url, json=payload, timeout=120)
    response.raise_for_status()
    return response.json().get("docs", [])


def fetch_company_doc(session: requests.Session, siren: str) -> dict | None:
    siren = (siren or "").strip()
    if not siren:
        return None
    for db in ("abt3", "keymanage_accounting"):
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(f'company:{siren}', safe='')}"
        response = session.get(url, timeout=60)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        return response.json()
    return None


def create_supplier_doc_from_source(partition_prefix: str, payload: dict, company_doc: dict | None) -> dict:
    issuer_name = payload["issuer_name"]
    issuer_siren = (payload["issuer_siren"] or "").strip()
    issuer_ape = (payload["issuer_ape"] or "").strip()
    digest = hashlib.sha1(f"{partition_prefix}|supplier|{issuer_siren}|{issuer_name}".encode("utf-8")).hexdigest()[:24]

    doc = {
        "_id": f"{partition_prefix}:{digest}",
        "p": "supplier",
        "data": {"collection": "Contact", "type": "Supplier", "sub_type": ""},
        "label": issuer_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "sub_profile": [
            {
                "name_sub_profile": "Auxiliary",
                "uid_sub_profile": f"auxiliary:auto:{digest}",
                "grouped": False,
            }
        ],
        "accounts": [],
    }
    if issuer_siren:
        doc["siren"] = issuer_siren
    if issuer_ape:
        doc["ape"] = issuer_ape

    if company_doc:
        formality = ((company_doc.get("formality") or {}).get("content") or {}).get("personneMorale") or {}
        etab = (formality.get("etablissementPrincipal") or {}).get("descriptionEtablissement") or {}
        enseigne = (etab.get("enseigne") or "").strip()
        if enseigne:
            doc["label"] = enseigne
        code_ape = (etab.get("codeApe") or "").strip()
        if code_ape:
            doc["ape"] = code_ape

    return doc


def choose_best_supplier_match(source_label: str, source_siren: str, suppliers: list[dict]) -> dict | None:
    normalized_source = normalize_label(source_label)
    if not normalized_source:
        return None
    compact_source = compact_label(source_label)
    source_siren = (source_siren or "").strip()

    if source_siren:
        exact_siren = [doc for doc in suppliers if (doc.get("siren") or "").strip() == source_siren]
        if exact_siren:
            return exact_siren[0]

    exact = [doc for doc in suppliers if normalize_label(doc.get("label") or "") == normalized_source]
    if exact:
        return exact[0]

    compact_exact = [doc for doc in suppliers if compact_label(doc.get("label") or "") == compact_source]
    if compact_exact:
        return compact_exact[0]

    containment = []
    for doc in suppliers:
        normalized_doc = normalize_label(doc.get("label") or "")
        if not normalized_doc:
            continue
        if normalized_source in normalized_doc or normalized_doc in normalized_source:
            containment.append((abs(len(normalized_doc) - len(normalized_source)), doc))
    if containment:
        containment.sort(key=lambda item: item[0])
        return containment[0][1]

    source_tokens = set(normalized_source.split())
    fuzzy_matches = []
    for doc in suppliers:
        normalized_doc = normalize_label(doc.get("label") or "")
        doc_tokens = set(normalized_doc.split())
        if not doc_tokens:
            continue
        overlap = source_tokens & doc_tokens
        if not overlap:
            continue
        score = len(overlap) / max(1, min(len(source_tokens), len(doc_tokens)))
        if score >= 0.5:
            fuzzy_matches.append((-score, abs(len(doc_tokens) - len(source_tokens)), doc))
    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda item: (item[0], item[1]))
        return fuzzy_matches[0][2]

    return None


def build_sub_profile_entry(sous_profil: str, payload: dict) -> dict:
    nature_charge = payload["nature_charge_counter"].most_common(1)[0][0] if payload["nature_charge_counter"] else ""
    comptes = [value for value, _count in payload["compte_counter"].most_common(5) if value]
    return {
        "name_sub_profile": display_sub_profile_name(sous_profil),
        "uid_sub_profile": f"charge_profile:{slugify(sous_profil)}",
        "grouped": True,
        "category": "charges_externes",
        "profil_facturation": payload["profil_facturation"],
        "profil_facturation_champs": sorted(payload["profil_facturation_champs"]),
        "nature_charge": nature_charge,
        "comptes_comptables_top": comptes,
        "articles_exemples": payload["examples"][:5],
        "invoice_form_ids": sorted(payload["invoice_ids"])[:10],
        "source": "invoice_form_matched_v1",
    }


def merge_sub_profiles(existing: list[dict], aggregated_profiles: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    updated = list(existing or [])
    created_entries: list[dict] = []

    by_uid = {str(item.get("uid_sub_profile") or ""): item for item in updated if isinstance(item, dict)}

    for sous_profil, payload in aggregated_profiles.items():
        entry = build_sub_profile_entry(sous_profil, payload)
        uid = entry["uid_sub_profile"]
        if uid in by_uid:
            current = by_uid[uid]
            current.update(entry)
        else:
            updated.append(entry)
            created_entries.append(entry)

    updated.sort(key=lambda item: (str(item.get("uid_sub_profile") or ""), str(item.get("name_sub_profile") or "")))
    return updated, created_entries


def merge_accounts(existing: list[dict] | None, aggregated_profiles: dict[str, dict]) -> list[dict]:
    updated = list(existing or [])
    by_account = {str(item.get("account_number") or ""): item for item in updated if isinstance(item, dict) and item.get("account_number")}

    for payload in aggregated_profiles.values():
        for account_number, _count in payload["compte_counter"].most_common(5):
            if not account_number:
                continue
            if account_number not in by_account:
                by_account[account_number] = {
                    "account_number": account_number,
                    "account_description": "",
                    "account_keywords": "",
                }
                updated.append(by_account[account_number])

    updated.sort(key=lambda item: str(item.get("account_number") or ""))
    return updated


def put_doc(session: requests.Session, db: str, doc: dict) -> None:
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(doc['_id'], safe='')}"
    response = session.put(url, json=doc, timeout=120)
    response.raise_for_status()


def ensure_safe_target(db: str, dry_run: bool, allow_production_db: bool) -> None:
    db = (db or "").strip()
    if dry_run:
        return
    if db in PROTECTED_DBS and not allow_production_db:
        raise SystemExit(
            f"Refus d'ecriture vers {db}. Utilise --db {SAFE_DEFAULT_DB}, --dry-run, "
            "ou ajoute --allow-production-db si tu assumes explicitement cette cible."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach external charge sub-profiles to supplier contacts in CouchDB.")
    parser.add_argument(
        "--input-json",
        default="v1_519665103_profile_charges_externes_detail_v1.json",
        help="Detailed external charge profile JSON built from script 15.",
    )
    parser.add_argument("--db", default=SAFE_DEFAULT_DB, help="Target CouchDB database.")
    parser.add_argument("--partition-prefix", default="fr_bd_519665103", help="Target partition prefix.")
    parser.add_argument(
        "--report-csv",
        default="v1_519665103_supplier_charge_profiles_report.csv",
        help="CSV report of matched/unmatched suppliers.",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Create missing supplier docs from company data when no supplier match exists.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to CouchDB.")
    parser.add_argument(
        "--allow-production-db",
        action="store_true",
        help="Allow writes to protected production databases like fec_452416191 or keymanage_accounting.",
    )
    args = parser.parse_args()

    ensure_safe_target(args.db, args.dry_run, args.allow_production_db)

    input_path = (SCRIPT_DIR / args.input_json).resolve() if not Path(args.input_json).is_absolute() else Path(args.input_json).resolve()
    report_path = (SCRIPT_DIR / args.report_csv).resolve() if not Path(args.report_csv).is_absolute() else Path(args.report_csv).resolve()

    items = load_profile_detail(input_path)
    suppliers_payload = aggregate_supplier_profiles(items)

    session = http_session()
    supplier_docs = fetch_suppliers(session, args.db, args.partition_prefix)

    report_rows: list[dict] = []
    matched_count = 0
    updated_count = 0

    for normalized_supplier, payload in sorted(suppliers_payload.items(), key=lambda item: item[1]["issuer_name"]):
        supplier_doc = choose_best_supplier_match(payload["issuer_name"], payload["issuer_siren"], supplier_docs)
        if not supplier_doc:
            report_rows.append(
                {
                    "issuer_name_source": payload["issuer_name"],
                    "issuer_siren_source": payload["issuer_siren"],
                    "issuer_ape_source": payload["issuer_ape"],
                    "matched_doc_id": "",
                    "matched_label": "",
                    "matched": "no",
                    "sub_profiles_added": " | ".join(sorted(payload["sub_profiles"].keys())),
                    "accounts_added": "",
                }
            )
            continue

        matched_count += 1
        existing_sub_profiles = list(supplier_doc.get("sub_profile") or [])
        merged_sub_profiles, created_entries = merge_sub_profiles(existing_sub_profiles, payload["sub_profiles"])
        merged_accounts = merge_accounts(supplier_doc.get("accounts"), payload["sub_profiles"])

        before_snapshot = json.dumps(existing_sub_profiles, ensure_ascii=False, sort_keys=True)
        after_snapshot = json.dumps(merged_sub_profiles, ensure_ascii=False, sort_keys=True)
        before_accounts = json.dumps(supplier_doc.get("accounts") or [], ensure_ascii=False, sort_keys=True)
        after_accounts = json.dumps(merged_accounts, ensure_ascii=False, sort_keys=True)

        if before_snapshot != after_snapshot or before_accounts != after_accounts:
            supplier_doc["sub_profile"] = merged_sub_profiles
            supplier_doc["accounts"] = merged_accounts
            supplier_doc["updated_at"] = now_iso()
            supplier_doc["external_charge_profiles_v1"] = {
                "generated_at": now_iso(),
                "source_file": str(input_path),
                "supplier_label_source": payload["issuer_name"],
                "supplier_siren_source": payload["issuer_siren"] or None,
                "supplier_ape_source": payload["issuer_ape"] or None,
                "sub_profiles": [
                    build_sub_profile_entry(sous_profil, details)
                    for sous_profil, details in sorted(payload["sub_profiles"].items())
                ],
            }
            if not args.dry_run:
                put_doc(session, args.db, supplier_doc)
            updated_count += 1

        report_rows.append(
            {
                "issuer_name_source": payload["issuer_name"],
                "issuer_siren_source": payload["issuer_siren"],
                "issuer_ape_source": payload["issuer_ape"],
                "matched_doc_id": supplier_doc.get("_id", ""),
                "matched_label": supplier_doc.get("label", ""),
                "matched": "yes",
                "sub_profiles_added": " | ".join(entry["name_sub_profile"] for entry in created_entries),
                "accounts_added": " | ".join(
                    account.get("account_number", "")
                    for account in merged_accounts
                    if account.get("account_number")
                ),
            }
        )

    if args.create_missing:
        remaining_unmatched = [row for row in report_rows if row["matched"] == "no"]
        for row in remaining_unmatched:
            source_label = row["issuer_name_source"]
            source_siren = row["issuer_siren_source"]
            key = normalize_label(source_label)
            payload = suppliers_payload.get(key)
            if not payload:
                continue
            company_doc = fetch_company_doc(session, source_siren)
            new_doc = create_supplier_doc_from_source(args.partition_prefix, payload, company_doc)
            merged_sub_profiles, created_entries = merge_sub_profiles(new_doc.get("sub_profile") or [], payload["sub_profiles"])
            merged_accounts = merge_accounts(new_doc.get("accounts"), payload["sub_profiles"])
            new_doc["sub_profile"] = merged_sub_profiles
            new_doc["accounts"] = merged_accounts
            new_doc["external_charge_profiles_v1"] = {
                "generated_at": now_iso(),
                "source_file": str(input_path),
                "supplier_label_source": payload["issuer_name"],
                "supplier_siren_source": payload["issuer_siren"] or None,
                "supplier_ape_source": payload["issuer_ape"] or None,
                "sub_profiles": [
                    build_sub_profile_entry(sous_profil, details)
                    for sous_profil, details in sorted(payload["sub_profiles"].items())
                ],
            }
            if not args.dry_run:
                put_doc(session, args.db, new_doc)
            updated_count += 1
            matched_count += 1
            row["matched"] = "created"
            row["matched_doc_id"] = new_doc["_id"]
            row["matched_label"] = new_doc.get("label", "")
            row["sub_profiles_added"] = " | ".join(entry["name_sub_profile"] for entry in created_entries)
            row["accounts_added"] = " | ".join(
                account.get("account_number", "")
                for account in merged_accounts
                if account.get("account_number")
            )

    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "issuer_name_source",
            "issuer_siren_source",
            "issuer_ape_source",
            "matched_doc_id",
            "matched_label",
            "matched",
            "sub_profiles_added",
            "accounts_added",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"[INFO] suppliers_detected={len(suppliers_payload)}")
    print(f"[INFO] suppliers_matched={matched_count}")
    print(f"[OK] suppliers_updated={updated_count} dry_run={args.dry_run}")
    print(f"[OK] report_csv={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
