#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
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
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_JSON = ROOT / "probe_user_client_lists_in_db_summary.json"
SUMMARY_MD = ROOT / "probe_user_client_lists_in_db_summary.md"

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

CLIENTS = {
    "restaurant": [
        {"client": "AADHI NAVI (MADRAS KITCHEN)", "siret": "94846718800017"},
        {"client": "COUSCOUS FACTORY", "siret": "93068993000012"},
        {"client": "LES TISANES", "siret": "84960275000010"},
    ],
    "boulangerie": [
        {"client": "BOULANGERIE L'UNIVERS DU PAIN", "siret": "88051787500022"},
        {"client": "la courbevoise", "siret": ""},
    ],
    "boucherie": [
        {"client": "BOUCHERIE DE L'ESPOIR", "siret": "82191329000010"},
        {"client": "BOUCHERIE IFRI", "siret": "89283383100019"},
    ],
    "btp": [
        {"client": "AEF (ARTISAN ENERGIE FRANCE)", "siret": "91483746300019"},
        {"client": "ASSAINIS", "siret": "87852354700015"},
        {"client": "DEM BAT", "siret": "94329774700017"},
        {"client": "IBB INTERMEDIARY BUSINESS BATIMENT", "siret": "981565930"},
        {"client": "IRD BAT", "siret": "87978823000016"},
        {"client": "IRPCH PLOMBERIE", "siret": "95142106400027"},
        {"client": "MB CONSTRUCTION", "siret": "94785830400019"},
        {"client": "MONDIAL BATIMENT", "siret": "88986093800014"},
        {"client": "PRO MRI45 PRO MAINTENANCE RESEAU", "siret": "94287932100019"},
        {"client": "SAFTA MENUISERIE", "siret": "93875102100016"},
        {"client": "TRAVAUX NETTS SARL", "siret": "90810801200018"},
    ],
    "transport_logistique": [
        {"client": "BS INTERNATIONAL TRANSFERT", "siret": "99366962100019"},
        {"client": "DAC EXPRESS", "siret": "92204050600011"},
        {"client": "DELIVERY GREEN", "siret": "93147986900014"},
        {"client": "HELP DELIVERY", "siret": "99114820600014"},
        {"client": "MHB TRANSPORTS", "siret": "98292174400016"},
        {"client": "MMA TRANSPORT", "siret": "95219282100017"},
        {"client": "MS TRANSPORT", "siret": "89085240300033"},
        {"client": "PRIM DEMENAGEMENT", "siret": "90828209800015"},
        {"client": "PROSERVICES AMBULANCES", "siret": "89175650400025"},
        {"client": "RAF TRANS", "siret": "979300076"},
    ],
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def extract_siren(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) >= 9:
        return digits[:9]
    return ""


def load_quality_index() -> dict[str, dict[str, Any]]:
    payload = json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))
    return {
        str(row.get("partition_prefix") or "").strip(): row
        for row in payload.get("partitions", [])
        if str(row.get("partition_prefix") or "").strip()
    }


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


def count_partition_docs(session: requests.Session, partition_prefix: str, selector: dict[str, Any]) -> tuple[int, list[str]]:
    bookmark: str | None = None
    total = 0
    samples: list[str] = []
    path = f"_partition/{quote(partition_prefix, safe='')}/_find"
    while True:
        payload = {
            "selector": selector,
            "fields": ["_id"],
            "limit": 500,
        }
        if bookmark:
            payload["bookmark"] = bookmark
        result = couch_request(session, SOURCE_DB, "POST", path, json=payload)
        docs = result.get("docs") or []
        if not docs:
            break
        total += len(docs)
        for doc in docs:
            doc_id = str(doc.get("_id") or "").strip()
            if doc_id and len(samples) < 3:
                samples.append(doc_id)
        next_bookmark = str(result.get("bookmark") or "").strip()
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark
    return total, samples


def fetch_company_doc(session: requests.Session, siren: str) -> dict[str, Any] | None:
    if not siren:
        return None
    result = couch_request(
        session,
        SOURCE_DB,
        "POST",
        "_find",
        json={
            "selector": {
                "p": "company",
                "siren": siren,
            },
            "limit": 1,
        },
    )
    docs = result.get("docs") or []
    return docs[0] if docs else None


def extract_ape(company_doc: dict[str, Any] | None) -> str:
    if not company_doc:
        return ""
    direct = str(company_doc.get("ape") or company_doc.get("naf") or "").strip()
    if direct:
        return direct
    formality = company_doc.get("formality") or {}
    content = formality.get("content") or {}
    person = content.get("personneMorale") or content.get("personnePhysique") or {}
    etab = person.get("etablissementPrincipal") or {}
    return str(etab.get("codeApe") or "").strip()


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Probe User Client Lists In DB",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `source_db`: `{summary['source_db']}`",
        "",
    ]
    for metier, rows in summary["results"].items():
        lines.append(f"## {metier}")
        lines.append("")
        for row in rows:
            lines.append(
                f"- `{row['client']}` | siren=`{row['siren'] or 'N/A'}` | partition=`{row['partition_prefix'] or 'N/A'}` | invoice_form=`{row['invoice_form_count']}` | entry=`{row['entry_count']}` | report_match=`{row['in_quality_report']}` | ape=`{row['ape']}`"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    session = http_session()
    quality_index = load_quality_index()
    results: dict[str, list[dict[str, Any]]] = {}

    for metier, rows in CLIENTS.items():
        bucket: list[dict[str, Any]] = []
        for row in rows:
            client = row["client"]
            siret = str(row.get("siret") or "").strip()
            siren = extract_siren(siret)
            partition_prefix = f"fr_bd_{siren}" if siren else ""
            quality_row = quality_index.get(partition_prefix, {})
            company_doc = fetch_company_doc(session, siren) if siren else None
            invoice_form_count = 0
            entry_count = 0
            sample_invoice_ids: list[str] = []
            if partition_prefix:
                invoice_form_count, sample_invoice_ids = count_partition_docs(session, partition_prefix, {"p": "invoice_form"})
                entry_count, _ = count_partition_docs(session, partition_prefix, {"p": "entry"})
            bucket.append(
                {
                    "client": client,
                    "siret": siret,
                    "siren": siren,
                    "partition_prefix": partition_prefix,
                    "invoice_form_count": invoice_form_count,
                    "entry_count": entry_count,
                    "sample_invoice_ids": sample_invoice_ids,
                    "in_quality_report": bool(quality_row),
                    "report_selected_metiers": quality_row.get("selected_metiers") or [],
                    "report_inferred_metiers": quality_row.get("inferred_metiers") or [],
                    "report_client_ape": quality_row.get("client_ape") or "",
                    "ape": extract_ape(company_doc) or str(quality_row.get("client_ape") or "").strip(),
                }
            )
        results[metier] = bucket

    summary = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "results": results,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
