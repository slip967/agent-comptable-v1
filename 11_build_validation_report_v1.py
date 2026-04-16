#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
from collections import Counter, defaultdict
from pathlib import Path


INPUT_CSV = "matcher_v1_on_tests.csv"
OUT_MD = "rapport_validation_v1.md"
OUT_REVIEW_CSV = "rapport_validation_v1_a_revoir.csv"
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

METIER_LABELS = {
    "global": "Charges externes",
    "boulangerie": "Boulangerie",
    "boucherie": "Boucherie",
    "restaurant": "Restaurant",
    "btp": "BTP",
    "transport": "Transport",
    "vtc": "VTC",
    "epicerie": "Epicerie",
}

CATEGORY_LABELS = {
    "exploitation_metier": "Exploitation metier",
    "charges_externes": "Charges externes",
}

SUB_CATEGORY_LABELS = {
    "matiere_premiere": "Matiere premiere",
    "frais_service": "Frais de service",
    "consommable_chantier": "Consommables chantier",
    "locations": "Locations",
    "charges_generales": "Charges generales",
    "emballage": "Emballage",
    "entretien_reparation": "Entretien / reparation",
}

CHARGE_SUBPROFILE_LABELS = {
    "cotisations_professionnelles": "Cotisations professionnelles",
    "transport_et_logistique": "Transport et logistique",
    "frais_administratifs_et_bancaires": "Frais administratifs et bancaires",
    "loyers_et_charges_locatives": "Loyers et charges locatives",
    "entretien_et_maintenance": "Entretien et maintenance",
    "telecom_et_abonnements": "Telecom et abonnements",
    "energie_electricite": "Energie electricite",
    "energie_gaz": "Energie gaz",
    "assurances": "Assurances",
    "autres_charges_externes": "Autres charges externes",
}


