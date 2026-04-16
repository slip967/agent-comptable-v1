#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
append_accounts_to_suppliers.py — Ajoute :
  • les comptes 6* utilisés dans les pièces FEC (hors 658/758)
  • le siren fournisseur depuis entry.invoice.siren_emetteur

CORRECTIONS :
- ne scanne que les journaux d'achat (par défaut {"AC"})
- ne scanne que les entries qui ont invoice (vu qu'on utilise siren_emetteur)
"""

import sys
import os
import argparse
import re
from typing import Dict, List, Set, Optional
from datetime import datetime

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

# ───────────────────────────────────────────────
# CONFIG COUCHDB
# ───────────────────────────────────────────────
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL)
DB_NAME = os.getenv("DB_ENTRIES", os.getenv("DB_NAME", "ayasmine_test"))
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)

CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY  = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT     = os.getenv("CA_CERT", DEFAULT_CA_CERT)

FIND_LIMIT = 1000
BULK_SIZE = 500
REQ_TIMEOUT = 180

# Journaux d'achat (mets aussi "ACH", "FA", etc si besoin)
def _parse_codes(value: str) -> Set[str]:
    return {x.strip() for x in (value or "").split(",") if x.strip()}

JOURNAL_CODES = _parse_codes(os.getenv("PURCHASE_JOURNAL_CODES", "AC")) or {"HA"}
STATS_OUTPUT = os.getenv("STATS_OUTPUT", "")


def _guess_siren(value: str) -> str:
    m = re.search(r"(\d{9})", value or "")
    return m.group(1) if m else ""


CLIENT_SIREN = (os.getenv("CLIENT_SIREN") or _guess_siren(DB_NAME)).strip()
ENTRIES_ID_PREFIX = os.getenv("ENTRIES_ID_PREFIX") or (f"fr_bd_{CLIENT_SIREN}:" if CLIENT_SIREN else "")


def _prefix_range(prefix: str) -> dict:
    return {"$gte": prefix, "$lt": prefix + "\ufff0"}

# ───────────────────────────────────────────────
# HTTP / COUCHDB
# ───────────────────────────────────────────────
def http_session() -> requests.Session:
    s = requests.Session()
    s.auth = (COUCHDB_USER, COUCHDB_PASS)
    s.cert = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3)
    s.mount("https://", adapter)
    return s

def couch_url(path: str = "") -> str:
    path = path.lstrip("/")
    return f"{COUCHDB_URL}/{DB_NAME}/{path}"

def couch_request(sess: requests.Session, method: str, path: str, **kwargs):
    url = couch_url(path)
    kwargs.setdefault("timeout", REQ_TIMEOUT)
    resp = sess.request(method, url, **kwargs)
    if not resp.ok:
        raise RuntimeError(f"CouchDB error [{resp.status_code}] {url} : {resp.text}")
    return resp.json()

def couch_bulk_docs(sess: requests.Session, docs: List[dict]):
    results = []
    for i in range(0, len(docs), BULK_SIZE):
        batch = docs[i:i + BULK_SIZE]
        res = couch_request(sess, "POST", "_bulk_docs", json={"docs": batch})
        results.extend(res)
    return results


def write_stats_text(path: str, stats: dict) -> None:
    if not path:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lines = [
        "03_append_accounts_to_suppliers - Stats",
        "=" * 48,
        f"timestamp: {datetime.now().isoformat()}",
        f"db_entries: {stats.get('db_entries')}",
        f"entries_id_prefix: {stats.get('entries_id_prefix')}",
        f"journal_codes: {stats.get('journal_codes')}",
        f"suppliers_loaded: {stats.get('suppliers_loaded')}",
        f"supplier_accounts_map: {stats.get('supplier_accounts_map')}",
        f"supplier_siren_map: {stats.get('supplier_siren_map')}",
        f"suppliers_to_update: {stats.get('suppliers_to_update')}",
        f"suppliers_updated_ok: {stats.get('suppliers_updated_ok')}",
        f"suppliers_updated_errors: {stats.get('suppliers_updated_errors')}",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[STATS] Fichier écrit: {path}")

# ───────────────────────────────────────────────
# UTIL : RÈGLE SUR LES COMPTES
# ───────────────────────────────────────────────
def is_account_selected(acc: str) -> bool:
    """Garder seulement comptes 6*, exclure 658* et 758*."""
    if not acc:
        return False
    acc = str(acc).strip()
    if not acc.startswith("6"):
        return False
    if acc.startswith("658") or acc.startswith("758"):
        return False
    return True

def build_accounts_list(existing_accounts: Optional[List[dict]], new_numbers: Set[str]) -> List[dict]:
    """
    Fusionne anciennes + nouvelles accounts sans doublons.
    """
    by_num = {}

    # anciens comptes
    if existing_accounts:
        for item in existing_accounts:
            num = str(item.get("account_number") or "").strip()
            if num and is_account_selected(num):
                by_num[num] = {
                    "account_number": num,
                    "account_description": item.get("account_description", ""),
                    "account_keywords": item.get("account_keywords", "")
                }

    # nouveaux comptes
    for num in new_numbers:
        num = str(num).strip()
        if is_account_selected(num) and num not in by_num:
            by_num[num] = {
                "account_number": num,
                "account_description": "",
                "account_keywords": ""
            }

    return sorted(by_num.values(), key=lambda x: x["account_number"])

# ───────────────────────────────────────────────
# LOAD SUPPLIERS
# ───────────────────────────────────────────────
def load_suppliers(sess) -> Dict[str, dict]:
    suppliers = {}
    bookmark = None

    print("Chargement des suppliers...")

    while True:
        selector = {"p": "supplier"}
        if ENTRIES_ID_PREFIX:
            selector["_id"] = _prefix_range(ENTRIES_ID_PREFIX)
        payload = {
            "selector": selector,
            "limit": FIND_LIMIT
        }
        if bookmark:
            payload["bookmark"] = bookmark

        res = couch_request(sess, "POST", "_find", json=payload)
        docs = res.get("docs", [])
        bookmark = res.get("bookmark")

        for d in docs:
            aux = d.get("auxiliary_code")
            if aux:
                suppliers[aux] = d

        if not docs:
            break

    print(f"Total suppliers chargés : {len(suppliers)}")
    return suppliers

# ───────────────────────────────────────────────
# SCAN DES ENTRIES (comptes + sirens)
# ───────────────────────────────────────────────
def scan_entries(sess):
    """
    Retourne :
      - supplier_accounts_map : aux_code -> comptes 6*
      - supplier_siren_map : aux_code -> siren_emetteur

    IMPORTANT :
      - on filtre sur journaux achat
      - on filtre sur invoice existant
    """
    pieces = {}
    bookmark = None

    print(f"Scan des entries FEC (journaux achat={sorted(JOURNAL_CODES)})...")

    selector = {
        "p": "entry",
        "piece_id": {"$exists": True},
        "invoice": {"$exists": True},
        "journal_code": {"$in": sorted(JOURNAL_CODES)},
    }
    if ENTRIES_ID_PREFIX:
        selector["_id"] = _prefix_range(ENTRIES_ID_PREFIX)

    while True:
        payload = {
            "selector": selector,
            "fields": ["piece_id", "aux_account", "account_number", "compte_num", "invoice", "journal_code"],
            "limit": FIND_LIMIT
        }
        if bookmark:
            payload["bookmark"] = bookmark

        res = couch_request(sess, "POST", "_find", json=payload)
        docs = res.get("docs", [])
        bookmark = res.get("bookmark")

        for e in docs:
            pid = e.get("piece_id")
            if not pid:
                continue

            if pid not in pieces:
                pieces[pid] = {"suppliers": set(), "accounts": set(), "sirens": set()}

            # suppliers (on récupère le code auxiliaire)
            aux = e.get("aux_account")
            if aux:
                aux_s = str(aux).strip()
                if ":" in aux_s:
                    aux_s = aux_s.split(":", 1)[1].strip()
                if aux_s:
                    pieces[pid]["suppliers"].add(aux_s)

            # comptes 6*
            acc = e.get("account_number") or e.get("compte_num")
            if acc and is_account_selected(str(acc)):
                pieces[pid]["accounts"].add(str(acc).strip())

            # siren émetteur
            inv = e.get("invoice") or {}
            se = inv.get("siren_emetteur")
            if se:
                pieces[pid]["sirens"].add(str(se).strip())

        if not docs:
            break

    supplier_accounts_map = {}
    supplier_siren_map = {}

    for _, pdata in pieces.items():
        suppliers = pdata["suppliers"]
        accounts = pdata["accounts"]
        sirens = pdata["sirens"]

        # on ne met le siren que si la pièce est cohérente (1 seul siren)
        siren_value = next(iter(sirens)) if len(sirens) == 1 else None

        for aux in suppliers:
            if accounts:
                supplier_accounts_map.setdefault(aux, set()).update(accounts)
            if siren_value:
                supplier_siren_map[aux] = siren_value

    return supplier_accounts_map, supplier_siren_map

# ───────────────────────────────────────────────
# MAIN UPDATE
# ───────────────────────────────────────────────
def append_accounts_to_suppliers():
    sess = http_session()

    suppliers = load_suppliers(sess)
    supplier_accounts_map, supplier_siren_map = scan_entries(sess)

    docs_to_update = []
    now = datetime.now().isoformat()

    for aux_code, sup_doc in suppliers.items():
        updated = False

        # 1) Ajouter SIREN fournisseur
        if aux_code in supplier_siren_map:
            siren = supplier_siren_map[aux_code]
            if (sup_doc.get("siren") or "") != siren:
                sup_doc["siren"] = siren
                updated = True

        # 2) Ajouter comptes
        if aux_code in supplier_accounts_map:
            merged = build_accounts_list(
                sup_doc.get("accounts", []),
                supplier_accounts_map[aux_code]
            )
            if merged != (sup_doc.get("accounts") or []):
                sup_doc["accounts"] = merged
                updated = True

        if updated:
            sup_doc["updated_at"] = now
            docs_to_update.append(sup_doc)

    if not docs_to_update:
        print("Aucun supplier à mettre à jour.")
        stats = {
            "db_entries": DB_NAME,
            "entries_id_prefix": ENTRIES_ID_PREFIX or "(none)",
            "journal_codes": ",".join(sorted(JOURNAL_CODES)),
            "suppliers_loaded": len(suppliers),
            "supplier_accounts_map": len(supplier_accounts_map),
            "supplier_siren_map": len(supplier_siren_map),
            "suppliers_to_update": 0,
            "suppliers_updated_ok": 0,
            "suppliers_updated_errors": 0,
        }
        write_stats_text(STATS_OUTPUT, stats)
        return stats

    res = couch_bulk_docs(sess, docs_to_update)
    ok = sum(1 for r in res if r.get("ok", False))
    errs = len(docs_to_update) - ok

    print(f"Suppliers mis à jour : {ok}/{len(docs_to_update)}")
    stats = {
        "db_entries": DB_NAME,
        "entries_id_prefix": ENTRIES_ID_PREFIX or "(none)",
        "journal_codes": ",".join(sorted(JOURNAL_CODES)),
        "suppliers_loaded": len(suppliers),
        "supplier_accounts_map": len(supplier_accounts_map),
        "supplier_siren_map": len(supplier_siren_map),
        "suppliers_to_update": len(docs_to_update),
        "suppliers_updated_ok": ok,
        "suppliers_updated_errors": errs,
    }
    write_stats_text(STATS_OUTPUT, stats)
    return stats

# ───────────────────────────────────────────────
# EXECUTE
# ───────────────────────────────────────────────
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Ajoute comptes 6* et SIREN aux suppliers depuis les entries FEC.")
        parser.add_argument("--db-entries", "--db", dest="db_name", default=DB_NAME, help="Base CouchDB des entries FEC.")
        parser.add_argument("--client-siren", "--siren", default=CLIENT_SIREN, help="SIREN client pour filtrer les docs.")
        parser.add_argument(
            "--entries-id-prefix",
            default=None,
            help="Override du préfixe _id des entries/suppliers (ex: fr_bd_123456789:).",
        )
        parser.add_argument(
            "--journal-codes",
            default=",".join(sorted(JOURNAL_CODES)),
            help="Liste de journaux achat, séparés par des virgules (ex: AC,HA).",
        )
        parser.add_argument("--stats-output", default=STATS_OUTPUT, help="Chemin du fichier texte de stats.")
        args = parser.parse_args()

        DB_NAME = args.db_name
        JOURNAL_CODES = _parse_codes(args.journal_codes)
        STATS_OUTPUT = args.stats_output
        if args.entries_id_prefix:
            ENTRIES_ID_PREFIX = args.entries_id_prefix
        elif args.client_siren:
            ENTRIES_ID_PREFIX = f"fr_bd_{args.client_siren}:"
        else:
            ENTRIES_ID_PREFIX = ""

        if not ENTRIES_ID_PREFIX:
            print("[WARN] Aucun filtre client actif: tous les clients de la DB seront scannés.")

        append_accounts_to_suppliers()
    except Exception as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
