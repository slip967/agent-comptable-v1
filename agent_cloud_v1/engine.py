from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GENERATOR_PATH = PROJECT_DIR / "05_generated_entries.py"


def extract_ape(entity: Optional[dict]) -> Optional[str]:
    if not entity:
        return None
    value = entity.get("ape")
    if value:
        return str(value).strip().upper()
    for reg in entity.get("company_registrations") or []:
        if str(reg.get("type") or "").strip().upper() == "APE":
            raw = reg.get("value")
            if raw:
                return str(raw).strip().upper()
    return None


class RecommendationEngine:
    def __init__(self) -> None:
        self._module = None
        self._generator = None

    def _load_generator_module(self):
        if self._module is not None:
            return self._module
        spec = importlib.util.spec_from_file_location("generated_entries_module", GENERATOR_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Impossible de charger {GENERATOR_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module = module
        return module

    def _build_local_generator(self):
        module = self._load_generator_module()
        obj = module.AccountingEntryGenerator.__new__(module.AccountingEntryGenerator)
        obj.verbose = False
        obj._external_charge_matcher_module = None
        obj._external_charge_refs = None
        obj._product_metier_refs = None
        obj._external_charge_matcher_error = None
        obj._scope_metier_by_client = None
        obj.stats = {
            "charge_source_external_charge_auto": 0,
            "charge_source_external_charge_validation": 0,
            "charge_source_product_metier_auto": 0,
            "charge_source_product_metier_validation": 0,
            "charge_source_line_item_mixed_auto": 0,
            "charge_source_line_item_mixed_validation": 0,
        }
        obj._log = lambda *args, **kwargs: None
        return obj

    def _get_generator(self):
        if self._generator is None:
            self._generator = self._build_local_generator()
        return self._generator

    def _normalize_invoice(self, payload: dict) -> dict:
        if isinstance(payload.get("invoice"), dict):
            return payload["invoice"]
        return payload

    def recommend(
        self,
        invoice_payload: dict[str, Any],
        client_siren: str = "519665103",
        client_ape: Optional[str] = None,
        supplier_ape: Optional[str] = None,
    ) -> dict[str, Any]:
        invoice = self._normalize_invoice(invoice_payload)
        if not isinstance(invoice, dict):
            raise ValueError("Le payload facture doit etre un objet JSON.")

        normalized_client_siren = str(client_siren or "").strip() or "519665103"
        normalized_client_ape = (client_ape or "").strip().upper() or None
        normalized_supplier_ape = (supplier_ape or "").strip().upper() or None

        if not normalized_client_ape:
            normalized_client_ape = (
                extract_ape(invoice.get("recipient") or {})
                or str(invoice.get("km_ape") or "").strip().upper()
                or None
            )
        if not normalized_supplier_ape:
            normalized_supplier_ape = (
                extract_ape(invoice.get("issuer") or {})
                or str(invoice.get("supplier_ape") or "").strip().upper()
                or None
            )

        generator = self._get_generator()

        external_accounts, external_details, external_src = generator._recommend_external_charge_accounts_from_invoice(  # noqa: SLF001
            invoice=invoice,
            supplier_ape=normalized_supplier_ape,
        )
        product_accounts, product_details, product_src = generator._recommend_product_metier_accounts_from_invoice(  # noqa: SLF001
            invoice=invoice,
            client_siren=normalized_client_siren,
            client_ape=normalized_client_ape,
        )
        merged_accounts, merged_details, merged_src = generator._merge_line_item_recommendations(  # noqa: SLF001
            external_accounts,
            external_details,
            external_src,
            product_accounts,
            product_details,
            product_src,
        )

        return {
            "meta": {
                "engine_file": str(GENERATOR_PATH),
                "invoice_id": str(invoice.get("_id") or "").strip(),
                "client_siren": normalized_client_siren,
                "client_ape": normalized_client_ape or "",
                "supplier_ape": normalized_supplier_ape or "",
                "line_items_count": len(invoice.get("line_items") or []),
            },
            "external_charge_recommendation": {
                "source": external_src,
                "accounts": external_accounts or [],
                "details": external_details or {},
            },
            "product_metier_recommendation": {
                "source": product_src,
                "accounts": product_accounts or [],
                "details": product_details or {},
            },
            "final_line_item_recommendation": {
                "source": merged_src,
                "accounts": merged_accounts or [],
                "details": merged_details or {},
            },
        }
