"""
_check_invoice_ids_in_couch.py
Verifie si les source_invoice_ids de transport et restaurant
existent reellement dans CouchDB (keymanage_accounting).
"""
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

sys.path.insert(0, '.')
from couch_config import (
    CA_CERT, CLIENT_CERT, CLIENT_KEY,
    COUCHDB_PASS, COUCHDB_URL, COUCHDB_USER,
)

DB = "keymanage_accounting"
BASES = {
    "transport": "base_produits_transport_v1.json",
    "restaurant": "base_produits_restaurant_v1.json",
}


def http_session():
    s = requests.Session()
    s.auth   = (COUCHDB_USER, COUCHDB_PASS)
    s.cert   = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=3))
    return s


def normalize_id(raw_id: str) -> str:
    """'part:part:uuid' -> 'part:uuid' ; 'part:uuid' -> 'part:uuid'"""
    parts = raw_id.split(":")
    if len(parts) == 3 and parts[0] == parts[1]:
        return parts[0] + ":" + parts[2]
    return raw_id


def fetch_existing(session, db: str, doc_ids: list[str]) -> set[str]:
    """Retourne l'ensemble des doc_ids qui existent dans CouchDB."""
    if not doc_ids:
        return set()
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_all_docs"
    resp = session.post(url, json={"keys": doc_ids}, timeout=60)
    resp.raise_for_status()
    existing = set()
    for row in resp.json().get("rows", []):
        # Si la cle existe et n'est pas un 'not_found'
        if "error" not in row and row.get("id"):
            existing.add(row["id"])
    return existing


def main():
    session = http_session()

    for metier, fp in BASES.items():
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        items = d["items"]

        # Collecter tous les IDs normalises
        id_to_items: dict[str, list[str]] = {}
        for item in items:
            for raw in (item.get("source_invoice_ids") or []):
                nid = normalize_id(raw)
                id_to_items.setdefault(nid, []).append(item["article_source"])

        all_ids = list(id_to_items.keys())
        print(f"\n=== {metier.upper()} ({fp}) ===")
        print(f"  {len(items)} articles sources, {len(all_ids)} IDs uniques a verifier")

        # Fetch par lots de 200
        existing = set()
        for start in range(0, len(all_ids), 200):
            batch = all_ids[start:start + 200]
            found = fetch_existing(session, DB, batch)
            existing.update(found)
            print(f"  batch {start}–{start+len(batch)}: {len(found)}/{len(batch)} trouves")

        missing_ids = set(all_ids) - existing
        print(f"\n  Trouves  : {len(existing)}/{len(all_ids)}")
        print(f"  Manquants: {len(missing_ids)}")

        if missing_ids:
            # Grouper par article
            art_missing: dict[str, list[str]] = {}
            for mid in sorted(missing_ids):
                for art in id_to_items.get(mid, []):
                    art_missing.setdefault(art, []).append(mid)

            print(f"\n  Articles avec IDs manquants ({len(art_missing)}):")
            for art, mids in sorted(art_missing.items()):
                print(f"    - {repr(art)}")
                for mid in mids:
                    print(f"        {mid}")
        else:
            print("  Tous les IDs sont valides dans CouchDB.")


if __name__ == "__main__":
    main()
