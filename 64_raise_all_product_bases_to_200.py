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
SUMMARY_JSON = SCRIPT_DIR / "raise_all_product_bases_to_200_summary.json"
SUMMARY_MD = SCRIPT_DIR / "raise_all_product_bases_to_200_summary.md"

ACCOUNT_MAP = {
    "601100": "6011",
    "60110000": "6011",
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
    "606400": "6064",
    "606800": "6068",
    "60680000": "6068",
    "607000": "607",
    "6071": "6071",
    "60970000": "6097",
    "626": "626",
    "6261": "626",
}

TARGETS = {
    "boulangerie": {
        "file": "base_produits_boulangerie_v1.json",
        "with_accounts": "base_produits_boulangerie_v1_with_accounts.json",
        "target_items": 200,
        "target_total": 200,
    },
    "btp": {
        "file": "base_produits_btp_v1.json",
        "with_accounts": "base_produits_btp_v1_with_accounts.json",
        "target_items": 155,
        "target_total": 200,
    },
    "transport": {
        "file": "base_produits_transport_v1.json",
        "with_accounts": "base_produits_transport_v1_with_accounts.json",
        "target_items": 133,
        "target_total": 200,
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


def build_active_item(helper, metier: str, row: dict, selection_source: str) -> dict:
    label = row["label"]
    stat = build_stat(label, row.get("account", ""), row.get("occurrences", 1))
    fake_pack_row = {"sample_account": row.get("account", "")}
    item = helper.build_product_item(metier, label, stat, fake_pack_row)
    item["compte_comptable"] = normalize_account(item.get("compte_comptable") or row.get("account", ""))
    item["selection_source"] = selection_source
    note = str(item.get("notes") or "").strip()
    suffix = f"Ajout cible 200 depuis {row.get('source','source_locale')}."
    item["notes"] = f"{note} | {suffix}".strip(" |")
    return item


def build_pending_item(helper, metier: str, row: dict, selection_source: str) -> dict:
    item = build_active_item(helper, metier, row, selection_source)
    item["validation_status"] = "a_controler_decision_comptable"
    item["validation_reason"] = "extension_volume_target_200"
    item["validation_note"] = (
        f"Ajout dans a_valider pour atteindre un volume >= 200 sur la base {metier}; "
        "a confirmer metierement avant activation pleine."
    )
    return item


def load_json(path: str) -> dict:
    return json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))


