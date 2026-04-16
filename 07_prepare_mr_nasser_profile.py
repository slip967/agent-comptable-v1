#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
from datetime import datetime, UTC
from pathlib import Path


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser(description="Prepare validation profile from a_revoir references.")
    parser.add_argument(
        "--a-revoir-json",
        default="reference_base_a_revoir_v1.json",
        help="Input a_revoir reference JSON.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=200,
        help="Number of highest-frequency items to prepare.",
    )
    parser.add_argument("--profile-id", default="articles_validation_v1")
    parser.add_argument("--client-siren", default="519665103")
    parser.add_argument("--partition-prefix", default="fr_bd_519665103")
    parser.add_argument("--db-factures", default="abt3")
    parser.add_argument("--db-entries", default="fec_452416191")
    parser.add_argument("--out-json", default="profile_mr_nasser_articles_v1.json")
    parser.add_argument("--out-csv", default="profile_mr_nasser_articles_v1.csv")
    args = parser.parse_args()

    src = Path(args.a_revoir_json).resolve()
    data = json.loads(src.read_text(encoding="utf-8"))
    items = data.get("items", [])
    top = items[: max(0, args.top_n)]

    profile_items = []
    for idx, it in enumerate(top, 1):
        source_labels_top = it.get("source_labels_top") or []
        tva_rates_top = it.get("tva_rates_top") or []
        ape_supplier_top = it.get("ape_supplier_top") or []
        ape_client_top = it.get("ape_client_top") or []
        examples = it.get("examples") or []

        profile_items.append(
            {
                "item_id": f"mrn_{idx:04d}",
                "status": "to_validate",
                "source": {
                    "canonical_label": it.get("canonical_label"),
                    "source_label_main": source_labels_top[0][0] if source_labels_top else None,
                    "source_labels_top": source_labels_top,
                    "proposed_account": it.get("proposed_account"),
                    "category": it.get("category"),
                    "tva_rates_top": tva_rates_top,
                    "ape_supplier_top": ape_supplier_top,
                    "ape_client_top": ape_client_top,
                    "occurrences": it.get("occurrences", 0),
                    "examples": examples,
                },
                "validation": {
                    "decision_keep_or_exclude": None,
                    "corrected_category": None,
                    "corrected_account": None,
                    "corrected_canonical_label": None,
                    "tva_rule_note": None,
                    "comment": None,
                },
                "validated_at": None,
            }
        )

    profile_payload = {
        "meta": {
            "generated_at": now_iso(),
            "profile_id": args.profile_id,
            "client_siren": args.client_siren,
            "partition_prefix": args.partition_prefix,
            "db_factures": args.db_factures,
            "db_entries": args.db_entries,
            "source_file": str(src),
            "items_total": len(profile_items),
        },
        "items": profile_items,
    }

    out_json = Path(args.out_json).resolve()
    out_json.write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out_csv = Path(args.out_csv).resolve()
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "item_id",
                "occurrences",
                "canonical_label",
                "source_label_main",
                "proposed_account",
                "tva_main",
                "ape_supplier_main",
                "ape_client_main",
                "decision_keep_or_exclude",
                "corrected_category",
                "corrected_account",
                "corrected_canonical_label",
                "tva_rule_note",
                "comment",
            ]
        )
        for it in profile_items:
            src_row = it["source"]
            tva_main = (src_row.get("tva_rates_top") or [[None, 0]])[0][0]
            ape_supplier_main = (src_row.get("ape_supplier_top") or [[None, 0]])[0][0]
            ape_client_main = (src_row.get("ape_client_top") or [[None, 0]])[0][0]
            writer.writerow(
                [
                    it["item_id"],
                    src_row.get("occurrences", 0),
                    src_row.get("canonical_label") or "",
                    src_row.get("source_label_main") or "",
                    src_row.get("proposed_account") or "",
                    tva_main or "",
                    ape_supplier_main or "",
                    ape_client_main or "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    print(f"[OK] JSON profile: {out_json}")
    print(f"[OK] CSV queue: {out_csv}")


if __name__ == "__main__":
    main()
