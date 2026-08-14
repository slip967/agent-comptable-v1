from __future__ import annotations

from datetime import datetime, timezone

from .database import (
    DATABASE_FILE,
    count_validation_stats,
    fetch_analysis_history_records,
    fetch_latest_validation_timestamps,
    fetch_validation_records,
    insert_analysis_history_record,
    insert_validation_record,
    upsert_analysis_history_records,
    update_validation_patterns,
)
from .account_labels import get_account_label
from .loader import normalize_text
from .signal_ranker import build_memory_signal_package
from .schemas import (
    AccountingDecision,
    AnalysisHistoryRecord,
    AnalysisHistoryResponse,
    HumanValidationInput,
    HumanValidationRecord,
    MemoryStats,
    SignalDetail,
    ValidationQueueResponse,
    InvoiceLineInput,
)


def _normalize_optional_context(value: str | None) -> str:
    return normalize_text(value or "")


def _build_lookup_key(
    article_source: str,
    metier_hint: str | None = None,
    fournisseur_hint: str | None = None,
) -> str:
    article_source_normalized = normalize_text(article_source)
    metier_hint_normalized = _normalize_optional_context(metier_hint)
    fournisseur_hint_normalized = _normalize_optional_context(fournisseur_hint)
    return f"{article_source_normalized}::{metier_hint_normalized}::{fournisseur_hint_normalized}"


def _build_legacy_lookup_key(article_source: str, metier_hint: str | None = None) -> str:
    article_source_normalized = normalize_text(article_source)
    metier_hint_normalized = _normalize_optional_context(metier_hint)
    return f"{article_source_normalized}::{metier_hint_normalized}"


def _select_analysis_record_candidate(record: AnalysisHistoryRecord):
    if not record.candidats:
        return None

    if record.compte_comptable:
        for candidate in record.candidats:
            if candidate.compte_comptable == record.compte_comptable:
                return candidate

    return record.candidats[0]


def ensure_analysis_record_signals(record: AnalysisHistoryRecord) -> AnalysisHistoryRecord:
    if record.signals:
        return record

    if record.source == "memory":
        record.signals = [
            SignalDetail(**signal)
            for signal in (
                build_memory_signal_package(
                    fournisseur_hint=record.fournisseur_hint,
                ).get("signals")
                or []
            )
        ]
        return record

    selected_candidate = _select_analysis_record_candidate(record)
    if selected_candidate is not None and selected_candidate.signals:
        record.signals = list(selected_candidate.signals)

    return record


def backfill_analysis_record_signals(
    records: list[AnalysisHistoryRecord],
) -> tuple[list[AnalysisHistoryRecord], list[AnalysisHistoryRecord]]:
    updated_records: list[AnalysisHistoryRecord] = []
    patched_records: list[AnalysisHistoryRecord] = []

    for record in records:
        had_signals = bool(record.signals)
        ensure_analysis_record_signals(record)
        updated_records.append(record)
        if not had_signals and record.signals:
            patched_records.append(record)

    return updated_records, patched_records


def persist_analysis_signal_backfill(records: list[AnalysisHistoryRecord]) -> None:
    if not records:
        return

    try:
        upsert_analysis_history_records(records)
    except Exception as exc:
        print(
            "[WARN] Persistance du backfill des signaux d'historique impossible "
            f"({exc}). Les signaux restent disponibles en memoire pour cette lecture."
        )


