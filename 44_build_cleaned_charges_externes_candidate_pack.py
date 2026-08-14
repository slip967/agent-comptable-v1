#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, RequestException

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

BASE_FILE = "base_charges_externes_v1.json"
ALLOWED_ACCOUNT_PREFIXES = (
    "6061",
    "613",
    "614",
    "615",
    "616",
    "618",
    "6226",
    "6227",
    "624",
    "626",
    "627",
    "6281",
    "628",
)

NOISE_LABELS = {
    "achat non detaille",
    "achat non détaillé",
    "article non specifie",
    "article non spécifié",
    "montant total de la commande ttc",
    "menu",
    "repas",
    "repas complet",
    "remise",
    "remise forfait",
    "remise forfait b you",
    "utilisateur standard",
    "vos abonnements forfaits et options",
    "vos services fournis par votre operateur",
}


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def post_find(session: requests.Session, endpoint: str, payload: dict, timeout: int = 120) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = session.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (ChunkedEncodingError, RequestException, ValueError) as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(min(5, attempt))
    raise RuntimeError(f"Failed to query CouchDB after retries: {endpoint}") from last_error


def unwrap_value(value):
    while isinstance(value, dict) and "value" in value:
        value = value.get("value")
    return value


def get_nested(obj, path, default=None):
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def first_non_empty(obj, paths, default=None):
    for path in paths:
        value = get_nested(obj, path, default=None)
        if value not in (None, "", [], {}):
            return value
    return default


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> set[str]:
    return set(normalize_text(value).split())


def contains_any(text: str, keywords: set[str]) -> bool:
    tokens = tokenize(text)
    if tokens & keywords:
        return True
    return any(keyword in text for keyword in keywords if " " in keyword)


def clean_text(value) -> str:
    return str(unwrap_value(value) or "").strip()


def clean_amount(value) -> str:
    raw = unwrap_value(value)
    if raw in (None, "", []):
        return ""
    try:
        return f"{float(raw):.2f}"
    except Exception:
        return str(raw).strip()


def extract_siren_from_party(party) -> str:
    if not isinstance(party, dict):
        return ""
    direct = str(unwrap_value(party.get("siren")) or "").strip()
    if direct:
        return direct
    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = str(unwrap_value(reg.get("type")) or "").strip().upper()
        reg_value = str(unwrap_value(reg.get("value")) or "").strip()
        if reg_type == "SIREN" and reg_value:
            return reg_value
        if reg_type == "SIRET" and len(reg_value) >= 9:
            return reg_value[:9]
    return ""


def extract_invoice_duplicate_key(doc) -> tuple[str, str, str, str, str] | None:
    issuer = first_non_empty(
        doc,
        [
            ("issuer",),
            ("invoice", "issuer"),
            ("data", "issuer"),
        ],
        default={},
    )
    supplier_siren = extract_siren_from_party(issuer)
    invoice_number = clean_text(doc.get("invoice_number"))
    invoice_date = clean_text(doc.get("invoice_date"))
    total_amount = clean_amount(doc.get("total_gross")) or clean_amount(doc.get("total_net"))
    document_type = clean_text(doc.get("document_type"))
    if not supplier_siren or not invoice_number or not invoice_date:
        return None
    return supplier_siren, invoice_number.upper(), invoice_date, total_amount, document_type.upper()


def get_line_items(doc):
    raw_items = first_non_empty(
        doc,
        [
            ("line_items",),
            ("invoice", "line_items"),
            ("data", "line_items"),
        ],
        default=[],
    )
    return raw_items if isinstance(raw_items, list) else []


