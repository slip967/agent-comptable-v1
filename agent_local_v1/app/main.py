from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import run_agent
from .config import FRONTEND_ORIGINS, OPENROUTER_MODEL
from .loader import load_all_bases
from .memory import build_memory_decision, find_reusable_validation, get_memory_stats, save_validation
from .schemas import (
    AccountingDecision,
    HumanValidationInput,
    HumanValidationRecord,
    InvoiceLineInput,
    MemoryStats,
)
from .tools import matcher_tool


app = FastAPI(
    title="Agent Comptable Local V1",
    description="API locale pour recommandation comptable ligne par ligne.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "openrouter_model": OPENROUTER_MODEL,
        "references_loaded": len(matcher_tool.load_references()),
        "base_items_loaded": len(load_all_bases()),
    }


@app.get("/memory/stats", response_model=MemoryStats)
def memory_stats() -> MemoryStats:
    return get_memory_stats()


@app.post("/recommend", response_model=AccountingDecision)
def recommend(payload: InvoiceLineInput) -> AccountingDecision:
    memory_record = find_reusable_validation(
        article_source=payload.article_source,
        metier_hint=payload.metier_hint,
    )
    if memory_record is not None:
        return build_memory_decision(payload.article_source, memory_record)

    candidates = matcher_tool.match_line(
        article_source=payload.article_source,
        metier_hint=payload.metier_hint,
        tva_hint=payload.tva_hint,
        top_n=3,
        include_charges=payload.include_charges,
    )

    result = run_agent(
        article_source=payload.article_source,
        candidates=candidates,
        metier_hint=payload.metier_hint,
        tva_hint=payload.tva_hint,
    )
    return AccountingDecision(**result)


@app.post("/feedback", response_model=HumanValidationRecord)
def feedback(payload: HumanValidationInput) -> HumanValidationRecord:
    return save_validation(payload)
