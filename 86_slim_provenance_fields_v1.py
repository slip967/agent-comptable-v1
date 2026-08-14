#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SUMMARY_MD = ROOT / "slim_provenance_fields_v1_summary.md"
SUMMARY_JSON = ROOT / "slim_provenance_fields_v1_summary.json"

PREFERRED_ORDER = [
    "article_source",
    "article_canonique",
    "mots_cles",
    "source_invoice_ids",
    "partitions_sources",
    "compte_comptable",
    "taux_tva",
    "tva_rate",
    "categorie",
    "sous_categorie",
    "type_fournisseur",
    "fournisseur_type",
]

REMOVED_KEYS = [
    "ids_factures_sources",
    "contexte_ape",
    "ape_context",
    "source_partition_ids",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_target_files() -> list[Path]:
    targets: list[Path] = []
    for path in sorted(ROOT.glob("base_*_v1.json")):
        if any(part in path.name for part in ["clean_v2", "corrected_v3"]):
            continue
        targets.append(path)
    for path in sorted(ROOT.glob("base_*_v1_with_accounts.json")):
        targets.append(path)
    return targets


def slim_item(item: dict) -> tuple[dict, dict]:
    source_invoice_ids = unique_strings(
        list(item.get("source_invoice_ids") or item.get("ids_factures_sources") or [])
    )[:3]
    if source_invoice_ids:
        partitions_sources = unique_strings(
            [invoice_id.split(":", 1)[0] for invoice_id in source_invoice_ids if ":" in invoice_id]
        )
    else:
        partitions_sources = unique_strings(
            list(item.get("partitions_sources") or item.get("source_partition_ids") or [])
        )

    new_item: dict = {}
    for key in PREFERRED_ORDER:
        if key == "source_invoice_ids":
            new_item[key] = source_invoice_ids
        elif key == "partitions_sources":
            new_item[key] = partitions_sources
        elif key in item:
            new_item[key] = item[key]

    for key, value in item.items():
        if key in new_item or key in REMOVED_KEYS:
            continue
        new_item[key] = value

    removed = [key for key in REMOVED_KEYS if key in item]
    return new_item, {
        "removed_keys": removed,
        "source_invoice_ids_count": len(source_invoice_ids),
        "partitions_sources_count": len(partitions_sources),
    }


def process_file(path: Path) -> dict:
    payload = load_json(path)
    summary = {
        "file": path.name,
        "items_changed": 0,
        "a_valider_changed": 0,
        "removed_key_counts": {key: 0 for key in REMOVED_KEYS},
        "examples": [],
    }

    for section in ["items", "a_valider"]:
        rows = payload.get(section) or []
        updated_rows = []
        for item in rows:
            if not isinstance(item, dict):
                updated_rows.append(item)
                continue
            before = json.dumps(item, ensure_ascii=False, sort_keys=True)
            new_item, stats = slim_item(item)
            after = json.dumps(new_item, ensure_ascii=False, sort_keys=True)
            if before != after:
                if section == "items":
                    summary["items_changed"] += 1
                else:
                    summary["a_valider_changed"] += 1
                for key in stats["removed_keys"]:
                    summary["removed_key_counts"][key] += 1
                if len(summary["examples"]) < 8:
                    summary["examples"].append(
                        {
                            "section": section,
                            "article_source": item.get("article_source"),
                            "source_invoice_ids": new_item.get("source_invoice_ids", []),
                            "partitions_sources": new_item.get("partitions_sources", []),
                        }
                    )
            updated_rows.append(new_item)
        payload[section] = updated_rows

    payload.setdefault("meta", {})
    payload["meta"]["updated_at"] = now_iso()
    payload["meta"]["provenance_slim_v2"] = {
        "applied_at": now_iso(),
        "kept_fields": ["source_invoice_ids", "partitions_sources"],
        "removed_fields": REMOVED_KEYS,
        "items_changed": summary["items_changed"],
        "a_valider_changed": summary["a_valider_changed"],
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
        "# Slim Provenance Fields V1",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        "",
    ]
    for row in file_summaries:
        lines.append(
            f"- {row['file']}: items_changed=`{row['items_changed']}` "
            f"a_valider_changed=`{row['a_valider_changed']}` "
            f"removed_key_counts=`{row['removed_key_counts']}`"
        )
    lines.append("")
    lines.append("Exemples :")
    for row in file_summaries:
        for example in row["examples"][:3]:
            lines.append(
                f"- `{row['file']}` / `{example['article_source']}` -> "
                f"`source_invoice_ids={example['source_invoice_ids']}` "
                f"`partitions_sources={example['partitions_sources']}`"
            )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    summaries = [process_file(path) for path in list_target_files()]
    write_reports(summaries)
    print(json.dumps({"files": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
