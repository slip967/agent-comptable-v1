#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fast_invoice_matcher_v3.py - Rapprochement factures depuis CouchDB

Modification majeure:
- Plus de dépendance au filesystem (pas de parcours de PDFs)
- Deux bases CouchDB distinctes: une pour les factures (JSONs), une pour les entries
- Parcours des invoice_forms pour les matcher avec les entries
- Lien par invoice_form_id dans les entries
"""

import os
import re
import requests
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)

# ───────────────────────────────────────────────
# CONFIGURATION - DEUX BASES DISTINCTES
# ───────────────────────────────────────────────
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL)

# SIREN (optionnel) pour filtrer les docs d'un seul client (prefix fr_bd_<SIREN>:...)
def _guess_siren(value: str) -> str:
    m = re.search(r"(\d{9})", value or "")
    return m.group(1) if m else ""

CLIENT_SIREN = (os.getenv("CLIENT_SIREN") or _guess_siren(os.getenv("DB_ENTRIES"))).strip()
ENTRIES_ID_PREFIX = os.getenv("ENTRIES_ID_PREFIX") or (f"fr_bd_{CLIENT_SIREN}:" if CLIENT_SIREN else "")
INVOICE_FORMS_ID_PREFIX = os.getenv("INVOICE_FORMS_ID_PREFIX") or (f"fr_bd_{CLIENT_SIREN}:" if CLIENT_SIREN else "")

# Base pour les factures (invoice_form + core_profile)
DB_FACTURES = os.getenv("DB_FACTURES", "abt3")  # ← À ADAPTER
COUCHDB_USER_FACTURES = DEFAULT_COUCHDB_USER
COUCHDB_PASS_FACTURES = DEFAULT_COUCHDB_PASS

# Base pour les entries comptables
DB_ENTRIES = os.getenv("DB_ENTRIES", "ayasmine_test")  # ← À ADAPTER
COUCHDB_USER_ENTRIES = DEFAULT_COUCHDB_USER
COUCHDB_PASS_ENTRIES = DEFAULT_COUCHDB_PASS

# Certificats (communs ou distincts selon config)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

# Fichier CSV de sortie pour les non-match
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "/root/traité/non_matched_invoices.csv")

# Tolérances
DATE_TOLERANCE = int(os.getenv("DATE_TOLERANCE", "2"))  # jours de tolérance pour le matching date
MAX_ROWS_SCAN = int(os.getenv("MAX_ROWS_SCAN", "200000"))
REQ_TIMEOUT_S = int(os.getenv("REQ_TIMEOUT_S", "18000"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))  # Parallélisation du traitement

# Phase 1: enrichir toutes les lignes de la pièce (si True: uniquement lignes 401)
ONLY_401 = (os.getenv("ONLY_401", "false").lower() == "true")

_session_factures = None
_session_entries = None

# CACHES GLOBAUX
CACHE_ENTRIES = {}                      # id -> entry (light)
CACHE_INVOICE_FORMS = {}                # id -> invoice_form
ENTRIES_BY_DATE = defaultdict(list)     # "YYYY-MM-DD" -> [entries]
ENTRIES_BY_PIECEID = defaultdict(list)  # piece_id -> [entries]
ENTRY_PREFIX_COUNTS = Counter()         # "fr_bd_xxx" -> nb entries
INVOICE_PREFIX_COUNTS = Counter()       # "fr_bd_xxx" -> nb invoice_forms

# ───────────────────────────────────────────────
# HTTP CouchDB - DEUX SESSIONS
# ───────────────────────────────────────────────
def http_factures():
    """Session pour la base des factures"""
    global _session_factures
    if _session_factures is None:
        s = requests.Session()
        s.auth = (COUCHDB_USER_FACTURES, COUCHDB_PASS_FACTURES)
        s.cert = (CLIENT_CERT, CLIENT_KEY)
        s.verify = CA_CERT
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3)
        s.mount("https://", adapter)
        _session_factures = s
    return _session_factures


def http_entries():
    """Session pour la base des entries"""
    global _session_entries
    if _session_entries is None:
        s = requests.Session()
        s.auth = (COUCHDB_USER_ENTRIES, COUCHDB_PASS_ENTRIES)
        s.cert = (CLIENT_CERT, CLIENT_KEY)
        s.verify = CA_CERT
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3)
        s.mount("https://", adapter)
        _session_entries = s
    return _session_entries


def couch_url(db_name, path=""):
    path = path.lstrip("/")
    return f"{COUCHDB_URL}/{db_name}/{path}" if path else f"{COUCHDB_URL}/{db_name}"


def couch_request(session, db_name, method, path="", **kwargs):
    url = couch_url(db_name, path)
    kwargs.setdefault("timeout", REQ_TIMEOUT_S)
    resp = session.request(method, url, **kwargs)
    if not resp.ok:
        raise RuntimeError(f"CouchDB error [{resp.status_code}] {url}: {resp.text}")
    if resp.content and resp.headers.get("Content-Type", "").startswith("application/json"):
        return resp.json()
    return {"ok": True}


def couch_get(session, db_name, doc_id):
    try:
        return couch_request(session, db_name, "GET", doc_id)
    except:
        return None


def couch_find(session, db_name, selector, fields=None, limit=1000, bookmark=None):
    payload = {"selector": selector, "limit": limit}
    if fields:
        payload["fields"] = fields
    if bookmark:
        payload["bookmark"] = bookmark
    return couch_request(session, db_name, "POST", "_find", json=payload)


def couch_bulk_get(session, db_name, ids):
    if not ids:
        return {}
    result = {}
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i+BATCH_SIZE]
        payload = {"docs": [{"id": id_} for id_ in batch]}
        try:
            res = couch_request(session, db_name, "POST", "_bulk_get", json=payload)
            for row in res.get("results", []):
                _id = row.get("id")
                docs = row.get("docs", [])
                if docs and "ok" in docs[0]:
                    result[_id] = docs[0]["ok"]
        except Exception as e:
            print(f"[WARN] Bulk get failed, fallback to individual: {e}")
            for id_ in batch:
                doc = couch_get(session, db_name, id_)
                if doc:
                    result[id_] = doc
    return result


def couch_bulk_docs(session, db_name, docs):
    if not docs:
        return []
    results = []
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i+BATCH_SIZE]
        payload = {"docs": batch, "new_edits": True}
        res = couch_request(session, db_name, "POST", "_bulk_docs", json=payload)
        results.extend(res)
    return results


# ───────────────────────────────────────────────
# CACHE & INDEX
# ───────────────────────────────────────────────
def load_all_entries():
    """
    Charge les entries depuis DB_ENTRIES et indexe par:
    - date
    - piece_id
    """
    global CACHE_ENTRIES, ENTRIES_BY_DATE, ENTRIES_BY_PIECEID, ENTRY_PREFIX_COUNTS

    print(f"[CACHE] Chargement des entries depuis {DB_ENTRIES}...")
    res = couch_find(
        http_entries(),
        DB_ENTRIES,
        {"p": "entry"},
        fields=[
            "_id", "piece_id", "piece_ref", "piece_date", "date",
            "debit", "credit", "account_number", "aux_account", "label",
            "journal_code", "invoice"
        ],
        limit=MAX_ROWS_SCAN,
    )
    docs = res.get("docs", [])

    for doc in docs:
        # 🔥 Filtrer sur un seul client si demandé (prefix fr_bd_<SIREN>:...)
        if ENTRIES_ID_PREFIX and not str(doc.get("_id", "")).startswith(ENTRIES_ID_PREFIX):
            continue

        CACHE_ENTRIES[doc["_id"]] = doc
        prefix = str(doc.get("_id", "")).split(":", 1)[0]
        if prefix:
            ENTRY_PREFIX_COUNTS[prefix] += 1

        # index date
        for date_field in ["piece_date", "date"]:
            if date_field in doc and doc[date_field]:
                date_str = str(doc[date_field])[:10]
                ENTRIES_BY_DATE[date_str].append(doc)

        # index piece_id
        if doc.get("piece_id"):
            ENTRIES_BY_PIECEID[doc["piece_id"]].append(doc)

    print(f"[CACHE] {len(CACHE_ENTRIES)} entries | {len(ENTRIES_BY_DATE)} dates | {len(ENTRIES_BY_PIECEID)} piece_ids")


def load_all_invoice_forms():
    """
    Charge tous les invoice_form depuis DB_FACTURES
    """
    global CACHE_INVOICE_FORMS, INVOICE_PREFIX_COUNTS

    print(f"[CACHE] Chargement des invoice_forms depuis {DB_FACTURES}...")
    res = couch_find(http_factures(), DB_FACTURES, {"p": "invoice_form"}, limit=MAX_ROWS_SCAN)
    docs = res.get("docs", [])

    for doc in docs:
        # 🔥 Filtrer sur un seul client si demandé (prefix fr_bd_<SIREN>:...)
        if INVOICE_FORMS_ID_PREFIX and not str(doc.get("_id", "")).startswith(INVOICE_FORMS_ID_PREFIX):
            continue

        CACHE_INVOICE_FORMS[doc["_id"]] = doc
        prefix = str(doc.get("_id", "")).split(":", 1)[0]
        if prefix:
            INVOICE_PREFIX_COUNTS[prefix] += 1

    print(f"[CACHE] {len(CACHE_INVOICE_FORMS)} invoice_forms chargés")


# ───────────────────────────────────────────────
# UTILS
# ───────────────────────────────────────────────
def to_date(s):
    if not s:
        return None
    try:
        return dateparser.parse(str(s), dayfirst=("/" in str(s))).date()
    except:
        return None


def to_float(s):
    if s is None or s == "":
        return None
    try:
        return float(str(s).replace(",", "."))
    except:
        return None


def normalize_num(s):
    if not s:
        return None
    s = str(s).strip().upper()
    s = re.sub(r"[-_\s/\\]+", "", s)
    s = re.sub(r"^(FAC|FACT|FACTURE|INV|INVOICE|FC|F)\s*(?=\d)", "", s)
    if s.isdigit():
        s = str(int(s))
    return s


# ───────────────────────────────────────────────
# EXTRACTION METADATA DEPUIS INVOICE_FORM
# ───────────────────────────────────────────────
def extract_meta_from_invoice_form(invoice_form):
    """Extrait les métadonnées nécessaires depuis un invoice_form"""
    if not isinstance(invoice_form, dict):
        return {
            "numero_facture": None,
            "date_facture": None,
            "montant_ttc": None,
            "siren_emetteur": None,
            "siren_destinataire": None,
        }

    # Numéro facture
    numero = invoice_form.get("invoice_number")
    if isinstance(numero, str):
        numero = normalize_num(numero)

    # Date facture
    datef = invoice_form.get("invoice_date")
    if datef:
        if str(datef).startswith("0000"):
            datef = None
        else:
            d = to_date(datef)
            datef = d.isoformat() if d else None

    # Montant TTC
    ttc = invoice_form.get("total_gross")
    ttc = to_float(ttc)

    # SIREN émetteur
    issuer = invoice_form.get("issuer", {})
    siren_emetteur = issuer.get("siren")
    if not siren_emetteur:
        regs = issuer.get("company_registrations", [])
        for reg in regs:
            if isinstance(reg, dict) and reg.get("type") == "SIREN":
                siren_emetteur = reg.get("value")
                break

    # SIREN destinataire
    recipient = invoice_form.get("recipient", {})
    siren_destinataire = recipient.get("siren")
    if not siren_destinataire:
        regs = recipient.get("company_registrations", [])
        for reg in regs:
            if isinstance(reg, dict) and reg.get("type") == "SIREN":
                siren_destinataire = reg.get("value")
                break

    return {
        "numero_facture": numero,
        "date_facture": datef,
        "montant_ttc": ttc,
        "siren_emetteur": siren_emetteur,
        "siren_destinataire": siren_destinataire,
    }


# ───────────────────────────────────────────────
# MATCHING
# ───────────────────────────────────────────────
def group_by_piece(entries):
    groups = defaultdict(list)
    for e in entries:
        pid = e.get("piece_id") or f"piece:{e['_id']}"
        groups[pid].append(e)

    result = {}
    for pid, rows in groups.items():
        sumd = sum(float(r.get("debit", 0)) for r in rows)
        sumc = sum(float(r.get("credit", 0)) for r in rows)
        result[pid] = {
            "piece_id": pid,
            "rows": rows,
            "montant_abs_total": round(max(sumd, sumc), 2),
        }
    return result


def find_piece_for_invoice(meta):
    """
    Matching amélioré :
      1. Match standard : une ligne = TTC
      2. Fallback : total piece_id (sum) = TTC
    """

    dte = to_date(meta.get("date_facture"))
    ttc = to_float(meta.get("montant_ttc"))

    if not dte:
        return None, "pas_de_date_facture"
    if not ttc or ttc <= 0:
        return None, "pas_de_montant_ttc"

    # Les entries sont déjà filtrées lors du chargement du cache
    if not CACHE_ENTRIES:
        return None, "aucune_entry_disponible"

    # 1) MATCH CLASSIQUE PAR LIGNE EXACTE
    matching_entries = []

    for days_offset in range(-DATE_TOLERANCE, DATE_TOLERANCE + 1):
        search_date = (dte + timedelta(days=days_offset)).isoformat()
        entries_of_day = ENTRIES_BY_DATE.get(search_date, [])

        for entry in entries_of_day:

            debit = entry.get("debit")
            credit = entry.get("credit")

            # Match exact TTC
            if debit is not None and abs(float(debit) - ttc) < 0.01:
                matching_entries.append(entry)

            elif credit is not None and abs(float(credit) - ttc) < 0.01:
                matching_entries.append(entry)

    # Si match simple → grouper
    if matching_entries:
        groups = group_by_piece(matching_entries)
        if len(groups) == 1:
            return list(groups.values())[0], "match_ttc_exact"
        else:
            # Choisir la date la plus proche
            best = None
            best_diff = 9999
            for pid, g in groups.items():
                pd = None
                for r in g["rows"]:
                    pd = to_date(r.get("piece_date")) or to_date(r.get("date"))
                    if pd:
                        break
                if pd:
                    diff = abs((pd - dte).days)
                    if diff < best_diff:
                        best = g
                        best_diff = diff
            if best:
                return best, "match_ttc_exact_multi_date_closest"

    # 2) FALLBACK : MATCH SUR TOTAL DU PIECE_ID (SOMME = TTC)
    candidate_pieces = []

    for pid, entries in ENTRIES_BY_PIECEID.items():

        # Calcul du total absolu de la pièce
        sumd = sum(float(x.get("debit", 0) or 0) for x in entries)
        sumc = sum(float(x.get("credit", 0) or 0) for x in entries)
        total_piece = max(sumd, sumc)

        if abs(total_piece - ttc) < 0.01:

            # Vérifier proximité date
            piece_dates = [
                to_date(x.get("piece_date")) or to_date(x.get("date"))
                for x in entries
                if to_date(x.get("piece_date")) or to_date(x.get("date"))
            ]

            if not piece_dates:
                continue

            # Prendre date de pièce la plus proche de la facture
            closest_date = min(piece_dates, key=lambda d: abs((d - dte).days))
            diff = abs((closest_date - dte).days)

            if diff <= DATE_TOLERANCE:
                candidate_pieces.append((pid, entries, diff))

    if candidate_pieces:
        # choisir la pièce avec date la plus proche
        pid, entries, _ = min(candidate_pieces, key=lambda x: x[2])
        group = group_by_piece(entries)[pid]
        return group, "fallback_sum_piece_equals_ttc"

    # Rien trouvé
    return None, "montant_non_trouve_dans_periode_ni_total_piece"



# ───────────────────────────────────────────────
# EXPANSION PAR piece_id
# ───────────────────────────────────────────────
def expand_piece_group_all_entries(piece_group):
    """Étend le groupe à TOUTES les écritures du même piece_id"""
    pid = piece_group.get("piece_id")
    if not pid:
        return piece_group
    
    all_rows = ENTRIES_BY_PIECEID.get(pid)
    if not all_rows:
        return piece_group
    
    sumd = sum(float(r.get("debit", 0)) for r in all_rows)
    sumc = sum(float(r.get("credit", 0)) for r in all_rows)
    expanded = {
        "piece_id": pid,
        "rows": all_rows,
        "montant_abs_total": round(max(sumd, sumc), 2),
    }
    return expanded


# ───────────────────────────────────────────────
# ENRICHISSEMENT ENTRIES
# ───────────────────────────────────────────────
def build_invoice_block(meta, invoice_form_id, core_profile_id):
    """Construit le bloc invoice à ajouter aux entries"""
    return {
        "invoice_form_id": invoice_form_id,
        "core_profile_id": core_profile_id,
        "numero_facture": meta.get("numero_facture"),
        "date_facture": meta.get("date_facture"),
        "montant_ttc": meta.get("montant_ttc"),
        "siren_emetteur": meta.get("siren_emetteur"),
        "siren_destinataire": meta.get("siren_destinataire"),
        "matched_at": datetime.utcnow().isoformat() + "Z",
    }


def _merge_invoice_preserving_values(existing: dict, newblk: dict) -> dict:
    """
    Fusion prudente: ne JAMAIS remplacer une valeur non nulle par None
    """
    out = dict(existing or {})
    
    # Champs à ne pas écraser par None
    for k in ("numero_facture", "date_facture", "montant_ttc", "siren_emetteur", "siren_destinataire"):
        nv = newblk.get(k)
        ov = out.get(k)
        if nv is not None:
            out[k] = nv
        else:
            out[k] = ov if ov is not None else None

    # IDs: toujours mettre à jour
    for k in ("invoice_form_id", "core_profile_id", "matched_at"):
        if newblk.get(k):
            out[k] = newblk[k]

    return out


def prepare_entries_update(piece_group, invoice_block):
    """
    Prépare les docs complets à mettre à jour avec fusion prudente
    """
    ids = []
    for r in piece_group["rows"]:
        if "_id" not in r:
            continue
        if ONLY_401 and not str(r.get("account_number", "")).startswith("401"):
            continue
        ids.append(r["_id"])

    if not ids:
        return []

    docs_map = couch_bulk_get(http_entries(), DB_ENTRIES, ids)
    docs_to_update = []
    
    for _id, doc in docs_map.items():
        existing = doc.get("invoice")
        if isinstance(existing, dict) and existing:
            doc["invoice"] = _merge_invoice_preserving_values(existing, invoice_block)
        else:
            doc["invoice"] = invoice_block
        docs_to_update.append(doc)

    return docs_to_update


# ───────────────────────────────────────────────
# TRAITEMENT D'UNE FACTURE
# ───────────────────────────────────────────────
def process_invoice_form(invoice_form):
    """
    Traite un invoice_form:
    1. Extrait les métadonnées
    2. Fait le matching avec les entries
    3. Met à jour les entries
    """
    try:
        invoice_form_id = invoice_form["_id"]
        invoice_prefix = str(invoice_form_id).split(":", 1)[0]

        # Si des préfixes entries sont connus et que celui de la facture n'existe pas,
        # le match est impossible (évite un faux "montant_non_trouve...").
        if ENTRY_PREFIX_COUNTS and invoice_prefix and invoice_prefix not in ENTRY_PREFIX_COUNTS:
            return {
                "status": "no_match",
                "invoice_form_id": invoice_form_id,
                "core_profile_id": None,
                "reason": "prefix_absent_entries_db",
                "meta": extract_meta_from_invoice_form(invoice_form),
            }

        # Récupérer le core_profile lié (optionnel)
        core_ref = invoice_form.get("form_common_core_ref", {})
        core_profile_id = core_ref.get("id") if isinstance(core_ref, dict) else None

        # Extraire les métadonnées
        meta = extract_meta_from_invoice_form(invoice_form)

        # Matching
        piece, reason = find_piece_for_invoice(meta)
        if not piece:
            return {
                "status": "no_match",
                "invoice_form_id": invoice_form_id,
                "core_profile_id": core_profile_id,
                "reason": reason,
                "meta": meta,
            }

        # Expansion à toutes les écritures du piece_id
        piece = expand_piece_group_all_entries(piece)

        # Construire le bloc invoice
        inv_block = build_invoice_block(meta, invoice_form_id, core_profile_id)

        # Préparer la mise à jour
        entries_to_update = prepare_entries_update(piece, inv_block)

        return {
            "status": "match",
            "invoice_form_id": invoice_form_id,
            "core_profile_id": core_profile_id,
            "piece_id": piece["piece_id"],
            "entries_to_update": entries_to_update,
            "reason": reason,
            "meta": meta,
        }

    except Exception as e:
        return {
            "status": "error",
            "invoice_form_id": invoice_form.get("_id", "unknown"),
            "error": str(e),
        }


# ───────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────
def main():
    import time
    start_time = time.time()

    print("=" * 60)
    print("INITIALISATION DES CACHES")
    print("=" * 60)

    # Chargement parallèle des caches
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(load_all_entries),
            executor.submit(load_all_invoice_forms),
        ]
        for future in as_completed(futures):
            future.result()

    invoice_forms = list(CACHE_INVOICE_FORMS.values())
    print(f"\n[INFO] {len(invoice_forms)} invoice_forms à traiter")

    # Diagnostic de cohérence multi-clients (utile quand aucun filtre siren/prefix n'est donné)
    entry_prefixes = set(ENTRY_PREFIX_COUNTS.keys())
    invoice_prefixes = set(INVOICE_PREFIX_COUNTS.keys())
    overlap_prefixes = entry_prefixes & invoice_prefixes
    missing_invoice_prefixes = invoice_prefixes - entry_prefixes
    missing_invoices_count = sum(INVOICE_PREFIX_COUNTS[p] for p in missing_invoice_prefixes)
    print(
        f"[DIAG] Prefix entries={len(entry_prefixes)} | "
        f"prefix invoice_forms={len(invoice_prefixes)} | overlap={len(overlap_prefixes)}"
    )
    if missing_invoices_count:
        print(
            f"[WARN] {missing_invoices_count} invoice_forms ont un prefix absent de {DB_ENTRIES}; "
            f"match impossible pour ces factures."
        )
        top_missing = sorted(
            ((p, INVOICE_PREFIX_COUNTS[p]) for p in missing_invoice_prefixes),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        for pfx, cnt in top_missing:
            print(f"       - {pfx}: {cnt}")

    if not invoice_forms:
        print("[INFO] Aucune facture à traiter")
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["invoice_form_id", "reason"])
        print(f"[CSV] Créé fichier vide: {OUTPUT_CSV}")
        return

    print("\n" + "=" * 60)
    print("TRAITEMENT DES FACTURES")
    print("=" * 60)

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_invoice_form, inv): inv for inv in invoice_forms}
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            status = result["status"].upper()
            inv_id = result.get("invoice_form_id", "unknown")
            reason = result.get("reason", "")
            if i % 100 == 0 or status != "MATCH":
                if reason:
                    print(f"[{i}/{len(invoice_forms)}] {status:20} - {inv_id} | {reason}")
                else:
                    print(f"[{i}/{len(invoice_forms)}] {status:20} - {inv_id}")

    # Agrégation
    all_entries_to_update = []
    matched = 0
    not_matched = 0
    errors = 0
    non_matched_rows = []

    for result in results:
        status = result["status"]

        if status == "match":
            matched += 1
            all_entries_to_update.extend(result.get("entries_to_update", []))

        elif status == "no_match":
            not_matched += 1
            non_matched_rows.append([
                result.get("invoice_form_id", "unknown"),
                result.get("reason", "")
            ])

        elif status == "error":
            errors += 1
            non_matched_rows.append([
                result.get("invoice_form_id", "unknown"),
                f"ERROR: {result.get('error', '')}"
            ])

    # ── SAUVEGARDE EN BASE ───────────────────────────────────
    print("\n" + "=" * 60)
    print("SAUVEGARDE EN BASE")
    print("=" * 60)

    if all_entries_to_update:
        print(f"[SAVE] Mise à jour de {len(all_entries_to_update)} entries dans {DB_ENTRIES}...")
        try:
            res = couch_bulk_docs(http_entries(), DB_ENTRIES, all_entries_to_update)
            updated = sum(1 for r in res if r.get("ok"))
            print(f"[SAVE] {updated}/{len(all_entries_to_update)} entries mises à jour")
        except Exception as e:
            print(f"[ERROR] Erreur bulk update entries: {e}")

    # CSV des non-match
    try:
        os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["invoice_form_id", "reason"])
            for row in sorted(non_matched_rows):
                writer.writerow(row)
        print(f"\n[CSV] Export des non-match: {OUTPUT_CSV} ({len(non_matched_rows)} lignes)")
    except Exception as e:
        print(f"[ERROR][CSV] Impossible d'écrire le CSV: {e}")

    # Résumé
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("RÉSUMÉ FINAL")
    print("=" * 60)
    print(f"  Factures matchées:                 {matched}")
    print(f"  Entries mises à jour:              {len(all_entries_to_update)}")
    print(f"  Non matchées:                      {not_matched}")
    print(f"  Erreurs:                           {errors}")
    print(f"  Temps total:                       {elapsed:.2f} secondes")
    if elapsed > 0:
        print(f"  Vitesse:                           {len(invoice_forms)/elapsed:.1f} factures/seconde")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rapprochement invoice_forms ↔ entries (TTC + date).")
    parser.add_argument("--db-factures", default=DB_FACTURES, help="Base CouchDB contenant les invoice_forms.")
    parser.add_argument("--db-entries", default=DB_ENTRIES, help="Base CouchDB contenant les entries FEC.")
    parser.add_argument("--client-siren", "--siren", default=CLIENT_SIREN, help="SIREN client pour filtrer les docs.")
    parser.add_argument("--entries-id-prefix", default=None, help="Override du prefix _id des entries (ex: fr_bd_123456789:).")
    parser.add_argument(
        "--invoice-forms-id-prefix",
        default=None,
        help="Override du prefix _id des invoice_forms (ex: fr_bd_123456789:).",
    )
    parser.add_argument("--output-csv", default=OUTPUT_CSV, help="Chemin CSV des factures non matchées.")
    parser.add_argument("--date-tolerance", type=int, default=DATE_TOLERANCE, help="Tolérance +/- jours pour le matching date.")
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS, help="Parallélisation du traitement des factures.")
    parser.add_argument("--only-401", action="store_true", default=ONLY_401, help="Met à jour uniquement les lignes 401.")
    args = parser.parse_args()

    DB_FACTURES = args.db_factures
    DB_ENTRIES = args.db_entries
    OUTPUT_CSV = args.output_csv
    DATE_TOLERANCE = args.date_tolerance
    MAX_WORKERS = args.max_workers
    ONLY_401 = args.only_401

    if args.entries_id_prefix:
        ENTRIES_ID_PREFIX = args.entries_id_prefix
    elif args.client_siren:
        ENTRIES_ID_PREFIX = f"fr_bd_{args.client_siren}:"
    else:
        ENTRIES_ID_PREFIX = ""

    if args.invoice_forms_id_prefix:
        INVOICE_FORMS_ID_PREFIX = args.invoice_forms_id_prefix
    elif args.client_siren:
        INVOICE_FORMS_ID_PREFIX = f"fr_bd_{args.client_siren}:"
    else:
        INVOICE_FORMS_ID_PREFIX = ""

    if not (args.client_siren or args.entries_id_prefix or args.invoice_forms_id_prefix):
        print(
            "[WARN] Aucun filtre client actif (siren/prefix). "
            "Le script va traiter toutes les factures de la DB_FACTURES."
        )

    main()
