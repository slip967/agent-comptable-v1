#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SUMMARY_JSON = SCRIPT_DIR / "cap_vtc_epicerie_to_500_summary.json"
SUMMARY_MD = SCRIPT_DIR / "cap_vtc_epicerie_to_500_summary.md"

TARGETS = {
    "vtc": [
        "base_produits_vtc_v1.json",
        "base_produits_vtc_v1_with_accounts.json",
    ],
    "epicerie": [
        "base_produits_epicerie_v1.json",
        "base_produits_epicerie_v1_with_accounts.json",
    ],
}

MAX_TOTAL = 500


def rank_value(item: dict) -> tuple[int, int, int]:
    score = int(item.get("compte_comptable_match_score") or 0)
    invoice_ids = len(item.get("source_invoice_ids") or [])
    keywords = len(item.get("mots_cles") or [])
    return score, invoice_ids, keywords


def select_items(items: list[dict], keep_count: int) -> list[dict]:
    ranked = []
    for idx, item in enumerate(items):
        ranked.append((rank_value(item), idx, item))
    ranked.sort(key=lambda row: (-row[0][0], -row[0][1], -row[0][2], row[1]))
    kept_indices = {idx for _, idx, _ in ranked[:keep_count]}
    return [item for idx, item in enumerate(items) if idx in kept_indices]


def process_file(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    a_valider = payload.get("a_valider") or []

    target_items_count = max(0, MAX_TOTAL - len(a_valider))
    kept_items = select_items(items, target_items_count)

    removed_count = len(items) - len(kept_items)
    payload["items"] = kept_items
    payload["a_valider"] = a_valider

    meta = payload.setdefault("meta", {})
    meta["items_count"] = len(kept_items)
    meta["a_valider_count"] = len(a_valider)
    meta["total_entries_count"] = len(kept_items) + len(a_valider)
    meta["cap_vtc_epicerie_to_500_v1"] = {
        "max_total": MAX_TOTAL,
        "previous_items_count": len(items),
        "previous_a_valider_count": len(a_valider),
        "removed_items_count": removed_count,
        "kept_items_count": len(kept_items),
    }

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "items_count": len(kept_items),
        "a_valider_count": len(a_valider),
        "total_entries_count": len(kept_items) + len(a_valider),
        "removed_items_count": removed_count,
    }


def write_markdown(summary: dict) -> None:
    lines = ["# Cap VTC Epicerie 500", ""]
    for path, data in summary.items():
        lines.append(f"## {path}")
        lines.append(f"- items: {data['items_count']}")
        lines.append(f"- a_valider: {data['a_valider_count']}")
        lines.append(f"- total: {data['total_entries_count']}")
        lines.append(f"- items retirés: {data['removed_items_count']}")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    summary = {}
    for _, paths in TARGETS.items():
        for rel_path in paths:
            summary[rel_path] = process_file(SCRIPT_DIR / rel_path)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
