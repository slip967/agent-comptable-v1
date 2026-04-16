#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> set[str]:
    return set(normalize_text(value).split())


def contains_any(text: str, keywords: set[str]) -> bool:
    tokens = tokenize(text)
    if tokens & keywords:
        return True
    return any(keyword in text for keyword in keywords if " " in keyword)


def classify_charge(item: dict) -> dict:
    article_source = str(item.get("article_source") or "").strip()
    article_canonique = str(item.get("article_canonique") or "").strip()
    text = normalize_text(f"{article_source} {article_canonique}")
    account = str(item.get("compte_comptable") or "").strip()

    telecom_keywords = {
        "abonnement",
        "mobile",
        "mobitpe",
        "telecom",
        "telephone",
        "internet",
        "fibre",
        "sim",
        "sims",
        "wifi",
        "forfait",
        "box",
    }
    electricite_keywords = {
        "electricite",
        "edf",
        "energie",
        "heures pleines",
        "heures creuses",
        "soutirage",
        "kwh",
    }
    gaz_keywords = {
        "gaz",
        "propane",
        "butane",
        "grdf",
        "gdf",
        "gaz naturel",
    }
    assurance_keywords = {
        "assurance",
        "prime",
        "multirisque",
        "sinistre",
        "responsabilite",
        "rc pro",
    }
    loyer_keywords = {
        "loyer",
        "charges locatives",
        "acompte sur charges",
        "solde charges",
        "solde charges locatives",
        "bail",
        "locatif",
        "locative",
    }
    entretien_keywords = {
        "entretien",
        "maintenance",
        "desourisation",
        "deratisation",
        "nettoyage",
        "parking",
        "reparation",
    }
    transport_keywords = {
        "port",
        "transport",
        "livraison",
        "sortie viande",
        "sortie volaille",
        "messagerie",
    }
    cotisation_keywords = {
        "coti",
        "cotisation",
        "interbev",
        "interb",
        "decro",
        "rsd",
        "f fixe",
        "frais fixes",
    }
    admin_keywords = {
        "relance",
        "administratif",
        "administratifs",
        "carte acheteur",
        "terme",
        "tm ht",
        "commission",
    }

    sous_profil = "autres_charges_externes"
    nature_charge = "frais"
    profil_facturation = "forfait_ou_frais"
    profil_facturation_champs = ["montant_ht", "montant_ttc"]
    reason = "fallback"

    has_telecom_keyword = contains_any(text, telecom_keywords)
    has_electricite_keyword = contains_any(text, electricite_keywords)
    has_gaz_keyword = contains_any(text, gaz_keywords)
    has_assurance_keyword = contains_any(text, assurance_keywords)
    has_loyer_keyword = contains_any(text, loyer_keywords)
    has_entretien_keyword = contains_any(text, entretien_keywords)
    has_transport_keyword = contains_any(text, transport_keywords)
    has_cotisation_keyword = contains_any(text, cotisation_keywords)
    has_admin_keyword = contains_any(text, admin_keywords)

    if has_telecom_keyword:
        sous_profil = "telecom_et_abonnements"
        nature_charge = "abonnement"
        profil_facturation = "abonnement_et_consommation"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "abonnement_ht",
            "consommation_ht",
            "identifiant_ligne",
        ]
        reason = "keyword:telecom"
    elif has_electricite_keyword:
        sous_profil = "energie_electricite"
        nature_charge = "consommation"
        profil_facturation = "abonnement_et_consommation"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "abonnement_ht",
            "consommation_ht",
            "consommation_unite",
        ]
        reason = "keyword:electricite"
    elif has_gaz_keyword:
        sous_profil = "energie_gaz"
        nature_charge = "consommation"
        profil_facturation = "abonnement_et_consommation"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "abonnement_ht",
            "consommation_ht",
            "consommation_unite",
        ]
        reason = "keyword:gaz"
    elif has_assurance_keyword:
        sous_profil = "assurances"
        nature_charge = "prime"
        profil_facturation = "prime_et_periode"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "prime_ht",
        ]
        reason = "keyword:assurance"
    elif has_entretien_keyword or account.startswith("615"):
        sous_profil = "entretien_et_maintenance"
        nature_charge = "entretien"
        profil_facturation = "intervention_ponctuelle"
        profil_facturation_champs = [
            "date_intervention",
            "description_intervention",
            "montant_ht",
        ]
        reason = "keyword_or_account:entretien"
    elif has_loyer_keyword or (account.startswith("613") and any(token in text for token in ("loyer", "charge", "locative"))):
        sous_profil = "loyers_et_charges_locatives"
        if "loyer" in text:
            nature_charge = "loyer"
        else:
            nature_charge = "charges_locatives"
        profil_facturation = "loyer_et_charges"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "loyer_ht",
            "charges_ht",
        ]
        reason = "keyword_or_account:loyer"
    elif has_transport_keyword:
        sous_profil = "transport_et_logistique"
        nature_charge = "transport"
        profil_facturation = "prestation_ponctuelle"
        profil_facturation_champs = [
            "date_prestation",
            "description_prestation",
            "montant_ht",
        ]
        reason = "keyword:transport"
    elif has_cotisation_keyword:
        sous_profil = "cotisations_professionnelles"
        nature_charge = "cotisation"
        profil_facturation = "cotisation_ou_forfait"
        profil_facturation_champs = [
            "periode_debut",
            "periode_fin",
            "montant_ht",
        ]
        reason = "keyword:cotisation"
    elif has_admin_keyword or account.startswith(("6226", "6281")):
        sous_profil = "frais_administratifs_et_bancaires"
        nature_charge = "frais"
        profil_facturation = "forfait_ou_frais"
        profil_facturation_champs = [
            "date_operation",
            "description_frais",
            "montant_ht",
        ]
        reason = "keyword_or_account:administratif"

    return {
        "sous_profil": sous_profil,
        "nature_charge": nature_charge,
        "profil_facturation": profil_facturation,
        "profil_facturation_champs": profil_facturation_champs,
        "classification_version": "charges_externes_rules_v1",
        "classification_reason": reason,
    }