def resolve_existing_path(filename: str) -> Path:
    candidates = [
        Path(".").resolve() / filename,
        SCRIPT_DIR / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def as_float(value: str | None) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def slug_label(value: str) -> str:
    return (value or "").strip() or "(vide)"


def display_label(value: str, mapping: dict[str, str] | None = None) -> str:
    raw = slug_label(value)
    if mapping and raw in mapping:
        return mapping[raw]
    return raw.replace("_", " ").strip().title()


def md_cell(value) -> str:
    return str(value).replace("|", "\\|")


def append_table(lines: list[str], headers: list[str], rows: list[list[object]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")


def detect_match_mode(reason: str) -> str:
    reason = reason or ""
    if "match exact article_source" in reason:
        return "exact_article_source"
    if "match normalise article_source" in reason:
        return "normalise_article_source"
    if "match normalise article_canonique" in reason:
        return "normalise_article_canonique"
    return "fuzzy_ou_mots_cles"


def build_examples(rows: list[dict]) -> list[dict]:
    selected: list[dict] = []
    seen_metiers: set[str] = set()
    for row in sorted(rows, key=lambda item: (item.get("metier") or "", item.get("article_source") or "")):
        metier = row.get("metier") or ""
        if metier in seen_metiers:
            continue
        selected.append(row)
        seen_metiers.add(metier)
    return selected


def write_review_csv(path: Path, review_rows: list[dict], review_fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=review_fields)
        writer.writeheader()
        for row in review_rows:
            writer.writerow({field: row.get(field, "") for field in review_fields})


def main() -> int:
    input_path = resolve_existing_path(INPUT_CSV)
    out_dir = input_path.parent
    rows = list(csv.DictReader(input_path.open("r", encoding="utf-8-sig", newline="")))

    if not rows:
        raise SystemExit("No rows found in matcher_v1_on_tests.csv")

    total = len(rows)
    by_decision = Counter(row.get("match_decision_finale") or "" for row in rows)
    by_tva = Counter(row.get("match_tva_coherence") or "" for row in rows)
    by_metier_coherence = Counter(row.get("match_metier_coherence") or "" for row in rows)
    by_match_mode = Counter(detect_match_mode(row.get("match_raison") or "") for row in rows)
    by_category = Counter(slug_label(row.get("match_categorie")) for row in rows)
    by_sub_category = Counter(slug_label(row.get("match_sous_categorie")) for row in rows)
    by_account = Counter(slug_label(row.get("match_compte_comptable")) for row in rows)
    by_charge_subprofile = Counter(
        slug_label(row.get("match_sous_profil"))
        for row in rows
        if slug_label(row.get("match_categorie")) == "charges_externes" and row.get("match_sous_profil")
    )
    alerts_counter = Counter()
    review_rows = [row for row in rows if (row.get("match_decision_finale") or "") != "auto_ok"]

    by_metier_stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "total": 0,
            "scores": [],
            "decisions": Counter(),
        }
    )

    for row in rows:
        metier = slug_label(row.get("metier"))
        stats = by_metier_stats[metier]
        stats["total"] += 1
        stats["scores"].append(as_float(row.get("match_score_confiance")))
        stats["decisions"][row.get("match_decision_finale") or ""] += 1

        for alert in (row.get("match_alertes") or "").split("|"):
            alert = alert.strip()
            if alert:
                alerts_counter[alert] += 1

    review_fields = [
        "base_file",
        "metier",
        "article_source",
        "tva_rate",
        "match_article_source",
        "match_metier",
        "match_compte_comptable",
        "match_sous_profil",
        "match_nature_charge",
        "match_profil_facturation",
        "match_tva_rate",
        "match_tva_coherence",
        "match_metier_coherence",
        "match_score_confiance",
        "match_decision_initiale",
        "match_decision_finale",
        "match_raison",
        "match_alertes",
        "match_source_invoice_ids",
    ]

    review_csv = out_dir / OUT_REVIEW_CSV
    write_review_csv(review_csv, review_rows, review_fields)

    auto_ok_rate = (by_decision.get("auto_ok", 0) / total) * 100
    exact_match_rate = (by_match_mode.get("exact_article_source", 0) / total) * 100
    scores = [as_float(row.get("match_score_confiance")) for row in rows]
    example_rows = build_examples(rows)

    lines = [
        "# Rapport De Validation V1",
        "",
        "Ce rapport synthetise le comportement du matcher V1 sur le jeu de tests issu des bases produits et charges externes.",
        "",
        "## Synthese",
        "",
        f"- Lignes testees : `{total}`",
        f"- Taux de `auto_ok` : `{auto_ok_rate:.1f}%`",
        f"- `auto_ok` : `{by_decision.get('auto_ok', 0)}`",
        f"- `validation_humaine` : `{by_decision.get('validation_humaine', 0)}`",
        f"- `rejeter` : `{by_decision.get('rejeter', 0)}`",
        f"- Score de confiance moyen : `{(sum(scores) / total):.1f}`",
        f"- Score de confiance minimum : `{min(scores):.1f}`",
        "",
        "## Controle TVA",
        "",
        f"- `coherente` : `{by_tva.get('coherente', 0)}`",
        f"- `a_verifier` : `{by_tva.get('a_verifier', 0)}`",
        f"- `incoherente` : `{by_tva.get('incoherente', 0)}`",
        "",
        "## Controle Metier",
        "",
        f"- `coherente` : `{by_metier_coherence.get('coherente', 0)}`",
        f"- `a_verifier` : `{by_metier_coherence.get('a_verifier', 0)}`",
        f"- `incoherente` : `{by_metier_coherence.get('incoherente', 0)}`",
        "",
        "## Repartition Par Metier",
        "",
    ]

    metier_rows: list[list[object]] = []
    for metier, stats in sorted(by_metier_stats.items(), key=lambda item: (-item[1]["total"], item[0])):
        metier_scores = stats["scores"]
        decisions = stats["decisions"]
        metier_rows.append(
            [
                display_label(metier, METIER_LABELS),
                stats["total"],
                decisions.get("auto_ok", 0),
                decisions.get("validation_humaine", 0),
                decisions.get("rejeter", 0),
                f"{(sum(metier_scores) / len(metier_scores)):.1f}",
                f"{min(metier_scores):.1f}",
            ]
        )
    append_table(
        lines,
        ["Metier", "Lignes", "auto_ok", "validation_humaine", "rejeter", "Score moyen", "Score min"],
        metier_rows,
    )

    lines.extend(
        [
            "",
            "## Nature Des Matchs",
            "",
            f"- Correspondance exacte avec le libelle source : `{by_match_mode.get('exact_article_source', 0)}` soit `{exact_match_rate:.1f}%`",
            f"- Correspondance normalisee avec le libelle source : `{by_match_mode.get('normalise_article_source', 0)}`",
            f"- Correspondance normalisee avec le libelle canonique : `{by_match_mode.get('normalise_article_canonique', 0)}`",
            f"- Correspondance fuzzy ou par mots cles : `{by_match_mode.get('fuzzy_ou_mots_cles', 0)}`",
        ]
    )
    if alerts_counter:
        lines.append(f"- Alertes detectees : `{sum(alerts_counter.values())}`")
    else:
        lines.append("- Alertes detectees : `0`")

    lines.extend(
        [
            "",
            "## Repartition Des References",
            "",
            "### Categories",
            "",
        ]
    )
    append_table(
        lines,
        ["Categorie", "Lignes"],
        [
            [display_label(category, CATEGORY_LABELS), count]
            for category, count in sorted(by_category.items(), key=lambda item: (-item[1], item[0]))
        ],
    )

    lines.extend(
        [
            "",
            "### Sous Categories",
            "",
        ]
    )
    append_table(
        lines,
        ["Sous categorie", "Lignes"],
        [
            [display_label(sub_category, SUB_CATEGORY_LABELS), count]
            for sub_category, count in sorted(by_sub_category.items(), key=lambda item: (-item[1], item[0]))
        ],
    )

    lines.extend(
        [
            "",
            "### Comptes Comptables",
            "",
        ]
    )
    append_table(
        lines,
        ["Compte", "Lignes"],
        [
            [account, count]
            for account, count in sorted(by_account.items(), key=lambda item: (-item[1], item[0]))
        ],
    )

    if by_charge_subprofile:
        lines.extend(
            [
                "",
                "### Sous Profils Charges Externes",
                "",
            ]
        )
        append_table(
            lines,
            ["Sous profil", "Lignes"],
            [
                [display_label(subprofile, CHARGE_SUBPROFILE_LABELS), count]
                for subprofile, count in sorted(by_charge_subprofile.items(), key=lambda item: (-item[1], item[0]))
            ],
        )

    lines.extend(
        [
            "",
            "## Exemples De Matchs",
            "",
        ]
    )
    append_table(
        lines,
        ["Metier", "Article source", "Match propose", "Compte", "Sous profil", "TVA", "Score"],
        [
                [
                display_label(row.get("metier"), METIER_LABELS),
                row.get("article_source", ""),
                row.get("match_article_source", ""),
                row.get("match_compte_comptable", ""),
                display_label(row.get("match_sous_profil", ""), CHARGE_SUBPROFILE_LABELS) if row.get("match_sous_profil") else "-",
                row.get("tva_rate", ""),
                row.get("match_score_confiance", ""),
            ]
            for row in example_rows
        ],
    )

    lines.extend(
        [
            "",
            "## Cas A Revoir",
            "",
            f"- Nombre de lignes a revoir : `{len(review_rows)}`",
            f"- Detail CSV : `{OUT_REVIEW_CSV}`",
            "",
        ]
    )

    if review_rows:
        append_table(
            lines,
            ["Article source", "Match propose", "Compte", "Sous profil", "TVA source", "TVA ref", "TVA coherence", "Alertes"],
            [
                [
                    row.get("article_source", ""),
                    row.get("match_article_source", ""),
                    row.get("match_compte_comptable", ""),
                    display_label(row.get("match_sous_profil", ""), CHARGE_SUBPROFILE_LABELS) if row.get("match_sous_profil") else "-",
                    row.get("tva_rate", ""),
                    row.get("match_tva_rate", ""),
                    row.get("match_tva_coherence", ""),
                    row.get("match_alertes", ""),
                ]
                for row in review_rows
            ],
        )
    else:
        lines.append("Aucun cas a revoir sur ce lot de validation.")

    if alerts_counter:
        lines.extend(
            [
                "",
                "## Alertes Detaillees",
                "",
            ]
        )
        append_table(
            lines,
            ["Alerte", "Occurrences"],
            [[alert, count] for alert, count in alerts_counter.most_common()],
        )

    report_content = "\n".join(lines) + "\n"
    report_md = out_dir / OUT_MD
    report_md.write_text(report_content, encoding="utf-8")

    mirrored_paths: list[Path] = []
    if ROOT_DIR != out_dir:
        root_report_md = ROOT_DIR / OUT_MD
        root_review_csv = ROOT_DIR / OUT_REVIEW_CSV
        root_report_md.write_text(report_content, encoding="utf-8")
        write_review_csv(root_review_csv, review_rows, review_fields)
        mirrored_paths.extend([root_report_md, root_review_csv])

    print(f"[OK] md={report_md}")
    print(f"[OK] csv={review_csv}")
    for path in mirrored_paths:
        print(f"[OK] mirror={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
