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
SUMMARY_JSON = ROOT / "new_btp_clients_exact_candidates_summary.json"
SUMMARY_MD = ROOT / "integrate_btp_shortlist_exact_summary.md"
SUMMARY_REPORT_JSON = ROOT / "integrate_btp_shortlist_exact_summary.json"
TARGET_FILES = [
    ROOT / "base_produits_btp_v1.json",
    ROOT / "base_produits_btp_v1_with_accounts.json",
]

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

SHORTLIST = {
    "MB CONSTRUCTION": [
        "MOYEN SACHET VISSERIE",
        "SEAU DOSEUR 12 LITRES",
        "ULTABOND ECO V4SP SEAU14KG",
        "BACHE FEUTRE 1X10M",
        "BOUCHON D40",
        "PLAN TRAV BASIC BLANC 200X60X2.8 1PX",
        "5 GANTS TVX GRIS SITE",
        "CABLE U1000R2V 3G2.5MM2 5M",
        "CABLE ACIER BRUT D1MM L5M STANDERS",
        "CASQUE DE CHANTIER QUARTZUP BLANC DELTA",
    ],
    "MONDIAL BATIMENT": [
        "1PX COLLE CARREAUX PLATRE BLANC 25 KG",
        "RAIL NF 48/28 3M ISOLPRO",
        "CORNIERE ANGLE PERFO GALVA 2.5M ISOLPRO",
        "EVAC MANCHON FF 40",
        "PROTEGE ANGLE CARREAUX PLATRE 2.5M",
        "500 CROISILLONS A SCELLER 2 MM",
        "ENDUIT GARNISSANT PDR 25KG PRESTONETT",
        "ENDUIT LISSAGE F PDRE PRESTONETT 25KG",
        "KERAFIX EXTRA GRIS 25KG MAPEI",
        "MANCHON FF D32",
    ],
    "SAFTA MENUISERIE": [
        "100 CHEVILLES DUOPOWER 8X40MM DIY",
        "MASQ SURF DELIC DEXTER PRO ROSE 25MMX25M",
        "MASQUAGE DROIT DEXTER 48MMX50M",
        "1PX MARTEAU DE MENUISIER BOIS 25 MM",
        "20 VIS TF CONS.BOIS TX 8X100 AB SPAX/XL",
        "24 VIS TFB TX 6X100 A.TREM WIROX SPAX HF",
        "BOITE A ONGLET PLASTIQUE + SCIE A DOS",
        "COFFRET 12 FRAISES AFFLEUREUSES TIVOLY",
    ],
}

