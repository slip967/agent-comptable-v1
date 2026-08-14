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
SCAN_SUMMARY_JSON = ROOT / "other_metiers_exact_candidates_summary.json"
SUMMARY_MD = ROOT / "expand_other_metiers_to_200_exact_summary.md"
SUMMARY_REPORT_JSON = ROOT / "expand_other_metiers_to_200_exact_summary.json"

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

TARGET_TOTAL = 200

CONFIGS = {
    "boulangerie": {
        "target_files": [
            ROOT / "base_produits_boulangerie_v1.json",
            ROOT / "base_produits_boulangerie_v1_with_accounts.json",
        ],
        "exclude_partitions": {"fr_bd_519665103"},
        "negative_patterns": (
            r"\b0xena\b",
            r"\bcontribution tarifaire\b",
            r"\bacheminement\b",
            r"\bbombe graisse\b",
            r"\bdecro\b",
            r"\bdexter\b",
            r"\bfacture client\b",
            r"\bjavel\b",
            r"\blingette\b",
            r"\bliq vaiss\b",
            r"\bmagnetiques\b",
            r"\boutil\b",
            r"\bserrage\b",
            r"\bvente\b",
            r"\bvolaille\b",
            r"\bveau\b",
            r"\bagneau\b",
            r"\bhalal\b",
            r"\bboucherie\b",
            r"\bboeuf\b",
            r"\bdinde\b",
            r"\bpoulet\b",
            r"\bfoie\b",
            r"\bwings\b",
            r"\bspicy\b",
            r"\bnasrya\b",
            r"\bsortie volaille\b",
        ),
        "packaging_tokens": (
            "boite",
            "bte",
            "cart",
            "cagette",
            "couv",
            "feuille",
            "gobelet",
            "papier",
            "pot",
            "sac",
            "sachet",
            "serv",
        ),
        "type_fournisseur_default": "fournisseur alimentaire",
    },
    "restaurant": {
        "target_files": [
            ROOT / "base_produits_restaurant_v1.json",
            ROOT / "base_produits_restaurant_v1_with_accounts.json",
        ],
        "exclude_partitions": set(),
        "negative_patterns": (
            r"\bboucherie\b",
            r"\bcta\b",
            r"\bc divers\b",
            r"\bc diuers\b",
            r"\bdivers\b",
            r"\bspotify\b",
            r"\bmontant net facturable\b",
            r"\bmontant total de la commande\b",
            r"\boption anti spam\b",
            r"\boption energie verte\b",
            r"\btaxes locales\b",
            r"\bacheminement\b",
            r"\bdeliveroo\b",
            r"\bservice\b",
            r"\boperateur\b",
            r"\bsim\b",
            r"\binternet\b",
            r"\bbox\b",
            r"\bnorton\b",
            r"\bsmartphone\b",
            r"\bsortie volaille\b",
            r"\barticle non specifie\b",
        ),
        "packaging_tokens": (
            "barquette",
            "boite",
            "bte",
            "bol",
            "couv",
            "gobelet",
            "kraft",
            "mpro",
            "papier",
            "pot",
            "rpet",
            "sac",
            "salade",
            "serv",
        ),
        "drink_tokens": (
            "coca",
            "cocacola",
            "cristaline",
            "evian",
            "granini",
            "oasis",
            "orangina",
            "perrier",
            "san pell",
            "scheppes",
            "schweppes",
        ),
        "type_fournisseur_default": "fournisseur alimentaire",
    },
    "transport": {
        "target_files": [
            ROOT / "base_produits_transport_v1.json",
            ROOT / "base_produits_transport_v1_with_accounts.json",
        ],
        "exclude_partitions": set(),
        "positive_patterns": (
            r"\badblue\b",
            r"\bavantage internet\b",
            r"\bavantage client box\b",
            r"\bbox\b",
            r"\bb you\b",
            r"\bbatterie\b",
            r"\bcarburant\b",
            r"\bcode lavage\b",
            r"\bcontrole\b",
            r"\bcredit lavage\b",
            r"\bdiesel\b",
            r"\bforfait\b",
            r"\bgasoil\b",
            r"\bgazole\b",
            r"\bgo\b",
            r"\bhuile\b",
            r"\binternet\b",
            r"\blavage\b",
            r"\bmms\b",
            r"\bnorton\b",
            r"\boption\b",
            r"\bpack securite\b",
            r"\bpneu\b",
            r"\bpompe\b",
            r"\bred\b",
            r"\bsms\b",
            r"\bsmartphone\b",
            r"\buber\b",
            r"\bvidange\b",
            r"\boperateur\b",
        ),
        "negative_patterns": (
            r"\bachat non detaille\b",
            r"\barticle non specifie\b",
            r"\bbanane\b",
            r"\bbaguette\b",
            r"\bboisson\b",
            r"\bcoca\b",
            r"\bchicken\b",
            r"\bdechets\b",
            r"\bdessert\b",
            r"\bdivers\b",
            r"\beau\b",
            r"\bessai sur route\b",
            r"\bfrites\b",
            r"\bhuile tourn\b",
            r"\boasis\b",
            r"\bpizza\b",
            r"\brejet de prelevement\b",
            r"\brepas\b",
            r"\bsandwich\b",
            r"\btest rapide\b",
            r"\byaourt\b",
        ),
        "telecom_tokens": (
            "box",
            "forfait",
            "internet",
            "norton",
            "option",
            "operateur",
            "red",
            "smartphone",
        ),
        "sms_tokens": (
            "sms",
            "mms",
        ),
        "maintenance_tokens": (
            "batterie",
            "controle",
            "courroie",
            "disques",
            "frein",
            "lavage",
            "liquide de refroidissement",
            "montage",
            "plaquette",
            "pneu",
            "reparation",
            "vidange",
        ),
        "fuel_tokens": (
            "adblue",
            "carburant",
            "diesel",
            "e85",
            "gasoil",
            "gazole",
            "go",
            "huile",
            "sp98",
            "spb98",
            "supreme",
        ),
        "type_fournisseur_default": "service_transport",
    },
}

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
    "6012": "6012",
    "6025": "6025",
    "606100": "6061",
    "60610000": "6061",
    "60611": "6061",
    "606110": "6061",
    "6062": "6062",
    "606200": "6062",
    "60620000": "6062",
    "6063": "6063",
    "606300": "6063",
    "60630000": "6063",
    "60631": "6063",
    "6068": "6068",
    "606800": "6068",
    "607000": "607",
    "6071": "607",
    "607100": "607",
    "615000": "615",
    "6155": "615",
    "615500": "615",
    "6261": "6261",
    "626": "626",
    "60610000": "6061",
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_account(account: str) -> str:
    account = str(account or "").strip()
    return ACCOUNT_MAP.get(account, account)


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


