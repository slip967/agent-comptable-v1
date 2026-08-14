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
SUMMARY_MD = ROOT / "expand_btp_to_200_exact_summary.md"
SUMMARY_REPORT_JSON = ROOT / "expand_btp_to_200_exact_summary.json"
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

PRIORITY_CLIENTS = {
    "MB CONSTRUCTION",
    "MONDIAL BATIMENT",
    "SAFTA MENUISERIE",
}
TARGET_TOTAL_ITEMS = 200

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
    "60631": "6063",
    "6064": "6064",
    "606400": "6064",
    "6068": "6068",
    "606800": "6068",
    "607000": "607",
}

POSITIVE_TOKENS = (
    "abras",
    "aeration",
    "ba13",
    "bache",
    "bande",
    "beton",
    "bonde",
    "bouchon",
    "bois",
    "brosse",
    "cable",
    "caniveau",
    "carrel",
    "casque",
    "cheville",
    "ciment",
    "colle",
    "collier",
    "corniere",
    "coude",
    "couteau",
    "croisillon",
    "cutter",
    "disque",
    "enduit",
    "enrobe",
    "epong",
    "evac",
    "fraise",
    "gants",
    "grille",
    "joint",
    "kerafix",
    "lame",
    "lavabo",
    "listel",
    "lunette",
    "madrier",
    "manchon",
    "marteau",
    "masq",
    "masquage",
    "mastic",
    "mortier",
    "montant",
    "moulure",
    "niveau",
    "patte",
    "peinture",
    "placo",
    "placoplatre",
    "plaque",
    "plomberie",
    "porteur",
    "pvc",
    "quincaillerie",
    "rabot",
    "raccord",
    "rail",
    "rond a beton",
    "robinet",
    "seau",
    "siphon",
    "sol",
    "sous couche",
    "taloche",
    "tube",
    "vis",
)

NEGATIVE_PATTERNS = (
    r"\bacompte\b",
    r"\babonnement\b",
    r"\bachat brico depot\b",
    r"\badblue\b",
    r"\baller\b",
    r"\bautoroute\b",
    r"\bbiscuit\b",
    r"\bboite rouge\b",
    r"\bcarburant\b",
    r"\bcartouche delonghi\b",
    r"\bcoca\b",
    r"\bcloud\b",
    r"\bcontribution\b",
    r"\bcuisine\s*&?\s*bain\b",
    r"\bcuisine et bain\b",
    r"\bcafé\b",
    r"\bcafe\b",
    r"\bdelonghi\b",
    r"\bdiesel\b",
    r"\beco part\b",
    r"\beco-part\b",
    r"\bessuyage\b",
    r"\bforfait\b",
    r"\bgazole\b",
    r"\bgprs\b",
    r"\bhdmi\b",
    r"\bmicrofibre\b",
    r"\bmcs\b",
    r"\bnestle\b",
    r"\bnettoyage\b",
    r"\boasis\b",
    r"\boperateur\b",
    r"\bpalette\b",
    r"\bpapier kraft\b",
    r"\bpeage\b",
    r"\bremise\b",
    r"\breduction\b",
    r"\bretour\b",
    r"\breutilisable\b",
    r"\bsac de caisse\b",
    r"\bsac inventer\b",
    r"\bsac papier\b",
    r"\bsans plomb\b",
    r"\bserpillere\b",
    r"\bservice\b",
    r"\bsim\b",
    r"\bspeciale\b",
    r"\btransport\b",
    r"\bvente vrac\b",
    r"\bwc\b",
)

EXCLUDED_EXACT = {
    "BALANCE VRAC CODE A CLOU VIS BOULON",
    "BALANCE VRAC CODE A CLOU VIS BOULON KG",
    "C/GODET VENTE VRAC GRAND 162X54X63MM",
    "C/ VRAC VISSERIE GRAND GODET",
    "DECOUPE DROITE PLAN TRAVAIL",
    "HC_$ BATI+PLAQUE CHR GROHE",
    "PALETTE LUSSIANA",
    "PETIT SAC DE CAISSE",
    "SAC INVENTER LA MAISON DE DEMAIN",
    "SAC PAPIER KRAFT BRICOMAN",
    "SAC DE CAISSE VERT REUTILISABLE 320*160",
    "SET BALAYETTE",
}
EXCLUDED_EXACT_NORMALIZED = set()

