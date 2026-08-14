from __future__ import annotations

from typing import Any


SIGNAL_WEIGHTS: dict[str, dict[str, Any]] = {
    "supplier_memory": {
        "label": "Fournisseur deja vu",
        "family": "fort",
        "weight": 0.50,
    },
    "human_validation": {
        "label": "Validation humaine precedente",
        "family": "fort",
        "weight": 0.20,
    },
    "ape_pair_context": {
        "label": "APE client / fournisseur",
        "family": "moyen",
        "weight": 0.10,
    },
    "tva_coherence": {
        "label": "TVA coherente",
        "family": "moyen",
        "weight": 0.075,
    },
    "metier_coherence": {
        "label": "Metier coherent",
        "family": "moyen",
        "weight": 0.075,
    },
    "text_similarity": {
        "label": "Similarite texte",
        "family": "faible",
        "weight": 0.15,
    },
}

FAMILY_ORDER = {"fort": 0, "moyen": 1, "faible": 2}
COHERENCE_VALUE_MAP = {
    "coherente": 1.0,
    "a_verifier": 0.55,
    "inconnue": None,
    "incoherente": 0.0,
}


def _clamp_signal(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _coherence_explanation(signal_key: str, coherence: str) -> str:
    if signal_key == "tva_coherence":
        if coherence == "coherente":
            return "Le taux de TVA est coherent avec la reference retenue."
        if coherence == "a_verifier":
            return "La TVA reste plausible mais demande encore un controle humain."
        if coherence == "incoherente":
            return "La TVA parait incoherente avec la reference comptable."
        return "Aucune TVA exploitable n'a ete fournie pour renforcer ce candidat."

    if coherence == "coherente":
        return "Le metier est coherent avec la reference proposee."
    if coherence == "a_verifier":
        return "Le metier reste plausible mais pas assez net pour auto-valider."
    if coherence == "incoherente":
        return "Le metier parait en conflit avec la reference proposee."
    return "Le contexte metier n'est pas assez precis pour renforcer ce candidat."


def _supplier_signal(stats: dict[str, Any] | None) -> tuple[float | None, str]:
    if not stats:
        return None, ""

    count = int(stats.get("count") or 0)
    total_matches = int(stats.get("total_matches") or 0)
    share = float(stats.get("share") or 0.0)
    is_dominant = bool(stats.get("is_dominant"))
    if count <= 0 or total_matches <= 0:
        return None, ""

    value = 0.45 + min(count, 3) * 0.10 + min(max(share, 0.0), 1.0) * 0.20
    if is_dominant and total_matches >= 2:
        value += 0.05
    value = min(1.0, round(value, 4))

    if count == 1:
        return value, "Le compte a deja ete valide une fois pour ce fournisseur."

    dominant_note = " C'est le compte dominant chez ce fournisseur." if is_dominant else ""
    return (
        value,
        f"Le compte a deja ete valide {count} fois pour ce fournisseur sur "
        f"{total_matches} validations.{dominant_note}".strip(),
    )


def _text_signal_explanation(text_reason: str, text_signal: float) -> str:
    if text_signal >= 0.95:
        return "Correspondance quasi exacte entre le libelle et la reference."
    if text_signal >= 0.80:
        return "Le texte est tres proche de la reference retenue."
    if text_signal >= 0.65:
        return "Le texte est proche mais reste partiellement ambigu."
    if text_signal >= 0.45:
        return "Le rapprochement textuel existe mais reste fragile."
    if text_reason:
        return text_reason
    return "Le texte seul reste faible pour confirmer ce candidat."


def _make_signal(
    *,
    key: str,
    value: float,
    explanation: str,
) -> dict[str, Any]:
    spec = SIGNAL_WEIGHTS[key]
    return {
        "key": key,
        "label": spec["label"],
        "family": spec["family"],
        "weight": float(spec["weight"]),
        "value": round(value, 4),
        "contribution": 0.0,
        "explanation": explanation,
    }


def _make_memory_signal(
    *,
    key: str,
    weight: float,
    explanation: str,
) -> dict[str, Any]:
    spec = SIGNAL_WEIGHTS[key]
    return {
        "key": key,
        "label": spec["label"],
        "family": spec["family"],
        "weight": round(weight, 4),
        "value": 1.0,
        "contribution": round(weight * 100.0, 2),
        "explanation": explanation,
    }


def _finalize_signal_package(active_signals: list[dict[str, Any]]) -> dict[str, Any]:
    available_weight = sum(float(signal["weight"]) for signal in active_signals)
    if available_weight <= 0:
        return {"final_score": 0.0, "signals": []}

    contributions: list[dict[str, Any]] = []
    final_score = 0.0
    for signal in active_signals:
        contribution = (float(signal["weight"]) * float(signal["value"]) / available_weight) * 100.0
        current = dict(signal)
        current["contribution"] = round(contribution, 2)
        contributions.append(current)
        final_score += contribution

    contributions.sort(
        key=lambda item: (
            FAMILY_ORDER.get(str(item.get("family") or ""), 9),
            -float(item.get("contribution") or 0.0),
            str(item.get("label") or ""),
        )
    )
    return {
        "final_score": round(final_score, 2),
        "signals": contributions,
    }


def rebuild_signal_package(signals: list[dict[str, Any]] | None) -> dict[str, Any]:
    active_signals: list[dict[str, Any]] = []
    for signal in signals or []:
        key = str(signal.get("key") or "").strip()
        if key not in SIGNAL_WEIGHTS:
            continue

        value = _clamp_signal(signal.get("value"))
        if value is None:
            continue

        explanation = str(signal.get("explanation") or "").strip()
        active_signals.append(
            _make_signal(
                key=key,
                value=value,
                explanation=explanation or SIGNAL_WEIGHTS[key]["label"],
            )
        )

    return _finalize_signal_package(active_signals)


def build_memory_signal_package(
    *,
    fournisseur_hint: str | None = None,
) -> dict[str, Any]:
    normalized_supplier = str(fournisseur_hint or "").strip()
    if not normalized_supplier:
        return {
            "final_score": 100.0,
            "signals": [
                _make_memory_signal(
                    key="human_validation",
                    weight=1.0,
                    explanation="La decision a ete reprise depuis une validation humaine precedente.",
                )
            ],
        }

    return {
        "final_score": 100.0,
        "signals": [
            _make_memory_signal(
                key="human_validation",
                weight=0.7,
                explanation=(
                    "La decision a ete reprise depuis une validation humaine precedente "
                    "sur le meme libelle."
                ),
            ),
            _make_memory_signal(
                key="supplier_memory",
                weight=0.3,
                explanation=(
                    f"Le contexte fournisseur {normalized_supplier} est deja connu "
                    "dans la memoire."
                ),
            ),
        ],
    }


def build_candidate_signal_package(
    *,
    text_signal: float,
    text_reason: str,
    tva_coherence: str,
    metier_coherence: str,
    supplier_stats: dict[str, Any] | None = None,
    human_validation_score: float | None = None,
    human_validation_explanation: str | None = None,
    ape_pair_score: float | None = None,
    ape_pair_explanation: str | None = None,
) -> dict[str, Any]:
    active_signals: list[dict[str, Any]] = []

    supplier_value, supplier_explanation = _supplier_signal(supplier_stats)
    supplier_value = _clamp_signal(supplier_value)
    if supplier_value is not None:
        active_signals.append(
            _make_signal(
                key="supplier_memory",
                value=supplier_value,
                explanation=supplier_explanation,
            )
        )

    human_value = _clamp_signal(human_validation_score)
    if human_value is not None:
        active_signals.append(
            _make_signal(
                key="human_validation",
                value=human_value,
                explanation=human_validation_explanation
                or "Une validation humaine precedente renforce ce candidat.",
            )
        )

    ape_value = _clamp_signal(ape_pair_score)
    if ape_value is not None:
        active_signals.append(
            _make_signal(
                key="ape_pair_context",
                value=ape_value,
                explanation=ape_pair_explanation
                or "Le contexte APE client / fournisseur renforce ce candidat.",
            )
        )

    tva_value = _clamp_signal(COHERENCE_VALUE_MAP.get(tva_coherence))
    if tva_value is not None:
        active_signals.append(
            _make_signal(
                key="tva_coherence",
                value=tva_value,
                explanation=_coherence_explanation("tva_coherence", tva_coherence),
            )
        )

    metier_value = _clamp_signal(COHERENCE_VALUE_MAP.get(metier_coherence))
    if metier_value is not None:
        active_signals.append(
            _make_signal(
                key="metier_coherence",
                value=metier_value,
                explanation=_coherence_explanation("metier_coherence", metier_coherence),
            )
        )

    text_value = _clamp_signal(text_signal) or 0.0
    active_signals.append(
        _make_signal(
            key="text_similarity",
            value=text_value,
            explanation=_text_signal_explanation(text_reason, text_value),
        )
    )

    return _finalize_signal_package(active_signals)
