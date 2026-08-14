#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
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


ROOT = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SOURCE_DB = "keymanage_accounting"
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_JSON = ROOT / "db_layer_missing_exact_candidates_summary.json"
SUMMARY_MD = ROOT / "db_layer_missing_exact_candidates_summary.md"

TARGETS = {
    "btp": "base_produits_btp_v1.json",
    "boulangerie": "base_produits_boulangerie_v1.json",
    "transport": "base_produits_transport_v1.json",
    "restaurant": "base_produits_restaurant_v1.json",
}

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
    "sans",
    "lot",
    "x",
}

GENERIC_LABELS = {
    "article",
    "articles",
    "divers",
    "diverse",
    "diverses",
    "marchandises",
    "article non specifie",
    "achat non detaille",
    "remise",
    "menu",
    "repas",
}

COMMON_REJECT_PATTERNS = (
    r"^remise\b",
    r"^montant\b",
    r"^total\b",
    r"^tva\b",
    r"^acompte\b",
    r"^reglement\b",
    r"^paiement\b",
    r"^solde\b",
    r"^report\b",
    r"^reliquat\b",
    r"^avoir\b",
    r"^vente\b",
    r"^frais\b",
    r"^contribution\b",
    r"^eco[\s-]*part",
    r"^prestation\b",
    r"^loyer\b",
    r"^eau$",
    r"^gaz$",
)

SERVICE_LIKE_TOKENS = {
    "abonnement",
    "forfait",
    "option",
    "communications",
    "communication",
    "location",
    "mise",
    "travaux",
    "prestation",
    "maintenance",
    "entretien",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def couch_request(session: requests.Session, db_name: str, method: str, path: str = "", **kwargs) -> dict[str, Any]:
    if path:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db_name, safe='')}"
    response = session.request(method, url, timeout=180, **kwargs)
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def iter_find(
    session: requests.Session,
    db_name: str,
    selector: dict[str, Any],
    *,
    fields: list[str] | None = None,
    partition_prefix: str | None = None,
    limit: int = 500,
):
    bookmark: str | None = None
    path = f"_partition/{quote(partition_prefix, safe='')}/_find" if partition_prefix else "_find"
    while True:
        payload: dict[str, Any] = {"selector": selector, "limit": limit}
        if fields:
            payload["fields"] = fields
        if bookmark:
            payload["bookmark"] = bookmark
        result = couch_request(session, db_name, "POST", path, json=payload)
        docs = result.get("docs") or []
        if not docs:
            break
        for doc in docs:
            yield doc
        next_bookmark = str(result.get("bookmark") or "").strip()
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def unique_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if token and token not in STOP_WORDS]


def extract_siren_from_party(party: Any) -> str:
    if not isinstance(party, dict):
        return ""
    direct = str(party.get("siren") or "").strip()
    if direct:
        return direct
    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = str(reg.get("type") or "").strip().upper()
        reg_value = str(reg.get("value") or "").strip()
        if reg_type == "SIREN" and reg_value:
            return reg_value
        if reg_type == "SIRET" and len(reg_value) >= 9:
            return reg_value[:9]
    return ""


def extract_invoice_duplicate_key(doc: dict[str, Any]) -> tuple[str, str, str, str, str] | None:
    supplier_siren = extract_siren_from_party(doc.get("issuer") or {})
    invoice_number = str(doc.get("invoice_number") or "").strip()
    invoice_date = str(doc.get("invoice_date") or "").strip()
    total_gross = doc.get("total_gross")
    total_net = doc.get("total_net")
    total_amount = ""
    for raw in (total_gross, total_net):
        if raw in (None, "", []):
            continue
        try:
            total_amount = f"{float(raw):.2f}"
            break
        except Exception:
            total_amount = str(raw).strip()
            break
    document_type = str(doc.get("document_type") or "").strip().upper()
    if not supplier_siren or not invoice_number or not invoice_date:
        return None
    return (supplier_siren, invoice_number.upper(), invoice_date, total_amount, document_type)


