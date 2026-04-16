#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from collections import defaultdict
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

CARBURANT_HINTS = {
    "diesel",
    "gasoil",
    "essence",
    "carburant",
    "adblue",
    "fuel",
}
DEPLACEMENT_HINTS = {
    "peage",
    "autoroute",
    "parking",
    "stationnement",
    "livraison",
}
ENTRETIEN_HINTS = {
    "vidange",
    "pneu",
    "pneus",
    "entretien",
    "revision",
    "lavage",
    "mecanique",
    "garage",
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


def infer_sous_categorie(article_source: str, article_canonique: str) -> str:
    words = set(tokenize(f"{article_source} {article_canonique}"))
    if words & CARBURANT_HINTS:
        return "carburant"
    if words & DEPLACEMENT_HINTS:
        return "deplacement"
    if words & ENTRETIEN_HINTS:
        return "entretien_vehicule"
    return "autres_exploitation_vtc"


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
    return out[:10]


def build_candidates(reference_json_paths: list[Path], source_clients: list[str]) -> list[dict]:
    by_article: dict[str, dict] = {}

    for ref_path in reference_json_paths:
        payload = json.loads(ref_path.read_text(encoding="utf-8-sig"))
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            source_labels_top = item.get("source_labels_top") or []
            article_source = ""
            if source_labels_top and isinstance(source_labels_top[0], list) and source_labels_top[0]:
                article_source = str(source_labels_top[0][0] or "").strip()

            article_canonique = str(item.get("canonical_label") or "").strip()
            proposed_account = str(item.get("proposed_account") or "").strip()
            if not article_source or not proposed_account:
                continue
            if not proposed_account.startswith("60"):
                continue

            key = normalize_text(article_source)
            if not key:
                continue

            occurrences = int(item.get("occurrences") or 0)
            tva_rate = parse_tva_rate(item.get("tva_rates_top") or [])
            mots_cles = tokenize(article_canonique)[:6]
            ape_context = extract_ape_context(item)
            source_invoice_ids = extract_source_invoice_ids(item)
            sous_categorie = infer_sous_categorie(article_source, article_canonique)
            candidate = {
                "article_source": article_source,
                "article_canonique": article_canonique,
                "categorie": "exploitation_metier",
                "sous_categorie": sous_categorie,
                "tva_rate": tva_rate,
                "mots_cles": mots_cles,
                "fournisseur_type": "prestataire_transport",
                "ape_context": ape_context,
                "notes": (
                    "Pre-rempli auto depuis invoice_form clients VTC "
                    f"{','.join(source_clients)} (occurrences={occurrences})"
                ),
                "source_invoice_ids": source_invoice_ids,
                "compte_comptable": proposed_account,
                "compte_comptable_source": "invoice_form_reference_v1",
                "compte_comptable_match_score": 250 + min(occurrences, 50),
                "compte_comptable_match_reason": "from_reference_exploitation_vtc_multi_client",
                "_occurrences": occurrences,
            }

            previous = by_article.get(key)
            if previous is None or int(previous.get("_occurrences") or 0) < occurrences:
                by_article[key] = candidate
            elif previous is not None:
                merged_ids = list(previous.get("source_invoice_ids") or [])
                for invoice_id in source_invoice_ids:
                    if invoice_id not in merged_ids:
                        merged_ids.append(invoice_id)
                previous["source_invoice_ids"] = merged_ids[:10]

    out = list(by_article.values())
    out.sort(key=lambda row: (-int(row.get("_occurrences") or 0), row.get("article_source") or ""))
    return out


def merge_into_base(base_path: Path, candidates: list[dict], source_clients: list[str]) -> tuple[int, int]:
    payload = json.loads(base_path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []

    existing = {normalize_text(str(row.get("article_source") or "")) for row in items if isinstance(row, dict)}
    added = 0
    for candidate in candidates:
        key = normalize_text(str(candidate.get("article_source") or ""))
        if not key or key in existing:
            continue
        row = dict(candidate)
        row.pop("_occurrences", None)
        items.append(row)
        existing.add(key)
        added += 1

    payload["items"] = items
    meta = payload.get("meta") or {}
    meta["items_count"] = len(items)
    meta["client_siren"] = "multi"
    meta["partition_prefix"] = "multi"
    meta["vtc_multi_client_enrichment_v1"] = {
        "source_clients": source_clients,
        "added_items": added,
        "candidate_items": len(candidates),
        "rule": "append new article_source not already present (normalized exact), accounts 60* only",
    }
    payload["meta"] = meta

    base_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(items), added


def resolve_path(name: str) -> Path:
    path = Path(name)
    if path.is_absolute():
        return path
    direct = (Path.cwd() / name).resolve()
    if direct.exists():
        return direct
    return (SCRIPT_DIR / name).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich VTC bases from multiple exploitation reference files.")
    parser.add_argument(
        "--reference-json",
        action="append",
        required=True,
        help="Reference exploitation json path (repeatable).",
    )
    parser.add_argument("--source-clients", required=True, help="Comma-separated siren list used for metadata.")
    parser.add_argument("--base-json", default="base_produits_vtc_v1.json")
    parser.add_argument("--base-json-with-accounts", default="base_produits_vtc_v1_with_accounts.json")
    args = parser.parse_args()

    reference_paths = [resolve_path(name) for name in args.reference_json]
    for path in reference_paths:
        if not path.exists():
            raise SystemExit(f"Reference file missing: {path}")

    source_clients = [part.strip() for part in str(args.source_clients or "").split(",") if part.strip()]
    base_json = resolve_path(args.base_json)
    base_json_wa = resolve_path(args.base_json_with_accounts)
    if not base_json.exists() or not base_json_wa.exists():
        raise SystemExit("Base VTC JSON file missing.")

    candidates = build_candidates(reference_paths, source_clients=source_clients)
    total_v1, added_v1 = merge_into_base(base_json, candidates, source_clients=source_clients)
    total_wa, added_wa = merge_into_base(base_json_wa, candidates, source_clients=source_clients)

    print(f"[INFO] candidates={len(candidates)}")
    print(f"[OK] file={base_json} total_items={total_v1} added_items={added_v1}")
    print(f"[OK] file={base_json_wa} total_items={total_wa} added_items={added_wa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
