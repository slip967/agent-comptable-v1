#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
SUMMARY_JSON = SCRIPT_DIR / "raise_charges_externes_to_200_summary.json"
SUMMARY_MD = SCRIPT_DIR / "raise_charges_externes_to_200_summary.md"

TARGET_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

ACTIVE_KEYWORDS = [
    "garde",
    "rsd",
    "interbev",
    "commission",
    "frais",
    "agios",
    "abonnement",
    "assurance",
    "loyer",
    "chauffage",
    "eau froide",
    "electricité",
    "électricité",
    "acheminement",
    "cspe",
    "cta",
    "ticgn",
    "transport",
    "deliveroo",
    "uber eats",
    "bimpli",
    "fleet",
    "livebox",
    "spotify",
    "forfait",
    "ticket fleet",
    "compteur eau",
    "provision eau",
    "cotis",
    "cotisation",
    "coti",
    "decro",
    "prestation emetteur",
    "prestation émetteur",
    "service assurance",
    "cyber",
    "visa business",
    "fructi",
    "securipro",
    "rythmeo",
    "carte bancaire",
    "rejet de prélèvement",
    "rejet de prelevement",
]

STOP_TERMS = [
    "coca",
    "fanta",
    "oasis",
    "orangina",
    "perrier",
    "cristaline",
    "cristali",
    "rioba",
    "granini",
    "lipton",
    "minute maid",
    "lait ",
    "sucre ",
    "banane",
    "orange grosse",
    "pomme de terre",
    "eau cristalline",
    "jus orange",
    "whisky",
    "sandwich",
    "kebab",
    "repas",
    "cafe",
    "café",
    "oeuf",
    "oeufs",
    "abats",
    "volaille",
    "viande",
    "beurre",
    "fleurs",
    "pantalon",
    "pochette",
    "fond plie",
    "emballage",
    "carton",
    "barquette",
    "plinthes",
]


def load_helper_module():
    spec = importlib.util.spec_from_file_location("triage_helper_module", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def build_stat(label: str, account: str, occurrences: int = 1) -> dict:
    stat = {
        "label_counter": Counter({label: 1}),
        "invoice_ids": set(),
        "partitions": set(),
        "account_counter": Counter(),
        "vat_counter": Counter(),
        "invoice_count_hint": int(occurrences or 1),
        "line_occurrences": int(occurrences or 1),
        "ape_context": set(),
    }
    if account:
        stat["account_counter"][str(account).strip()] += 1
    return stat


def load_existing_labels(path: str) -> set[str]:
    payload = json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))
    labels = set()
    for bucket in ("items", "a_valider"):
        for item in payload.get(bucket) or []:
            if isinstance(item, dict):
                labels.add(norm_text(item.get("article_source") or ""))
    return labels


def build_active_pool(existing: set[str]) -> list[dict]:
    pool = []
    with (SCRIPT_DIR / "candidate_packs_metier/charges_externes_top_500_cleaned_candidates.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            if not label:
                continue
            label_norm = norm_text(label)
            if label_norm in existing:
                continue
            if any(term in label_norm for term in STOP_TERMS):
                continue
            if not any(term in label_norm for term in ACTIVE_KEYWORDS):
                continue
            pool.append(
                {
                    "label": label,
                    "account": str(row.get("sample_account") or "").strip(),
                    "occurrences": int(row.get("invoice_count") or 1),
                    "source": "candidate_packs_metier/charges_externes_top_500_cleaned_candidates.csv",
                }
            )
    pool.sort(key=lambda row: (-row["occurrences"], row["label"]))
    return pool


def build_charge_item(helper, row: dict) -> dict:
    stat = build_stat(row["label"], row["account"], row["occurrences"])
    fake_pack_row = {"sample_account": row["account"]}
    item = helper.build_charge_item(row["label"], stat, fake_pack_row)
    item["selection_source"] = "raise_charges_externes_to_200_active_v1"
    note = str(item.get("notes") or "").strip()
    item["notes"] = f"{note} | Ajout cible 200 depuis {row['source']}".strip(" |")
    return item


def integrate_items(path: str, helper, new_items: list[dict]) -> dict:
    payload = json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))
    payload.setdefault("items", [])
    existing = {
        helper.normalize_text(str(item.get("article_source") or ""))
        for bucket in ("items", "a_valider")
        for item in (payload.get(bucket) or [])
        if isinstance(item, dict)
    }
    added = []
    for item in new_items:
        key = helper.normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            continue
        payload["items"].append(item)
        existing.add(key)
        added.append(item["article_source"])
    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(payload.get("items") or [])
    meta["a_valider_count"] = len(payload.get("a_valider") or [])
    meta["total_entries_count"] = meta["items_count"] + meta["a_valider_count"]
    meta["raise_charges_externes_to_200_v1"] = {
        "updated_at": helper.now_iso(),
        "added_items": len(added),
        "added_item_labels": added,
    }
    if path.startswith("base_charges_externes"):
        helper.refresh_charges_profile_enrichment(payload)
    (SCRIPT_DIR / path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "added_items": len(added),
        "added_item_labels": added,
        "items_count": meta["items_count"],
        "a_valider_count": meta["a_valider_count"],
        "total_entries_count": meta["total_entries_count"],
    }


def write_markdown(summary: dict) -> None:
    lines = ["# Mise à niveau charges externes vers 200", ""]
    for file_name, data in summary.items():
        lines.append(f"## {file_name}")
        lines.append(f"- items: {data['items_count']}")
        lines.append(f"- a_valider: {data['a_valider_count']}")
        lines.append(f"- total: {data['total_entries_count']}")
        lines.append(f"- ajouts items: {data['added_items']}")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    helper = load_helper_module()
    current_totals = {}
    for path in TARGET_FILES:
        payload = json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))
        current_totals[path] = len(payload.get("items") or []) + len(payload.get("a_valider") or [])

    lower_total = min(current_totals.values())
    needed = max(0, 200 - lower_total)

    existing = load_existing_labels("base_charges_externes_v1.json")
    pool = build_active_pool(existing)
    selected_rows = pool[:needed]
    new_items = [build_charge_item(helper, row) for row in selected_rows]

    summary = {}
    for path in TARGET_FILES:
        summary[path] = integrate_items(path, helper, new_items)

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
