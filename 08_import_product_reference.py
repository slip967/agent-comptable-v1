#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
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

SAFE_DEFAULT_DB = "ayasmine_test"
PROTECTED_DBS = {"fec_452416191", "keymanage_accounting"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    s = requests.Session()
    s.auth = (COUCHDB_USER, COUCHDB_PASS)
    s.cert = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return s


def stable_doc_id(
    partition_prefix: str,
    profile_id: str,
    metier: str,
    article_canonique: str,
    compte_comptable: str,
    tva_rate,
) -> str:
    raw = f"{profile_id}|{metier}|{article_canonique}|{compte_comptable}|{tva_rate}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{partition_prefix}:productref:{metier}:{digest}"


def load_source(path: Path) -> tuple[dict, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {}, data
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object or a list of items.")
    return data.get("meta") or {}, data.get("items") or []


def build_doc(meta: dict, item: dict, partition_prefix: str, profile_id: str, metier: str) -> dict:
    article_source = (item.get("article_source") or "").strip()
    article_canonique = (item.get("article_canonique") or "").strip().lower()
    compte = str(item.get("compte_comptable") or "").strip()
    tva_rate = item.get("tva_rate")
    status = (item.get("status") or "to_validate").strip()

    doc_id = stable_doc_id(
        partition_prefix=partition_prefix,
        profile_id=profile_id,
        metier=metier,
        article_canonique=article_canonique,
        compte_comptable=compte,
        tva_rate=tva_rate,
    )

    doc = {
        "_id": doc_id,
        "p": "product_reference",
        "data": {"collection": "ProductReference", "type": "AccountingProduct", "sub_type": metier},
        "profile_id": profile_id,
        "metier": metier,
        "client_siren": meta.get("client_siren"),
        "article_source": article_source,
        "article_canonique": article_canonique,
        "categorie": item.get("categorie"),
        "sous_categorie": item.get("sous_categorie"),
        "compte_comptable": compte,
        "tva_rate": tva_rate,
        "mots_cles": item.get("mots_cles") or [],
        "fournisseur_type": item.get("fournisseur_type"),
        "ape_context": item.get("ape_context") or [],
        "status": status,
        "validated_at": item.get("validated_at"),
        "notes": item.get("notes") or "",
        "source_meta": {
            "source_file_profile_id": meta.get("profile_id"),
            "source_version": meta.get("version"),
        },
        "updated_at": now_iso(),
    }

    optional_fields = (
        "source_invoice_ids",
        "compte_comptable_source",
        "compte_comptable_match_score",
        "compte_comptable_match_reason",
        "sous_profil",
        "nature_charge",
        "profil_facturation",
        "profil_facturation_champs",
        "classification_version",
        "classification_reason",
    )
    for key in optional_fields:
        value = item.get(key)
        if value not in (None, "", []):
            doc[key] = value

    return doc


def get_doc(sess: requests.Session, db: str, doc_id: str):
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(doc_id, safe='')}"
    r = sess.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def put_doc(sess: requests.Session, db: str, doc: dict):
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(doc['_id'], safe='')}"
    r = sess.put(url, json=doc, timeout=30)
    r.raise_for_status()
    return r.json()


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
    parser = argparse.ArgumentParser(description="Import product reference profile into CouchDB.")
    parser.add_argument("--input", required=True, help="Input JSON file (base_produits_*.json).")
    parser.add_argument("--db", default=os.getenv("DB_ENTRIES", SAFE_DEFAULT_DB), help="Target CouchDB database.")
    parser.add_argument(
        "--partition-prefix",
        default=os.getenv("V1_PARTITION_PREFIX", "fr_bd_519665103"),
        help="Partition prefix for doc IDs.",
    )
    parser.add_argument("--profile-id", default="", help="Override profile id from file.")
    parser.add_argument("--metier", default="", help="Override metier from file.")
    parser.add_argument(
        "--only-validated",
        action="store_true",
        help="Import only items with status='validated'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build docs without writing to CouchDB.")
    parser.add_argument(
        "--allow-production-db",
        action="store_true",
        help="Allow writes to protected production databases like fec_452416191 or keymanage_accounting.",
    )
    args = parser.parse_args()

    ensure_safe_target(args.db, args.dry_run, args.allow_production_db)

    src = Path(args.input).resolve()
    meta, items = load_source(src)
    if not items:
        raise SystemExit("No items found in input file.")

    partition_prefix = (args.partition_prefix or meta.get("partition_prefix") or "").strip()
    if not partition_prefix:
        raise SystemExit("Missing partition prefix.")

    profile_id = (args.profile_id or meta.get("profile_id") or "product_profile_v1").strip()
    metier = (args.metier or meta.get("metier") or "unknown").strip().lower()

    docs = []
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        if args.only_validated and (item.get("status") or "").strip().lower() != "validated":
            skipped += 1
            continue
        if (item.get("decision_keep_or_exclude") or "").strip().lower() == "exclude":
            skipped += 1
            continue
        if not item.get("article_canonique") or not item.get("compte_comptable"):
            skipped += 1
            continue
        docs.append(build_doc(meta, item, partition_prefix, profile_id, metier))

    print(f"[INFO] input items: {len(items)}")
    print(f"[INFO] docs ready: {len(docs)}")
    print(f"[INFO] skipped: {skipped}")

    if args.dry_run:
        print("[DRY-RUN] Nothing written to CouchDB.")
        preview = docs[:3]
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return

    sess = http_session()
    created = 0
    updated = 0

    for doc in docs:
        existing = get_doc(sess, args.db, doc["_id"])
        if existing and existing.get("_rev"):
            doc["_rev"] = existing["_rev"]
            if existing.get("created_at"):
                doc["created_at"] = existing["created_at"]
            else:
                doc["created_at"] = now_iso()
            put_doc(sess, args.db, doc)
            updated += 1
        else:
            doc["created_at"] = now_iso()
            put_doc(sess, args.db, doc)
            created += 1

    print(f"[OK] created={created} updated={updated} db={args.db}")


if __name__ == "__main__":
    main()