def candidate_allowed(metier: str, row: dict[str, Any]) -> bool:
    config = CONFIGS[metier]
    normalized = normalize_text(str(row.get("article_source") or ""))
    if not normalized:
        return False
    if str(row.get("partition") or "").strip() in config.get("exclude_partitions", set()):
        return False
    for pattern in config.get("negative_patterns", ()):
        if re.search(pattern, normalized):
            return False
    if metier == "transport":
        if not any(re.search(pattern, normalized) for pattern in config.get("positive_patterns", ())):
            return False
    if len(normalized.split()) == 1 and len(normalized) < 5:
        return False
    return True


def infer_packaging(metier: str, normalized: str) -> bool:
    return any(token in normalized for token in CONFIGS[metier].get("packaging_tokens", ()))


def normalize_account_for_metier(metier: str, article_source: str, sample_account: str) -> str:
    normalized = normalize_text(article_source)
    sample = normalize_account(sample_account)
    if metier == "restaurant":
        if any(token in normalized for token in CONFIGS[metier]["drink_tokens"]):
            return "607"
        return sample
    if metier == "transport":
        if any(token in normalized for token in CONFIGS[metier]["maintenance_tokens"]):
            return "615"
        if any(token in normalized for token in CONFIGS[metier]["sms_tokens"]):
            return "626"
        if any(token in normalized for token in CONFIGS[metier]["telecom_tokens"]):
            return "6261"
        if any(token in normalized for token in CONFIGS[metier]["fuel_tokens"]):
            return "6063"
        return sample
    return sample