def enrich_payload(payload: dict, source_name: str) -> dict:
    items = payload.get("items") or []

    counts_sous_profil = Counter()
    counts_nature = Counter()
    counts_profil = Counter()

    for item in items:
        if not isinstance(item, dict):
            continue
        enrichment = classify_charge(item)
        item.update(enrichment)
        counts_sous_profil[enrichment["sous_profil"]] += 1
        counts_nature[enrichment["nature_charge"]] += 1
        counts_profil[enrichment["profil_facturation"]] += 1

    meta = payload.setdefault("meta", {})
    meta["charges_profile_enrichment"] = {
        "source_file": source_name,
        "generated_at": now_iso(),
        "version": "charges_externes_rules_v1",
        "counts_by_sous_profil": dict(sorted(counts_sous_profil.items())),
        "counts_by_nature_charge": dict(sorted(counts_nature.items())),
        "counts_by_profil_facturation": dict(sorted(counts_profil.items())),
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description="Enrich base_charges_externes with sous-profils and billing profile hints.")
    parser.add_argument("--input", default="base_charges_externes_v1.json", help="Input JSON file.")
    parser.add_argument("--output", default="", help="Output JSON file. Defaults to input path.")
    args = parser.parse_args()

    input_path = (SCRIPT_DIR / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input).resolve()
    output_path = input_path if not args.output else (
        (SCRIPT_DIR / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    )

    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise SystemExit("Input JSON must be an object with meta/items.")

    enriched = enrich_payload(payload, input_path.name)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = enriched.get("meta", {}).get("charges_profile_enrichment", {}).get("counts_by_sous_profil", {})
    print(f"[OK] output={output_path}")
    print(f"[INFO] counts_by_sous_profil={json.dumps(counts, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
