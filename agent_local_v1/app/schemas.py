from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InvoiceLineInput(BaseModel):
    article_source: str = Field(..., description="Libelle de ligne facture")
    fournisseur_hint: str | None = Field(default=None, description="Nom du fournisseur si connu")
    metier_hint: str | None = Field(default=None, description="Indice metier si connu")
    client_ape_hint: str | None = Field(default=None, description="APE client si connu")
    supplier_ape_hint: str | None = Field(default=None, description="APE fournisseur si connu")
    tva_hint: float | None = Field(default=None, description="TVA de la ligne si connue")
    include_charges: bool = Field(
        default=True,
        description="Inclure les charges externes dans la recherche",
    )


class OCRTextAnalysisInput(BaseModel):
    filename: str = Field(default="ocr-text.txt", description="Nom du document OCR")
    ocr_text: str = Field(..., description="Texte OCR deja extrait par Mistral OCR")
    metier_hint: str | None = Field(default=None, description="Indice metier si connu")
    ape_client: str | None = Field(default=None, description="Code APE client si connu")
    ape_fournisseur: str | None = Field(default=None, description="Code APE fournisseur si connu")
    fournisseur_hint: str | None = Field(default=None, description="Fournisseur si deja connu")


class SignalDetail(BaseModel):
    key: str
    label: str
    family: Literal["fort", "moyen", "faible"]
    weight: float
    value: float = 0.0
    contribution: float = 0.0
    explanation: str = ""


class CandidateLine(BaseModel):
    base_cible: str
    metier: str
    article_source: str | None = None
    article_source_match: str
    article_canonique: str
    categorie: str
    sous_categorie: str
    compte_comptable: str
    compte_comptable_libelle: str | None = None
    account_label: str | None = None
    score_confiance: float
    final_score: float | None = None
    score_texte: float | None = None
    raison_match: str
    tva_coherence: str
    metier_coherence: str
    decision: str
    taux_tva: float | None = None
    type_fournisseur: str | None = None
    alertes: list[str] = Field(default_factory=list)
    source_invoice_ids: list[str] = Field(default_factory=list)
    ids_factures_sources: list[str] = Field(default_factory=list)
    invoice_paths_sources: list[str] = Field(default_factory=list)
    partitions_sources: list[str] = Field(default_factory=list)
    ape_context: list[str] = Field(default_factory=list)
    signals: list[SignalDetail] = Field(default_factory=list)


class AccountingDecision(BaseModel):
    article_source: str
    categorie: str | None = None
    sous_categorie: str | None = None
    compte_comptable: str | None = None
    compte_comptable_libelle: str | None = None
    score_confiance: float = 0.0
    decision: Literal["auto_ok", "validation_humaine", "rejeter"] = "validation_humaine"
    explication: str
    source: Literal["engine", "memory", "ai"] = "engine"
    signals: list[SignalDetail] = Field(default_factory=list)
    candidats: list[CandidateLine] = Field(default_factory=list)


class HumanValidationInput(BaseModel):
    article_source: str = Field(..., description="Libelle valide humainement")
    fournisseur_hint: str | None = Field(default=None, description="Fournisseur de contexte")
    metier_hint: str | None = Field(default=None, description="Metier de contexte")
    client_ape_hint: str | None = Field(default=None, description="APE client de contexte")
    supplier_ape_hint: str | None = Field(default=None, description="APE fournisseur de contexte")
    tva_hint: float | None = Field(default=None, description="TVA de contexte")
    decision_humaine: Literal["valider", "modifier", "rejeter"]
    compte_comptable_final: str | None = None
    categorie_finale: str | None = None
    sous_categorie_finale: str | None = None
    commentaire: str | None = None
    recommandation_ia: AccountingDecision | None = None


class HumanValidationRecord(HumanValidationInput):
    article_source_normalized: str
    lookup_key: str
    created_at: str


class MemoryStats(BaseModel):
    memory_file: str
    total_records: int
    reusable_records: int


class AnalysisHistoryRecord(BaseModel):
    article_source: str
    article_source_normalized: str
    lookup_key: str
    fournisseur_hint: str | None = None
    metier_hint: str | None = None
    client_ape_hint: str | None = None
    supplier_ape_hint: str | None = None
    tva_hint: float | None = None
    include_charges: bool = True
    categorie: str | None = None
    sous_categorie: str | None = None
    compte_comptable: str | None = None
    score_confiance: float = 0.0
    decision: Literal["auto_ok", "validation_humaine", "rejeter"] = "validation_humaine"
    explication: str
    source: Literal["engine", "memory", "ai"] = "engine"
    signals: list[SignalDetail] = Field(default_factory=list)
    candidats: list[CandidateLine] = Field(default_factory=list)
    created_at: str


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryRecord] = Field(default_factory=list)


