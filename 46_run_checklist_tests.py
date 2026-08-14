#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import importlib.util
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPT_DIR / "05_generated_entries.py"

DEFAULT_CONTEXTS = {
    "boucherie": {"client_siren": "519665103", "client_ape": "4722Z", "supplier_ape": "4632A"},
    "restaurant": {"client_siren": "452416191", "client_ape": "5610A", "supplier_ape": "4639B"},
    "transport": {"client_siren": "824332985", "client_ape": "4941A", "supplier_ape": "4730Z"},
    "boulangerie": {"client_siren": "519665103", "client_ape": "1071C", "supplier_ape": "4639B"},
    "btp": {"client_siren": "832065999", "client_ape": "4329A", "supplier_ape": "2361Z"},
    "charges_externes": {"client_siren": "519665103", "client_ape": "4722Z", "supplier_ape": "4632A"},
}

OUTPUT_FIELDS = [
    "metier",
    "libelle_test",
    "contexte_suggere",
    "compte_propose",
    "reference_top1",
    "source_decision",
    "tva_proposee",
    "statut_test_reel",
    "commentaire_test_reel",
    "controle_metier_compte",
    "controle_metier_tva",
    "controle_metier_classement",
    "action_a_prendre",
]


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def load_generator_module():
    spec = importlib.util.spec_from_file_location("generated_entries_module", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_local_generator(module):
    obj = module.AccountingEntryGenerator.__new__(module.AccountingEntryGenerator)
    obj.verbose = False
    obj._external_charge_matcher_module = None
    obj._external_charge_refs = None
    obj._product_metier_refs = None
    obj._external_charge_matcher_error = None
    obj._scope_metier_by_client = None
    obj.stats = {
        "charge_source_external_charge_auto": 0,
        "charge_source_external_charge_validation": 0,
        "charge_source_product_metier_auto": 0,
        "charge_source_product_metier_validation": 0,
        "charge_source_line_item_mixed_auto": 0,
        "charge_source_line_item_mixed_validation": 0,
    }
    obj._log = lambda *args, **kwargs: None
    return obj


def parse_float(value: str) -> float:
    cleaned = str(value or "").strip().replace(",", ".")
    return float(cleaned)


def build_invoice(row: dict, context: dict) -> dict:
    return {
        "_id": f"checklist:{normalize_text(row['metier'])}:{normalize_text(row['libelle_test'])}",
        "invoice_number": "CHECKLIST-001",
        "invoice_date": "28/04/2026",
        "issuer": {"name": "FOURNISSEUR TEST", "ape": context["supplier_ape"]},
        "recipient": {"name": "CLIENT TEST", "ape": context["client_ape"]},
        "line_items": [
            {
                "description": row["libelle_test"],
                "vat_percent": parse_float(row["tva_proposee"]),
            }
        ],
    }


def first_line_match(details: dict | None) -> dict | None:
    if not isinstance(details, dict):
        return None
    line_matches = details.get("line_matches") or []
    if line_matches:
        return line_matches[0]
    return None


def classify_result(row: dict, source: str, line_match: dict | None) -> tuple[str, str]:
    label = row["libelle_test"]
    if not line_match:
        return "aucune_reco", "Aucune line_match retournee par le moteur."

    predicted_account = str(line_match.get("predicted_account") or "").strip()
    top1_article = ""
    top3_articles = line_match.get("top3_articles") or []
    if top3_articles:
        top1_article = str(top3_articles[0] or "").strip()
    if not top1_article:
        top1_article = str(line_match.get("line_text") or "").strip()

    exact_match = normalize_text(top1_article) == normalize_text(label)
    decision = str(line_match.get("recommendation_decision") or "").strip() or "unknown"
    predicted_score = line_match.get("predicted_score")

    if not predicted_account:
        return "aucune_reco", "Aucun compte predit."
    if exact_match and decision == "auto_ok":
        return "OK_auto", f"Match exact top1, score={predicted_score}, source={source}"
    if exact_match:
        return "a_valider", f"Match exact mais decision={decision}, source={source}"
    return "ambigu", f"Top1 different ({top1_article}), decision={decision}, source={source}"


def quick_compte_check(metier: str, account: str, source: str = "") -> str:
    account = str(account or "").strip()
    if not account:
        return "A revoir"
    if metier == "charges_externes" or str(source or "").startswith("external_charge_"):
        return "OK probable" if account.startswith(("60", "61", "62", "626", "627", "628")) else "A revoir"
    return "OK probable" if account.startswith("60") else "A revoir"


def quick_tva_check(expected: str, line_match: dict | None) -> str:
    if not line_match:
        return "A revoir"
    try:
        expected_value = parse_float(expected)
    except Exception:
        return "A revoir"
    observed = line_match.get("tva_hint")
    try:
        observed_value = float(observed)
    except Exception:
        return "A revoir"
    return "OK probable" if abs(expected_value - observed_value) < 0.001 else "A revoir"


def quick_classement(row: dict, line_match: dict | None) -> str:
    if not line_match:
        return "A revoir"
    if row["metier"] == "charges_externes":
        sous_profil = str(line_match.get("predicted_sous_profil") or "").strip()
        return sous_profil or "A revoir"
    metier = str(line_match.get("predicted_metier") or "").strip()
    sous_categorie = str(line_match.get("predicted_sous_categorie") or "").strip()
    sous_profil = str(line_match.get("predicted_sous_profil") or "").strip()
    if metier and sous_categorie:
        return f"{metier}/{sous_categorie}"
    if metier:
        return metier
    if sous_profil:
        return sous_profil
    return "A revoir"


def quick_action(status: str, compte_check: str, tva_check: str) -> str:
    if status == "OK_auto" and compte_check == "OK probable" and tva_check == "OK probable":
        return "Conserver"
    if status == "aucune_reco":
        return "Corriger base"
    return "Verifier"


def run_one_test(generator, row: dict) -> dict:
    metier = str(row["metier"] or "").strip()
    context = deepcopy(DEFAULT_CONTEXTS[metier])
    invoice = build_invoice(row, context)

    external_accounts, external_details, external_src = generator._recommend_external_charge_accounts_from_invoice(  # noqa: SLF001
        invoice=invoice,
        supplier_ape=context["supplier_ape"],
    )
    product_accounts, product_details, product_src = generator._recommend_product_metier_accounts_from_invoice(  # noqa: SLF001
        invoice=invoice,
        client_siren=context["client_siren"],
        client_ape=context["client_ape"],
    )
    merged_accounts, merged_details, merged_src = generator._merge_line_item_recommendations(  # noqa: SLF001
        external_accounts,
        external_details,
        external_src,
        product_accounts,
        product_details,
        product_src,
    )

    if metier == "charges_externes":
        active_src = external_src or merged_src or ""
        active_details = external_details or {}
        line_match = first_line_match(active_details)
        fallback_account = ((external_accounts or [{}])[0]).get("account_number") if external_accounts else ""
    else:
        if product_details:
            active_src = product_src or ""
            active_details = product_details
            fallback_account = ((product_accounts or [{}])[0]).get("account_number") if product_accounts else ""
        elif merged_details:
            active_src = merged_src or external_src or ""
            active_details = merged_details
            fallback_account = ((merged_accounts or [{}])[0]).get("account_number") if merged_accounts else ""
        else:
            active_src = external_src or merged_src or ""
            active_details = external_details or {}
            fallback_account = ((external_accounts or [{}])[0]).get("account_number") if external_accounts else ""
        line_match = first_line_match(active_details)

    predicted_account = str((line_match or {}).get("predicted_account") or fallback_account or "").strip()
    top3_articles = (line_match or {}).get("top3_articles") or []
    top1_article = str(top3_articles[0] or "").strip() if top3_articles else str((line_match or {}).get("line_text") or "").strip()
    status, comment = classify_result(row, active_src, line_match)
    compte_check = quick_compte_check(metier, predicted_account, active_src)
    tva_check = quick_tva_check(row["tva_proposee"], line_match)
    classement_check = quick_classement(row, line_match)

    result = deepcopy(row)
    result["compte_propose"] = predicted_account
    result["reference_top1"] = top1_article
    result["source_decision"] = active_src
    result["statut_test_reel"] = status
    result["commentaire_test_reel"] = comment
    result["controle_metier_compte"] = compte_check
    result["controle_metier_tva"] = tva_check
    result["controle_metier_classement"] = classement_check
    result["action_a_prendre"] = quick_action(status, compte_check, tva_check)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local engine tests on the checklist CSV.")
    parser.add_argument("--input-csv", default="checklist_tests_reels_controle_metier.csv")
    parser.add_argument("--output-csv", default="checklist_tests_reels_controle_metier_resultats.csv")
    parser.add_argument("--summary-json", default="checklist_tests_reels_controle_metier_summary.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = (SCRIPT_DIR / args.input_csv).resolve()
    output_path = (SCRIPT_DIR / args.output_csv).resolve()
    summary_path = (SCRIPT_DIR / args.summary_json).resolve()

    module = load_generator_module()
    generator = build_local_generator(module)

    with input_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    results = [run_one_test(generator, row) for row in rows]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "total_tests": len(results),
        "by_status": {},
        "by_metier": {},
    }
    for row in results:
        status = row["statut_test_reel"]
        metier = row["metier"]
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        summary["by_metier"].setdefault(metier, {"total": 0, "OK_auto": 0, "a_valider": 0, "ambigu": 0, "aucune_reco": 0})
        summary["by_metier"][metier]["total"] += 1
        summary["by_metier"][metier][status] = summary["by_metier"][metier].get(status, 0) + 1

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] results_csv={output_path}")
    print(f"[OK] summary_json={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
