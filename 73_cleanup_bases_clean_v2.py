#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
REPORT_CSV = SCRIPT_DIR / "cleanup_auto_v2_report.csv"
REPORT_MD = SCRIPT_DIR / "cleanup_auto_v2_report.md"
REPORT_JSON = SCRIPT_DIR / "cleanup_auto_v2_report.json"


LIST_UNION_FIELDS = {
    "source_invoice_ids",
    "ape_context",
    "mots_cles",
    "profil_facturation_champs",
}

DATE_STOP_WORDS = {
    "janvier",
    "fevrier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
    "décembre",
    "periode",
    "period",
    "mensuel",
    "mensuelle",
    "trimestre",
    "trim",
    "annuel",
    "annuelle",
    "du",
    "au",
    "aux",
}

USELESS_UNIT_TOKENS = {
    "kg",
    "g",
    "gr",
    "mg",
    "l",
    "lt",
    "ml",
    "cl",
    "dl",
    "cm",
    "mm",
    "m",
    "m2",
    "m3",
    "km",
    "kw",
    "kwh",
    "go",
    "gb",
    "mo",
    "tb",
    "ah",
    "v",
    "w",
    "x",
    "ht",
    "ttc",
    "eur",
    "euro",
    "euros",
    "pcs",
    "pc",
    "piece",
    "pieces",
    "jour",
    "jours",
}

STRONG_CHARGE_KEYWORDS = {
    "abonnement",
    "bbox",
    "box",
    "forfait",
    "telecom",
    "telephone",
    "internet",
    "wifi",
    "mobile",
    "sim",
    "sims",
    "electricite",
    "energie",
    "gaz",
    "assurance",
    "loyer",
    "parking",
    "livraison",
    "maintenance",
    "nettoyage",
    "reparation",
    "airbnb",
    "lycamobile",
    "acrobat",
    "main oeuvre",
    "sous traitance",
    "prestation",
    "recharge",
    "lebara",
    "symacom",
    "mobitpe",
}

SERVICE_VERB_HINTS = {
    "deposer",
    "repose",
    "poser",
    "peindre",
    "remplacer",
    "regler",
    "nettoyage",
    "laver",
    "lavage",
    "maintenance",
    "vidange",
    "programmer",
    "effectuer",
    "montage",
    "demontage",
    "installation",
    "essai",
    "test rapide",
    "visite technique",
    "location",
    "mission",
    "campagne",
}

PRODUCT_HINTS = {
    "boucherie": {
        "boeuf",
        "basse",
        "cote",
        "veau",
        "mouton",
        "agneau",
        "poulet",
        "dinde",
        "abats",
        "foie",
        "gésier",
        "gesier",
        "halal",
        "carcasse",
        "lapin",
        "steack",
    },
    "boulangerie": {
        "farine",
        "levure",
        "beurre",
        "lait",
        "sucre",
        "chocolat",
        "creme",
        "oeuf",
        "oeufs",
        "brioche",
        "pain",
        "mascarpone",
        "amande",
        "vanille",
        "glucose",
    },
    "restaurant": {
        "salade",
        "tiramisu",
        "carotte",
        "boisson",
        "coca",
        "oasis",
        "menu",
        "dessert",
        "poulet",
        "sauce",
        "barquette",
        "frites",
        "burger",
    },
    "transport": {
        "gazole",
        "adblue",
        "filtre",
        "pneu",
        "plaquette",
        "frein",
        "carburant",
        "jante",
        "huile",
        "amortisseur",
        "silentbloc",
        "batterie",
        "polish",
        "ressort",
        "console",
    },
    "btp": {
        "beton",
        "ciment",
        "plaque",
        "placo",
        "peinture",
        "rivet",
        "vis",
        "brique",
        "grillage",
        "profil",
        "gants",
        "balai",
        "alu",
        "pvc",
        "quincaillerie",
        "contre",
        "echafaudage",
    },
}

