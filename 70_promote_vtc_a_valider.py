#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TARGET_FILES = [
    "base_produits_vtc_v1.json",
    "base_produits_vtc_v1_with_accounts.json",
]


def main() -> int:
    summary = {}
    for file_name in TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))

        items = payload.get("items") or []
        pending = payload.get("a_valider") or []
        promoted = []

        for item in pending:
            if not isinstance(item, dict):
                continue
            note = str(item.get("notes") or "").strip()
            promote_note = "promotion_vtc_a_valider_v1"
            item["notes"] = f"{note} | {promote_note}".strip(" |")
            item["selection_source"] = "manual_vtc_include_beverage_v1"
            item.pop("validation_status", None)
            item.pop("validation_reason", None)
            item.pop("validation_note", None)
            items.append(item)
            promoted.append(str(item.get("article_source") or ""))

        payload["items"] = items
        payload["a_valider"] = []
        payload.setdefault("meta", {})
        payload["meta"]["items_count"] = len(items)
        payload["meta"]["a_valider_count"] = 0
        payload["meta"]["total_entries_count"] = len(items)
        payload["meta"]["promote_vtc_a_valider_v1"] = {
            "promoted_count": len(promoted),
            "promoted_labels": promoted,
        }

        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary[file_name] = {
            "promoted_count": len(promoted),
            "items_count": len(items),
            "a_valider_count": 0,
        }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
