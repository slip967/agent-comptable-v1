from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .account_labels import get_account_label
from .config import PROJECT_DIR, REFERENCE_COUCH_DB, REFERENCE_SOURCE


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

METIER_BY_FILE = {
    "base_produits_boulangerie_v1.json": "boulangerie",
    "base_produits_boucherie_v1.json": "boucherie",
    "base_produits_restaurant_v1.json": "restaurant",
    "base_produits_btp_v1.json": "btp",
    "base_produits_transport_v1.json": "transport",
    "base_produits_epicerie_v1.json": "epicerie",
    "base_produits_vtc_v1.json": "vtc",
    "base_charges_externes_v1.json": "global",
}

LAST_LOAD_SOURCE = "uninitialized"
LAST_LOAD_ERROR = ""


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def _build_local_reference_item(filename: str, item: dict[str, Any]) -> dict[str, Any]:
    account = (item.get("compte_comptable") or "").strip()
    tva_rate = item.get("taux_tva")
    if tva_rate is None:
        tva_rate = item.get("tva_rate")

    return {
        "base_file": filename,
        "metier": METIER_BY_FILE.get(filename, ""),
        "article_source": (item.get("article_source") or "").strip(),
        "article_canonique": (item.get("article_canonique") or "").strip(),
        "article_canonique_normalized": normalize_text(item.get("article_canonique") or ""),
        "categorie": (item.get("categorie") or "").strip(),
        "sous_categorie": (item.get("sous_categorie") or "").strip(),
        "compte_comptable": account,
        "compte_comptable_libelle": (
            item.get("compte_comptable_libelle")
            or item.get("account_label")
            or get_account_label(account)
            or ""
        ).strip(),
        "account_label": (
            item.get("account_label")
            or item.get("compte_comptable_libelle")
            or get_account_label(account)
            or ""
        ).strip(),
        "source_partition": (item.get("source_partition") or "").strip(),
        "mots_cles": list(item.get("mots_cles") or []),
        "tva_rate": tva_rate,
        "ape_context": list(item.get("ape_context") or []),
        "source_invoice_ids": list(item.get("source_invoice_ids") or []),
        "ids_factures_sources": list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []),
        "invoice_paths_sources": list(item.get("invoice_paths_sources") or []),
        "partitions_sources": list(item.get("partitions_sources") or []),
        "type_fournisseur": (item.get("type_fournisseur") or "").strip(),
        "sous_profil": (item.get("sous_profil") or "").strip(),
        "nature_charge": (item.get("nature_charge") or "").strip(),
        "profil_facturation": (item.get("profil_facturation") or "").strip(),
    }


def load_local_bases(data_dir: Path | None = None) -> list[dict[str, Any]]:
    root = data_dir or PROJECT_DIR
    items: list[dict[str, Any]] = []
    for filename in BASE_FILES:
        path = root / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for item in payload.get("items", []):
            if isinstance(item, dict):
                items.append(_build_local_reference_item(filename, item))
    return items


def get_reference_load_status() -> tuple[str, str]:
    return LAST_LOAD_SOURCE, LAST_LOAD_ERROR


def load_all_bases(data_dir: Path | None = None) -> list[dict[str, Any]]:
    global LAST_LOAD_SOURCE, LAST_LOAD_ERROR
    if REFERENCE_SOURCE in {"couchdb", "auto"}:
        try:
            from .couch_product_loader import load_couch_reference_rows

            rows = load_couch_reference_rows(db_name=REFERENCE_COUCH_DB)
            LAST_LOAD_SOURCE = f"couchdb:{REFERENCE_COUCH_DB}"
            LAST_LOAD_ERROR = ""
            return rows
        except Exception as exc:
            LAST_LOAD_SOURCE = "local_json:fallback"
            LAST_LOAD_ERROR = str(exc)
            print(
                f"[WARN] Chargement CouchDB des references impossible ({exc}). "
                "Fallback sur les JSON locaux."
            )
    else:
        LAST_LOAD_SOURCE = "local_json"
        LAST_LOAD_ERROR = ""
    return load_local_bases(data_dir=data_dir)