def classify_charge(article_source: str, account: str) -> dict:
    article_canonique = normalize_text(article_source)
    text = normalize_text(f"{article_source} {article_canonique}")
    account = str(account or "").strip()

    telecom_keywords = {
        "abonnement",
        "mobile",
        "mobitpe",
        "telecom",
        "telephone",
        "internet",
        "fibre",
        "sim",
        "sims",
        "wifi",
        "forfait",
        "box",
        "bbox",
        "lycamobile",
        "sfr",
        "orange",
        "bouygues",
    }
    electricite_keywords = {
        "electricite",
        "edf",
        "energie",
        "heures pleines",
        "heures creuses",
        "soutirage",
        "kwh",
    }
    gaz_keywords = {
        "gaz",
        "propane",
        "butane",
        "grdf",
        "gdf",
        "gaz naturel",
    }
    eau_keywords = {
        "eau",
        "eaux",
        "assainissement",
        "veolia",
        "suez",
    }
    assurance_keywords = {
        "assurance",
        "prime",
        "multirisque",
        "sinistre",
        "responsabilite",
        "rc pro",
    }
    loyer_keywords = {
        "loyer",
        "charges locatives",
        "acompte sur charges",
        "solde charges",
        "solde charges locatives",
        "bail",
        "locatif",
        "locative",
    }
    entretien_keywords = {
        "entretien",
        "maintenance",
        "desourisation",
        "deratisation",
        "nettoyage",
        "parking",
        "reparation",
    }
    transport_keywords = {
        "port",
        "transport",
        "livraison",
        "messagerie",
        "expedition",
        "frais de port",
    }
    cotisation_keywords = {
        "coti",
        "cotisation",
        "interbev",
        "interb",
        "decro",
        "rsd",
        "f fixe",
        "frais fixes",
    }
    admin_keywords = {
        "relance",
        "administratif",
        "administratifs",
        "carte acheteur",
        "terme",
        "tm ht",
        "commission",
        "frais dossier",
        "frais bancaire",
    }

    sous_profil = "autres_charges_externes"
    nature_charge = "frais"
    profil_facturation = "forfait_ou_frais"
    reason = "fallback"

    if contains_any(text, telecom_keywords) or account.startswith("626"):
        sous_profil = "telecom_et_abonnements"
        nature_charge = "abonnement"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword_or_account:telecom"
    elif contains_any(text, electricite_keywords) or (account.startswith("6061") and "gaz" not in text and "eau" not in text):
        sous_profil = "energie_electricite"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword_or_account:electricite"
    elif contains_any(text, gaz_keywords):
        sous_profil = "energie_gaz"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword:gaz"
    elif contains_any(text, eau_keywords):
        sous_profil = "energie_et_utilites"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword:eau"
    elif contains_any(text, assurance_keywords) or account.startswith("616"):
        sous_profil = "assurances"
        nature_charge = "prime"
        profil_facturation = "prime_et_periode"
        reason = "keyword_or_account:assurance"
    elif contains_any(text, entretien_keywords) or account.startswith("615"):
        sous_profil = "entretien_et_maintenance"
        nature_charge = "entretien"
        profil_facturation = "intervention_ponctuelle"
        reason = "keyword_or_account:entretien"
    elif contains_any(text, loyer_keywords) or account.startswith(("613", "614")):
        sous_profil = "loyers_et_charges_locatives"
        nature_charge = "loyer" if "loyer" in text else "charges_locatives"
        profil_facturation = "loyer_et_charges"
        reason = "keyword_or_account:loyer"
    elif contains_any(text, transport_keywords) or account.startswith("624"):
        sous_profil = "transport_et_logistique"
        nature_charge = "transport"
        profil_facturation = "prestation_ponctuelle"
        reason = "keyword_or_account:transport"
    elif contains_any(text, cotisation_keywords) or account.startswith(("6227", "6281")):
        sous_profil = "cotisations_professionnelles"
        nature_charge = "cotisation"
        profil_facturation = "cotisation_ou_forfait"
        reason = "keyword_or_account:cotisation"
    elif contains_any(text, admin_keywords) or account.startswith(("6226", "627")):
        sous_profil = "frais_administratifs_et_bancaires"
        nature_charge = "frais"
        profil_facturation = "forfait_ou_frais"
        reason = "keyword_or_account:administratif"

    return {
        "sous_profil": sous_profil,
        "nature_charge": nature_charge,
        "profil_facturation": profil_facturation,
        "classification_reason": reason,
    }


def should_keep_charge(description: str, account: str, classification: dict) -> bool:
    if not description or not account:
        return False

    normalized = normalize_text(description)
    if not normalized or normalized in NOISE_LABELS:
        return False
    if len(normalized) <= 3:
        return False
    if normalized.isdigit():
        return False

    alpha_count = sum(1 for ch in normalized if ch.isalpha())
    if alpha_count < 3:
        return False

    if classification["classification_reason"] != "fallback":
        return True
    return any(str(account).startswith(prefix) for prefix in ALLOWED_ACCOUNT_PREFIXES)


