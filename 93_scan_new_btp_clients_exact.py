#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter
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
SUMMARY_JSON = ROOT / "new_btp_clients_exact_candidates_summary.json"
SUMMARY_MD = ROOT / "new_btp_clients_exact_candidates_summary.md"

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

TARGET_CLIENTS = [
    {
        "client": "ASSAINIS",
        "partition": "fr_bd_878523547",
        "ape": "3700Z",
    },
    {
        "client": "MB CONSTRUCTION",
        "partition": "fr_bd_947858304",
        "ape": "4120A",
    },
    {
        "client": "MONDIAL BATIMENT",
        "partition": "fr_bd_889860938",
        "ape": "4120A",
    },
    {
        "client": "TRAVAUX NETTS SARL",
        "partition": "fr_bd_908108012",
        "ape": "4399C",
    },
    {
        "client": "SAFTA MENUISERIE",
        "partition": "fr_bd_938751021",
        "ape": "4332A",
    },
]

ALLOWED_ACCOUNTS = ("601", "6011", "602", "6021", "6022", "604", "605", "6058", "606", "6061", "6062", "6063", "6064", "6068")

REJECT_PATTERNS = (
    r"\btransport\b",
    r"\blocation\b",
    r"\bnettoyage\b",
    r"\baller\b",
    r"\bretour\b",
    r"\bpeage\b",
    r"\bautoroute\b",
    r"\bforfait\b",
    r"\bservice\b",
    r"\bprestation\b",
    r"\beco contribution\b",
    r"\beco-contribution\b",
    r"\bvalobat\b",
    r"\bremise\b",
    r"\bfrais\b",
    r"\bconsignation\b",
)


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


def load_existing_sources() -> tuple[set[str], set[str]]:
    payload = load_json(ROOT / "base_produits_btp_v1.json")
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


def is_candidate(raw_desc: str, account: str) -> bool:
    account = str(account or "").strip()
    if not raw_desc or not account.startswith(ALLOWED_ACCOUNTS):
        return False
    normalized = normalize_text(raw_desc)
    if not normalized:
        return False
    alpha_count = sum(1 for ch in normalized if ch.isalpha())
    if alpha_count < 4:
        return False
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, normalized):
            return False
    return True


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# New BTP Clients Exact Candidates",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `source_db`: `{summary['source_db']}`",
        "",
    ]
    for client in summary["clients"]:
        lines.extend(
            [
                f"## {client['client']}",
                "",
                f"- partition: `{client['partition']}`",
                f"- ape: `{client['ape']}`",
                f"- invoice_forms_seen: `{client['invoice_forms_seen']}`",
                f"- line_items_seen: `{client['line_items_seen']}`",
                f"- exact_new_candidates: `{len(client['candidates'])}`",
                "",
            ]
        )
        for row in client["candidates"][:20]:
            lines.append(
                f"- `{row['article_source']}` | compte=`{row['sample_account']}` | occurrences=`{row['line_occurrences']}` | factures=`{row['invoice_count']}` | deja_couvert_norm=`{row['already_covered_by_normalized']}`"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    session = http_session()
    existing_exact_sources, existing_normalized_sources = load_existing_sources()
    client_summaries: list[dict[str, Any]] = []

    for target in TARGET_CLIENTS:
        counter: dict[str, dict[str, Any]] = {}
        invoice_forms_seen = 0
        line_items_seen = 0

        for doc in iter_find(
            session,
            SOURCE_DB,
            {"p": "invoice_form"},
            fields=["_id", "line_items"],
            partition_prefix=target["partition"],
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
                if not is_candidate(raw_desc, account):
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

        client_summaries.append(
            {
                "client": target["client"],
                "partition": target["partition"],
                "ape": target["ape"],
                "invoice_forms_seen": invoice_forms_seen,
                "line_items_seen": line_items_seen,
                "candidates": rows,
            }
        )

    summary = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "clients": client_summaries,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
