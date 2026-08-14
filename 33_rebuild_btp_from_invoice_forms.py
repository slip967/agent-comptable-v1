#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
33_rebuild_btp_from_invoice_forms.py

Vide base_produits_btp_v1.json et la reconstruit depuis les invoice_form
de la base abt3 (CouchDB), en parcourant les 9 partitions BTP connues.

Usage:
  python 33_rebuild_btp_from_invoice_forms.py           # dry-run (aucune écriture)
  python 33_rebuild_btp_from_invoice_forms.py --apply   # écrase la base
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)

# ─── Config ───────────────────────────────────────────────────────────────────
COUCHDB_URL  = os.getenv("COUCHDB_URL",  DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT  = os.getenv("CLIENT_CERT",  DEFAULT_CLIENT_CERT)
CLIENT_KEY   = os.getenv("CLIENT_KEY",   DEFAULT_CLIENT_KEY)
CA_CERT      = os.getenv("CA_CERT",      DEFAULT_CA_CERT)

# abt3 ne contient pas les accounting_account ; keymanage_accounting est la source correcte
DB_FACTURES  = os.getenv("DB_FACTURES", "keymanage_accounting")
BASE_BTP_FILE = "base_produits_btp_v1.json"

# Partitions BTP confirmées (fr_bd_519665103 exclu : c'est une boucherie halal)
BTP_PARTITIONS = [
    "fr_bd_509118329",
    "fr_bd_842785719",
    "fr_bd_844858571",
    "fr_bd_879788230",
    "fr_bd_889860938",
    "fr_bd_914837463",
    "fr_bd_938751021",
    "fr_bd_947858304",
]

# Comptes 60x valides pour BTP (achats matériaux, approvisionnements, marchandises, fournitures)
COMPTES_BTP_VALIDES = {
    "601", "6011", "6012",
    "602", "6021", "6022", "6023",
    "607",
    "6061", "6062", "6063", "6068",
}

COMPTE_LIBELLES = {
    "601":  "Achats de matières premières",
    "6011": "Achats de matières premières",
    "6012": "Achats de matières premières",
    "602":  "Approvisionnements",
    "6021": "Matières consommables",
    "6022": "Produits énergétiques",
    "6023": "Matières consommables",
    "607":  "Achats de marchandises",
    "6061": "Fournitures non stockables",
    "6062": "Fournitures consommables",
    "6063": "Fournitures d'entretien et de petit équipement",
    "6068": "Autres matières et fournitures",
}

# Mots-clés de charges génériques à exclure du BTP
EXTERNAL_LIKE = {
    "frais", "loyer", "abonnement", "relance", "terme",
    "sortie", "port", "cotisation", "maintenance",
    "assurance", "electricite", "telephone", "internet",
}

# Mots-clés alimentaires / boucherie à exclure strictement du BTP
FOOD_EXCLUDE = {
    "poulet", "halal", "veau", "agneau", "boeuf", "bœuf", "viande",
    "poisson", "filet", "cuisse", "pilon", "coquelet", "dinde",
    "lapin", "chevre", "mouton", "caille", "canard", "merguez",
    "kefta", "saucisse", "miel", "lait", "beurre", "fromage",
    "yaourt", "oeuf", "farine", "sucre", "sel", "huile", "legume",
    "fruit", "poivron", "tomate", "pomme", "carotte", "oignon",
}
# Mots-clés logiciels/licences à exclure du BTP
SOFTWARE_EXCLUDE = {
    "acrobat", "adobe", "utilisateur", "licence", "logiciel",
    "microsoft", "office", "windows", "cloud", "saas",
}

# Seuil minimum d'occurrences pour inclure un article
MIN_OCCURRENCES = 2
# Nombre maximum d'articles à conserver (les plus fréquents)
MAX_ITEMS = 200
STOP_WORDS = {
    "de", "du", "des", "la", "le", "les", "a", "au", "aux",
    "et", "en", "sur", "pour", "par", "avec", "x", "l",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def http_session() -> requests.Session:
    s = requests.Session()
    s.auth  = (COUCHDB_USER, COUCHDB_PASS)
    s.cert  = (CLIENT_CERT, CLIENT_KEY)
    s.verify = CA_CERT
    s.mount("https://", HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=3))
    return s


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split()
            if tok and tok not in STOP_WORDS]


def canonical_label(value: str) -> str:
    toks = tokenize(value)
    return " ".join(toks[:8]) if toks else normalize_text(value)


