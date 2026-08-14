#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
TARGET_FILES = [
    ROOT / "base_produits_transport_v1.json",
    ROOT / "base_produits_transport_v1_with_accounts.json",
]

OLD_LABEL = "Plaquette avant"
NEW_ITEM: dict[str, Any] = {
    "article_source": "Cable de frein a main gauche",
    "article_canonique": "cable de frein a main gauche",
    "mots_cles": [
        "cable",
        "de",
        "frein",
        "a",
        "main",
        "gauche",
    ],
    "source_invoice_ids": [
        "fr_bd_908282098:c237833d-842c-408a-9e09-9b220d9ae60f",
    ],
    "invoice_paths_sources": [],
    "ape_context": [
        "4942Z",
    ],
    "partitions_sources": [
        "fr_bd_908282098",
    ],
    "compte_comptable": "6062",
    "taux_tva": 20.0,
    "categorie": "exploitation_metier",
    "sous_categorie": "matiere_premiere",
    "type_fournisseur": "service_transport",
    "ids_factures_sources": [
        "fr_bd_908282098:c237833d-842c-408a-9e09-9b220d9ae60f",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for path in TARGET_FILES:
        payload = load_json(path)
        items = payload.get("items") or []
        replaced = False
        for index, item in enumerate(items):
            if str(item.get("article_source") or "").strip() == OLD_LABEL:
                items[index] = NEW_ITEM.copy()
                replaced = True
                break
        if not replaced:
            raise RuntimeError(f"{path.name}: label not found: {OLD_LABEL}")
        payload.setdefault("meta", {})
        payload["meta"]["items_count"] = len(items)
        dump_json(path, payload)
        print(f"[OK] replaced in {path.name}")


if __name__ == "__main__":
    main()
