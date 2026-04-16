#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent

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


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def normalize_rate(value) -> str:
    try:
        return f"{float(value):.1f}"
    except Exception:
        return ""


def resolve_existing_path(name: str) -> Path:
    direct = Path(name)
    if direct.exists():
        return direct.resolve()
    fallback = SCRIPT_DIR / name
    if fallback.exists():
        return fallback.resolve()
    return fallback.resolve()


@dataclass
class ReferenceMatch:
    canonical_norm: str
    source_labels_norm: set[str]
    source_labels_main: list[str]
    proposed_account: str
    category: str
    tva_rates: set[str]
    invoice_ids: set[str]
    occurrences: int


def load_reference_items(path: Path) -> list[ReferenceMatch]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    out: list[ReferenceMatch] = []
    for item in data.get("items") or []:
        source_labels_top = item.get("source_labels_top") or []
        examples = item.get("examples") or []
        source_labels_main = [str(entry[0]).strip() for entry in source_labels_top if isinstance(entry, list) and entry]
        source_labels_norm = {normalize_text(label) for label in source_labels_main if label}
        invoice_ids = {
            str(example.get("invoice_id") or "").strip()
            for example in examples
            if isinstance(example, dict) and str(example.get("invoice_id") or "").strip()
        }
        tva_rates = set()
        for entry in item.get("tva_rates_top") or []:
            if isinstance(entry, list) and entry:
                tva_rates.add(normalize_rate(entry[0]))

        proposed_account = str(item.get("proposed_account") or "").strip()
        if not proposed_account:
            continue

        out.append(
            ReferenceMatch(
                canonical_norm=normalize_text(item.get("canonical_label") or ""),
                source_labels_norm=source_labels_norm,
                source_labels_main=source_labels_main,
                proposed_account=proposed_account,
                category=str(item.get("category") or "").strip(),
                tva_rates=tva_rates,
                invoice_ids=invoice_ids,
                occurrences=int(item.get("occurrences") or 0),
            )
        )
    return out


def build_indexes(refs: list[ReferenceMatch]):
    by_invoice_id: dict[str, list[int]] = defaultdict(list)
    by_source_label: dict[str, list[int]] = defaultdict(list)
    by_canonical: dict[str, list[int]] = defaultdict(list)

    for idx, ref in enumerate(refs):
        for invoice_id in ref.invoice_ids:
            by_invoice_id[invoice_id].append(idx)
        for label in ref.source_labels_norm:
            by_source_label[label].append(idx)
        if ref.canonical_norm:
            by_canonical[ref.canonical_norm].append(idx)

    return by_invoice_id, by_source_label, by_canonical


def score_match(item: dict, ref: ReferenceMatch, expected_category: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    item_source_norm = normalize_text(item.get("article_source") or "")
    item_canon_norm = normalize_text(item.get("article_canonique") or "")
    item_invoice_ids = {str(value).strip() for value in item.get("source_invoice_ids") or [] if str(value).strip()}
    item_tva = normalize_rate(item.get("tva_rate"))

    overlap = len(item_invoice_ids & ref.invoice_ids)
    if overlap:
        score += overlap * 120
        reasons.append(f"invoice_id_overlap={overlap}")

    if item_source_norm and item_source_norm in ref.source_labels_norm:
        score += 100
        reasons.append("article_source_exact")

    if item_source_norm and item_source_norm == ref.canonical_norm:
        score += 60
        reasons.append("article_source_equals_canonical")

    if item_canon_norm and item_canon_norm == ref.canonical_norm:
        score += 50
        reasons.append("article_canonique_exact")

    if item_tva and item_tva in ref.tva_rates:
        score += 20
        reasons.append("tva_match")

    if expected_category and ref.category == expected_category:
        score += 10
        reasons.append("category_match")

    if ref.occurrences:
        score += min(ref.occurrences, 10)
        reasons.append("occurrences_bonus")

    return score, reasons


def infer_reference_file(meta: dict) -> str:
    client_siren = str(meta.get("client_siren") or "").strip()
    metier = str(meta.get("metier") or "").strip().lower()

    prefix = f"v1_{client_siren}_" if client_siren else ""
    if metier == "global":
        return f"{prefix}reference_base_charges_externes_v1.json"
    return f"{prefix}reference_base_exploitation_v1.json"


def expected_category(meta: dict) -> str:
    return "charges_externes" if str(meta.get("metier") or "").strip().lower() == "global" else "exploitation_metier"


def attach_accounts_to_file(path: Path, out_path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    meta = data.get("meta") or {}
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"Invalid items format in {path.name}")

    ref_name = infer_reference_file(meta)
    ref_path = resolve_existing_path(ref_name)
    refs = load_reference_items(ref_path)
    by_invoice_id, by_source_label, by_canonical = build_indexes(refs)
    category_expected = expected_category(meta)

    matched = 0
    unmatched = 0
    already_present = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("compte_comptable") or "").strip():
            already_present += 1
            continue

        item_source_norm = normalize_text(item.get("article_source") or "")
        item_canon_norm = normalize_text(item.get("article_canonique") or "")
        item_invoice_ids = {str(value).strip() for value in item.get("source_invoice_ids") or [] if str(value).strip()}

        candidate_ids: set[int] = set()
        for invoice_id in item_invoice_ids:
            candidate_ids.update(by_invoice_id.get(invoice_id, []))
        candidate_ids.update(by_source_label.get(item_source_norm, []))
        candidate_ids.update(by_canonical.get(item_canon_norm, []))
        candidate_ids.update(by_canonical.get(item_source_norm, []))

        best_ref: ReferenceMatch | None = None
        best_score = -1
        best_reasons: list[str] = []
        for idx in candidate_ids:
            ref = refs[idx]
            score, reasons = score_match(item, ref, category_expected)
            if score > best_score:
                best_ref = ref
                best_score = score
                best_reasons = reasons

        if best_ref and best_score > 0:
            item["compte_comptable"] = best_ref.proposed_account
            item["compte_comptable_source"] = "invoice_form_reference_v1"
            item["compte_comptable_match_score"] = best_score
            item["compte_comptable_match_reason"] = ", ".join(best_reasons)
            matched += 1
        else:
            unmatched += 1

    meta["accounts_enrichment"] = {
        "reference_file": ref_name,
        "matched_items": matched,
        "unmatched_items": unmatched,
        "already_present": already_present,
    }
    data["meta"] = meta
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "matched": matched,
        "unmatched": unmatched,
        "already_present": already_present,
        "total_items": len(items),
    }


def iter_input_paths(names: Iterable[str]) -> list[Path]:
    return [resolve_existing_path(name) for name in names]


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach compte_comptable to product bases from V1 invoice_form references.")
    parser.add_argument("--input", action="append", default=[], help="Input base JSON file. Can be repeated.")
    parser.add_argument("--output-suffix", default="_with_accounts", help="Suffix for output files when not using --in-place.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input files.")
    args = parser.parse_args()

    input_paths = iter_input_paths(args.input or BASE_FILES)
    for path in input_paths:
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        out_path = path if args.in_place else path.with_name(f"{path.stem}{args.output_suffix}{path.suffix}")
        stats = attach_accounts_to_file(path, out_path)
        print(
            "[OK] file={file} matched={matched} unmatched={unmatched} already_present={already_present} total={total}".format(
                file=out_path,
                matched=stats["matched"],
                unmatched=stats["unmatched"],
                already_present=stats["already_present"],
                total=stats["total_items"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
