#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPT_DIR / "05_generated_entries.py"

PRODUCT_BASE_FILES = [
    "base_produits_boulangerie_v1.json",
    "base_produits_boucherie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
]

DEFAULT_CLIENT_APE_BY_METIER = {
    "boulangerie": "1071C",
    "boucherie": "4722Z",
    "restaurant": "5610A",
    "epicerie": "4711C",
    "btp": "4120A",
    "transport": "4941A",
    "vtc": "4932Z",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def load_items_from_bases() -> list[dict]:
    rows: list[dict] = []
    for filename in PRODUCT_BASE_FILES:
        path = SCRIPT_DIR / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        meta = payload.get("meta") or {}
        metier = str(meta.get("metier") or "").strip()
        client_siren = str(meta.get("client_siren") or "519665103").strip()
        for item in payload.get("items") or []:
            rows.append(
                {
                    "base_file": filename,
                    "metier_base": metier,
                    "client_siren": client_siren,
                    "item": item,
                }
            )
    return rows


def build_invoice(item: dict) -> dict:
    return {
        "_id": ((item.get("source_invoice_ids") or [""])[0] or "").strip(),
        "line_items": [
            {
                "description": item.get("article_source"),
                "vat_percent": item.get("tva_rate"),
            }
        ],
    }


def choose_client_ape(row: dict) -> tuple[str | None, str]:
    item = row["item"]
    metier = str(row.get("metier_base") or "").strip()
    ape_context = list(item.get("ape_context") or [])
    if ape_context:
        ape = str(ape_context[0] or "").strip().upper()
        if ape:
            return ape, "item_ape_context"
    fallback = DEFAULT_CLIENT_APE_BY_METIER.get(metier)
    if fallback:
        return fallback, "metier_default"
    return None, "none"


def top_summary(values: list[str], scores: list[float]) -> str:
    pairs: list[str] = []
    for idx, value in enumerate(values):
        if not value:
            continue
        score = scores[idx] if idx < len(scores) else ""
        pairs.append(f"{value} ({score})")
    return " | ".join(pairs)


def evaluate_rows(rows: list[dict], generator) -> tuple[list[dict], dict]:
    results: list[dict] = []
    summary = {
        "items_total": 0,
        "matched_total": 0,
        "account_match_total": 0,
        "metier_match_total": 0,
        "decision_auto_ok_total": 0,
        "decision_validation_humaine_total": 0,
        "decision_rejeter_total": 0,
        "no_match_total": 0,
    }
    by_metier: dict[str, Counter] = defaultdict(Counter)

    for row in rows:
        item = row["item"]
        metier_base = str(row.get("metier_base") or "").strip()
        client_siren = str(row.get("client_siren") or "519665103").strip()
        client_ape, client_ape_source = choose_client_ape(row)
        invoice = build_invoice(item)

        accounts, details, source_label = generator._recommend_product_metier_accounts_from_invoice(  # noqa: SLF001
            invoice=invoice,
            client_siren=client_siren,
            client_ape=client_ape,
        )

        summary["items_total"] += 1
        by_metier[metier_base]["items_total"] += 1

        if not details or not accounts:
            summary["no_match_total"] += 1
            by_metier[metier_base]["no_match_total"] += 1
            results.append(
                {
                    "base_file": row["base_file"],
                    "metier_base": metier_base,
                    "client_siren": client_siren,
                    "client_ape_used": client_ape or "",
                    "client_ape_source": client_ape_source,
                    "article_source": str(item.get("article_source") or "").strip(),
                    "article_canonique": str(item.get("article_canonique") or "").strip(),
                    "tva_rate": item.get("tva_rate") if item.get("tva_rate") is not None else "",
                    "expected_compte_comptable": str(item.get("compte_comptable") or "").strip(),
                    "predicted_compte_comptable": "",
                    "account_match": "no",
                    "expected_metier": metier_base,
                    "predicted_metier": "",
                    "metier_match": "no",
                    "predicted_categorie": "",
                    "predicted_sous_categorie": "",
                    "predicted_score_confiance": "",
                    "score_gap_top2": "",
                    "recommendation_source": "",
                    "recommendation_decision": "rejeter",
                    "recommendation_alerts": "aucun_candidat",
                    "top3_accounts": "",
                    "top3_metiers": "",
                    "top3_articles": "",
                    "top1_match_reason": "",
                }
            )
            continue

        summary["matched_total"] += 1
        by_metier[metier_base]["matched_total"] += 1

        line_matches = list(details.get("line_matches") or [])
        top1 = line_matches[0] if line_matches else {}
        expected_account = str(item.get("compte_comptable") or "").strip()
        predicted_account = str((accounts[0] or {}).get("account_number") or "").strip()
        expected_metier = metier_base
        predicted_metier = str(top1.get("predicted_metier") or "").strip()
        account_match = expected_account == predicted_account
        metier_match = expected_metier == predicted_metier
        decision = str(details.get("decision") or "validation_humaine")

        summary["account_match_total"] += 1 if account_match else 0
        summary["metier_match_total"] += 1 if metier_match else 0
        summary[f"decision_{decision}_total"] += 1
        by_metier[metier_base]["account_match_total"] += 1 if account_match else 0
        by_metier[metier_base]["metier_match_total"] += 1 if metier_match else 0
        by_metier[metier_base][f"decision_{decision}_total"] += 1

        top3_accounts_values = list(top1.get("top3_accounts") or [])
        top3_metiers_values = list(top1.get("top3_metiers") or [])
        top3_articles_values = list(top1.get("top3_articles") or [])
        top3_scores = []
        predicted_score = top1.get("predicted_score")
        if predicted_score is not None:
            top3_scores.append(predicted_score)
        while len(top3_scores) < len(top3_accounts_values):
            top3_scores.append("")

        results.append(
            {
                "base_file": row["base_file"],
                "metier_base": metier_base,
                "client_siren": client_siren,
                "client_ape_used": client_ape or "",
                "client_ape_source": client_ape_source,
                "article_source": str(item.get("article_source") or "").strip(),
                "article_canonique": str(item.get("article_canonique") or "").strip(),
                "tva_rate": item.get("tva_rate") if item.get("tva_rate") is not None else "",
                "expected_compte_comptable": expected_account,
                "predicted_compte_comptable": predicted_account,
                "account_match": "yes" if account_match else "no",
                "expected_metier": expected_metier,
                "predicted_metier": predicted_metier,
                "metier_match": "yes" if metier_match else "no",
                "predicted_categorie": str(top1.get("predicted_categorie") or "").strip(),
                "predicted_sous_categorie": str(top1.get("predicted_sous_categorie") or "").strip(),
                "predicted_score_confiance": predicted_score if predicted_score is not None else "",
                "score_gap_top2": top1.get("score_gap_top2") if top1.get("score_gap_top2") is not None else "",
                "recommendation_source": source_label or "",
                "recommendation_decision": decision,
                "recommendation_alerts": " | ".join(details.get("alerts") or top1.get("recommendation_alerts") or []),
                "top3_accounts": top_summary(top3_accounts_values, top3_scores),
                "top3_metiers": top_summary(top3_metiers_values, top3_scores),
                "top3_articles": top_summary(top3_articles_values, top3_scores),
                "top1_match_reason": str(top1.get("top1_reason") or "").strip(),
            }
        )

    if summary["items_total"]:
        summary["match_rate"] = round(100.0 * summary["matched_total"] / summary["items_total"], 2)
        summary["account_match_rate"] = round(100.0 * summary["account_match_total"] / summary["items_total"], 2)
        summary["metier_match_rate"] = round(100.0 * summary["metier_match_total"] / summary["items_total"], 2)
    else:
        summary["match_rate"] = 0.0
        summary["account_match_rate"] = 0.0
        summary["metier_match_rate"] = 0.0

    summary["by_metier"] = {}
    for metier, counter in sorted(by_metier.items()):
        total = counter.get("items_total", 0)
        matched = counter.get("matched_total", 0)
        account_match = counter.get("account_match_total", 0)
        metier_match = counter.get("metier_match_total", 0)
        summary["by_metier"][metier] = {
            "items_total": total,
            "matched_total": matched,
            "no_match_total": counter.get("no_match_total", 0),
            "account_match_total": account_match,
            "metier_match_total": metier_match,
            "decision_auto_ok_total": counter.get("decision_auto_ok_total", 0),
            "decision_validation_humaine_total": counter.get("decision_validation_humaine_total", 0),
            "match_rate": round(100.0 * matched / total, 2) if total else 0.0,
            "account_match_rate": round(100.0 * account_match / total, 2) if total else 0.0,
            "metier_match_rate": round(100.0 * metier_match / total, 2) if total else 0.0,
        }

    return results, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "base_file",
        "metier_base",
        "client_siren",
        "client_ape_used",
        "client_ape_source",
        "article_source",
        "article_canonique",
        "tva_rate",
        "expected_compte_comptable",
        "predicted_compte_comptable",
        "account_match",
        "expected_metier",
        "predicted_metier",
        "metier_match",
        "predicted_categorie",
        "predicted_sous_categorie",
        "predicted_score_confiance",
        "score_gap_top2",
        "recommendation_source",
        "recommendation_decision",
        "recommendation_alerts",
        "top3_accounts",
        "top3_metiers",
        "top3_articles",
        "top1_match_reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local recommendation/evaluation report for product metier profiles."
    )
    parser.add_argument(
        "--out-json",
        default="v1_519665103_product_metier_recommendations_v1.json",
        help="Output JSON report.",
    )
    parser.add_argument(
        "--out-csv",
        default="v1_519665103_product_metier_recommendations_v1.csv",
        help="Output CSV report.",
    )
    args = parser.parse_args()

    out_json = (SCRIPT_DIR / args.out_json).resolve()
    out_csv = (SCRIPT_DIR / args.out_csv).resolve()

    module = load_generator_module()
    generator = build_local_generator(module)
    rows = load_items_from_bases()
    results, summary = evaluate_rows(rows, generator)

    payload = {
        "meta": {
            "generated_at": now_iso(),
            "source_files": PRODUCT_BASE_FILES,
            "items_total": summary["items_total"],
            "matched_total": summary["matched_total"],
            "no_match_total": summary["no_match_total"],
            "match_rate": summary["match_rate"],
            "account_match_rate": summary["account_match_rate"],
            "metier_match_rate": summary["metier_match_rate"],
            "decision_auto_ok_total": summary["decision_auto_ok_total"],
            "decision_validation_humaine_total": summary["decision_validation_humaine_total"],
            "decision_rejeter_total": summary["decision_rejeter_total"],
            "by_metier": summary["by_metier"],
        },
        "items": results,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(out_csv, results)

    print(f"[INFO] items_total={summary['items_total']}")
    print(f"[INFO] matched_total={summary['matched_total']}")
    print(f"[INFO] match_rate={summary['match_rate']}%")
    print(f"[INFO] account_match_rate={summary['account_match_rate']}%")
    print(f"[INFO] metier_match_rate={summary['metier_match_rate']}%")
    print(f"[INFO] decision_auto_ok_total={summary['decision_auto_ok_total']}")
    print(f"[INFO] decision_validation_humaine_total={summary['decision_validation_humaine_total']}")
    print(f"[OK] json={out_json}")
    print(f"[OK] csv={out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
