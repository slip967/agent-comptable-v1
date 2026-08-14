from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from .config import PROJECT_DIR
from .loader import BASE_FILES, METIER_BY_FILE
from .schemas import KnowledgeBaseSummaryItem, KnowledgeBasesSummaryResponse


MATCHER_PATH = PROJECT_DIR / "10_match_reference_v1.py"

DISPLAY_LABELS = {
    "boulangerie": "Boulangerie",
    "boucherie": "Boucherie",
    "restaurant": "Restaurant",
    "btp": "BTP",
    "transport": "Transport",
    "epicerie": "Epicerie",
    "vtc": "VTC",
    "global": "Charges externes",
}


class LocalKnowledgeBaseStore:
    def __init__(self) -> None:
        self._module = None
        self._refs = None
        self._summary = None

    def _load_module(self):
        if self._module is not None:
            return self._module

        spec = importlib.util.spec_from_file_location("match_reference_v1", MATCHER_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Impossible de charger {MATCHER_PATH}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module = module
        return module

    def load_references(self):
        if self._refs is not None:
            return self._refs

        module = self._load_module()
        self._refs = module.load_references()
        return self._refs

    def match_line(
        self,
        *,
        article_source: str,
        fournisseur_hint: str | None = None,
        metier_hint: str | None = None,
        client_ape_hint: str | None = None,
        supplier_ape_hint: str | None = None,
        tva_hint: float | None = None,
        top_n: int = 3,
        include_charges: bool = True,
        supplier_account_stats: dict[str, dict[str, object]] | None = None,
        validation_pattern_stats: dict[str, dict[str, object]] | None = None,
    ) -> list[dict[str, Any]]:
        module = self._load_module()
        refs = self.load_references()
        return module.match_text(
            refs=refs,
            text=article_source,
            fournisseur_hint=fournisseur_hint,
            metier=metier_hint,
            client_ape_hint=client_ape_hint,
            supplier_ape_hint=supplier_ape_hint,
            top_n=top_n,
            tva_hint=tva_hint,
            include_charges=include_charges,
            supplier_account_stats=supplier_account_stats,
            validation_pattern_stats=validation_pattern_stats,
        )

    def get_summary(self) -> KnowledgeBasesSummaryResponse:
        if self._summary is not None:
            return self._summary

        root = PROJECT_DIR
        items: list[KnowledgeBaseSummaryItem] = []
        total_articles = 0

        for filename in BASE_FILES:
            path = root / filename
            if not path.exists():
                continue

            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = [item for item in payload.get("items", []) if isinstance(item, dict)]
            article_count = len(rows)
            total_articles += article_count

            with_invoice_sources = sum(1 for row in rows if row.get("source_invoice_ids"))
            with_partitions = sum(1 for row in rows if row.get("partitions_sources"))
            metier_key = METIER_BY_FILE.get(filename, "")
            readiness = (
                "pret"
                if article_count > 0
                and with_invoice_sources == article_count
                and with_partitions == article_count
                else "a_controler"
            )

            items.append(
                KnowledgeBaseSummaryItem(
                    key=metier_key,
                    label=DISPLAY_LABELS.get(metier_key, metier_key.title()),
                    file=filename,
                    articles=article_count,
                    with_invoice_sources=with_invoice_sources,
                    with_partitions=with_partitions,
                    readiness=readiness,
                )
            )

        self._summary = KnowledgeBasesSummaryResponse(
            total_bases=len(items),
            total_articles=total_articles,
            items=items,
        )
        return self._summary


local_knowledge_bases = LocalKnowledgeBaseStore()
