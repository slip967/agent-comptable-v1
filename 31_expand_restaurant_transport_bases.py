#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
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


SCRIPT_DIR = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)
DEFAULT_DB = os.getenv("DB_FACTURES", "abt3")


STOP_WORDS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "a",
    "au",
    "aux",
    "et",
    "en",
    "sur",
    "pour",
    "par",
    "avec",
    "x",
    "kg",
}

EXTERNAL_LIKE = {
    "frais",
    "loyer",
    "abonnement",
    "relance",
    "terme",
    "sortie",
    "port",
    "cotisation",
    "maintenance",
    "entretien",
}

RESTAURANT_KEYWORDS = {
    "huile",
    "tournesol",
    "olive",
    "film",
    "emballage",
    "barquette",
    "boite",
    "emporter",
    "sac",
    "sachet",
    "alimentaire",
    "friture",
    "colorant",
    "thon",
    "harissa",
    "persil",
    "canelle",
}

TRANSPORT_KEYWORDS = {
    "ctte",
    "camionnette",
    "camion",
    "transport",
    "livraison",
    "gasoil",
    "diesel",
    "carburant",
    "essence",
    "peage",
    "parking",
    "stationnement",
}

PACKAGING_HINTS = {"film", "emballage", "barquette", "sachet", "boite", "carton", "sac"}


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok and tok not in STOP_WORDS]


def canonical_label(value: str) -> str:
    toks = tokenize(value)
    return " ".join(toks[:6]) if toks else normalize_text(value)