class ValidationQueueResponse(BaseModel):
    items: list[AnalysisHistoryRecord] = Field(default_factory=list)


class FrontendAssistantInput(BaseModel):
    user_message: str = Field(..., description="Message libre saisi dans l'assistant frontend")
    article_source: str | None = Field(default=None, description="Libelle actuellement saisi")
    fournisseur_hint: str | None = Field(default=None, description="Fournisseur en contexte")
    metier_hint: str | None = Field(default=None, description="Metier en contexte")
    client_ape_hint: str | None = Field(default=None, description="APE client en contexte")
    supplier_ape_hint: str | None = Field(default=None, description="APE fournisseur en contexte")
    tva_hint: float | None = Field(default=None, description="TVA en contexte")
    current_decision: AccountingDecision | None = Field(
        default=None,
        description="Derniere decision retournee par /recommend si disponible",
    )
    selected_candidate: CandidateLine | None = Field(
        default=None,
        description="Candidat actuellement selectionne dans le panneau detail si disponible",
    )


class FrontendAssistantReply(BaseModel):
    answer: str
    suggested_action: Literal["analyser", "valider", "modifier", "rejeter", "neutre"] = "neutre"


class OCRCompanyRegistration(BaseModel):
    type: str | None = None
    value: str | None = None


class OCRInvoiceIssuer(BaseModel):
    name: str | None = None
    company_registrations: list[OCRCompanyRegistration] = Field(default_factory=list)
    iban: str | None = None
    bic: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class OCRInvoiceRecipient(BaseModel):
    name: str | None = None
    company_registrations: list[OCRCompanyRegistration] = Field(default_factory=list)
    client_code: str | None = None
    billing_address: str | None = None
    shipping_address: str | None = None


class OCRInvoiceLineItem(BaseModel):
    product_code: str | None = None
    description: str
    item_type: str | None = None
    activity_match_confidence_score: float | None = None
    unit_price: float | None = None
    quantity: float | None = None
    unit: str | None = None
    discount: float | None = None
    vat_percent: float | None = None
    vat_total: float | None = None
    total_net: float | None = None
    total_gross: float | None = None
    accounting_account: str | None = None
    accounting_account_label: str | None = None


class OCRInvoiceVATLine(BaseModel):
    vat_amount: float | None = None
    vat_percent: float | None = None
    vat_total: float | None = None


class OCRAccountingSummaryLine(BaseModel):
    accounting_account: str | None = None
    accounting_account_label: str | None = None
    total_net: float | None = None
    total_vat: float | None = None
    total_gross: float | None = None


class OCRPaymentInfo(BaseModel):
    payment_method: str | None = None
    payment_due_date: str | None = None
    payment_amount: float | None = None
    language: str | None = None


class OCRStructuredInvoice(BaseModel):
    filename: str | None = None
    raw_ocr_text: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    document_type: str | None = "Invoice"
    issuer: OCRInvoiceIssuer = Field(default_factory=OCRInvoiceIssuer)
    recipient: OCRInvoiceRecipient = Field(default_factory=OCRInvoiceRecipient)
    line_items: list[OCRInvoiceLineItem] = Field(default_factory=list)
    flag_articles_atypiques: bool | None = None
    vat: list[OCRInvoiceVATLine] = Field(default_factory=list)
    discount_percent: float | None = None
    discount_amount: float | None = None
    cash_discount_percent: float | None = None
    cash_discount_amount: float | None = None
    deposit_amount: float | None = None
    down_payment_amount: float | None = None
    total_net: float | None = None
    total_vat: float | None = None
    total_gross: float | None = None
    accounting_summary: list[OCRAccountingSummaryLine] = Field(default_factory=list)
    payment: OCRPaymentInfo = Field(default_factory=OCRPaymentInfo)
    currency: str | None = None


class OCRInvoiceLine(BaseModel):
    raw_text: str
    quantity: float | None = None
    amount: float | None = None


class OCRInvoiceExtraction(OCRStructuredInvoice):
    pass


