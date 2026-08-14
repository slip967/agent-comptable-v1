#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
SUMMARY_JSON = SCRIPT_DIR / "eighth_wave_transport_vtc_reference_summary.json"
SUMMARY_MD = SCRIPT_DIR / "eighth_wave_transport_vtc_reference_summary.md"

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
    "626": "626",
    "6261": "626",
}

TRANSPORT_SOURCES = [
    "base_produits_vtc_v1.json",
    "v1_839181104_reference_base_exploitation_v1.json",
    "v1_844082156_reference_base_exploitation_v1.json",
]

TRANSPORT_TARGET_FILES = [
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
]

TRANSPORT_LABELS = (
    "GALET DE RENVOI",
    "SYSTEME REGULATION D AIR",
    "TRAVERSE",
    "SUPPORT",
    "CADRE DE CALANDRE",
    "POMPE A EAU",
    "GARNITURE FREIN A DI",
    "FILTRE POUSSIERE",
    "JEU PCES GARNITURE FREIN",
    "ANTIGEL ROUGE 1L (PDP)",
    "ANTIGEL ROUGE 5L (PDP)",
    "COURROIE TRAPEZOIDALE",
    "TENDEUR DE COURROIE",
    "ADBLUE vraC",
    "ADBLUE 10L (PDP)",
    "CAPUCHON DE VALVE",
    "ELEMENT DE FILTRE D'HUILE",
    "GRAISSE NOIRE CARDAN",
    "RIVET",
    "RIVET SYSTEME REGULATION D AIR",
    "AILE AVANT",
    "BOUCHON",
    "GRILLE DE PROTECTION",
    "TUBE ENTRETOISE",
    "BATTERIE DE DEMARRAGE",
    "Radiateur de refroidissement",
)

BTP_SOURCE = "candidate_packs_metier/btp_top_500_cleaned_candidates.csv"
BTP_TARGET_FILES = [
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
]
BTP_LABELS = (
    "PALETTE LUSSIANA",
    "PALETTE CONSIGNE SLM OPL SPC",
)


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
        stat["account_counter"][normalize_account(account)] += 1
    return stat


def load_transport_rows() -> dict[str, dict]:
    row_map: dict[str, dict] = {}

    for source_name in TRANSPORT_SOURCES:
        path = SCRIPT_DIR / source_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))

        if source_name.startswith("base_produits_vtc"):
            for bucket_name in ("items", "a_valider"):
                for item in payload.get(bucket_name) or []:
                    if not isinstance(item, dict):
                        continue
                    label = str(item.get("article_source") or "").strip()
                    if not label or label in row_map:
                        continue
                    row_map[label] = {
                        "label": label,
                        "account": str(item.get("compte_comptable") or "").strip(),
                        "occurrences": int(item.get("compte_comptable_match_score") or 1),
                        "source": source_name,
                    }
        else:
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                source_labels = item.get("source_labels_top") or []
                label = ""
                if source_labels:
                    first = source_labels[0]
                    label = str(first[0] if isinstance(first, list) else first).strip()
                if not label or label in row_map:
                    continue
                row_map[label] = {
                    "label": label,
                    "account": str(item.get("proposed_account") or "").strip(),
                    "occurrences": int(item.get("occurrences") or 1),
                    "source": source_name,
                }
    return row_map


def load_btp_rows() -> dict[str, dict]:
    import csv

    path = SCRIPT_DIR / BTP_SOURCE
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            if label and label not in rows:
                rows[label] = {
                    "label": label,
                    "account": str(row.get("sample_account") or "").strip(),
                    "occurrences": int(row.get("invoice_count") or 1),
                    "source": BTP_SOURCE,
                }
    return rows


def build_transport_items(helper, row_map: dict[str, dict]) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in TRANSPORT_LABELS:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_stat(label, row["account"], row["occurrences"])
        fake_pack_row = {"sample_account": row["account"]}
        item = helper.build_product_item("transport", label, stat, fake_pack_row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or row["account"])
        item["selection_source"] = "manual_eighth_wave_vtc_reference_v1"
        note = str(item.get("notes") or "").strip()
        suffix = f"Ajout manuel 8e vague depuis {row['source']}."
        item["notes"] = f"{note} | {suffix}".strip(" |")
        items.append(item)
    return items, missing


def build_btp_items(helper, row_map: dict[str, dict]) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in BTP_LABELS:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_stat(label, row["account"], row["occurrences"])
        fake_pack_row = {"sample_account": row["account"]}
        item = helper.build_product_item("btp", label, stat, fake_pack_row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or row["account"])
        item["selection_source"] = "manual_eighth_wave_btp_v1"
        note = str(item.get("notes") or "").strip()
        suffix = f"Ajout manuel 8e vague depuis {row['source']}."
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

    transport_row_map = load_transport_rows()
    transport_items, transport_missing = build_transport_items(helper, transport_row_map)
    transport_results = []
    for file_name in TRANSPORT_TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_items(payload, transport_items, helper, "manual_eighth_wave_vtc_reference_v1")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        transport_results.append({"file": file_name, **result})

    btp_row_map = load_btp_rows()
    btp_items, btp_missing = build_btp_items(helper, btp_row_map)
    btp_results = []
    for file_name in BTP_TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_items(payload, btp_items, helper, "manual_eighth_wave_btp_v1")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        btp_results.append({"file": file_name, **result})

    summary = {
        "transport": {
            "requested_active": list(TRANSPORT_LABELS),
            "missing": transport_missing,
            "files": transport_results,
        },
        "btp": {
            "requested_active": list(BTP_LABELS),
            "missing": btp_missing,
            "files": btp_results,
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Eighth Wave Transport / BTP Summary",
        "",
        "Selection mode: transport from VTC/reference local sources, plus last plausible BTP labels.",
        "",
        "## transport",
        "",
        f"- requested_active: `{len(TRANSPORT_LABELS)}`",
    ]
    if transport_missing:
        lines.append(f"- missing: `{transport_missing}`")
    for result in transport_results:
        lines.append(
            f"- {result['file']}: items_added=`{result['added']}` skipped_existing=`{result['skipped_existing']}`"
        )
    lines.extend(
        [
            "",
            "## btp",
            "",
            f"- requested_active: `{len(BTP_LABELS)}`",
        ]
    )
    if btp_missing:
        lines.append(f"- missing: `{btp_missing}`")
    for result in btp_results:
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