def parse_date(value) -> datetime | None:
    text = str(value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def normalize_account(acc: str) -> str | None:
    if not acc:
        return None
    acc = acc.strip()
    while len(acc) > 3 and acc.endswith("0"):
        acc = acc[:-1]
    return acc


def get_val(field) -> str | None:
    """Décompresse le format {'value': ...} de keymanage_accounting."""
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return field


def parse_ape_from_party(party: dict) -> list[str]:
    apes = []
    if not isinstance(party, dict):
        return apes
    regs = party.get("company_registrations") or []
    for reg in (regs if isinstance(regs, list) else []):
        if not isinstance(reg, dict):
            continue
        if str(reg.get("type") or "").upper() in {"APE", "NAF"}:
            v = (reg.get("value") or "").strip().upper().replace(" ", "")
            if v and v not in apes:
                apes.append(v)
    return apes[:2]


def compte_libelle(acc: str) -> str:
    norm = normalize_account(acc) or acc
    for k, v in COMPTE_LIBELLES.items():
        if norm.startswith(k) or acc.startswith(k):
            return v
    return acc


def is_valid_btp_account(acc: str) -> bool:
    """Accepte tous les comptes 60x sauf 609x (rabais/remises)."""
    norm = normalize_account(acc) or acc
    if norm.startswith("609") or acc.startswith("609"):
        return False
    return norm.startswith("60") or acc.startswith("60")


def quality_ok(desc: str, toks: list[str]) -> bool:
    alpha = "".join(ch for ch in normalize_text(desc) if ch.isalpha())
    if len(alpha) < 4:
        return False
    if len(toks) == 1 and len(toks[0]) <= 3:
        return False
    return True

# ─── Fetch invoice_forms d'une partition ──────────────────────────────────────
def fetch_partition(
    session: requests.Session,
    db: str,
    partition: str,
) -> dict:
    """
    Retourne un dict {desc_norm: bucket} avec agrégat par description normalisée.
    """
    endpoint = (
        f"{COUCHDB_URL}/{quote(db, safe='')}/"
        f"_partition/{quote(partition, safe='')}/_find"
    )
    bookmark = None
    stats: dict[str, dict] = defaultdict(lambda: {
        "label_counter":   Counter(),
        "account_counter": Counter(),
        "tva_counter":     Counter(),
        "ape_counter":     Counter(),
        "invoice_rows":    [],
        "occurrences":     0,
    })

    while True:
        payload = {
            "selector": {"p": "invoice_form"},
            "fields": ["_id", "invoice_date", "line_items", "issuer"],
            "limit": 500,
        }
        if bookmark:
            payload["bookmark"] = bookmark

        try:
            resp = session.post(endpoint, json=payload, timeout=120)
            resp.raise_for_status()
        except Exception as exc:
            print(f"  [WARN] {partition}: {exc}")
            break

        data = resp.json()
        docs = data.get("docs") or []
        if not docs:
            break

        for doc in docs:
            invoice_id   = str(doc.get("_id") or "").strip()
            invoice_date = str(doc.get("invoice_date") or "").strip()
            issuer       = doc.get("issuer") or {}
            ape_issuer   = parse_ape_from_party(issuer)

            for line in (doc.get("line_items") or []):
                if not isinstance(line, dict):
                    continue

                desc    = str(get_val(line.get("description")) or "").strip()
                acc_raw = str(get_val(line.get("accounting_account")) or "").strip()

                if not desc or not acc_raw:
                    continue
                if not is_valid_btp_account(acc_raw):
                    continue

                toks = tokenize(desc)
                if not quality_ok(desc, toks):
                    continue
                if set(toks) & EXTERNAL_LIKE:
                    continue
                if set(toks) & FOOD_EXCLUDE:
                    continue
                if set(toks) & SOFTWARE_EXCLUDE:
                    continue

                desc_norm = normalize_text(desc)
                b = stats[desc_norm]
                b["occurrences"]         += 1
                b["label_counter"][desc] += 1
                b["account_counter"][normalize_account(acc_raw) or acc_raw] += 1

                vat_raw = get_val(line.get("vat_percent"))
                if vat_raw is not None:
                    b["tva_counter"][str(vat_raw)] += 1

                for ape in ape_issuer:
                    b["ape_counter"][ape] += 1

                b["invoice_rows"].append((
                    f"{partition}:{invoice_id}", invoice_date
                ))

        bm = data.get("bookmark")
        if not bm or bm == bookmark:
            break
        bookmark = bm

    return stats


# ─── Construction des items ───────────────────────────────────────────────────
def build_items(all_stats: dict) -> list[dict]:
    items = []
    for desc_norm, b in all_stats.items():
        label   = b["label_counter"].most_common(1)[0][0]
        account = b["account_counter"].most_common(1)[0][0]

        tva_rate = None
        if b["tva_counter"]:
            try:
                tva_rate = float(b["tva_counter"].most_common(1)[0][0])
            except Exception:
                pass

        ape_context = [ape for ape, _ in b["ape_counter"].most_common(3)]

        uniq: dict[str, str] = {}
        for inv_id, inv_date in b["invoice_rows"]:
            if inv_id not in uniq:
                uniq[inv_id] = inv_date

        sorted_ids = sorted(
            uniq.items(),
            key=lambda r: (parse_date(r[1]) or datetime.max, r[0]),
        )
        source_invoice_ids = [r[0] for r in sorted_ids]

        partitions_sources = list({sid.split(":")[0] for sid in source_invoice_ids})
        words = tokenize(label)

        items.append({
            "article_source":            label,
            "article_canonique":         canonical_label(label),
            "mots_cles":                 words[:8],
            "source_invoice_ids":        source_invoice_ids,
            "ids_factures_sources":      source_invoice_ids,
            "invoice_paths_sources":     [],
            "ape_context":               ape_context,
            "partitions_sources":        partitions_sources,
            "compte_comptable":          account,
            "compte_comptable_libelle":  compte_libelle(account),
            "taux_tva":                  tva_rate,
            "categorie":                 "exploitation_metier",
            "sous_categorie":            "matiere_premiere",
            "type_fournisseur":          "fournisseur_materiaux",
            "_occurrences":              b["occurrences"],
        })

    items.sort(key=lambda i: (-i["_occurrences"], i["article_source"]))
    # Seuil de fréquence minimum
    items = [i for i in items if i["_occurrences"] >= MIN_OCCURRENCES]
    # Limiter au top MAX_ITEMS (les plus fréquents)
    items = items[:MAX_ITEMS]
    for i in items:
        del i["_occurrences"]
    return items


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",    action="store_true",
                        help="Écraser base_produits_btp_v1.json (sans --apply = dry-run)")
    parser.add_argument("--db",       default=DB_FACTURES,
                        help="Base CouchDB source (défaut: keymanage_accounting)")
    parser.add_argument("--partitions", nargs="+", default=BTP_PARTITIONS,
                        metavar="PART",
                        help="Partitions BTP à parcourir")
    args = parser.parse_args()

    print(f"[config] DB={args.db}  apply={args.apply}")
    print(f"[config] {len(args.partitions)} partitions BTP")

    session   = http_session()
    all_stats = defaultdict(lambda: {
        "label_counter":   Counter(),
        "account_counter": Counter(),
        "tva_counter":     Counter(),
        "ape_counter":     Counter(),
        "invoice_rows":    [],
        "occurrences":     0,
    })

    for part in args.partitions:
        print(f"\n[fetch] partition {part} …", end=" ", flush=True)
        stats = fetch_partition(session, args.db, part)
        # Fusionner dans all_stats
        for desc_norm, b in stats.items():
            a = all_stats[desc_norm]
            a["occurrences"]   += b["occurrences"]
            a["invoice_rows"]  += b["invoice_rows"]
            a["label_counter"]   += b["label_counter"]
            a["account_counter"] += b["account_counter"]
            a["tva_counter"]     += b["tva_counter"]
            a["ape_counter"]     += b["ape_counter"]
        print(f"{len(stats)} descriptions uniques")

    print(f"\n[build] {len(all_stats)} descriptions agrégées")
    items = build_items(all_stats)
    print(f"[build] {len(items)} items construits")

    # Distribution des comptes
    from collections import Counter as Ctr
    cpt = Ctr(i["compte_comptable"] for i in items)
    print("\nDistribution comptes:")
    for c, n in cpt.most_common():
        print(f"  {c}: {n}")

    # Dry-run : afficher les 20 premiers
    print("\n[preview] 20 premiers items (par fréquence):")
    for i, item in enumerate(items[:20]):
        print(f"  {i+1:3}. {item['article_source']!r}  [{item['compte_comptable']}/{item['taux_tva']}%]  x{len(item['source_invoice_ids'])} factures")

    if not args.apply:
        print("\n[dry-run] Aucune modification. Relancer avec --apply pour appliquer.")
        return 0

    # Charger la base existante pour conserver le méta
    fp = Path(BASE_BTP_FILE)
    try:
        with fp.open(encoding="utf-8") as f:
            base = json.load(f)
    except UnicodeDecodeError:
        with fp.open(encoding="utf-8-sig") as f:
            base = json.load(f)

    old_count = len(base.get("items") or [])
    base["items"] = items
    base["meta"]["items_count"] = len(items)
    base["meta"]["updated"] = datetime.now(timezone.utc).isoformat()
    base["meta"]["rebuilt_from_invoice_forms"] = {
        "applied_at":    datetime.now(timezone.utc).isoformat(),
        "db":            args.db,
        "partitions":    args.partitions,
        "rule":          "invoice_form line_items with comptes 60x (BTP), exclure EXTERNAL_LIKE",
        "items_before":  old_count,
        "items_after":   len(items),
    }

    with fp.open("w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)

    print(f"\n[saved] {BASE_BTP_FILE}: {old_count} → {len(items)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