def load_existing_base_keys(root_dir: Path) -> set[str]:
    payload = json.loads((root_dir / BASE_FILE).read_text(encoding="utf-8-sig"))
    keys = set()
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = normalize_text(str(item.get("article_source") or ""))
        if key:
            keys.add(key)
    return keys


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "article_source",
                "normalized_label",
                "invoice_count",
                "line_occurrences",
                "sample_account",
                "predicted_sous_profil",
                "predicted_nature_charge",
                "predicted_profil_facturation",
                "classification_reason",
                "already_in_base",
                "partitions",
            ],
        )
        writer.writeheader()
        for row in rows:
            payload = dict(row)
            payload["partitions"] = " | ".join(payload.get("partitions") or [])
            writer.writerow(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cleaned candidate pack for charges externes.")
    parser.add_argument("--report-json", default="copy_keymanage_metier_docs_report_quality_v3.json")
    parser.add_argument("--source-db", default="")
    parser.add_argument("--output-dir", default="candidate_packs_metier")
    parser.add_argument("--top-n", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = (SCRIPT_DIR / args.report_json).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source_db = str(args.source_db or report.get("source_db") or "").strip()
    if not source_db:
        raise SystemExit("Missing source_db.")

    output_dir = (SCRIPT_DIR / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_base = load_existing_base_keys(SCRIPT_DIR)
    session = http_session()

    counters = defaultdict(
        lambda: {
            "label_counter": Counter(),
            "invoice_ids": set(),
            "partitions": set(),
            "account_counter": Counter(),
            "line_occurrences": 0,
            "sous_profil_counter": Counter(),
            "nature_counter": Counter(),
            "profil_counter": Counter(),
            "reason_counter": Counter(),
        }
    )

    partitions = report.get("partitions") or []
    total_seen = 0
    total_kept_invoices = 0
    total_dup_invoices = 0
    selected_partitions = set()

    for partition in partitions:
        partition_prefix = str(partition.get("partition_prefix") or "").strip()
        selected_metiers = partition.get("selected_metiers") or []
        if not partition_prefix or not selected_metiers:
            continue
        selected_partitions.add(partition_prefix)

        endpoint = f"{COUCHDB_URL}/{quote(source_db, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
        bookmark = None
        seen_invoice_keys = set()

        while True:
            payload = {
                "selector": {"p": "invoice_form"},
                "fields": [
                    "_id",
                    "invoice_number",
                    "invoice_date",
                    "total_gross",
                    "total_net",
                    "document_type",
                    "issuer",
                    "invoice",
                    "data",
                    "line_items",
                ],
                "limit": 500,
            }
            if bookmark:
                payload["bookmark"] = bookmark

            data = post_find(session, endpoint, payload, timeout=120)
            docs = data.get("docs") or []
            if not docs:
                break

            for doc in docs:
                total_seen += 1
                duplicate_key = extract_invoice_duplicate_key(doc)
                if duplicate_key is not None:
                    if duplicate_key in seen_invoice_keys:
                        total_dup_invoices += 1
                        continue
                    seen_invoice_keys.add(duplicate_key)
                total_kept_invoices += 1

                invoice_id = str(doc.get("_id") or "").strip()
                for line in get_line_items(doc):
                    if not isinstance(line, dict):
                        continue
                    description = clean_text(line.get("description"))
                    account = clean_text(line.get("accounting_account"))
                    classification = classify_charge(description, account)
                    if not should_keep_charge(description, account, classification):
                        continue

                    key = normalize_text(description)
                    bucket = counters[key]
                    bucket["label_counter"][description] += 1
                    if invoice_id:
                        bucket["invoice_ids"].add(invoice_id)
                    bucket["partitions"].add(partition_prefix)
                    bucket["account_counter"][account] += 1
                    bucket["line_occurrences"] += 1
                    bucket["sous_profil_counter"][classification["sous_profil"]] += 1
                    bucket["nature_counter"][classification["nature_charge"]] += 1
                    bucket["profil_counter"][classification["profil_facturation"]] += 1
                    bucket["reason_counter"][classification["classification_reason"]] += 1

            next_bookmark = data.get("bookmark")
            if not next_bookmark or next_bookmark == bookmark:
                break
            bookmark = next_bookmark

    rows_all = []
    rows_new = []
    sous_profil_counter = Counter()
    for normalized_label, bucket in counters.items():
        best_label = bucket["label_counter"].most_common(1)[0][0]
        predicted_sous_profil = bucket["sous_profil_counter"].most_common(1)[0][0]
        predicted_nature_charge = bucket["nature_counter"].most_common(1)[0][0]
        predicted_profil_facturation = bucket["profil_counter"].most_common(1)[0][0]
        classification_reason = bucket["reason_counter"].most_common(1)[0][0]
        row = {
            "article_source": best_label,
            "normalized_label": normalized_label,
            "invoice_count": len(bucket["invoice_ids"]),
            "line_occurrences": bucket["line_occurrences"],
            "sample_account": bucket["account_counter"].most_common(1)[0][0],
            "predicted_sous_profil": predicted_sous_profil,
            "predicted_nature_charge": predicted_nature_charge,
            "predicted_profil_facturation": predicted_profil_facturation,
            "classification_reason": classification_reason,
            "already_in_base": normalized_label in existing_base,
            "partitions": sorted(bucket["partitions"]),
        }
        rows_all.append(row)
        sous_profil_counter[predicted_sous_profil] += 1
        if not row["already_in_base"]:
            rows_new.append(row)

    rows_all.sort(key=lambda row: (-row["invoice_count"], -row["line_occurrences"], row["article_source"]))
    rows_new.sort(key=lambda row: (-row["invoice_count"], -row["line_occurrences"], row["article_source"]))

    payload = {
        "metier": "charges_externes",
        "summary": {
            "partitions_count": len(selected_partitions),
            "invoice_forms_seen": total_seen,
            "invoice_forms_kept_after_dedup": total_kept_invoices,
            "invoice_forms_skipped_as_duplicate": total_dup_invoices,
            "base_current_distinct": len(existing_base),
            "cleaned_distinct_article_source": len(rows_all),
            "cleaned_already_in_base": len(rows_all) - len(rows_new),
            "cleaned_new_candidates": len(rows_new),
            "counts_by_sous_profil": dict(sorted(sous_profil_counter.items())),
        },
        "top_all": rows_all[: args.top_n],
        "top_new_to_inject": rows_new[: args.top_n],
    }

    json_path = output_dir / f"charges_externes_top_{args.top_n}_cleaned_candidates.json"
    csv_path = output_dir / f"charges_externes_top_{args.top_n}_cleaned_candidates.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, payload["top_new_to_inject"])
    print(f"[OK] json={json_path}")
    print(f"[OK] csv={csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
