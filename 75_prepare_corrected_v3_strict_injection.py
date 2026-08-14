import csv
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "prepared_corrected_v3_injection"
TARGET_DIR = ROOT / "prepared_corrected_v3_injection_strict"

KEEP_FILES = [
    "base_produits_boucherie_corrected_v3.json",
    "base_produits_boulangerie_corrected_v3.json",
    "base_produits_restaurant_corrected_v3.json",
    "base_produits_btp_corrected_v3.json",
    "base_produits_transport_corrected_v3.json",
    "base_charges_externes_corrected_v3.json",
]

EXCLUDED_FILES = [
    "base_produits_epicerie_corrected_v3.json",
    "base_produits_vtc_corrected_v3.json",
]

TRANSPORT_FUEL_ACCOUNT_PATTERNS = [
    re.compile(r"\bgazole\b", re.I),
    re.compile(r"\bcarburant\b", re.I),
    re.compile(r"\badblue\b", re.I),
]

TRANSPORT_SUPPLY_ACCOUNT_OVERRIDES = {
    "PATE POUR FREINS": "6062",
}

BTP_SERVICE_PATTERNS = [
    re.compile(r"\bcoulage\b", re.I),
    re.compile(r"\bforfait\b", re.I),
    re.compile(r"\bparking\b", re.I),
    re.compile(r"pompe b[ée]ton", re.I),
    re.compile(r"mission g3", re.I),
    re.compile(r"terrassement", re.I),
    re.compile(r"sous[- ]traitance", re.I),
    re.compile(r"\blocation\b", re.I),
    re.compile(r"echafaud", re.I),
    re.compile(r"amen[ée]e[- ]repli", re.I),
    re.compile(r"implantation", re.I),
    re.compile(r"test d.arrachement", re.I),
    re.compile(r"essai de contr[ôo]le", re.I),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_transport_fuel_like(item: dict) -> bool:
    haystack = " ".join(
        [
            item.get("article_source", ""),
            item.get("article_canonique", ""),
            " ".join(item.get("mots_cles", [])),
        ]
    )
    return any(pattern.search(haystack) for pattern in TRANSPORT_FUEL_ACCOUNT_PATTERNS)


def is_btp_service_like(item: dict) -> bool:
    haystack = " ".join(
        [
            item.get("article_source", ""),
            item.get("article_canonique", ""),
            " ".join(item.get("mots_cles", [])),
        ]
    )
    return any(pattern.search(haystack) for pattern in BTP_SERVICE_PATTERNS)


def update_meta(payload: dict, file_name: str, summary: dict) -> None:
    meta = payload.setdefault("meta", {})
    item_count = len(payload.get("items", []))
    meta["items_count"] = item_count
    meta["total_entries_count"] = item_count
    meta["a_valider_count"] = len(payload.get("a_valider", []))
    meta["cleanup_corrected_v3_strict"] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "source_file": file_name,
        "excluded_base_files": EXCLUDED_FILES,
        "summary": summary,
    }


def prepare_transport(payload: dict, file_name: str, changes: list[dict]) -> dict:
    result = deepcopy(payload)
    fixed = 0
    for item in result.get("items", []):
        source = item.get("article_source", "")
        old_account = item.get("compte_comptable")
        new_account = old_account

        if source in TRANSPORT_SUPPLY_ACCOUNT_OVERRIDES:
            new_account = TRANSPORT_SUPPLY_ACCOUNT_OVERRIDES[source]
        elif is_transport_fuel_like(item):
            new_account = "6063"

        if new_account != old_account:
            item["compte_comptable"] = new_account
            reason = item.get("compte_comptable_match_reason", "")
            item["compte_comptable_match_reason"] = (
                f"{reason} | strict_pre_injection_v1:{old_account}->{new_account}".strip(" |")
            )
            item["compte_comptable_source"] = "strict_pre_injection_v1"
            item["notes"] = (
                f"{item.get('notes', '')} | Compte ajuste en preparation d'injection stricte."
            ).strip(" |")
            fixed += 1
            changes.append(
                {
                    "base": file_name,
                    "action": "account_fix",
                    "article_source": source,
                    "old_account": old_account,
                    "new_account": new_account,
                    "reason": "fuel_or_vehicle_supply_strict_review",
                }
            )

    update_meta(result, file_name, {"account_fixes": fixed, "excluded_items": 0})
    return result


