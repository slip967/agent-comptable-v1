#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, RequestException

from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)


SCRIPT_DIR = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

STOP_WORDS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "a",
    "au",
    "aux",
    "et",
    "en",
    "sur",
    "pour",
    "par",
    "avec",
    "x",
    "kg",
}

PACKAGING_HINTS = {
    "film",
    "emballage",
    "barquette",
    "boite",
    "bte",
    "sac",
    "sacs",
    "bobine",
    "serv",
    "serviette",
    "couv",
    "couverts",
    "kraft",
    "degrais",
    "decapant",
}

DRINK_HINTS = {
    "coca",
    "cocacola",
    "coca cola",
    "oasis",
    "fuzetea",
    "lipton",
    "perrier",
    "cristali",
    "cristaline",
    "eau",
}

BTP_HINTS = {
    "beton",
    "coulage",
    "coffrage",
    "sciage",
    "poncage",
    "pompe",
    "chantier",
    "tuyaux",
    "couronne",
    "peinture",
    "surfaquartz",
}

CHARGES_SOUS_CATEGORIE_MAP = {
    "cotisations_professionnelles": "charges_generales",
    "telecom_et_abonnements": "frais_service",
    "energie_electricite": "energie_electricite",
    "energie_gaz": "energie_gaz",
    "energie_et_utilites": "energie_eau",
    "assurances": "frais_service",
    "entretien_et_maintenance": "entretien_reparation",
    "loyers_et_charges_locatives": "locations",
    "transport_et_logistique": "transport",
    "frais_administratifs_et_bancaires": "frais_service",
    "autres_charges_externes": "charges_generales",
}

