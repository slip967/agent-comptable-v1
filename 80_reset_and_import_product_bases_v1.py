#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
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
from product_base_instances_lib import build_instances_from_source, find_source_files, load_source


ROOT = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SAFE_DEFAULT_DB = "ayasmine_test2"
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


def build_profile_doc(path: Path, meta: dict, items: list[dict]) -> dict:
    metier = str(meta.get("metier") or "").strip().lower()
    profile_id = str(meta.get("profile_id") or path.stem).strip()
    source_client = str(meta.get("source_client") or meta.get("client_siren") or "").strip()
    derived_partition = f"fr_bd_{source_client}" if source_client.isdigit() and len(source_client) == 9 else "multi"
    partition_prefix = str(meta.get("partition_prefix") or derived_partition or "multi").strip()
    version = str(meta.get("version") or "v1").strip()
    doc_id = f"{partition_prefix}:profile:{profile_id}"
    return {
        "_id": doc_id,
        "p": "product_base_profile",
        "data": {
            "collection": "Profile",
            "type": "ProductBase",
            "sub_type": metier or "unknown",
        },
        "profile_kind": "product_base_metier",
        "profile_id": profile_id,
        "metier": metier,
        "client_siren": meta.get("client_siren") or source_client or None,
        "partition_prefix": partition_prefix,
        "version": version,
        "status": meta.get("status") or "draft",
        "source_file": path.name,
        "items_count": len(items),
        "meta": meta,
        "items": items,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def fetch_existing_revs(sess: requests.Session, db: str, ids: list[str]) -> dict[str, str]:
    revs: dict[str, str] = {}
    for start in range(0, len(ids), 300):
        chunk = ids[start : start + 300]
        result = couch_request(sess, db, "POST", "_all_docs", json={"keys": chunk})
        for row in result.get("rows", []):
            doc_id = str(row.get("id") or "").strip()
            rev = str((row.get("value") or {}).get("rev") or "").strip()
            if doc_id and rev:
                revs[doc_id] = rev
    return revs


def bulk_upsert_docs(sess: requests.Session, db: str, docs: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for start in range(0, len(docs), 200):
        chunk = docs[start : start + 200]
        result = couch_request(sess, db, "POST", "_bulk_docs", json={"docs": chunk})
        rows.extend(result)
        errors = [row for row in result if row.get("error")]
        if errors:
            sample = json.dumps(errors[:5], ensure_ascii=False, indent=2)
            raise RuntimeError(f"Erreurs CouchDB sur _bulk_docs: {sample}")
    return rows


def purge_docs(sess: requests.Session, db: str, revs_by_id: dict[str, str]) -> int:
    purged = 0
    doc_ids = list(revs_by_id.keys())
    for start in range(0, len(doc_ids), 25):
        chunk_ids = doc_ids[start : start + 25]
        payload = {doc_id: [revs_by_id[doc_id]] for doc_id in chunk_ids}
        result = couch_request(sess, db, "POST", "_purge", json=payload)
        purged_docs = result.get("purged", {}) or {}
        purged += len(purged_docs)
    return purged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supprime les anciens profiles/instances V1 puis importe les profiles et instances dans CouchDB."
    )
    parser.add_argument("--db", default=SAFE_DEFAULT_DB, help="Base CouchDB cible.")
    parser.add_argument(
        "--pattern",
        nargs="*",
        default=["base_produits_*_v1.json", "base_charges_externes_v1.json"],
        help="Glob(s) des fichiers V1 a traiter.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simule sans ecrire.")
    parser.add_argument("--allow-production-db", action="store_true")
    args = parser.parse_args()

    ensure_safe_target(args.db, args.dry_run, args.allow_production_db)

    source_files = find_source_files(args.pattern)
    if not source_files:
        raise SystemExit(f"Aucun fichier trouve pour les patterns: {args.pattern}")

    profile_docs: list[dict] = []
    instance_docs: list[dict] = []
    stats: list[tuple[str, int]] = []

    for source in source_files:
        meta, items = load_source(source)
        profile_docs.append(build_profile_doc(source, meta, items))
        _, docs = build_instances_from_source(source)
        instance_docs.extend(docs)
        stats.append((source.name, len(docs)))

    print(f"[INFO] base cible: {args.db}")
    print(f"[INFO] fichiers source: {len(source_files)}")
    print(f"[INFO] profiles a importer: {len(profile_docs)}")
    print(f"[INFO] instances a importer: {len(instance_docs)}")
    for name, count in stats:
        print(f"  - {name}: {count}")

    if args.dry_run:
        print("[DRY-RUN] Aucun document ecrit dans CouchDB.")
        print(json.dumps(profile_docs[:1], ensure_ascii=False, indent=2))
        print(json.dumps(instance_docs[:1], ensure_ascii=False, indent=2))
        return

    sess = http_session()
    target_ids = [doc["_id"] for doc in profile_docs] + [doc["_id"] for doc in instance_docs]
    existing_revs = fetch_existing_revs(sess, args.db, target_ids)
    print(f"[INFO] docs existants a purger: {len(existing_revs)}")
    if existing_revs:
        purged = purge_docs(sess, args.db, existing_revs)
        print(f"[OK] purged={purged}")

    bulk_upsert_docs(sess, args.db, profile_docs)
    print(f"[OK] profiles_upserted={len(profile_docs)}")

    bulk_upsert_docs(sess, args.db, instance_docs)
    print(f"[OK] instances_upserted={len(instance_docs)}")


if __name__ == "__main__":
    main()
