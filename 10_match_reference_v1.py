#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR

BASE_FILES = {
    "boulangerie": "base_produits_boulangerie_v1.json",
    "boucherie": "base_produits_boucherie_v1.json",
    "restaurant": "base_produits_restaurant_v1.json",
    "btp": "base_produits_btp_v1.json",
    "vtc": "base_produits_vtc_v1.json",
    "epicerie": "base_produits_epicerie_v1.json",
    "transport": "base_produits_transport_v1.json",
    "global": "base_charges_externes_v1.json",
}

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
    "trim",
    "lot",
    "x",
}

TEMPORAL_TOKENS = {
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
}

BILLING_HINTS = {
    "abonnement",
    "consommation",
    "periode",
    "facture",
    "factures",
    "solde",
    "loyer",
    "charges",
    "locatives",
    "mensualite",
}

EXTERNAL_HINTS = {
    "abonnement",
    "loyer",
    "charge",
    "charges",
    "locatives",
    "frais",
    "entretien",
    "maintenance",
    "prestation",
    "service",
    "services",
    "assurance",
    "telecom",
    "telephone",
    "mobile",
    "internet",
    "fibre",
    "sim",
    "electricite",
    "edf",
    "gaz",
    "grdf",
    "coti",
    "cotisation",
    "interbev",
    "forfait",
    "port",
    "livraison",
    "transport",
    "parking",
    "stationnement",
    "locative",
    "relance",
    "desourisation",
}

UTILITY_HINTS = {
    "electricite",
    "edf",
    "gaz",
    "grdf",
    "eau",
    "kwh",
    "cspe",
    "loyer",
    "locatives",
}

FOOD_METIERS = {"boulangerie", "boucherie", "restaurant", "epicerie"}

METIER_KEYWORDS = {
    "boulangerie": {"farine", "levure", "semoule", "sucre", "lait", "oeufs", "huile", "pate"},
    "boucherie": {"boeuf", "veau", "volaille", "viande", "basse", "cote", "carcasse", "oeufs"},
    "restaurant": {"huile", "emballage", "film", "barquette", "boite", "emporter"},
    "btp": {"carrelage", "colle", "joint", "ragreage", "malaxeur", "perceuse", "chantier", "axton"},
    "vtc": {"uber", "chauffeur", "taxi", "vtc", "course", "trajet"},
    "epicerie": {"epicerie", "alimentaire", "boisson", "conserve", "riz", "pates", "huile"},
    "transport": {"camionnette", "ctte", "transport", "livraison", "camion", "stationnement", "parking"},
}


@dataclass
class ReferenceItem:
    base_file: str
    metier: str
    article_source: str
    article_canonique: str
    categorie: str
    sous_categorie: str
    compte_comptable: str
    tva_rate: float | None
    mots_cles: list[str]
    ape_context: list[str]
    source_invoice_ids: list[str]
    sous_profil: str
    nature_charge: str
    profil_facturation: str


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok and tok not in STOP_WORDS]


def important_tokens(tokens: set[str]) -> set[str]:
    important: set[str] = set()
    for tok in tokens:
        if tok in TEMPORAL_TOKENS:
            continue
        if re.fullmatch(r"(19|20)\d{2}", tok):
            continue
        if any(ch.isdigit() for ch in tok):
            important.add(tok)
            continue
        if len(tok) >= 4:
            important.add(tok)
    return important


def is_external_charge_like(value: str) -> bool:
    tokens = set(tokenize(value))
    return bool(tokens & EXTERNAL_HINTS)


def has_billing_context(tokens: set[str]) -> bool:
    if tokens & BILLING_HINTS:
        return True
    if tokens & TEMPORAL_TOKENS:
        return True
    return any(re.fullmatch(r"(19|20)\d{2}", tok) for tok in tokens)


def is_utility_charge_like(value: str) -> bool:
    tokens = set(tokenize(value))
    return bool(tokens & UTILITY_HINTS) and has_billing_context(tokens)


