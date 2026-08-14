#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
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
from product_base_instances_lib import build_instances_from_source, find_source_files


ROOT = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SAFE_DEFAULT_DB = "ayasmine_test2"
PROTECTED_DBS = {"fec_452416191", "keymanage_accounting"}


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def ensure_safe_target(db: str, dry_run: bool, allow_production_db: bool) -> None:
    target = (db or "").strip()
    if dry_run:
        return
    if target in PROTECTED_DBS and not allow_production_db:
        raise SystemExit(
            f"Refus d'ecriture vers {target}. Utilise --db {SAFE_DEFAULT_DB}, --dry-run, "
            "ou ajoute --allow-production-db si tu assumes explicitement cette cible."
        )


def couch_request(sess: requests.Session, db: str, method: str, path: str = "", **kwargs):
    if path:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}"
    response = sess.request(method, url, timeout=120, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def fetch_existing_revs(sess: requests.Session, db: str, ids: list[str]) -> dict[str, str]:
    revs: dict[str, str] = {}
    for start in range(0, len(ids), 300):
        chunk = ids[start : start + 300]
        payload = {"keys": chunk}
        result = couch_request(sess, db, "POST", "_all_docs", json=payload)
        for row in result.get("rows", []):
            doc_id = str(row.get("id") or "").strip()
            value = row.get("value") or {}
            rev = str(value.get("rev") or "").strip()
            if doc_id and rev:
                revs[doc_id] = rev
    return revs


def bulk_upsert_docs(sess: requests.Session, db: str, docs: list[dict]) -> None:
    for start in range(0, len(docs), 200):
        chunk = docs[start : start + 200]
        couch_request(sess, db, "POST", "_bulk_docs", json={"docs": chunk})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importe dans CouchDB une instance par article_source depuis les bases produits v1."
    )
    parser.add_argument(
        "--db",
        default=os.getenv("DB_ENTRIES", SAFE_DEFAULT_DB),
        help="Base CouchDB cible.",
    )
    parser.add_argument(
        "--pattern",
        nargs="*",
        default=["base_produits_*_v1.json", "base_charges_externes_v1.json"],
        help="Glob(s) des fichiers source a importer.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Construit les docs sans ecrire dans CouchDB.")
    parser.add_argument(
        "--allow-production-db",
        action="store_true",
        help="Autorise l'ecriture vers une base protegee.",
    )
    args = parser.parse_args()

    ensure_safe_target(args.db, args.dry_run, args.allow_production_db)

    source_files = find_source_files(args.pattern)
    if not source_files:
        raise SystemExit(f"Aucun fichier trouve pour les patterns: {args.pattern}")

    docs: list[dict] = []
    stats_by_source: list[tuple[str, int]] = []
    for source in source_files:
        _, source_docs = build_instances_from_source(source)
        docs.extend(source_docs)
        stats_by_source.append((source.name, len(source_docs)))

    print(f"[INFO] fichiers source: {len(source_files)}")
    print(f"[INFO] docs instance prets: {len(docs)}")
    print(f"[INFO] base cible: {args.db}")
    for name, count in stats_by_source:
        print(f"  - {name}: {count}")

    if args.dry_run:
        print("[DRY-RUN] Aucun document ecrit dans CouchDB.")
        return

    sess = http_session()
    ids = [str(doc["_id"]) for doc in docs]
    existing_revs = fetch_existing_revs(sess, args.db, ids)

    created = 0
    updated = 0
    for doc in docs:
        doc_id = str(doc["_id"])
        rev = existing_revs.get(doc_id)
        if rev:
            doc["_rev"] = rev
            updated += 1
        else:
            created += 1

    bulk_upsert_docs(sess, args.db, docs)
    print(f"[OK] created={created} updated={updated} db={args.db}")


if __name__ == "__main__":
    main()
