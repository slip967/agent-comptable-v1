from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_APP_URL,
    OPENROUTER_MODEL,
)
from .schemas import AccountingDecision, CandidateLine


MIN_CONFIDENCE_FOR_PROPOSED_ACCOUNT = 20.0


SYSTEM_PROMPT = (
    "Tu es un agent comptable local. "
    "Tu ne dois jamais inventer un compte comptable. "
    "Tu dois choisir uniquement parmi les candidats fournis. "
    "Si le doute est fort, retourne decision='validation_humaine'. "
    "Si aucun candidat n'est credible, retourne decision='rejeter'. "
    "Si tu choisis un candidat, recopie exactement ses champs categorie, sous_categorie, compte_comptable et score_confiance. "
    "Reponds uniquement en JSON valide."
)


def _build_client() -> OpenAI | None:
    if not OPENROUTER_API_KEY:
        return None
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={
            "HTTP-Referer": OPENROUTER_APP_URL,
            "X-OpenRouter-Title": OPENROUTER_APP_NAME,
        },
    )


def _candidate_score(candidate: dict[str, Any] | None) -> float:
    if not candidate:
        return 0.0
    return float(candidate.get("score_confiance") or 0.0)


def _candidate_decision(candidate: dict[str, Any] | None) -> str:
    if not candidate:
        return ""
    return str(candidate.get("decision") or "").strip().lower()


def _should_expose_proposed_account(candidate: dict[str, Any] | None) -> bool:
    if not candidate:
        return False
    if _candidate_decision(candidate) == "rejeter":
        return False
    return _candidate_score(candidate) >= MIN_CONFIDENCE_FOR_PROPOSED_ACCOUNT


def _clear_proposed_fields(parsed: AccountingDecision) -> None:
    parsed.categorie = None
    parsed.sous_categorie = None
    parsed.compte_comptable = None


def _fallback_decision(article_source: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best = candidates[0] if candidates else None
    if not best:
        return AccountingDecision(
            article_source=article_source,
            decision="rejeter",
            explication="Aucun candidat local n'a ete trouve.",
            candidats=[],
        ).model_dump()

    normalized_candidates = [CandidateLine(**candidate) for candidate in candidates]

    if not _should_expose_proposed_account(best):
        return AccountingDecision(
            article_source=article_source,
            score_confiance=_candidate_score(best),
            decision="validation_humaine",
            explication=(
                "Decision locale sans LLM. "
                "Le meilleur candidat local est trop faible ou deja rejete, "
                "donc aucun compte n'est propose automatiquement."
            ),
            candidats=normalized_candidates,
        ).model_dump()

    return AccountingDecision(
        article_source=article_source,
        categorie=best.get("categorie"),
        sous_categorie=best.get("sous_categorie"),
        compte_comptable=best.get("compte_comptable"),
        score_confiance=float(best.get("score_confiance") or 0.0),
        decision=best.get("decision") or "validation_humaine",
        explication=(
            "Decision locale sans LLM. "
            f"Candidat retenu: {best.get('article_source_match', '')}. "
            f"Raison: {best.get('raison_match', '')}"
        ).strip(),
        candidats=normalized_candidates,
    ).model_dump()


def _normalize_llm_decision(
    article_source: str,
    parsed: AccountingDecision,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    best = candidates[0] if candidates else None
    normalized_candidates = [CandidateLine(**candidate) for candidate in candidates]

    if not parsed.candidats:
        parsed.candidats = normalized_candidates

    if best is None:
        if not parsed.explication:
            parsed.explication = "Aucun candidat local n'a ete trouve."
        return parsed.model_dump()

    candidate_by_account = {
        str(candidate.get("compte_comptable") or "").strip(): candidate
        for candidate in candidates
        if candidate.get("compte_comptable")
    }

    chosen = None
    parsed_account = str(parsed.compte_comptable or "").strip()
    if parsed_account and parsed_account in candidate_by_account:
        chosen = candidate_by_account[parsed_account]
    elif parsed.decision != "rejeter":
        chosen = best

    if chosen is not None:
        if not parsed.categorie:
            parsed.categorie = chosen.get("categorie")
        if not parsed.sous_categorie:
            parsed.sous_categorie = chosen.get("sous_categorie")
        if not parsed.compte_comptable:
            parsed.compte_comptable = chosen.get("compte_comptable")
        if not parsed.score_confiance:
            parsed.score_confiance = float(chosen.get("score_confiance") or 0.0)

    if not parsed.explication:
        parsed.explication = "Decision retournee par le modele."

    if parsed.decision == "rejeter":
        _clear_proposed_fields(parsed)
    elif not _should_expose_proposed_account(chosen):
        parsed.decision = "validation_humaine"
        _clear_proposed_fields(parsed)
        if chosen is not None and not parsed.score_confiance:
            parsed.score_confiance = _candidate_score(chosen)
        weakness_note = (
            "Le meilleur candidat local est trop faible ou deja en rejet, "
            "donc aucun compte n'est propose automatiquement."
        )
        if weakness_note not in parsed.explication:
            parsed.explication = f"{parsed.explication} {weakness_note}".strip()

    if parsed.article_source != article_source:
        parsed.article_source = article_source

    return parsed.model_dump()


def run_agent(
    article_source: str,
    candidates: list[dict[str, Any]],
    metier_hint: str | None = None,
    tva_hint: float | None = None,
) -> dict[str, Any]:
    client = _build_client()
    if client is None:
        return _fallback_decision(article_source, candidates)

    payload = {
        "article_source": article_source,
        "metier_hint": metier_hint,
        "tva_hint": tva_hint,
        "candidats": candidates,
        "regles": {
            "ne_pas_inventer_de_compte": True,
            "validation_humaine_si_ambigu": True,
            "choisir_uniquement_parmi_les_candidats": True,
        },
    }

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "accounting_decision",
                    "strict": True,
                    "schema": AccountingDecision.model_json_schema(),
                },
            },
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        parsed = AccountingDecision.model_validate_json(content)
        return _normalize_llm_decision(article_source, parsed, candidates)
    except Exception:
        return _fallback_decision(article_source, candidates)
