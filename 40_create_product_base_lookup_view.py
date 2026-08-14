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


COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SAFE_DEFAULT_DB = "ayasmine_test2"
DESIGN_DOC_ID = "_design/product_base_lookup"


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def couch_request(
    sess: requests.Session,
    db: str,
    method: str,
    path: str = "",
    *,
    allow_404: bool = False,
    **kwargs,
):
    if path:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}"
    response = sess.request(method, url, timeout=120, **kwargs)
    if response.status_code == 404 and allow_404:
        return None
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def build_design_doc() -> dict:
    summary_value = (
        "{"
        "id: doc._id,"
        "profile_id: doc.profile_id || null,"
        "metier: doc.metier || null,"
        "article_source: doc.article_source || null,"
        "article_source_normalized: doc.article_source_normalized || null,"
        "article_canonique: doc.article_canonique || null,"
        "categorie: doc.categorie || null,"
        "sous_categorie: doc.sous_categorie || null,"
        "compte_comptable: doc.compte_comptable || null,"
        "source_file: doc.source_file || null"
        "}"
    )
    return {
        "_id": DESIGN_DOC_ID,
        "language": "javascript",
        "options": {
            "partitioned": False,
        },
        "views": {
            "by_article_source": {
                "map": (
                    "function(doc) {"
                    "  if (doc.p !== 'product_base_instance' || !doc.article_source) return;"
                    f"  emit(doc.article_source, {summary_value});"
                    "}"
                )
            },
            "by_article_source_normalized": {
                "map": (
                    "function(doc) {"
                    "  if (doc.p !== 'product_base_instance' || !doc.article_source_normalized) return;"
                    f"  emit(doc.article_source_normalized, {summary_value});"
                    "}"
                )
            },
        },
        "meta": {
            "purpose": "lookup product_base_instance by article_source",
            "version": 2,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cree ou met a jour une vue CouchDB pour retrouver un article par article_source."
    )
    parser.add_argument(
        "--db",
        default=os.getenv("DB_ENTRIES", SAFE_DEFAULT_DB),
        help="Base CouchDB cible.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Affiche le design doc final en JSON.",
    )
    args = parser.parse_args()

    sess = http_session()
    existing = couch_request(sess, args.db, "GET", quote(DESIGN_DOC_ID, safe=""), allow_404=True)
    design_doc = build_design_doc()
    if existing and isinstance(existing, dict) and existing.get("_rev"):
        design_doc["_rev"] = existing["_rev"]

    result = couch_request(
        sess,
        args.db,
        "PUT",
        quote(DESIGN_DOC_ID, safe=""),
        json=design_doc,
    )

    print(
        f"[OK] design_doc={DESIGN_DOC_ID} db={args.db} "
        f"rev={result.get('rev', '')} updated={bool(existing)}"
    )
    if args.json:
        print(json.dumps(design_doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
