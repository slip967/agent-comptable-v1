#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
TARGET_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

RESTORE_MAP = {
    "Nettoyage fin de chantier": "Nettoyage en cours et en fin de chantier. Nettoyage fin de chantier et mise en décharge de déchets du chantier.",
}


def main() -> int:
    summary = {}
    for file_name in TARGET_FILES:
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        restored = []
        for bucket in ("items", "a_valider"):
            for item in payload.get(bucket) or []:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("article_source") or "")
                if label in RESTORE_MAP:
                    item["article_source"] = RESTORE_MAP[label]
                    restored.append(label)
        payload.setdefault("meta", {})
        payload["meta"]["restore_specific_labels_after_cleanup_v1"] = {
            "restored_count": len(restored),
            "restored_labels": restored,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary[file_name] = restored

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
