from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def slugify(value: str, fallback: str) -> str:
    normalized = normalize_text(value).replace(" ", "-")
    return normalized[:80] if normalized else fallback


def find_source_files(patterns: list[str]) -> list[Path]:
    selected: dict[str, Path] = {}
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if path.name.endswith("_with_accounts.json"):
                continue
            selected[str(path.resolve())] = path
    return list(selected.values())


def load_source(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: un objet JSON est attendu.")
    meta = payload.get("meta") or {}
    items = payload.get("items") or []
    if not isinstance(meta, dict) or not isinstance(items, list):
        raise ValueError(f"{path.name}: format meta/items invalide.")
    return meta, items


def build_instance_doc(
    *,
    source_file: Path,
    meta: dict,
    item: dict,
    index: int,
) -> tuple[str, dict]:
    profile_id = str(meta.get("profile_id") or source_file.stem).strip()
    metier = str(meta.get("metier") or "").strip().lower()
    source_client = str(meta.get("source_client") or meta.get("client_siren") or "").strip()
    derived_partition = f"fr_bd_{source_client}" if source_client.isdigit() and len(source_client) == 9 else "multi"
    partition_prefix = str(meta.get("partition_prefix") or derived_partition or "multi").strip()
    article_source = str(item.get("article_source") or "").strip()
    article_canonique = str(item.get("article_canonique") or "").strip()
    compte_comptable = str(item.get("compte_comptable") or "").strip()
    categorie = str(item.get("categorie") or "").strip() or None
    sous_categorie = str(item.get("sous_categorie") or "").strip() or None
    source_invoice_ids = item.get("source_invoice_ids") or item.get("ids_factures_sources") or []
    invoice_paths_sources = item.get("invoice_paths_sources") or item.get("chemins_factures_sources") or []
    partitions_sources = item.get("partitions_sources") or item.get("source_partition_ids") or []
    ape_context = item.get("ape_context") or item.get("contexte_ape") or []
    taux_tva = item.get("taux_tva")
    tva_rate = item.get("tva_rate", taux_tva)
    type_fournisseur = item.get("type_fournisseur") or item.get("fournisseur_type")
    fournisseur_type = item.get("fournisseur_type") or type_fournisseur

    digest_source = "|".join(
        [
            profile_id,
            metier,
            article_source,
            article_canonique,
            compte_comptable,
            str(index),
        ]
    )
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:12]
    slug = slugify(article_source or article_canonique, f"item-{index:04d}")
    file_name = f"{index:04d}_{slug}.json"

    payload = {
        "_id": f"{partition_prefix}:product-instance:{profile_id}:{digest}",
        "p": "product_base_instance",
        "data": {
            "collection": "ProductBaseInstance",
            "type": "ProductArticle",
            "sub_type": metier or "unknown",
        },
        "instance_kind": "product_article_source",
        "profile_id": profile_id,
        "metier": metier,
        "client_siren": meta.get("client_siren") or source_client or None,
        "partition_prefix": partition_prefix,
        "source_file": source_file.name,
        "source_profile_meta": meta,
        "item_index": index,
        "article_source": article_source,
        "article_source_normalized": normalize_text(article_source),
        "article_canonique": article_canonique,
        "categorie": categorie,
        "sous_categorie": sous_categorie,
        "compte_comptable": compte_comptable or None,
        "taux_tva": taux_tva,
        "tva_rate": tva_rate,
        "mots_cles": item.get("mots_cles") or [],
        "source_invoice_ids": source_invoice_ids,
        "invoice_paths_sources": invoice_paths_sources,
        "ape_context": ape_context,
        "partitions_sources": partitions_sources,
        "type_fournisseur": type_fournisseur,
        "fournisseur_type": fournisseur_type,
        "payload": item,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    return file_name, payload


def build_instances_from_source(source: Path) -> tuple[dict, list[dict]]:
    meta, items = load_source(source)
    docs: list[dict] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        _, payload = build_instance_doc(
            source_file=source,
            meta=meta,
            item=item,
            index=index,
        )
        docs.append(payload)
    return meta, docs
