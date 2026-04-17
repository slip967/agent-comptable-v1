from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .agent import run_agent, run_frontend_assistant
from .config import FRONTEND_ORIGINS, OPENROUTER_MODEL
from .loader import load_all_bases
from .memory import (
    build_memory_decision,
    find_reusable_validation,
    get_analysis_history,
    get_memory_stats,
    get_validation_queue,
    save_analysis_event,
    save_validation,
)
from .schemas import (
    AccountingDecision,
    AnalysisHistoryResponse,
    FrontendAssistantInput,
    FrontendAssistantReply,
    HumanValidationInput,
    HumanValidationRecord,
    InvoiceLineInput,
    MemoryStats,
    ValidationQueueResponse,
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


def _recommend_payload(payload: InvoiceLineInput) -> AccountingDecision:
    memory_record = find_reusable_validation(
        article_source=payload.article_source,
        metier_hint=payload.metier_hint,
    )
    if memory_record is not None:
        decision = build_memory_decision(payload.article_source, memory_record)
        save_analysis_event(payload, decision, source="memory")
        return decision

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
    decision = AccountingDecision(**result)
    save_analysis_event(payload, decision, source="engine")
    return decision


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


@app.get("/analysis/history", response_model=AnalysisHistoryResponse)
def analysis_history(limit: int = Query(default=12, ge=1, le=100)) -> AnalysisHistoryResponse:
    return get_analysis_history(limit=limit)


@app.get("/validation-queue", response_model=ValidationQueueResponse)
def validation_queue(limit: int = Query(default=12, ge=1, le=100)) -> ValidationQueueResponse:
    return get_validation_queue(limit=limit)


@app.post("/recommend", response_model=AccountingDecision)
def recommend(payload: InvoiceLineInput) -> AccountingDecision:
    return _recommend_payload(payload)


@app.post("/feedback", response_model=HumanValidationRecord)
def feedback(payload: HumanValidationInput) -> HumanValidationRecord:
    return save_validation(payload)


@app.post("/assistant", response_model=FrontendAssistantReply)
def assistant(payload: FrontendAssistantInput) -> FrontendAssistantReply:
    return run_frontend_assistant(payload)
