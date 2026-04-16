from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .engine import RecommendationEngine


class RecommendRequest(BaseModel):
    invoice: dict[str, Any] = Field(
        ...,
        description="Facture JSON avec line_items ou payload contenant la cle invoice.",
    )
    client_siren: str = Field(default="519665103", description="SIREN client pour contexte metier.")
    client_ape: Optional[str] = Field(default=None, description="APE client (optionnel).")
    supplier_ape: Optional[str] = Field(default=None, description="APE fournisseur (optionnel).")


class RecommendResponse(BaseModel):
    ok: bool
    result: dict[str, Any]


app = FastAPI(
    title="Agent Comptable V1",
    description="API cloud pour recommendation comptable (moteur hybride script interne).",
    version="1.0.0",
)

ENGINE = RecommendationEngine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest) -> RecommendResponse:
    try:
        result = ENGINE.recommend(
            invoice_payload=payload.invoice,
            client_siren=payload.client_siren,
            client_ape=payload.client_ape,
            supplier_ape=payload.supplier_ape,
        )
        return RecommendResponse(ok=True, result=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur moteur: {exc}") from exc
