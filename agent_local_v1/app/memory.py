from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PACKAGE_DIR
from .loader import normalize_text
from .schemas import (
    AccountingDecision,
    AnalysisHistoryRecord,
    AnalysisHistoryResponse,
    HumanValidationInput,
    HumanValidationRecord,
    MemoryStats,
    ValidationQueueResponse,
    InvoiceLineInput,
)


MEMORY_DIR = PACKAGE_DIR / "data"
MEMORY_FILE = MEMORY_DIR / "validation_memory.jsonl"
ANALYSIS_HISTORY_FILE = MEMORY_DIR / "analysis_history.jsonl"


def _ensure_memory_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _read_lines() -> list[dict]:
    return _read_jsonl(MEMORY_FILE)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _build_lookup_key(article_source: str, metier_hint: str | None = None) -> str:
    article_source_normalized = normalize_text(article_source)
    metier_hint_normalized = (metier_hint or "").strip().lower()
    return f"{article_source_normalized}::{metier_hint_normalized}"


def save_validation(payload: HumanValidationInput) -> HumanValidationRecord:
    _ensure_memory_dir()

    record = HumanValidationRecord(
        **payload.model_dump(),
        article_source_normalized=normalize_text(payload.article_source),
        lookup_key=_build_lookup_key(payload.article_source, payload.metier_hint),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    _append_jsonl(MEMORY_FILE, record.model_dump())

    return record


def save_analysis_event(
    payload: InvoiceLineInput,
    decision: AccountingDecision,
    source: str,
) -> AnalysisHistoryRecord:
    _ensure_memory_dir()

    record = AnalysisHistoryRecord(
        article_source=decision.article_source,
        article_source_normalized=normalize_text(decision.article_source),
        lookup_key=_build_lookup_key(decision.article_source, payload.metier_hint),
        metier_hint=payload.metier_hint,
        tva_hint=payload.tva_hint,
        include_charges=payload.include_charges,
        categorie=decision.categorie,
        sous_categorie=decision.sous_categorie,
        compte_comptable=decision.compte_comptable,
        score_confiance=decision.score_confiance,
        decision=decision.decision,
        explication=decision.explication,
        source="memory" if source == "memory" else "engine",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    _append_jsonl(ANALYSIS_HISTORY_FILE, record.model_dump())
    return record


def find_reusable_validation(
    article_source: str,
    metier_hint: str | None = None,
) -> HumanValidationRecord | None:
    lookup_key = _build_lookup_key(article_source, metier_hint)

    for row in reversed(_read_lines()):
        try:
            record = HumanValidationRecord(**row)
        except Exception:
            continue

        if record.lookup_key != lookup_key or record.decision_humaine == "rejeter":
            continue
        if not record.compte_comptable_final:
            continue

        return record

    return None


def build_memory_decision(
    article_source: str,
    record: HumanValidationRecord,
) -> AccountingDecision:
    return AccountingDecision(
        article_source=article_source,
        categorie=record.categorie_finale,
        sous_categorie=record.sous_categorie_finale,
        compte_comptable=record.compte_comptable_final,
        score_confiance=100.0,
        decision="auto_ok",
        explication=(
            "Reprise d'une validation humaine precedente sur le meme libelle. "
            f"Derniere decision humaine: {record.decision_humaine}."
        ),
        candidats=[],
    )


def get_memory_stats() -> MemoryStats:
    rows = _read_lines()
    reusable = 0
    for row in rows:
        decision_humaine = str(row.get("decision_humaine") or "").strip().lower()
        compte_comptable_final = str(row.get("compte_comptable_final") or "").strip()
        if decision_humaine != "rejeter" and compte_comptable_final:
            reusable += 1

    return MemoryStats(
        memory_file=str(MEMORY_FILE),
        total_records=len(rows),
        reusable_records=reusable,
    )


def get_analysis_history(limit: int = 20) -> AnalysisHistoryResponse:
    items: list[AnalysisHistoryRecord] = []
    for row in reversed(_read_jsonl(ANALYSIS_HISTORY_FILE)):
        try:
            items.append(AnalysisHistoryRecord(**row))
        except Exception:
            continue
        if len(items) >= limit:
            break

    return AnalysisHistoryResponse(items=items)


def get_validation_queue(limit: int = 20) -> ValidationQueueResponse:
    latest_validation_by_key: dict[str, str] = {}
    for row in _read_lines():
        try:
            record = HumanValidationRecord(**row)
        except Exception:
            continue
        latest_validation_by_key[record.lookup_key] = max(
            latest_validation_by_key.get(record.lookup_key, ""),
            record.created_at,
        )

    seen_keys: set[str] = set()
    items: list[AnalysisHistoryRecord] = []
    for row in reversed(_read_jsonl(ANALYSIS_HISTORY_FILE)):
        try:
            record = AnalysisHistoryRecord(**row)
        except Exception:
            continue

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

    return ValidationQueueResponse(items=items)
