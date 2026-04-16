#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def resolve_existing_path(*candidates: str) -> Path | None:
    for candidate in candidates:
        path = SCRIPT_DIR / candidate
        if path.exists():
            return path
    return None


def load_invoice_index(path: Path | None) -> dict[str, dict]:
    if not path or not path.exists():
        return {}

    index: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            invoice_id = (row.get("invoice_id") or "").strip()
            if invoice_id:
                index[invoice_id] = row
    return index


def top_counter_values(counter: Counter, limit: int = 5) -> list[list[object]]:
    return [[value, count] for value, count in counter.most_common(limit) if value]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_detailed_item(
    idx: int,
    item: dict,
    invoice_index: dict[str, dict],
) -> dict:
    source_invoice_ids = list(item.get("source_invoice_ids") or [])
    invoice_rows = [invoice_index.get(invoice_id, {}) for invoice_id in source_invoice_ids]

    issuer_names = Counter((row.get("issuer_name") or "").strip() for row in invoice_rows if row.get("issuer_name"))
    issuer_apes = Counter((row.get("issuer_ape") or "").strip() for row in invoice_rows if row.get("issuer_ape"))
    recipient_names = Counter((row.get("recipient_name") or "").strip() for row in invoice_rows if row.get("recipient_name"))
    recipient_apes = Counter((row.get("recipient_ape") or "").strip() for row in invoice_rows if row.get("recipient_ape"))

    source_invoices = []
    for invoice_id, row in zip(source_invoice_ids, invoice_rows):
        source_invoices.append(
            {
                "invoice_id": invoice_id,
                "invoice_number": row.get("invoice_number") or None,
                "invoice_date": row.get("invoice_date") or None,
                "issuer_name": row.get("issuer_name") or None,
                "issuer_siren": row.get("issuer_siren") or None,
                "issuer_ape": row.get("issuer_ape") or None,
                "recipient_name": row.get("recipient_name") or None,
                "recipient_siren": row.get("recipient_siren") or None,
                "recipient_ape": row.get("recipient_ape") or None,
            }
        )

    return {
        "item_id": f"cext_{idx:04d}",
        "status": "to_validate",
        "source": {
            "article_source": item.get("article_source"),
            "article_canonique": item.get("article_canonique"),
            "categorie": item.get("categorie"),
            "sous_categorie": item.get("sous_categorie"),
            "sous_profil": item.get("sous_profil"),
            "nature_charge": item.get("nature_charge"),
            "profil_facturation": item.get("profil_facturation"),
            "profil_facturation_champs": list(item.get("profil_facturation_champs") or []),
            "compte_comptable": item.get("compte_comptable"),
            "tva_rate": item.get("tva_rate"),
            "notes": item.get("notes"),
            "source_invoice_ids": source_invoice_ids,
            "issuer_names_top": top_counter_values(issuer_names, limit=5),
            "issuer_apes_top": top_counter_values(issuer_apes, limit=5),
            "recipient_names_top": top_counter_values(recipient_names, limit=5),
            "recipient_apes_top": top_counter_values(recipient_apes, limit=5),
            "source_invoices": source_invoices,
        },
        "validation": {
            "decision_keep_or_exclude": None,
            "corrected_sous_profil": None,
            "corrected_compte_comptable": None,
            "corrected_profil_facturation": None,
            "corrected_profil_facturation_champs": None,
            "splitting_rule_note": None,
            "comment": None,
        },
        "validated_at": None,
    }


