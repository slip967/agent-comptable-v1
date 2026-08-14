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
SUMMARY_JSON = SCRIPT_DIR / "second_wave_metier_expansion_summary.json"
SUMMARY_MD = SCRIPT_DIR / "second_wave_metier_expansion_summary.md"

ACCOUNT_MAP = {
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "622600": "6226",
}

TARGETS = {
    "boucherie": {
        "candidate_csv": "candidate_packs_metier/boucherie_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_boucherie_v1.json",
            "base_produits_boucherie_v1_with_accounts.json",
        ],
        "max_add": 45,
        "min_invoice_count": 10,
        "allowed_account_prefixes": ("60", "601", "606", "607"),
        "allow_terms": (
            "poulet",
            "veau",
            "boeuf",
            "agneau",
            "mouton",
            "dinde",
            "volaille",
            "foie",
            "gesier",
            "fressure",
            "panse",
            "crepine",
            "queue",
            "cuisseau",
            "poitrine",
            "basse cote",
            "bavette",
            "rumsteack",
            "collier",
            "lapin",
            "testicule",
            "carre agneau",
            "abats",
            "carcasse",
            "pied",
        ),
        "deny_terms": (
            "pomme de terre",
            "gratin",
            "donut",
            "tender",
            "banane",
            "coca",
            "oasis",
            "lipton",
            "cristaline",
            "eau",
            "sucre",
            "farine",
            "lait",
            "beurre",
            "origine",
            "trace",
            " n abt",
            "sous vide",
            "hallal",
            "manutention",
            "interbev",
        ),
    },
    "restaurant": {
        "candidate_csv": "candidate_packs_metier/restaurant_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_restaurant_v1.json",
            "base_produits_restaurant_v1_with_accounts.json",
        ],
        "max_add": 70,
        "min_invoice_count": 8,
        "allowed_account_prefixes": ("60", "601", "606"),
        "allow_terms": (),
        "deny_terms": (
            "montant total",
            "montant net",
            "facturable",
            "spotify",
            "contribution tarifaire",
            "abonnement",
            "forfait",
            "boucherie",
            "commande ttc",
            "cta",
            "livraison du mois",
            "taxe",
            "taxes locales",
            "anti spam",
            "deliveroo",
            "achat non detaille",
            "paiements supplementaires",
            "obligations",
            "votre operateur",
            "fourniture d electricite",
            "avantage client box",
            "article non specifie",
            "gazole",
            "epicerie",
            "revenus en titre",
            "promotions sur les articles",
            "option energie verte",
        ),
    },
    "boulangerie": {
        "candidate_csv": "candidate_packs_metier/boulangerie_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_boulangerie_v1.json",
            "base_produits_boulangerie_v1_with_accounts.json",
        ],
        "max_add": 35,
        "min_invoice_count": 10,
        "allowed_account_prefixes": ("60", "601", "602", "606"),
        "allow_terms": (
            "farine",
            "beurre",
            "oeuf",
            "levure",
            "lait",
            "creme",
            "sucre",
            "eau",
            "chocolat",
            "croissant",
            "pain",
            "emmental",
            "chevre",
            "fromage",
            "saumon",
            "javel",
            "groseille",
            "banane",
            "lipton",
            "brioche",
            "pate",
            "fondant",
            "nappage",
            "mini pain",
        ),
        "deny_terms": (
            "veau",
            "poulet",
            "agneau",
            "boeuf",
            "mouton",
            "dinde",
            "volaille",
            "fressure",
            "panse",
            "queue",
            "cuisseau",
            "basse cote",
            "carcasse",
            "abats",
            "hallal",
            "halal",
            "vache",
            "bavette",
            "crepine",
        ),
    },
    "btp": {
        "candidate_csv": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_btp_v1.json",
            "base_produits_btp_v1_with_accounts.json",
        ],
        "max_add": 25,
        "min_invoice_count": 2,
        "allowed_account_prefixes": ("604", "606"),
        "allow_terms": (
            "beton",
            "coulage",
            "coffrage",
            "sciage",
            "poncage",
            "tuyaux",
            "pompe",
            "surfaquartz",
            "dallage",
            "helicoptere",
            "corex",
            "peinture",
            "carottage",
            "mortier",
            "ciment",
            "joint",
            "colle",
            "ragreage",
            "plancher",
            "dalle",
            "radier",
            "beton cellulaire",
            "rond a beton",
            "bloc coff",
            "poche a joint",
            "promacure",
        ),
        "deny_terms": (
            "poulet",
            "agneau",
            "veau",
            "boeuf",
            "dinde",
            "volaille",
            "forfait 150 go",
            "family",
            "e services",
            "repas",
            "gazole",
            "carburant",
            "diesel",
            "orange",
            "coca",
            "menu",
        ),
    },
    "transport": {
        "candidate_csv": "candidate_packs_metier/transport_top_500_cleaned_candidates.csv",
        "base_files": [
            "base_produits_transport_v1.json",
            "base_produits_transport_v1_with_accounts.json",
        ],
        "max_add": 8,
        "min_invoice_count": 2,
        "allowed_account_prefixes": ("606",),
        "allow_terms": (
            "gazole",
            "diesel",
            "carburant",
            "adblue",
            "lavage",
            "b10",
        ),
        "deny_terms": (
            "forfait",
            "internet",
            "bbox",
            "box",
            "norton",
            "sms",
            "international",
            "option",
            "multi tv",
            "securite",
            "repas",
            "banane",
            "menu",
            "abonnement",
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


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def load_partition_ape_map() -> dict[str, str]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    return {
        str(part.get("partition_prefix") or "").strip(): str(part.get("client_ape") or "").strip()
        for part in (report.get("partitions") or [])
        if str(part.get("partition_prefix") or "").strip()
    }


def load_current_labels(base_path: Path, helper) -> set[str]:
    payload = json.loads(base_path.read_text(encoding="utf-8-sig"))
    labels = set()
    for bucket_name in ("items", "a_valider"):
        for item in payload.get(bucket_name) or []:
            if isinstance(item, dict):
                key = helper.normalize_text(str(item.get("article_source") or ""))
                if key:
                    labels.add(key)
    return labels


def candidate_allowed(metier: str, row: dict, rule: dict, helper) -> tuple[bool, str]:
    label = str(row.get("article_source") or "").strip()
    norm = helper.normalize_text(label)
    if not norm:
        return False, "empty_label"

    invoice_count = int(row.get("invoice_count") or 0)
    if invoice_count < int(rule["min_invoice_count"]):
        return False, "invoice_count_too_low"

    account = str(row.get("sample_account") or "").strip()
    if account and not account.startswith(rule["allowed_account_prefixes"]):
        return False, "account_prefix_not_allowed"

    if contains_any(norm, rule["deny_terms"]):
        return False, "deny_term"

    if rule["allow_terms"] and not contains_any(norm, rule["allow_terms"]):
        return False, "missing_allow_term"

    return True, "ok"


def normalize_account(account: str) -> str:
    account = str(account or "").strip()
    return ACCOUNT_MAP.get(account, account)


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


def integrate_items_with_meta(base_path: Path, new_items: list[dict], meta_key: str, helper) -> tuple[int, int]:
    payload = json.loads(base_path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    existing = {
        helper.normalize_text(str(item.get("article_source") or ""))
        for item in items
        if isinstance(item, dict)
    }
    added = 0
    skipped = 0
    for item in new_items:
        key = helper.normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            skipped += 1
            continue
        items.append(item)
        existing.add(key)
        added += 1

    payload["items"] = items
    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(items)
    meta[meta_key] = {
        "updated_at": helper.now_iso(),
        "added_items": added,
        "skipped_existing": skipped,
        "selection_mode": "auto_filtered_second_wave",
    }
    base_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added, skipped


def main() -> int:
    helper = load_helper_module()
    partition_ape_map = load_partition_ape_map()
    summary: dict[str, dict] = {}
    markdown_lines = [
        "# Second Wave Metier Expansion Summary",
        "",
        "Date: 2026-04-30",
        "",
        "Selection mode: auto-filtered second wave from cleaned candidate packs.",
        "",
    ]

    for metier, rule in TARGETS.items():
        candidate_path = SCRIPT_DIR / rule["candidate_csv"]
        rows = list(csv.DictReader(candidate_path.open(encoding="utf-8-sig", newline="")))
        current_labels = load_current_labels(SCRIPT_DIR / rule["base_files"][0], helper)

        selected_rows: list[dict] = []
        rejected_reasons = Counter()

        for row in rows:
            key = helper.normalize_text(str(row.get("article_source") or ""))
            if not key or key in current_labels:
                rejected_reasons["already_present"] += 1
                continue
            allowed, reason = candidate_allowed(metier, row, rule, helper)
            if not allowed:
                rejected_reasons[reason] += 1
                continue
            selected_rows.append(row)
            current_labels.add(key)
            if len(selected_rows) >= int(rule["max_add"]):
                break

        new_items = []
        labels = []
        for row in selected_rows:
            stat = build_fake_stat(row, partition_ape_map)
            item = helper.build_product_item(metier, str(row.get("article_source") or "").strip(), stat, row)
            item["compte_comptable"] = normalize_account(item.get("compte_comptable") or "")
            item["notes"] = (
                f"{item.get('notes') or ''} | "
                "Ajout auto seconde vague depuis candidate pack nettoye avec filtre metier strict."
            ).strip()
            item["selection_source"] = "auto_filtered_second_wave_v1"
            new_items.append(item)
            labels.append(
                {
                    "article_source": item["article_source"],
                    "invoice_count": int(row.get("invoice_count") or 0),
                    "sample_account": normalize_account(str(row.get("sample_account") or "").strip()),
                }
            )

        file_results = []
        for file_name in rule["base_files"]:
            added, skipped = integrate_items_with_meta(
                SCRIPT_DIR / file_name,
                new_items,
                "auto_filtered_second_wave_v1",
                helper,
            )
            file_results.append({"file": file_name, "added": added, "skipped_existing": skipped})

        summary[metier] = {
            "selected_count": len(labels),
            "selected_labels": labels,
            "rejected_reasons": dict(rejected_reasons),
            "files": file_results,
        }

        markdown_lines.append(f"## {metier}")
        markdown_lines.append("")
        markdown_lines.append(f"- added_candidates: `{len(labels)}`")
        markdown_lines.append(f"- rejected_reasons: `{dict(rejected_reasons)}`")
        for file_result in file_results:
            markdown_lines.append(
                f"- {file_result['file']}: added=`{file_result['added']}` skipped=`{file_result['skipped_existing']}`"
            )
        if labels:
            markdown_lines.append("- selected_labels:")
            for label in labels:
                markdown_lines.append(
                    f"  - `{label['article_source']}` | invoices=`{label['invoice_count']}` | account=`{label['sample_account']}`"
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