def save_validation(payload: HumanValidationInput) -> HumanValidationRecord:
    record = HumanValidationRecord(
        **payload.model_dump(),
        article_source_normalized=normalize_text(payload.article_source),
        lookup_key=_build_lookup_key(
            payload.article_source,
            payload.metier_hint,
            payload.fournisseur_hint,
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    insert_validation_record(record)
    update_validation_patterns(
        record,
        recommended_account=(payload.recommandation_ia.compte_comptable if payload.recommandation_ia else None),
    )
    return record


def save_analysis_event(
    payload: InvoiceLineInput,
    decision: AccountingDecision,
    source: str,
) -> AnalysisHistoryRecord:
    source_value = source if source in {"memory", "engine", "ai"} else "engine"
    record = AnalysisHistoryRecord(
        article_source=decision.article_source,
        article_source_normalized=normalize_text(decision.article_source),
        lookup_key=_build_lookup_key(
            decision.article_source,
            payload.metier_hint,
            payload.fournisseur_hint,
        ),
        fournisseur_hint=payload.fournisseur_hint,
        metier_hint=payload.metier_hint,
        client_ape_hint=payload.client_ape_hint,
        supplier_ape_hint=payload.supplier_ape_hint,
        tva_hint=payload.tva_hint,
        include_charges=payload.include_charges,
        categorie=decision.categorie,
        sous_categorie=decision.sous_categorie,
        compte_comptable=decision.compte_comptable,
        score_confiance=decision.score_confiance,
        decision=decision.decision,
        explication=decision.explication,
        source=source_value,
        signals=decision.signals,
        candidats=decision.candidats,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    ensure_analysis_record_signals(record)
    insert_analysis_history_record(record)
    return record


def find_reusable_validation(
    article_source: str,
    metier_hint: str | None = None,
    fournisseur_hint: str | None = None,
) -> HumanValidationRecord | None:
    lookup_keys = {
        _build_lookup_key(article_source, metier_hint, fournisseur_hint),
        _build_legacy_lookup_key(article_source, metier_hint),
    }
    current_supplier = _normalize_optional_context(fournisseur_hint)

    for record in fetch_validation_records(lookup_keys):
        if record.lookup_key not in lookup_keys or record.decision_humaine == "rejeter":
            continue
        if not record.compte_comptable_final:
            continue
        record_supplier = _normalize_optional_context(record.fournisseur_hint)
        if current_supplier:
            if record_supplier and record_supplier != current_supplier:
                continue
        elif record_supplier:
            continue

        return record

    return None


def build_memory_decision(
    article_source: str,
    record: HumanValidationRecord,
) -> AccountingDecision:
    supplier_note = (
        f" et le meme fournisseur ({record.fournisseur_hint})"
        if record.fournisseur_hint
        else ""
    )
    return AccountingDecision(
        article_source=article_source,
        categorie=record.categorie_finale,
        sous_categorie=record.sous_categorie_finale,
        compte_comptable=record.compte_comptable_final,
        compte_comptable_libelle=get_account_label(record.compte_comptable_final),
        score_confiance=100.0,
        decision="auto_ok",
        explication=(
            f"Reprise d'une validation humaine precedente sur le meme libelle{supplier_note}. "
            f"Derniere decision humaine: {record.decision_humaine}."
        ),
        source="memory",
        signals=build_memory_signal_package(
            fournisseur_hint=record.fournisseur_hint,
        ).get("signals")
        or [],
        candidats=[],
    )


def get_memory_stats() -> MemoryStats:
    total_records, reusable_records = count_validation_stats()
    return MemoryStats(
        memory_file=str(DATABASE_FILE),
        total_records=total_records,
        reusable_records=reusable_records,
    )


def get_analysis_history(limit: int = 20) -> AnalysisHistoryResponse:
    records, patched_records = backfill_analysis_record_signals(
        fetch_analysis_history_records(limit=limit)
    )
    persist_analysis_signal_backfill(patched_records)
    return AnalysisHistoryResponse(items=records)


def get_validation_queue(limit: int = 20) -> ValidationQueueResponse:
    latest_validation_by_key = fetch_latest_validation_timestamps()
    seen_keys: set[str] = set()
    items: list[AnalysisHistoryRecord] = []
    for record in fetch_analysis_history_records(limit=None):
        if record.decision != "validation_humaine":
            continue
        if record.lookup_key in seen_keys:
            continue

        latest_validation_at = latest_validation_by_key.get(record.lookup_key)
        if latest_validation_at and latest_validation_at >= record.created_at:
            seen_keys.add(record.lookup_key)
            continue

        seen_keys.add(record.lookup_key)
        items.append(record)
        if len(items) >= limit:
            break

    items, patched_records = backfill_analysis_record_signals(items)
    persist_analysis_signal_backfill(patched_records)
    return ValidationQueueResponse(items=items)