TARGETS = {
    "boucherie": {
        "triage": "candidate_packs_metier/boucherie_top_50_triage.md",
        "base_files": [
            "base_produits_boucherie_v1.json",
            "base_produits_boucherie_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/boucherie_top_500_cleaned_candidates.json",
    },
    "restaurant": {
        "triage": "candidate_packs_metier/restaurant_top_50_triage.md",
        "base_files": [
            "base_produits_restaurant_v1.json",
            "base_produits_restaurant_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/restaurant_top_500_cleaned_candidates.json",
    },
    "transport": {
        "triage": "candidate_packs_metier/transport_top_50_triage.md",
        "base_files": [
            "base_produits_transport_v1.json",
            "base_produits_transport_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/transport_top_500_cleaned_candidates.json",
    },
    "boulangerie": {
        "triage": "candidate_packs_metier/boulangerie_top_50_triage.md",
        "base_files": [
            "base_produits_boulangerie_v1.json",
            "base_produits_boulangerie_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/boulangerie_top_500_cleaned_candidates.json",
    },
    "btp": {
        "triage": "candidate_packs_metier/btp_top_50_triage.md",
        "base_files": [
            "base_produits_btp_v1.json",
            "base_produits_btp_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/btp_top_500_cleaned_candidates.json",
    },
    "charges_externes": {
        "triage": "candidate_packs_metier/charges_externes_top_50_triage.md",
        "base_files": [
            "base_charges_externes_v1.json",
            "base_charges_externes_v1_with_accounts.json",
        ],
        "candidate_pack": "candidate_packs_metier/charges_externes_top_500_cleaned_candidates.json",
    },
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def post_find(session: requests.Session, endpoint: str, payload: dict, timeout: int = 120) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            response = session.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (ChunkedEncodingError, RequestException, ValueError) as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(min(5, attempt))
    raise RuntimeError(f"Failed to query CouchDB after retries: {endpoint}") from last_error


def unwrap_value(value):
    while isinstance(value, dict) and "value" in value:
        value = value.get("value")
    return value


def get_nested(obj, path, default=None):
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def first_non_empty(obj, paths, default=None):
    for path in paths:
        value = get_nested(obj, path, default=None)
        if value not in (None, "", [], {}):
            return value
    return default


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok and tok not in STOP_WORDS]


def clean_text(value) -> str:
    return str(unwrap_value(value) or "").strip()


def clean_amount(value) -> str:
    raw = unwrap_value(value)
    if raw in (None, "", []):
        return ""
    try:
        return f"{float(raw):.2f}"
    except Exception:
        return str(raw).strip()


def extract_siren_from_party(party) -> str:
    if not isinstance(party, dict):
        return ""
    direct = str(unwrap_value(party.get("siren")) or "").strip()
    if direct:
        return direct
    for reg in party.get("company_registrations") or []:
        if not isinstance(reg, dict):
            continue
        reg_type = str(unwrap_value(reg.get("type")) or "").strip().upper()
        reg_value = str(unwrap_value(reg.get("value")) or "").strip()
        if reg_type == "SIREN" and reg_value:
            return reg_value
        if reg_type == "SIRET" and len(reg_value) >= 9:
            return reg_value[:9]
    return ""


def extract_invoice_duplicate_key(doc) -> tuple[str, str, str, str, str] | None:
    issuer = first_non_empty(
        doc,
        [
            ("issuer",),
            ("invoice", "issuer"),
            ("data", "issuer"),
        ],
        default={},
    )
    supplier_siren = extract_siren_from_party(issuer)
    invoice_number = clean_text(doc.get("invoice_number"))
    invoice_date = clean_text(doc.get("invoice_date"))
    total_amount = clean_amount(doc.get("total_gross")) or clean_amount(doc.get("total_net"))
    document_type = clean_text(doc.get("document_type"))
    if not supplier_siren or not invoice_number or not invoice_date:
        return None
    return supplier_siren, invoice_number.upper(), invoice_date, total_amount, document_type.upper()


def get_line_items(doc):
    raw_items = first_non_empty(
        doc,
        [
            ("line_items",),
            ("invoice", "line_items"),
            ("data", "line_items"),
        ],
        default=[],
    )
    return raw_items if isinstance(raw_items, list) else []


def contains_any(text: str, keywords: set[str]) -> bool:
    tokens = set(tokenize(text))
    if tokens & keywords:
        return True
    return any(keyword in text for keyword in keywords if " " in keyword)


def classify_charge(article_source: str, account: str) -> dict:
    article_canonique = normalize_text(article_source)
    text = normalize_text(f"{article_source} {article_canonique}")
    account = str(account or "").strip()

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
        "bbox",
        "lycamobile",
        "sfr",
        "orange",
        "bouygues",
        "acrobat",
    }
    electricite_keywords = {
        "electricite",
        "edf",
        "energie",
        "heures pleines",
        "heures creuses",
        "soutirage",
        "kwh",
        "cspe",
        "cta",
    }
    gaz_keywords = {
        "gaz",
        "propane",
        "butane",
        "grdf",
        "gdf",
        "gaz naturel",
    }
    eau_keywords = {
        "eau",
        "eaux",
        "assainissement",
        "veolia",
        "suez",
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
        "décharge",
        "decharge",
    }
    transport_keywords = {
        "port",
        "transport",
        "livraison",
        "messagerie",
        "expedition",
        "frais de port",
        "deliveroo",
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
        "commission sur vente",
        "commission deliveroo",
    }
    admin_keywords = {
        "relance",
        "administratif",
        "administratifs",
        "carte acheteur",
        "terme",
        "tm ht",
        "commission",
        "frais dossier",
        "frais bancaire",
        "agios",
        "recouvrement",
        "bimpli",
        "frais de gestion",
        "debit",
        "paiements supplementaires",
        "paiements supplémentaires",
        "airbnb",
        "prestation emetteur",
        "prestation émetteur",
        "frais de transaction",
        "frais de service",
    }

    sous_profil = "autres_charges_externes"
    nature_charge = "frais"
    profil_facturation = "forfait_ou_frais"
    reason = "fallback"

    if contains_any(text, telecom_keywords) or account.startswith("626"):
        sous_profil = "telecom_et_abonnements"
        nature_charge = "abonnement"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword_or_account:telecom"
    elif contains_any(text, electricite_keywords) or (account.startswith("6061") and "gaz" not in text and "eau" not in text):
        sous_profil = "energie_electricite"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword_or_account:electricite"
    elif contains_any(text, gaz_keywords):
        sous_profil = "energie_gaz"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword:gaz"
    elif contains_any(text, eau_keywords):
        sous_profil = "energie_et_utilites"
        nature_charge = "energie"
        profil_facturation = "abonnement_et_consommation"
        reason = "keyword:eau"
    elif contains_any(text, assurance_keywords) or account.startswith("616"):
        sous_profil = "assurances"
        nature_charge = "prime"
        profil_facturation = "prime_et_periode"
        reason = "keyword_or_account:assurance"
    elif contains_any(text, entretien_keywords) or account.startswith("615"):
        sous_profil = "entretien_et_maintenance"
        nature_charge = "entretien"
        profil_facturation = "intervention_ponctuelle"
        reason = "keyword_or_account:entretien"
    elif contains_any(text, loyer_keywords) or account.startswith(("613", "614")):
        sous_profil = "loyers_et_charges_locatives"
        nature_charge = "loyer" if "loyer" in text else "charges_locatives"
        profil_facturation = "loyer_et_charges"
        reason = "keyword_or_account:loyer"
    elif contains_any(text, transport_keywords) or account.startswith("624"):
        sous_profil = "transport_et_logistique"
        nature_charge = "transport"
        profil_facturation = "prestation_ponctuelle"
        reason = "keyword_or_account:transport"
    elif contains_any(text, admin_keywords) or account.startswith(("6226", "627")):
        sous_profil = "frais_administratifs_et_bancaires"
        nature_charge = "frais"
        profil_facturation = "forfait_ou_frais"
        reason = "keyword_or_account:administratif"
    elif contains_any(text, cotisation_keywords) or account.startswith(("6227", "6281", "6351")):
        sous_profil = "cotisations_professionnelles"
        nature_charge = "cotisation"
        profil_facturation = "cotisation_ou_forfait"
        reason = "keyword_or_account:cotisation"

    return {
        "sous_profil": sous_profil,
        "nature_charge": nature_charge,
        "profil_facturation": profil_facturation,
        "classification_reason": reason,
    }


def parse_a_garder_labels(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_section = False
    labels: list[str] = []
    pattern = re.compile(r"^\d+\.\s+`(.+?)`")
    for line in lines:
        if line.strip() == "## A Garder":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = pattern.match(line.strip())
        if match:
            labels.append(match.group(1).strip())
    return labels


def load_candidate_pack_map(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for bucket_name in ("top_all", "top_new_to_inject"):
        for row in payload.get(bucket_name) or []:
            key = normalize_text(str(row.get("article_source") or ""))
            if key and key not in rows:
                rows[key] = row
    return rows


def collect_selected_line_stats(
    session: requests.Session,
    source_db: str,
    report_path: Path,
    triage_labels: dict[str, list[str]],
) -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    partitions = report.get("partitions") or []
    partition_ape_map = {
        str(part.get("partition_prefix") or "").strip(): str(part.get("client_ape") or "").strip()
        for part in partitions
    }

    normalized_targets = {
        metier: {normalize_text(label): label for label in labels}
        for metier, labels in triage_labels.items()
    }
    selected_sets = {metier: set(mapping.keys()) for metier, mapping in normalized_targets.items()}

    stats = {
        metier: defaultdict(
            lambda: {
                "label_counter": Counter(),
                "invoice_ids": set(),
                "partitions": set(),
                "account_counter": Counter(),
                "vat_counter": Counter(),
                "line_occurrences": 0,
                "ape_context": set(),
            }
        )
        for metier in triage_labels
    }

    for partition in partitions:
        partition_prefix = str(partition.get("partition_prefix") or "").strip()
        selected_metiers = set(partition.get("selected_metiers") or [])
        if not partition_prefix:
            continue
        endpoint = f"{COUCHDB_URL}/{quote(source_db, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
        bookmark = None
        seen_invoice_keys = set()

        while True:
            payload = {
                "selector": {"p": "invoice_form"},
                "fields": [
                    "_id",
                    "invoice_number",
                    "invoice_date",
                    "total_gross",
                    "total_net",
                    "document_type",
                    "issuer",
                    "invoice",
                    "data",
                    "line_items",
                ],
                "limit": 500,
            }
            if bookmark:
                payload["bookmark"] = bookmark

            data = post_find(session, endpoint, payload, timeout=120)
            docs = data.get("docs") or []
            if not docs:
                break

            for doc in docs:
                duplicate_key = extract_invoice_duplicate_key(doc)
                if duplicate_key is not None:
                    if duplicate_key in seen_invoice_keys:
                        continue
                    seen_invoice_keys.add(duplicate_key)

                invoice_id = str(doc.get("_id") or "").strip()
                for line in get_line_items(doc):
                    if not isinstance(line, dict):
                        continue
                    description = clean_text(line.get("description"))
                    if not description:
                        continue
                    key = normalize_text(description)
                    account = clean_text(line.get("accounting_account"))
                    vat = clean_text(line.get("vat_percent"))

                    for metier, target_keys in selected_sets.items():
                        if metier != "charges_externes" and metier not in selected_metiers:
                            continue
                        if key not in target_keys:
                            continue
                        bucket = stats[metier][key]
                        bucket["label_counter"][description] += 1
                        if invoice_id:
                            bucket["invoice_ids"].add(invoice_id)
                        bucket["partitions"].add(partition_prefix)
                        if account:
                            bucket["account_counter"][account] += 1
                        if vat:
                            bucket["vat_counter"][vat] += 1
                        bucket["line_occurrences"] += 1
                        ape = partition_ape_map.get(partition_prefix)
                        if ape:
                            bucket["ape_context"].add(ape)

            next_bookmark = data.get("bookmark")
            if not next_bookmark or next_bookmark == bookmark:
                break
            bookmark = next_bookmark

    return stats, partition_ape_map


def infer_product_sous_categorie(metier: str, label: str, account: str) -> str:
    text = normalize_text(label)
    tokens = set(tokenize(label))
    if metier == "btp":
        if tokens & BTP_HINTS or any(h in text for h in BTP_HINTS):
            return "consommable_chantier"
        if tokens & PACKAGING_HINTS:
            return "emballage"
        if str(account).startswith("6068"):
            return "consommable_chantier"
        return "matiere_premiere"
    if metier in {"restaurant", "boulangerie"} and (tokens & DRINK_HINTS or any(h in text for h in DRINK_HINTS if " " in h)):
        return "matiere_premiere"
    if metier in {"boucherie", "restaurant"} and (tokens & PACKAGING_HINTS or any(h in text for h in PACKAGING_HINTS)):
        return "emballage"
    return "matiere_premiere"


def infer_product_fournisseur_type(metier: str, sous_categorie: str, label: str) -> str:
    if metier == "boucherie":
        return "consommables" if sous_categorie == "emballage" else "grossiste viande"
    if metier == "restaurant":
        return "consommables" if sous_categorie == "emballage" else "grossiste alimentaire"
    if metier == "transport":
        return "service_transport"
    if metier == "btp":
        return "fournisseur_materiaux"
    return "fournisseur alimentaire"


def infer_product_tva_rate(metier: str, label: str, account: str) -> float:
    text = normalize_text(label)
    tokens = set(tokenize(label))
    if metier in {"transport", "btp"}:
        return 20.0
    if sous_categorie_is_packaging(metier, label, account):
        return 20.0
    if tokens & DRINK_HINTS or any(h in text for h in DRINK_HINTS if " " in h):
        return 20.0
    if any(keyword in text for keyword in ("degrais", "decapant", "javel", "lavage", "nettoyage")):
        return 20.0
    return 5.5


def build_product_item(metier: str, label: str, stat: dict, pack_row: dict) -> dict:
    normalized = normalize_text(label)
    article_source = stat["label_counter"].most_common(1)[0][0] if stat["label_counter"] else label
    compte = ""
    if stat["account_counter"]:
        compte = stat["account_counter"].most_common(1)[0][0]
    elif pack_row:
        compte = str(pack_row.get("sample_account") or "").strip()

    tva_rate = None
    if stat["vat_counter"]:
        raw = stat["vat_counter"].most_common(1)[0][0]
        try:
            tva_rate = float(raw)
        except Exception:
            tva_rate = None
    if tva_rate is None:
        tva_rate = infer_product_tva_rate(metier, article_source, compte)

    sous_categorie = infer_product_sous_categorie(metier, article_source, compte)
    mots_cles = tokenize(article_source)[:6]
    invoice_count = len(stat["invoice_ids"]) or int(stat.get("invoice_count_hint") or 0)
    line_occurrences = stat["line_occurrences"]

    return {
        "article_source": article_source,
        "article_canonique": normalized,
        "categorie": "exploitation_metier",
        "sous_categorie": sous_categorie,
        "tva_rate": tva_rate,
        "mots_cles": mots_cles,
        "fournisseur_type": infer_product_fournisseur_type(metier, sous_categorie, article_source),
        "ape_context": sorted(stat["ape_context"]),
        "notes": f"Integre depuis triage manuel {metier} (invoice_count={invoice_count}, line_occurrences={line_occurrences})",
        "source_invoice_ids": sorted(stat["invoice_ids"])[:30],
        "compte_comptable": compte,
        "compte_comptable_source": "triage_manual_candidate_pack_v1",
        "compte_comptable_match_score": min(600, 200 + invoice_count * 2 + min(line_occurrences, 100)),
        "compte_comptable_match_reason": f"manual_triage_keep; predominant_account={compte}; invoices={invoice_count}; occurrences={line_occurrences}",
    }


def sous_categorie_is_packaging(metier: str, label: str, account: str) -> bool:
    return infer_product_sous_categorie(metier, label, account) == "emballage"


def build_charge_item(label: str, stat: dict, pack_row: dict) -> dict:
    normalized = normalize_text(label)
    article_source = stat["label_counter"].most_common(1)[0][0] if stat["label_counter"] else label
    compte = ""
    if stat["account_counter"]:
        compte = stat["account_counter"].most_common(1)[0][0]
    elif pack_row:
        compte = str(pack_row.get("sample_account") or "").strip()

    tva_rate = None
    if stat["vat_counter"]:
        raw = stat["vat_counter"].most_common(1)[0][0]
        try:
            tva_rate = float(raw)
        except Exception:
            tva_rate = None
    if tva_rate is None:
        tva_rate = 20.0

    classification = classify_charge(article_source, compte)
    invoice_count = len(stat["invoice_ids"]) or int(stat.get("invoice_count_hint") or 0)
    line_occurrences = stat["line_occurrences"]

    return {
        "article_source": article_source,
        "article_canonique": normalized,
        "categorie": "charges_externes",
        "sous_categorie": CHARGES_SOUS_CATEGORIE_MAP.get(classification["sous_profil"], "charges_generales"),
        "tva_rate": tva_rate,
        "mots_cles": tokenize(article_source)[:6],
        "fournisseur_type": "service",
        "ape_context": sorted(stat["ape_context"]),
        "notes": f"Integre depuis triage manuel charges_externes (invoice_count={invoice_count}, line_occurrences={line_occurrences})",
        "source_invoice_ids": sorted(stat["invoice_ids"])[:30],
        "compte_comptable": compte,
        "compte_comptable_source": "triage_manual_candidate_pack_v1",
        "compte_comptable_match_score": min(600, 200 + invoice_count * 2 + min(line_occurrences, 100)),
        "compte_comptable_match_reason": f"manual_triage_keep; predominant_account={compte}; invoices={invoice_count}; occurrences={line_occurrences}",
        "sous_profil": classification["sous_profil"],
        "nature_charge": classification["nature_charge"],
        "profil_facturation": classification["profil_facturation"],
        "profil_facturation_champs": default_charges_champs(classification["profil_facturation"]),
        "classification_version": "charges_externes_rules_v1_manual_triage",
        "classification_reason": classification["classification_reason"],
    }


def default_charges_champs(profil_facturation: str) -> list[str]:
    if profil_facturation == "abonnement_et_consommation":
        return ["periode_debut", "periode_fin", "abonnement_ht", "consommation_ht"]
    if profil_facturation == "cotisation_ou_forfait":
        return ["periode_debut", "periode_fin", "montant_ht"]
    if profil_facturation == "intervention_ponctuelle":
        return ["date_intervention", "description_intervention", "montant_ht"]
    if profil_facturation == "loyer_et_charges":
        return ["periode_debut", "periode_fin", "loyer_ht", "charges_ht"]
    if profil_facturation == "prestation_ponctuelle":
        return ["date_prestation", "description_prestation", "montant_ht"]
    if profil_facturation == "prime_et_periode":
        return ["periode_debut", "periode_fin", "prime_ht"]
    return ["montant_ht", "montant_ttc"]


def refresh_charges_profile_enrichment(payload: dict) -> None:
    items = payload.get("items") or []
    counts_sous_profil = Counter()
    counts_nature = Counter()
    counts_profil = Counter()
    for item in items:
        if not isinstance(item, dict):
            continue
        counts_sous_profil[str(item.get("sous_profil") or "")] += 1
        counts_nature[str(item.get("nature_charge") or "")] += 1
        counts_profil[str(item.get("profil_facturation") or "")] += 1
    meta = payload.setdefault("meta", {})
    meta["charges_profile_enrichment"] = {
        "source_file": meta.get("profile_id", "charges_externes_global_v1"),
        "generated_at": now_iso(),
        "version": "charges_externes_rules_v1_manual_triage",
        "counts_by_sous_profil": dict(sorted(counts_sous_profil.items())),
        "counts_by_nature_charge": dict(sorted(counts_nature.items())),
        "counts_by_profil_facturation": dict(sorted(counts_profil.items())),
    }


def integrate_items(target_path: Path, new_items: list[dict], triage_name: str) -> tuple[int, int]:
    payload = json.loads(target_path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    existing = {normalize_text(str(item.get("article_source") or "")) for item in items if isinstance(item, dict)}
    added = 0
    skipped = 0
    for item in new_items:
        key = normalize_text(str(item.get("article_source") or ""))
        if not key or key in existing:
            skipped += 1
            continue
        items.append(item)
        existing.add(key)
        added += 1
    payload["items"] = items
    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(items)
    meta["triage_manual_integration_v1"] = {
        "updated_at": now_iso(),
        "source_triage": triage_name,
        "added_items": added,
        "skipped_existing": skipped,
    }
    if target_path.name.startswith("base_charges_externes"):
        refresh_charges_profile_enrichment(payload)
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate all 'A Garder' items from triage markdowns into base JSON files.")
    parser.add_argument("--report-json", default="copy_keymanage_metier_docs_report_quality_v3.json")
    parser.add_argument("--source-db", default="")
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=sorted(TARGETS.keys()),
        default=None,
        help="Limit integration to a subset of targets.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Build items from local triage + candidate packs only, without querying CouchDB.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = (SCRIPT_DIR / args.report_json).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    active_targets = args.targets or list(TARGETS.keys())
    source_db = str(args.source_db or report.get("source_db") or "").strip()
    partition_ape_map = {
        str(part.get("partition_prefix") or "").strip(): str(part.get("client_ape") or "").strip()
        for part in (report.get("partitions") or [])
        if str(part.get("partition_prefix") or "").strip()
    }

    triage_labels = {}
    candidate_maps = {}
    for metier in active_targets:
        cfg = TARGETS[metier]
        triage_path = (SCRIPT_DIR / cfg["triage"]).resolve()
        labels = parse_a_garder_labels(triage_path)
        triage_labels[metier] = labels
        candidate_maps[metier] = load_candidate_pack_map((SCRIPT_DIR / cfg["candidate_pack"]).resolve())

    stats_by_metier = {metier: defaultdict(dict) for metier in active_targets}
    if not args.offline:
        if not source_db:
            raise SystemExit("Missing source_db.")
        session = http_session()
        stats_by_metier, _partition_ape_map = collect_selected_line_stats(session, source_db, report_path, triage_labels)

    integrated_summary = {}
    for metier in active_targets:
        cfg = TARGETS[metier]
        new_items = []
        for label in triage_labels[metier]:
            key = normalize_text(label)
            stat = stats_by_metier[metier].get(key)
            pack_row = candidate_maps[metier].get(key, {})
            if not stat:
                stat = {
                    "label_counter": Counter({label: 1}),
                    "invoice_ids": set(),
                    "partitions": set(pack_row.get("partitions") or []),
                    "account_counter": Counter(),
                    "vat_counter": Counter(),
                    "invoice_count_hint": int(pack_row.get("invoice_count") or 0),
                    "line_occurrences": int(pack_row.get("line_occurrences") or 1),
                    "ape_context": {
                        ape
                        for ape in (
                            partition_ape_map.get(str(partition or "").strip())
                            for partition in (pack_row.get("partitions") or [])
                        )
                        if ape
                    },
                }
                sample_account = str(pack_row.get("sample_account") or "").strip()
                if sample_account:
                    stat["account_counter"][sample_account] += 1
            if metier == "charges_externes":
                item = build_charge_item(label, stat, pack_row)
            else:
                item = build_product_item(metier, label, stat, pack_row)
            new_items.append(item)

        file_results = []
        for file_name in cfg["base_files"]:
            target_path = (SCRIPT_DIR / file_name).resolve()
            added, skipped = integrate_items(target_path, new_items, Path(cfg["triage"]).name)
            file_results.append({"file": file_name, "added": added, "skipped_existing": skipped})

        integrated_summary[metier] = {
            "labels_selected": len(triage_labels[metier]),
            "files": file_results,
        }

    print(json.dumps(integrated_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