ACCOUNT_PRIORITY = {
    "601": 0,
    "6011": 0,
    "6021": 1,
    "6022": 1,
    "602": 1,
    "605": 2,
    "6058": 2,
    "6061": 3,
    "6062": 3,
    "6063": 3,
    "6064": 4,
    "6068": 5,
    "606": 5,
    "607": 6,
    "604": 7,
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


for _value in EXCLUDED_EXACT:
    EXCLUDED_EXACT_NORMALIZED.add(normalize_text(_value))


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


def has_positive_signal(normalized: str) -> bool:
    return any(token in normalized for token in POSITIVE_TOKENS)


def is_clean_candidate(article_source: str, account: str) -> bool:
    normalized = normalize_text(article_source)
    if not normalized or normalized in EXCLUDED_EXACT_NORMALIZED:
        return False
    if re.search("|".join(NEGATIVE_PATTERNS), normalized):
        return False
    if len(normalized.split()) == 1 and normalized not in {"rail", "manchon", "bouchon"}:
        return False
    clean_account = normalize_account(account)
    if clean_account.startswith(("604", "607")):
        return False
    if not has_positive_signal(normalized) and not clean_account.startswith(("601", "602")):
        return False
    return True


def guess_sub_category(account: str, article_source: str) -> str:
    normalized = normalize_text(article_source)
    if any(token in normalized for token in ("tube", "pvc", "coude", "manchon", "siphon", "bonde", "evac", "raccord", "lavabo", "per")):
        return "plomberie"
    if any(token in normalized for token in ("vis", "cheville", "bouchon", "corniere", "rail", "montant", "croisillon", "joint", "grille", "moulure", "profil", "listel", "patte")):
        return "quincaillerie"
    if any(token in normalized for token in ("marteau", "coffret", "scie", "cutter", "disque", "lame", "couteau", "niveau", "brosse", "taloche", "lunette", "masque")):
        return "outillage"
    if any(token in normalized for token in ("gants", "casque", "bache", "masq", "masquage", "seau", "eponge")):
        return "consommable_chantier"
    if any(token in normalized for token in ("colle", "enduit", "ciment", "mortier", "plaque", "placo", "placoplatre", "beton", "sol", "peinture", "madrier", "carrel")):
        return "matiere_premiere"
    if str(account).startswith(("601", "602")):
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
    return {
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


def quality_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    account = normalize_account(str(row.get("sample_account") or "").strip())
    occurrences = int(row.get("line_occurrences") or 0)
    invoice_count = int(row.get("invoice_count") or 0)
    positive_bonus = 1 if has_positive_signal(normalize_text(str(row.get("article_source") or ""))) else 0
    account_rank = ACCOUNT_PRIORITY.get(account, 99)
    return (-occurrences, -invoice_count, -positive_bonus, account_rank, str(row.get("article_source") or ""))


def main() -> None:
    summary = load_json(SUMMARY_JSON)
    base_payload = load_json(ROOT / "base_produits_btp_v1.json")
    existing_norm = {
        normalize_text(str(item.get("article_source") or ""))
        for section in ("items", "a_valider")
        for item in (base_payload.get(section) or [])
        if isinstance(item, dict)
    }
    current_total = len(base_payload.get("items") or [])
    needed = max(0, TARGET_TOTAL_ITEMS - current_total)
    if needed == 0:
        report = {
            "generated_at": now_iso(),
            "source_db": SOURCE_DB,
            "current_total": current_total,
            "target_total": TARGET_TOTAL_ITEMS,
            "needed": 0,
            "selected": 0,
            "message": "BTP base already at or above target total.",
        }
        SUMMARY_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        SUMMARY_MD.write_text("# Expand BTP To 200 Exact Summary\n\n- No change needed.\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    selected: list[dict[str, Any]] = []
    selected_norm: set[str] = set()
    selected_by_client: dict[str, int] = {}
    all_source_ids: list[str] = []

    for client in summary.get("clients", []):
        client_name = str(client.get("client") or "").strip()
        if client_name not in PRIORITY_CLIENTS:
            continue
        candidates = []
        for row in client.get("candidates") or []:
            if not isinstance(row, dict):
                continue
            source = str(row.get("article_source") or "").strip()
            normalized = normalize_text(source)
            if not source or not normalized or normalized in existing_norm or normalized in selected_norm:
                continue
            if not is_clean_candidate(source, str(row.get("sample_account") or "").strip()):
                continue
            row = dict(row)
            row["_client"] = client_name
            row["_partition"] = str(client.get("partition") or "").strip()
            row["_ape"] = str(client.get("ape") or "").strip()
            candidates.append(row)
        candidates.sort(key=quality_key)
        for row in candidates:
            if len(selected) >= needed:
                break
            normalized = normalize_text(str(row.get("article_source") or ""))
            if normalized in selected_norm:
                continue
            selected.append(row)
            selected_norm.add(normalized)
            selected_by_client[client_name] = selected_by_client.get(client_name, 0) + 1
            all_source_ids.extend(row.get("source_invoice_ids") or [])
        if len(selected) >= needed:
            break

    if len(selected) < needed:
        raise RuntimeError(f"Unable to select enough clean BTP candidates: selected={len(selected)} needed={needed}")

    session = http_session()
    invoice_path_by_id = fetch_invoice_paths(session, list(dict.fromkeys(all_source_ids)))

    integrated_count_by_file: dict[str, int] = {}
    skipped_existing_by_file: dict[str, int] = {}

    for path in TARGET_FILES:
        payload = load_json(path)
        file_existing_norm = {
            normalize_text(str(item.get("article_source") or ""))
            for section in ("items", "a_valider")
            for item in (payload.get(section) or [])
            if isinstance(item, dict)
        }
        added = 0
        skipped = 0
        for row in selected:
            item = build_item(
                row,
                partition=str(row.get("_partition") or "").strip(),
                ape=str(row.get("_ape") or "").strip(),
                invoice_path_by_id=invoice_path_by_id,
            )
            key = normalize_text(item["article_source"])
            if not key or key in file_existing_norm:
                skipped += 1
                continue
            payload.setdefault("items", []).append(item)
            file_existing_norm.add(key)
            added += 1

        payload.setdefault("meta", {})
        payload["meta"]["items_count"] = len(payload.get("items") or [])
        payload["meta"]["generated_at"] = payload["meta"].get("generated_at") or now_iso()
        payload["meta"]["updated"] = now_iso()
        payload["meta"]["selector"] = (
            "strict_exact_only + manual_btp_shortlist_from_user_clients + exact_btp_expansion_to_200_from_keymanage_accounting"
        )
        dump_json(path, payload)
        integrated_count_by_file[path.name] = added
        skipped_existing_by_file[path.name] = skipped

    report = {
        "generated_at": now_iso(),
        "source_db": SOURCE_DB,
        "current_total": current_total,
        "target_total": TARGET_TOTAL_ITEMS,
        "needed": needed,
        "selected": len(selected),
        "selected_by_client": selected_by_client,
        "files": [
            {
                "file": path.name,
                "added": integrated_count_by_file[path.name],
                "skipped_existing": skipped_existing_by_file[path.name],
            }
            for path in TARGET_FILES
        ],
        "added_labels": [str(row.get("article_source") or "") for row in selected],
    }
    SUMMARY_REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Expand BTP To 200 Exact Summary",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `current_total`: `{report['current_total']}`",
        f"- `target_total`: `{report['target_total']}`",
        f"- `needed`: `{report['needed']}`",
        f"- `selected`: `{report['selected']}`",
        "",
        "## Selected By Client",
        "",
    ]
    for client_name, count in sorted(selected_by_client.items()):
        lines.append(f"- `{client_name}`: `{count}`")
    lines.extend(["", "## Files", ""])
    for row in report["files"]:
        lines.append(f"- {row['file']}: added=`{row['added']}` skipped_existing=`{row['skipped_existing']}`")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_REPORT_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")


if __name__ == "__main__":
    main()
