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


def find_source_files(patterns: list[str]) -> list[Path]:
    selected: dict[str, Path] = {}
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if path.name.endswith("_with_accounts.json"):
                continue
            selected[str(path.resolve())] = path
    return list(selected.values())


def load_source(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: contenu JSON invalide, objet attendu.")
    meta = payload.get("meta") or {}
    items = payload.get("items") or []
    if not isinstance(meta, dict) or not isinstance(items, list):
        raise ValueError(f"{path.name}: format meta/items invalide.")
    return meta, items


def build_doc(path: Path, meta: dict, items: list[dict], partition_prefix_override: str | None = None) -> dict:
    metier = str(meta.get("metier") or "").strip().lower()
    profile_id = str(meta.get("profile_id") or path.stem).strip()
    partition_prefix = str(
        partition_prefix_override or meta.get("partition_prefix") or "multi"
    ).strip()
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
        "client_siren": meta.get("client_siren"),
        "partition_prefix": partition_prefix,
        "version": version,
        "status": meta.get("status") or "draft",
        "source_file": path.name,
        "source_path": str(path),
        "items_count": len(items),
        "meta": meta,
        "items": items,
        "updated_at": now_iso(),
    }


def get_doc(sess: requests.Session, db: str, doc_id: str):
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(doc_id, safe='')}"
    response = sess.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def put_doc(sess: requests.Session, db: str, doc: dict) -> dict:
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/{quote(doc['_id'], safe='')}"
    response = sess.put(url, json=doc, timeout=60)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importe les bases produits v1 dans CouchDB sous forme de documents p='product_base_profile'."
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
    parser.add_argument(
        "--partition-prefix",
        default="",
        help="Override du partition prefix pour tous les documents.",
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
    for path in source_files:
        meta, items = load_source(path)
        docs.append(build_doc(path, meta, items, args.partition_prefix or None))

    print(f"[INFO] fichiers source: {len(source_files)}")
    print(f"[INFO] docs profile prets: {len(docs)}")
    print(f"[INFO] base cible: {args.db}")

    if args.dry_run:
        print("[DRY-RUN] Aucun document ecrit dans CouchDB.")
        print(json.dumps(docs[:2], ensure_ascii=False, indent=2))
        return

    sess = http_session()
    created = 0
    updated = 0

    for doc in docs:
        existing = get_doc(sess, args.db, doc["_id"])
        if existing and existing.get("_rev"):
            doc["_rev"] = existing["_rev"]
            doc["created_at"] = existing.get("created_at") or now_iso()
            put_doc(sess, args.db, doc)
            updated += 1
        else:
            doc["created_at"] = now_iso()
            put_doc(sess, args.db, doc)
            created += 1

    print(f"[OK] created={created} updated={updated} db={args.db}")


if __name__ == "__main__":
    main()