def load_references() -> list[ReferenceItem]:
    refs: list[ReferenceItem] = []
    for metier, filename in BASE_FILES.items():
        path = ROOT / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in data.get("items", []):
            refs.append(
                ReferenceItem(
                    base_file=filename,
                    metier=metier,
                    article_source=(item.get("article_source") or "").strip(),
                    article_canonique=(item.get("article_canonique") or "").strip(),
                    categorie=(item.get("categorie") or "").strip(),
                    sous_categorie=(item.get("sous_categorie") or "").strip(),
                    compte_comptable=(item.get("compte_comptable") or "").strip(),
                    tva_rate=item.get("tva_rate"),
                    mots_cles=list(item.get("mots_cles") or []),
                    ape_context=list(item.get("ape_context") or []),
                    source_invoice_ids=list(item.get("source_invoice_ids") or []),
                    sous_profil=(item.get("sous_profil") or "").strip(),
                    nature_charge=(item.get("nature_charge") or "").strip(),
                    profil_facturation=(item.get("profil_facturation") or "").strip(),
                )
            )
    return refs


def select_candidate_refs(
    refs: list[ReferenceItem],
    text: str,
    metier: str | None,
    include_charges: bool,
) -> list[ReferenceItem]:
    if metier:
        selected = [ref for ref in refs if ref.metier == metier]
        if include_charges or is_external_charge_like(text) or is_utility_charge_like(text):
            selected.extend(ref for ref in refs if ref.metier == "global")
        return selected

    if is_external_charge_like(text) or is_utility_charge_like(text):
        return list(refs)

    return [ref for ref in refs if ref.metier != "global"] + [ref for ref in refs if ref.metier == "global"]


def build_reason(reasons: list[str]) -> str:
    return ", ".join(dict.fromkeys(reasons))


def build_alerts(alerts: list[str]) -> list[str]:
    return list(dict.fromkeys(alerts))


def coherence_rank(value: str) -> int:
    order = {
        "coherente": 3,
        "a_verifier": 2,
        "inconnue": 1,
        "incoherente": 0,
    }
    return order.get(value or "", -1)


def decision_rank(value: str) -> int:
    order = {
        "auto_ok": 2,
        "validation_humaine": 1,
        "rejeter": 0,
    }
    return order.get(value or "", -1)


def expected_tva_rates(ref: ReferenceItem) -> set[float]:
    if ref.categorie == "charges_externes" or ref.metier == "global":
        if ref.sous_categorie in {"locations", "charges_generales"}:
            return {0.0, 20.0}
        return {20.0}
    if ref.sous_categorie == "emballage":
        return {20.0}
    if ref.metier in FOOD_METIERS:
        if ref.tva_rate is not None and abs(float(ref.tva_rate)) < 0.01:
            return {0.0}
        return {5.5}
    if ref.metier in {"btp", "transport", "vtc"}:
        return {20.0}
    return {float(ref.tva_rate)} if ref.tva_rate is not None else set()


def evaluate_tva_coherence(ref: ReferenceItem, tva_hint: float | None) -> tuple[str, list[str]]:
    alerts: list[str] = []
    if tva_hint is None:
        return "inconnue", alerts

    expected = expected_tva_rates(ref)
    try:
        tva = float(tva_hint)
    except Exception:
        alerts.append("tva_inexploitable")
        return "a_verifier", alerts

    if ref.tva_rate is not None and abs(tva - float(ref.tva_rate)) < 0.01:
        return "coherente", alerts

    if expected and any(abs(tva - val) < 0.01 for val in expected):
        alerts.append("tva_differe_de_la_reference")
        return "a_verifier", alerts

    alerts.append("tva_incoherente")
    return "incoherente", alerts


def evaluate_metier_coherence(text: str, ref: ReferenceItem, metier_hint: str | None) -> tuple[str, list[str]]:
    alerts: list[str] = []
    tokens = set(tokenize(text))

    if metier_hint:
        if ref.metier == metier_hint:
            return "coherente", alerts
        if ref.metier == "global" and (is_external_charge_like(text) or is_utility_charge_like(text)):
            return "coherente", alerts
        alerts.append("metier_reference_different_du_metier_attendu")
        return "incoherente", alerts

    if ref.metier == "global":
        if is_external_charge_like(text) or is_utility_charge_like(text):
            return "coherente", alerts
        alerts.append("ligne_non_typique_charges_externes")
        return "a_verifier", alerts

    expected_tokens = METIER_KEYWORDS.get(ref.metier, set())
    if expected_tokens and tokens & expected_tokens:
        return "coherente", alerts
    if is_external_charge_like(text) or is_utility_charge_like(text):
        alerts.append("libelle_ressemble_a_une_charge_externe")
        return "incoherente", alerts
    alerts.append("metier_a_confirmer")
    return "a_verifier", alerts


