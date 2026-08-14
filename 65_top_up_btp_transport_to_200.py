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
SUMMARY_JSON = SCRIPT_DIR / "top_up_btp_transport_to_200_summary.json"
SUMMARY_MD = SCRIPT_DIR / "top_up_btp_transport_to_200_summary.md"

ACCOUNT_MAP = {
    "6021": "6021",
    "6022": "6022",
    "6058": "6058",
    "606": "606",
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "606300": "6063",
    "60630000": "6063",
    "606800": "6068",
    "60680000": "6068",
    "607000": "607",
    "60970000": "6097",
    "626": "626",
    "6261": "626",
}

BTP_LABELS = (
    "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
    "Amenée-repli de l'atelier de l'injection",
    "Electricité",
    "Fo et pose de grosse boites de dérivation",
    "Jour de location",
    "TA-E 80X60 W0 GOUL DISTRI AU METRE",
    "Anémométre pour store - suivant CCTP",
    "Ascenseur",
    "BAST SAP/EPI TRCL2 63X160 3M00",
    "BOB. PROTECT. ULTIBAT 75M.",
    "Campagne de test d'arrachement",
    "CONTRE PLAQUE FILME PLUS 15MM 250X125X15MM",
    "CROISILLONS EN T 3MM 250 PIECES",
)

TRANSPORT_LABELS = (
    "Visite technique périodique",
    "NCS, MO-S",
    "RENOV.ULTIME MEGUIARS 473 ML (PROMO)",
    "ULTIM.BRILLANCE MEGUIARS 709ML (PROMO)",
    "VIS DE FERMETURE",
    "022 H.MOT 229-52 v rac 5W30",
    "022 H.MOT 229-52 vrac 5W30",
    "120186/CONSOLE",
    "Cloison sous aile avant gauche remplacer",
    "H.MOT 229.5 1L OW40",
    "JEU DE CART. FILTR. CARB",
    "Lavage express",
    "Polish",
    "RAIL DE RECOUVREMENT",
    "RESSORT",
    "Remplacer la pile de la clé-émetteur 022 PILE 2032",
    "TUBE DE GUIDAGE",
    "TUBE DE TROP-PLEIN",
    "VIS",
    "VIS 6 PANS AVEC BRIDE",
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


def build_pending_item(helper, metier: str, row: dict, source_tag: str) -> dict:
    stat = build_stat(row["label"], row["account"], row["occurrences"])
    fake_pack_row = {"sample_account": row["account"]}
    item = helper.build_product_item(metier, row["label"], stat, fake_pack_row)
    item["compte_comptable"] = normalize_account(item.get("compte_comptable") or row["account"])
    item["selection_source"] = source_tag
    item["validation_status"] = "a_controler_decision_comptable"
    item["validation_reason"] = "top_up_target_200"
    item["validation_note"] = "Ajout final en a_valider pour atteindre le seuil de 200 references."
    note = str(item.get("notes") or "").strip()
    item["notes"] = f"{note} | Top-up final cible 200 depuis {row['source']}".strip(" |")
    return item


def load_btp_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with (SCRIPT_DIR / "candidate_packs_metier/btp_top_500_cleaned_candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            if not label or label in rows:
                continue
            rows[label] = {
                "label": label,
                "account": str(row.get("sample_account") or "").strip(),
                "occurrences": int(row.get("invoice_count") or 1),
                "source": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
            }
    return rows


def load_transport_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    payload = json.loads((SCRIPT_DIR / "base_produits_vtc_v1.json").read_text(encoding="utf-8-sig"))
    for bucket in ("items", "a_valider"):
        for item in payload.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("article_source") or "").strip()
            if not label or label in rows:
                continue
            rows[label] = {
                "label": label,
                "account": str(item.get("compte_comptable") or "").strip(),
                "occurrences": int(item.get("compte_comptable_match_score") or 1),
                "source": "base_produits_vtc_v1.json",
            }
    return rows


def integrate_pending(path: str, helper, items: list[dict], meta_key: str) -> dict:
    payload = json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))
    payload.setdefault("a_valider", [])
    existing = {
        helper.normalize_text(str(item.get("article_source") or ""))
        for bucket in ("items", "a_valider")
        for item in (payload.get(bucket) or [])
        if isinstance(item, dict)
    }
    added = []
    for item in items:
        key = helper.normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            continue
        payload["a_valider"].append(item)
        existing.add(key)
        added.append(item["article_source"])
    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(payload.get("items") or [])
    meta["a_valider_count"] = len(payload.get("a_valider") or [])
    meta["total_entries_count"] = meta["items_count"] + meta["a_valider_count"]
    meta[meta_key] = {
        "updated_at": helper.now_iso(),
        "added_a_valider": len(added),
        "added_a_valider_labels": added,
    }
    (SCRIPT_DIR / path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "added_a_valider": len(added),
        "added_a_valider_labels": added,
        "items_count": meta["items_count"],
        "a_valider_count": meta["a_valider_count"],
        "total_entries_count": meta["total_entries_count"],
    }


def write_markdown(summary: dict) -> None:
    lines = ["# Top-up final vers 200", ""]
    for metier, data in summary.items():
        lines.append(f"## {metier}")
        lines.append(f"- items: {data['items_count']}")
        lines.append(f"- a_valider: {data['a_valider_count']}")
        lines.append(f"- total: {data['total_entries_count']}")
        lines.append(f"- ajout a_valider: {data['added_a_valider']}")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    helper = load_helper_module()
    btp_rows = load_btp_rows()
    transport_rows = load_transport_rows()

    btp_pending = [
        build_pending_item(helper, "btp", btp_rows[label], "top_up_target_200_btp_v1")
        for label in BTP_LABELS
        if label in btp_rows
    ]
    transport_pending = [
        build_pending_item(helper, "transport", transport_rows[label], "top_up_target_200_transport_v1")
        for label in TRANSPORT_LABELS
        if label in transport_rows
    ]

    summary = {
        "btp": integrate_pending("base_produits_btp_v1.json", helper, btp_pending, "top_up_target_200_btp_v1"),
        "transport": integrate_pending("base_produits_transport_v1.json", helper, transport_pending, "top_up_target_200_transport_v1"),
    }
    integrate_pending("base_produits_btp_v1_with_accounts.json", helper, btp_pending, "top_up_target_200_btp_v1")
    integrate_pending("base_produits_transport_v1_with_accounts.json", helper, transport_pending, "top_up_target_200_transport_v1")

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
