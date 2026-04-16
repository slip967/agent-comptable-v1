from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .config import PROJECT_DIR


BASE_FILES = [
    "base_produits_boulangerie_v1.json",
    "base_produits_boucherie_v1.json",
    "base_produits_restaurant_v1.json",
    "base_produits_btp_v1.json",
    "base_produits_transport_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
    "base_charges_externes_v1.json",
]


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def load_all_bases(data_dir: Path | None = None) -> list[dict]:
    root = data_dir or PROJECT_DIR
    items: list[dict] = []
    for filename in BASE_FILES:
        path = root / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in payload.get("items", []):
            items.append(
                {
                    "base_file": filename,
                    "article_source": (item.get("article_source") or "").strip(),
                    "article_canonique": (item.get("article_canonique") or "").strip(),
                    "article_canonique_normalized": normalize_text(item.get("article_canonique") or ""),
                    "categorie": (item.get("categorie") or "").strip(),
                    "sous_categorie": (item.get("sous_categorie") or "").strip(),
                    "compte_comptable": (item.get("compte_comptable") or "").strip(),
                    "source_partition": (item.get("source_partition") or "").strip(),
                    "mots_cles": list(item.get("mots_cles") or []),
                }
            )
    return items

