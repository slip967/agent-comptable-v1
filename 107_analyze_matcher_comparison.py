#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORT_BEFORE = ROOT / "random_invoice_form_fuzzy_match_report_40_more.json"
REPORT_AFTER = ROOT / "random_invoice_form_fuzzy_match_report_40_more_after_engine_update.json"
OUT_SHIFT = ROOT / "decision_shift_validation_to_reject.md"
OUT_FAMILIES = ROOT / "enrichment_priority_families.md"


BASE_LABELS = {
    "base_produits_boulangerie_v1.json": "Boulangerie",
    "base_produits_boucherie_v1.json": "Boucherie",
    "base_produits_restaurant_v1.json": "Restaurant",
    "base_produits_btp_v1.json": "BTP",
    "base_produits_vtc_v1.json": "VTC",
    "base_produits_epicerie_v1.json": "Epicerie",
    "base_produits_transport_v1.json": "Transport",
    "base_charges_externes_v1.json": "Charges externes",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def top1(line: dict) -> dict | None:
    matches = list(line.get("top_matches") or [])
    return matches[0] if matches else None


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def family_of(text: str) -> str:
    t = normalize_text(text)
    if any(k in t for k in ["remise", "option", "periode", "avoir", "escompte", "taxe", "debits", "regularisation", "avantage"]):
        return "remises / options / periodes / lignes non comptables"
    if any(k in t for k in ["bbox", "bouygues", "byou", "b you", "forfait", "fibre", "internet", "telephonie", "telephone", "multi tv", "livebox"]):
        return "telecom / forfaits / bbox / b&you"
    if any(k in t for k in ["recharge", "lycamobile", "syma", "symacom", "orange", "sfr la carte", "lebara", "transcash"]):
        return "recharges telephoniques"
    if any(k in t for k in ["gazole", "diesel", "excellium", "sp98", "carburant", "lavage", "adblue", "station"]):
        return "carburant / gazole / lavage"
    if any(k in t for k in ["epice", "sauce", "colorant", "paprika", "piment"]):
        return "epices / sauces / colorants"
    if any(k in t for k in ["saucisse", "merguez", "steak", "jambon", "dinde", "viande", "poulet halal", "boeuf", "veau"]):
        return "saucisse / merguez / viande transformee"
    if any(k in t for k in ["lame", "ruban", "coutellerie", "supinox", "inox"]):
        return "materiel boucherie / coutellerie"
    if any(
        k in t
        for k in [
            "peinture",
            "mastic",
            "diluant",
            "filtre",
            "moteur",
            "plaquette",
            "frein",
            "amortisseur",
            "vernis",
            "poncage",
            "ponssage",
            "mirka",
            "debeer",
            "mipa",
            "primer",
            "pare brise",
            "retro",
            "feu arr",
            "agrafe",
            "epange",
            "eponge",
            "skotch",
            "plateau",
            "durcisseur",
            "bombe",
            "p80",
            "p800",
            "pps",
            "auge",
            "enduire",
            "taloche",
            "platoir",
        ]
    ):
        return "BTP / peinture / mastic / diluant / filtre / moteur / plaquette"
    if any(
        k in t
        for k in [
            "cristaline",
            "coca",
            "oasis",
            "tropico",
            "schweppes",
            "perrier",
            "mirinda",
            "selecto",
            "orangina",
            "boga",
            "capri sun",
            "lait",
            "semoule",
            "farine",
            "huile",
            "creme",
            "citron",
            "film alimentaire",
            "papier toilette",
            "calypso",
            "san pellegrino",
            "seven up",
        ]
    ):
        return "produits METRO / alimentation generale"
    if any(
        k in t
        for k in [
            "javel",
            "cotton",
            "spray",
            "nettoyant",
            "surface",
            "lessive",
            "mouchoir",
            "gel",
            "vaisselle",
            "brosse a dents",
            "assouplissant",
            "anti odeur",
            "classic normal",
            "soft white",
        ]
    ):
        return "hygiene / entretien / droguerie"
    return "autres / a analyser"


def family_recommendation(family: str) -> str:
    if family == "remises / options / periodes / lignes non comptables":
        return "filtrer comme non_comptable"
    if family in {"telecom / forfaits / bbox / b&you", "recharges telephoniques"}:
        return "ajouter regle metier"
    if family in {"produits METRO / alimentation generale", "epices / sauces / colorants", "saucisse / merguez / viande transformee", "carburant / gazole / lavage"}:
        return "enrichir base JSON"
    if family in {"BTP / peinture / mastic / diluant / filtre / moteur / plaquette", "materiel boucherie / coutellerie"}:
        return "ajouter synonymes"
    if family == "hygiene / entretien / droguerie":
        return "garder en validation humaine"
    return "garder en validation humaine"


def escape_md(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def human_base_label(value: str | None) -> str:
    if not value:
        return "Non renseigne"
    return BASE_LABELS.get(value, value)


def shift_reason(before_top: dict, after_top: dict, text: str) -> str:
    reasons: list[str] = []
    old_score = float(before_top.get("score_confiance") or 0.0)
    new_score = float(after_top.get("score_confiance") or 0.0)
    if after_top.get("metier_coherence") == "incoherente":
        reasons.append("l'incoherence metier est maintenant bloquante")
    if old_score < 70.0 and new_score < 70.0:
        reasons.append(f"le score {new_score:.2f} est desormais sous le seuil de 70")
    elif new_score < old_score:
        reasons.append("le score a ete devalue apres renforcement des regles")
    if after_top.get("tva_coherence") == "a_verifier":
        reasons.append("la TVA reste seulement partiellement coherente")
    if after_top.get("metier_coherence") == "a_verifier":
        reasons.append("le contexte activite/APE ne confirme pas assez le metier")
    if not reasons:
        reasons.append("la combinaison score + coherence ne suffit plus a maintenir la ligne en validation humaine")
    return "; ".join(reasons)


def reject_assessment(text: str, before_top: dict, after_top: dict) -> tuple[str, str]:
    family = family_of(text)
    old_base = str(before_top.get("base_cible") or "")
    old_account = str(before_top.get("compte_comptable") or "")
    old_score = float(before_top.get("score_confiance") or 0.0)

    plausible_stock_match = old_base == "base_produits_epicerie_v1.json" and old_account in {"607", "601", "6011"}
    plausible_telecom_match = family in {"telecom / forfaits / bbox / b&you", "recharges telephoniques"} and old_base == "base_produits_epicerie_v1.json"
    plausible_auto_match = family == "BTP / peinture / mastic / diluant / filtre / moteur / plaquette" and old_score >= 68.0

    if family == "remises / options / periodes / lignes non comptables":
        return "logique", "ligne non comptable ou trop administrative"
    if after_top.get("metier_coherence") == "incoherente" and plausible_telecom_match:
        return "a revoir", "la ligne ressemble a une vraie recharge/vente telecom, mais la coherence metier est trop dure"
    if plausible_stock_match:
        return "a revoir", "la ligne ressemble a un vrai article de revente/alimentaire et merite plutot un enrichissement du referentiel"
    if plausible_auto_match:
        return "a revoir", "la ligne ressemble a une vraie piece ou consommable atelier, mais les synonymes/metiers sont insuffisants"
    if old_base in {"base_produits_vtc_v1.json", "base_charges_externes_v1.json", "base_produits_restaurant_v1.json"} and family == "produits METRO / alimentation generale":
        return "logique", "la proposition historique pointait deja vers une base peu credible pour une boisson ou un produit d'epicerie"
    if family == "hygiene / entretien / droguerie":
        return "logique", "la ligne peut relever soit de la revente soit de la consommation interne, donc le rejet prudent se tient"
    return "logique", "la proposition reste trop faible ou trop ambigue pour etre gardee en validation humaine"


def build_maps(report: dict) -> dict[tuple[str, int], tuple[dict, dict, dict | None]]:
    mapping: dict[tuple[str, int], tuple[dict, dict, dict | None]] = {}
    for invoice in report.get("invoice_forms", []):
        for line in invoice.get("line_matches", []):
            mapping[(str(invoice.get("invoice_id") or ""), int(line.get("line_index") or 0))] = (
                invoice,
                line,
                top1(line),
            )
    return mapping


def write_shift_report(before: dict, after: dict) -> list[dict]:
    before_map = build_maps(before)
    after_map = build_maps(after)
    shifts: list[dict] = []

    for key, (invoice_before, line_before, top_before) in before_map.items():
        if top_before is None or top_before.get("decision_finale") != "validation_humaine":
            continue
        candidate_after = after_map.get(key)
        if candidate_after is None:
            continue
        invoice_after, line_after, top_after = candidate_after
        if top_after is None or top_after.get("decision_finale") != "rejeter":
            continue

        verdict, verdict_note = reject_assessment(line_before.get("line_text") or "", top_before, top_after)
        shifts.append(
            {
                "invoice_id": invoice_before.get("invoice_id"),
                "fournisseur": invoice_before.get("issuer_name") or "Non renseigne",
                "client": invoice_before.get("recipient_name") or "Non renseigne",
                "line_text": line_before.get("line_text") or "Non renseigne",
                "before_decision": top_before.get("decision_finale") or "Non renseigne",
                "before_score": float(top_before.get("score_confiance") or 0.0),
                "after_decision": top_after.get("decision_finale") or "Non renseigne",
                "after_score": float(top_after.get("score_confiance") or 0.0),
                "before_base": human_base_label(top_before.get("base_cible")),
                "after_base": human_base_label(top_after.get("base_cible")),
                "before_account": top_before.get("compte_comptable") or "Non renseigne",
                "after_account": top_after.get("compte_comptable") or "Non renseigne",
                "reason": shift_reason(top_before, top_after, line_before.get("line_text") or ""),
                "assessment": verdict,
                "assessment_note": verdict_note,
                "family": family_of(line_before.get("line_text") or ""),
            }
        )

    shifts.sort(key=lambda row: (row["family"], row["fournisseur"], row["invoice_id"], row["line_text"]))

    lines: list[str] = []
    lines.append("# Analyse des bascules validation_humaine -> rejeter")
    lines.append("")
    lines.append(f"- Lot compare: `40` factures, meme perimetre avant/apres.")
    lines.append(f"- Nombre de bascules observees: `{len(shifts)}`.")
    lines.append("- Lecture: ces lignes etaient jugées assez credibles pour une validation humaine avant, puis sont passees en rejet apres durcissement du moteur.")
    lines.append("")
    lines.append("| invoice_id | Fournisseur | Client | line_item | Ancienne decision | Ancien score | Nouvelle decision | Nouveau score | Ancienne base | Nouvelle base | Ancien compte | Nouveau compte | Raison du changement | Rejet logique ou a revoir |")
    lines.append("|---|---|---|---|---|---:|---|---:|---|---|---|---|---|---|")
    for row in shifts:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(row["invoice_id"]),
                    escape_md(row["fournisseur"]),
                    escape_md(row["client"]),
                    escape_md(row["line_text"]),
                    escape_md(row["before_decision"]),
                    f"{row['before_score']:.2f}",
                    escape_md(row["after_decision"]),
                    f"{row['after_score']:.2f}",
                    escape_md(row["before_base"]),
                    escape_md(row["after_base"]),
                    escape_md(row["before_account"]),
                    escape_md(row["after_account"]),
                    escape_md(row["reason"]),
                    escape_md(f"{row['assessment']} — {row['assessment_note']}"),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Lecture rapide")
    lines.append("")
    lines.append("- Les bascules viennent surtout du nouveau seuil `70` pour garder une ligne en `validation_humaine`.")
    lines.append("- Le plus gros bloc concerne des boissons / produits d'epicerie de type METRO/IDF: plusieurs lignes plausibles en `Epicerie/607` sont maintenant rejetees par prudence.")
    lines.append("- Quelques rejets sont sains: bases candidates peu credibles (`VTC`, `Restaurant`, `Charges externes`) pour des produits d'epicerie ou de surface.")
    lines.append("- Le cas `Recharge SYMACOM FORFAIT BLOQUE` montre une faiblesse residuelle: la recharge ressemble a un vrai article de revente, mais la coherence metier actuelle la rejette trop vite.")
    lines.append("")

    OUT_SHIFT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return shifts


def write_family_report(after: dict) -> None:
    stats = defaultdict(
        lambda: {
            "count": 0,
            "bases": Counter(),
            "accounts": Counter(),
            "decisions": Counter(),
            "scores": [],
            "examples": [],
        }
    )

    for invoice in after.get("invoice_forms", []):
        for line in invoice.get("line_matches", []):
            top = top1(line)
            if top is None:
                continue
            score = float(top.get("score_confiance") or 0.0)
            if top.get("decision_finale") != "rejeter" and score >= 70.0:
                continue

            family = family_of(line.get("line_text") or "")
            bucket = stats[family]
            bucket["count"] += 1
            bucket["bases"][human_base_label(top.get("base_cible"))] += 1
            bucket["accounts"][str(top.get("compte_comptable") or "Non renseigne")] += 1
            bucket["decisions"][str(top.get("decision_finale") or "Non renseigne")] += 1
            bucket["scores"].append(score)
            if len(bucket["examples"]) < 5:
                bucket["examples"].append(str(line.get("line_text") or ""))

    rows: list[dict] = []
    for family, bucket in stats.items():
        if bucket["count"] <= 0:
            continue
        dominant_decision = bucket["decisions"].most_common(1)[0][0] if bucket["decisions"] else "Non renseigne"
        rows.append(
            {
                "family": family,
                "count": bucket["count"],
                "bases": ", ".join(f"{name} ({count})" for name, count in bucket["bases"].most_common(3)),
                "accounts": ", ".join(f"{name} ({count})" for name, count in bucket["accounts"].most_common(3)),
                "avg_score": round(sum(bucket["scores"]) / len(bucket["scores"]), 2),
                "dominant_decision": dominant_decision,
                "recommendation": family_recommendation(family),
                "examples": ", ".join(bucket["examples"]),
            }
        )

    rows.sort(key=lambda row: (-row["count"], row["family"]))

    lines: list[str] = []
    lines.append("# Priorites d'enrichissement des familles")
    lines.append("")
    lines.append("- Base d'analyse: lot des `40` factures re-testees avec le moteur durci.")
    lines.append("- Perimetre retenu: lignes en `rejeter` ou lignes sous `70` de score.")
    lines.append("")
    lines.append("| Famille | Nb lignes | Bases candidates frequentes | Comptes proposes frequents | Score moyen | Decision dominante | Recommandation | Exemples |")
    lines.append("|---|---:|---|---|---:|---|---|---|")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(row["family"]),
                    str(row["count"]),
                    escape_md(row["bases"]),
                    escape_md(row["accounts"]),
                    f"{row['avg_score']:.2f}",
                    escape_md(row["dominant_decision"]),
                    escape_md(row["recommendation"]),
                    escape_md(row["examples"]),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Conclusion courte")
    lines.append("")
    lines.append("- Le moteur s'est ameliore sur la prudence: il garde moins de faux candidats en `validation_humaine` et rejette plus franchement les lignes faibles.")
    lines.append("- Ce qui reste faible: les boissons/produits d'epicerie, les recharges telephoniques revendues en magasin, et les libelles atelier/carrosserie tres abbreviés.")
    lines.append("- Familles a enrichir en priorite: `produits METRO / alimentation generale`, `recharges telephoniques`, puis `BTP / peinture / mastic / diluant / filtre / moteur / plaquette`.")
    lines.append("- Regles metier a ajouter ensuite: filtrage des lignes non comptables, boost `Epicerie -> 607` pour boissons/recharges, et dictionnaire de synonymes OCR pour atelier/carrosserie.")
    lines.append("")

    OUT_FAMILIES.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    before = load_json(REPORT_BEFORE)
    after = load_json(REPORT_AFTER)
    write_shift_report(before, after)
    write_family_report(after)
    print(f"[OK] {OUT_SHIFT}")
    print(f"[OK] {OUT_FAMILIES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
