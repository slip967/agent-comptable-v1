#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
REPORT_PATH = SCRIPT_DIR / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_JSON = SCRIPT_DIR / "seventh_wave_boucherie_db_layer_summary.json"
SUMMARY_MD = SCRIPT_DIR / "seventh_wave_boucherie_db_layer_summary.md"

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "606300": "6063",
    "60630000": "6063",
    "606800": "6068",
    "60680000": "6068",
    "607000": "607",
}

TARGET = {
    "candidate_csv": "candidate_packs_metier/boucherie_top_500_cleaned_candidates.csv",
    "base_files": [
        "base_produits_boucherie_v1.json",
        "base_produits_boucherie_v1_with_accounts.json",
    ],
    "active_labels": (
        "RUMSTEACK BLANC BLEU BELGE VIANDE HALLAL",
        "BAVETTE ALOYAU BLANC BLEU BELGE VIANDE HALLAL",
        "VEAU",
        "BASSE COTE SOUS VIDE BEUF",
        "FILET DE POULET HALAL UE origine : NL",
        "CUISSE DE POULET HALAL UE origine : NL",
        "FILET DE POULET HALAL UE origine : UE",
        "FILET DE POULET HALAL CEE origine : NL",
        "PILON DE POULET HALAL UE origine : NL",
        "VEAU FOIE",
        "VEAU CREPINE",
        "BOEUF QUEUE SOUS-VIDE ORIGINE :FRANCE",
        "AILE DE POULET HALAL UE origine : UE",
        "AILES DE POULET HALAL CEE origine : BE",
        "VEAU PIED ORIGINE :FRANCE",
    ),
}


def load_helper_module():
    spec = importlib.util.spec_from_file_location("triage_helper_module", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_account(account: str) -> str:
    account = str(account or "").strip()
    return ACCOUNT_MAP.get(account, account)


def load_partition_ape_map() -> dict[str, str]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return {
        str(part.get("partition_prefix") or "").strip(): str(part.get("client_ape") or "").strip()
        for part in (report.get("partitions") or [])
        if str(part.get("partition_prefix") or "").strip()
    }


def load_csv_rows(path: Path) -> dict[str, dict]:
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            if label:
                rows[label] = row
    return rows


def build_fake_stat(row: dict, partition_ape_map: dict[str, str]) -> dict:
    article_source = str(row.get("article_source") or "").strip()
    sample_account = normalize_account(str(row.get("sample_account") or "").strip())
    partitions_raw = str(row.get("partitions") or "").strip()
    partitions = [part.strip() for part in partitions_raw.split("|") if part.strip()]
    invoice_count = int(row.get("invoice_count") or 0)
    line_occurrences = int(row.get("line_occurrences") or invoice_count or 1)
    ape_context = {partition_ape_map.get(part, "") for part in partitions if partition_ape_map.get(part, "")}

    stat = {
        "label_counter": Counter({article_source: 1}),
        "invoice_ids": set(),
        "partitions": set(partitions),
        "account_counter": Counter(),
        "vat_counter": Counter(),
        "invoice_count_hint": invoice_count,
        "line_occurrences": line_occurrences,
        "ape_context": ape_context,
    }
    if sample_account:
        stat["account_counter"][sample_account] += 1
    return stat


def build_items(labels: tuple[str, ...], row_map: dict[str, dict], partition_ape_map: dict[str, str], helper) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in labels:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_fake_stat(row, partition_ape_map)
        item = helper.build_product_item("boucherie", label, stat, row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or "")
        item["selection_source"] = "manual_seventh_wave_db_layer_v1"
        note = str(item.get("notes") or "").strip()
        suffix = "Ajout manuel 7e vague depuis couche DB entry/invoice_form."
        item["notes"] = f"{note} | {suffix}".strip(" |")
        items.append(item)
    return items, missing


def integrate_items(payload: dict, new_items: list[dict], helper) -> dict:
    payload.setdefault("items", [])
    existing = {
        helper.normalize_text(str(item.get("article_source") or ""))
        for bucket_name in ("items", "a_valider")
        for item in (payload.get(bucket_name) or [])
        if isinstance(item, dict)
    }

    added = 0
    skipped = 0
    added_labels = []
    for item in new_items:
        key = helper.normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            skipped += 1
            continue
        payload["items"].append(item)
        existing.add(key)
        added += 1
        added_labels.append(item["article_source"])

    payload.setdefault("meta", {})
    payload["meta"]["items_count"] = len(payload.get("items") or [])
    payload["meta"]["manual_seventh_wave_db_layer_v1"] = {
        "updated_at": helper.now_iso(),
        "added_items": added,
        "skipped_existing": skipped,
        "added_labels": added_labels,
    }
    return {"added": added, "skipped_existing": skipped, "added_labels": added_labels}


def main() -> int:
    helper = load_helper_module()
    partition_ape_map = load_partition_ape_map()
    row_map = load_csv_rows(SCRIPT_DIR / TARGET["candidate_csv"])
    items, missing = build_items(TARGET["active_labels"], row_map, partition_ape_map, helper)

    file_results = []
    for file_name in TARGET["base_files"]:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_items(payload, items, helper)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        file_results.append({"file": file_name, **result})

    summary = {
        "requested_active": list(TARGET["active_labels"]),
        "missing": missing,
        "files": file_results,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Seventh Wave Boucherie DB Layer Summary",
        "",
        "Selection mode: manual curation from DB-derived candidate pack (`entry` / `invoice_form`).",
        "",
        f"- requested_active: `{len(TARGET['active_labels'])}`",
    ]
    if missing:
        lines.append(f"- missing: `{missing}`")
    for result in file_results:
        lines.append(
            f"- {result['file']}: items_added=`{result['added']}` skipped_existing=`{result['skipped_existing']}`"
        )
    lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
