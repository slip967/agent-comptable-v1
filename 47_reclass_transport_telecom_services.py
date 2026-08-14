#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import importlib.util
import json
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
RECLASS_CSV = SCRIPT_DIR / "a_reclasser_hors_base_produits_selon_pdf.csv"


def load_rules_module():
    spec = importlib.util.spec_from_file_location("triage_rules_module", RULES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {RULES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_reclass_rows():
    rows = []
    with RECLASS_CSV.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        rows.extend(reader)
    return rows


def build_charge_item(module, transport_item: dict, row: dict) -> dict:
    article_source = str(transport_item.get("article_source") or "").strip()
    compte = str(transport_item.get("compte_comptable") or "").strip()
    classification = module.classify_charge(article_source, compte)
    charge_item = deepcopy(transport_item)
    charge_item["categorie"] = "charges_externes"
    charge_item["sous_categorie"] = module.CHARGES_SOUS_CATEGORIE_MAP.get(
        classification["sous_profil"], "charges_generales"
    )
    charge_item["fournisseur_type"] = "service"
    charge_item["notes"] = (
        f"{str(transport_item.get('notes') or '').strip()} | "
        "Reclassé depuis base_produits_transport_v1 selon doctrine PDF "
        "(prestations/telecom hors base produit métier)"
    ).strip(" |")
    charge_item["sous_profil"] = classification["sous_profil"]
    charge_item["nature_charge"] = classification["nature_charge"]
    charge_item["profil_facturation"] = classification["profil_facturation"]
    charge_item["profil_facturation_champs"] = module.default_charges_champs(
        classification["profil_facturation"]
    )
    charge_item["classification_version"] = "charges_externes_rules_v1_reclass_transport_pdf"
    charge_item["classification_reason"] = classification["classification_reason"]
    charge_item["reclassement_source"] = "transport_to_charges_externes_pdf_v1"
    charge_item["reclassement_recommande"] = row["reclassement_recommande"]
    charge_item["motif_pdf"] = row["motif_pdf"]
    return charge_item


def normalize(module, value: str) -> str:
    return module.normalize_text(str(value or ""))


def process_pair(module, transport_file: str, charges_file: str, rows: list[dict]) -> dict:
    transport_path = SCRIPT_DIR / transport_file
    charges_path = SCRIPT_DIR / charges_file

    transport_payload = json.loads(transport_path.read_text(encoding="utf-8"))
    charges_payload = json.loads(charges_path.read_text(encoding="utf-8"))

    transport_items = transport_payload.get("items") or []
    transport_a_valider = transport_payload.get("a_valider") or []
    charges_items = charges_payload.get("items") or []

    rows_by_key = {normalize(module, row["article_source"]): row for row in rows}
    target_keys = set(rows_by_key.keys())
    charges_existing = {
        normalize(module, str(item.get("article_source") or "")) for item in charges_items if isinstance(item, dict)
    }

    kept_transport_items = []
    moved_to_a_valider = 0
    added_to_charges = 0
    already_in_charges = 0

    for item in transport_items:
        if not isinstance(item, dict):
            kept_transport_items.append(item)
            continue
        key = normalize(module, str(item.get("article_source") or ""))
        if key not in target_keys:
            kept_transport_items.append(item)
            continue

        row = rows_by_key[key]
        archived = deepcopy(item)
        archived["reclassement_recommande"] = row["reclassement_recommande"]
        archived["motif_pdf"] = row["motif_pdf"]
        archived["reclassement_source"] = "transport_to_charges_externes_pdf_v1"
        archived["notes"] = (
            f"{str(archived.get('notes') or '').strip()} | "
            "Sorti de la base produit active transport selon doctrine PDF"
        ).strip(" |")
        transport_a_valider.append(archived)
        moved_to_a_valider += 1

        if key in charges_existing:
            already_in_charges += 1
            continue

        charge_item = build_charge_item(module, item, row)
        charges_items.append(charge_item)
        charges_existing.add(key)
        added_to_charges += 1

    transport_payload["items"] = kept_transport_items
    transport_payload["a_valider"] = transport_a_valider
    transport_payload.setdefault("meta", {})
    transport_payload["meta"]["items_count"] = len(kept_transport_items)
    transport_payload["meta"]["transport_pdf_reclass_v1"] = {
        "updated_at": module.now_iso(),
        "moved_from_items_to_a_valider": moved_to_a_valider,
        "target": "charges_externes/telecom_et_abonnements",
        "source_csv": RECLASS_CSV.name,
    }

    charges_payload["items"] = charges_items
    charges_payload.setdefault("meta", {})
    charges_payload["meta"]["items_count"] = len(charges_items)
    charges_payload["meta"]["transport_pdf_reclass_v1"] = {
        "updated_at": module.now_iso(),
        "added_from_transport": added_to_charges,
        "already_present": already_in_charges,
        "source_csv": RECLASS_CSV.name,
    }
    module.refresh_charges_profile_enrichment(charges_payload)

    transport_path.write_text(json.dumps(transport_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    charges_path.write_text(json.dumps(charges_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "transport_file": transport_file,
        "charges_file": charges_file,
        "moved_to_a_valider": moved_to_a_valider,
        "added_to_charges": added_to_charges,
        "already_in_charges": already_in_charges,
        "transport_items_after": len(kept_transport_items),
        "transport_a_valider_after": len(transport_a_valider),
        "charges_items_after": len(charges_items),
    }


def main() -> int:
    module = load_rules_module()
    rows = load_reclass_rows()
    summary = []
    summary.append(
        process_pair(
            module,
            "base_produits_transport_v1.json",
            "base_charges_externes_v1.json",
            rows,
        )
    )
    summary.append(
        process_pair(
            module,
            "base_produits_transport_v1_with_accounts.json",
            "base_charges_externes_v1_with_accounts.json",
            rows,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
