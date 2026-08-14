from __future__ import annotations

import os
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

from .account_labels import get_account_label
from .config import REFERENCE_COUCH_DB, REFERENCE_PAGE_SIZE
from .loader import normalize_text


COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

REFERENCE_FIELDS = [
    "source_file",
    "metier",
    "partition_prefix",
    "article_source",
    "article_source_normalized",
    "article_canonique",
    "categorie",
    "sous_categorie",
    "compte_comptable",
    "compte_comptable_libelle",
    "account_label",
    "taux_tva",
    "tva_rate",
    "mots_cles",
    "source_invoice_ids",
    "ids_factures_sources",
    "invoice_paths_sources",
    "partitions_sources",
    "type_fournisseur",
    "payload",
]


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def couch_request(sess: requests.Session, db: str, method: str, path: str = "", **kwargs) -> dict[str, Any]:
    if path:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}"
    response = sess.request(method, url, timeout=120, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def fetch_product_base_instances(db_name: str | None = None) -> list[dict[str, Any]]:
    db = (db_name or REFERENCE_COUCH_DB).strip() or REFERENCE_COUCH_DB
    sess = http_session()
    docs: list[dict[str, Any]] = []
    bookmark: str | None = None

    while True:
        payload: dict[str, Any] = {
            "selector": {"p": "product_base_instance"},
            "fields": REFERENCE_FIELDS,
            "limit": REFERENCE_PAGE_SIZE,
        }
        if bookmark:
            payload["bookmark"] = bookmark
        result = couch_request(sess, db, "POST", "_find", json=payload)
        chunk = result.get("docs") or []
        if not chunk:
            break
        docs.extend(doc for doc in chunk if isinstance(doc, dict))
        new_bookmark = str(result.get("bookmark") or "").strip()
        if len(chunk) < REFERENCE_PAGE_SIZE or not new_bookmark or new_bookmark == bookmark:
            break
        bookmark = new_bookmark

    return docs


def flatten_product_instance(doc: dict[str, Any]) -> dict[str, Any]:
    payload = doc.get("payload") or {}
    article_source = str(doc.get("article_source") or payload.get("article_source") or "").strip()
    article_canonique = str(doc.get("article_canonique") or payload.get("article_canonique") or "").strip()
    account = str(doc.get("compte_comptable") or payload.get("compte_comptable") or "").strip()
    account_label = str(
        doc.get("compte_comptable_libelle")
        or payload.get("compte_comptable_libelle")
        or doc.get("account_label")
        or payload.get("account_label")
        or get_account_label(account)
        or ""
    ).strip()
    tva_rate = payload.get("taux_tva", payload.get("tva_rate", doc.get("taux_tva", doc.get("tva_rate"))))
    return {
        "base_file": str(doc.get("source_file") or "").strip(),
        "metier": str(doc.get("metier") or (doc.get("data") or {}).get("sub_type") or "").strip(),
        "article_source": article_source,
        "article_canonique": article_canonique,
        "article_canonique_normalized": normalize_text(article_canonique),
        "categorie": str(doc.get("categorie") or payload.get("categorie") or "").strip(),
        "sous_categorie": str(doc.get("sous_categorie") or payload.get("sous_categorie") or "").strip(),
        "compte_comptable": account,
        "compte_comptable_libelle": account_label,
        "account_label": account_label,
        "source_partition": str(doc.get("partition_prefix") or payload.get("source_partition") or "").strip(),
        "mots_cles": list(doc.get("mots_cles") or payload.get("mots_cles") or []),
        "tva_rate": tva_rate,
        "ape_context": list(payload.get("ape_context") or []),
        "source_invoice_ids": list(doc.get("source_invoice_ids") or payload.get("source_invoice_ids") or []),
        "ids_factures_sources": list(
            doc.get("ids_factures_sources")
            or payload.get("ids_factures_sources")
            or doc.get("source_invoice_ids")
            or payload.get("source_invoice_ids")
            or []
        ),
        "invoice_paths_sources": list(
            doc.get("invoice_paths_sources") or payload.get("invoice_paths_sources") or []
        ),
        "partitions_sources": list(doc.get("partitions_sources") or payload.get("partitions_sources") or []),
        "type_fournisseur": str(doc.get("type_fournisseur") or payload.get("type_fournisseur") or "").strip(),
        "sous_profil": str(payload.get("sous_profil") or "").strip(),
        "nature_charge": str(payload.get("nature_charge") or "").strip(),
        "profil_facturation": str(payload.get("profil_facturation") or "").strip(),
    }


def load_couch_reference_rows(db_name: str | None = None) -> list[dict[str, Any]]:
    docs = fetch_product_base_instances(db_name=db_name)
    return [flatten_product_instance(doc) for doc in docs]
