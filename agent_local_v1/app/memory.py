from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PACKAGE_DIR
from .loader import normalize_text
from .schemas import (
    AccountingDecision,
    HumanValidationInput,
    HumanValidationRecord,
    MemoryStats,
)


MEMORY_DIR = PACKAGE_DIR / "data"
MEMORY_FILE = MEMORY_DIR / "validation_memory.jsonl"


def _ensure_memory_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _read_lines() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []

    rows: list[dict] = []
    with MEMORY_FILE.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def save_validation(payload: HumanValidationInput) -> HumanValidationRecord:
    _ensure_memory_dir()

    record = HumanValidationRecord(
        **payload.model_dump(),
        article_source_normalized=normalize_text(payload.article_source),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    with MEMORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

    return record


def find_reusable_validation(
    article_source: str,
    metier_hint: str | None = None,
) -> HumanValidationRecord | None:
    article_source_normalized = normalize_text(article_source)
    metier_hint_normalized = (metier_hint or "").strip().lower()

    for row in reversed(_read_lines()):
        try:
            record = HumanValidationRecord(**row)
        except Exception:
            continue

        if record.article_source_normalized != article_source_normalized:
            continue
        if record.decision_humaine == "rejeter":
            continue
        if not record.compte_comptable_final:
            continue

        record_metier = (record.metier_hint or "").strip().lower()
        if metier_hint_normalized and record_metier and record_metier != metier_hint_normalized:
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
