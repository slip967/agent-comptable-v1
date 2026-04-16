#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def detect_year(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4] == "-":
        return text[:4]
    if "/" in text and len(text) >= 10:
        return text[-4:]
    return ""


def build_invoice_year_index(root: Path) -> dict[str, str]:
    index: dict[str, str] = {}
    for name in ["invoice_form_519665103_all_with_ape.json", "invoice_form_519665103_all.json"]:
        path = root / name
        if not path.exists():
            continue
        data = read_json(path)
        rows = data if isinstance(data, list) else data.get("items", [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            invoice_id = str(row.get("invoice_id") or row.get("_id") or "").strip()
            if not invoice_id:
                continue
            date_value = row.get("invoice_date") or row.get("date_facture") or row.get("date")
            year = detect_year(str(date_value or ""))
            if year:
                index[invoice_id] = year
    return index


def iter_base_files(root: Path) -> list[Path]:
    return sorted(root.glob("base_*_v1*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep only source_invoice_ids from a target year in base JSON files.")
    parser.add_argument("--year", default="2024", help="Target year to keep (default: 2024).")
    parser.add_argument("--apply", action="store_true", help="Write changes to files.")
    args = parser.parse_args()

    year = str(args.year).strip()
    if not year.isdigit() or len(year) != 4:
        raise SystemExit("Invalid --year, expected YYYY.")

    invoice_year = build_invoice_year_index(SCRIPT_DIR)
    if not invoice_year:
        raise SystemExit("No invoice year index found. Missing invoice_form JSON sources.")

    totals = Counter()
    files_changed = 0

    for path in iter_base_files(SCRIPT_DIR):
        data = read_json(path)
        items = data.get("items") or []
        if not isinstance(items, list):
            continue

        before = 0
        after = 0
        dropped = 0
        unknown = 0
        file_changed = False

        for item in items:
            if not isinstance(item, dict):
                continue
            source_ids = [str(v).strip() for v in (item.get("source_invoice_ids") or []) if str(v).strip()]
            if not source_ids:
                continue
            before += len(source_ids)
            kept = []
            for invoice_id in source_ids:
                y = invoice_year.get(invoice_id, "")
                if not y:
                    unknown += 1
                    continue
                if y == year:
                    kept.append(invoice_id)
                else:
                    dropped += 1
            if kept != source_ids:
                item["source_invoice_ids"] = kept
                file_changed = True
            after += len(kept)

        if file_changed:
            meta = data.get("meta") or {}
            meta["source_invoice_year_filter"] = year
            data["meta"] = meta
            files_changed += 1
            if args.apply:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        totals["before"] += before
        totals["after"] += after
        totals["dropped"] += dropped
        totals["unknown"] += unknown
        print(
            "[INFO] file={file} changed={changed} before={before} after={after} dropped={dropped} unknown={unknown}".format(
                file=path.name,
                changed="yes" if file_changed else "no",
                before=before,
                after=after,
                dropped=dropped,
                unknown=unknown,
            )
        )

    mode = "apply" if args.apply else "dry_run"
    print(f"[INFO] mode={mode}")
    print(f"[INFO] files_changed={files_changed}")
    print(
        f"[INFO] totals before={totals['before']} after={totals['after']} "
        f"dropped={totals['dropped']} unknown={totals['unknown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