def parse_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def resolve_path(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct.resolve()
    return (SCRIPT_DIR / name).resolve()


def build_candidates(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
    keyword_set: set[str],
) -> list[dict]:
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
    selector = {"p": "invoice_form"}
    bookmark = None

    stats: dict[str, dict] = defaultdict(
        lambda: {
            "label_counter": Counter(),
            "account_counter": Counter(),
            "tva_counter": Counter(),
            "invoice_rows": [],
            "occurrences": 0,
        }
    )

    while True:
        payload = {
            "selector": selector,
            "fields": ["_id", "invoice_date", "line_items"],
            "limit": 500,
        }
        if bookmark:
            payload["bookmark"] = bookmark

        response = session.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        docs = data.get("docs") or []
        if not docs:
            break

        for doc in docs:
            invoice_id = str(doc.get("_id") or "").strip()
            invoice_date = str(doc.get("invoice_date") or "").strip()

            for line in doc.get("line_items") or []:
                if not isinstance(line, dict):
                    continue
                desc = str(line.get("description") or "").strip()
                account = str(line.get("accounting_account") or "").strip()
                if not desc or not account:
                    continue
                if not account.startswith("60"):
                    continue

                toks = set(tokenize(desc))
                if not toks:
                    continue
                if toks & EXTERNAL_LIKE:
                    continue
                if not (toks & keyword_set):
                    continue

                desc_norm = normalize_text(desc)
                bucket = stats[desc_norm]
                bucket["occurrences"] += 1
                bucket["label_counter"][desc] += 1
                bucket["account_counter"][account] += 1
                vat_percent = line.get("vat_percent")
                if vat_percent is not None:
                    bucket["tva_counter"][str(vat_percent)] += 1
                bucket["invoice_rows"].append((invoice_id, invoice_date))

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark

    out = []
    for _desc_norm, payload in stats.items():
        label = payload["label_counter"].most_common(1)[0][0]
        account = payload["account_counter"].most_common(1)[0][0]
        tva_rate = None
        if payload["tva_counter"]:
            try:
                tva_rate = float(payload["tva_counter"].most_common(1)[0][0])
            except Exception:
                tva_rate = None

        uniq = {}
        for invoice_id, invoice_date in payload["invoice_rows"]:
            if invoice_id not in uniq:
                uniq[invoice_id] = invoice_date
        sorted_ids = sorted(uniq.items(), key=lambda row: (parse_date(row[1]) or datetime.max, row[0]))
        source_ids = [row[0] for row in sorted_ids][:10]

        words = tokenize(label)
        sous_categorie = "emballage" if set(words) & PACKAGING_HINTS else "matiere_premiere"
        fournisseur_type = "fournisseur non alimentaire" if sous_categorie == "emballage" else "fournisseur alimentaire"

        out.append(
            {
                "article_source": label,
                "article_canonique": canonical_label(label),
                "categorie": "exploitation_metier",
                "sous_categorie": sous_categorie,
                "tva_rate": tva_rate,
                "mots_cles": words[:6],
                "fournisseur_type": fournisseur_type,
                "ape_context": [],
                "notes": f"Pre-rempli auto depuis invoice_form metier (occurrences={payload['occurrences']})",
                "source_invoice_ids": source_ids,
                "compte_comptable": account,
                "compte_comptable_source": "invoice_form_reference_v1",
                "compte_comptable_match_score": min(400, 250 + payload["occurrences"]),
                "compte_comptable_match_reason": "from_invoice_form_keyword_scope",
                "_occurrences": payload["occurrences"],
            }
        )

    out.sort(key=lambda row: (-row["_occurrences"], row["article_source"]))
    return out


def merge_base(base_data: dict, candidates: list[dict], target_total: int, metier_name: str) -> tuple[dict, int]:
    items = base_data.get("items") or []
    if not isinstance(items, list):
        items = []

    existing = {normalize_text(str(item.get("article_source") or "")) for item in items if isinstance(item, dict)}
    added = 0

    for cand in candidates:
        if len(items) >= target_total:
            break
        key = normalize_text(cand.get("article_source") or "")
        if not key or key in existing:
            continue
        item = dict(cand)
        item.pop("_occurrences", None)
        items.append(item)
        existing.add(key)
        added += 1

    meta = base_data.get("meta") or {}
    meta["items_count"] = len(items)
    meta[f"{metier_name}_expansion_from_invoice_form"] = {
        "added_items": added,
        "target_total": target_total,
        "source": "invoice_form",
        "rule": "account startswith 60 + metier keyword filters + lexical quality",
    }
    base_data["meta"] = meta
    base_data["items"] = items
    return base_data, added


def process_metier(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
    base_path: Path,
    base_wa_path: Path,
    keyword_set: set[str],
    target_total: int,
    metier_name: str,
) -> tuple[int, int, int]:
    candidates = build_candidates(
        session=session,
        db_name=db_name,
        partition_prefix=partition_prefix,
        keyword_set=keyword_set,
    )
    data = json.loads(base_path.read_text(encoding="utf-8-sig"))
    data_wa = json.loads(base_wa_path.read_text(encoding="utf-8-sig"))

    updated, added = merge_base(data, candidates, target_total=target_total, metier_name=metier_name)
    updated_wa, added_wa = merge_base(data_wa, candidates, target_total=target_total, metier_name=metier_name)

    base_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    base_wa_path.write_text(json.dumps(updated_wa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(candidates), added, added_wa


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand restaurant and transport bases from invoice_form.")
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--partition-prefix", default="fr_bd_519665103")
    parser.add_argument("--restaurant-target-total", type=int, default=20)
    parser.add_argument("--transport-target-total", type=int, default=6)
    parser.add_argument("--base-restaurant", default="base_produits_restaurant_v1.json")
    parser.add_argument("--base-restaurant-wa", default="base_produits_restaurant_v1_with_accounts.json")
    parser.add_argument("--base-transport", default="base_produits_transport_v1.json")
    parser.add_argument("--base-transport-wa", default="base_produits_transport_v1_with_accounts.json")
    args = parser.parse_args()

    session = http_session()

    restaurant_base = resolve_path(args.base_restaurant)
    restaurant_base_wa = resolve_path(args.base_restaurant_wa)
    transport_base = resolve_path(args.base_transport)
    transport_base_wa = resolve_path(args.base_transport_wa)

    if not restaurant_base.exists() or not restaurant_base_wa.exists() or not transport_base.exists() or not transport_base_wa.exists():
        raise SystemExit("One or more target base files are missing.")

    resto_candidates, resto_added, resto_added_wa = process_metier(
        session=session,
        db_name=args.db_factures,
        partition_prefix=args.partition_prefix,
        base_path=restaurant_base,
        base_wa_path=restaurant_base_wa,
        keyword_set=RESTAURANT_KEYWORDS,
        target_total=max(2, int(args.restaurant_target_total)),
        metier_name="restaurant",
    )
    transport_candidates, transport_added, transport_added_wa = process_metier(
        session=session,
        db_name=args.db_factures,
        partition_prefix=args.partition_prefix,
        base_path=transport_base,
        base_wa_path=transport_base_wa,
        keyword_set=TRANSPORT_KEYWORDS,
        target_total=max(1, int(args.transport_target_total)),
        metier_name="transport",
    )

    print(
        f"[OK] restaurant candidates={resto_candidates} added={resto_added} added_with_accounts={resto_added_wa}"
    )
    print(
        f"[OK] transport candidates={transport_candidates} added={transport_added} added_with_accounts={transport_added_wa}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