def build_catalog(items: list[dict], invoice_index: dict[str, dict]) -> list[dict]:
    grouped: dict[str, dict] = {}

    for item in items:
        sous_profil = (item.get("sous_profil") or "").strip() or "autres_charges_externes"
        group = grouped.setdefault(
            sous_profil,
            {
                "sous_profil": sous_profil,
                "profil_facturation_counter": Counter(),
                "nature_charge_counter": Counter(),
                "comptes": Counter(),
                "sous_categories": Counter(),
                "articles": Counter(),
                "fournisseurs": Counter(),
                "apes_fournisseur": Counter(),
                "profil_facturation_champs": set(),
                "items_total": 0,
            },
        )

        group["items_total"] += 1
        group["profil_facturation_counter"][(item.get("profil_facturation") or "").strip()] += 1
        group["nature_charge_counter"][(item.get("nature_charge") or "").strip()] += 1
        group["comptes"][(item.get("compte_comptable") or "").strip()] += 1
        group["sous_categories"][(item.get("sous_categorie") or "").strip()] += 1
        group["articles"][(item.get("article_source") or "").strip()] += 1
        for field_name in item.get("profil_facturation_champs") or []:
            if field_name:
                group["profil_facturation_champs"].add(str(field_name))

        for invoice_id in item.get("source_invoice_ids") or []:
            row = invoice_index.get(invoice_id, {})
            issuer_name = (row.get("issuer_name") or "").strip()
            issuer_ape = (row.get("issuer_ape") or "").strip()
            if issuer_name:
                group["fournisseurs"][issuer_name] += 1
            if issuer_ape:
                group["apes_fournisseur"][issuer_ape] += 1

    catalog_items: list[dict] = []
    for sous_profil, group in sorted(grouped.items(), key=lambda entry: (-entry[1]["items_total"], entry[0])):
        catalog_items.append(
            {
                "sous_profil": sous_profil,
                "profil_facturation": group["profil_facturation_counter"].most_common(1)[0][0],
                "nature_charge_top": top_counter_values(group["nature_charge_counter"], limit=3),
                "comptes_comptables_top": top_counter_values(group["comptes"], limit=5),
                "sous_categories_top": top_counter_values(group["sous_categories"], limit=5),
                "profil_facturation_champs": sorted(group["profil_facturation_champs"]),
                "articles_exemples": [value for value, _count in group["articles"].most_common(5)],
                "fournisseurs_exemples": [value for value, _count in group["fournisseurs"].most_common(5)],
                "ape_fournisseur_top": top_counter_values(group["apes_fournisseur"], limit=5),
                "items_total": group["items_total"],
                "validation": {
                    "profil_actif": None,
                    "decision_keep_or_exclude": None,
                    "corrected_profil_facturation": None,
                    "corrected_profil_facturation_champs": None,
                    "comment": None,
                },
            }
        )
    return catalog_items


