#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
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
    "sortie",
    "port",
    "terme",
    "loyer",
    "abonnement",
    "relance",
    "maintenance",
    "entretien",
    "transport",
    "cotisation",
}

PACKAGING_HINTS = {"film", "emballage", "barquette", "sachet", "boite", "carton"}


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


def load_boucherie_invoice_ids(assign_csv: Path) -> set[str]:
    ids = set()
    with assign_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            metier = str(row.get("base_produit_metier_suggere") or "").strip().lower()
            if metier != "boucherie":
                continue
            invoice_id = str(row.get("invoice_id") or "").strip()
            if invoice_id:
                ids.add(invoice_id)
    return ids


def build_candidates(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
    invoice_ids_scope: set[str],
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
            if invoice_ids_scope and invoice_id not in invoice_ids_scope:
                continue
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

                desc_norm = normalize_text(desc)
                if not desc_norm:
                    continue

                toks = set(tokenize(desc))
                if toks & EXTERNAL_LIKE:
                    continue

                # Keep only labels with minimum lexical signal.
                if len("".join(ch for ch in desc_norm if ch.isalpha())) < 4:
                    continue
                if len(toks) == 1 and len(next(iter(toks))) <= 3:
                    continue

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
    for desc_norm, payload in stats.items():
        label = payload["label_counter"].most_common(1)[0][0]
        account = payload["account_counter"].most_common(1)[0][0]
        tva_rate = None
        if payload["tva_counter"]:
            try:
                tva_rate = float(payload["tva_counter"].most_common(1)[0][0])
            except Exception:
                tva_rate = None

        # unique invoice ids, oldest first
        uniq = {}
        for invoice_id, invoice_date in payload["invoice_rows"]:
            if invoice_id not in uniq:
                uniq[invoice_id] = invoice_date
        sorted_ids = sorted(
            uniq.items(),
            key=lambda row: (parse_date(row[1]) or datetime.max, row[0]),
        )
        source_ids = [row[0] for row in sorted_ids]

        canon = canonical_label(label)
        words = tokenize(label)
        sous_categorie = "emballage" if set(words) & PACKAGING_HINTS else "matiere_premiere"
        fournisseur_type = "fournisseur non alimentaire" if sous_categorie == "emballage" else "fournisseur alimentaire"

        out.append(
            {
                "article_source": label,
                "article_canonique": canon,
                "categorie": "exploitation_metier",
                "sous_categorie": sous_categorie,
                "tva_rate": tva_rate,
                "mots_cles": words[:6],
                "fournisseur_type": fournisseur_type,
                "ape_context": [],
                "notes": f"Pre-rempli auto depuis invoice_form boucherie (occurrences={payload['occurrences']})",
                "source_invoice_ids": source_ids,
                "compte_comptable": account,
                "compte_comptable_source": "invoice_form_reference_v1",
                "compte_comptable_match_score": min(400, 250 + payload["occurrences"]),
                "compte_comptable_match_reason": "from_invoice_form_boucherie_scope",
                "_occurrences": payload["occurrences"],
            }
        )

    out.sort(key=lambda row: (-row["_occurrences"], row["article_source"]))
    return out


def merge_base(base_data: dict, candidates: list[dict], target_total: int) -> tuple[dict, int]:
    items = base_data.get("items") or []
    if not isinstance(items, list):
        items = []

    existing_norm = {normalize_text(str(item.get("article_source") or "")) for item in items if isinstance(item, dict)}
    added = 0

    for cand in candidates:
        if len(items) >= target_total:
            break
        key = normalize_text(cand.get("article_source") or "")
        if not key or key in existing_norm:
            continue
        item = dict(cand)
        item.pop("_occurrences", None)
        # Keep only first 10 source ids to avoid huge payloads.
        item["source_invoice_ids"] = (item.get("source_invoice_ids") or [])[:10]
        items.append(item)
        existing_norm.add(key)
        added += 1

    meta = base_data.get("meta") or {}
    meta["items_count"] = len(items)
    meta["boucherie_expansion_from_invoice_form"] = {
        "added_items": added,
        "target_total": target_total,
        "source": "invoice_form",
        "rule": "scope=boucherie template + account startswith 60 + lexical quality filters",
    }
    base_data["meta"] = meta
    base_data["items"] = items
    return base_data, added


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand boucherie base with more real article sources from invoice_form.")
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--partition-prefix", default="fr_bd_519665103")
    parser.add_argument("--assign-csv", default="invoice_form_519665103_metier_assignment_template_with_ape.csv")
    parser.add_argument("--base-json", default="base_produits_boucherie_v1.json")
    parser.add_argument("--base-json-with-accounts", default="base_produits_boucherie_v1_with_accounts.json")
    parser.add_argument("--target-total", type=int, default=40)
    args = parser.parse_args()

    assign_csv = resolve_path(args.assign_csv)
    base_json = resolve_path(args.base_json)
    base_json_wa = resolve_path(args.base_json_with_accounts)
    if not assign_csv.exists():
        raise SystemExit(f"Assignment CSV missing: {assign_csv}")
    if not base_json.exists() or not base_json_wa.exists():
        raise SystemExit("Base JSON file missing.")

    invoice_scope = load_boucherie_invoice_ids(assign_csv)
    session = http_session()
    candidates = build_candidates(
        session=session,
        db_name=args.db_factures,
        partition_prefix=args.partition_prefix,
        invoice_ids_scope=invoice_scope,
    )

    base_data = json.loads(base_json.read_text(encoding="utf-8-sig"))
    base_wa_data = json.loads(base_json_wa.read_text(encoding="utf-8-sig"))

    updated, added = merge_base(base_data, candidates, max(2, int(args.target_total)))
    updated_wa, added_wa = merge_base(base_wa_data, candidates, max(2, int(args.target_total)))

    base_json.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    base_json_wa.write_text(json.dumps(updated_wa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] invoice_scope={len(invoice_scope)}")
    print(f"[INFO] candidates={len(candidates)}")
    print(f"[OK] file={base_json} added_items={added} total_items={len(updated.get('items') or [])}")
    print(f"[OK] file={base_json_wa} added_items={added_wa} total_items={len(updated_wa.get('items') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