class InvoiceAISignals(BaseModel):
    article_match: bool = False
    metier_match: bool = False
    tva_match: bool = False
    ape_match: bool = False
    memory_match: bool = False
    invoice_sources_found: bool = False


class InvoiceTopCandidate(BaseModel):
    account: str | None = None
    account_label: str | None = None
    compte_comptable_libelle: str | None = None
    article_source: str
    article_canonique: str | None = None
    base: str
    score: float
    reason: str
    categorie: str | None = None
    sous_categorie: str | None = None
    taux_tva: float | None = None
    type_fournisseur: str | None = None
    source_invoice_ids: list[str] = Field(default_factory=list)
    ids_factures_sources: list[str] = Field(default_factory=list)
    invoice_paths_sources: list[str] = Field(default_factory=list)
    partitions_sources: list[str] = Field(default_factory=list)
    ape_context: list[str] = Field(default_factory=list)


class InvoiceLineAnalysis(BaseModel):
    raw_text: str
    recommended_account: str | None = None
    recommended_account_label: str | None = None
    compte_comptable_libelle: str | None = None
    metier: str | None = None
    confidence: float = 0.0
    risk_level: Literal["faible", "moyen", "eleve"] = "moyen"
    status: Literal["Auto OK", "Validation humaine", "Inconnu"] = "Validation humaine"
    explanation: str = ""
    justification: str = ""
    decision_source: Literal["engine", "memory", "ai"] = "engine"
    category: str | None = None
    subcategory: str | None = None
    taux_tva: float | None = None
    type_fournisseur: str | None = None
    source_invoice_ids: list[str] = Field(default_factory=list)
    ids_factures_sources: list[str] = Field(default_factory=list)
    invoice_paths_sources: list[str] = Field(default_factory=list)
    partitions_sources: list[str] = Field(default_factory=list)
    ape_context: list[str] = Field(default_factory=list)
    signals: InvoiceAISignals = Field(default_factory=InvoiceAISignals)
    top_candidates: list[InvoiceTopCandidate] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class InvoiceAnalysisResponse(BaseModel):
    invoice: OCRStructuredInvoice
    ocr_lines: list[OCRInvoiceLine] = Field(default_factory=list)
    analysis: list[InvoiceLineAnalysis] = Field(default_factory=list)


class KnowledgeBaseSummaryItem(BaseModel):
    key: str
    label: str
    file: str
    articles: int = 0
    with_invoice_sources: int = 0
    with_partitions: int = 0
    readiness: Literal["pret", "a_controler"] = "pret"


class KnowledgeBasesSummaryResponse(BaseModel):
    total_bases: int = 0
    total_articles: int = 0
    items: list[KnowledgeBaseSummaryItem] = Field(default_factory=list)


class StrongAnalysisContext(BaseModel):
    supplier: str | None = None
    client: str | None = None
    client_ape: str | None = None
    supplier_ape: str | None = None
    metier_hint: str | None = None
    currency: str | None = None


