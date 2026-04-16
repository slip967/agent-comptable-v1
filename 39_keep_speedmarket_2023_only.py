#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SPEEDMARKET_SIREN = "831962394"
SPEEDMARKET_PREFIX = f"fr_bd_{SPEEDMARKET_SIREN}:"
ALLOWED_YEAR = "2023"

TARGET_FILES = [
    "base_produits_epicerie_v1.json",
    "base_produits_epicerie_v1_with_accounts.json",
]

REFERENCE_FILE = "v1_831962394_reference_base_exploitation_v1.json"


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_year(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) >= 10 and raw[2] == "/" and raw[5] == "/":
        return raw[6:10]
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:4]
    return ""


def build_invoice_year_map(path: Path) -> dict[str, set[str]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    id_years: dict[str, set[str]] = defaultdict(set)
    for item in data.get("items") or []:
        for ex in item.get("examples") or []:
            invoice_id = str(ex.get("invoice_id") or "").strip()
            if not invoice_id.startswith(SPEEDMARKET_PREFIX):
                continue
            year = parse_year(str(ex.get("invoice_date") or ""))
            if year:
                id_years[invoice_id].add(year)
    return id_years


def filter_bucket(rows: list[dict], id_years: dict[str, set[str]]):
    kept = []
    stats = {
        "rows_with_speedmarket": 0,
        "rows_removed": 0,
        "rows_kept_with_speedmarket_2023": 0,
        "speedmarket_ids_removed": 0,
    }

    for row in rows:
        if not isinstance(row, dict):
            kept.append(row)
            continue

        source_ids = [str(v).strip() for v in (row.get("source_invoice_ids") or []) if str(v).strip()]
        speed_ids = [x for x in source_ids if x.startswith(SPEEDMARKET_PREFIX)]
        if not speed_ids:
            kept.append(row)
            continue

        stats["rows_with_speedmarket"] += 1

        keep_speed_ids = []
        for invoice_id in speed_ids:
            years = id_years.get(invoice_id, set())
            if ALLOWED_YEAR in years:
                keep_speed_ids.append(invoice_id)
            else:
                stats["speedmarket_ids_removed"] += 1

        other_ids = [x for x in source_ids if not x.startswith(SPEEDMARKET_PREFIX)]
        new_ids = other_ids + keep_speed_ids

        if not new_ids:
            stats["rows_removed"] += 1
            continue

        row["source_invoice_ids"] = new_ids
        if keep_speed_ids:
            stats["rows_kept_with_speedmarket_2023"] += 1
        kept.append(row)

    return kept, stats


def process_file(path: Path, id_years: dict[str, set[str]], apply: bool):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    a_valider = data.get("a_valider") or []

    if not isinstance(items, list):
        raise ValueError(f"Invalid items array in {path}")
    if not isinstance(a_valider, list):
        a_valider = []

    new_items, item_stats = filter_bucket(items, id_years)
    new_a_valider, val_stats = filter_bucket(a_valider, id_years)

    data["items"] = new_items
    data["a_valider"] = new_a_valider

    meta = data.get("meta") or {}
    meta["items_count"] = len(new_items)
    meta["speedmarket_2023_only_filter_v1"] = {
        "updated_at": now_iso(),
        "siren": SPEEDMARKET_SIREN,
        "allowed_year": ALLOWED_YEAR,
        "items_rows_with_speedmarket": item_stats["rows_with_speedmarket"],
        "items_rows_removed": item_stats["rows_removed"],
        "items_rows_kept_with_speedmarket_2023": item_stats["rows_kept_with_speedmarket_2023"],
        "items_speedmarket_ids_removed": item_stats["speedmarket_ids_removed"],
        "a_valider_rows_with_speedmarket": val_stats["rows_with_speedmarket"],
        "a_valider_rows_removed": val_stats["rows_removed"],
        "a_valider_rows_kept_with_speedmarket_2023": val_stats["rows_kept_with_speedmarket_2023"],
        "a_valider_speedmarket_ids_removed": val_stats["speedmarket_ids_removed"],
    }
    data["meta"] = meta

    if apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "items_removed": item_stats["rows_removed"],
        "items_kept_speed_2023": item_stats["rows_kept_with_speedmarket_2023"],
        "items_with_speed": item_stats["rows_with_speedmarket"],
        "items_count": len(new_items),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep only Speedmarket (831962394) source_invoice_ids from year 2023.")
    parser.add_argument("--apply", action="store_true", help="Write changes to files.")
    args = parser.parse_args()

    ref_path = (SCRIPT_DIR / REFERENCE_FILE).resolve()
    if not ref_path.exists():
        raise SystemExit(f"Reference file not found: {ref_path}")

    id_years = build_invoice_year_map(ref_path)
    print(f"[INFO] speedmarket_reference_invoice_ids={len(id_years)}")

    for file_name in TARGET_FILES:
        path = (SCRIPT_DIR / file_name).resolve()
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        stats = process_file(path, id_years, apply=args.apply)
        print(
            f"[INFO] file={path.name} items_with_speedmarket={stats['items_with_speed']} "
            f"items_removed={stats['items_removed']} items_kept_speed_2023={stats['items_kept_speed_2023']} "
            f"items_count={stats['items_count']}"
        )

    print(f"[INFO] mode={'apply' if args.apply else 'dry_run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