def save_json(path: str, payload: dict) -> None:
    (SCRIPT_DIR / path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(helper, value: str) -> str:
    return helper.normalize_text(str(value or ""))


def get_existing_keys(helper, payload: dict) -> set[str]:
    keys = set()
    for bucket in ("items", "a_valider"):
        for item in payload.get(bucket) or []:
            if isinstance(item, dict):
                keys.add(norm(helper, item.get("article_source") or ""))
    return keys


def integrate_payload(payload: dict, helper, active_items: list[dict], pending_items: list[dict], meta_key: str) -> dict:
    payload.setdefault("items", [])
    payload.setdefault("a_valider", [])
    existing = get_existing_keys(helper, payload)

    added_items = []
    added_pending = []

    for item in active_items:
        key = norm(helper, item.get("article_source") or "")
        if not key or key in existing:
            continue
        payload["items"].append(item)
        existing.add(key)
        added_items.append(item["article_source"])

    for item in pending_items:
        key = norm(helper, item.get("article_source") or "")
        if not key or key in existing:
            continue
        payload["a_valider"].append(item)
        existing.add(key)
        added_pending.append(item["article_source"])

    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(payload.get("items") or [])
    meta["a_valider_count"] = len(payload.get("a_valider") or [])
    meta["total_entries_count"] = meta["items_count"] + meta["a_valider_count"]
    meta[meta_key] = {
        "updated_at": helper.now_iso(),
        "added_items": len(added_items),
        "added_a_valider": len(added_pending),
        "added_item_labels": added_items,
        "added_a_valider_labels": added_pending,
    }
    return {
        "added_items": len(added_items),
        "added_a_valider": len(added_pending),
        "added_item_labels": added_items,
        "added_a_valider_labels": added_pending,
        "items_count": meta["items_count"],
        "a_valider_count": meta["a_valider_count"],
        "total_entries_count": meta["total_entries_count"],
    }


def boulangerie_candidates(helper, existing: set[str]) -> list[dict]:
    epi = load_json("base_produits_epicerie_v1.json")
    strong_keywords = {
        "farine", "levure", "beurre", "lait", "oeuf", "oeufs", "sucre", "chocolat",
        "cacao", "amande", "amandes", "noisette", "noisettes", "pistache", "vanille",
        "creme", "crème", "fleur d'oranger", "fleur", "oranger", "fecule", "fécule",
        "semoule", "brioche", "pain lait", "pain chocolat", "mascarpone", "miel",
        "glucose", "sirop", "sel", "sesame", "sésame",
    }
    stop_terms = {
        "nettoyant", "lessive", "liquide vaisselle", "vaisselle", "coca", "orangina",
        "oasis", "monster", "redbull", "heinken", "mirinda", "schweppes", "banane",
        "poulet", "veau", "boeuf", "bœuf", "halal", "gazole", "forfait",
    }
    rows = []
    for item in epi.get("items") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("article_source") or "").strip()
        account = str(item.get("compte_comptable") or "").strip()
        label_norm = norm(helper, label)
        if not label or label_norm in existing:
            continue
        if any(term in label_norm for term in stop_terms):
            continue
        if not any(term in label_norm for term in strong_keywords):
            continue
        score = 0
        for kw in strong_keywords:
            if kw in label_norm:
                score += 3 if kw in {"farine", "levure", "beurre", "lait", "sucre", "chocolat", "creme", "crème"} else 1
        if len(label) <= 35:
            score += 2
        rows.append({
            "label": label,
            "account": account,
            "occurrences": 1,
            "source": "base_produits_epicerie_v1.json",
            "score": score,
        })
    rows.sort(key=lambda row: (-row["score"], row["label"]))
    return rows


