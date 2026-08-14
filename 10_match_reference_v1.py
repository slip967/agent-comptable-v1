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

from agent_local_v1.app.account_labels import get_account_label
from agent_local_v1.app.signal_ranker import build_candidate_signal_package, rebuild_signal_package

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

OCR_NORMALIZATION_RULES = (
    (r"\bb\s*&\s*you\b", " byou "),
    (r"\bb\s+you\b", " byou "),
    (r"\bsceau\b", " seau "),
    (r"\bkgs\b", " kg "),
    (r"\bkilos?\b", " kg "),
    (r"\bgrams?\b", " g "),
    (r"\bgrammes?\b", " g "),
    (r"\blitres?\b", " l "),
    (r"\bcentilitres?\b", " cl "),
    (r"\bmillilitres?\b", " ml "),
    (r"\bep\.\b", " epice "),
    (r"\bepices\b", " epice "),
    (r"\billimitee\b", " illimite "),
    (r"\billimitee\b", " illimite "),
    (r"\breconstitueur\b", " reconstitueur "),
)

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

BILLING_RANGE_PATTERN = re.compile(
    r"\bdu\s+\d{2}[/-]\d{2}(?:[/-]\d{2,4})?\s+au\s+\d{2}[/-]\d{2}(?:[/-]\d{2,4})?\b"
)

NON_ARTICLE_PATTERNS = (
    re.compile(r"\boption\s+pour\s+le\s+paiement\b"),
    re.compile(r"\bpaiement\s+de\s+la\s+taxe\b"),
    re.compile(r"\bremise\b"),
    re.compile(r"\bavoir\b"),
    re.compile(r"\bescompte\b"),
    re.compile(r"\bristourne\b"),
    re.compile(r"\bannulation\b"),
    re.compile(r"\bcorrection\b"),
    re.compile(r"\bregularisation\b"),
)