class StrongAnalysisLineInput(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount_ht: float | None = None
    amount_ttc: float | None = None
    tva: float | None = None


class StrongAnalysisLinesInput(BaseModel):
    filename: str | None = "facture_existante.pdf"
    ocr_text: str | None = None
    lines: list[StrongAnalysisLineInput] = Field(default_factory=list)
    context: StrongAnalysisContext = Field(default_factory=StrongAnalysisContext)


class StrongEnrichmentSuggestion(BaseModel):
    should_enrich: bool = False
    suggested_base: str | None = None
    suggested_account: str | None = None
    suggested_label: str | None = None
    reason: str = ""
    requires_expert_validation: bool = True


class StrongTopCandidate(BaseModel):
    account: str | None = None
    account_label: str | None = None
    article_source: str | None = None
    article_canonique: str | None = None
    base: str | None = None
    score: float = 0.0
    reason: str = ""
    decision: str | None = None
    evidence_status: Literal["complete", "partial", "missing"] = "missing"
    categorie: str | None = None
    sous_categorie: str | None = None
    taux_tva: float | None = None
    type_fournisseur: str | None = None
    source_invoice_ids: list[str] = Field(default_factory=list)
    invoice_paths_sources: list[str] = Field(default_factory=list)
    partitions_sources: list[str] = Field(default_factory=list)
    ape_context: list[str] = Field(default_factory=list)


class StrongInvoiceHeader(BaseModel):
    invoice_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier: str | None = None
    client: str | None = None
    client_ape: str | None = None
    supplier_ape: str | None = None
    metier_hint: str | None = None
    currency: str | None = None
    total_lines: int = 0
    exploitable_lines: int = 0
    status: str = "prete_a_analyser"


class StrongLineAnalysis(BaseModel):
    raw_text: str
    cleaned_text: str
    quantity: float | None = None
    unit_price: float | None = None
    amount_ht: float | None = None
    amount_ttc: float | None = None
    tva: float | None = None
    supplier: str | None = None
    client: str | None = None
    client_ape: str | None = None
    supplier_ape: str | None = None
    metier_hint: str | None = None
    detected_activity: str | None = None
    referential_status: Literal[
        "found_exact",
        "found_fuzzy",
        "missing_candidate",
        "unknown",
        "non_comptable",
    ] = "unknown"
    recommended_account: str | None = None
    recommended_account_label: str | None = None
    confidence: float = 0.0
    risk_level: Literal["faible", "moyen", "eleve"] = "moyen"
    decision: Literal["auto_ok", "validation_humaine", "rejeter", "non_comptable"] = (
        "validation_humaine"
    )
    decision_reason: str = ""
    evidence_status: Literal["complete", "partial", "missing"] = "missing"
    quality_status: Literal["fiable", "a_controler"] = "a_controler"
    source_invoice_ids: list[str] = Field(default_factory=list)
    invoice_paths_sources: list[str] = Field(default_factory=list)
    partitions_sources: list[str] = Field(default_factory=list)
    ape_context: list[str] = Field(default_factory=list)
    taux_tva: float | None = None
    categorie: str | None = None
    sous_categorie: str | None = None
    type_fournisseur: str | None = None
    top_candidates: list[StrongTopCandidate] = Field(default_factory=list)
    enrichment_suggestion: StrongEnrichmentSuggestion = Field(
        default_factory=StrongEnrichmentSuggestion
    )


class StrongAnalysisSummary(BaseModel):
    total_lines: int = 0
    auto_ok: int = 0
    validation_humaine: int = 0
    rejeter: int = 0
    non_comptable: int = 0
    unknown: int = 0
    articles_absents_referentiel: int = 0
    average_confidence: float = 0.0


class StrongAnalysisResponse(BaseModel):
    invoice: StrongInvoiceHeader = Field(default_factory=StrongInvoiceHeader)
    summary: StrongAnalysisSummary = Field(default_factory=StrongAnalysisSummary)
    lines: list[StrongLineAnalysis] = Field(default_factory=list)
    accounting_proposal: AccountingProposal | None = None


# ---------------------------------------------------------------------------
# Accounting proposal schemas
# ---------------------------------------------------------------------------

class AccountingProposalLine(BaseModel):
    line_id: str
    raw_text: str
    cleaned_text: str
    amount_ht: float | None = None
    amount_ttc: float | None = None
    tva: float | None = None
    recommended_account: str | None = None
    account_label: str | None = None
    confidence: float = 0.0
    risk_level: Literal["faible", "moyen", "eleve"] = "moyen"
    decision: Literal["auto_ok", "validation_humaine", "rejeter", "non_comptable"] = "validation_humaine"
    referential_status: Literal[
        "found_exact",
        "found_fuzzy",
        "missing_candidate",
        "unknown",
        "non_comptable",
    ] = "unknown"
    evidence_status: Literal["complete", "partial", "missing"] = "missing"
    reason: str = ""
    can_auto_post: bool = False
    requires_human_validation: bool = True


class AccountingProposalSummary(BaseModel):
    total_lines: int = 0
    auto_ok: int = 0
    validation_humaine: int = 0
    rejected: int = 0
    non_comptable: int = 0
    average_confidence: float = 0.0


class AccountingProposal(BaseModel):
    invoice_id: str | None = None
    invoice_number: str | None = None
    supplier: str | None = None
    client: str | None = None
    proposal_status: Literal["auto_ok", "validation_required", "rejected", "partial"] = "partial"
    summary: AccountingProposalSummary = Field(default_factory=AccountingProposalSummary)
    lines: list[AccountingProposalLine] = Field(default_factory=list)


class RandomInvoiceListItem(BaseModel):
    invoice_id: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total_ttc: float | None = None
    supplier: str | None = None
    client: str | None = None
    client_ape: str | None = None
    supplier_ape: str | None = None
    line_items_count: int = 0
    exploitable_lines_count: int = 0
    status: Literal["prete_a_analyser", "sans_lignes_exploitables"] = "prete_a_analyser"


class RandomInvoicesResponse(BaseModel):
    items: list[RandomInvoiceListItem] = Field(default_factory=list)


class AnalysisBatchJob(BaseModel):
    job_id: str
    database: str
    status: Literal["queued", "running", "stopping", "stopped", "completed", "failed", "already_running"] = "queued"
    limit: int = 0
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    processed: int = 0
    success: int = 0
    failed: int = 0
    sampled_count: int = 0
    current_invoice_id: str = ""
    current_invoice_label: str = ""
    duration_ms: int = 0
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
    selection_strategy: str = "unprocessed_first"
    sort_strategy: Literal["DUE_DATE", "CHRONO", "SUPPLIER", "AMOUNT"] = "DUE_DATE"
    already_analyzed_count: int = 0
    candidates_found: int = 0
    selected_count: int = 0
    saved_count: int = 0
    pending_save_count: int = 0
    last_saved_at: str = ""
    result_count: int = 0
    results: list["AnalysisBatchResultItem"] = Field(default_factory=list)


class AnalysisBatchResultItem(BaseModel):
    result_id: str
    job_id: str
    invoice_id: str
    database: str
    status: Literal["completed", "failed"] = "completed"
    analysis_status: str = "success"
    workflow_status: str = "A_CONTROLER"
    created_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    invoice_number: str = ""
    invoice_date: str = ""
    supplier: str = ""
    client: str = ""
    client_ape: str = ""
    supplier_ape: str = ""
    line_items_count: int = 0
    exploitable_lines_count: int = 0
    total_lines: int = 0
    auto_ok: int = 0
    validation_humaine: int = 0
    rejeter: int = 0
    non_comptable: int = 0
    unknown: int = 0
    articles_absents_referentiel: int = 0
    average_confidence: float = 0.0
    proposal_status: str = "partial"
    auto_ok_lines: int = 0
    human_validation_lines: int = 0
    rejected_lines: int = 0
    pdf_status: Literal[
        "available",
        "missing_file",
        "no_path",
        "inaccessible",
        "unknown",
    ] = "unknown"
    pdf_message: str = ""
    error_message: str = ""
    invoice_label: str = ""
    analyzed_at: str = ""
    analysis_payload: dict | None = None
    persisted: bool = False


class AnalysisBatchResultsResponse(BaseModel):
    database: str
    job_id: str | None = None
    count: int = 0
    items: list[AnalysisBatchResultItem] = Field(default_factory=list)


class ControlQueueCounts(BaseModel):
    all: int = 0
    to_control: int = 0
    new_articles: int = 0
    low_risk: int = 0
    not_analyzed: int = 0
    high_risk: int = 0


class ControlQueueSummary(BaseModel):
    auto_ok: int = 0
    validation_humaine: int = 0
    rejeter: int = 0
    non_comptable: int = 0
    missing_candidate: int = 0
    unknown: int = 0
    found_exact: int = 0
    found_fuzzy: int = 0
    average_confidence: float = 0.0


class ControlQueueItem(BaseModel):
    id: str
    supplier: str | None = None
    client: str | None = None
    date: str | None = None
    invoice_number: str | None = None
    line_count: int = 0
    exploitable_lines_count: int = 0
    client_ape: str | None = None
    supplier_ape: str | None = None
    analysis_status: str = "not_analyzed"
    queue_status: Literal[
        "to_control",
        "new_articles",
        "low_risk",
        "not_analyzed",
        "no_lines",
    ] = "not_analyzed"
    summary: ControlQueueSummary = Field(default_factory=ControlQueueSummary)
    badges: list[str] = Field(default_factory=list)
    ready: bool = False
    preview: str | None = None
    has_pdf: bool = False
    pdf_status: Literal[
        "available",
        "missing_file",
        "no_path",
        "inaccessible",
        "unknown",
    ] = "unknown"
    pdf_message: str | None = None


class ControlQueueResponse(BaseModel):
    items: list[ControlQueueItem] = Field(default_factory=list)
    counts: ControlQueueCounts = Field(default_factory=ControlQueueCounts)
    count: int = 0
    database: str | None = None
    clients_found: list[str] = Field(default_factory=list)
    pdf_available_count: int = 0
    pdf_missing_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int = 0

