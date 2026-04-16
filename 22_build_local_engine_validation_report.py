#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_EXTERNAL_JSON = "v1_519665103_external_charge_recommendations_v1.json"
DEFAULT_PRODUCT_JSON = "v1_519665103_product_metier_recommendations_v1.json"
DEFAULT_OUT_MD = "rapport_moteur_local_v1.md"

METIER_LABELS = {
    "boulangerie": "Boulangerie",
    "boucherie": "Boucherie",
    "restaurant": "Restaurant",
    "btp": "BTP",
    "transport": "Transport",
    "vtc": "VTC",
    "epicerie": "Epicerie",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def md_cell(value) -> str:
    return str(value).replace("|", "\\|")


def append_table(lines: list[str], headers: list[str], rows: list[list[object]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")


def get_ambiguous_rows(items: list[dict], decision_key: str) -> list[dict]:
    return [row for row in items if str(row.get(decision_key) or "") == "validation_humaine"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a consolidated markdown report for the local recommendation engine."
    )
    parser.add_argument("--external-json", default=DEFAULT_EXTERNAL_JSON)
    parser.add_argument("--product-json", default=DEFAULT_PRODUCT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    external_path = (SCRIPT_DIR / args.external_json).resolve()
    product_path = (SCRIPT_DIR / args.product_json).resolve()
    out_md = (SCRIPT_DIR / args.out_md).resolve()

    external_payload = load_json(external_path)
    product_payload = load_json(product_path)

    external_meta = external_payload.get("meta") or {}
    external_items = list(external_payload.get("items") or [])
    product_meta = product_payload.get("meta") or {}
    product_items = list(product_payload.get("items") or [])

    total_items = int(external_meta.get("items_total") or 0) + int(product_meta.get("items_total") or 0)
    total_auto_ok = int(external_meta.get("decision_auto_ok_total") or 0) + int(product_meta.get("decision_auto_ok_total") or 0)
    total_validation = int(external_meta.get("decision_validation_humaine_total") or 0) + int(product_meta.get("decision_validation_humaine_total") or 0)
    total_reject = int(external_meta.get("decision_rejeter_total") or 0) + int(product_meta.get("decision_rejeter_total") or 0)

    external_ambiguous = get_ambiguous_rows(external_items, "recommendation_decision")
    product_ambiguous = get_ambiguous_rows(product_items, "recommendation_decision")

    lines = [
        "# Rapport Moteur Local V1",
        "",
        "Ce rapport consolide les resultats locaux du moteur de recommandation comptable sur les charges externes et les produits metier.",
        "",
        "## Synthese Globale",
        "",
        f"- Elements evalues : `{total_items}`",
        f"- `auto_ok` : `{total_auto_ok}`",
        f"- `validation_humaine` : `{total_validation}`",
        f"- `rejeter` : `{total_reject}`",
        f"- Taux de validation automatique global : `{(100.0 * total_auto_ok / total_items):.1f}%`" if total_items else "- Taux de validation automatique global : `0.0%`",
        "",
        "## Charges Externes",
        "",
        f"- Elements evalues : `{external_meta.get('items_total', 0)}`",
        f"- Taux bon compte : `{external_meta.get('account_match_rate', 0)}%`",
        f"- Taux bon sous-profil : `{external_meta.get('sous_profil_match_rate', 0)}%`",
        f"- `auto_ok` : `{external_meta.get('decision_auto_ok_total', 0)}`",
        f"- `validation_humaine` : `{external_meta.get('decision_validation_humaine_total', 0)}`",
        "",
        "## Produits Metier",
        "",
        f"- Elements evalues : `{product_meta.get('items_total', 0)}`",
        f"- Taux de match : `{product_meta.get('match_rate', 0)}%`",
        f"- Taux bon compte : `{product_meta.get('account_match_rate', 0)}%`",
        f"- Taux bon metier : `{product_meta.get('metier_match_rate', 0)}%`",
        f"- `auto_ok` : `{product_meta.get('decision_auto_ok_total', 0)}`",
        f"- `validation_humaine` : `{product_meta.get('decision_validation_humaine_total', 0)}`",
        "",
        "## Repartition Par Metier",
        "",
    ]

    by_metier_rows: list[list[object]] = []
    for metier, stats in sorted((product_meta.get("by_metier") or {}).items(), key=lambda item: item[0]):
        by_metier_rows.append(
            [
                METIER_LABELS.get(metier, metier),
                stats.get("items_total", 0),
                stats.get("decision_auto_ok_total", 0),
                stats.get("decision_validation_humaine_total", 0),
                f"{stats.get('account_match_rate', 0)}%",
                f"{stats.get('metier_match_rate', 0)}%",
            ]
        )
    append_table(
        lines,
        ["Metier", "Items", "auto_ok", "validation_humaine", "Bon compte", "Bon metier"],
        by_metier_rows,
    )

    lines.extend(
        [
            "",
            "## Cas Ambigus Charges Externes",
            "",
        ]
    )
    if external_ambiguous:
        external_rows = []
        for row in external_ambiguous[:10]:
            external_rows.append(
                [
                    row.get("article_source", ""),
                    row.get("expected_compte_comptable", ""),
                    row.get("predicted_compte_comptable", ""),
                    row.get("recommendation_alerts", ""),
                ]
            )
        append_table(
            lines,
            ["Article", "Compte attendu", "Compte propose", "Alerte"],
            external_rows,
        )
    else:
        lines.append("Aucun cas ambigu sur les charges externes.")

    lines.extend(
        [
            "",
            "## Cas Ambigus Produits Metier",
            "",
        ]
    )
    if product_ambiguous:
        product_rows = []
        for row in product_ambiguous[:15]:
            product_rows.append(
                [
                    row.get("metier_base", ""),
                    row.get("article_source", ""),
                    row.get("expected_compte_comptable", ""),
                    row.get("predicted_compte_comptable", ""),
                    row.get("recommendation_alerts", ""),
                ]
            )
        append_table(
            lines,
            ["Metier", "Article", "Compte attendu", "Compte propose", "Alerte"],
            product_rows,
        )
    else:
        lines.append("Aucun cas ambigu sur les produits metier.")

    lines.extend(
        [
            "",
            "## Sources",
            "",
            f"- Charges externes : `{external_path.name}`",
            f"- Produits metier : `{product_path.name}`",
        ]
    )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] md={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
