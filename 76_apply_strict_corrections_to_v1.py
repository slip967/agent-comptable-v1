import json
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TRANSPORT_FILES = [
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
]

BTP_FILES = [
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
]

CHARGES_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

TRANSPORT_ACCOUNT_FIXES = {
    "PATE POUR FREINS": "6062",
}

TRANSPORT_FUEL_PATTERNS = [
    re.compile(r"\bgazole\b", re.I),
    re.compile(r"\bcarburant\b", re.I),
    re.compile(r"\badblue\b", re.I),
]

BTP_SERVICE_PATTERNS = [
    re.compile(r"\bcoulage\b", re.I),
    re.compile(r"\bforfait\b", re.I),
    re.compile(r"\bparking\b", re.I),
    re.compile(r"pompe beton", re.I),
    re.compile(r"mission g3", re.I),
    re.compile(r"terrassement", re.I),
    re.compile(r"sous[- ]traitance", re.I),
    re.compile(r"\blocation\b", re.I),
    re.compile(r"echafaud", re.I),
    re.compile(r"amenee[- ]repli", re.I),
    re.compile(r"implantation", re.I),
    re.compile(r"test d.arrachement", re.I),
    re.compile(r"essai de controle", re.I),
    re.compile(r"beton pompe", re.I),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", ascii_value).strip()


def is_transport_fuel_like(item: dict) -> bool:
    text = " ".join(
        [
            item.get("article_source", ""),
            item.get("article_canonique", ""),
            " ".join(item.get("mots_cles", [])),
        ]
    )
    return any(pattern.search(text) for pattern in TRANSPORT_FUEL_PATTERNS)


def is_btp_service_like(item: dict) -> bool:
    text = normalize_text(
        " ".join(
            [
                item.get("article_source", ""),
                item.get("article_canonique", ""),
                " ".join(item.get("mots_cles", [])),
            ]
        )
    )
    return any(pattern.search(text) for pattern in BTP_SERVICE_PATTERNS)


def update_meta_counts(payload: dict) -> None:
    meta = payload.setdefault("meta", {})
    item_count = len(payload.get("items", []))
    a_valider_count = len(payload.get("a_valider", []))
    meta["items_count"] = item_count
    meta["a_valider_count"] = a_valider_count
    meta["total_entries_count"] = item_count + a_valider_count


def tag_cleanup_meta(payload: dict, summary: dict) -> None:
    meta = payload.setdefault("meta", {})
    meta["strict_v1_realign_with_corrected_v3"] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }


def apply_transport_fixes(path: Path, report_rows: list[dict]) -> None:
    payload = load_json(path)
    fixes = 0
    for item in payload.get("items", []):
        source = item.get("article_source", "")
        old_account = item.get("compte_comptable")
        new_account = old_account

        if source in TRANSPORT_ACCOUNT_FIXES:
            new_account = TRANSPORT_ACCOUNT_FIXES[source]
        elif is_transport_fuel_like(item):
            new_account = "6063"

        if new_account != old_account:
            item["compte_comptable"] = new_account
            item["compte_comptable_source"] = "strict_v1_realign_with_corrected_v3"
            reason = item.get("compte_comptable_match_reason", "")
            item["compte_comptable_match_reason"] = (
                f"{reason} | strict_v1_realign:{old_account}->{new_account}".strip(" |")
            )
            item["notes"] = (
                f"{item.get('notes', '')} | Correction compte transport depuis revue stricte V3."
            ).strip(" |")
            fixes += 1
            report_rows.append(
                {
                    "file": path.name,
                    "action": "transport_account_fix",
                    "article_source": source,
                    "detail": f"{old_account}->{new_account}",
                }
            )

    update_meta_counts(payload)
    tag_cleanup_meta(payload, {"transport_account_fixes": fixes, "btp_moved_to_charges_a_valider": 0})
    dump_json(path, payload)


def build_charges_pending_item(item: dict) -> dict:
    moved = deepcopy(item)
    moved["categorie"] = "charges_externes"
    moved["sous_categorie"] = "frais_service"
    moved["fournisseur_type"] = "service"
    moved["sous_profil"] = "entretien_et_maintenance"
    moved["nature_charge"] = "prestation"
    moved["profil_facturation"] = "intervention_ponctuelle"
    moved["profil_facturation_champs"] = ["montant_ht", "montant_ttc"]
    moved["classification_version"] = "strict_v1_realign_with_corrected_v3"
    moved["classification_reason"] = "reclass_from_btp_product_to_charges_pending"
    moved["validation_reason"] = "ligne_btp_prestation_a_valider_en_charges_externes"
    moved["notes"] = (
        f"{moved.get('notes', '')} | Deplace depuis base_produits_btp_v1 vers charges_externes/a_valider apres revue stricte."
    ).strip(" |")
    return moved


