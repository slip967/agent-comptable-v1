#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_MD = ROOT / "restore_ape_context_v1_summary.md"
SUMMARY_JSON = ROOT / "restore_ape_context_v1_summary.json"

PREFERRED_ORDER = [
    "article_source",
    "article_canonique",
    "mots_cles",
    "source_invoice_ids",
    "ape_context",
    "partitions_sources",
    "compte_comptable",
    "taux_tva",
    "tva_rate",
    "categorie",
    "sous_categorie",
    "type_fournisseur",
    "fournisseur_type",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def list_target_files() -> list[Path]:
    targets: list[Path] = []
    for pattern in ["base_*_v1.json", "base_*_v1_with_accounts.json"]:
        for path in sorted(ROOT.glob(pattern)):
            if any(part in path.name for part in ["clean_v2", "corrected_v3"]):
                continue
            targets.append(path)
    return targets


def build_partition_to_ape() -> dict[str, str]:
    payload = load_json(QUALITY_REPORT)
    mapping: dict[str, str] = {}
    for row in payload.get("partitions", []):
        partition = str(row.get("partition_prefix") or "").strip()
        ape = str(row.get("client_ape") or "").strip()
        if partition and ape:
            mapping[partition] = ape
    return mapping


def reorder_item(item: dict) -> dict:
    ordered: dict = {}
    for key in PREFERRED_ORDER:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def process_file(path: Path, partition_to_ape: dict[str, str]) -> dict:
    payload = load_json(path)
    summary = {
        "file": path.name,
        "items_changed": 0,
        "a_valider_changed": 0,
        "ape_filled": 0,
        "examples": [],
    }

    for section in ["items", "a_valider"]:
        rows = payload.get(section) or []
        updated_rows = []
        for item in rows:
            if not isinstance(item, dict):
                updated_rows.append(item)
                continue

            before_ape = unique_strings(list(item.get("ape_context") or []))
            partitions = unique_strings(list(item.get("partitions_sources") or []))
            inferred_apes = unique_strings([partition_to_ape[p] for p in partitions if partition_to_ape.get(p)])

            new_item = dict(item)
            new_item["ape_context"] = inferred_apes
            new_item = reorder_item(new_item)

            if before_ape != inferred_apes:
                if section == "items":
                    summary["items_changed"] += 1
                else:
                    summary["a_valider_changed"] += 1
                if not before_ape and inferred_apes:
                    summary["ape_filled"] += 1
                if len(summary["examples"]) < 8:
                    summary["examples"].append(
                        {
                            "section": section,
                            "article_source": item.get("article_source"),
                            "before_ape": before_ape,
                            "after_ape": inferred_apes,
                            "partitions_sources": partitions,
                        }
                    )

            updated_rows.append(new_item)
        payload[section] = updated_rows

    payload.setdefault("meta", {})
    payload["meta"]["updated_at"] = now_iso()
    payload["meta"]["restore_ape_context_v1"] = {
        "applied_at": now_iso(),
        "rule": "ape_context derived from partitions_sources via quality report",
        "items_changed": summary["items_changed"],
        "a_valider_changed": summary["a_valider_changed"],
        "ape_filled": summary["ape_filled"],
    }
    dump_json(path, payload)
    return summary


def write_reports(file_summaries: list[dict]) -> None:
    payload = {
        "generated_at": now_iso(),
        "files": file_summaries,
    }
    SUMMARY_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Restore Ape Context V1",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        "",
    ]
    for row in file_summaries:
        lines.append(
            f"- {row['file']}: items_changed=`{row['items_changed']}` "
            f"a_valider_changed=`{row['a_valider_changed']}` ape_filled=`{row['ape_filled']}`"
        )
    lines.append("")
    lines.append("Exemples :")
    for row in file_summaries:
        for example in row["examples"][:3]:
            lines.append(
                f"- `{row['file']}` / `{example['article_source']}` -> "
                f"`ape_context={example['after_ape']}` depuis `{example['partitions_sources']}`"
            )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    partition_to_ape = build_partition_to_ape()
    file_summaries = [process_file(path, partition_to_ape) for path in list_target_files()]
    write_reports(file_summaries)
    print(json.dumps({"files": file_summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
