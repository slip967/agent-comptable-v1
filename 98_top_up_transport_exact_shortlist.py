#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SUMMARY_JSON = ROOT / "other_metiers_exact_candidates_summary.json"
SUMMARY_REPORT_JSON = ROOT / "top_up_transport_exact_shortlist_summary.json"
SUMMARY_REPORT_MD = ROOT / "top_up_transport_exact_shortlist_summary.md"
TARGET_FILES = [
    ROOT / "base_produits_transport_v1.json",
    ROOT / "base_produits_transport_v1_with_accounts.json",
]
TARGET_TOTAL = 200

# Exact-only shortlist kept intentionally narrow:
# - present in keymanage_accounting exact scan summary
# - clearly transport / vehicle exploitation
# - excludes telecoms and overly generic labels
SHORTLIST = [
    "SP98 EXCELLIUM",
    "PLAQUETTE FREIN BOSCH",
    "240filtre huile nor auto",
    "ENSEMBLE FILTRE-AIR",
    "FILTRE A AIR VL",
    "FILTRE A HUILE VL",
    "PLAQUETTE DE FREIN AV",
    "BATTERIE NAP 74AMP",
    "BATTERIE VL BOSCH(S-LINE) 70AH 760A (278X175X190)",
    "DISQUE FR BOSCH X1 BD2434",
    "DISQUE FR BOSCH X2 BD2433",
    "ETEC 10W30 (Huile moteur)",
    "Filtre huile norauto",
    "Huile de boite",
    "LIQUIDE DE FREINS BIDON DOT4",
    "NETTOYANT FREINS EMBRAYAGES 600ML",
    "Plaquettes de frein arriere + témoin",
]

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
    "6061": "6061",
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
    "607100": "607",
    "615000": "615",
    "6155": "615",
    "615500": "615",
    "626": "626",
    "6261": "6261",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def build_item(row: dict[str, Any]) -> dict[str, Any]:
    article_source = str(row.get("article_source") or "").strip()
    normalized = normalize_text(article_source)
    seen_ids: set[str] = set()
    source_ids: list[str] = []
    for value in row.get("source_invoice_ids") or []:
        value = str(value or "").strip()
        if not value or value in seen_ids:
            continue
        seen_ids.add(value)
        source_ids.append(value)
        if len(source_ids) >= 3:
            break

    partition = str(row.get("partition") or "").strip()
    ape = str(row.get("ape") or "").strip()
    return {
        "article_source": article_source,
        "article_canonique": normalized,
        "mots_cles": tokenize_keywords(article_source),
        "ids_factures_sources": source_ids,
        "source_invoice_ids": source_ids,
        "invoice_paths_sources": [],
        "ape_context": [ape] if ape else [],
        "partitions_sources": [partition] if partition else [],
        "compte_comptable": normalize_account(str(row.get("sample_account") or "").strip()),
        "taux_tva": row.get("sample_vat"),
        "categorie": "exploitation_metier",
        "sous_categorie": "matiere_premiere",
        "type_fournisseur": "service_transport",
    }


def main() -> None:
    summary = load_json(SUMMARY_JSON)
    candidates = summary["metiers"]["transport"]["all_candidates"]
    row_by_source = {
        str(row.get("article_source") or "").strip(): row
        for row in candidates
        if str(row.get("article_source") or "").strip() in SHORTLIST
    }

    missing_from_summary = [label for label in SHORTLIST if label not in row_by_source]
    if missing_from_summary:
        raise RuntimeError(f"Labels not found in transport exact summary: {missing_from_summary}")

    report_files: list[dict[str, Any]] = []

    for path in TARGET_FILES:
        payload = load_json(path)
        items = payload.setdefault("items", [])
        existing_norm = {
            normalize_text(str(item.get("article_source") or ""))
            for section in ("items", "a_valider")
            for item in (payload.get(section) or [])
            if isinstance(item, dict)
        }
        added_labels: list[str] = []
        starting_count = len(items)

        for label in SHORTLIST:
            if len(items) >= TARGET_TOTAL:
                break
            row = row_by_source[label]
            item = build_item(row)
            key = normalize_text(item["article_source"])
            if not key or key in existing_norm:
                continue
            items.append(item)
            existing_norm.add(key)
            added_labels.append(item["article_source"])

        if len(items) != TARGET_TOTAL:
            raise RuntimeError(
                f"{path.name}: expected {TARGET_TOTAL} items after top-up, got {len(items)}"
            )

        payload.setdefault("meta", {})
        selector = str(payload["meta"].get("selector") or "").strip()
        topup_marker = "transport_exact_shortlist_top_up_from_keymanage_accounting"
        if topup_marker not in selector:
            payload["meta"]["selector"] = f"{selector} + {topup_marker}" if selector else topup_marker
        payload["meta"]["items_count"] = len(items)
        payload["meta"]["updated"] = now_iso()
        dump_json(path, payload)

        report_files.append(
            {
                "file": path.name,
                "starting_count": starting_count,
                "ending_count": len(items),
                "added": len(added_labels),
                "added_labels": added_labels,
            }
        )

    report = {
        "generated_at": now_iso(),
        "target_total": TARGET_TOTAL,
        "shortlist": SHORTLIST,
        "files": report_files,
    }
    SUMMARY_REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Top Up Transport Exact Shortlist Summary",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `target_total`: `{report['target_total']}`",
        "",
        "## Shortlist",
        "",
    ]
    for label in SHORTLIST:
        lines.append(f"- {label}")
    lines.append("")
    for file_row in report_files:
        lines.append(f"## {file_row['file']}")
        lines.append("")
        lines.append(f"- `starting_count`: `{file_row['starting_count']}`")
        lines.append(f"- `ending_count`: `{file_row['ending_count']}`")
        lines.append(f"- `added`: `{file_row['added']}`")
        for label in file_row["added_labels"]:
            lines.append(f"- {label}")
        lines.append("")
    SUMMARY_REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_REPORT_JSON}")
    print(f"[OK] summary_md={SUMMARY_REPORT_MD}")


if __name__ == "__main__":
    main()
