from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


BASE_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_vtc_v1.json",
    "base_charges_externes_v1.json",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _dump_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        current = str(value).strip()
        if not current or current in seen:
            continue
        seen.add(current)
        cleaned.append(current)
    return cleaned


def _derive_partitions(source_invoice_ids: list[str]) -> list[str]:
    partitions: list[str] = []
    seen: set[str] = set()
    for source_id in source_invoice_ids:
        current = str(source_id).strip()
        if ":" not in current:
            continue
        partition = current.split(":", 1)[0].strip()
        if not partition or partition in seen:
            continue
        seen.add(partition)
        partitions.append(partition)
    return partitions


def normalize_file(path: Path) -> dict[str, int | str]:
    payload = _load_json(path)
    items = list(payload.get("items") or [])
    normalized_items: list[dict] = []
    removed_missing_provenance = 0
    partitions_recomputed = 0
    invoice_ids_normalized = 0

    for item in items:
        source_invoice_ids = _ordered_unique(
            list(item.get("source_invoice_ids") or item.get("ids_factures_sources") or [])
        )
        if not source_invoice_ids:
            removed_missing_provenance += 1
            continue

        derived_partitions = _derive_partitions(source_invoice_ids)
        if not derived_partitions:
            removed_missing_provenance += 1
            continue

        if item.get("source_invoice_ids") != source_invoice_ids:
            invoice_ids_normalized += 1
        if item.get("partitions_sources") != derived_partitions:
            partitions_recomputed += 1

        item["source_invoice_ids"] = source_invoice_ids
        item["partitions_sources"] = derived_partitions

        if "ids_factures_sources" in item:
            item["ids_factures_sources"] = list(source_invoice_ids)
        if "source_partition_ids" in item:
            item["source_partition_ids"] = list(derived_partitions)

        normalized_items.append(item)

    payload["items"] = normalized_items
    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(normalized_items)
    meta["updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta["strict_provenance_from_invoice_ids"] = {
        "applied_at": meta["updated"],
        "rule": "keep only items with source_invoice_ids; recompute partitions_sources exactly from invoice_form/entry source ids",
        "removed_missing_provenance": removed_missing_provenance,
        "partitions_recomputed": partitions_recomputed,
        "invoice_ids_normalized": invoice_ids_normalized,
    }

    _dump_json(path, payload)
    return {
        "file": path.name,
        "remaining_items": len(normalized_items),
        "removed_missing_provenance": removed_missing_provenance,
        "partitions_recomputed": partitions_recomputed,
        "invoice_ids_normalized": invoice_ids_normalized,
    }


def main() -> None:
    reports: list[dict[str, int | str]] = []
    for base_name in BASE_FILES:
        for suffix in ("", "_with_accounts"):
            target = Path(base_name.replace(".json", f"{suffix}.json"))
            if not target.exists():
                continue
            reports.append(normalize_file(target))

    summary_path = Path("strict_provenance_from_invoice_ids_summary.json")
    summary_path.write_text(
        json.dumps({"files": reports}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for report in reports:
        print(
            f"{report['file']}: remaining={report['remaining_items']} "
            f"removed={report['removed_missing_provenance']} "
            f"partitions_recomputed={report['partitions_recomputed']}"
        )


if __name__ == "__main__":
    main()
