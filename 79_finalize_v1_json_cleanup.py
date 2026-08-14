import json
import re
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
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_source(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def merge_unique_list(left, right):
    result = []
    seen = set()
    for value in list(left or []) + list(right or []):
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def choose_preferred_value(key: str, left, right):
    if key in {"ids_factures_sources", "source_invoice_ids", "contexte_ape", "ape_context", "partitions_sources", "source_partition_ids", "mots_cles"}:
        return merge_unique_list(left, right)
    if key in {"taux_tva", "tva_rate"}:
        # Prefer 20 over 5.5 for these remaining duplicates, which all belong to charges/service-like entries.
        values = [v for v in [left, right] if v not in (None, "", [])]
        if 20.0 in values:
            return 20.0
        return values[0] if values else left
    if key in {"sous_categorie"}:
        priorities = ["transport", "charges_generales", "frais_service", "matiere_premiere"]
        values = [v for v in [left, right] if v]
        for priority in priorities:
            if priority in values:
                return priority
        return values[0] if values else left
    return left if left not in (None, "", []) else right


def merge_items(primary: dict, duplicate: dict) -> dict:
    merged = dict(primary)
    for key, value in duplicate.items():
        merged[key] = choose_preferred_value(key, merged.get(key), value)
    return merged


def dedupe_section(items: list[dict]) -> tuple[list[dict], int]:
    deduped = []
    by_norm = {}
    duplicates_removed = 0
    for item in items:
        norm = normalize_source(item.get("article_source", ""))
        if norm in by_norm:
            idx = by_norm[norm]
            deduped[idx] = merge_items(deduped[idx], item)
            duplicates_removed += 1
        else:
            by_norm[norm] = len(deduped)
            deduped.append(item)
    return deduped, duplicates_removed


def fill_generated_at(meta: dict) -> bool:
    if meta.get("generated_at"):
        return False
    replacement = meta.get("updated_at") or datetime.now(timezone.utc).isoformat()
    meta["generated_at"] = replacement
    return True


def main() -> None:
    summary = {}
    for file_name in TARGET_FILES:
        path = ROOT / file_name
        payload = load_json(path)
        generated_at_filled = fill_generated_at(payload.setdefault("meta", {}))
        items, items_removed = dedupe_section(payload.get("items", []))
        a_valider, a_valider_removed = dedupe_section(payload.get("a_valider", []))
        payload["items"] = items
        payload["a_valider"] = a_valider
        payload["meta"]["items_count"] = len(items)
        payload["meta"]["a_valider_count"] = len(a_valider)
        payload["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload["meta"]["final_cleanup_v1"] = {
            "applied_at": payload["meta"]["updated_at"],
            "generated_at_filled": generated_at_filled,
            "duplicates_removed_items": items_removed,
            "duplicates_removed_a_valider": a_valider_removed,
        }
        dump_json(path, payload)
        summary[file_name] = payload["meta"]["final_cleanup_v1"]

    (ROOT / "final_cleanup_v1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = ["# Final Cleanup V1", ""]
    for file_name, info in summary.items():
        lines.append(f"## {file_name}")
        lines.append("")
        lines.append(f"- generated_at rempli : `{info['generated_at_filled']}`")
        lines.append(f"- doublons retirés dans `items` : `{info['duplicates_removed_items']}`")
        lines.append(f"- doublons retirés dans `a_valider` : `{info['duplicates_removed_a_valider']}`")
        lines.append("")
    (ROOT / "final_cleanup_v1_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
