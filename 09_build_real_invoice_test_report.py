#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
from collections import Counter
from pathlib import Path


BASE_FILES = [
    "base_produits_boulangerie_v1.json",
    "base_produits_boucherie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_vtc_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_transport_v1.json",
    "base_charges_externes_v1.json",
]

INVOICE_CSV = "invoice_form_519665103_all.csv"
OUT_CSV = "tests_factures_reelles_v1.csv"
OUT_MD = "tests_factures_reelles_v1.md"


def load_invoice_index(path: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            invoice_id = (row.get("invoice_id") or "").strip()
            if invoice_id:
                index[invoice_id] = row
    return index


def safe_json_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    root = Path(".").resolve()
    invoice_index = load_invoice_index(root / INVOICE_CSV)

    rows: list[dict] = []
    summary: list[dict] = []

    for name in BASE_FILES:
        path = root / name
        if not path.exists():
            continue

        data = safe_json_load(path)
        meta = data.get("meta") or {}
        items = data.get("items") or []
        metier = meta.get("metier") or ""
        profile_id = meta.get("profile_id") or ""

        status_counter = Counter()

        for item in items:
            source_ids = list(item.get("source_invoice_ids") or [])[:3]
            test_status = "source_ok" if source_ids else "a_revoir"
            status_counter[test_status] += 1

            invoice_rows = [invoice_index.get(inv_id, {}) for inv_id in source_ids]
            while len(invoice_rows) < 3:
                invoice_rows.append({})

            rows.append(
                {
                    "base_file": name,
                    "profile_id": profile_id,
                    "metier": metier,
                    "article_source": item.get("article_source") or "",
                    "article_canonique": item.get("article_canonique") or "",
                    "categorie": item.get("categorie") or "",
                    "sous_categorie": item.get("sous_categorie") or "",
                    "tva_rate": item.get("tva_rate"),
                    "test_status": test_status,
                    "source_invoice_id_1": source_ids[0] if len(source_ids) > 0 else "",
                    "source_invoice_date_1": invoice_rows[0].get("invoice_date") or "",
                    "source_invoice_number_1": invoice_rows[0].get("invoice_number") or "",
                    "source_issuer_1": invoice_rows[0].get("issuer_name") or "",
                    "source_recipient_1": invoice_rows[0].get("recipient_name") or "",
                    "source_invoice_id_2": source_ids[1] if len(source_ids) > 1 else "",
                    "source_invoice_date_2": invoice_rows[1].get("invoice_date") or "",
                    "source_invoice_number_2": invoice_rows[1].get("invoice_number") or "",
                    "source_issuer_2": invoice_rows[1].get("issuer_name") or "",
                    "source_recipient_2": invoice_rows[1].get("recipient_name") or "",
                    "source_invoice_id_3": source_ids[2] if len(source_ids) > 2 else "",
                    "source_invoice_date_3": invoice_rows[2].get("invoice_date") or "",
                    "source_invoice_number_3": invoice_rows[2].get("invoice_number") or "",
                    "source_issuer_3": invoice_rows[2].get("issuer_name") or "",
                    "source_recipient_3": invoice_rows[2].get("recipient_name") or "",
                    "notes": item.get("notes") or "",
                }
            )

        summary.append(
            {
                "base_file": name,
                "metier": metier,
                "items_total": len(items),
                "source_ok": status_counter["source_ok"],
                "a_revoir": status_counter["a_revoir"],
            }
        )

    rows.sort(key=lambda r: (r["metier"], r["article_source"]))
    summary.sort(key=lambda r: (r["metier"], r["base_file"]))

    out_csv = root / OUT_CSV
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    out_md = root / OUT_MD
    lines = [
        "# Tests Sur Factures Reelles V1",
        "",
        "Ce rapport verifie, pour chaque article des bases V1, la presence de jusqu'a 3 `invoice_id` source.",
        "",
        "| Base | Metier | Items | Sources OK | A revoir |",
        "|---|---|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['base_file']} | {row['metier']} | {row['items_total']} | {row['source_ok']} | {row['a_revoir']} |"
        )

    lines.extend(
        [
            "",
            "## Lecture",
            "",
            "- `source_ok` : l'article a au moins un `source_invoice_id` rattache a une facture reelle.",
            "- `a_revoir` : l'article n'a pas encore de source facture fiable.",
            f"- Detail complet : `{OUT_CSV}`",
        ]
    )

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[OK] csv={out_csv}")
    print(f"[OK] md={out_md}")


if __name__ == "__main__":
    main()
