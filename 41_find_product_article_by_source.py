#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
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
from product_base_instances_lib import normalize_text


COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SAFE_DEFAULT_DB = "ayasmine_test2"
DESIGN_DOC = "product_base_lookup"


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


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


def query_view(
    sess: requests.Session,
    db: str,
    view_name: str,
    key: str,
    limit: int,
) -> list[dict]:
    params = {
        "key": json.dumps(key, ensure_ascii=False),
        "limit": str(limit),
        "reduce": "false",
    }
    path = f"_design/{DESIGN_DOC}/_view/{view_name}"
    payload = couch_request(sess, db, "GET", path, params=params)
    return payload.get("rows", []) or []


def compact_row(row: dict) -> dict:
    value = row.get("value") or {}
    return {
        "_id": value.get("id"),
        "article_source": value.get("article_source"),
        "article_source_normalized": value.get("article_source_normalized"),
        "article_canonique": value.get("article_canonique"),
        "metier": value.get("metier"),
        "profile_id": value.get("profile_id"),
        "categorie": value.get("categorie"),
        "sous_categorie": value.get("sous_categorie"),
        "compte_comptable": value.get("compte_comptable"),
        "source_file": value.get("source_file"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrouve un article product_base_instance par article_source dans CouchDB."
    )
    parser.add_argument(
        "article_source",
        help="Libelle a rechercher.",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("DB_ENTRIES", SAFE_DEFAULT_DB),
        help="Base CouchDB cible.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Nombre max de resultats.",
    )
    parser.add_argument(
        "--exact-only",
        action="store_true",
        help="Ne cherche que le match exact sur article_source.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Affiche les resultats en JSON.",
    )
    args = parser.parse_args()

    sess = http_session()
    rows = query_view(sess, args.db, "by_article_source", args.article_source, args.limit)
    mode = "exact"

    if not rows and not args.exact_only:
        normalized = normalize_text(args.article_source)
        rows = query_view(sess, args.db, "by_article_source_normalized", normalized, args.limit)
        mode = "normalized"

    items = [compact_row(row) for row in rows]

    print(f"[INFO] db={args.db} mode={mode} results={len(items)}")
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return

    if not items:
        print("[INFO] aucun article trouve.")
        return

    for index, item in enumerate(items, start=1):
        print(
            f"[{index}] {item.get('article_source') or ''} | "
            f"metier={item.get('metier') or ''} | "
            f"compte={item.get('compte_comptable') or ''} | "
            f"categorie={item.get('categorie') or ''} / {item.get('sous_categorie') or ''} | "
            f"id={item.get('_id') or ''}"
        )


if __name__ == "__main__":
    main()
