from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TARGET_FILES = [
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

ACCOUNT_MAP = {
    "606100": "6061",
    "60610000": "6061",
    "606200": "6062",
    "60620000": "6062",
    "606300": "6063",
    "60630000": "6063",
    "606800": "6068",
    "60680000": "6068",
    "622600": "6226",
}


def walk_and_normalize(node, stats):
    if isinstance(node, dict):
        compte = node.get("compte_comptable")
        if compte in ACCOUNT_MAP:
            normalized = ACCOUNT_MAP[compte]
            node["compte_comptable"] = normalized
            stats["changed_items"] += 1
            stats["normalized_pairs"].setdefault(f"{compte}->{normalized}", 0)
            stats["normalized_pairs"][f"{compte}->{normalized}"] += 1

        for value in node.values():
            walk_and_normalize(value, stats)
        return

    if isinstance(node, list):
        for item in node:
            walk_and_normalize(item, stats)


def main():
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for relative_path in TARGET_FILES:
        path = ROOT / relative_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        stats = {"changed_items": 0, "normalized_pairs": {}}

        walk_and_normalize(payload, stats)

        payload.setdefault("meta", {})
        payload["meta"]["account_normalization_v2"] = {
            "updated_at": timestamp,
            "rule": "normalize selected padded account codes to canonical form",
            "changed_items": stats["changed_items"],
            "normalized_pairs": stats["normalized_pairs"],
        }

        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"{relative_path}: changed_items={stats['changed_items']} normalized_pairs={stats['normalized_pairs']}"
        )


if __name__ == "__main__":
    main()
