from __future__ import annotations

import time
import traceback

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .agent import run_agent, run_frontend_assistant
from .history_service import add_history_event
from .config import (
    FRONTEND_ORIGINS,
    COUCHDB_DATABASE,
    MEMORY_COUCH_DB,
    MEMORY_SOURCE,
    OPENROUTER_MODEL,
    OPENROUTER_VISION_MODEL,
    REFERENCE_COUCH_DB,
    REFERENCE_SOURCE,
)
from .database import DATABASE_FILE, get_supplier_memory, get_validation_patterns
from .invoice_analysis import analyze_invoice_upload, analyze_ocr_text_payload
from .invoice_engine_service import (
    analyze_invoice_by_id,
    analyze_invoice_lines_strong,
    determine_invoice_workflow_status,
    fetch_random_invoices,
)
from .local_knowledge_bases import local_knowledge_bases
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
    InvoiceAnalysisResponse,
    InvoiceLineInput,
    KnowledgeBasesSummaryResponse,
    MemoryStats,
    OCRTextAnalysisInput,
    RandomInvoicesResponse,
    StrongAnalysisLinesInput,
    StrongAnalysisResponse,
    ValidationQueueResponse,
)
from .routers import analysis_router, human_validation_router, invoices_router, motor_sync_router, workflow_router
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

