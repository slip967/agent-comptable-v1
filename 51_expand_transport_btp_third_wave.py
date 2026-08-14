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
SUMMARY_JSON = SCRIPT_DIR / "third_wave_transport_btp_summary.json"
SUMMARY_MD = SCRIPT_DIR / "third_wave_transport_btp_summary.md"

ACCOUNT_MAP = {
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "606300": "6063",
    "60630000": "6063",
    "606800": "6068",
    "60680000": "6068",
    "622600": "6226",
}

TARGETS = {
    "transport": {
        "candidate_csv": "candidate_packs_metier/transport_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_transport_v1.json",
            "base_produits_transport_v1_with_accounts.json",
        ],
        "active_labels": (
            "SP98 EXCELLIUM",
            "TS CART. FILTRE A HUILE",
            "GARNITURE FREIN A DISQUE",
            "CAPTEUR D'USURE",
            "FILTRE A HUILE",
            "PATE POUR FREINS (PDP)",
            "PLAQUETTE FREIN BOSCH",
            "DISQUE DE FREIN COMPOSITE",
            "DISQUE DE FREIN VENTILE",
        ),
        "a_valider_labels": (
            "Vos abonnements, forfaits et options",
            "Bbox - location équipement (du 02/05 au 01/06)",
            "Bbox - location équipement (du 02/12 au 01/01)",
            "Vos communications (du 02/12 au 01/01)",
            "Appels a tarification majorée (Numéros spéciaux)",
            "Appels tarification majorée - Numéros spéciaux",
            "Applications - contenus - services",
            "Avantage Internet 100Go",
            "Bbox - location équipement (du 02/02 au 01/03)",
            "Bbox - location équipement (du 02/10 au 01/11)",
            "Bbox - location équipement (du 02/11 au 01/12)",
            "Bbox fibre jusqu'a1 Gb/s (du 02/05 au 01/06)",
            "Bbox fibre jusqu'a1 Gb/s (du 02/07 au 01/08)",
            "Bbox fibre jusqu'a1 Gb/s (du 02/12 au 01/01)",
            "Evolution d'offre - Appels illimités mobiles France_ (du 02/07 au 01/08)",
            "Forfait Sensation client 70Go",
            "Internet 10Go France",
            "Multi-TV FTTH (du 02/05 au 01/06)",
            "Multi-TV FTTH (du 02/12 au 01/01)",
            "Services de télécommunications (forfait, communications, autres services)",
            "Vos communications (du 02/07 au 01/08)",
            "Vos communications (du 02/09 au 01/10)",
        ),
    },
    "btp": {
        "candidate_csv": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_btp_v1.json",
            "base_produits_btp_v1_with_accounts.json",
        ],
        "active_labels": (
            "CUTTER STANDARD 18MM AVEC 3 LAMES NOIR",
            "Sac a gravat tissé 60x100cm paquet de 10 pièces",
            "PROMACURE S -Cure des bétons,phase solvant -BIDON DE 20 LITRES",
            "ROND A BETON TOR HLE FE5005 6MM 3M",
            "Rabot à béton essence",
            "PARKING Coulage Radier",
            "PLANCHER SUPERSTRUCTURE ( 100 % ) Finition brut",
            "BPS C25/30 CEMI SR5+Cv D20 S3 XF1",
            "Passerelle",
            "vanne thermostatique connectée",
            "CUTTER A LAME CASSABLE 25 MM d213",
            "CUTTER NOVI LAME RETRACT 18MM",
        ),
        "a_valider_labels": (
            "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
            "Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau",
            "Amenée-repli de l'atelier de forage des micropieux",
            "Implantation des micropieux",
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


def build_items(metier: str, labels: tuple[str, ...], row_map: dict[str, dict], partition_ape_map: dict[str, str], helper, source_tag: str) -> tuple[list[dict], list[str]]:
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
        item["selection_source"] = source_tag
        base_note = str(item.get("notes") or "").strip()
        suffix = "Ajout manuel 3e vague depuis candidate pack nettoye."
        item["notes"] = f"{base_note} | {suffix}" if base_note else suffix
        items.append(item)
    return items, missing


def integrate_bucket(payload: dict, bucket_name: str, new_items: list[dict], helper, meta_key: str) -> dict:
    payload.setdefault("items", [])
    payload.setdefault("a_valider", [])
    bucket = payload.setdefault(bucket_name, [])

    existing = set()
    for source_bucket in ("items", "a_valider"):
        for item in payload.get(source_bucket) or []:
            if isinstance(item, dict):
                key = helper.normalize_text(str(item.get("article_source") or ""))
                if key:
                    existing.add(key)

    added = 0
    skipped = 0
    added_labels = []
    for item in new_items:
        key = helper.normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            skipped += 1
            continue
        bucket.append(item)
        existing.add(key)
        added += 1
        added_labels.append(item["article_source"])

    payload.setdefault("meta", {})
    payload["meta"]["items_count"] = len(payload.get("items") or [])
    payload["meta"]["a_valider_count"] = len(payload.get("a_valider") or [])
    payload["meta"].setdefault(meta_key, {})
    payload["meta"][meta_key][bucket_name] = {
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
    markdown_lines = [
        "# Third Wave Transport/BTP Summary",
        "",
        "Selection mode: manual strict curation on top of cleaned candidate packs.",
        "",
    ]

    for metier, cfg in TARGETS.items():
        row_map = load_csv_rows(SCRIPT_DIR / cfg["candidate_csv"])
        active_items, missing_active = build_items(
            metier,
            cfg["active_labels"],
            row_map,
            partition_ape_map,
            helper,
            "manual_third_wave_active_v1",
        )
        a_valider_items, missing_a_valider = build_items(
            metier,
            cfg["a_valider_labels"],
            row_map,
            partition_ape_map,
            helper,
            "manual_third_wave_a_valider_v1",
        )

        file_results = []
        for file_name in cfg["base_files"]:
            path = SCRIPT_DIR / file_name
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            active_result = integrate_bucket(payload, "items", active_items, helper, "manual_third_wave_v1")
            a_valider_result = integrate_bucket(payload, "a_valider", a_valider_items, helper, "manual_third_wave_v1")
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            file_results.append(
                {
                    "file": file_name,
                    "items": active_result,
                    "a_valider": a_valider_result,
                }
            )

        summary[metier] = {
            "requested_active": list(cfg["active_labels"]),
            "requested_a_valider": list(cfg["a_valider_labels"]),
            "missing_active": missing_active,
            "missing_a_valider": missing_a_valider,
            "files": file_results,
        }

        markdown_lines.append(f"## {metier}")
        markdown_lines.append("")
        markdown_lines.append(f"- requested_active: `{len(cfg['active_labels'])}`")
        markdown_lines.append(f"- requested_a_valider: `{len(cfg['a_valider_labels'])}`")
        if missing_active or missing_a_valider:
            markdown_lines.append(f"- missing_active: `{missing_active}`")
            markdown_lines.append(f"- missing_a_valider: `{missing_a_valider}`")
        for result in file_results:
            markdown_lines.append(
                f"- {result['file']}: items_added=`{result['items']['added']}` a_valider_added=`{result['a_valider']['added']}`"
            )
        markdown_lines.append("")

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_MD.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