NON_ARTICLE_TOKENS = {
    "remise",
    "avoir",
    "escompte",
    "ristourne",
    "taxe",
    "taxes",
    "debit",
    "debits",
    "credit",
    "credits",
    "annulation",
    "correction",
    "regularisation",
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

APE_METIER_RULES = (
    ("1071", "boulangerie"),
    ("4722", "boucherie"),
    ("5610", "restaurant"),
    ("4711", "epicerie"),
    ("4932", "vtc"),
    ("4941", "transport"),
    ("5229", "transport"),
    ("4120", "btp"),
    ("4211", "btp"),
    ("4299", "btp"),
    ("4312", "btp"),
    ("4321", "btp"),
    ("4322", "btp"),
    ("4331", "btp"),
    ("4332", "btp"),
    ("4333", "btp"),
    ("4334", "btp"),
    ("4339", "btp"),
    ("4399", "btp"),
    ("4673", "btp"),
)

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
    compte_comptable_libelle: str
    tva_rate: float | None
    mots_cles: list[str]
    ape_context: list[str]
    source_invoice_ids: list[str]
    ids_factures_sources: list[str]
    invoice_paths_sources: list[str]
    partitions_sources: list[str]
    type_fournisseur: str
    sous_profil: str
    nature_charge: str
    profil_facturation: str


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    for pattern, replacement in OCR_NORMALIZATION_RULES:
        value = re.sub(pattern, replacement, value)
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


def infer_metiers_from_ape(value: str | None) -> set[str]:
    ape = normalize_ape(value)
    if not ape:
        return set()

    metiers: set[str] = set()
    for prefix, metier in APE_METIER_RULES:
        if ape.startswith(prefix):
            metiers.add(metier)
    return metiers


def resolve_activity_hints(
    metier_hint: str | None,
    client_ape_hint: str | None,
    supplier_ape_hint: str | None,
) -> set[str]:
    hints: set[str] = set()
    normalized_metier = str(metier_hint or "").strip().lower()
    if normalized_metier in BASE_FILES:
        hints.add(normalized_metier)
    hints.update(infer_metiers_from_ape(client_ape_hint))
    hints.update(infer_metiers_from_ape(supplier_ape_hint))
    return hints


def is_non_article_line(value: str) -> bool:
    norm = normalize_text(value)
    if not norm:
        return True

    tokens = set(norm.split())
    if not tokens:
        return True

    if all(token.isdigit() for token in tokens):
        return True

    if any(pattern.search(norm) for pattern in NON_ARTICLE_PATTERNS):
        return True

    if "option" in tokens and {"paiement", "taxe"} & tokens:
        return True

    if "taxe" in tokens and {"paiement", "debit", "debits"} & tokens:
        return True

    if BILLING_RANGE_PATTERN.search(norm) and (
        {"remise", "avantage", "option", "regularisation"} & tokens
    ):
        return True

    if tokens & NON_ARTICLE_TOKENS and len(tokens) <= 6:
        return True

    if "tva" in tokens and len(tokens) <= 4:
        return True

    return False


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
            tva_rate = item.get("taux_tva")
            if tva_rate is None:
                tva_rate = item.get("tva_rate")
            source_invoice_ids = list(item.get("source_invoice_ids") or [])
            ids_factures_sources = list(item.get("ids_factures_sources") or source_invoice_ids)
            refs.append(
                ReferenceItem(
                    base_file=filename,
                    metier=metier,
                    article_source=(item.get("article_source") or "").strip(),
                    article_canonique=(item.get("article_canonique") or "").strip(),
                    categorie=(item.get("categorie") or "").strip(),
                    sous_categorie=(item.get("sous_categorie") or "").strip(),
                    compte_comptable=(item.get("compte_comptable") or "").strip(),
                    compte_comptable_libelle=(
                        item.get("compte_comptable_libelle")
                        or item.get("account_label")
                        or get_account_label(item.get("compte_comptable"))
                        or ""
                    ).strip(),
                    tva_rate=tva_rate,
                    mots_cles=list(item.get("mots_cles") or []),
                    ape_context=list(item.get("ape_context") or []),
                    source_invoice_ids=source_invoice_ids,
                    ids_factures_sources=ids_factures_sources,
                    invoice_paths_sources=list(item.get("invoice_paths_sources") or []),
                    partitions_sources=list(item.get("partitions_sources") or []),
                    type_fournisseur=(item.get("type_fournisseur") or "").strip(),
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


def has_strong_confirmation(
    *,
    text_score: float,
    signals: list[dict] | None = None,
) -> bool:
    if float(text_score or 0.0) >= 90.0:
        return True

    for signal in signals or []:
        signal_key = str(signal.get("key") or "").strip()
        signal_value = float(signal.get("value") or 0.0)
        if signal_key == "supplier_memory" and signal_value >= 0.75:
            return True
        if signal_key == "human_validation" and signal_value >= 0.72:
            return True
        if signal_key == "ape_pair_context" and signal_value >= 0.85:
            return True

    return False


def evaluate_candidate_decision(
    *,
    final_score: float,
    text_score: float,
    signals: list[dict] | None,
    tva_coherence: str,
    metier_coherence: str,
    has_real_evidence: bool,
) -> tuple[str, str]:
    strong_confirmation = has_strong_confirmation(
        text_score=text_score,
        signals=signals,
    )

    if metier_coherence == "incoherente":
        decision_initiale = "rejeter"
    elif final_score >= 92.0 and strong_confirmation and has_real_evidence and tva_coherence == "coherente":
        decision_initiale = "auto_ok"
    elif final_score >= 70.0:
        decision_initiale = "validation_humaine"
    else:
        decision_initiale = "rejeter"

    decision_finale = decide_final_status(
        decision_initiale=decision_initiale,
        tva_coherence=tva_coherence,
        metier_coherence=metier_coherence,
    )
    return decision_initiale, decision_finale


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


def evaluate_metier_coherence(
    text: str,
    ref: ReferenceItem,
    metier_hint: str | None,
    client_ape_hint: str | None = None,
    supplier_ape_hint: str | None = None,
) -> tuple[str, list[str]]:
    alerts: list[str] = []
    tokens = set(tokenize(text))
    activity_hints = resolve_activity_hints(metier_hint, client_ape_hint, supplier_ape_hint)

    if metier_hint:
        if ref.metier == metier_hint:
            return "coherente", alerts
        if ref.metier == "global" and (is_external_charge_like(text) or is_utility_charge_like(text)):
            return "coherente", alerts
        alerts.append("metier_reference_different_du_metier_attendu")
        return "incoherente", alerts

    if activity_hints:
        if ref.metier in activity_hints:
            return "coherente", alerts
        if ref.metier == "global" and (is_external_charge_like(text) or is_utility_charge_like(text)):
            return "coherente", alerts
        alerts.append("metier_incompatible_avec_contexte_activite")
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


def normalize_ape(value: str | None) -> str:
    return str(value or "").strip().upper()


def evaluate_ape_pair_context(
    ref: ReferenceItem,
    client_ape_hint: str | None = None,
    supplier_ape_hint: str | None = None,
) -> tuple[float | None, str, list[str]]:
    alerts: list[str] = []
    client_ape = normalize_ape(client_ape_hint)
    supplier_ape = normalize_ape(supplier_ape_hint)
    ref_ape_context = {
        normalize_ape(value)
        for value in getattr(ref, "ape_context", [])
        if normalize_ape(value)
    }

    if not ref_ape_context or (not client_ape and not supplier_ape):
        return None, "", alerts

    client_match = bool(client_ape and client_ape in ref_ape_context)
    supplier_match = bool(supplier_ape and supplier_ape in ref_ape_context)

    if client_match and supplier_match and client_ape != supplier_ape:
        return (
            1.0,
            "Les APE client et fournisseur sont tous les deux alignes avec le contexte de reference.",
            alerts,
        )

    if ref.metier == "global":
        if supplier_match:
            explanation = "L'APE fournisseur est coherent avec cette reference de charges externes."
            if client_match:
                explanation += " L'APE client renforce aussi ce contexte."
            return 0.92 if client_match else 0.86, explanation, alerts
        if client_match:
            alerts.append("ape_fournisseur_a_confirmer")
            return (
                0.62,
                "L'APE client rejoint le contexte de reference, mais l'APE fournisseur manque encore pour confirmer.",
                alerts,
            )
        alerts.append("ape_contexte_a_verifier")
        return (
            0.25,
            "Le couple APE client / fournisseur ne confirme pas encore cette reference de charges externes.",
            alerts,
        )

    if client_match:
        explanation = "L'APE client est coherent avec le contexte metier de cette reference."
        if supplier_match:
            explanation += " L'APE fournisseur va dans le meme sens."
            return 0.96, explanation, alerts
        return 0.84, explanation, alerts

    if supplier_match:
        alerts.append("ape_client_a_confirmer")
        return (
            0.68,
            "L'APE fournisseur est connu dans le contexte de reference, mais l'APE client manque encore pour confirmer.",
            alerts,
        )

    alerts.append("ape_contexte_a_verifier")
    return (
        0.25,
        "Le couple APE client / fournisseur n'est pas encore coherent avec le contexte de reference.",
        alerts,
    )


def decide_final_status(
    decision_initiale: str,
    tva_coherence: str,
    metier_coherence: str,
) -> str:
    if metier_coherence == "incoherente":
        return "rejeter"
    if decision_initiale == "rejeter":
        return "rejeter"
    if tva_coherence == "incoherente":
        return "validation_humaine"
    if "a_verifier" in {tva_coherence, metier_coherence}:
        return "validation_humaine"
    return decision_initiale


def score_reference(
    text: str,
    ref: ReferenceItem,
    fournisseur_hint: str | None = None,
    metier_hint: str | None = None,
    client_ape_hint: str | None = None,
    supplier_ape_hint: str | None = None,
    tva_hint: float | None = None,
    supplier_account_stats: dict[str, dict[str, object]] | None = None,
    validation_pattern_stats: dict[str, dict[str, object]] | None = None,
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
    text_score = 0.0
    activity_hints = resolve_activity_hints(metier_hint, client_ape_hint, supplier_ape_hint)
    ref_ape_context = {normalize_ape(value) for value in ref.ape_context if normalize_ape(value)}
    normalized_client_ape = normalize_ape(client_ape_hint)
    normalized_supplier_ape = normalize_ape(supplier_ape_hint)

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

    text_score = max(0.0, min(100.0, round(score, 2)))

    if ref.source_invoice_ids:
        bonus = min(len(ref.source_invoice_ids), 3) * 2.0
        score += bonus
        reasons.append("source facture réelle")

    if metier_hint and ref.metier == metier_hint:
        score += 8.0
        reasons.append("bonus metier")

    if activity_hints:
        if ref.metier in activity_hints:
            score += 10.0
            reasons.append("bonus activite coherente")
        elif ref.metier != "global":
            score -= 16.0
            reasons.append("malus activite incoherente")
            alerts.append("activite_metier_incoherente")

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

    ape_direct_matches = 0
    if normalized_client_ape and normalized_client_ape in ref_ape_context:
        ape_direct_matches += 1
    if normalized_supplier_ape and normalized_supplier_ape in ref_ape_context:
        ape_direct_matches += 1
    if ape_direct_matches == 2:
        score += 10.0
        reasons.append("bonus APE client et fournisseur")
    elif ape_direct_matches == 1:
        score += 6.0
        reasons.append("bonus APE contextuel")
    elif ref_ape_context and activity_hints and ref.metier not in activity_hints and ref.metier != "global":
        score -= 6.0
        reasons.append("malus APE incoherent")

    tva_coherence, tva_alerts = evaluate_tva_coherence(ref, tva_hint)
    metier_coherence, metier_alerts = evaluate_metier_coherence(
        raw,
        ref,
        metier_hint,
        client_ape_hint=client_ape_hint,
        supplier_ape_hint=supplier_ape_hint,
    )
    ape_pair_score, ape_pair_explanation, ape_pair_alerts = evaluate_ape_pair_context(
        ref,
        client_ape_hint=client_ape_hint,
        supplier_ape_hint=supplier_ape_hint,
    )
    alerts.extend(tva_alerts)
    alerts.extend(metier_alerts)
    alerts.extend(ape_pair_alerts)
    supplier_stats = None
    if supplier_account_stats:
        supplier_stats = supplier_account_stats.get(ref.compte_comptable)
    human_pattern_stats = None
    if validation_pattern_stats:
        human_pattern_stats = validation_pattern_stats.get(ref.compte_comptable)

    signal_package = build_candidate_signal_package(
        text_signal=text_score / 100.0,
        text_reason=build_reason(reasons),
        tva_coherence=tva_coherence,
        metier_coherence=metier_coherence,
        supplier_stats=supplier_stats,
        human_validation_score=(
            float(human_pattern_stats.get("score") or 0.0) if human_pattern_stats else None
        ),
        human_validation_explanation=(
            str(human_pattern_stats.get("explanation") or "").strip() if human_pattern_stats else None
        ),
        ape_pair_score=ape_pair_score,
        ape_pair_explanation=ape_pair_explanation,
    )
    final_score = float(signal_package.get("final_score") or 0.0)
    signals = list(signal_package.get("signals") or [])

    if supplier_stats:
        count = int(supplier_stats.get("count") or 0)
        total_matches = int(supplier_stats.get("total_matches") or 0)
        share = float(supplier_stats.get("share") or 0.0)
        is_dominant = bool(supplier_stats.get("is_dominant"))
        if count == 1:
            reasons.append("historique fournisseur confirme")
        elif count > 1:
            reasons.append(f"historique fournisseur x{count}")
        if is_dominant and total_matches >= 2 and share >= 0.5:
            reasons.append("compte dominant chez ce fournisseur")
        if count >= 2:
            alerts.append("signal_fournisseur_fort")

    if human_pattern_stats:
        validation_count = int(human_pattern_stats.get("count") or 0)
        if validation_count == 1:
            reasons.append("validation humaine similaire")
        elif validation_count > 1:
            reasons.append(f"pattern humain x{validation_count}")
        if float(human_pattern_stats.get("score") or 0.0) >= 0.75:
            alerts.append("signal_validation_humaine_fort")

    if ape_pair_score is not None:
        if ape_pair_score >= 0.85:
            reasons.append("contexte APE client/fournisseur confirme")
        elif ape_pair_score >= 0.6:
            reasons.append("contexte APE partiellement coherent")
        elif ape_pair_score <= 0.3:
            reasons.append("contexte APE fragile")

    decision_initiale, decision_finale = evaluate_candidate_decision(
        final_score=final_score,
        text_score=text_score,
        signals=signals,
        tva_coherence=tva_coherence,
        metier_coherence=metier_coherence,
        has_real_evidence=bool(ref.source_invoice_ids or ref.invoice_paths_sources),
    )

    return {
        "base_cible": ref.base_file,
        "metier": ref.metier,
        "article_source": ref.article_source,
        "article_source_match": ref.article_source,
        "article_canonique": ref.article_canonique,
        "categorie": ref.categorie,
        "sous_categorie": ref.sous_categorie,
        "compte_comptable": ref.compte_comptable,
        "compte_comptable_libelle": ref.compte_comptable_libelle,
        "account_label": ref.compte_comptable_libelle,
        "taux_tva": ref.tva_rate,
        "tva_rate": ref.tva_rate,
        "type_fournisseur": ref.type_fournisseur,
        "sous_profil": ref.sous_profil,
        "nature_charge": ref.nature_charge,
        "profil_facturation": ref.profil_facturation,
        "score_confiance": final_score,
        "final_score": final_score,
        "match_priority": match_priority,
        "score_texte": text_score,
        "raison_match": build_reason(reasons),
        "tva_coherence": tva_coherence,
        "metier_coherence": metier_coherence,
        "alertes": build_alerts(alerts),
        "source_invoice_ids": ref.source_invoice_ids[:3],
        "ids_factures_sources": ref.ids_factures_sources[:3],
        "invoice_paths_sources": ref.invoice_paths_sources[:3],
        "partitions_sources": ref.partitions_sources[:3],
        "ape_context": ref.ape_context[:5],
        "signals": signals,
        "decision_initiale": decision_initiale,
        "decision_finale": decision_finale,
        "decision": decision_finale,
    }


def apply_supplier_account_signal(
    scored: list[dict],
    supplier_account_stats: dict[str, dict[str, object]] | None = None,
) -> list[dict]:
    if not scored or not supplier_account_stats:
        return scored

    supplier_rows = [
        (account, stats)
        for account, stats in supplier_account_stats.items()
        if str(account or "").strip() and int((stats or {}).get("count") or 0) > 0
    ]
    if not supplier_rows:
        return scored

    dominant_account, dominant_stats = max(
        supplier_rows,
        key=lambda item: (
            int((item[1] or {}).get("count") or 0),
            float((item[1] or {}).get("share") or 0.0),
            str((item[1] or {}).get("latest_validation_at") or ""),
        ),
    )
    dominant_count = int((dominant_stats or {}).get("count") or 0)
    dominant_share = float((dominant_stats or {}).get("share") or 0.0)
    total_matches = int((dominant_stats or {}).get("total_matches") or 0)
    if total_matches < 2 or dominant_count < 2 or dominant_share < 0.6:
        return scored

    updated_rows: list[dict] = []
    for row in scored:
        current = dict(row)
        account = str(current.get("compte_comptable") or "").strip()
        if not account or account in supplier_account_stats:
            updated_rows.append(current)
            continue

        supplier_signal_value = 0.5 if dominant_share >= 0.85 else 0.6 if dominant_share >= 0.72 else 0.7
        signals = [dict(signal) for signal in current.get("signals") or []]
        signals.append(
            {
                "key": "supplier_memory",
                "value": supplier_signal_value,
                "explanation": (
                    "Le fournisseur est deja connu, mais pas avec ce compte. "
                    f"L'historique favorise plutot {dominant_account} "
                    f"({dominant_count}/{total_matches} validations)."
                ),
            }
        )
        signal_package = rebuild_signal_package(signals)
        final_score = float(signal_package.get("final_score") or 0.0)
        current["signals"] = list(signal_package.get("signals") or [])
        current["final_score"] = final_score
        current["score_confiance"] = final_score

        alerts = list(current.get("alertes") or [])
        alerts.append("historique_fournisseur_a_verifier")
        current["alertes"] = build_alerts(alerts)

        decision_initiale, decision_finale = evaluate_candidate_decision(
            final_score=final_score,
            text_score=float(current.get("score_texte") or 0.0),
            signals=current["signals"],
            tva_coherence=str(current.get("tva_coherence") or ""),
            metier_coherence=str(current.get("metier_coherence") or ""),
            has_real_evidence=bool(current.get("source_invoice_ids") or current.get("invoice_paths_sources")),
        )
        current["decision_initiale"] = decision_initiale
        current["decision_finale"] = decision_finale
        current["decision"] = decision_finale
        updated_rows.append(current)

    return updated_rows


def match_text(
    refs: list[ReferenceItem],
    text: str,
    fournisseur_hint: str | None,
    metier: str | None,
    client_ape_hint: str | None,
    supplier_ape_hint: str | None,
    top_n: int,
    tva_hint: float | None,
    include_charges: bool,
    supplier_account_stats: dict[str, dict[str, object]] | None = None,
    validation_pattern_stats: dict[str, dict[str, object]] | None = None,
) -> list[dict]:
    if is_non_article_line(text):
        return []

    candidates = select_candidate_refs(refs, text, metier, include_charges)
    scored = [
        score_reference(
            text,
            ref,
            fournisseur_hint=fournisseur_hint,
            metier_hint=metier,
            client_ape_hint=client_ape_hint,
            supplier_ape_hint=supplier_ape_hint,
            tva_hint=tva_hint,
            supplier_account_stats=supplier_account_stats,
            validation_pattern_stats=validation_pattern_stats,
        )
        for ref in candidates
    ]
    scored = apply_supplier_account_signal(scored, supplier_account_stats)
    # Le classement repose d'abord sur le final_score du ranker,
    # puis sur les signaux de coherence et la priorite de match.
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
        fournisseur_hint=args.fournisseur,
        metier=args.metier,
        client_ape_hint=args.client_ape,
        supplier_ape_hint=args.supplier_ape,
        top_n=args.top_n,
        tva_hint=args.tva,
        include_charges=args.include_charges,
        supplier_account_stats=None,
        validation_pattern_stats=None,
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
        print(f"    score_texte     : {row.get('score_texte')}")
        print(f"    tva_coherence   : {row['tva_coherence']}")
        print(f"    metier_coherence: {row['metier_coherence']}")
        print(f"    decision_initiale: {row['decision_initiale']}")
        print(f"    decision_finale : {row['decision_finale']}")
        print(f"    raison_match    : {row['raison_match']}")
        print(f"    alertes         : {', '.join(row['alertes'])}")
        print(f"    source_invoice_ids: {', '.join(row['source_invoice_ids'])}")
        if row.get("signals"):
            print("    signaux         :")
            for signal in row["signals"]:
                print(
                    "      - "
                    f"{signal['label']} [{signal['family']}] "
                    f"value={signal['value']:.2f} contrib={signal['contribution']:.2f}"
                )
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
            fournisseur_hint=(row.get("fournisseur") or row.get("issuer_name") or "").strip() or None,
            metier=row_metier,
            client_ape_hint=(row.get("client_ape") or row.get("km_ape") or "").strip() or None,
            supplier_ape_hint=(row.get("supplier_ape") or "").strip() or None,
            top_n=1,
            tva_hint=row_tva,
            include_charges=args.include_charges,
            validation_pattern_stats=None,
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
    parser.add_argument("--fournisseur", default=None, help="Nom du fournisseur si disponible.")
    parser.add_argument("--metier", choices=[k for k in BASE_FILES if k != "global"], default=None)
    parser.add_argument("--client-ape", default=None, help="APE client si disponible.")
    parser.add_argument("--supplier-ape", default=None, help="APE fournisseur si disponible.")
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
