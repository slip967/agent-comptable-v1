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
SUMMARY_JSON = SCRIPT_DIR / "tenth_wave_transport_btp_summary.json"
SUMMARY_MD = SCRIPT_DIR / "tenth_wave_transport_btp_summary.md"

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
    "60225": "6025",
    "6058": "6058",
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

TRANSPORT_SOURCE_FILES = [
    "base_produits_vtc_v1.json",
    "v1_824332985_reference_base_exploitation_v1.json",
    "v1_839181104_reference_base_exploitation_v1.json",
]
TRANSPORT_TARGET_FILES = [
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
]
TRANSPORT_LABELS = (
    "KIT DE REPARATION SUPPORT BAGUETTE ENJOLIVEUSE",
    "022 H.MOT 229.71 1 L OW20/HUILE M CSVP",
    "J.PC.CARTOUCH.FILTR.HUILE",
    "JOINT TORIQUE, 39.8X2.2",
    "REPARPNEU",
    "RONDELLE DE BOUCHON DE",
    "SILENTBLOC",
    "VIS DE FERMETURE TS CART. FILTRE A HUILE",
    "120186/CONSOLE TRAVERSE",
    "CAPTEUR D'USURE PLAQUETTE",
    "GARNITURE DE FREIN",
    "GARNITURE FREINA DISQUE",
    "OML MUL NETT. FREIN 50",
)

BTP_SOURCE_CSV = "candidate_packs_metier/btp_top_500_cleaned_candidates.csv"
BTP_TARGET_FILES = [
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
]
BTP_LABELS = (
    "PLIAGE ALUMINIUM 10/10 ANODISE + PERFO (DETAIL 5) Long : 2000 Dev : 320",
    "ADH PVC ORANGE NOVIPRO (3) 33MX50MM",
    "CHAINE ACIER LONGUEUR 1000MM 8MM DIAM 8016EURD",
    "CHAINE ACIER LONGUEUR 1500MM 8MM DIAM 8017EURD",
    "Couteau à enduire type américain manche plastique inox 150mm noir",
    "Gants anti-dérapant Netceed 2.1.3.1 Taille 8",
    "Lot 6 p gants easy grip t9 Réf.89163",
    "PLIAGE ALUMINIUM 10/10 ANODISE + PERFO (DETAIL 2 LARGEUR 350 Long : 2000 Dev : 442 Eco contribution",
    "PLIAGE ALUMINIUM 10/10 ANODISE + PINCE COUDE (DETAIL 5 Long : 2000 Dev : 170 Eco contribution",
    "PLIAGE ALUMINIUM 10/10 ANODISE + PLI ECRASE (DETAIL 5) Long : 2000 Dev : 170",
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
    rows: dict[str, dict] = {}
    for source_name in TRANSPORT_SOURCE_FILES:
        payload = json.loads((SCRIPT_DIR / source_name).read_text(encoding="utf-8-sig"))
        if source_name.startswith("base_produits_vtc"):
            for bucket_name in ("items", "a_valider"):
                for item in payload.get(bucket_name) or []:
                    if not isinstance(item, dict):
                        continue
                    label = str(item.get("article_source") or "").strip()
                    if not label or label in rows:
                        continue
                    rows[label] = {
                        "label": label,
                        "account": str(item.get("compte_comptable") or "").strip(),
                        "occurrences": int(item.get("compte_comptable_match_score") or 1),
                        "source": source_name,
                    }
            continue

        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            labels = item.get("source_labels_top") or []
            label = ""
            if labels:
                first = labels[0]
                label = str(first[0] if isinstance(first, list) else first).strip()
            if not label or label in rows:
                continue
            rows[label] = {
                "label": label,
                "account": str(item.get("proposed_account") or "").strip(),
                "occurrences": int(item.get("occurrences") or 1),
                "source": source_name,
            }
    return rows


def load_btp_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (SCRIPT_DIR / BTP_SOURCE_CSV).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            if not label or label in rows:
                continue
            rows[label] = {
                "label": label,
                "account": str(row.get("sample_account") or "").strip(),
                "occurrences": int(row.get("invoice_count") or 1),
                "source": BTP_SOURCE_CSV,
            }
    return rows


def build_items(helper, labels: tuple[str, ...], row_map: dict[str, dict], metier: str, selection_source: str) -> tuple[list[dict], list[str]]:
    items = []
    missing = []
    for label in labels:
        row = row_map.get(label)
        if row is None:
            missing.append(label)
            continue
        stat = build_stat(label, row["account"], row["occurrences"])
        fake_pack_row = {"sample_account": row["account"]}
        item = helper.build_product_item(metier, label, stat, fake_pack_row)
        item["compte_comptable"] = normalize_account(item.get("compte_comptable") or row["account"])
        item["selection_source"] = selection_source
        note = str(item.get("notes") or "").strip()
        suffix = f"Ajout manuel 10e vague depuis {row['source']}."
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


def write_markdown(summary: dict) -> None:
    lines = [
        "# 10e vague transport/btp",
        "",
        "## Transport",
        f"- demandes: {len(summary['transport']['requested_active'])}",
        f"- manquants: {len(summary['transport']['missing'])}",
    ]
    for result in summary["transport"]["files"]:
        lines.append(f"- {result['file']}: +{result['added']} ajoutes, {result['skipped_existing']} deja presents")

    lines.extend([
        "",
        "## BTP",
        f"- demandes: {len(summary['btp']['requested_active'])}",
        f"- manquants: {len(summary['btp']['missing'])}",
    ])
    for result in summary["btp"]["files"]:
        lines.append(f"- {result['file']}: +{result['added']} ajoutes, {result['skipped_existing']} deja presents")

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    helper = load_helper_module()

    transport_items, transport_missing = build_items(
        helper,
        TRANSPORT_LABELS,
        load_transport_rows(),
        "transport",
        "manual_tenth_wave_transport_v1",
    )
    btp_items, btp_missing = build_items(
        helper,
        BTP_LABELS,
        load_btp_rows(),
        "btp",
        "manual_tenth_wave_btp_v1",
    )

    summary = {
        "transport": {
            "requested_active": list(TRANSPORT_LABELS),
            "missing": transport_missing,
            "files": [],
        },
        "btp": {
            "requested_active": list(BTP_LABELS),
            "missing": btp_missing,
            "files": [],
        },
    }

    for file_name in TRANSPORT_TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_items(payload, transport_items, helper, "manual_tenth_wave_transport_v1")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["transport"]["files"].append({"file": file_name, **result})

    for file_name in BTP_TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        result = integrate_items(payload, btp_items, helper, "manual_tenth_wave_btp_v1")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["btp"]["files"].append({"file": file_name, **result})

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
