#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE_FILE = ROOT / "base_produits_btp_v1.json"
OUT_JSON = ROOT / "btp_articles_sans_ids_factures_report.json"
OUT_CSV = ROOT / "btp_articles_sans_ids_factures_report.csv"
OUT_MD = ROOT / "btp_articles_sans_ids_factures_report.md"


def load_helper(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {file_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genere un rapport des articles BTP sans ids_factures_sources, avec quasi-matchs faibles pour revue manuelle."
    )
    parser.add_argument("--db-factures", default="abt3")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    fuzzy = load_helper("btp_fuzzy", "82_restore_btp_fuzzy_sources.py")
    payload = load_json(BASE_FILE)
    items = payload.get("items") or []

    session = fuzzy.http_session()
    all_partitions, partition_to_ape, ape_to_partitions = fuzzy.build_btp_partitions()
    partition_buckets = {
        partition: fuzzy.build_label_bucket_index(session, args.db_factures, partition)
        for partition in all_partitions
    }

    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        existing_ids = fuzzy.unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
        if existing_ids:
            continue

        article_source = str(item.get("article_source") or "").strip()
        article_canonique = str(item.get("article_canonique") or "").strip()
        item_norm = fuzzy.normalize_text(article_source or article_canonique)
        item_tokens = fuzzy.semantic_tokens(article_source or article_canonique)
        partitions_sources = fuzzy.unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
        contexte_ape = fuzzy.unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))

        search_partitions = partitions_sources[:]
        if not search_partitions and contexte_ape:
            for ape in contexte_ape:
                search_partitions.extend(ape_to_partitions.get(ape, []))
        search_partitions = fuzzy.unique_strings(search_partitions or all_partitions)

        candidates = []
        for partition in search_partitions:
            for bucket in partition_buckets.get(partition, []):
                overlap = sorted(set(item_tokens) & set(bucket["tokens"]))
                if not overlap:
                    continue
                score, details = fuzzy.score_match(item_tokens, item_norm, bucket)
                candidates.append(
                    {
                        "partition": partition,
                        "ape": partition_to_ape.get(partition, ""),
                        "label": bucket["label"],
                        "invoice_ids": bucket["invoice_ids"][:3],
                        "score": round(score, 4),
                        "overlap": overlap,
                        "coverage_item": round(details.get("coverage_item", 0.0), 4),
                        "coverage_candidate": round(details.get("coverage_candidate", 0.0), 4),
                    }
                )

        candidates.sort(
            key=lambda row: (
                -row["score"],
                -len(row["overlap"]),
                -row["coverage_item"],
                row["label"],
            )
        )

        record = {
            "article_source": article_source,
            "article_canonique": article_canonique,
            "mots_cles": item.get("mots_cles") or [],
            "compte_comptable": item.get("compte_comptable"),
            "taux_tva": item.get("taux_tva"),
            "categorie": item.get("categorie"),
            "sous_categorie": item.get("sous_categorie"),
            "type_fournisseur": item.get("type_fournisseur") or item.get("fournisseur_type"),
            "partitions_sources": partitions_sources,
            "contexte_ape": contexte_ape,
            "quasi_matchs": candidates[: max(1, int(args.top_k))],
        }
        records.append(record)

    summary = {
        "generated_at": fuzzy.now_iso(),
        "source_db_factures": args.db_factures,
        "base_file": BASE_FILE.name,
        "total_items": len(items),
        "missing_source_invoice_ids": len(records),
        "records": records,
    }

    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "article_source",
                "article_canonique",
                "mots_cles",
                "compte_comptable",
                "taux_tva",
                "categorie",
                "sous_categorie",
                "type_fournisseur",
                "partitions_sources",
                "contexte_ape",
                "quasi_match_1_label",
                "quasi_match_1_partition",
                "quasi_match_1_ape",
                "quasi_match_1_score",
                "quasi_match_1_overlap",
                "quasi_match_1_invoice_ids",
                "quasi_match_2_label",
                "quasi_match_2_partition",
                "quasi_match_2_ape",
                "quasi_match_2_score",
                "quasi_match_2_overlap",
                "quasi_match_2_invoice_ids",
            ],
        )
        writer.writeheader()
        for row in records:
            match1 = row["quasi_matchs"][0] if len(row["quasi_matchs"]) > 0 else {}
            match2 = row["quasi_matchs"][1] if len(row["quasi_matchs"]) > 1 else {}
            writer.writerow(
                {
                    "article_source": row["article_source"],
                    "article_canonique": row["article_canonique"],
                    "mots_cles": " | ".join(row["mots_cles"]),
                    "compte_comptable": row["compte_comptable"],
                    "taux_tva": row["taux_tva"],
                    "categorie": row["categorie"],
                    "sous_categorie": row["sous_categorie"],
                    "type_fournisseur": row["type_fournisseur"],
                    "partitions_sources": " | ".join(row["partitions_sources"]),
                    "contexte_ape": " | ".join(row["contexte_ape"]),
                    "quasi_match_1_label": match1.get("label", ""),
                    "quasi_match_1_partition": match1.get("partition", ""),
                    "quasi_match_1_ape": match1.get("ape", ""),
                    "quasi_match_1_score": match1.get("score", ""),
                    "quasi_match_1_overlap": " | ".join(match1.get("overlap", [])),
                    "quasi_match_1_invoice_ids": " | ".join(match1.get("invoice_ids", [])),
                    "quasi_match_2_label": match2.get("label", ""),
                    "quasi_match_2_partition": match2.get("partition", ""),
                    "quasi_match_2_ape": match2.get("ape", ""),
                    "quasi_match_2_score": match2.get("score", ""),
                    "quasi_match_2_overlap": " | ".join(match2.get("overlap", [])),
                    "quasi_match_2_invoice_ids": " | ".join(match2.get("invoice_ids", [])),
                }
            )

    lines = [
        "# BTP Sans IDs Factures Sources",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- source_db_factures: `{summary['source_db_factures']}`",
        f"- base_file: `{summary['base_file']}`",
        f"- missing_source_invoice_ids: `{summary['missing_source_invoice_ids']}`",
        "",
    ]
    for row in records[:30]:
        lines.append(f"## {row['article_source']}")
        lines.append(f"- article_canonique: `{row['article_canonique']}`")
        lines.append(f"- mots_cles: `{row['mots_cles']}`")
        lines.append(f"- compte_comptable: `{row['compte_comptable']}`")
        lines.append(f"- taux_tva: `{row['taux_tva']}`")
        lines.append(f"- categorie: `{row['categorie']}`")
        lines.append(f"- sous_categorie: `{row['sous_categorie']}`")
        lines.append(f"- type_fournisseur: `{row['type_fournisseur']}`")
        lines.append(f"- partitions_sources: `{row['partitions_sources']}`")
        lines.append(f"- contexte_ape: `{row['contexte_ape']}`")
        if row["quasi_matchs"]:
            lines.append("- quasi_matchs:")
            for match in row["quasi_matchs"][: max(1, int(args.top_k))]:
                lines.append(
                    f"  - `{match['label']}` partition=`{match['partition']}` ape=`{match['ape']}` "
                    f"score=`{match['score']}` overlap=`{match['overlap']}`"
                )
        else:
            lines.append("- quasi_matchs: `[]`")
        lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"missing_source_invoice_ids": len(records), "json": OUT_JSON.name, "csv": OUT_CSV.name, "md": OUT_MD.name}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