@app.middleware("http")
async def ensure_json_utf8(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.lower().startswith("application/json"):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response

app.include_router(analysis_router, prefix="/api")
app.include_router(human_validation_router, prefix="/api")
app.include_router(invoices_router, prefix="/api")
app.include_router(motor_sync_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")


@app.on_event("startup")
def warmup_references() -> None:
    print(f"CouchDB database utilisée : {COUCHDB_DATABASE}")
    try:
        matcher_tool.load_references()
    except Exception:
        pass

    try:
        local_knowledge_bases.load_references()
        local_knowledge_bases.get_summary()
    except Exception:
        pass


def _append_explanation_note(explication: str, note: str) -> str:
    base = (explication or "").strip()
    extra = (note or "").strip()
    if not extra:
        return base
    if extra in base:
        return base
    if not base:
        return extra
    return f"{base} {extra}".strip()


def _build_supplier_signal_note(
    fournisseur_hint: str | None,
    compte_comptable: str | None,
    supplier_account_stats: dict[str, dict[str, object]] | None,
) -> str:
    if not fournisseur_hint or not compte_comptable or not supplier_account_stats:
        return ""

    stats = supplier_account_stats.get(str(compte_comptable).strip())
    if not stats:
        return ""

    count = int(stats.get("count") or 0)
    total_matches = int(stats.get("total_matches") or 0)
    is_dominant = bool(stats.get("is_dominant"))
    if count <= 0 or total_matches <= 0:
        return ""

    if count == 1:
        return (
            f"Signal fournisseur: le compte {compte_comptable} a deja ete valide une fois "
            f"pour {fournisseur_hint}."
        )

    dominant_note = (
        f" C'est le compte le plus frequent pour ce fournisseur sur {total_matches} validations."
        if is_dominant
        else ""
    )
    return (
        f"Signal fournisseur: le compte {compte_comptable} a deja ete valide {count} fois "
        f"pour {fournisseur_hint}.{dominant_note}"
    ).strip()


def _build_human_pattern_note(
    compte_comptable: str | None,
    validation_pattern_stats: dict[str, dict[str, object]] | None,
) -> str:
    if not compte_comptable or not validation_pattern_stats:
        return ""

    stats = validation_pattern_stats.get(str(compte_comptable).strip())
    if not stats:
        return ""

    explanation = str(stats.get("explanation") or "").strip()
    if explanation:
        return f"Signal validation humaine: {explanation}"

    count = int(stats.get("count") or 0)
    if count <= 0:
        return ""

    if count == 1:
        return f"Signal validation humaine: le compte {compte_comptable} a deja ete retenu une fois sur un cas similaire."

    return (
        f"Signal validation humaine: le compte {compte_comptable} a deja ete retenu "
        f"{count} fois sur des cas similaires."
    )


def _build_ape_signal_note(
    decision: AccountingDecision,
    client_ape_hint: str | None,
    supplier_ape_hint: str | None,
) -> str:
    selected_candidate = _select_decision_candidate(decision)
    if selected_candidate is None:
        return ""

    ape_signal = next(
        (signal for signal in selected_candidate.signals if signal.key == "ape_pair_context"),
        None,
    )
    if ape_signal is None:
        return ""

    score = float(ape_signal.value or 0.0)
    context_bits: list[str] = []
    if client_ape_hint:
        context_bits.append(f"client={client_ape_hint}")
    if supplier_ape_hint:
        context_bits.append(f"fournisseur={supplier_ape_hint}")
    context_note = f" ({', '.join(context_bits)})" if context_bits else ""

    if score >= 0.85:
        return f"Signal APE: {ape_signal.explanation}{context_note}"
    if score >= 0.6:
        return f"Signal APE partiel: {ape_signal.explanation}{context_note}"
    return f"Signal APE faible: {ape_signal.explanation}{context_note}"


def _select_decision_candidate(decision: AccountingDecision):
    if not decision.candidats:
        return None

    if decision.compte_comptable:
        selected_candidate = next(
            (
                candidate
                for candidate in decision.candidats
                if candidate.compte_comptable == decision.compte_comptable
            ),
            None,
        )
        if selected_candidate is not None:
            return selected_candidate

    return decision.candidats[0]


def _extract_decision_signals(decision: AccountingDecision) -> list:
    if decision.signals:
        return list(decision.signals)

    selected_candidate = _select_decision_candidate(decision)
    if selected_candidate is None:
        return []

    return list(selected_candidate.signals or [])


def _recommend_payload(payload: InvoiceLineInput) -> AccountingDecision:
    memory_record = find_reusable_validation(
        article_source=payload.article_source,
        metier_hint=payload.metier_hint,
        fournisseur_hint=payload.fournisseur_hint,
    )
    if memory_record is not None:
        decision = build_memory_decision(payload.article_source, memory_record)
        save_analysis_event(payload, decision, source="memory")
        return decision

    supplier_account_stats = get_supplier_memory(
        fournisseur_hint=payload.fournisseur_hint,
        metier_hint=payload.metier_hint,
    )
    validation_pattern_stats = get_validation_patterns(
        article_source=payload.article_source,
        fournisseur_hint=payload.fournisseur_hint,
        metier_hint=payload.metier_hint,
    )
    candidates = matcher_tool.match_line(
        article_source=payload.article_source,
        fournisseur_hint=payload.fournisseur_hint,
        metier_hint=payload.metier_hint,
        client_ape_hint=payload.client_ape_hint,
        supplier_ape_hint=payload.supplier_ape_hint,
        tva_hint=payload.tva_hint,
        top_n=3,
        include_charges=payload.include_charges,
        supplier_account_stats=supplier_account_stats,
        validation_pattern_stats=validation_pattern_stats,
    )

    result = run_agent(
        article_source=payload.article_source,
        candidates=candidates,
        fournisseur_hint=payload.fournisseur_hint,
        metier_hint=payload.metier_hint,
        tva_hint=payload.tva_hint,
    )
    decision = AccountingDecision(**result)
    decision.signals = _extract_decision_signals(decision)
    supplier_note = _build_supplier_signal_note(
        payload.fournisseur_hint,
        decision.compte_comptable,
        supplier_account_stats,
    )
    if supplier_note:
        decision.explication = _append_explanation_note(decision.explication, supplier_note)
    human_pattern_note = _build_human_pattern_note(
        decision.compte_comptable,
        validation_pattern_stats,
    )
    if human_pattern_note:
        decision.explication = _append_explanation_note(decision.explication, human_pattern_note)
    ape_note = _build_ape_signal_note(
        decision,
        payload.client_ape_hint,
        payload.supplier_ape_hint,
    )
    if ape_note:
        decision.explication = _append_explanation_note(decision.explication, ape_note)
    save_analysis_event(payload, decision, source=decision.source)
    return decision


@app.get("/health")
def health() -> dict[str, object]:
    refs = matcher_tool.load_references()
    return {
        "status": "ok",
        "openrouter_model": OPENROUTER_MODEL,
        "openrouter_vision_model": OPENROUTER_VISION_MODEL,
        "references_loaded": len(refs),
        "base_items_loaded": len(refs),
        "references_backend": matcher_tool.reference_source,
        "reference_source_mode": REFERENCE_SOURCE,
        "reference_db": REFERENCE_COUCH_DB,
        "reference_error": matcher_tool.reference_error or None,
        "memory_backend": MEMORY_SOURCE,
        "memory_db": MEMORY_COUCH_DB,
        "memory_store": str(DATABASE_FILE),
    }


@app.get("/memory/stats", response_model=MemoryStats)
def memory_stats() -> MemoryStats:
    return get_memory_stats()


@app.get("/knowledge-bases/summary", response_model=KnowledgeBasesSummaryResponse)
def knowledge_bases_summary() -> KnowledgeBasesSummaryResponse:
    return local_knowledge_bases.get_summary()


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


@app.post("/ocr/analyze-invoice", response_model=InvoiceAnalysisResponse)
def analyze_invoice(file: UploadFile = File(...)) -> InvoiceAnalysisResponse:
    return analyze_invoice_upload(file)


@app.post("/analyze/ocr-text", response_model=InvoiceAnalysisResponse)
def analyze_ocr_text(payload: OCRTextAnalysisInput) -> InvoiceAnalysisResponse:
    return analyze_ocr_text_payload(payload)


@app.post("/analysis/strong-lines", response_model=StrongAnalysisResponse)
def analyze_strong_lines(payload: StrongAnalysisLinesInput) -> StrongAnalysisResponse:
    if not payload.lines and not str(payload.ocr_text or "").strip():
        raise HTTPException(status_code=400, detail="Aucune ligne exploitable fournie.")

    try:
        source_payload: dict[str, object] | list[dict[str, object]] | str
        if payload.lines:
            source_payload = [
                {
                    "description": line.description,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "amount_ht": line.amount_ht,
                    "amount_ttc": line.amount_ttc,
                    "tva": line.tva,
                }
                for line in payload.lines
            ]
        else:
            source_payload = payload.ocr_text or ""
        response = analyze_invoice_lines_strong(source_payload, payload.context)
        add_history_event(
            {
                "event_type": "invoice_analyzed",
                "source": "analyse_ia",
                "invoice_id": str(response.invoice.invoice_id or "").strip(),
                "invoice_number": str(response.invoice.invoice_number or payload.filename or "").strip(),
                "supplier": str(response.invoice.supplier or payload.context.supplier or "").strip(),
                "client": str(response.invoice.client or payload.context.client or "").strip(),
                "message": (
                    f"Analyse lancee sur {response.summary.total_lines} ligne(s) "
                    f"dont {response.summary.auto_ok} Auto OK et "
                    f"{response.summary.validation_humaine} a valider."
                ),
            }
        )
        return response
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/analysis/strong-invoice/{invoice_id}", response_model=StrongAnalysisResponse)
def analyze_strong_invoice(invoice_id: str) -> StrongAnalysisResponse:
    started = time.perf_counter()
    print(f"[api/analysis/strong-invoice] start invoice_id={invoice_id}")
    try:
        response = analyze_invoice_by_id(invoice_id)
        routing = determine_invoice_workflow_status(response, invoice_id=invoice_id)
        workflow_status = str(routing.get("workflow_status") or "A_CONTROLER")
        response.invoice.status = workflow_status
        from .analysis_batch_service import _apply_invoice_workflow_status

        _apply_invoice_workflow_status(
            response,
            {
                "invoice_id": str(response.invoice.invoice_id or invoice_id).strip(),
                "invoice_number": str(response.invoice.invoice_number or "").strip(),
                "supplier": str(response.invoice.supplier or "").strip(),
                "client": str(response.invoice.client or "").strip(),
                "workflow_status": workflow_status,
                "destination": str(routing.get("destination") or "validation_humaine"),
                "routing_reasons": list(routing.get("routing_reasons") or []),
                "all_lines_exact_auto": bool(routing.get("all_lines_exact_auto") or False),
                "amounts_balanced": bool(routing.get("amounts_balanced") or False),
                "is_duplicate": bool(routing.get("is_duplicate") or False),
                "global_decision": str(routing.get("global_decision") or ""),
                "global_risk_level": str(routing.get("global_risk_level") or ""),
                "can_validate_accounting": bool(routing.get("can_validate_accounting") if routing.get("can_validate_accounting") is not None else True),
                "status": "completed",
                "analysis_status": "success",
                "auto_ok": int(response.summary.auto_ok or 0),
                "validation_humaine": int(response.summary.validation_humaine or 0),
                "rejeter": int(response.summary.rejeter or 0),
                "non_comptable": int(response.summary.non_comptable or 0),
                "unknown": int(response.summary.unknown or 0),
                "average_confidence": float(routing.get("average_confidence") or response.summary.average_confidence or 0.0),
            },
        )
        total_ms = round((time.perf_counter() - started) * 1000, 2)
        print(
            f"[api/analysis/strong-invoice] success invoice_id={invoice_id} "
            f"lines={response.summary.total_lines} workflow_status={workflow_status} "
            f"destination={routing.get('destination')} total_ms={total_ms}"
        )
        return response
    except RuntimeError as exc:
        total_ms = round((time.perf_counter() - started) * 1000, 2)
        detail = str(exc)
        status_code = 404 if "introuvable" in detail.lower() else 503
        print(
            f"[api/analysis/strong-invoice] runtime_error invoice_id={invoice_id} "
            f"status={status_code} total_ms={total_ms} detail={detail}"
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:  # pragma: no cover - runtime observability
        total_ms = round((time.perf_counter() - started) * 1000, 2)
        print(
            f"[api/analysis/strong-invoice] unexpected_error invoice_id={invoice_id} "
            f"total_ms={total_ms} error={exc.__class__.__name__}: {exc}"
        )
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur moteur pendant l'analyse.") from exc


@app.get("/analysis/random-invoices", response_model=RandomInvoicesResponse)
def random_invoices(limit: int = Query(default=10, ge=1, le=30)) -> RandomInvoicesResponse:
    try:
        return fetch_random_invoices(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