def build_item(metier: str, row: dict[str, Any], invoice_path_by_id: dict[str, str]) -> dict[str, Any]:
    article_source = str(row.get("article_source") or "").strip()
    normalized = normalize_text(article_source)
    source_ids = [str(value or "").strip() for value in (row.get("source_invoice_ids") or []) if str(value or "").strip()][:3]
    invoice_paths = []
    for source_id in source_ids:
        path = invoice_path_by_id.get(source_id, "")
        if path and path not in invoice_paths:
            invoice_paths.append(path)

    packaging = infer_packaging(metier, normalized)
    compte = normalize_account_for_metier(metier, article_source, str(row.get("sample_account") or "").strip())
    sous_categorie = "emballage" if packaging else "matiere_premiere"

    if metier == "restaurant":
        type_fournisseur = "consommables" if packaging else "fournisseur alimentaire"
    else:
        type_fournisseur = CONFIGS[metier]["type_fournisseur_default"]

    return {
        "article_source": article_source,
        "article_canonique": normalized,
        "mots_cles": tokenize_keywords(article_source),
        "ids_factures_sources": source_ids,
        "source_invoice_ids": source_ids,
        "invoice_paths_sources": invoice_paths[:3],
        "ape_context": [str(row.get("ape") or "").strip()] if str(row.get("ape") or "").strip() else [],
        "partitions_sources": [str(row.get("partition") or "").strip()] if str(row.get("partition") or "").strip() else [],
        "compte_comptable": compte,
        "taux_tva": row.get("sample_vat"),
        "categorie": "exploitation_metier",
        "sous_categorie": sous_categorie,
        "type_fournisseur": type_fournisseur,
    }


def main() -> None:
    summary = load_json(SCAN_SUMMARY_JSON)
    session = http_session()
    all_source_ids: list[str] = []
    selections: dict[str, list[dict[str, Any]]] = {}

    for metier, config in CONFIGS.items():
        payload = load_json(config["target_files"][0])
        existing_norm = {
            normalize_text(str(item.get("article_source") or ""))
            for section in ("items", "a_valider")
            for item in (payload.get(section) or [])
            if isinstance(item, dict)
        }
        current_total = len(payload.get("items") or [])
        needed = max(0, TARGET_TOTAL - current_total)
        if needed == 0:
            selections[metier] = []
            continue
        candidates = []
        for row in summary["metiers"][metier]["all_candidates"]:
            if not candidate_allowed(metier, row):
                continue
            normalized = normalize_text(str(row.get("article_source") or ""))
            if not normalized or normalized in existing_norm:
                continue
            candidates.append(row)
        candidates.sort(
            key=lambda row: (
                -int(row.get("line_occurrences") or 0),
                -int(row.get("invoice_count") or 0),
                str(row.get("article_source") or ""),
            )
        )
        chosen: list[dict[str, Any]] = []
        selected_norm: set[str] = set()
        for row in candidates:
            normalized = normalize_text(str(row.get("article_source") or ""))
            if not normalized or normalized in selected_norm:
                continue
            chosen.append(row)
            selected_norm.add(normalized)
            if len(chosen) >= needed:
                break
        if len(chosen) < needed:
            raise RuntimeError(f"{metier}: not enough candidates after filtering ({len(chosen)} < {needed})")
        selections[metier] = chosen
        for row in chosen:
            all_source_ids.extend(row.get("source_invoice_ids") or [])

    invoice_path_by_id = fetch_invoice_paths(session, list(dict.fromkeys(all_source_ids)))
    report_rows: list[dict[str, Any]] = []

    for metier, config in CONFIGS.items():
        chosen = selections[metier]
        file_reports = []
        for path in config["target_files"]:
            payload = load_json(path)
            existing_norm = {
                normalize_text(str(item.get("article_source") or ""))
                for section in ("items", "a_valider")
                for item in (payload.get(section) or [])
                if isinstance(item, dict)
            }
            added = 0
            skipped = 0
            for row in chosen:
                item = build_item(metier, row, invoice_path_by_id)
                key = normalize_text(item["article_source"])
                if not key or key in existing_norm:
                    skipped += 1
                    continue
                payload.setdefault("items", []).append(item)
                existing_norm.add(key)
                added += 1
            payload.setdefault("meta", {})
            payload["meta"]["items_count"] = len(payload.get("items") or [])
            payload["meta"]["updated"] = now_iso()
            payload["meta"]["selector"] = (
                "strict_exact_only + user_client_exact_expansion_to_200_from_keymanage_accounting"
            )
            dump_json(path, payload)
            file_reports.append({"file": path.name, "added": added, "skipped_existing": skipped})
        report_rows.append(
            {
                "metier": metier,
                "selected": len(chosen),
                "added_labels": [str(row.get("article_source") or "") for row in chosen],
                "files": file_reports,
            }
        )

    report = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "target_total": TARGET_TOTAL,
        "metiers": report_rows,
    }
    SUMMARY_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Expand Other Metiers To 200 Exact Summary",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `target_total`: `{report['target_total']}`",
        "",
    ]
    for row in report_rows:
        lines.append(f"## {row['metier']}")
        lines.append("")
        lines.append(f"- selected: `{row['selected']}`")
        for file_row in row["files"]:
            lines.append(f"- {file_row['file']}: added=`{file_row['added']}` skipped_existing=`{file_row['skipped_existing']}`")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_REPORT_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