def build_detailed_csv_rows(profile_items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in profile_items:
        source = item["source"]
        validation = item["validation"]
        source_invoice_ids = source.get("source_invoice_ids") or []
        invoices = source.get("source_invoices") or []
        main_invoice = invoices[0] if invoices else {}

        rows.append(
            {
                "item_id": item["item_id"],
                "article_source": source.get("article_source") or "",
                "article_canonique": source.get("article_canonique") or "",
                "compte_comptable": source.get("compte_comptable") or "",
                "tva_rate": source.get("tva_rate") if source.get("tva_rate") is not None else "",
                "sous_categorie": source.get("sous_categorie") or "",
                "sous_profil": source.get("sous_profil") or "",
                "nature_charge": source.get("nature_charge") or "",
                "profil_facturation": source.get("profil_facturation") or "",
                "profil_facturation_champs": " | ".join(source.get("profil_facturation_champs") or []),
                "source_invoice_id_main": source_invoice_ids[0] if source_invoice_ids else "",
                "issuer_name_main": main_invoice.get("issuer_name") or "",
                "issuer_ape_main": main_invoice.get("issuer_ape") or "",
                "recipient_name_main": main_invoice.get("recipient_name") or "",
                "recipient_ape_main": main_invoice.get("recipient_ape") or "",
                "decision_keep_or_exclude": validation.get("decision_keep_or_exclude") or "",
                "corrected_sous_profil": validation.get("corrected_sous_profil") or "",
                "corrected_compte_comptable": validation.get("corrected_compte_comptable") or "",
                "corrected_profil_facturation": validation.get("corrected_profil_facturation") or "",
                "corrected_profil_facturation_champs": validation.get("corrected_profil_facturation_champs") or "",
                "splitting_rule_note": validation.get("splitting_rule_note") or "",
                "comment": validation.get("comment") or "",
            }
        )
    return rows


def build_catalog_csv_rows(catalog_items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in catalog_items:
        validation = item["validation"]
        rows.append(
            {
                "sous_profil": item["sous_profil"],
                "profil_facturation": item["profil_facturation"],
                "profil_facturation_champs": " | ".join(item.get("profil_facturation_champs") or []),
                "nature_charge_top": " | ".join(f"{value} ({count})" for value, count in item.get("nature_charge_top") or []),
                "comptes_comptables_top": " | ".join(f"{value} ({count})" for value, count in item.get("comptes_comptables_top") or []),
                "sous_categories_top": " | ".join(f"{value} ({count})" for value, count in item.get("sous_categories_top") or []),
                "fournisseurs_exemples": " | ".join(item.get("fournisseurs_exemples") or []),
                "ape_fournisseur_top": " | ".join(f"{value} ({count})" for value, count in item.get("ape_fournisseur_top") or []),
                "articles_exemples": " | ".join(item.get("articles_exemples") or []),
                "items_total": item.get("items_total") or 0,
                "profil_actif": validation.get("profil_actif") or "",
                "decision_keep_or_exclude": validation.get("decision_keep_or_exclude") or "",
                "corrected_profil_facturation": validation.get("corrected_profil_facturation") or "",
                "corrected_profil_facturation_champs": validation.get("corrected_profil_facturation_champs") or "",
                "comment": validation.get("comment") or "",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build external charges billing profile templates from base_charges_externes_v1.")
    parser.add_argument("--input-json", default="base_charges_externes_v1.json", help="Input base charges JSON.")
    parser.add_argument(
        "--invoice-csv",
        default="",
        help="Invoice export CSV with issuer/recipient/APE columns. Defaults to *_with_ape when available.",
    )
    parser.add_argument(
        "--out-detail-json",
        default="v1_519665103_profile_charges_externes_detail_v1.json",
        help="Detailed output JSON.",
    )
    parser.add_argument(
        "--out-detail-csv",
        default="v1_519665103_profile_charges_externes_detail_v1.csv",
        help="Detailed output CSV.",
    )
    parser.add_argument(
        "--out-catalog-json",
        default="v1_519665103_profile_charges_externes_sous_profils_v1.json",
        help="Catalog output JSON.",
    )
    parser.add_argument(
        "--out-catalog-csv",
        default="v1_519665103_profile_charges_externes_sous_profils_v1.csv",
        help="Catalog output CSV.",
    )
    args = parser.parse_args()

    input_path = (SCRIPT_DIR / args.input_json).resolve() if not Path(args.input_json).is_absolute() else Path(args.input_json).resolve()
    invoice_csv = None
    if args.invoice_csv:
        invoice_csv = (SCRIPT_DIR / args.invoice_csv).resolve() if not Path(args.invoice_csv).is_absolute() else Path(args.invoice_csv).resolve()
    else:
        invoice_csv = resolve_existing_path(
            "invoice_form_519665103_all_with_ape.csv",
            "invoice_form_519665103_all.csv",
        )

    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    if not items:
        raise SystemExit("No items found in base_charges_externes input.")

    invoice_index = load_invoice_index(invoice_csv)
    profile_items = [build_detailed_item(idx, item, invoice_index) for idx, item in enumerate(items, 1)]
    catalog_items = build_catalog(items, invoice_index)

    detail_payload = {
        "meta": {
            "generated_at": now_iso(),
            "profile_id": "charges_externes_detail_v1",
            "source_file": str(input_path),
            "invoice_csv": str(invoice_csv) if invoice_csv else None,
            "items_total": len(profile_items),
        },
        "items": profile_items,
    }
    catalog_payload = {
        "meta": {
            "generated_at": now_iso(),
            "profile_id": "charges_externes_sous_profils_v1",
            "source_file": str(input_path),
            "invoice_csv": str(invoice_csv) if invoice_csv else None,
            "items_total": len(catalog_items),
        },
        "items": catalog_items,
    }

    out_detail_json = (SCRIPT_DIR / args.out_detail_json).resolve() if not Path(args.out_detail_json).is_absolute() else Path(args.out_detail_json).resolve()
    out_detail_csv = (SCRIPT_DIR / args.out_detail_csv).resolve() if not Path(args.out_detail_csv).is_absolute() else Path(args.out_detail_csv).resolve()
    out_catalog_json = (SCRIPT_DIR / args.out_catalog_json).resolve() if not Path(args.out_catalog_json).is_absolute() else Path(args.out_catalog_json).resolve()
    out_catalog_csv = (SCRIPT_DIR / args.out_catalog_csv).resolve() if not Path(args.out_catalog_csv).is_absolute() else Path(args.out_catalog_csv).resolve()

    out_detail_json.write_text(json.dumps(detail_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_catalog_json.write_text(json.dumps(catalog_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    detail_rows = build_detailed_csv_rows(profile_items)
    catalog_rows = build_catalog_csv_rows(catalog_items)

    write_csv(
        out_detail_csv,
        [
            "item_id",
            "article_source",
            "article_canonique",
            "compte_comptable",
            "tva_rate",
            "sous_categorie",
            "sous_profil",
            "nature_charge",
            "profil_facturation",
            "profil_facturation_champs",
            "source_invoice_id_main",
            "issuer_name_main",
            "issuer_ape_main",
            "recipient_name_main",
            "recipient_ape_main",
            "decision_keep_or_exclude",
            "corrected_sous_profil",
            "corrected_compte_comptable",
            "corrected_profil_facturation",
            "corrected_profil_facturation_champs",
            "splitting_rule_note",
            "comment",
        ],
        detail_rows,
    )
    write_csv(
        out_catalog_csv,
        [
            "sous_profil",
            "profil_facturation",
            "profil_facturation_champs",
            "nature_charge_top",
            "comptes_comptables_top",
            "sous_categories_top",
            "fournisseurs_exemples",
            "ape_fournisseur_top",
            "articles_exemples",
            "items_total",
            "profil_actif",
            "decision_keep_or_exclude",
            "corrected_profil_facturation",
            "corrected_profil_facturation_champs",
            "comment",
        ],
        catalog_rows,
    )

    print(f"[OK] detail_json={out_detail_json}")
    print(f"[OK] detail_csv={out_detail_csv}")
    print(f"[OK] catalog_json={out_catalog_json}")
    print(f"[OK] catalog_csv={out_catalog_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
