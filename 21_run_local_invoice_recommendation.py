#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import importlib.util
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_PATH = SCRIPT_DIR / "05_generated_entries.py"


def load_generator_module():
    spec = importlib.util.spec_from_file_location("generated_entries_module", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_local_generator(module):
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


def extract_ape(entity: dict | None) -> str | None:
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


def load_invoice(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and isinstance(payload.get("invoice"), dict):
        return payload["invoice"]
    if not isinstance(payload, dict):
        raise RuntimeError("Le fichier JSON doit contenir un objet facture.")
    return payload


def build_payload(
    invoice: dict,
    client_siren: str,
    client_ape: str | None,
    supplier_ape: str | None,
    external_accounts: list[dict] | None,
    external_details: dict | None,
    external_src: str | None,
    product_accounts: list[dict] | None,
    product_details: dict | None,
    product_src: str | None,
    merged_accounts: list[dict] | None,
    merged_details: dict | None,
    merged_src: str | None,
) -> dict:
    return {
        "meta": {
            "engine_file": str(GENERATOR_PATH),
            "invoice_id": str(invoice.get("_id") or "").strip(),
            "client_siren": client_siren,
            "client_ape": client_ape or "",
            "supplier_ape": supplier_ape or "",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local recommendation engine on one invoice JSON file."
    )
    parser.add_argument("--input-json", required=True, help="Invoice JSON file with line_items.")
    parser.add_argument("--client-siren", default="519665103", help="Client siren used for metier context.")
    parser.add_argument("--client-ape", default="", help="Optional client APE override.")
    parser.add_argument("--supplier-ape", default="", help="Optional supplier APE override.")
    parser.add_argument("--out-json", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    input_path = (SCRIPT_DIR / args.input_json).resolve() if not Path(args.input_json).is_absolute() else Path(args.input_json)
    invoice = load_invoice(input_path)

    client_siren = str(args.client_siren or "").strip() or "519665103"
    client_ape = str(args.client_ape or "").strip().upper() or None
    supplier_ape = str(args.supplier_ape or "").strip().upper() or None

    if not client_ape:
        client_ape = extract_ape(invoice.get("recipient") or {}) or str(invoice.get("km_ape") or "").strip().upper() or None
    if not supplier_ape:
        supplier_ape = extract_ape(invoice.get("issuer") or {}) or str(invoice.get("supplier_ape") or "").strip().upper() or None

    module = load_generator_module()
    generator = build_local_generator(module)

    external_accounts, external_details, external_src = generator._recommend_external_charge_accounts_from_invoice(  # noqa: SLF001
        invoice=invoice,
        supplier_ape=supplier_ape,
    )
    product_accounts, product_details, product_src = generator._recommend_product_metier_accounts_from_invoice(  # noqa: SLF001
        invoice=invoice,
        client_siren=client_siren,
        client_ape=client_ape,
    )
    merged_accounts, merged_details, merged_src = generator._merge_line_item_recommendations(  # noqa: SLF001
        external_accounts,
        external_details,
        external_src,
        product_accounts,
        product_details,
        product_src,
    )

    payload = build_payload(
        invoice=invoice,
        client_siren=client_siren,
        client_ape=client_ape,
        supplier_ape=supplier_ape,
        external_accounts=external_accounts,
        external_details=external_details,
        external_src=external_src,
        product_accounts=product_accounts,
        product_details=product_details,
        product_src=product_src,
        merged_accounts=merged_accounts,
        merged_details=merged_details,
        merged_src=merged_src,
    )

    out_path = Path(args.out_json) if args.out_json else input_path.with_name(input_path.stem + "_local_recommendation.json")
    if not out_path.is_absolute():
        out_path = (SCRIPT_DIR / out_path).resolve()
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] input={input_path}")
    print(f"[INFO] client_siren={client_siren}")
    print(f"[INFO] client_ape={client_ape or ''}")
    print(f"[INFO] supplier_ape={supplier_ape or ''}")
    print(f"[INFO] external_source={external_src or ''}")
    print(f"[INFO] product_source={product_src or ''}")
    print(f"[INFO] final_source={merged_src or ''}")
    print(f"[OK] json={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