def move_btp_service_like_items(report_rows: list[dict]) -> None:
    btp_payloads = {name: load_json(ROOT / name) for name in BTP_FILES}
    charges_payloads = {name: load_json(ROOT / name) for name in CHARGES_FILES}

    base_btp = btp_payloads["base_produits_btp_v1.json"]
    base_btp_with = btp_payloads["base_produits_btp_v1_with_accounts.json"]
    base_charges = charges_payloads["base_charges_externes_v1.json"]
    base_charges_with = charges_payloads["base_charges_externes_v1_with_accounts.json"]

    base_charges.setdefault("a_valider", [])
    base_charges_with.setdefault("a_valider", [])

    existing_charges_norm = {normalize_text(i.get("article_source", "")) for i in base_charges.get("items", [])}
    existing_charges_pending_norm = {normalize_text(i.get("article_source", "")) for i in base_charges.get("a_valider", [])}
    existing_charges_with_norm = {normalize_text(i.get("article_source", "")) for i in base_charges_with.get("items", [])}
    existing_charges_with_pending_norm = {normalize_text(i.get("article_source", "")) for i in base_charges_with.get("a_valider", [])}

    moved_count = 0

    def split_items(payload: dict, charges_payload: dict, items_norm: set[str], pending_norm: set[str], file_name: str) -> list[dict]:
        nonlocal moved_count
        kept = []
        for item in payload.get("items", []):
            source = item.get("article_source", "")
            normalized = normalize_text(source)
            if is_btp_service_like(item):
                moved_count += 1 if file_name == "base_produits_btp_v1.json" else 0
                if normalized not in items_norm and normalized not in pending_norm:
                    charges_payload["a_valider"].append(build_charges_pending_item(item))
                    pending_norm.add(normalized)
                report_rows.append(
                    {
                        "file": file_name,
                        "action": "move_btp_item_to_charges_a_valider",
                        "article_source": source,
                        "detail": item.get("compte_comptable", ""),
                    }
                )
            else:
                kept.append(item)
        return kept

    base_btp["items"] = split_items(
        base_btp,
        base_charges,
        existing_charges_norm,
        existing_charges_pending_norm,
        "base_produits_btp_v1.json",
    )
    base_btp_with["items"] = split_items(
        base_btp_with,
        base_charges_with,
        existing_charges_with_norm,
        existing_charges_with_pending_norm,
        "base_produits_btp_v1_with_accounts.json",
    )

    for payload in [base_btp, base_btp_with, base_charges, base_charges_with]:
        update_meta_counts(payload)

    tag_cleanup_meta(base_btp, {"transport_account_fixes": 0, "btp_moved_to_charges_a_valider": moved_count})
    tag_cleanup_meta(base_btp_with, {"transport_account_fixes": 0, "btp_moved_to_charges_a_valider": moved_count})
    tag_cleanup_meta(base_charges, {"transport_account_fixes": 0, "btp_moved_to_charges_a_valider": moved_count})
    tag_cleanup_meta(base_charges_with, {"transport_account_fixes": 0, "btp_moved_to_charges_a_valider": moved_count})

    dump_json(ROOT / "base_produits_btp_v1.json", base_btp)
    dump_json(ROOT / "base_produits_btp_v1_with_accounts.json", base_btp_with)
    dump_json(ROOT / "base_charges_externes_v1.json", base_charges)
    dump_json(ROOT / "base_charges_externes_v1_with_accounts.json", base_charges_with)


def write_summary(report_rows: list[dict]) -> None:
    summary_path = ROOT / "strict_v1_realign_with_corrected_v3_summary.md"
    lines = [
        "# Strict V1 Realign With Corrected V3",
        "",
        "## Corrections appliquees",
        "",
    ]
    transport_fixes = [row for row in report_rows if row["action"] == "transport_account_fix"]
    btp_moves = [row for row in report_rows if row["action"] == "move_btp_item_to_charges_a_valider"]
    lines.append(f"- `transport` comptes corriges : `{len(transport_fixes)}`")
    lines.append(f"- `btp` lignes deplacees vers `charges_externes/a_valider` : `{len(btp_moves) // 2}`")
    lines.append("")
    lines.append("## Exemples")
    lines.append("")
    for row in transport_fixes[:8]:
        lines.append(f"- `{row['file']}` : `{row['article_source']}` -> `{row['detail']}`")
    for row in btp_moves[:8]:
        lines.append(f"- `{row['file']}` : `{row['article_source']}`")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    report_rows: list[dict] = []
    for file_name in TRANSPORT_FILES:
        apply_transport_fixes(ROOT / file_name, report_rows)
    move_btp_service_like_items(report_rows)
    write_summary(report_rows)


if __name__ == "__main__":
    main()