def prepare_btp(payload: dict, file_name: str, changes: list[dict]) -> tuple[dict, list[dict]]:
    result = deepcopy(payload)
    kept_items = []
    excluded_items = []

    for item in result.get("items", []):
        if is_btp_service_like(item):
            excluded_items.append(item)
            changes.append(
                {
                    "base": file_name,
                    "action": "exclude_from_strict_product_injection",
                    "article_source": item.get("article_source", ""),
                    "old_account": item.get("compte_comptable", ""),
                    "new_account": "",
                    "reason": "btp_service_like_label",
                }
            )
        else:
            kept_items.append(item)

    result["items"] = kept_items
    update_meta(
        result,
        file_name,
        {"account_fixes": 0, "excluded_items": len(excluded_items)},
    )
    return result, excluded_items


def prepare_passthrough(payload: dict, file_name: str) -> dict:
    result = deepcopy(payload)
    update_meta(result, file_name, {"account_fixes": 0, "excluded_items": 0})
    return result


def main() -> None:
    TARGET_DIR.mkdir(exist_ok=True)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(SOURCE_DIR),
        "target_dir": str(TARGET_DIR),
        "included_files": [],
        "excluded_files": EXCLUDED_FILES,
        "changes_count": 0,
        "dry_run_ready": True,
    }
    changes: list[dict] = []
    excluded_btp_items: list[dict] = []

    for file_name in KEEP_FILES:
        source_path = SOURCE_DIR / file_name
        payload = load_json(source_path)

        if file_name == "base_produits_transport_corrected_v3.json":
            prepared = prepare_transport(payload, file_name, changes)
        elif file_name == "base_produits_btp_corrected_v3.json":
            prepared, excluded = prepare_btp(payload, file_name, changes)
            excluded_btp_items.extend(excluded)
        else:
            prepared = prepare_passthrough(payload, file_name)

        target_path = TARGET_DIR / file_name
        dump_json(target_path, prepared)
        manifest["included_files"].append(
            {
                "file": file_name,
                "items_count": len(prepared.get("items", [])),
            }
        )

    manifest["changes_count"] = len(changes)
    manifest["excluded_btp_items_count"] = len(excluded_btp_items)
    dump_json(TARGET_DIR / "manifest_corrected_v3_strict_injection.json", manifest)
    dump_json(TARGET_DIR / "strict_changes.json", {"changes": changes, "excluded_btp_items": excluded_btp_items})

    csv_path = TARGET_DIR / "strict_changes.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["base", "action", "article_source", "old_account", "new_account", "reason"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(changes)

    lines = [
        "# Corrected V3 Strict Injection",
        "",
        "## Perimetre",
        "",
        "- Bases incluses : `boucherie`, `boulangerie`, `restaurant`, `btp`, `transport`, `charges_externes`",
        "- Bases exclues volontairement : `vtc`, `epicerie`",
        "",
        "## Corrections appliquees",
        "",
        f"- Corrections de comptes `transport` : `{sum(1 for c in changes if c['action'] == 'account_fix')}`",
        f"- Lignes BTP sorties du lot produit strict : `{sum(1 for c in changes if c['action'] == 'exclude_from_strict_product_injection')}`",
        "",
        "## Volumes",
        "",
    ]
    for item in manifest["included_files"]:
        lines.append(f"- `{item['file']}` : `{item['items_count']}`")
    lines.extend(
        [
            "",
            "## Commande dry-run",
            "",
            "```bash",
            "python 22_import_product_base_instances.py --db ayasmine_test2 --pattern prepared_corrected_v3_injection_strict/base_produits_*_corrected_v3.json prepared_corrected_v3_injection_strict/base_charges_externes_corrected_v3.json --dry-run",
            "```",
            "",
        ]
    )
    (TARGET_DIR / "README_ready_to_inject_strict.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