ACCOUNT_MAP = {
    "601000": "601",
    "601100": "6011",
    "60110000": "6011",
    "602100": "6021",
    "60210000": "6021",
    "602200": "6022",
    "60220000": "6022",
    "604000": "604",
    "605000": "605",
    "605800": "6058",
    "606": "606",
    "606100": "6061",
    "60610000": "6061",
    "606110": "6061",
    "6062": "6062",
    "606200": "6062",
    "60620000": "6062",
    "6063": "6063",
    "606300": "6063",
    "60630000": "6063",
    "6064": "6064",
    "606400": "6064",
    "6068": "6068",
    "606800": "6068",
    "607000": "607",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize_keywords(*values: str) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        for token in normalize_text(value).split():
            if not token or token in seen:
                continue
            seen.add(token)
            output.append(token)
    return output[:12]


def normalize_account(account: str) -> str:
    account = str(account or "").strip()
    return ACCOUNT_MAP.get(account, account)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def fetch_invoice_paths(session: requests.Session, source_ids: list[str]) -> dict[str, str]:
    invoice_to_core: dict[str, str] = {}
    for start in range(0, len(source_ids), 200):
        chunk = source_ids[start : start + 200]
        result = couch_request(session, SOURCE_DB, "POST", "_all_docs?include_docs=true", json={"keys": chunk})
        for row in result.get("rows", []):
            doc = row.get("doc") or {}
            if str(doc.get("p") or "").strip() != "invoice_form":
                continue
            invoice_id = str(row.get("id") or "").strip()
            core_id = str(((doc.get("form_common_core_ref") or {}).get("id")) or "").strip()
            if invoice_id and core_id:
                invoice_to_core[invoice_id] = core_id

    core_to_path: dict[str, str] = {}
    core_ids = list(dict.fromkeys(invoice_to_core.values()))
    for start in range(0, len(core_ids), 200):
        chunk = core_ids[start : start + 200]
        result = couch_request(session, SOURCE_DB, "POST", "_all_docs?include_docs=true", json={"keys": chunk})
        for row in result.get("rows", []):
            doc = row.get("doc") or {}
            form_common_core = doc.get("form_common_core") or {}
            ingest = form_common_core.get("ingest") or {}
            file_node = form_common_core.get("file") or {}
            path_value = str(ingest.get("path") or "").strip() or str(file_node.get("file_name") or "").strip()
            core_id = str(row.get("id") or "").strip()
            if core_id and path_value:
                core_to_path[core_id] = path_value

    return {
        invoice_id: core_to_path[core_id]
        for invoice_id, core_id in invoice_to_core.items()
        if core_id in core_to_path
    }


def guess_sub_category(account: str, article_source: str) -> str:
    normalized = normalize_text(article_source)
    if any(token in normalized for token in ("vis", "cheville", "bouchon", "manchon", "corniere", "rail", "cable", "croisillons")):
        return "quincaillerie"
    if any(token in normalized for token in ("colle", "enduit", "kerafix")):
        return "matiere_premiere"
    if any(token in normalized for token in ("marteau", "coffret", "scie")):
        return "outillage"
    if any(token in normalized for token in ("gants", "casque")):
        return "equipement_chantier"
    if any(token in normalized for token in ("bache", "masq", "masquage", "seau")):
        return "consommable_chantier"
    if str(account).startswith(("601", "602", "607")):
        return "matiere_premiere"
    return "consommable_chantier"


def build_item(candidate: dict[str, Any], *, partition: str, ape: str, invoice_path_by_id: dict[str, str]) -> dict[str, Any]:
    source_ids = [str(value or "").strip() for value in (candidate.get("source_invoice_ids") or []) if str(value or "").strip()][:3]
    article_source = str(candidate.get("article_source") or "").strip()
    compte = normalize_account(str(candidate.get("sample_account") or "").strip())
    invoice_paths = []
    for source_id in source_ids:
        path = invoice_path_by_id.get(source_id, "")
        if path and path not in invoice_paths:
            invoice_paths.append(path)
    item = {
        "article_source": article_source,
        "article_canonique": normalize_text(article_source),
        "mots_cles": tokenize_keywords(article_source),
        "ids_factures_sources": source_ids,
        "source_invoice_ids": source_ids,
        "invoice_paths_sources": invoice_paths[:3],
        "ape_context": [ape] if ape else [],
        "partitions_sources": [partition] if partition else [],
        "compte_comptable": compte,
        "taux_tva": candidate.get("sample_vat"),
        "categorie": "exploitation_metier",
        "sous_categorie": guess_sub_category(compte, article_source),
        "type_fournisseur": "fournisseur_materiaux",
    }
    return item


def main() -> None:
    summary = load_json(SUMMARY_JSON)
    session = http_session()

    wanted: dict[tuple[str, str], dict[str, Any]] = {}
    all_source_ids: list[str] = []
    for client in summary.get("clients", []):
        client_name = str(client.get("client") or "").strip()
        shortlist = SHORTLIST.get(client_name) or []
        if not shortlist:
            continue
        candidate_map = {
            str(row.get("article_source") or "").strip(): row
            for row in (client.get("candidates") or [])
            if isinstance(row, dict)
        }
        for article_source in shortlist:
            row = candidate_map.get(article_source)
            if row is None:
                continue
            wanted[(client_name, article_source)] = {
                "partition": str(client.get("partition") or "").strip(),
                "ape": str(client.get("ape") or "").strip(),
                "candidate": row,
            }
            all_source_ids.extend(row.get("source_invoice_ids") or [])

    invoice_path_by_id = fetch_invoice_paths(session, list(dict.fromkeys(all_source_ids)))
    integrated_count_by_file: dict[str, int] = {}
    skipped_existing_by_file: dict[str, int] = {}
    added_labels: list[str] = []

    for path in TARGET_FILES:
        payload = load_json(path)
        existing_norm = {
            normalize_text(str(item.get("article_source") or ""))
            for section in ("items", "a_valider")
            for item in (payload.get(section) or [])
            if isinstance(item, dict)
        }
        added = 0
        skipped = 0
        for _, payload_row in wanted.items():
            item = build_item(
                payload_row["candidate"],
                partition=payload_row["partition"],
                ape=payload_row["ape"],
                invoice_path_by_id=invoice_path_by_id,
            )
            key = normalize_text(item["article_source"])
            if not key or key in existing_norm:
                skipped += 1
                continue
            payload.setdefault("items", []).append(item)
            existing_norm.add(key)
            added += 1
            if path.name == "base_produits_btp_v1.json":
                added_labels.append(item["article_source"])

        payload.setdefault("meta", {})
        payload["meta"]["items_count"] = len(payload.get("items") or [])
        payload["meta"]["generated_at"] = payload["meta"].get("generated_at") or now_iso()
        payload["meta"]["updated"] = now_iso()
        payload["meta"]["selector"] = (
            "strict_exact_only + manual_btp_shortlist_from_user_clients: exact invoice_form line_items.description from keymanage_accounting"
        )
        dump_json(path, payload)
        integrated_count_by_file[path.name] = added
        skipped_existing_by_file[path.name] = skipped

    report = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "shortlist_requested": sum(len(values) for values in SHORTLIST.values()),
        "shortlist_found": len(wanted),
        "files": [
            {
                "file": path.name,
                "added": integrated_count_by_file[path.name],
                "skipped_existing": skipped_existing_by_file[path.name],
            }
            for path in TARGET_FILES
        ],
        "added_labels": added_labels,
    }
    SUMMARY_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Integrate BTP Shortlist Exact Summary",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `shortlist_requested`: `{report['shortlist_requested']}`",
        f"- `shortlist_found`: `{report['shortlist_found']}`",
    ]
    for row in report["files"]:
        lines.append(f"- {row['file']}: added=`{row['added']}` skipped_existing=`{row['skipped_existing']}`")
    lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_REPORT_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
