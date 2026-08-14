#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_local_v1.app.account_labels import get_account_label


ROOT = Path(__file__).resolve().parent
SOURCE_PDF = r"C:\Users\Dell\Downloads\LES 250 ÉCRITURES COMPTABLES LES PLUS FRÉQUENTES (1) 1.pdf"

BASE_FILES = [
    "base_charges_externes_v1.json",
    "base_produits_boucherie_v1.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_vtc_v1.json",
]


def add_after_compte(item: dict[str, Any], label: str) -> dict[str, Any]:
    enriched: dict[str, Any] = {}
    inserted = False
    for key, value in item.items():
        enriched[key] = value
        if key == "compte_comptable":
            enriched["compte_comptable_libelle"] = label
            inserted = True

    if not inserted:
        enriched["compte_comptable_libelle"] = label
    return enriched


def enrich_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"Format items invalide dans {path.name}")

    changed = 0
    missing: dict[str, int] = {}
    account_counts: dict[str, int] = {}
    enriched_items: list[Any] = []

    for item in items:
        if not isinstance(item, dict):
            enriched_items.append(item)
            continue

        account = str(item.get("compte_comptable") or "").strip()
        if not account:
            enriched_items.append(item)
            continue

        account_counts[account] = account_counts.get(account, 0) + 1
        label = get_account_label(account)
        if not label:
            missing[account] = missing.get(account, 0) + 1
            enriched_items.append(item)
            continue

        if item.get("compte_comptable_libelle") != label:
            changed += 1
            item = add_after_compte(item, label)
        enriched_items.append(item)

    if missing:
        raise ValueError(f"{path.name}: comptes sans libelle: {sorted(missing)}")

    payload["items"] = enriched_items
    meta = payload.setdefault("meta", {})
    meta["compte_comptable_libelles"] = {
        "field": "compte_comptable_libelle",
        "source_pdf": SOURCE_PDF,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "accounts_covered": sorted(account_counts),
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "file": path.name,
        "items": len(items),
        "changed": changed,
        "accounts": account_counts,
    }


def main() -> None:
    summary = {
        "source_pdf": SOURCE_PDF,
        "field_added": "compte_comptable_libelle",
        "files": [],
    }

    for filename in BASE_FILES:
        path = ROOT / filename
        if not path.exists():
            raise FileNotFoundError(path)
        summary["files"].append(enrich_file(path))

    out_path = ROOT / "add_account_labels_to_v1_bases_summary.json"
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
