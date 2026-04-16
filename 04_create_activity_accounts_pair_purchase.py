#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
create_activity_accounts_pair_purchase.py

Construit des ActivityAccount par paire (client_ape, fournisseur_ape) à partir du FEC
MAIS uniquement sur les journaux d'achat.

Comptes conservés pour activity_account:
- 6* et 2*
Exclusions:
- 531
- 658*, 758*
- tout ce qui commence par 5 ou 7
- (on ignore aussi les 4* par nature: 401/445 etc.)
"""

import os
import sys
import json
import time
import hashlib
import threading
import argparse
from typing import Dict, Optional
from collections import Counter, defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

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
# ENV HELPERS
# ───────────────────────────────────────────────
# ======================================================================
# CONFIG COUCHDB
# ======================================================================
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL)
DB_NAME = os.getenv("DB_ENTRIES", os.getenv("DB_NAME", "ayasmine_test"))
ABT_DB_NAME = os.getenv("ABT_DB_NAME", os.getenv("DB_FACTURES", "abt3"))

COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)

CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY  = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT     = os.getenv("CA_CERT", DEFAULT_CA_CERT)

FIND_LIMIT = 1000
BULK_SIZE = 500
REQ_TIMEOUT = 180

# Journaux d'achat (mets aussi "ACH", "FA", etc si vous en avez)
def _parse_codes(value: str):
    return {x.strip() for x in (value or "").split(",") if x.strip()}

JOURNAL_CODES = _parse_codes(os.getenv("PURCHASE_JOURNAL_CODES", "")) or {"AC"}

STRICT_REQUIRE_APE = (os.getenv("STRICT_REQUIRE_APE", "true").lower() == "true")
STATS_OUTPUT = os.getenv("STATS_OUTPUT", "")


def _guess_siren(value: str) -> str:
    m = re.search(r"(\d{9})", value or "")
    return m.group(1) if m else ""


CLIENT_SIREN = (os.getenv("CLIENT_SIREN") or _guess_siren(DB_NAME)).strip()
ENTRIES_ID_PREFIX = os.getenv("ENTRIES_ID_PREFIX") or (f"fr_bd_{CLIENT_SIREN}:" if CLIENT_SIREN else "")


def _prefix_range(prefix: str) -> dict:
    return {"$gte": prefix, "$lt": prefix + "\ufff0"}

# ======================================================================
# CONFIG API recherche-entreprises (api.gouv.fr)
# ======================================================================
# NOTE:
# - On conserve les noms INPI_* pour compatibilité de CLI/env avec run_pipeline.py.
# - INPI_USERNAME / INPI_PASSWORD ne sont plus utilisés.
INPI_BASE_URL = os.getenv("INPI_BASE_URL", "https://recherche-entreprises.api.gouv.fr")
INPI_USERNAME = os.getenv("INPI_USERNAME", "")
INPI_PASSWORD = os.getenv("INPI_PASSWORD", "")

USE_INPI_API = os.getenv("USE_INPI_API", "true").lower() == "true"
APE_DEBUG = False

MAX_QPS = 1.5
MAX_WORKERS = 3
MAX_RETRIES = 5
BASE_BACKOFF = 0.7
TIMEOUT_S = 12
INPI_QPS_HARD_LIMIT = 3.0

CACHE_PATH = os.getenv("APE_CACHE_PATH", "/root/db scripts/cache_ape.json")
SAVE_EVERY = 25

# ======================================================================
# GLOBAL STATE
# ======================================================================
inpi_session: Optional[requests.Session] = None
_ape_cache_mem: Dict[str, Optional[str]] = {}
_cache_lock = threading.Lock()
_cache_dirty = 0
_last_call_ts = 0.0
_qps_lock = threading.Lock()
_inpi_auth_lock = threading.Lock()

# ======================================================================
# NORMALISATION APE (strict)
# ======================================================================
APE_PATTERN = re.compile(r"^\d{4}[A-Z]$")

def normalize_ape(ape_code: Optional[str]) -> Optional[str]:
    if not ape_code:
        return None
    cleaned = ape_code.replace(".", "").replace(" ", "").upper()
    if not APE_PATTERN.match(cleaned):
        if APE_DEBUG:
            print(f"[WARN] APE invalide : {ape_code} -> {cleaned}")
        return None
    return cleaned

def ensure_rate_limit():
    global _last_call_ts
    with _qps_lock:
        qps = max(0.1, min(float(MAX_QPS or 0), INPI_QPS_HARD_LIMIT))
        now = time.time()
        min_i = 1.0 / qps
        delta = now - _last_call_ts
        if delta < min_i:
            time.sleep(min_i - delta)
        _last_call_ts = time.time()

# ======================================================================
# COUCHDB UTILS
# ======================================================================
def http_session() -> requests.Session:
    s = requests.Session()
    s.auth = (COUCHDB_USER, COUCHDB_PASS)
    s.cert = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
    return s

def couch_url(db_name, path=""):
    path = path.lstrip("/")
    return f"{COUCHDB_URL}/{db_name}/{path}" if path else f"{COUCHDB_URL}/{db_name}"

def couch_request_db(sess, db, method, path, **kw):
    url = couch_url(db, path)
    kw.setdefault("timeout", REQ_TIMEOUT)
    r = sess.request(method, url, **kw)
    if not r.ok:
        raise RuntimeError(f"CouchDB [{r.status_code}] {url}: {r.text}")
    if r.headers.get("Content-Type", "").startswith("application/json"):
        return r.json()
    return {"ok": True}

def couch_bulk_get_db(sess, db, ids):
    out = {}
    for i in range(0, len(ids), BULK_SIZE):
        batch = ids[i:i+BULK_SIZE]
        payload = {"docs": [{"id": x} for x in batch]}
        res = couch_request_db(sess, db, "POST", "_bulk_get", json=payload)
        for r in res.get("results", []):
            docs = r.get("docs", [])
            if docs and "ok" in docs[0]:
                out[r["id"]] = docs[0]["ok"]
    return out

def couch_request(sess, method, path, **kw):
    return couch_request_db(sess, DB_NAME, method, path, **kw)

def couch_bulk_docs(sess, docs):
    out = []
    for i in range(0, len(docs), BULK_SIZE):
        b = docs[i:i+BULK_SIZE]
        r = couch_request(sess, "POST", "_bulk_docs", json={"docs": b, "new_edits": True})
        out.extend(r)
    return out


def write_stats_text(path: str, stats: dict):
    if not path:
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    lines = [
        "04_create_activity_accounts_pair_purchase - Stats",
        "=" * 58,
        f"timestamp: {datetime.now().isoformat()}",
        f"db_entries: {stats.get('db_entries')}",
        f"db_factures: {stats.get('db_factures')}",
        f"entries_id_prefix: {stats.get('entries_id_prefix')}",
        f"journal_codes: {stats.get('journal_codes')}",
        f"use_inpi_api: {stats.get('use_inpi_api')}",
        f"strict_require_ape: {stats.get('strict_require_ape')}",
        f"fec_entries_loaded: {stats.get('fec_entries_loaded')}",
        f"pieces_total: {stats.get('pieces_total')}",
        f"sirens_detected: {stats.get('sirens_detected')}",
        f"invoice_form_ids_detected: {stats.get('invoice_form_ids_detected')}",
        f"local_ape_hits: {stats.get('local_ape_hits')}",
        f"ape_lookup_missing_initial: {stats.get('ape_lookup_missing_initial')}",
        f"activity_accounts_to_save: {stats.get('activity_accounts_to_save')}",
        f"activity_accounts_saved_ok: {stats.get('activity_accounts_saved_ok')}",
        f"activity_accounts_saved_errors: {stats.get('activity_accounts_saved_errors')}",
        f"pieces_processed: {stats.get('pieces_processed')}",
        f"pieces_skipped: {stats.get('pieces_skipped')}",
        "skip_reasons:",
    ]
    skip_reasons = stats.get("skip_reasons", {})
    if not skip_reasons:
        lines.append("  - none")
    else:
        for reason, count in sorted(skip_reasons.items()):
            lines.append(f"  - {reason}: {count}")
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[STATS] Fichier écrit: {path}")

# ======================================================================
# CACHE APE
# ======================================================================
def load_ape_cache():
    global _ape_cache_mem
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r") as f:
                _ape_cache_mem = json.load(f)
        except:
            pass

def save_ape_cache(force=False):
    global _cache_dirty
    if not force and _cache_dirty < SAVE_EVERY:
        return
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_ape_cache_mem, f, indent=2)
    os.replace(tmp, CACHE_PATH)
    _cache_dirty = 0

def cache_put(siren, ape):
    global _cache_dirty
    with _cache_lock:
        _ape_cache_mem[siren] = ape
        _cache_dirty += 1
    save_ape_cache()

def cache_get(siren):
    return _ape_cache_mem.get(siren)

# ======================================================================
# API recherche-entreprises (api.gouv.fr)
# ======================================================================
def build_inpi_session():
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "User-Agent": "km-ape-fetcher/1.0"})
    return s

def extract_ape_from_inpi(data, siren: str):
    """
    Extraction APE depuis la réponse:
      GET {INPI_BASE_URL}/search?q=<siren>
    """
    if not isinstance(data, dict):
        return None

    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None

    # Priorité aux résultats de SIREN exact.
    exact = [r for r in results if isinstance(r, dict) and str(r.get("siren") or "") == str(siren)]
    others = [r for r in results if isinstance(r, dict) and str(r.get("siren") or "") != str(siren)]

    for item in exact + others:
        candidates = []
        candidates.append(item.get("activite_principale"))
        siege = item.get("siege") or {}
        if isinstance(siege, dict):
            candidates.append(siege.get("activite_principale"))

        for raw in candidates:
            ape = normalize_ape(raw)
            if ape:
                return ape
    return None

def _inpi_once(siren):
    global inpi_session
    if inpi_session is None:
        with _inpi_auth_lock:
            if inpi_session is None:
                inpi_session = build_inpi_session()

    base = INPI_BASE_URL.rstrip("/")
    url = f"{base}/search"
    ensure_rate_limit()
    r = inpi_session.get(url, params={"q": str(siren)}, timeout=TIMEOUT_S)

    if r.status_code == 200:
        return extract_ape_from_inpi(r.json(), str(siren))

    if r.status_code in (429, 500, 502, 503, 504):
        raise requests.exceptions.RetryError()

    return None

def get_ape_from_inpi_with_retry(siren):
    cached = cache_get(siren)
    if cached is not None:
        return cached

    delay = BASE_BACKOFF
    for attempt in range(1, MAX_RETRIES+1):
        try:
            ape = _inpi_once(siren)
            if ape:
                cache_put(siren, ape)
                return ape
            if attempt >= 3:
                break
        except:
            time.sleep(delay)
            delay *= 1.7

    cache_put(siren, None)
    return None

# ======================================================================
# FEC UTILS
# ======================================================================
def load_fec_entries(sess):
    """
    Charge uniquement les entries des journaux d'achat.
    """
    out = []
    bookmark = None
    print(f"Chargement FEC (journaux achat={sorted(JOURNAL_CODES)})...")

    selector = {"p": "entry", "invoice": {"$exists": True}, "journal_code": {"$in": sorted(JOURNAL_CODES)}}
    if ENTRIES_ID_PREFIX:
        selector["_id"] = _prefix_range(ENTRIES_ID_PREFIX)

    while True:
        payload = {
            "selector": selector,
            "fields": ["_id"],
            "limit": FIND_LIMIT
        }
        if bookmark:
            payload["bookmark"] = bookmark

        res = couch_request(sess, "POST", "_find", json=payload)
        docs = res.get("docs", [])
        if not docs:
            break

        ids = [d["_id"] for d in docs]
        full = couch_bulk_get_db(sess, DB_NAME, ids)
        entries = [d for d in full.values()
                   if d.get("p") == "entry" and d.get("invoice") and d.get("journal_code") in JOURNAL_CODES]
        out.extend(entries)

        bookmark = res.get("bookmark")
        if not bookmark:
            break

    print(f"FEC chargés : {len(out)}")
    return out

def extract_client_siren_from_id(doc_id):
    if not doc_id:
        return None
    prefix = doc_id.split(":", 1)[0]
    parts = prefix.split("_")
    s = parts[-1]
    return s if s.isdigit() else None

def extract_sirens_for_piece(entries):
    fs = None
    cs = None

    for e in entries:
        inv = e.get("invoice") or {}
        if not fs:
            fs = inv.get("siren_emetteur")
        if not cs:
            cs = extract_client_siren_from_id(e.get("_id"))
        if fs and cs:
            break

    if not cs:
        for e in entries:
            inv = e.get("invoice") or {}
            cs = inv.get("siren_destinataire")
            if cs:
                break

    return fs, cs

def is_account_ok_for_activity(acc: str) -> bool:
    if not acc:
        return False
    s = str(acc).strip()
    if s in {"531"}:
        return False
    if s.startswith("5") or s.startswith("7"):
        return False
    if s.startswith("658") or s.startswith("758"):
        return False
    # on garde 6* et 2*
    return s.startswith("6") or s.startswith("2")

def collect_unique_accounts(entries):
    out = set()
    for e in entries:
        acc = e.get("account_number") or e.get("compte_num")
        if not acc:
            continue
        s = str(acc).strip()
        # on ignore la classe 4 (401/445...) ici
        if s.startswith("4"):
            continue
        if is_account_ok_for_activity(s):
            out.add(s)
    return sorted(out)

# ======================================================================
# ABT_v2 — extraction APE (issuer/recipient)
# ======================================================================
def extract_apes_from_invoice_forms(invoice_forms):
    siren_to_ape = {}

    for _, doc in invoice_forms.items():
        issuer = doc.get("issuer") or {}
        recipient = doc.get("recipient") or {}

        issuer_siren = issuer.get("siren")
        if issuer_siren:
            issuer_ape = None
            for reg in issuer.get("company_registrations") or []:
                if reg.get("type") == "APE" and reg.get("value"):
                    issuer_ape = normalize_ape(reg["value"])
                    break
            if issuer_ape:
                siren_to_ape[str(issuer_siren)] = issuer_ape

        recipient_siren = recipient.get("siren")
        if not recipient_siren:
            for reg in recipient.get("company_registrations") or []:
                if reg.get("type") == "SIRET" and reg.get("value"):
                    v = reg["value"]
                    if isinstance(v, str) and v.isdigit() and len(v) >= 9:
                        recipient_siren = v[:9]
                        break

        if recipient_siren:
            recipient_ape = None
            for reg in recipient.get("company_registrations") or []:
                if reg.get("type") == "APE" and reg.get("value"):
                    recipient_ape = normalize_ape(reg["value"])
                    break
            if recipient_ape:
                siren_to_ape[str(recipient_siren)] = recipient_ape

    return siren_to_ape

def fetch_all_apes(sirens):
    load_ape_cache()
    out = {}

    for s in list(sirens):
        c = cache_get(s)
        if c is not None:
            out[s] = c

    need = [s for s in sirens if s not in out]

    def worker(s):
        return s, get_ape_from_inpi_with_retry(s)

    if need:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(worker, s): s for s in need}
            for fut in as_completed(futures):
                s = futures[fut]
                try:
                    _, ape = fut.result()
                except:
                    ape = None
                out[s] = ape

    save_ape_cache(force=True)
    return out

# ======================================================================
# PAIRE APE → ID deterministe
# ======================================================================
def create_activity_account_id_pair(client_ape, fournisseur_ape):
    key = f"{client_ape}_{fournisseur_ape}"
    return f"activity_account:{client_ape}_{fournisseur_ape}_{hashlib.md5(key.encode()).hexdigest()[:8]}"

def merge_accounts_list(old, new):
    m = {d["account_number"]: d for d in old}
    for d in new:
        if d["account_number"] not in m:
            m[d["account_number"]] = d
    return sorted(m.values(), key=lambda x: x["account_number"])

# ======================================================================
# MAIN PIPELINE
# ======================================================================
def process_and_create_activity_accounts():
    global inpi_session
    if USE_INPI_API:
        inpi_session = build_inpi_session()

    sess = http_session()

    fec_entries = load_fec_entries(sess)

    # group par piece_id (plus sûr)
    pieces = defaultdict(list)
    for e in fec_entries:
        pid = e.get("piece_id") or e.get("piece_ref")
        if pid:
            pieces[pid].append(e)

    print(f"Total pièces : {len(pieces)}")

    all_sirens = set()
    form_ids = set()

    for entries in pieces.values():
        fs, cs = extract_sirens_for_piece(entries)
        if fs: all_sirens.add(str(fs))
        if cs: all_sirens.add(str(cs))
        for e in entries:
            inv = e.get("invoice") or {}
            fid = inv.get("invoice_form_id")
            if fid:
                form_ids.add(fid)

    siren_ape_local = {}
    if form_ids:
        forms = couch_bulk_get_db(sess, ABT_DB_NAME, list(form_ids))
        siren_ape_local = extract_apes_from_invoice_forms(forms)

    missing = {s for s in all_sirens if s not in siren_ape_local}
    siren_ape_api = fetch_all_apes(missing)

    siren_to_ape = dict(siren_ape_api)
    siren_to_ape.update(siren_ape_local)

    activity_accounts = {}
    processed = 0
    skipped = 0
    skip_reasons = Counter()

    for _, entries in pieces.items():
        fs, cs = extract_sirens_for_piece(entries)
        if not fs or not cs:
            skipped += 1
            skip_reasons["missing_siren"] += 1
            continue
        fs = str(fs); cs = str(cs)
        if fs == cs:
            skipped += 1
            skip_reasons["same_siren"] += 1
            continue

        fape = siren_to_ape.get(fs)
        cape = siren_to_ape.get(cs)

        if STRICT_REQUIRE_APE and (not fape or not cape):
            skipped += 1
            skip_reasons["missing_ape"] += 1
            continue

        fape = fape or "UNKNOWN_F"
        cape = cape or "UNKNOWN_C"

        doc_id = create_activity_account_id_pair(cape, fape)

        nums = collect_unique_accounts(entries)
        if not nums:
            skipped += 1
            skip_reasons["no_activity_accounts"] += 1
            continue

        accounts = [{"account_number": n, "account_description": "", "account_keywords": ""} for n in nums]
        now = datetime.now().isoformat()

        if doc_id in activity_accounts:
            merged = merge_accounts_list(activity_accounts[doc_id]["accounts"], accounts)
            activity_accounts[doc_id]["accounts"] = merged
            activity_accounts[doc_id]["updated_at"] = now
        else:
            activity_accounts[doc_id] = {
                "_id": doc_id,
                "p": "activity_account",
                "data": {"collection": "ActivityAccount", "type": "", "sub_type": ""},
                "accounts": accounts,
                "created_at": now,
                "updated_at": now
            }

        processed += 1

    docs = list(activity_accounts.values())
    if not docs:
        print("Aucun ActivityAccount à créer")
        stats = {
            "db_entries": DB_NAME,
            "db_factures": ABT_DB_NAME,
            "entries_id_prefix": ENTRIES_ID_PREFIX or "(none)",
            "journal_codes": ",".join(sorted(JOURNAL_CODES)),
            "use_inpi_api": USE_INPI_API,
            "strict_require_ape": STRICT_REQUIRE_APE,
            "fec_entries_loaded": len(fec_entries),
            "pieces_total": len(pieces),
            "sirens_detected": len(all_sirens),
            "invoice_form_ids_detected": len(form_ids),
            "local_ape_hits": len(siren_ape_local),
            "ape_lookup_missing_initial": len(missing),
            "activity_accounts_to_save": 0,
            "activity_accounts_saved_ok": 0,
            "activity_accounts_saved_errors": 0,
            "pieces_processed": processed,
            "pieces_skipped": skipped,
            "skip_reasons": dict(skip_reasons),
        }
        write_stats_text(STATS_OUTPUT, stats)
        return stats

    print(f"Sauvegarde {len(docs)} Activity Accounts…")
    res = couch_bulk_docs(sess, docs)
    ok = sum(1 for r in res if r.get("ok"))
    errs = len(docs) - ok
    print("OK :", ok)
    print("Traités :", processed)
    print("Skips :", skipped)
    stats = {
        "db_entries": DB_NAME,
        "db_factures": ABT_DB_NAME,
        "entries_id_prefix": ENTRIES_ID_PREFIX or "(none)",
        "journal_codes": ",".join(sorted(JOURNAL_CODES)),
        "use_inpi_api": USE_INPI_API,
        "strict_require_ape": STRICT_REQUIRE_APE,
        "fec_entries_loaded": len(fec_entries),
        "pieces_total": len(pieces),
        "sirens_detected": len(all_sirens),
        "invoice_form_ids_detected": len(form_ids),
        "local_ape_hits": len(siren_ape_local),
        "ape_lookup_missing_initial": len(missing),
        "activity_accounts_to_save": len(docs),
        "activity_accounts_saved_ok": ok,
        "activity_accounts_saved_errors": errs,
        "pieces_processed": processed,
        "pieces_skipped": skipped,
        "skip_reasons": dict(skip_reasons),
    }
    write_stats_text(STATS_OUTPUT, stats)
    return stats

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Crée des ActivityAccount (paire APE client/fournisseur) à partir du FEC (journaux achat)."
        )
        parser.add_argument("--db-entries", "--db", dest="db_entries", default=DB_NAME, help="Base CouchDB des entries.")
        parser.add_argument("--client-siren", "--siren", default=CLIENT_SIREN, help="SIREN client pour filtrer les entries.")
        parser.add_argument(
            "--entries-id-prefix",
            default=None,
            help="Override du préfixe _id des entries (ex: fr_bd_123456789:).",
        )
        parser.add_argument(
            "--db-factures",
            "--db-abt",
            dest="db_factures",
            default=ABT_DB_NAME,
            help="Base CouchDB contenant les invoice_forms (pour extraire les APE).",
        )
        parser.add_argument(
            "--journal-codes",
            default=",".join(sorted(JOURNAL_CODES)),
            help="Liste de journaux achat, séparés par des virgules (ex: AC,HA).",
        )
        parser.add_argument(
            "--use-inpi-api",
            action=argparse.BooleanOptionalAction,
            default=USE_INPI_API,
            help="Active l'API INPI pour compléter les APE manquants.",
        )
        parser.add_argument(
            "--strict-require-ape",
            action=argparse.BooleanOptionalAction,
            default=STRICT_REQUIRE_APE,
            help="Ignore les pièces si APE client/fournisseur manquant.",
        )
        parser.add_argument("--ape-cache-path", default=CACHE_PATH, help="Chemin du cache APE (json).")
        parser.add_argument(
            "--inpi-base-url",
            default=INPI_BASE_URL,
            help="Base URL API recherche-entreprises (ex: https://recherche-entreprises.api.gouv.fr).",
        )
        parser.add_argument(
            "--inpi-username",
            default=INPI_USERNAME,
            help="Compat héritée: ignoré (l'API recherche-entreprises ne nécessite pas d'auth).",
        )
        parser.add_argument(
            "--inpi-password",
            default=INPI_PASSWORD,
            help="Compat héritée: ignoré (l'API recherche-entreprises ne nécessite pas d'auth).",
        )
        parser.add_argument("--max-workers", type=int, default=MAX_WORKERS, help="Nombre de workers.")
        parser.add_argument("--max-qps", type=float, default=MAX_QPS, help="Débit max INPI (QPS).")
        parser.add_argument("--stats-output", default=STATS_OUTPUT, help="Chemin du fichier texte de stats.")
        args = parser.parse_args()

        DB_NAME = args.db_entries
        if args.entries_id_prefix:
            ENTRIES_ID_PREFIX = args.entries_id_prefix
        elif args.client_siren:
            ENTRIES_ID_PREFIX = f"fr_bd_{args.client_siren}:"
        else:
            ENTRIES_ID_PREFIX = ""
        ABT_DB_NAME = args.db_factures
        JOURNAL_CODES = _parse_codes(args.journal_codes)
        USE_INPI_API = args.use_inpi_api
        STRICT_REQUIRE_APE = args.strict_require_ape
        CACHE_PATH = args.ape_cache_path
        INPI_BASE_URL = args.inpi_base_url
        INPI_USERNAME = args.inpi_username
        INPI_PASSWORD = args.inpi_password
        MAX_WORKERS = args.max_workers
        requested_qps = args.max_qps
        MAX_QPS = max(0.1, min(float(requested_qps or 0), INPI_QPS_HARD_LIMIT))
        STATS_OUTPUT = args.stats_output

        if requested_qps > INPI_QPS_HARD_LIMIT:
            print(
                f"[WARN] --max-qps={requested_qps} > {INPI_QPS_HARD_LIMIT}; "
                f"plafonné à {INPI_QPS_HARD_LIMIT} req/s."
            )
        if args.inpi_username or args.inpi_password:
            print("[INFO] --inpi-username/--inpi-password ignorés avec l'API recherche-entreprises.")

        if not ENTRIES_ID_PREFIX:
            print("[WARN] Aucun filtre client actif: tous les clients de la DB entries seront scannés.")

        process_and_create_activity_accounts()
    except Exception as e:
        print("[FATAL]", e)
        sys.exit(1)
