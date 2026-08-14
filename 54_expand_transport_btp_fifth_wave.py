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
SUMMARY_JSON = SCRIPT_DIR / "fifth_wave_transport_btp_summary.json"
SUMMARY_MD = SCRIPT_DIR / "fifth_wave_transport_btp_summary.md"

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

PRODUCT_TARGETS = {
    "transport": {
        "candidate_csv": "candidate_packs_metier/transport_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_transport_v1.json",
            "base_produits_transport_v1_with_accounts.json",
        ],
        "active_labels": (
            "AMORTISSEUR DE CHOC",
        ),
    },
    "btp": {
        "candidate_csv": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_btp_v1.json",
            "base_produits_btp_v1_with_accounts.json",
        ],
        "active_labels": (
            "POUR PANNEAUX FIBRE CIMENT POUR SYSTEME UNI RIVET 11MM",
            "Palette HMFC ciments 95x115 cm",
        ),
    },
}

TRANSPORT_CHARGES_TARGETS = {
    "candidate_csv": "candidate_packs_metier/transport_top_500_cleaned_candidates.csv",
    "charges_files": [
        "base_charges_externes_v1.json",
        "base_charges_externes_v1_with_accounts.json",
    ],
    "labels": (
        "Déposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu arrière (Roues complètes démontées)",
        "Remplacer les garnitures de frein et les disques de frein de l'essieu arriere (roues complètes démontées)",
        "Remplacer les garnitures de frein et les disques de frein de l'essieu avant (roues complètes démontées) sur véh. avec étrier fixe",
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


def build_product_items(metier: str, labels: tuple[str, ...], row_map: dict[str, dict], partition_ape_map: dict[str, str], helper) -> tuple[list[dict], list[str]]:
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
        item["selection_source"] = "manual_fifth_wave_v1"
        note = str(item.get("notes") or "").strip()
        suffix = "Ajout manuel 5e vague depuis candidate pack nettoyé."
        item["notes"] = f"{note} | {suffix}".strip(" |")
        items.append(item)
    return items, missing


def integrate_product_items(payload: dict, new_items: list[dict], helper, meta_key: str) -> dict:
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


def build_transport_charge_items(labels: tuple[str, ...], row_map: dict[str, dict], partition_ape_map: dict[str, str], helper) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in labels:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_fake_stat(row, partition_ape_map)
        item = helper.build_charge_item(label, stat, row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or "")
        item["sous_profil"] = "entretien_et_maintenance"
        item["nature_charge"] = "entretien"
        item["profil_facturation"] = "intervention_ponctuelle"
        item["profil_facturation_champs"] = helper.default_charges_champs("intervention_ponctuelle")
        item["sous_categorie"] = helper.CHARGES_SOUS_CATEGORIE_MAP.get("entretien_et_maintenance", "entretien_reparation")
        item["classification_version"] = "charges_externes_rules_v1_transport_fifth_wave"
        item["classification_reason"] = "manual_reclass:maintenance_transport"
        item["selection_source"] = "manual_fifth_wave_transport_to_charges_v1"
        note = str(item.get("notes") or "").strip()
        suffix = "Ajout manuel 5e vague depuis transport, reclassé en maintenance."
        item["notes"] = f"{note} | {suffix}".strip(" |")
        items.append(item)
    return items, missing


def integrate_charge_items(payload: dict, new_items: list[dict], helper, meta_key: str) -> dict:
    payload.setdefault("items", [])
    existing = {
        helper.normalize_text(str(item.get("article_source") or ""))
        for item in (payload.get("items") or [])
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
    helper.refresh_charges_profile_enrichment(payload)
    return {"added": added, "skipped_existing": skipped, "added_labels": added_labels}


def main() -> int:
    helper = load_helper_module()
    partition_ape_map = load_partition_ape_map()
    summary: dict[str, dict] = {}
    md_lines = [
        "# Fifth Wave Transport/BTP Summary",
        "",
        "Selection mode: manual strict curation on the remaining candidate pool.",
        "",
    ]

    for metier, cfg in PRODUCT_TARGETS.items():
        row_map = load_csv_rows(SCRIPT_DIR / cfg["candidate_csv"])
        items, missing = build_product_items(metier, cfg["active_labels"], row_map, partition_ape_map, helper)
        file_results = []
        for file_name in cfg["base_files"]:
            path = SCRIPT_DIR / file_name
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            result = integrate_product_items(payload, items, helper, "manual_fifth_wave_v1")
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
        md_lines.append("")

    transport_row_map = load_csv_rows(SCRIPT_DIR / TRANSPORT_CHARGES_TARGETS["candidate_csv"])
    charge_items, missing_transport_charges = build_transport_charge_items(
        TRANSPORT_CHARGES_TARGETS["labels"],
        transport_row_map,
        partition_ape_map,
        helper,
    )
    charge_results = []
    for file_name in TRANSPORT_CHARGES_TARGETS["charges_files"]:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_charge_items(payload, charge_items, helper, "manual_fifth_wave_transport_charges_v1")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        charge_results.append({"file": file_name, **result})
    summary["transport_to_charges"] = {
        "requested_labels": list(TRANSPORT_CHARGES_TARGETS["labels"]),
        "missing": missing_transport_charges,
        "files": charge_results,
    }
    md_lines.append("## transport_to_charges")
    md_lines.append("")
    md_lines.append(f"- requested_labels: `{len(TRANSPORT_CHARGES_TARGETS['labels'])}`")
    if missing_transport_charges:
        md_lines.append(f"- missing: `{missing_transport_charges}`")
    for result in charge_results:
        md_lines.append(
            f"- {result['file']}: items_added=`{result['added']}` skipped_existing=`{result['skipped_existing']}`"
        )
    md_lines.append("")

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
