from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InvoiceLineInput(BaseModel):
    article_source: str = Field(..., description="Libelle de ligne facture")
    metier_hint: str | None = Field(default=None, description="Indice metier si connu")
    tva_hint: float | None = Field(default=None, description="TVA de la ligne si connue")
    include_charges: bool = Field(
        default=True,
        description="Inclure les charges externes dans la recherche",
    )


class CandidateLine(BaseModel):
    base_cible: str
    metier: str
    article_source_match: str
    article_canonique: str
    categorie: str
    sous_categorie: str
    compte_comptable: str
    score_confiance: float
    raison_match: str
    tva_coherence: str
    metier_coherence: str
    decision: str
    alertes: list[str] = Field(default_factory=list)
    source_invoice_ids: list[str] = Field(default_factory=list)


class AccountingDecision(BaseModel):
    article_source: str
    categorie: str | None = None
    sous_categorie: str | None = None
    compte_comptable: str | None = None
    score_confiance: float = 0.0
    decision: Literal["auto_ok", "validation_humaine", "rejeter"] = "validation_humaine"
    explication: str
    candidats: list[CandidateLine] = Field(default_factory=list)


class HumanValidationInput(BaseModel):
    article_source: str = Field(..., description="Libelle valide humainement")
    metier_hint: str | None = Field(default=None, description="Metier de contexte")
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
    metier_hint: str | None = None
    tva_hint: float | None = None
    include_charges: bool = True
    categorie: str | None = None
    sous_categorie: str | None = None
    compte_comptable: str | None = None
    score_confiance: float = 0.0
    decision: Literal["auto_ok", "validation_humaine", "rejeter"] = "validation_humaine"
    explication: str
    source: Literal["engine", "memory"] = "engine"
    created_at: str


class AnalysisHistoryResponse(BaseModel):
    items: list[AnalysisHistoryRecord] = Field(default_factory=list)


class ValidationQueueResponse(BaseModel):
    items: list[AnalysisHistoryRecord] = Field(default_factory=list)


class FrontendAssistantInput(BaseModel):
    user_message: str = Field(..., description="Message libre saisi dans l'assistant frontend")
    article_source: str | None = Field(default=None, description="Libelle actuellement saisi")
    metier_hint: str | None = Field(default=None, description="Metier en contexte")
    tva_hint: float | None = Field(default=None, description="TVA en contexte")
    current_decision: AccountingDecision | None = Field(
        default=None,
        description="Derniere decision retournee par /recommend si disponible",
    )


class FrontendAssistantReply(BaseModel):
    answer: str
    suggested_action: Literal["analyser", "valider", "modifier", "rejeter", "neutre"] = "neutre"