def btp_active_candidates(helper, existing: set[str]) -> list[dict]:
    keep = [
        "armature", "big bag", "casq chantier", "cable", "câble", "coffret", "fourreau",
        "platines", "gant", "gants", "petites fournitures", "technoce", "vis ",
        "balai", "manche", "rivet", "grillage", "pliage", "galva", "bache", "bloc ",
        "bastaing", "clou", "brosse", "ampoule", "applicateur", "robinetterie", "ciment",
        "ba13", "sable", "melange", "mélange", "securite", "sécurité", "fer", "acier",
        "joint", "disque", "tube", "pvc", "profil",
    ]
    stop = [
        "poulet", "veau", "boeuf", "bœuf", "agneau", "halal", "gazole", "carburant",
        "diesel", "forfait", "internet", "lavage offert", "pomme de terre", "banane",
        "coca ", "orangina", "monster", "redbull", "heinken", "mirinda", "schweppes",
        "utilisateur standard", "article non specifie", "article non spécifié",
        "abonnements", "option 5g", "taxe de sejour", "taxe de séjour", "nuits a", "nuits à",
        "repas", "cafe", "café", "acrobat", "electricite", "électricité",
    ]
    verbs = [
        "travaux de", "amenée-repli", "amenee-repli", "realisation", "réalisation",
        "dépose", "demontage", "démontage", "repose", "fo et pose", "pose de",
        "mission", "sous-traitance", "location", "jour de location",
    ]
    rows = []
    with (SCRIPT_DIR / "candidate_packs_metier/btp_top_500_cleaned_candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            account = str(row.get("sample_account") or "").strip()
            occurrences = int(row.get("invoice_count") or 1)
            label_norm = norm(helper, label)
            if not label or label_norm in existing:
                continue
            if any(term in label_norm for term in stop):
                continue
            if any(term in label_norm for term in verbs):
                continue
            if not any(term in label_norm for term in keep):
                continue
            rows.append({
                "label": label,
                "account": account,
                "occurrences": occurrences,
                "source": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
            })
    rows.sort(key=lambda row: (-row["occurrences"], row["label"]))
    return rows


def btp_pending_candidates(helper, existing: set[str]) -> list[dict]:
    stop = [
        "poulet", "veau", "boeuf", "bœuf", "agneau", "halal", "gazole", "carburant",
        "diesel", "forfait", "internet", "lavage offert", "pomme de terre", "banane",
        "coca ", "orangina", "monster", "redbull", "heinken", "mirinda", "schweppes",
        "utilisateur standard", "article non specifie", "article non spécifié",
        "abonnements", "option 5g", "taxe de sejour", "taxe de séjour", "nuits a", "nuits à",
        "repas", "cafe", "café", "acrobat", "voyage", "avantage client box",
    ]
    keep = [
        "micropieux", "cable", "câble", "fourreau", "coffret", "luminaires", "anémométres",
        "anemometres", "platines", "chantier", "bag", "armature", "casq", "gants",
        "fournitures", "valobat", "pmcb", "ciment", "sable", "bloc", "bastaing", "bache",
        "clou", "brosse", "ampoule", "applicateur", "ba13", "grillage", "pliage", "galva",
        "platre", "plâtre", "profil", "pvc", "disque", "tube", "robinetterie", "réseaux enterrés",
        "reseaux enterres", "mission g3", "sous-traitance", "sous traitance", "terrassement",
        "etancheite", "étanchéité", "filins acier", "outillage", "petites fournitures",
    ]
    rows = []
    with (SCRIPT_DIR / "candidate_packs_metier/btp_top_500_cleaned_candidates.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("article_source") or "").strip()
            account = str(row.get("sample_account") or "").strip()
            occurrences = int(row.get("invoice_count") or 1)
            label_norm = norm(helper, label)
            if not label or label_norm in existing:
                continue
            if any(term in label_norm for term in stop):
                continue
            if not any(term in label_norm for term in keep):
                continue
            rows.append({
                "label": label,
                "account": account,
                "occurrences": occurrences,
                "source": "candidate_packs_metier/btp_top_500_cleaned_candidates.csv",
            })
    rows.sort(key=lambda row: (-row["occurrences"], row["label"]))
    return rows


def transport_active_candidates(helper, existing: set[str]) -> list[dict]:
    keep = [
        "polisseuse", "gache", "kit de protection", "pose kit reparation optique",
        "pose kit réparation optique", "kit embrayage", "booster", "capuchon",
        "ecrou", "écrou", "degrippant", "chauffage du volant", "chauffage pour lave glaces",
        "chauffage pour lave-glaces", "element porteur", "graisse", "litre mobil",
        "masse a coller", "masse à coller", "jante", "pneu", "batterie", "capteur",
        "huile", "filtre", "joint", "garniture", "frein", "drustine",
    ]
    stop = [
        "forfait", "bbox", "communications", "abonnement", "operator", "operateur",
        "opérateur", "uber", "freebox", "tv by canal", "vos services", "vos abonnements",
        "apple", "disney", "internet", "repas", "banane", "coca", "oasis", "orangina",
        "redbull", "monster", "heinken", "mirinda", "schweppes", "fanta", "evian",
        "granini", "beurre", "chemise", "carven", "pantalon", "huile de tournesol",
    ]
    verbs = [
        "effectuer", "deposer", "déposer", "demonter", "démonter", "remplacer",
        "remplacement", "main d'oeuvre", "main d ceuvre", "maintenance", "supplement",
        "supplément", "peindre", "reparation", "réparation",
    ]
    payload = load_json("base_produits_vtc_v1.json")
    rows = []
    for bucket in ("items", "a_valider"):
        for item in payload.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("article_source") or "").strip()
            account = str(item.get("compte_comptable") or "").strip()
            occurrences = int(item.get("compte_comptable_match_score") or 1)
            label_norm = norm(helper, label)
            if not label or label_norm in existing:
                continue
            if any(term in label_norm for term in stop):
                continue
            if any(term in label_norm for term in verbs):
                continue
            if not any(term in label_norm for term in keep):
                continue
            rows.append({
                "label": label,
                "account": account,
                "occurrences": occurrences,
                "source": "base_produits_vtc_v1.json",
            })
    rows.sort(key=lambda row: (-row["occurrences"], row["label"]))
    return rows


def transport_pending_candidates(helper, existing: set[str]) -> list[dict]:
    keep = [
        "essai sur route", "test rapide", "garnitures de frein", "bloc optique", "bouclier",
        "pare-chocs", "pare chocs", "maintenance", "peinture", "optique", "roues",
        "pompe a liquide de refroidissement", "pompe à liquide de refroidissement",
        "compartiment moteur", "direction assistee", "direction assistée", "paliers",
        "suspension", "huile moteur", "filtre a huile", "filtre à huile", "liquide de refroidissement",
        "renovation", "rénovation", "frein", "batterie", "vidange", "main d'oeuvre",
        "atelier", "toit ouvrant", "carrosserie", "projecteur", "capteur", "trains avant",
        "portes", "roue complete", "roues completes",
    ]
    stop = [
        "forfait", "bbox", "communications", "abonnement", "operator", "operateur",
        "opérateur", "uber", "freebox", "tv by canal", "vos services", "vos abonnements",
        "apple", "disney", "internet", "repas", "banane", "coca", "oasis", "orangina",
        "redbull", "monster", "heinken", "mirinda", "schweppes", "fanta", "evian",
        "granini", "beurre", "chemise", "carven", "pantalon", "huile de tournesol",
    ]
    payload = load_json("base_produits_vtc_v1.json")
    rows = []
    for bucket in ("items", "a_valider"):
        for item in payload.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            label = str(item.get("article_source") or "").strip()
            account = str(item.get("compte_comptable") or "").strip()
            occurrences = int(item.get("compte_comptable_match_score") or 1)
            label_norm = norm(helper, label)
            if not label or label_norm in existing:
                continue
            if any(term in label_norm for term in stop):
                continue
            if not any(term in label_norm for term in keep):
                continue
            rows.append({
                "label": label,
                "account": account,
                "occurrences": occurrences,
                "source": "base_produits_vtc_v1.json",
            })
    rows.sort(key=lambda row: (-row["occurrences"], row["label"]))
    return rows


def take_rows(rows: list[dict], count: int, existing_keys: set[str], helper) -> list[dict]:
    selected = []
    local_existing = set(existing_keys)
    for row in rows:
        key = norm(helper, row.get("label", ""))
        if not key or key in local_existing:
            continue
        selected.append(row)
        local_existing.add(key)
        if len(selected) >= count:
            break
    return selected


def write_markdown(summary: dict) -> None:
    lines = ["# Mise à niveau vers 200", ""]
    for metier, data in summary.items():
        lines.append(f"## {metier}")
        lines.append(f"- items: {data['items_count']}")
        lines.append(f"- a_valider: {data['a_valider_count']}")
        lines.append(f"- total: {data['total_entries_count']}")
        lines.append(f"- ajouts items: {data['added_items']}")
        lines.append(f"- ajouts a_valider: {data['added_a_valider']}")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    helper = load_helper_module()
    summary = {}

    # Boulangerie: 200 actifs
    boul_cfg = TARGETS["boulangerie"]
    boul_payload = load_json(boul_cfg["file"])
    boul_existing = get_existing_keys(helper, boul_payload)
    boul_current_items = len(boul_payload.get("items") or [])
    boul_needed_items = max(0, boul_cfg["target_items"] - boul_current_items)
    boul_rows = take_rows(boulangerie_candidates(helper, boul_existing), boul_needed_items, boul_existing, helper)
    boul_active_items = [build_active_item(helper, "boulangerie", row, "raise_to_200_boulangerie_active_v1") for row in boul_rows]
    boul_result = integrate_payload(boul_payload, helper, boul_active_items, [], "raise_to_200_boulangerie_v1")
    save_json(boul_cfg["file"], boul_payload)
    boul_payload_wa = load_json(boul_cfg["with_accounts"])
    integrate_payload(
        boul_payload_wa,
        helper,
        [build_active_item(helper, "boulangerie", row, "raise_to_200_boulangerie_active_v1") for row in boul_rows],
        [],
        "raise_to_200_boulangerie_v1",
    )
    save_json(boul_cfg["with_accounts"], boul_payload_wa)
    summary["boulangerie"] = boul_result

    # BTP: actifs + a_valider jusqu'à 200 total
    btp_cfg = TARGETS["btp"]
    btp_payload = load_json(btp_cfg["file"])
    btp_existing = get_existing_keys(helper, btp_payload)
    btp_current_items = len(btp_payload.get("items") or [])
    btp_current_total = btp_current_items + len(btp_payload.get("a_valider") or [])
    btp_needed_items = max(0, btp_cfg["target_items"] - btp_current_items)
    btp_active_rows = take_rows(btp_active_candidates(helper, btp_existing), btp_needed_items, btp_existing, helper)
    btp_active_items = [build_active_item(helper, "btp", row, "raise_to_200_btp_active_v1") for row in btp_active_rows]
    btp_existing_after_active = btp_existing | {norm(helper, row["label"]) for row in btp_active_rows}
    btp_needed_total_after_active = max(0, btp_cfg["target_total"] - (btp_current_total + len(btp_active_rows)))
    btp_pending_rows = take_rows(btp_pending_candidates(helper, btp_existing_after_active), btp_needed_total_after_active, btp_existing_after_active, helper)
    btp_pending_items = [build_pending_item(helper, "btp", row, "raise_to_200_btp_pending_v1") for row in btp_pending_rows]
    btp_result = integrate_payload(btp_payload, helper, btp_active_items, btp_pending_items, "raise_to_200_btp_v1")
    save_json(btp_cfg["file"], btp_payload)
    btp_payload_wa = load_json(btp_cfg["with_accounts"])
    integrate_payload(
        btp_payload_wa,
        helper,
        [build_active_item(helper, "btp", row, "raise_to_200_btp_active_v1") for row in btp_active_rows],
        [build_pending_item(helper, "btp", row, "raise_to_200_btp_pending_v1") for row in btp_pending_rows],
        "raise_to_200_btp_v1",
    )
    save_json(btp_cfg["with_accounts"], btp_payload_wa)
    summary["btp"] = btp_result

    # Transport: actifs + a_valider jusqu'à 200 total
    transport_cfg = TARGETS["transport"]
    transport_payload = load_json(transport_cfg["file"])
    transport_existing = get_existing_keys(helper, transport_payload)
    transport_current_items = len(transport_payload.get("items") or [])
    transport_current_total = transport_current_items + len(transport_payload.get("a_valider") or [])
    transport_needed_items = max(0, transport_cfg["target_items"] - transport_current_items)
    transport_active_rows = take_rows(transport_active_candidates(helper, transport_existing), transport_needed_items, transport_existing, helper)
    transport_active_items = [build_active_item(helper, "transport", row, "raise_to_200_transport_active_v1") for row in transport_active_rows]
    transport_existing_after_active = transport_existing | {norm(helper, row["label"]) for row in transport_active_rows}
    transport_needed_total_after_active = max(0, transport_cfg["target_total"] - (transport_current_total + len(transport_active_rows)))
    transport_pending_rows = take_rows(
        transport_pending_candidates(helper, transport_existing_after_active),
        transport_needed_total_after_active,
        transport_existing_after_active,
        helper,
    )
    transport_pending_items = [build_pending_item(helper, "transport", row, "raise_to_200_transport_pending_v1") for row in transport_pending_rows]
    transport_result = integrate_payload(
        transport_payload,
        helper,
        transport_active_items,
        transport_pending_items,
        "raise_to_200_transport_v1",
    )
    save_json(transport_cfg["file"], transport_payload)
    transport_payload_wa = load_json(transport_cfg["with_accounts"])
    integrate_payload(
        transport_payload_wa,
        helper,
        [build_active_item(helper, "transport", row, "raise_to_200_transport_active_v1") for row in transport_active_rows],
        [build_pending_item(helper, "transport", row, "raise_to_200_transport_pending_v1") for row in transport_pending_rows],
        "raise_to_200_transport_v1",
    )
    save_json(transport_cfg["with_accounts"], transport_payload_wa)
    summary["transport"] = transport_result

    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