def is_product_like_candidate(description: str, account: str, metier: str) -> bool:
    raw = str(description or "").strip()
    if not raw:
        return False
    normalized = normalize_text(raw)
    if not normalized or normalized in GENERIC_LABELS:
        return False
    if any(re.search(pattern, normalized) for pattern in COMMON_REJECT_PATTERNS):
        return False
    alpha_count = sum(1 for ch in normalized if ch.isalpha())
    if alpha_count < 4:
        return False
    tokens = tokenize(raw)
    if not tokens:
        return False
    if len(tokens) == 1 and len(tokens[0]) <= 3:
        return False
    digit_count = sum(1 for ch in normalized if ch.isdigit())
    if digit_count > alpha_count * 2 and alpha_count < 8:
        return False

    account_value = str(account or "").strip()
    if metier == "transport":
        return account_value.startswith(("60", "61", "62"))
    return account_value.startswith(("60", "61", "62", "607", "615"))


def load_existing_exact_sources() -> dict[str, set[str]]:
    existing: dict[str, set[str]] = {}
    for metier, file_name in TARGETS.items():
        payload = load_json(ROOT / file_name)
        keys: set[str] = set()
        for section in ("items", "a_valider"):
            for item in payload.get(section, []) or []:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("article_source") or "").strip()
                if source:
                    keys.add(source)
        existing[metier] = keys
    return existing


def load_target_partitions() -> dict[str, list[str]]:
    report = load_json(QUALITY_REPORT)
    output: dict[str, list[str]] = defaultdict(list)
    for row in report.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        selected = [str(value or "").strip().lower() for value in (row.get("selected_metiers") or [])]
        if not partition:
            continue
        for metier in TARGETS:
            if metier in selected:
                output[metier].append(partition)
    return dict(output)


