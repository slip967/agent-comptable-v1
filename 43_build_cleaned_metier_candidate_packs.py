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
    "transport",
}

NOISE_LABELS = {
    "article",
    "articles",
    "divers",
    "diverse",
    "diverses",
    "forfait",
    "forfaits",
    "marchandises",
    "prestation",
    "prestations",
    "produit",
    "produits",
    "service",
    "services",
}

BASE_FILES = {
    "boulangerie": "base_produits_boulangerie_v1.json",
    "boucherie": "base_produits_boucherie_v1.json",
    "restaurant": "base_produits_restaurant_v1.json",
    "transport": "base_produits_transport_v1.json",
    "btp": "base_produits_btp_v1.json",
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


def tokenize(value: str):
    return [tok for tok in normalize_text(value).split() if tok and tok not in STOP_WORDS]


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


def is_clean_candidate(description: str, account: str) -> bool:
    if not description or not account:
        return False
    if not str(account).startswith("60"):
        return False

    desc_norm = normalize_text(description)
    if not desc_norm or desc_norm in NOISE_LABELS:
        return False
    if desc_norm.isdigit():
        return False

    alpha_count = sum(1 for ch in desc_norm if ch.isalpha())
    if alpha_count < 4:
        return False

    tokens = set(tokenize(description))
    if not tokens:
        return False
    if tokens & EXTERNAL_LIKE:
        return False
    if len(tokens) == 1 and len(next(iter(tokens))) <= 3:
        return False

    digit_count = sum(1 for ch in desc_norm if ch.isdigit())
    if digit_count > alpha_count * 2 and alpha_count < 8:
        return False

    return True


def load_existing_base_keys(root_dir: Path) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {}
    for metier, file_name in BASE_FILES.items():
        path = root_dir / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        keys = set()
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            key = normalize_text(str(item.get("article_source") or ""))
            if key:
                keys.add(key)
        output[metier] = keys
    return output


def build_candidate_packs(
    session: requests.Session,
    source_db: str,
    selected_partitions: list[dict],
    existing_base_keys: dict[str, set[str]],
) -> dict:
    per_metier = {
        metier: {
            "partitions": set(),
            "invoice_forms_seen": 0,
            "invoice_forms_kept_after_dedup": 0,
            "invoice_forms_skipped_as_duplicate": 0,
            "candidates": defaultdict(
                lambda: {
                    "label_counter": Counter(),
                    "invoice_ids": set(),
                    "partitions": set(),
                    "account_counter": Counter(),
                    "line_occurrences": 0,
                }
            ),
        }
        for metier in BASE_FILES
    }

    for partition in selected_partitions:
        partition_prefix = str(partition.get("partition_prefix") or "").strip()
        metiers = [m for m in (partition.get("selected_metiers") or []) if m in BASE_FILES]
        if not partition_prefix or not metiers:
            continue

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
                for metier in metiers:
                    per_metier[metier]["partitions"].add(partition_prefix)
                    per_metier[metier]["invoice_forms_seen"] += 1

                duplicate_key = extract_invoice_duplicate_key(doc)
                if duplicate_key is not None:
                    if duplicate_key in seen_invoice_keys:
                        for metier in metiers:
                            per_metier[metier]["invoice_forms_skipped_as_duplicate"] += 1
                        continue
                    seen_invoice_keys.add(duplicate_key)

                for metier in metiers:
                    per_metier[metier]["invoice_forms_kept_after_dedup"] += 1

                invoice_id = str(doc.get("_id") or "").strip()
                for line in get_line_items(doc):
                    if not isinstance(line, dict):
                        continue
                    description = clean_text(line.get("description"))
                    account = clean_text(line.get("accounting_account"))
                    if not is_clean_candidate(description, account):
                        continue

                    key = normalize_text(description)
                    for metier in metiers:
                        bucket = per_metier[metier]["candidates"][key]
                        bucket["label_counter"][description] += 1
                        if invoice_id:
                            bucket["invoice_ids"].add(invoice_id)
                        bucket["partitions"].add(partition_prefix)
                        bucket["account_counter"][account] += 1
                        bucket["line_occurrences"] += 1

            next_bookmark = data.get("bookmark")
            if not next_bookmark or next_bookmark == bookmark:
                break
            bookmark = next_bookmark

    output = {"metiers": {}}
    for metier in BASE_FILES:
        existing = existing_base_keys[metier]
        payload = per_metier[metier]
        top_all = []
        top_new = []
        overlap_count = 0

        for normalized_label, bucket in payload["candidates"].items():
            best_label = bucket["label_counter"].most_common(1)[0][0]
            row = {
                "article_source": best_label,
                "normalized_label": normalized_label,
                "invoice_count": len(bucket["invoice_ids"]),
                "line_occurrences": bucket["line_occurrences"],
                "partitions": sorted(bucket["partitions"]),
                "sample_account": bucket["account_counter"].most_common(1)[0][0],
                "already_in_base": normalized_label in existing,
            }
            top_all.append(row)
            if row["already_in_base"]:
                overlap_count += 1
            else:
                top_new.append(row)

        top_all.sort(key=lambda row: (-row["invoice_count"], -row["line_occurrences"], row["article_source"]))
        top_new.sort(key=lambda row: (-row["invoice_count"], -row["line_occurrences"], row["article_source"]))

        output["metiers"][metier] = {
            "partitions_count": len(payload["partitions"]),
            "invoice_forms_seen": payload["invoice_forms_seen"],
            "invoice_forms_kept_after_dedup": payload["invoice_forms_kept_after_dedup"],
            "invoice_forms_skipped_as_duplicate": payload["invoice_forms_skipped_as_duplicate"],
            "base_current_distinct": len(existing),
            "cleaned_distinct_article_source": len(top_all),
            "cleaned_already_in_base": overlap_count,
            "cleaned_new_candidates": len(top_new),
            "rows_all": top_all,
            "rows_new": top_new,
        }

    return output


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
    parser = argparse.ArgumentParser(
        description=(
            "Construit des packs de candidats article_source nettoyes par metier "
            "a partir des partitions retenues dans un rapport dry-run."
        )
    )
    parser.add_argument("--report-json", default="copy_keymanage_metier_docs_report_quality_v3.json")
    parser.add_argument("--source-db", default="")
    parser.add_argument("--output-dir", default="candidate_packs_metier")
    parser.add_argument("--top-n", type=int, default=500)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = (SCRIPT_DIR / args.report_json).resolve()
    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    selected_partitions = report.get("partitions") or []
    source_db = str(args.source_db or report.get("source_db") or "").strip()
    if not source_db:
        raise SystemExit("Missing source_db.")

    output_dir = (SCRIPT_DIR / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_base_keys = load_existing_base_keys(SCRIPT_DIR)
    session = http_session()
    payload = build_candidate_packs(
        session=session,
        source_db=source_db,
        selected_partitions=selected_partitions,
        existing_base_keys=existing_base_keys,
    )

    summary = {
        "generated_from": report_path.name,
        "source_db": source_db,
        "read_only": True,
        "top_n": int(args.top_n),
        "metiers": {},
    }

    for metier, metier_payload in payload["metiers"].items():
        top_all = metier_payload["rows_all"][: args.top_n]
        top_new = metier_payload["rows_new"][: args.top_n]

        json_payload = {
            "metier": metier,
            "summary": {
                "partitions_count": metier_payload["partitions_count"],
                "invoice_forms_seen": metier_payload["invoice_forms_seen"],
                "invoice_forms_kept_after_dedup": metier_payload["invoice_forms_kept_after_dedup"],
                "invoice_forms_skipped_as_duplicate": metier_payload["invoice_forms_skipped_as_duplicate"],
                "base_current_distinct": metier_payload["base_current_distinct"],
                "cleaned_distinct_article_source": metier_payload["cleaned_distinct_article_source"],
                "cleaned_already_in_base": metier_payload["cleaned_already_in_base"],
                "cleaned_new_candidates": metier_payload["cleaned_new_candidates"],
            },
            "top_all": top_all,
            "top_new_to_inject": top_new,
        }

        json_path = output_dir / f"{metier}_top_{args.top_n}_cleaned_candidates.json"
        csv_path = output_dir / f"{metier}_top_{args.top_n}_cleaned_candidates.csv"
        json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(csv_path, top_new)

        summary["metiers"][metier] = json_payload["summary"]

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
