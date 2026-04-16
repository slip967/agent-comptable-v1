#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

VTC_SOURCE_FILE = "base_produits_vtc_v1_with_accounts.json"
CHARGES_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

ARTICLE_PATTERN = re.compile(
    r"^Abonnement aux services d'entreprise\s+([A-ZÉÈÊËÂÀÎÏÔÖÙÛÜÇ]+)\s+\d{4}\s+-\s+.*Conseil en entreprise$",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def extract_candidates(vtc_data: dict):
    out = []
    months = []
    seen = set()
    for item in vtc_data.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("article_source") or "").strip()
        m = ARTICLE_PATTERN.match(source)
        if not m:
            continue
        key = normalize_text(source)
        if key in seen:
            continue
        seen.add(key)
        month = m.group(1).upper()
        months.append(month)
        out.append(item)
    return out, months


def build_charge_item(source_item: dict) -> dict:
    source = str(source_item.get("article_source") or "").strip()
    canon = str(source_item.get("article_canonique") or "").strip()
    tva = source_item.get("tva_rate")
    mots_cles = list(source_item.get("mots_cles") or [])
    ape_context = list(source_item.get("ape_context") or [])
    source_invoice_ids = [str(v).strip() for v in (source_item.get("source_invoice_ids") or []) if str(v).strip()]

    account = str(source_item.get("compte_comptable") or "").strip() or "6226"
    score = source_item.get("compte_comptable_match_score")
    reason = str(source_item.get("compte_comptable_match_reason") or "").strip()
    if reason:
        reason = f"{reason}; moved_from_vtc_hors_scope_v1"
    else:
        reason = "moved_from_vtc_hors_scope_v1"

    if not mots_cles:
        mots_cles = [tok for tok in normalize_text(source).split() if len(tok) > 1][:8]

    return {
        "article_source": source,
        "article_canonique": canon or normalize_text(source),
        "categorie": "charges_externes",
        "sous_categorie": "frais_service",
        "tva_rate": tva,
        "mots_cles": mots_cles[:10],
        "fournisseur_type": "service",
        "ape_context": ape_context[:3],
        "notes": "Ajoute depuis base_produits_vtc_v1_with_accounts (hors VTC), validation metier requise.",
        "source_invoice_ids": source_invoice_ids[:5],
        "compte_comptable": account,
        "compte_comptable_source": "vtc_hors_scope_transfer_v1",
        "compte_comptable_match_score": int(score) if isinstance(score, int) else 100,
        "compte_comptable_match_reason": reason,
        "sous_profil": "frais_administratifs_et_bancaires",
        "nature_charge": "frais",
        "profil_facturation": "forfait_ou_frais",
        "profil_facturation_champs": [
            "periode_debut",
            "periode_fin",
            "montant_ht",
        ],
        "classification_version": "vtc_hors_scope_transfer_v1",
        "classification_reason": "abonnement_service_entreprise_conseil",
    }


def apply_on_charges_file(path: Path, candidates: list[dict], months: list[str], apply: bool):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"Invalid items array in {path}")

    existing_keys = {normalize_text(str(it.get("article_source") or "")) for it in items if isinstance(it, dict)}

    added = 0
    for src in candidates:
        out = build_charge_item(src)
        key = normalize_text(out["article_source"])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        items.append(out)
        added += 1

    meta = data.get("meta") or {}
    transfer_block = {
        "updated_at": now_iso(),
        "source_file": VTC_SOURCE_FILE,
        "added_items": added,
        "months": sorted(set(months)),
    }
    meta["vtc_hors_scope_transfer_v1"] = transfer_block
    meta["items_count"] = len(items)
    data["meta"] = meta
    data["items"] = items

    if apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return added, sorted(set(months))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transfer VTC out-of-scope monthly service subscriptions to charges externes base."
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to files.")
    args = parser.parse_args()

    vtc_path = (SCRIPT_DIR / VTC_SOURCE_FILE).resolve()
    vtc_data = json.loads(vtc_path.read_text(encoding="utf-8-sig"))
    candidates, months = extract_candidates(vtc_data)

    print(f"[INFO] candidates_found={len(candidates)}")
    print(f"[INFO] months={sorted(set(months))}")

    for name in CHARGES_FILES:
        path = (SCRIPT_DIR / name).resolve()
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        added, month_list = apply_on_charges_file(path, candidates, months, apply=args.apply)
        print(f"[INFO] file={path.name} added={added} months={month_list}")

    print(f"[INFO] mode={'apply' if args.apply else 'dry_run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
