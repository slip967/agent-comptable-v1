import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TARGET_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_boulangerie_v1_with_accounts.json",
    "base_produits_restaurant_v1.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_produits_vtc_v1.json",
    "base_produits_vtc_v1_with_accounts.json",
    "base_produits_epicerie_v1.json",
    "base_produits_epicerie_v1_with_accounts.json",
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def trim_ids(values) -> list[str]:
    if isinstance(values, list):
        return values[:3]
    return []


def trim_list(values) -> list:
    if isinstance(values, list):
        return values
    return []


def slim_item(item: dict) -> dict:
    ids_fr = trim_ids(item.get("ids_factures_sources") or item.get("source_invoice_ids"))
    ids_en = trim_ids(item.get("source_invoice_ids") or item.get("ids_factures_sources"))
    partitions_fr = trim_list(item.get("partitions_sources") or item.get("source_partition_ids"))
    partitions_en = trim_list(item.get("source_partition_ids") or item.get("partitions_sources"))
    ape_fr = trim_list(item.get("contexte_ape") or item.get("ape_context"))
    ape_en = trim_list(item.get("ape_context") or item.get("contexte_ape"))
    taux_tva = item.get("taux_tva", item.get("tva_rate"))
    type_fournisseur = item.get("type_fournisseur", item.get("fournisseur_type"))

    slim = {
        "article_source": item.get("article_source", ""),
        "article_canonique": item.get("article_canonique", ""),
        "mots_cles": trim_list(item.get("mots_cles")),
        "ids_factures_sources": ids_fr,
        "source_invoice_ids": ids_en,
        "contexte_ape": ape_fr,
        "ape_context": ape_en,
        "partitions_sources": partitions_fr,
        "source_partition_ids": partitions_en,
        "compte_comptable": item.get("compte_comptable", ""),
        "taux_tva": taux_tva,
        "tva_rate": taux_tva,
        "categorie": item.get("categorie", ""),
        "sous_categorie": item.get("sous_categorie", ""),
        "type_fournisseur": type_fournisseur,
        "fournisseur_type": type_fournisseur,
    }
    return slim


def extract_alignment_meta(meta: dict) -> tuple[str, str]:
    for key, value in meta.items():
        if key.startswith("accounts_alignment_from_") and isinstance(value, dict):
            return str(value.get("db", "")), str(value.get("selector", ""))
    return "", ""


def slim_meta(meta: dict, items_count: int, a_valider_count: int) -> dict:
    accounts_alignment_from, selector = extract_alignment_meta(meta)
    generated_at = meta.get("generated_at", "")
    client_siren = meta.get("client_siren", "")
    partition_prefix = meta.get("partition_prefix", "")
    updated_at = datetime.now(timezone.utc).isoformat()
    return {
        "profile_id": meta.get("profile_id", ""),
        "metier": meta.get("metier", ""),
        "client_siren": client_siren,
        "partition_prefix": partition_prefix,
        "generated_at": generated_at,
        "updated_at": updated_at,
        "items_count": items_count,
        "a_valider_count": a_valider_count,
        "accounts_alignment_from": accounts_alignment_from,
        "selector": selector,
        "source_client": client_siren or partition_prefix,
    }


def main() -> None:
    summary = {}
    for file_name in TARGET_FILES:
        path = ROOT / file_name
        payload = load_json(path)
        items = [slim_item(item) for item in payload.get("items", [])]
        a_valider = [slim_item(item) for item in payload.get("a_valider", [])]
        meta = slim_meta(payload.get("meta", {}), len(items), len(a_valider))
        cleaned = {
            "meta": meta,
            "items": items,
            "a_valider": a_valider,
        }
        dump_json(path, cleaned)
        summary[file_name] = {
            "items": len(items),
            "a_valider": len(a_valider),
        }

    (ROOT / "slim_v1_json_to_essential_fields_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
