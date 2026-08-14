#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

TARGETS = {
    "base_produits_restaurant_v1.json": {
        "Montant net facturable par Deliveroo",
        "Taxes locales - part communale",
        "Option Anti-spam",
        "Achat non détaillé",
        "Paiements supplémentaires",
        "Obligations",
        "Vos services fournis par votre opérateur",
        "Fourniture d'électricité - Consommation",
        "Avantage client box",
        "Article non spécifié",
        "Gazole",
        "EPICERIE",
        "Revenus en titre-restaurant",
        "Promotions sur les articles",
        "Option Energie Verte",
    },
    "base_produits_restaurant_v1_with_accounts.json": {
        "Montant net facturable par Deliveroo",
        "Taxes locales - part communale",
        "Option Anti-spam",
        "Achat non détaillé",
        "Paiements supplémentaires",
        "Obligations",
        "Vos services fournis par votre opérateur",
        "Fourniture d'électricité - Consommation",
        "Avantage client box",
        "Article non spécifié",
        "Gazole",
        "EPICERIE",
        "Revenus en titre-restaurant",
        "Promotions sur les articles",
        "Option Energie Verte",
    },
    "base_produits_boucherie_v1.json": {
        "Manutention et approvisionnement. Approvisionnement à pied d'œuvre des différents matériaux.",
        "Manutention et approvisionnement. Approvisionnement à pied d'oeuvre des différents matériaux.",
        "INTERBEV Boeuf",
    },
    "base_produits_boucherie_v1_with_accounts.json": {
        "Manutention et approvisionnement. Approvisionnement à pied d'œuvre des différents matériaux.",
        "Manutention et approvisionnement. Approvisionnement à pied d'oeuvre des différents matériaux.",
        "INTERBEV Boeuf",
    },
}


def main() -> int:
    for file_name, labels in TARGETS.items():
        path = SCRIPT_DIR / file_name
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        items = payload.get("items") or []
        kept = []
        removed = []
        for item in items:
            if not isinstance(item, dict):
                kept.append(item)
                continue
            article_source = str(item.get("article_source") or "").strip()
            if article_source in labels:
                removed.append(article_source)
                continue
            kept.append(item)
        payload["items"] = kept
        payload.setdefault("meta", {})
        payload["meta"]["items_count"] = len(kept)
        payload["meta"]["second_wave_restaurant_cleanup_v1"] = {
            "removed_labels": removed,
            "removed_count": len(removed),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{file_name}: removed={len(removed)} labels={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