def decide_final_status(
    decision_initiale: str,
    tva_coherence: str,
    metier_coherence: str,
) -> str:
    if decision_initiale == "rejeter":
        return "rejeter"
    if "incoherente" in {tva_coherence, metier_coherence}:
        return "validation_humaine"
    if "a_verifier" in {tva_coherence, metier_coherence}:
        return "validation_humaine"
    return decision_initiale


def score_reference(
    text: str,
    ref: ReferenceItem,
    metier_hint: str | None = None,
    tva_hint: float | None = None,
) -> dict:
    raw = (text or "").strip()
    norm_text = normalize_text(raw)
    norm_source = normalize_text(ref.article_source)
    norm_canon = normalize_text(ref.article_canonique)
    text_tokens = set(tokenize(raw))
    source_tokens = set(tokenize(ref.article_source))
    canon_tokens = set(tokenize(ref.article_canonique))
    keyword_tokens = set(tokenize(" ".join(ref.mots_cles)))
    candidate_tokens = source_tokens | canon_tokens | keyword_tokens
    important_query_tokens = important_tokens(text_tokens)
    reasons: list[str] = []
    alerts: list[str] = []
    match_priority = 1

    score = 0.0

    if raw == ref.article_source:
        score = 100.0
        match_priority = 4
        reasons.append("match exact article_source")
    elif norm_text == norm_source:
        score = 96.0
        match_priority = 3
        reasons.append("match normalise article_source")
    elif norm_text == norm_canon:
        score = 90.0
        match_priority = 2
        reasons.append("match normalise article_canonique")
    else:
        source_ratio = SequenceMatcher(None, norm_text, norm_source).ratio()
        canon_ratio = SequenceMatcher(None, norm_text, norm_canon).ratio()
        best_ratio = max(source_ratio, canon_ratio)
        overlap_source = len(text_tokens & source_tokens)
        overlap_canon = len(text_tokens & canon_tokens)
        overlap_keywords = len(text_tokens & keyword_tokens)
        important_overlap = len(important_query_tokens & candidate_tokens)
        important_missing = len(important_query_tokens - candidate_tokens)
        score = best_ratio * 60.0
        score += overlap_source * 9.0
        score += overlap_canon * 8.0
        score += overlap_keywords * 4.0
        score += important_overlap * 5.0
        score -= important_missing * 7.0
        if norm_text and norm_text in norm_source:
            score += 8.0
            reasons.append("libelle inclus dans article_source")
        if norm_text and norm_text in norm_canon:
            score += 6.0
            reasons.append("libelle inclus dans article_canonique")
        if ref.metier == "global" and has_billing_context(text_tokens):
            if source_tokens and source_tokens.issubset(text_tokens):
                score += 18.0
                reasons.append("libelle global inclus dans la requete")
            elif canon_tokens and canon_tokens.issubset(text_tokens):
                score += 16.0
                reasons.append("libelle global canonique inclus dans la requete")
        if overlap_source or overlap_canon or overlap_keywords:
            reasons.append("chevauchement mots cles")
        if important_overlap:
            reasons.append("tokens importants aligns")
        if important_missing:
            reasons.append("tokens importants manquants")
        reasons.append(f"similarite={best_ratio:.2f}")

    if ref.source_invoice_ids:
        bonus = min(len(ref.source_invoice_ids), 3) * 2.0
        score += bonus
        reasons.append("source facture reelle")

    if metier_hint and ref.metier == metier_hint:
        score += 3.0
        reasons.append("bonus metier")

    if (is_external_charge_like(text) or is_utility_charge_like(text)) and ref.metier == "global":
        score += 4.0
        reasons.append("bonus charges externes")

    if ref.metier == "global" and (text_tokens & candidate_tokens & UTILITY_HINTS):
        score += 12.0
        reasons.append("bonus utilite")

    if tva_hint is not None and ref.tva_rate is not None:
        try:
            if abs(float(tva_hint) - float(ref.tva_rate)) < 0.01:
                score += 4.0
                reasons.append("bonus TVA")
            else:
                score -= 4.0
                reasons.append("TVA a verifier")
        except Exception:
            pass

    score = max(0.0, min(100.0, round(score, 2)))

    if score >= 90.0 and ref.source_invoice_ids:
        decision_initiale = "auto_ok"
    elif score >= 65.0:
        decision_initiale = "validation_humaine"
    else:
        decision_initiale = "rejeter"

    tva_coherence, tva_alerts = evaluate_tva_coherence(ref, tva_hint)
    metier_coherence, metier_alerts = evaluate_metier_coherence(raw, ref, metier_hint)
    alerts.extend(tva_alerts)
    alerts.extend(metier_alerts)
    decision_finale = decide_final_status(
        decision_initiale=decision_initiale,
        tva_coherence=tva_coherence,
        metier_coherence=metier_coherence,
    )

    return {
        "base_cible": ref.base_file,
        "metier": ref.metier,
        "article_source_match": ref.article_source,
        "article_canonique": ref.article_canonique,
        "categorie": ref.categorie,
        "sous_categorie": ref.sous_categorie,
        "compte_comptable": ref.compte_comptable,
        "tva_rate": ref.tva_rate,
        "sous_profil": ref.sous_profil,
        "nature_charge": ref.nature_charge,
        "profil_facturation": ref.profil_facturation,
        "score_confiance": score,
        "match_priority": match_priority,
        "raison_match": build_reason(reasons),
        "tva_coherence": tva_coherence,
        "metier_coherence": metier_coherence,
        "alertes": build_alerts(alerts),
        "source_invoice_ids": ref.source_invoice_ids[:3],
        "decision_initiale": decision_initiale,
        "decision_finale": decision_finale,
        "decision": decision_finale,
    }


