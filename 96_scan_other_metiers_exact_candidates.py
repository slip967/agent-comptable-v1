#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import unicodedata
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
SOURCE_DB = "keymanage_accounting"
SUMMARY_JSON = ROOT / "other_metiers_exact_candidates_summary.json"
SUMMARY_MD = ROOT / "other_metiers_exact_candidates_summary.md"

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

CONFIGS = {
    "boulangerie": {
        "base_file": ROOT / "base_produits_boulangerie_v1.json",
        "allowed_accounts": ("601", "6011", "6012", "6025", "6061", "6063", "6068", "607"),
        "reject_patterns": (
            r"\babonnement\b",
            r"\badblue\b",
            r"\bavoir\b",
            r"\bbase vie\b",
            r"\bcabine\b",
            r"\bcarburant\b",
            r"\bcloud\b",
            r"\bdiesel\b",
            r"\beau\b",
            r"\belectricite\b",
            r"\bfrais\b",
            r"\bforfait\b",
            r"\bgazole\b",
            r"\bgprs\b",
            r"\bgaz\b",
            r"\blivraison\b",
            r"\blocation\b",
            r"\bmcs\b",
            r"\bnettoyage\b",
            r"\boperateur\b",
            r"\bpeage\b",
            r"\bprestation\b",
            r"\bservice\b",
            r"\bsim\b",
            r"\btransport\b",
            r"\bwc\b",
        ),
        "targets": [
            {"client": "fr_bd_880517875", "partition": "fr_bd_880517875", "ape": "1071C"},
            {"client": "fr_bd_890233000", "partition": "fr_bd_890233000", "ape": "1071C"},
            {"client": "fr_bd_915197842", "partition": "fr_bd_915197842", "ape": "1071C"},
            {"client": "fr_bd_519665103", "partition": "fr_bd_519665103", "ape": "4722Z"},
        ],
    },
    "restaurant": {
        "base_file": ROOT / "base_produits_restaurant_v1.json",
        "allowed_accounts": ("601", "6011", "6012", "6061", "6062", "6063", "6068", "607"),
        "reject_patterns": (
            r"\babonnement\b",
            r"\badblue\b",
            r"\bavoir\b",
            r"\bbase vie\b",
            r"\bcabine\b",
            r"\bcarburant\b",
            r"\bcloud\b",
            r"\bdiesel\b",
            r"\beau\b",
            r"\belectricite\b",
            r"\bfrais\b",
            r"\bforfait\b",
            r"\bgazole\b",
            r"\bgprs\b",
            r"\bgaz\b",
            r"\blocation\b",
            r"\bmcs\b",
            r"\bnettoyage\b",
            r"\boperateur\b",
            r"\bpeage\b",
            r"\bprestation\b",
            r"\bservice\b",
            r"\bsim\b",
            r"\bwc\b",
        ),
        "targets": [
            {"client": "fr_bd_891370595", "partition": "fr_bd_891370595", "ape": "5610C"},
            {"client": "fr_bd_952061570", "partition": "fr_bd_952061570", "ape": "5610A"},
            {"client": "fr_bd_929728467", "partition": "fr_bd_929728467", "ape": "5610C"},
            {"client": "LES TISANES", "partition": "fr_bd_849602750", "ape": "4778C"},
        ],
    },
    "transport": {
        "base_file": ROOT / "base_produits_transport_v1.json",
        "allowed_accounts": ("6061", "6062", "6063", "6068", "607", "615", "626", "6261"),
        "reject_patterns": (
            r"\bavoir\b",
            r"\beco part\b",
            r"\beco-part\b",
            r"\bfrais de port\b",
            r"\bremise\b",
            r"\bconsignation\b",
            r"\bvalobat\b",
        ),
        "targets": [
            {"client": "fr_bd_839181104", "partition": "fr_bd_839181104", "ape": "4932Z"},
            {"client": "fr_bd_888020088", "partition": "fr_bd_888020088", "ape": "4932Z"},
            {"client": "fr_bd_831060876", "partition": "fr_bd_831060876", "ape": "4932Z"},
            {"client": "fr_bd_890852403", "partition": "fr_bd_890852403", "ape": "4941A"},
            {"client": "fr_bd_904094349", "partition": "fr_bd_904094349", "ape": "4941B"},
            {"client": "fr_bd_922040506", "partition": "fr_bd_922040506", "ape": "4932Z"},
            {"client": "fr_bd_844082156", "partition": "fr_bd_844082156", "ape": "4932Z"},
            {"client": "fr_bd_840367817", "partition": "fr_bd_840367817", "ape": "4932Z"},
            {"client": "fr_bd_979300076", "partition": "fr_bd_979300076", "ape": "4932Z"},
            {"client": "fr_bd_950819938", "partition": "fr_bd_950819938", "ape": "4941B"},
            {"client": "DELIVERY GREEN", "partition": "fr_bd_931479869", "ape": "4941A"},
            {"client": "MHB TRANSPORTS", "partition": "fr_bd_982921744", "ape": "4932Z"},
            {"client": "MS TRANSPORT", "partition": "fr_bd_890852403", "ape": "4941A"},
            {"client": "PRIM DEMENAGEMENT", "partition": "fr_bd_908282098", "ape": "4942Z"},
            {"client": "BS INTERNATIONAL TRANSFERT", "partition": "fr_bd_993669621", "ape": "4932Z"},
            {"client": "HELP DELIVERY", "partition": "fr_bd_991148206", "ape": "4941A"},
        ],
    },
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
    url = f"{COUCHDB_URL}/{quote(db_name, safe='')}"
    if path:
        url = f"{url}/{path}"
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


def unwrap_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return unwrap_value(value.get("value"))
    return value


def load_existing_sources(base_file: Path) -> tuple[set[str], set[str]]:
    payload = load_json(base_file)
    exact_sources: set[str] = set()
    normalized_sources: set[str] = set()
    for section in ("items", "a_valider"):
        for item in payload.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            source = str(item.get("article_source") or "").strip()
            canonical = str(item.get("article_canonique") or "").strip()
            if source:
                exact_sources.add(source)
                normalized_sources.add(normalize_text(source))
            if canonical:
                normalized_sources.add(normalize_text(canonical))
    return exact_sources, normalized_sources


def is_candidate(raw_desc: str, account: str, *, allowed_accounts: tuple[str, ...], reject_patterns: tuple[str, ...]) -> bool:
    account = str(account or "").strip()
    if not raw_desc or not any(account.startswith(prefix) for prefix in allowed_accounts):
        return False
    normalized = normalize_text(raw_desc)
    if not normalized:
        return False
    alpha_count = sum(1 for ch in normalized if ch.isalpha())
    if alpha_count < 4:
        return False
    if len(normalized.split()) == 1 and len(normalized) < 5:
        return False
    for pattern in reject_patterns:
        if re.search(pattern, normalized):
            return False
    return True


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Other Metiers Exact Candidates",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `source_db`: `{summary['source_db']}`",
        "",
    ]
    for metier, payload in summary["metiers"].items():
        lines.extend(
            [
                f"## {metier}",
                "",
                f"- current_items: `{payload['current_items']}`",
                f"- target_items: `{payload['target_items']}`",
                f"- needed: `{payload['needed']}`",
                f"- candidates_total: `{payload['candidates_total']}`",
                "",
            ]
        )
        for row in payload["top_candidates"][:40]:
            lines.append(
                f"- `{row['article_source']}` | compte=`{row['sample_account']}` | occurrences=`{row['line_occurrences']}` | factures=`{row['invoice_count']}` | client=`{row['client']}`"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    session = http_session()
    metier_summaries: dict[str, Any] = {}

    for metier, config in CONFIGS.items():
        existing_exact_sources, existing_normalized_sources = load_existing_sources(config["base_file"])
        current_payload = load_json(config["base_file"])
        current_items = len(current_payload.get("items") or [])
        counter: dict[str, dict[str, Any]] = {}
        invoice_forms_seen = 0
        line_items_seen = 0

        for target in config["targets"]:
            partition = str(target["partition"] or "").strip()
            if not partition:
                continue
            for doc in iter_find(
                session,
                SOURCE_DB,
                {"p": "invoice_form"},
                fields=["_id", "line_items"],
                partition_prefix=partition,
                limit=500,
            ):
                invoice_forms_seen += 1
                invoice_id = str(doc.get("_id") or "").strip()
                for line in doc.get("line_items") or []:
                    if not isinstance(line, dict):
                        continue
                    line_items_seen += 1
                    raw_desc = str(unwrap_value(line.get("description")) or "").strip()
                    account = str(unwrap_value(line.get("accounting_account")) or "").strip()
                    vat = unwrap_value(line.get("vat_percent"))
                    if not is_candidate(
                        raw_desc,
                        account,
                        allowed_accounts=config["allowed_accounts"],
                        reject_patterns=config["reject_patterns"],
                    ):
                        continue
                    if raw_desc in existing_exact_sources:
                        continue
                    bucket = counter.setdefault(
                        raw_desc,
                        {
                            "article_source": raw_desc,
                            "article_canonique": normalize_text(raw_desc),
                            "sample_account": account,
                            "sample_vat": vat,
                            "line_occurrences": 0,
                            "invoice_ids": [],
                            "client": str(target["client"] or "").strip(),
                            "partition": partition,
                            "ape": str(target["ape"] or "").strip(),
                        },
                    )
                    bucket["line_occurrences"] += 1
                    if invoice_id and invoice_id not in bucket["invoice_ids"] and len(bucket["invoice_ids"]) < 3:
                        bucket["invoice_ids"].append(invoice_id)

        rows: list[dict[str, Any]] = []
        for payload in counter.values():
            rows.append(
                {
                    "article_source": payload["article_source"],
                    "article_canonique": payload["article_canonique"],
                    "sample_account": payload["sample_account"],
                    "sample_vat": payload["sample_vat"],
                    "line_occurrences": payload["line_occurrences"],
                    "invoice_count": len(payload["invoice_ids"]),
                    "source_invoice_ids": payload["invoice_ids"],
                    "already_covered_by_normalized": payload["article_canonique"] in existing_normalized_sources,
                    "client": payload["client"],
                    "partition": payload["partition"],
                    "ape": payload["ape"],
                }
            )

        rows.sort(
            key=lambda row: (
                row["already_covered_by_normalized"],
                -int(row["line_occurrences"]),
                -int(row["invoice_count"]),
                row["article_source"],
            )
        )

        metier_summaries[metier] = {
            "current_items": current_items,
            "target_items": 200,
            "needed": max(0, 200 - current_items),
            "invoice_forms_seen": invoice_forms_seen,
            "line_items_seen": line_items_seen,
            "candidates_total": len(rows),
            "top_candidates": rows[:250],
            "all_candidates": rows,
        }

    summary = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "metiers": metier_summaries,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
