#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


STOP_WORDS = {
    "de",
    "du",
    "des",
    "la",
    "le",
    "les",
    "a",
    "au",
    "aux",
    "et",
    "en",
    "sur",
    "pour",
    "par",
    "avec",
    "x",
}

PACKAGING_KEYWORDS = {
    "emballage",
    "emballages",
    "film",
    "sachet",
    "sachets",
    "sac",
    "sacs",
    "barquette",
    "barquettes",
    "carton",
    "cartons",
    "boite",
    "boites",
    "gobelet",
    "gobelets",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def tokenize(value: str) -> list[str]:
    return [tok for tok in normalize_text(value).split() if tok and tok not in STOP_WORDS]


def parse_tva_rate(tva_rates_top: list) -> float | None:
    if not isinstance(tva_rates_top, list) or not tva_rates_top:
        return None
    first = tva_rates_top[0]
    if not isinstance(first, list) or not first:
        return None
    try:
        return float(first[0])
    except Exception:
        return None


def infer_sous_categorie(proposed_account: str, article_source: str, article_canonique: str) -> str:
    account = str(proposed_account or "").strip()
    tokens = set(tokenize(f"{article_source} {article_canonique}"))
    if account.startswith(("6062", "6063")):
        return "emballage"
    if tokens & PACKAGING_KEYWORDS:
        return "emballage"
    return "matiere_premiere"


def extract_ape_context(item: dict) -> list[str]:
    out = []
    for entry in item.get("ape_supplier_top") or []:
        if not isinstance(entry, list) or not entry:
            continue
        ape = str(entry[0] or "").strip().upper()
        if ape and ape not in out:
            out.append(ape)
    return out[:3]


def extract_source_invoice_ids(item: dict) -> list[str]:
    out = []
    for ex in item.get("examples") or []:
        if not isinstance(ex, dict):
            continue
        invoice_id = str(ex.get("invoice_id") or "").strip()
        if invoice_id and invoice_id not in out:
            out.append(invoice_id)
    return out[:3]


def build_items(reference_items: list[dict]) -> list[dict]:
    items = []
    for ref in reference_items:
        if not isinstance(ref, dict):
            continue

        source_labels_top = ref.get("source_labels_top") or []
        article_source = ""
        if source_labels_top and isinstance(source_labels_top[0], list) and source_labels_top[0]:
            article_source = str(source_labels_top[0][0] or "").strip()

        article_canonique = str(ref.get("canonical_label") or "").strip()
        proposed_account = str(ref.get("proposed_account") or "").strip()
        if not article_source or not proposed_account:
            continue

        sous_categorie = infer_sous_categorie(proposed_account, article_source, article_canonique)
        tva_rate = parse_tva_rate(ref.get("tva_rates_top") or [])
        mots_cles = tokenize(article_canonique)[:6]
        ape_context = extract_ape_context(ref)
        source_invoice_ids = extract_source_invoice_ids(ref)
        occurrences = int(ref.get("occurrences") or 0)

        items.append(
            {
                "article_source": article_source,
                "article_canonique": article_canonique,
                "categorie": "exploitation_metier",
                "sous_categorie": sous_categorie,
                "tva_rate": tva_rate,
                "mots_cles": mots_cles,
                "fournisseur_type": "fournisseur alimentaire" if sous_categorie == "matiere_premiere" else "fournisseur non alimentaire",
                "ape_context": ape_context,
                "notes": f"Pre-rempli auto depuis reference exploitation speedmarket (occurrences={occurrences})",
                "source_invoice_ids": source_invoice_ids,
                "compte_comptable": proposed_account,
                "compte_comptable_source": "invoice_form_reference_v1",
                "compte_comptable_match_score": 250 + min(occurrences, 50),
                "compte_comptable_match_reason": "from_reference_exploitation_v1",
            }
        )

    # Deduplicate by exact article_source while keeping first (highest occurrence in reference order).
    dedup = []
    seen = set()
    for it in items:
        key = normalize_text(it.get("article_source") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        dedup.append(it)
    return dedup


def main() -> int:
    parser = argparse.ArgumentParser(description="Build base_produits_epicerie_v1.json from exploitation reference JSON.")
    parser.add_argument(
        "--reference-json",
        default="v1_827722265_reference_base_exploitation_v1.json",
        help="Input reference exploitation JSON.",
    )
    parser.add_argument("--client-siren", default="827722265")
    parser.add_argument("--partition-prefix", default="fr_bd_827722265")
    parser.add_argument("--out-json", default="base_produits_epicerie_v1.json")
    parser.add_argument("--out-with-accounts", default="base_produits_epicerie_v1_with_accounts.json")
    args = parser.parse_args()

    reference_path = Path(args.reference_json)
    if not reference_path.is_absolute():
        reference_path = (SCRIPT_DIR / reference_path).resolve()
    if not reference_path.exists():
        raise SystemExit(f"Reference file not found: {reference_path}")

    ref_data = json.loads(reference_path.read_text(encoding="utf-8-sig"))
    ref_items = ref_data.get("items") or []
    items = build_items(ref_items)

    meta = {
        "profile_id": "produits_epicerie_v1",
        "metier": "epicerie",
        "client_siren": str(args.client_siren).strip(),
        "partition_prefix": str(args.partition_prefix).strip(),
        "version": "v1",
        "status": "draft",
        "source_note": "Pre-rempli automatiquement depuis invoice_form CouchDB; validation metier requise.",
        "generated_at": now_iso(),
        "items_count": len(items),
        "cleanup_note": "Nettoyage manuel: suppression charges_externes en base metier + dedoublonnage produits.",
        "source_invoice_ids_note": "Jusqu a 3 invoice_id source par article_source depuis invoice_form.",
        "accounts_enrichment": {
            "reference_file": reference_path.name,
            "matched_items": len(items),
            "unmatched_items": 0,
            "already_present": 0,
        },
    }

    payload = {
        "meta": meta,
        "items": items,
        "a_valider": [],
    }

    out_json = Path(args.out_json)
    if not out_json.is_absolute():
        out_json = (SCRIPT_DIR / out_json).resolve()
    out_with_accounts = Path(args.out_with_accounts)
    if not out_with_accounts.is_absolute():
        out_with_accounts = (SCRIPT_DIR / out_with_accounts).resolve()

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_with_accounts.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[OK] reference={reference_path}")
    print(f"[OK] items={len(items)}")
    print(f"[OK] json={out_json}")
    print(f"[OK] json_with_accounts={out_with_accounts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