def match_text(
    refs: list[ReferenceItem],
    text: str,
    metier: str | None,
    top_n: int,
    tva_hint: float | None,
    include_charges: bool,
) -> list[dict]:
    candidates = select_candidate_refs(refs, text, metier, include_charges)
    scored = [score_reference(text, ref, metier_hint=metier, tva_hint=tva_hint) for ref in candidates]
    # On garde le score textuel comme critere principal, puis on favorise
    # les candidats qui passent mieux les controles TVA/metier a score egal.
    scored.sort(
        key=lambda row: (
            -row["score_confiance"],
            -row["match_priority"],
            -decision_rank(row["decision_finale"]),
            -coherence_rank(row["tva_coherence"]),
            -coherence_rank(row["metier_coherence"]),
            -len(row["source_invoice_ids"]),
            row["article_source_match"],
            row["article_canonique"],
        )
    )
    return scored[:top_n]


def run_single_text(args, refs: list[ReferenceItem]) -> int:
    matches = match_text(
        refs=refs,
        text=args.text,
        metier=args.metier,
        top_n=args.top_n,
        tva_hint=args.tva,
        include_charges=args.include_charges,
    )
    if args.as_json:
        print(json.dumps(matches, ensure_ascii=False, indent=2))
        return 0

    for idx, row in enumerate(matches, 1):
        print(f"[{idx}] {row['article_source_match']}")
        print(f"    base_cible      : {row['base_cible']}")
        print(f"    metier          : {row['metier']}")
        print(f"    article_canonique: {row['article_canonique']}")
        print(f"    compte_comptable: {row['compte_comptable']}")
        if row.get("sous_profil"):
            print(f"    sous_profil     : {row['sous_profil']}")
        if row.get("nature_charge"):
            print(f"    nature_charge   : {row['nature_charge']}")
        if row.get("profil_facturation"):
            print(f"    profil_facturation: {row['profil_facturation']}")
        print(f"    score_confiance : {row['score_confiance']}")
        print(f"    tva_coherence   : {row['tva_coherence']}")
        print(f"    metier_coherence: {row['metier_coherence']}")
        print(f"    decision_initiale: {row['decision_initiale']}")
        print(f"    decision_finale : {row['decision_finale']}")
        print(f"    raison_match    : {row['raison_match']}")
        print(f"    alertes         : {', '.join(row['alertes'])}")
        print(f"    source_invoice_ids: {', '.join(row['source_invoice_ids'])}")
    return 0


