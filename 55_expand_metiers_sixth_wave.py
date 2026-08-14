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
SUMMARY_JSON = SCRIPT_DIR / "sixth_wave_metier_expansion_summary.json"
SUMMARY_MD = SCRIPT_DIR / "sixth_wave_metier_expansion_summary.md"

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
    "60225": "6025",
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "606300": "6063",
    "60630000": "6063",
    "606800": "6068",
    "60680000": "6068",
    "607000": "607",
    "622600": "6226",
}

TARGETS = {
    "boucherie": {
        "candidate_csv": "candidate_packs_metier/boucherie_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_boucherie_v1.json",
            "base_produits_boucherie_v1_with_accounts.json",
        ],
        "active_labels": (
            "BACON DE VEAU HALAL",
            "GRAND SAUCISSON SEC HALAL COUPE",
            "AGNEAU FRESSURE ORIGINE :FRANCE",
            "AGNEAU TETE ORIGINE :FRANCE",
            "BOEUF CUISSE FLANCH BLANC BLEU BELGE VIANDE HALLAL",
            "CARRE DE VEAU SANS ROGNONS - VIANDE HALLAL",
            "JAMBON DE VEAU HALAL KG",
            "CERVELLE VEAU UE (V)",
            "FILET DE DINDE HALAL origine : FR",
            "DEMI ROSBIF AGNEAU",
            "POULET FERMIER HALAL PAC origine : FR",
            "CUISSE DE POULET FERMIER HALAL origine : FR",
            "FOIE DE POULET CEE HALAL origine : BE",
            "FILET DE POULET FERMIER HALAL origine : FR",
            "FILET DE DINDE CEE HALAL origine : IT",
            "CUISSEAU DE VEAU - VIANDE HALLAL",
            "PILON DE POULET HALLAL CEE",
        ),
    },
    "boulangerie": {
        "candidate_csv": "candidate_packs_metier/boulangerie_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_boulangerie_v1.json",
            "base_produits_boulangerie_v1_with_accounts.json",
        ],
        "active_labels": (
            "SPECULOS BRISURE MOULU 750 gr 64695",
            "GD SAC REGROUP PAIN 39X20X76CM",
            "LAIT FERMENTE \"LUXLAIT \" 8 X 1L",
            "PAIN SUEDOIS ROND 55 GR X 72 UVI1",
            "PATE PISTACHE COLOREE MANE 1KG GR",
            "250 SAC PAIN VERT 16X10X35",
            "CROUSTI CHOC LAIT NOIR BLC DGF POT 450G",
            "MINI BEIGNET FOURRAGE SAVEUR FRAISE 21G *",
            "SAC PAIN TR BEIG BAGO PUR 230/40X420X200",
            "SAC PAIN TR JAUN BAGO PUR 120/50X350X200",
        ),
    },
    "transport": {
        "candidate_csv": "candidate_packs_metier/transport_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_transport_v1.json",
            "base_produits_transport_v1_with_accounts.json",
        ],
        "active_labels": (),
    },
    "btp": {
        "candidate_csv": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_btp_v1.json",
            "base_produits_btp_v1_with_accounts.json",
        ],
        "active_labels": (
            "PALETTE EQIOM GRANULATS",
            "CARRELAGE SDB 60*120 GRIS DU MARAIS BEIGE Epaisseur 7mm. Emballé par 3 soit 216 m2/Bte 64.80 m2/Palette 35.82 kg/Bte",
        ),
    },
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


def build_items(metier: str, labels: tuple[str, ...], row_map: dict[str, dict], partition_ape_map: dict[str, str], helper) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in labels:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_fake_stat(row, partition_ape_map)
        item = helper.build_product_item(metier, label, stat, row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or "")
        item["selection_source"] = "manual_sixth_wave_v1"
        note = str(item.get("notes") or "").strip()
        suffix = "Ajout manuel 6e vague depuis candidate pack nettoyé."
        item["notes"] = f"{note} | {suffix}".strip(" |")
        items.append(item)
    return items, missing


def integrate_items(payload: dict, new_items: list[dict], helper, meta_key: str) -> dict:
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
    payload["meta"][meta_key] = {
        "updated_at": helper.now_iso(),
        "added_items": added,
        "skipped_existing": skipped,
        "added_labels": added_labels,
    }
    return {"added": added, "skipped_existing": skipped, "added_labels": added_labels}


def main() -> int:
    helper = load_helper_module()
    partition_ape_map = load_partition_ape_map()
    summary = {}
    md_lines = [
        "# Sixth Wave Metier Expansion Summary",
        "",
        "Selection mode: manual strict curation from the remaining candidate pool.",
        "",
    ]

    for metier, cfg in TARGETS.items():
        row_map = load_csv_rows(SCRIPT_DIR / cfg["candidate_csv"])
        items, missing = build_items(metier, cfg["active_labels"], row_map, partition_ape_map, helper)
        file_results = []
        for file_name in cfg["base_files"]:
            path = SCRIPT_DIR / file_name
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            result = integrate_items(payload, items, helper, "manual_sixth_wave_v1")
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            file_results.append({"file": file_name, **result})
        summary[metier] = {
            "requested_active": list(cfg["active_labels"]),
            "missing": missing,
            "files": file_results,
        }
        md_lines.append(f"## {metier}")
        md_lines.append("")
        md_lines.append(f"- requested_active: `{len(cfg['active_labels'])}`")
        if missing:
            md_lines.append(f"- missing: `{missing}`")
        for result in file_results:
            md_lines.append(
                f"- {result['file']}: items_added=`{result['added']}` skipped_existing=`{result['skipped_existing']}`"
            )
        if not cfg["active_labels"]:
            md_lines.append("- note: `no clean remaining product candidate selected on this wave`")
        md_lines.append("")

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