PRODUCT_ACCOUNT_ALLOWED_PREFIXES = ("60", "607")
CHARGE_ACCOUNT_ALLOWED_PREFIXES = (
    "604",
    "605",
    "6061",
    "6062",
    "6063",
    "6064",
    "6065",
    "6068",
    "613",
    "614",
    "615",
    "616",
    "622",
    "624",
    "626",
    "627",
    "628",
    "635",
)
CHARGE_ACCOUNT_SUSPICIOUS_PREFIXES = ("601", "602", "607")


def load_helper_module():
    spec = importlib.util.spec_from_file_location("cleanup_helper_module", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_output_name(path: Path) -> Path:
    if path.name.endswith("_v1.json"):
        return path.with_name(path.name.replace("_v1.json", "_clean_v2.json"))
    return path.with_name(path.stem + "_clean_v2.json")


def normalize_account(account: str) -> str:
    raw = re.sub(r"\s+", "", str(account or ""))
    if not raw:
        return ""
    digits = re.sub(r"[^0-9]", "", raw)
    if digits:
        while len(digits) > 3 and digits.endswith("0"):
            digits = digits[:-1]
        return digits
    return raw


def unique_list(values) -> list:
    seen = set()
    result = []
    for value in values or []:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def merge_notes(a: str, b: str) -> str:
    parts = []
    for value in (a, b):
        text = str(value or "").strip()
        if not text:
            continue
        for part in [seg.strip() for seg in text.split("|")]:
            if part and part not in parts:
                parts.append(part)
    return " | ".join(parts)


def build_keywords(helper, item: dict) -> list[str]:
    article_source = str(item.get("article_source") or "").strip()
    article_canonique = str(item.get("article_canonique") or "").strip()
    article_source_original = str(item.get("article_source_original") or "").strip()
    raw_parts = [article_source, article_source_original, article_canonique]
    text = " ".join(part for part in raw_parts if part)
    tokens = helper.normalize_text(text).split()

    keywords = []
    seen = set()
    stop_words = set(getattr(helper, "STOP_WORDS", set())) | DATE_STOP_WORDS | USELESS_UNIT_TOKENS

    for token in tokens:
        if not token:
            continue
        if token in stop_words:
            continue
        if len(token) <= 1:
            continue
        if re.fullmatch(r"\d{1,4}", token):
            continue
        if re.fullmatch(r"\d{1,2}(er)?", token):
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)

    if not keywords:
        for token in (item.get("mots_cles") or []):
            key = helper.normalize_text(str(token or ""))
            if key and key not in seen:
                seen.add(key)
                keywords.append(key)

    return keywords