def run_csv_mode(args, refs: list[ReferenceItem]) -> int:
    input_path = ROOT / args.input_csv
    output_path = ROOT / args.output_csv
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra_fields = [
        "match_base_cible",
        "match_metier",
        "match_article_source",
        "match_article_canonique",
        "match_categorie",
        "match_sous_categorie",
        "match_compte_comptable",
        "match_tva_rate",
        "match_sous_profil",
        "match_nature_charge",
        "match_profil_facturation",
        "match_tva_coherence",
        "match_metier_coherence",
        "match_score_confiance",
        "match_decision_initiale",
        "match_decision_finale",
        "match_decision",
        "match_raison",
        "match_alertes",
        "match_source_invoice_ids",
    ]

    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    for row in rows:
        text = (row.get(args.description_column) or "").strip()
        row_metier = args.metier or (row.get("metier") or "").strip() or None
        row_tva = args.tva
        if row_tva is None:
            raw_tva = (row.get("tva_rate") or "").strip()
            if raw_tva:
                try:
                    row_tva = float(raw_tva)
                except Exception:
                    row_tva = None
        matches = match_text(
            refs=refs,
            text=text,
            metier=row_metier,
            top_n=1,
            tva_hint=row_tva,
            include_charges=args.include_charges,
        )
        best = matches[0] if matches else None
        if not best:
            continue
        row["match_base_cible"] = best["base_cible"]
        row["match_metier"] = best["metier"]
        row["match_article_source"] = best["article_source_match"]
        row["match_article_canonique"] = best["article_canonique"]
        row["match_categorie"] = best["categorie"]
        row["match_sous_categorie"] = best["sous_categorie"]
        row["match_compte_comptable"] = best["compte_comptable"]
        row["match_tva_rate"] = best["tva_rate"]
        row["match_sous_profil"] = best["sous_profil"]
        row["match_nature_charge"] = best["nature_charge"]
        row["match_profil_facturation"] = best["profil_facturation"]
        row["match_tva_coherence"] = best["tva_coherence"]
        row["match_metier_coherence"] = best["metier_coherence"]
        row["match_score_confiance"] = best["score_confiance"]
        row["match_decision_initiale"] = best["decision_initiale"]
        row["match_decision_finale"] = best["decision_finale"]
        row["match_decision"] = best["decision"]
        row["match_raison"] = best["raison_match"]
        row["match_alertes"] = " | ".join(best["alertes"])
        row["match_source_invoice_ids"] = " | ".join(best["source_invoice_ids"])

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] csv={output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Matcher V1 entre libelle facture et bases metier.")
    parser.add_argument("text", nargs="?", help="Libelle a matcher.")
    parser.add_argument("--metier", choices=[k for k in BASE_FILES if k != "global"], default=None)
    parser.add_argument("--tva", type=float, default=None, help="TVA de la ligne si disponible.")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--include-charges", action="store_true", help="Inclure base_charges_externes meme avec un metier fixe.")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Afficher le resultat en JSON.")
    parser.add_argument("--input-csv", default="", help="CSV d'entree pour mode batch.")
    parser.add_argument("--description-column", default="article_source", help="Nom de la colonne texte dans le CSV.")
    parser.add_argument("--output-csv", default="matcher_v1_results.csv", help="Nom du CSV de sortie en mode batch.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    refs = load_references()

    if args.input_csv:
        return run_csv_mode(args, refs)

    if not args.text:
        parser.error("Fournir un libelle a matcher ou utiliser --input-csv.")
    return run_single_text(args, refs)


if __name__ == "__main__":
    raise SystemExit(main())
