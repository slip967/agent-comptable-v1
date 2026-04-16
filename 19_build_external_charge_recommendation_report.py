#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
MATCHER_PATH = SCRIPT_DIR / "10_match_reference_v1.py"


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_matcher_module():
    spec = importlib.util.spec_from_file_location("match_reference_v1_module", MATCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {MATCHER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_detail_items(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload.get("items") or []


def top_values(counter_like: list[list[object]]) -> list[str]:
    values: list[str] = []
    for row in counter_like or []:
        if not row:
            continue
        value = str(row[0] or "").strip()
        if value:
            values.append(value)
    return values


def patch_candidate_with_context(candidate: dict, ref, source: dict) -> dict:
    patched = dict(candidate)
    reasons = [part.strip() for part in str(patched.get("match_reason") or "").split(",") if part.strip()]
    score = float(patched.get("score_confiance") or 0.0)

    issuer_apes = set(top_values(source.get("issuer_apes_top") or []))
    ref_ape_context = {str(value).strip() for value in getattr(ref, "ape_context", []) if str(value).strip()}
    if issuer_apes and ref_ape_context and issuer_apes & ref_ape_context:
        score += 5.0
        reasons.append("ape_context_match")

    source_invoice_ids = set(source.get("source_invoice_ids") or [])
    ref_invoice_ids = set(getattr(ref, "source_invoice_ids", []) or [])
    if source_invoice_ids and ref_invoice_ids:
        overlap = len(source_invoice_ids & ref_invoice_ids)
        if overlap:
            score += min(6.0, 2.0 * overlap)
            reasons.append(f"source_invoice_overlap={overlap}")

    patched["score_confiance"] = round(min(100.0, score), 2)
    patched["match_reason"] = ", ".join(dict.fromkeys(reasons))
    return patched


def is_exact_article_source_hit(row: dict) -> bool:
    reason = str((row or {}).get("raison_match") or "")
    if "match exact article_source" in reason:
        return True
    return int((row or {}).get("match_priority") or 0) >= 4


def decide_recommendation(top_rows: list[dict]) -> tuple[str, list[str], float]:
    if not top_rows:
        return "rejeter", ["aucun_candidat"], 0.0

    alerts: list[str] = []
    top1 = top_rows[0]
    score_gap_top2 = round(float(top1.get("score_confiance") or 0.0) - float((top_rows[1].get("score_confiance") or 0.0) if len(top_rows) > 1 else 0.0), 2)

    decision = str(top1.get("decision_finale") or top1.get("decision") or "validation_humaine")
    if len(top_rows) > 1 and score_gap_top2 < 8.0:
        top2 = top_rows[1]
        top1_account = str(top1.get("compte_comptable") or "").strip()
        top2_account = str(top2.get("compte_comptable") or "").strip()
        top1_profile = str(top1.get("sous_profil") or "").strip()
        top2_profile = str(top2.get("sous_profil") or "").strip()
        top1_exact = is_exact_article_source_hit(top1)
        top2_exact = is_exact_article_source_hit(top2)

        if top1_exact and not top2_exact:
            decision = "auto_ok"
        elif top1_exact and top2_exact and top1_account and top1_account == top2_account:
            decision = "auto_ok"
        elif top1_account != top2_account or top1_profile != top2_profile:
            alerts.append("top_candidates_too_close")
            decision = "validation_humaine"
    if float(top1.get("score_confiance") or 0.0) < 70.0:
        alerts.append("score_trop_faible")
        decision = "validation_humaine"

    return decision, alerts, score_gap_top2


def build_top_summary(rows: list[dict], field: str) -> str:
    values: list[str] = []
    for row in rows:
        value = str(row.get(field) or "").strip()
        if value:
            values.append(f"{value} ({row.get('score_confiance')})")
    return " | ".join(values)


def evaluate_items(items: list[dict], matcher_module) -> tuple[list[dict], dict]:
    refs = [ref for ref in matcher_module.load_references() if getattr(ref, "metier", "") == "global"]
    results: list[dict] = []

    summary = {
        "items_total": 0,
        "account_match_total": 0,
        "sous_profil_match_total": 0,
        "decision_auto_ok_total": 0,
        "decision_validation_humaine_total": 0,
        "decision_rejeter_total": 0,
    }

    for item in items:
        source = item.get("source") or {}
        query_text = str(source.get("article_source") or "").strip()
        if not query_text:
            continue

        tva_rate = source.get("tva_rate")
        scored = []
        for ref in refs:
            row = matcher_module.score_reference(query_text, ref, metier_hint="global", tva_hint=tva_rate)
            row = patch_candidate_with_context(row, ref, source)
            scored.append(row)

        scored.sort(
            key=lambda row: (
                -float(row.get("score_confiance") or 0.0),
                -int(row.get("match_priority") or 0),
                -matcher_module.decision_rank(row.get("decision_finale")),
                -matcher_module.coherence_rank(row.get("tva_coherence")),
                str(row.get("article_source_match") or ""),
                str(row.get("compte_comptable") or ""),
            )
        )
        top3 = scored[:3]
        top1 = top3[0] if top3 else {}

        recommendation_decision, recommendation_alerts, score_gap_top2 = decide_recommendation(top3)
        expected_account = str(source.get("compte_comptable") or "").strip()
        expected_sous_profil = str(source.get("sous_profil") or "").strip()
        predicted_account = str(top1.get("compte_comptable") or "").strip()
        predicted_sous_profil = str(top1.get("sous_profil") or "").strip()
        account_match = expected_account == predicted_account
        sous_profil_match = expected_sous_profil == predicted_sous_profil

        summary["items_total"] += 1
        summary["account_match_total"] += 1 if account_match else 0
        summary["sous_profil_match_total"] += 1 if sous_profil_match else 0
        summary[f"decision_{recommendation_decision}_total"] += 1

        results.append(
            {
                "item_id": item.get("item_id") or "",
                "article_source": query_text,
                "issuer_name_main": ((source.get("source_invoices") or [{}])[0] or {}).get("issuer_name") or "",
                "issuer_ape_main": ((source.get("source_invoices") or [{}])[0] or {}).get("issuer_ape") or "",
                "tva_rate": tva_rate if tva_rate is not None else "",
                "expected_compte_comptable": expected_account,
                "predicted_compte_comptable": predicted_account,
                "account_match": "yes" if account_match else "no",
                "expected_sous_profil": expected_sous_profil,
                "predicted_sous_profil": predicted_sous_profil,
                "sous_profil_match": "yes" if sous_profil_match else "no",
                "predicted_profil_facturation": str(top1.get("profil_facturation") or "").strip(),
                "predicted_score_confiance": top1.get("score_confiance") or "",
                "score_gap_top2": score_gap_top2,
                "recommendation_decision": recommendation_decision,
                "recommendation_alerts": " | ".join(recommendation_alerts),
                "top3_accounts": build_top_summary(top3, "compte_comptable"),
                "top3_sous_profils": build_top_summary(top3, "sous_profil"),
                "top3_articles": build_top_summary(top3, "article_source_match"),
                "top1_match_reason": str(top1.get("raison_match") or "").strip(),
                "top1_tva_coherence": str(top1.get("tva_coherence") or "").strip(),
                "top1_metier_coherence": str(top1.get("metier_coherence") or "").strip(),
            }
        )

    if summary["items_total"]:
        summary["account_match_rate"] = round(100.0 * summary["account_match_total"] / summary["items_total"], 2)
        summary["sous_profil_match_rate"] = round(100.0 * summary["sous_profil_match_total"] / summary["items_total"], 2)
    else:
        summary["account_match_rate"] = 0.0
        summary["sous_profil_match_rate"] = 0.0

    return results, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "item_id",
        "article_source",
        "issuer_name_main",
        "issuer_ape_main",
        "tva_rate",
        "expected_compte_comptable",
        "predicted_compte_comptable",
        "account_match",
        "expected_sous_profil",
        "predicted_sous_profil",
        "sous_profil_match",
        "predicted_profil_facturation",
        "predicted_score_confiance",
        "score_gap_top2",
        "recommendation_decision",
        "recommendation_alerts",
        "top3_accounts",
        "top3_sous_profils",
        "top3_articles",
        "top1_match_reason",
        "top1_tva_coherence",
        "top1_metier_coherence",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local recommendation/evaluation report for external charge profiles."
    )
    parser.add_argument(
        "--input-json",
        default="v1_519665103_profile_charges_externes_detail_v1.json",
        help="Detailed external charges profile JSON.",
    )
    parser.add_argument(
        "--out-json",
        default="v1_519665103_external_charge_recommendations_v1.json",
        help="Output JSON report.",
    )
    parser.add_argument(
        "--out-csv",
        default="v1_519665103_external_charge_recommendations_v1.csv",
        help="Output CSV report.",
    )
    args = parser.parse_args()

    input_path = (SCRIPT_DIR / args.input_json).resolve()
    out_json = (SCRIPT_DIR / args.out_json).resolve()
    out_csv = (SCRIPT_DIR / args.out_csv).resolve()

    matcher_module = load_matcher_module()
    items = load_detail_items(input_path)
    rows, summary = evaluate_items(items, matcher_module)

    payload = {
        "meta": {
            "generated_at": now_iso(),
            "source_file": str(input_path),
            "items_total": summary["items_total"],
            "account_match_rate": summary["account_match_rate"],
            "sous_profil_match_rate": summary["sous_profil_match_rate"],
            "decision_auto_ok_total": summary["decision_auto_ok_total"],
            "decision_validation_humaine_total": summary["decision_validation_humaine_total"],
            "decision_rejeter_total": summary["decision_rejeter_total"],
        },
        "items": rows,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(out_csv, rows)

    print(f"[INFO] items_total={summary['items_total']}")
    print(f"[INFO] account_match_rate={summary['account_match_rate']}%")
    print(f"[INFO] sous_profil_match_rate={summary['sous_profil_match_rate']}%")
    print(f"[INFO] decision_auto_ok_total={summary['decision_auto_ok_total']}")
    print(f"[INFO] decision_validation_humaine_total={summary['decision_validation_humaine_total']}")
    print(f"[OK] json={out_json}")
    print(f"[OK] csv={out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