def has_any_keyword(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_product_misclassification(helper, metier: str, item: dict) -> tuple[bool, str]:
    article_source = str(item.get("article_source") or "").strip()
    account = normalize_account(item.get("compte_comptable"))
    text = helper.normalize_text(" ".join([article_source, str(item.get("article_canonique") or "")]))
    charge_profile = helper.classify_charge(article_source, account)
    charge_keyword_hit = has_any_keyword(text, STRONG_CHARGE_KEYWORDS)
    service_hint_hit = has_any_keyword(text, SERVICE_VERB_HINTS)
    service_account_hit = account.startswith(("613", "614", "615", "616", "622", "624", "626", "627"))
    product_hint_hit = has_any_keyword(text, PRODUCT_HINTS.get(metier, set()))

    if metier in {"boucherie", "boulangerie", "restaurant", "epicerie"}:
        if charge_keyword_hit and not product_hint_hit:
            return True, f"charge_keyword:{charge_profile['sous_profil']}"
        if service_account_hit and not product_hint_hit:
            return True, "service_account_prefix"
        return False, ""

    if metier == "transport":
        if service_hint_hit:
            return True, "service_transport_like"
        if charge_keyword_hit and not product_hint_hit:
            return True, f"charge_keyword:{charge_profile['sous_profil']}"
        if service_account_hit and not product_hint_hit:
            return True, "service_account_prefix"
        return False, ""

    if metier == "btp":
        if has_any_keyword(text, {"mise a disposition", "location", "sous traitance", "mission", "jour de location"}):
            return True, "service_btp_like"
        if "travaux" in text and not product_hint_hit:
            return True, "service_btp_like"
        if service_hint_hit and charge_keyword_hit and not product_hint_hit:
            return True, "service_btp_like"
        if service_account_hit and not product_hint_hit:
            return True, "service_account_prefix"
        return False, ""

    if charge_profile["sous_profil"] != "autres_charges_externes" and (charge_keyword_hit or service_hint_hit or service_account_hit) and not product_hint_hit:
        return True, f"charge_profile:{charge_profile['sous_profil']}"

    return False, ""


def classify_charge_manual_review(helper, item: dict) -> tuple[bool, str]:
    account = normalize_account(item.get("compte_comptable"))
    text = helper.normalize_text(" ".join(
        [
            str(item.get("article_source") or ""),
            str(item.get("article_canonique") or ""),
            str(item.get("article_source_original") or ""),
        ]
    ))

    if account.startswith(CHARGE_ACCOUNT_SUSPICIOUS_PREFIXES) and not has_any_keyword(text, STRONG_CHARGE_KEYWORDS):
        return True, "charge_account_looks_product_like"

    if has_any_keyword(text, PRODUCT_HINTS["boucherie"] | PRODUCT_HINTS["boulangerie"] | PRODUCT_HINTS["restaurant"] | PRODUCT_HINTS["transport"] | PRODUCT_HINTS["btp"]) and not has_any_keyword(text, STRONG_CHARGE_KEYWORDS):
        return True, "charge_text_looks_product_like"

    return False, ""


def account_suspicion(kind: str, metier: str, item: dict) -> tuple[bool, str]:
    account = normalize_account(item.get("compte_comptable"))
    if not account:
        return True, "missing_account"
    if kind == "product":
        if not account.startswith(PRODUCT_ACCOUNT_ALLOWED_PREFIXES):
            return True, f"product_account_prefix_unexpected:{account}"
    else:
        if not account.startswith(CHARGE_ACCOUNT_ALLOWED_PREFIXES):
            return True, f"charge_account_prefix_unexpected:{account}"
    return False, ""


def build_charge_item_from_product(helper, item: dict, source_file: str) -> dict:
    moved = deepcopy(item)
    article_source = str(moved.get("article_source") or "").strip()
    account = normalize_account(moved.get("compte_comptable"))
    text = helper.normalize_text(" ".join([article_source, str(moved.get("article_canonique") or "")]))
    _, source_metier = infer_kind_and_metier(Path(source_file))

    if source_metier == "btp":
        classification = {
            "sous_profil": "autres_charges_externes",
            "nature_charge": "prestation",
            "profil_facturation": "intervention_ponctuelle",
            "classification_reason": "manual_reclass:btp_service",
        }
    elif source_metier in {"transport", "vtc"} and has_any_keyword(text, {"livraison", "condition de livraison"}):
        classification = {
            "sous_profil": "transport_et_logistique",
            "nature_charge": "transport",
            "profil_facturation": "prestation_ponctuelle",
            "classification_reason": "manual_reclass:transport_logistique",
        }
    elif source_metier in {"transport", "vtc"}:
        classification = {
            "sous_profil": "entretien_et_maintenance",
            "nature_charge": "entretien",
            "profil_facturation": "intervention_ponctuelle",
            "classification_reason": "manual_reclass:transport_service",
        }
    else:
        classification = helper.classify_charge(article_source, account)

    moved["categorie"] = "charges_externes"
    moved["fournisseur_type"] = "service"
    moved["sous_profil"] = classification["sous_profil"]
    moved["nature_charge"] = classification["nature_charge"]
    moved["profil_facturation"] = classification["profil_facturation"]
    moved["profil_facturation_champs"] = helper.default_charges_champs(classification["profil_facturation"])
    moved["sous_categorie"] = helper.CHARGES_SOUS_CATEGORIE_MAP.get(classification["sous_profil"], "charges_generales")
    moved["classification_reason"] = classification["classification_reason"]
    moved["classification_version"] = "cleanup_auto_v2"
    moved["compte_comptable"] = account
    moved["notes"] = merge_notes(
        moved.get("notes"),
        f"Auto-move cleanup_auto_v2 depuis {source_file} vers charges_externes.",
    )
    return moved


def recompute_charge_fields(helper, item: dict) -> tuple[dict, list[str]]:
    corrected_fields = []
    article_source = str(item.get("article_source") or "").strip()
    account = normalize_account(item.get("compte_comptable"))
    classification = helper.classify_charge(article_source, account)

    expected = {
        "categorie": "charges_externes",
        "fournisseur_type": "service",
        "sous_profil": classification["sous_profil"],
        "nature_charge": classification["nature_charge"],
        "profil_facturation": classification["profil_facturation"],
        "profil_facturation_champs": helper.default_charges_champs(classification["profil_facturation"]),
        "sous_categorie": helper.CHARGES_SOUS_CATEGORIE_MAP.get(classification["sous_profil"], "charges_generales"),
        "classification_reason": classification["classification_reason"],
        "classification_version": "cleanup_auto_v2",
    }

    for key, value in expected.items():
        if item.get(key) != value:
            item[key] = value
            corrected_fields.append(key)
    return item, corrected_fields


def merge_duplicate_items(helper, items: list[dict], file_name: str, bucket: str, report_rows: list[dict], manual_reviews: list[dict]) -> list[dict]:
    merged: list[dict] = []
    by_source: dict[str, int] = {}
    by_canon: dict[str, int] = {}

    for item in items:
        if not isinstance(item, dict):
            continue
        source_key = helper.normalize_text(str(item.get("article_source") or ""))
        canon_key = helper.normalize_text(str(item.get("article_canonique") or ""))
        idx = None
        reason = ""
        if source_key and source_key in by_source:
            idx = by_source[source_key]
            reason = "duplicate_article_source"
        elif canon_key and canon_key in by_canon:
            idx = by_canon[canon_key]
            reason = "duplicate_article_canonique"

        if idx is None:
            idx = len(merged)
            merged.append(item)
            if source_key:
                by_source[source_key] = idx
            if canon_key:
                by_canon[canon_key] = idx
            continue

        target = merged[idx]
        account_a = normalize_account(target.get("compte_comptable"))
        account_b = normalize_account(item.get("compte_comptable"))
        if account_a and account_b and account_a != account_b:
            manual_reviews.append(
                {
                    "source_file": file_name,
                    "bucket": bucket,
                    "article_source": target.get("article_source") or item.get("article_source"),
                    "reason": "duplicate_conflicting_accounts",
                    "details": f"{account_a} vs {account_b}",
                }
            )

        for field in set(target.keys()) | set(item.keys()):
            if field in LIST_UNION_FIELDS:
                target[field] = unique_list((target.get(field) or []) + (item.get(field) or []))
            elif field == "notes":
                target[field] = merge_notes(target.get(field), item.get(field))
            elif not target.get(field) and item.get(field) not in (None, "", [], {}):
                target[field] = item.get(field)

        report_rows.append(
            {
                "source_file": file_name,
                "output_file": "",
                "action": "duplicate_merged",
                "bucket": bucket,
                "article_source_before": item.get("article_source", ""),
                "article_source_after": target.get("article_source", ""),
                "account_before": account_b,
                "account_after": account_a or account_b,
                "details": reason,
                "target_file": "",
            }
        )

    return merged


def update_meta(helper, payload: dict, source_file: str, stats: dict) -> None:
    payload.setdefault("meta", {})
    payload["meta"]["items_count"] = len(payload.get("items") or [])
    payload["meta"]["a_valider_count"] = len(payload.get("a_valider") or [])
    payload["meta"]["cleanup_auto_v2"] = {
        "updated_at": helper.now_iso(),
        "source_file": source_file,
        **stats,
    }


def base_files() -> list[Path]:
    files = sorted(SCRIPT_DIR.glob("base_produits_*_v1.json"))
    files = [path for path in files if not path.name.endswith("_with_accounts.json")]
    files.append(SCRIPT_DIR / "base_charges_externes_v1.json")
    return sorted({path.resolve() for path in files})


def infer_kind_and_metier(path: Path) -> tuple[str, str]:
    if path.name == "base_charges_externes_v1.json":
        return "charges", "charges_externes"
    match = re.match(r"base_produits_(.+?)_v1\.json$", path.name)
    if not match:
        return "product", "inconnu"
    return "product", match.group(1)


def main() -> None:
    helper = load_helper_module()
    original_payloads = {path.name: load_json(path) for path in base_files()}
    clean_payloads = {name: deepcopy(payload) for name, payload in original_payloads.items()}

    report_rows: list[dict] = []
    suspicious_accounts: list[dict] = []
    manual_reviews: list[dict] = []
    moved_to_charges: list[dict] = []
    file_summaries: dict[str, dict] = {}

    charges_file = "base_charges_externes_v1.json"
    charges_payload = clean_payloads[charges_file]
    incoming_charge_items: list[dict] = []

    for file_name, payload in clean_payloads.items():
        kind, metier = infer_kind_and_metier(Path(file_name))
        file_summaries[file_name] = {
            "kind": kind,
            "metier": metier,
            "items_before": len((original_payloads[file_name].get("items") or [])),
            "a_valider_before": len((original_payloads[file_name].get("a_valider") or [])),
            "account_normalized": 0,
            "canonical_rebuilt": 0,
            "keywords_rebuilt": 0,
            "auto_moved_to_charges": 0,
            "charge_fields_refreshed": 0,
        }

        for bucket in ("items", "a_valider"):
            source_items = payload.get(bucket) or []
            cleaned_items = []

            for item in source_items:
                if not isinstance(item, dict):
                    cleaned_items.append(item)
                    continue

                original_source = str(item.get("article_source") or "")
                original_canon = str(item.get("article_canonique") or "")
                original_account = str(item.get("compte_comptable") or "")
                original_keywords = list(item.get("mots_cles") or [])

                new_account = normalize_account(original_account)
                if new_account != original_account:
                    item["compte_comptable"] = new_account
                    file_summaries[file_name]["account_normalized"] += 1
                    report_rows.append(
                        {
                            "source_file": file_name,
                            "output_file": clean_output_name(Path(file_name)).name,
                            "action": "normalize_account",
                            "bucket": bucket,
                            "article_source_before": original_source,
                            "article_source_after": original_source,
                            "account_before": original_account,
                            "account_after": new_account,
                            "details": "trim_trailing_zeros",
                            "target_file": "",
                        }
                    )

                new_canon = helper.normalize_text(original_source)
                if new_canon != original_canon:
                    item["article_canonique"] = new_canon
                    file_summaries[file_name]["canonical_rebuilt"] += 1
                    report_rows.append(
                        {
                            "source_file": file_name,
                            "output_file": clean_output_name(Path(file_name)).name,
                            "action": "rebuild_article_canonique",
                            "bucket": bucket,
                            "article_source_before": original_source,
                            "article_source_after": original_source,
                            "account_before": new_account,
                            "account_after": new_account,
                            "details": f"{original_canon} -> {new_canon}",
                            "target_file": "",
                        }
                    )

                new_keywords = build_keywords(helper, item)
                if new_keywords != original_keywords:
                    item["mots_cles"] = new_keywords
                    file_summaries[file_name]["keywords_rebuilt"] += 1
                    report_rows.append(
                        {
                            "source_file": file_name,
                            "output_file": clean_output_name(Path(file_name)).name,
                            "action": "rebuild_keywords",
                            "bucket": bucket,
                            "article_source_before": original_source,
                            "article_source_after": original_source,
                            "account_before": new_account,
                            "account_after": new_account,
                            "details": f"{original_keywords} -> {new_keywords}",
                            "target_file": "",
                        }
                    )

                suspect, reason = account_suspicion(kind, metier, item)
                if suspect:
                    suspicious_accounts.append(
                        {
                            "source_file": file_name,
                            "bucket": bucket,
                            "article_source": original_source,
                            "reason": reason,
                            "account": new_account,
                        }
                    )
                    report_rows.append(
                        {
                            "source_file": file_name,
                            "output_file": clean_output_name(Path(file_name)).name,
                            "action": "suspicious_account",
                            "bucket": bucket,
                            "article_source_before": original_source,
                            "article_source_after": original_source,
                            "account_before": new_account,
                            "account_after": new_account,
                            "details": reason,
                            "target_file": "",
                        }
                    )

                if kind == "product":
                    should_move, move_reason = classify_product_misclassification(helper, metier, item)
                    if should_move:
                        incoming_charge_items.append(build_charge_item_from_product(helper, item, file_name))
                        file_summaries[file_name]["auto_moved_to_charges"] += 1
                        moved_to_charges.append(
                            {
                                "source_file": file_name,
                                "bucket": bucket,
                                "article_source": original_source,
                                "reason": move_reason,
                                "target_file": clean_output_name(Path(charges_file)).name,
                            }
                        )
                        report_rows.append(
                            {
                                "source_file": file_name,
                                "output_file": clean_output_name(Path(file_name)).name,
                                "action": "auto_move_to_charges",
                                "bucket": bucket,
                                "article_source_before": original_source,
                                "article_source_after": original_source,
                                "account_before": new_account,
                                "account_after": new_account,
                                "details": move_reason,
                                "target_file": clean_output_name(Path(charges_file)).name,
                            }
                        )
                        continue

                if kind == "charges":
                    item, corrected_charge_fields = recompute_charge_fields(helper, item)
                    if corrected_charge_fields:
                        file_summaries[file_name]["charge_fields_refreshed"] += 1
                        report_rows.append(
                            {
                                "source_file": file_name,
                                "output_file": clean_output_name(Path(file_name)).name,
                                "action": "refresh_charge_classification",
                                "bucket": bucket,
                                "article_source_before": original_source,
                                "article_source_after": original_source,
                                "account_before": new_account,
                                "account_after": new_account,
                                "details": ",".join(corrected_charge_fields),
                                "target_file": "",
                            }
                        )
                    review, review_reason = classify_charge_manual_review(helper, item)
                    if review:
                        manual_reviews.append(
                            {
                                "source_file": file_name,
                                "bucket": bucket,
                                "article_source": original_source,
                                "reason": review_reason,
                                "details": new_account,
                            }
                        )
                        report_rows.append(
                            {
                                "source_file": file_name,
                                "output_file": clean_output_name(Path(file_name)).name,
                                "action": "manual_review",
                                "bucket": bucket,
                                "article_source_before": original_source,
                                "article_source_after": original_source,
                                "account_before": new_account,
                                "account_after": new_account,
                                "details": review_reason,
                                "target_file": "",
                            }
                        )

                cleaned_items.append(item)

            payload[bucket] = cleaned_items

    charges_payload["items"] = (charges_payload.get("items") or []) + incoming_charge_items

    for file_name, payload in clean_payloads.items():
        for bucket in ("items", "a_valider"):
            payload[bucket] = merge_duplicate_items(helper, payload.get(bucket) or [], file_name, bucket, report_rows, manual_reviews)

    for file_name, payload in clean_payloads.items():
        summary = file_summaries[file_name]
        summary["items_after"] = len(payload.get("items") or [])
        summary["a_valider_after"] = len(payload.get("a_valider") or [])
        summary["duplicates_merged"] = sum(1 for row in report_rows if row["source_file"] == file_name and row["action"] == "duplicate_merged")
        summary["manual_review_count"] = sum(1 for row in manual_reviews if row["source_file"] == file_name)
        update_meta(helper, payload, file_name, summary)
        save_json(clean_output_name(Path(file_name)), payload)

    report_payload = {
        "generated_at": helper.now_iso(),
        "generated_from": "73_cleanup_bases_clean_v2.py",
        "outputs": {file_name: clean_output_name(Path(file_name)).name for file_name in clean_payloads},
        "file_summaries": file_summaries,
        "moved_to_charges": moved_to_charges,
        "suspicious_accounts": suspicious_accounts,
        "manual_reviews": manual_reviews,
        "report_rows_count": len(report_rows),
    }
    REPORT_JSON.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file",
                "output_file",
                "action",
                "bucket",
                "article_source_before",
                "article_source_after",
                "account_before",
                "account_after",
                "details",
                "target_file",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    md_lines = [
        "# Cleanup Auto V2 Report",
        "",
        "Script: `73_cleanup_bases_clean_v2.py`",
        "",
        "## Fichiers produits",
        "",
    ]
    for file_name, summary in file_summaries.items():
        md_lines.extend(
            [
                f"### {file_name}",
                "",
                f"- output: `{clean_output_name(Path(file_name)).name}`",
                f"- items before/after: `{summary['items_before']} -> {summary['items_after']}`",
                f"- a_valider before/after: `{summary['a_valider_before']} -> {summary['a_valider_after']}`",
                f"- normalized accounts: `{summary['account_normalized']}`",
                f"- rebuilt canonical: `{summary['canonical_rebuilt']}`",
                f"- rebuilt keywords: `{summary['keywords_rebuilt']}`",
                f"- auto moved to charges: `{summary['auto_moved_to_charges']}`",
                f"- refreshed charge fields: `{summary['charge_fields_refreshed']}`",
                f"- duplicates merged: `{summary['duplicates_merged']}`",
                f"- manual review count: `{summary['manual_review_count']}`",
                "",
            ]
        )

    md_lines.extend(["## Articles deplaces vers charges_externes", ""])
    if moved_to_charges:
        for row in moved_to_charges:
            md_lines.append(
                f"- `{row['article_source']}` depuis `{row['source_file']}` -> `{row['target_file']}` ({row['reason']})"
            )
    else:
        md_lines.append("- Aucun")
    md_lines.append("")

    md_lines.extend(["## Comptes suspects", ""])
    if suspicious_accounts:
        for row in suspicious_accounts:
            md_lines.append(
                f"- `{row['source_file']}` / `{row['article_source']}` / compte `{row['account']}` -> {row['reason']}"
            )
    else:
        md_lines.append("- Aucun")
    md_lines.append("")

    md_lines.extend(["## Articles a valider manuellement", ""])
    if manual_reviews:
        for row in manual_reviews:
            md_lines.append(
                f"- `{row['source_file']}` / `{row['article_source']}` -> {row['reason']} ({row.get('details','')})"
            )
    else:
        md_lines.append("- Aucun")
    md_lines.append("")

    md_lines.extend(["## Duplicates merges", ""])
    duplicate_rows = [row for row in report_rows if row["action"] == "duplicate_merged"]
    if duplicate_rows:
        for row in duplicate_rows:
            md_lines.append(
                f"- `{row['source_file']}` / `{row['article_source_before']}` -> fusion ({row['details']})"
            )
    else:
        md_lines.append("- Aucun")
    md_lines.append("")

    REPORT_MD.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {REPORT_JSON.name}")
    print(f"Wrote {REPORT_CSV.name}")
    print(f"Wrote {REPORT_MD.name}")
    for file_name, summary in file_summaries.items():
        print(
            f"{file_name}: items {summary['items_before']}->{summary['items_after']} "
            f"a_valider {summary['a_valider_before']}->{summary['a_valider_after']} "
            f"moved_to_charges={summary['auto_moved_to_charges']}"
        )


if __name__ == "__main__":
    main()
