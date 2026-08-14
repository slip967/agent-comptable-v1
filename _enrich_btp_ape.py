"""
_enrich_btp_ape.py
Enrichit ape_context de chaque item de base_produits_btp_v1.json
en fetchant les invoice_form correspondants via source_invoice_ids.
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
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
BASE_FILE = "base_produits_btp_v1.json"


def http_session():
    s = requests.Session()
    s.auth   = (COUCHDB_USER, COUCHDB_PASS)
    s.cert   = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=3))
    return s


def get_val(field):
    """Déplie le format {'value': ...} de keymanage_accounting."""
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return field


def parse_ape(issuer: dict) -> list[str]:
    """Extrait les codes APE/NAF depuis le champ issuer (format keymanage)."""
    apes = []
    if not isinstance(issuer, dict):
        return apes
    regs = issuer.get("company_registrations") or []
    for reg in (regs if isinstance(regs, list) else []):
        if not isinstance(reg, dict):
            continue
        reg_type = get_val(reg.get("type") or "") or ""
        if reg_type.strip().upper() in {"APE", "NAF"}:
            v = (get_val(reg.get("value")) or "").strip().upper().replace(" ", "")
            if v and v not in apes:
                apes.append(v)
    return apes[:3]


def fetch_docs_bulk(session, db: str, doc_ids: list[str]) -> dict:
    """Retourne {doc_id: doc} via _all_docs?include_docs=true."""
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_all_docs"
    payload = {"keys": doc_ids}
    resp = session.post(url, json=payload, params={"include_docs": "true"}, timeout=60)
    resp.raise_for_status()
    result = {}
    for row in resp.json().get("rows", []):
        doc = row.get("doc")
        if doc:
            result[doc["_id"]] = doc
    return result


def main():
    with open(BASE_FILE, encoding="utf-8") as f:
        base = json.load(f)

    items = base["items"]

    # Collecter tous les doc_ids nécessaires (max 3 par item)
    all_ids = {}  # doc_id -> [item_indices]
    for idx, item in enumerate(items):
        for raw_id in (item.get("source_invoice_ids") or [])[:3]:
            # Normaliser : "partition:partition:uuid" → "partition:uuid"
            parts = raw_id.split(":")
            if len(parts) == 3 and parts[0] == parts[1]:
                doc_id = parts[0] + ":" + parts[2]
            else:
                doc_id = raw_id
            all_ids.setdefault(doc_id, []).append(idx)

    print(f"[fetch] {len(all_ids)} doc_ids uniques à récupérer…")

    session = http_session()

    # Fetch par lots de 200
    id_list = list(all_ids.keys())
    docs_cache = {}
    for start in range(0, len(id_list), 200):
        batch = id_list[start:start + 200]
        fetched = fetch_docs_bulk(session, DB, batch)
        docs_cache.update(fetched)
        print(f"  batch {start}–{start+len(batch)}: {len(fetched)} trouvés")

    # Enrichir chaque item
    enrichis = 0
    for idx, item in enumerate(items):
        ape_ctr = Counter()
        for raw_id in (item.get("source_invoice_ids") or [])[:3]:
            parts = raw_id.split(":")
            doc_id = (parts[0] + ":" + parts[2]) if (len(parts) == 3 and parts[0] == parts[1]) else raw_id
            doc = docs_cache.get(doc_id)
            if not doc:
                continue
            issuer = doc.get("issuer") or {}
            for ape in parse_ape(issuer):
                ape_ctr[ape] += 1

        if ape_ctr:
            item["ape_context"] = [a for a, _ in ape_ctr.most_common(3)]
            enrichis += 1

    base["meta"]["updated"] = datetime.now(timezone.utc).isoformat()
    with open(BASE_FILE, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)

    print(f"\nItems enrichis avec APE : {enrichis} / {len(items)}")

    # Distribution APE
    all_apes = [a for item in items for a in (item.get("ape_context") or [])]
    ctr = Counter(all_apes)
    print("Distribution APE:")
    for ape, n in ctr.most_common(15):
        print(f"  {ape}: {n}")
    print("\nDone.")


if __name__ == "__main__":
    main()
