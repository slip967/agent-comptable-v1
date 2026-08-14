from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .account_labels import get_account_label
from .config import PROJECT_DIR
from .loader import get_reference_load_status, load_all_bases


MATCHER_PATH = PROJECT_DIR / "10_match_reference_v1.py"


class MatcherTool:
    def __init__(self) -> None:
        self._module = None
        self._refs = None
        self._reference_source = "uninitialized"
        self._reference_error = ""

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

    @property
    def reference_source(self) -> str:
        return self._reference_source

    @property
    def reference_error(self) -> str:
        return self._reference_error

    def _build_reference_items(self, rows: list[dict[str, Any]]):
        module = self._load_module()
        refs = []
        for row in rows:
            refs.append(
                module.ReferenceItem(
                    base_file=str(row.get("base_file") or "").strip(),
                    metier=str(row.get("metier") or "").strip(),
                    article_source=str(row.get("article_source") or "").strip(),
                    article_canonique=str(row.get("article_canonique") or "").strip(),
                    categorie=str(row.get("categorie") or "").strip(),
                    sous_categorie=str(row.get("sous_categorie") or "").strip(),
                    compte_comptable=str(row.get("compte_comptable") or "").strip(),
                    compte_comptable_libelle=str(
                        row.get("compte_comptable_libelle")
                        or row.get("account_label")
                        or get_account_label(row.get("compte_comptable"))
                        or ""
                    ).strip(),
                    tva_rate=row.get("tva_rate"),
                    mots_cles=list(row.get("mots_cles") or []),
                    ape_context=list(row.get("ape_context") or []),
                    source_invoice_ids=list(row.get("source_invoice_ids") or []),
                    ids_factures_sources=list(row.get("ids_factures_sources") or row.get("source_invoice_ids") or []),
                    invoice_paths_sources=list(row.get("invoice_paths_sources") or []),
                    partitions_sources=list(row.get("partitions_sources") or []),
                    type_fournisseur=str(row.get("type_fournisseur") or "").strip(),
                    sous_profil=str(row.get("sous_profil") or "").strip(),
                    nature_charge=str(row.get("nature_charge") or "").strip(),
                    profil_facturation=str(row.get("profil_facturation") or "").strip(),
                )
            )
        return refs

    def load_references(self):
        if self._refs is not None:
            return self._refs
        try:
            rows = load_all_bases()
            self._refs = self._build_reference_items(rows)
            self._reference_source, self._reference_error = get_reference_load_status()
        except Exception as exc:
            module = self._load_module()
            self._refs = module.load_references()
            self._reference_source = "local_json:fallback"
            self._reference_error = str(exc)
            print(
                f"[WARN] Construction des references via le loader unifiee impossible ({exc}). "
                "Fallback sur le chargeur local du matcher."
            )
        return self._refs

    def match_line(
        self,
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


matcher_tool = MatcherTool()