def scan_invoice_form_candidates(
    session: requests.Session,
    partitions_by_metier: dict[str, list[str]],
    existing_exact_sources: dict[str, set[str]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    candidates: dict[str, dict[str, dict[str, Any]]] = {metier: {} for metier in TARGETS}
    scan_stats: dict[str, Any] = {}

    for metier, partitions in partitions_by_metier.items():
        seen_invoice_keys: set[Any] = set()
        docs_seen = 0
        docs_kept = 0
        duplicates_skipped = 0
        line_items_seen = 0
        line_items_missing = 0

        for partition in partitions:
            for doc in iter_find(
                session,
                SOURCE_DB,
                {"p": "invoice_form"},
                fields=["_id", "invoice_number", "invoice_date", "total_gross", "total_net", "document_type", "issuer", "line_items"],
                partition_prefix=partition,
                limit=500,
            ):
                docs_seen += 1
                duplicate_key = extract_invoice_duplicate_key(doc)
                if duplicate_key and duplicate_key in seen_invoice_keys:
                    duplicates_skipped += 1
                    continue
                if duplicate_key:
                    seen_invoice_keys.add(duplicate_key)
                docs_kept += 1

                invoice_id = str(doc.get("_id") or "").strip()
                for line in doc.get("line_items") or []:
                    if not isinstance(line, dict):
                        continue
                    line_items_seen += 1
                    raw_desc = str(line.get("description") or "").strip()
                    account = str(line.get("accounting_account") or "").strip()
                    if not is_product_like_candidate(raw_desc, account, metier):
                        continue
                    normalized = normalize_text(raw_desc)
                    if not normalized or raw_desc in existing_exact_sources[metier]:
                        continue
                    bucket = candidates[metier].setdefault(
                        raw_desc,
                        {
                            "raw_source": raw_desc,
                            "normalized": normalized,
                            "account_counter": Counter(),
                            "vat_counter": Counter(),
                            "invoice_ids": [],
                            "partitions": set(),
                            "line_occurrences": 0,
                        },
                    )
                    bucket["line_occurrences"] += 1
                    if account:
                        bucket["account_counter"][account] += 1
                    vat_value = line.get("vat_percent")
                    if vat_value not in (None, "", []):
                        bucket["vat_counter"][str(vat_value)] += 1
                    if invoice_id and invoice_id not in bucket["invoice_ids"] and len(bucket["invoice_ids"]) < 3:
                        bucket["invoice_ids"].append(invoice_id)
                    bucket["partitions"].add(partition)
                    line_items_missing += 1

        scan_stats[metier] = {
            "partitions": partitions,
            "invoice_forms_seen": docs_seen,
            "invoice_forms_kept_after_dedup": docs_kept,
            "invoice_forms_skipped_as_duplicate": duplicates_skipped,
            "line_items_seen": line_items_seen,
            "missing_candidate_hits": line_items_missing,
        }

    final: dict[str, list[dict[str, Any]]] = {}
    for metier, buckets in candidates.items():
        rows: list[dict[str, Any]] = []
        for payload in buckets.values():
            account_counter: Counter = payload["account_counter"]
            vat_counter: Counter = payload["vat_counter"]
            raw_source = payload["raw_source"]
            tokens = set(tokenize(raw_source))
            rows.append(
                {
                    "article_source": raw_source,
                    "article_canonique": payload["normalized"],
                    "invoice_count": len(payload["invoice_ids"]),
                    "line_occurrences": payload["line_occurrences"],
                    "sample_account": account_counter.most_common(1)[0][0] if account_counter else "",
                    "sample_vat": vat_counter.most_common(1)[0][0] if vat_counter else "",
                    "source_invoice_ids": payload["invoice_ids"],
                    "partitions_sources": sorted(payload["partitions"]),
                    "service_like": bool(tokens & SERVICE_LIKE_TOKENS) and metier != "transport",
                }
            )
        rows.sort(
            key=lambda row: (
                row["service_like"],
                -int(row["line_occurrences"]),
                -int(row["invoice_count"]),
                row["article_source"],
            )
        )
        final[metier] = rows
    return final, scan_stats


def scan_entry_layer(session: requests.Session, partitions_by_metier: dict[str, list[str]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for metier, partitions in partitions_by_metier.items():
        top_labels: Counter = Counter()
        docs_seen = 0
        for partition in partitions:
            for doc in iter_find(
                session,
                SOURCE_DB,
                {"p": "entry"},
                fields=["label", "account_number"],
                partition_prefix=partition,
                limit=500,
            ):
                docs_seen += 1
                label = str(doc.get("label") or "").strip()
                account_number = str(doc.get("account_number") or "").strip()
                if label and account_number.startswith(("60", "61", "62", "607")):
                    top_labels[f"{account_number} | {label}"] += 1
        summary[metier] = {
            "docs_seen": docs_seen,
            "top_product_like_labels": [{"label": label, "count": count} for label, count in top_labels.most_common(10)],
        }
    return summary


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# DB Layer Missing Exact Candidates",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `source_db`: `{summary['source_db']}`",
        "",
        "## Entry Layer Note",
        "",
        "Les `entry` ont ete controles a part. Ils remontent surtout des libelles de contrepartie / fournisseur, pas des vraies lignes article exploitables comme `article_source`.",
        "",
    ]
    for metier in TARGETS:
        rows = summary["invoice_form_candidates"].get(metier, [])
        stats = summary["invoice_form_scan_stats"].get(metier, {})
        entry = summary["entry_layer_check"].get(metier, {})
        lines.extend(
            [
                f"## {metier}",
                "",
                f"- partitions: `{stats.get('partitions', [])}`",
                f"- invoice_forms_seen: `{stats.get('invoice_forms_seen', 0)}`",
                f"- invoice_forms_kept_after_dedup: `{stats.get('invoice_forms_kept_after_dedup', 0)}`",
                f"- duplicates_skipped: `{stats.get('invoice_forms_skipped_as_duplicate', 0)}`",
                f"- missing_exact_candidates: `{len(rows)}`",
                f"- entry_docs_seen: `{entry.get('docs_seen', 0)}`",
                "",
            ]
        )
        if entry.get("top_product_like_labels"):
            lines.append("Top `entry.label` observes:")
            for row in entry["top_product_like_labels"][:5]:
                lines.append(f"- `{row['label']}` -> `{row['count']}`")
            lines.append("")
        if not rows:
            lines.append("Aucun nouveau candidat exact propre detecte.\n")
            continue
        lines.append("Top candidats absents des `V1` strictes:")
        for row in rows[:15]:
            lines.append(
                f"- `{row['article_source']}` | compte=`{row['sample_account']}` | hits=`{row['line_occurrences']}` | factures=`{row['invoice_count']}` | service_like=`{row['service_like']}`"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    session = http_session()
    existing_exact_sources = load_existing_exact_sources()
    partitions_by_metier = load_target_partitions()
    invoice_form_candidates, invoice_form_scan_stats = scan_invoice_form_candidates(session, partitions_by_metier, existing_exact_sources)
    entry_layer_check = scan_entry_layer(session, partitions_by_metier)

    summary = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "invoice_form_scan_stats": invoice_form_scan_stats,
        "invoice_form_candidates": invoice_form_candidates,
        "entry_layer_check": entry_layer_check,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
