#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
SUMMARY_JSON = SCRIPT_DIR / "reclass_transport_btp_a_valider_to_charges_summary.json"
SUMMARY_MD = SCRIPT_DIR / "reclass_transport_btp_a_valider_to_charges_summary.md"

TARGETS = {
    "transport": {
        "product_file": "base_produits_transport_v1.json",
        "charges_file": "base_charges_externes_v1.json",
        "labels": (
            "Forfait Client B&You 260Go 5G",
            "Communications vers l'international",
            "Forfait Client B&You 230Go",
            "Forfait Spécial client 350Go 5G Av. smartphone",
            "Solutions Sécurité Smartphone avec Norton",
            "Avantage Internet 60Go",
            "Forfait Sensation 150Go 5G Avantages Smartphone",
            "Option multi-SIM Internet",
            "Avantage Internet 80Go",
            "Bbox - location équipement (du 02/07 au 01/08)",
            "Bbox - location équipement (du 02/09 au 01/10)",
            "Pack sécurité Norton",
            "Multi-TV FTTH (du 02/07 au 01/08)",
            "Multi-TV FTTH (du 02/09 au 01/10)",
            "Option Week-end internet illimité",
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
    "transport_with_accounts": {
        "product_file": "base_produits_transport_v1_with_accounts.json",
        "charges_file": "base_charges_externes_v1_with_accounts.json",
        "labels": (
            "Forfait Client B&You 260Go 5G",
            "Communications vers l'international",
            "Forfait Client B&You 230Go",
            "Forfait Spécial client 350Go 5G Av. smartphone",
            "Solutions Sécurité Smartphone avec Norton",
            "Avantage Internet 60Go",
            "Forfait Sensation 150Go 5G Avantages Smartphone",
            "Option multi-SIM Internet",
            "Avantage Internet 80Go",
            "Bbox - location équipement (du 02/07 au 01/08)",
            "Bbox - location équipement (du 02/09 au 01/10)",
            "Pack sécurité Norton",
            "Multi-TV FTTH (du 02/07 au 01/08)",
            "Multi-TV FTTH (du 02/09 au 01/10)",
            "Option Week-end internet illimité",
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
        "product_file": "base_produits_btp_v1.json",
        "charges_file": "base_charges_externes_v1.json",
        "labels": (
            "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
            "Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau",
            "Amenée-repli de l'atelier de forage des micropieux",
            "Implantation des micropieux",
        ),
    },
    "btp_with_accounts": {
        "product_file": "base_produits_btp_v1_with_accounts.json",
        "charges_file": "base_charges_externes_v1_with_accounts.json",
        "labels": (
            "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
            "Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau",
            "Amenée-repli de l'atelier de forage des micropieux",
            "Implantation des micropieux",
        ),
    },
}


def load_rules_module():
    spec = importlib.util.spec_from_file_location("triage_rules_module", RULES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {RULES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(module, value: str) -> str:
    return module.normalize_text(str(value or ""))


def build_charge_item(module, source_item: dict, origin: str) -> dict:
    article_source = str(source_item.get("article_source") or "").strip()
    compte = str(source_item.get("compte_comptable") or "").strip()
    charge_item = deepcopy(source_item)
    charge_item["categorie"] = "charges_externes"
    charge_item["fournisseur_type"] = "service"

    if origin.startswith("transport"):
        classification = module.classify_charge(article_source, compte)
        charge_item["sous_profil"] = classification["sous_profil"]
        charge_item["nature_charge"] = classification["nature_charge"]
        charge_item["profil_facturation"] = classification["profil_facturation"]
        charge_item["profil_facturation_champs"] = module.default_charges_champs(
            classification["profil_facturation"]
        )
        charge_item["sous_categorie"] = module.CHARGES_SOUS_CATEGORIE_MAP.get(
            classification["sous_profil"], "charges_generales"
        )
        charge_item["classification_reason"] = classification["classification_reason"]
        charge_item["classification_version"] = "charges_externes_rules_v1_transport_reclass"
    else:
        charge_item["sous_profil"] = "autres_charges_externes"
        charge_item["nature_charge"] = "prestation"
        charge_item["profil_facturation"] = "intervention_ponctuelle"
        charge_item["profil_facturation_champs"] = module.default_charges_champs("intervention_ponctuelle")
        charge_item["sous_categorie"] = module.CHARGES_SOUS_CATEGORIE_MAP.get(
            "autres_charges_externes", "charges_generales"
        )
        charge_item["classification_reason"] = "manual_reclass:prestation_technique_chantier"
        charge_item["classification_version"] = "charges_externes_rules_v1_btp_reclass"

    note = str(charge_item.get("notes") or "").strip()
    suffix = (
        "Reclassé depuis a_valider base_produits_transport vers charges_externes/telecom_et_abonnements."
        if origin.startswith("transport")
        else "Reclassé depuis a_valider base_produits_btp vers charges_externes/prestation_chantier."
    )
    charge_item["notes"] = f"{note} | {suffix}".strip(" |")
    charge_item["reclassement_source"] = "transport_btp_a_valider_to_charges_v1"
    charge_item["origine_base_metier"] = "transport" if origin.startswith("transport") else "btp"
    return charge_item


def process_target(module, key: str, cfg: dict) -> dict:
    product_path = SCRIPT_DIR / cfg["product_file"]
    charges_path = SCRIPT_DIR / cfg["charges_file"]
    labels = set(cfg["labels"])

    product_payload = json.loads(product_path.read_text(encoding="utf-8"))
    charges_payload = json.loads(charges_path.read_text(encoding="utf-8"))

    product_a_valider = product_payload.get("a_valider") or []
    charges_items = charges_payload.get("items") or []

    target_keys = {normalize(module, label): label for label in labels}
    charges_existing = {
        normalize(module, str(item.get("article_source") or "")) for item in charges_items if isinstance(item, dict)
    }

    kept_a_valider = []
    removed_from_a_valider = 0
    added_to_charges = 0
    already_in_charges = 0
    moved_labels = []

    for item in product_a_valider:
        if not isinstance(item, dict):
            kept_a_valider.append(item)
            continue
        label = str(item.get("article_source") or "").strip()
        norm = normalize(module, label)
        if norm not in target_keys:
            kept_a_valider.append(item)
            continue

        removed_from_a_valider += 1
        moved_labels.append(label)

        if norm in charges_existing:
            already_in_charges += 1
            continue

        charge_item = build_charge_item(module, item, key)
        charges_items.append(charge_item)
        charges_existing.add(norm)
        added_to_charges += 1

    product_payload["a_valider"] = kept_a_valider
    product_payload.setdefault("meta", {})
    product_payload["meta"]["items_count"] = len(product_payload.get("items") or [])
    product_payload["meta"]["a_valider_count"] = len(kept_a_valider)
    product_payload["meta"]["transport_btp_a_valider_reclass_v1"] = {
        "updated_at": module.now_iso(),
        "removed_from_a_valider": removed_from_a_valider,
        "moved_labels": moved_labels,
        "target": charges_path.name,
    }

    charges_payload["items"] = charges_items
    charges_payload.setdefault("meta", {})
    charges_payload["meta"]["items_count"] = len(charges_items)
    charges_payload["meta"]["transport_btp_a_valider_reclass_v1"] = {
        "updated_at": module.now_iso(),
        "added_from_product_a_valider": added_to_charges,
        "already_present": already_in_charges,
        "source_product_file": product_path.name,
        "moved_labels": moved_labels,
    }
    module.refresh_charges_profile_enrichment(charges_payload)

    product_path.write_text(json.dumps(product_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    charges_path.write_text(json.dumps(charges_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "key": key,
        "product_file": product_path.name,
        "charges_file": charges_path.name,
        "removed_from_a_valider": removed_from_a_valider,
        "added_to_charges": added_to_charges,
        "already_in_charges": already_in_charges,
        "product_a_valider_after": len(kept_a_valider),
        "charges_items_after": len(charges_items),
    }


def main() -> int:
    module = load_rules_module()
    results = [process_target(module, key, cfg) for key, cfg in TARGETS.items()]

    SUMMARY_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Reclass Transport/BTP A Valider To Charges Summary",
        "",
    ]
    for result in results:
        lines.append(f"## {result['key']}")
        lines.append("")
        lines.append(f"- product_file: `{result['product_file']}`")
        lines.append(f"- charges_file: `{result['charges_file']}`")
        lines.append(f"- removed_from_a_valider: `{result['removed_from_a_valider']}`")
        lines.append(f"- added_to_charges: `{result['added_to_charges']}`")
        lines.append(f"- already_in_charges: `{result['already_in_charges']}`")
        lines.append(f"- product_a_valider_after: `{result['product_a_valider_after']}`")
        lines.append(f"- charges_items_after: `{result['charges_items_after']}`")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
