#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


LETTER_RANGE = "A-Za-zÀ-ÿ"


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return collapse_spaces(value)


def replace_ocr_zero_as_letter(value: str) -> str:
    # 0 at start of an alpha token: 0EUFS -> OEUFS
    value = re.sub(rf"(?<=\b)0(?=[{LETTER_RANGE}])", "O", value)
    # 0 inside alpha token: C0CA -> COCA
    value = re.sub(rf"(?<=[{LETTER_RANGE}])0(?=[{LETTER_RANGE}])", "O", value)
    # trailing 0 after alpha token: AR0 -> ARO
    value = re.sub(rf"\b([{LETTER_RANGE}]+)0\b", r"\1O", value)
    return value


def normalize_article_source(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u00A0", " ").replace("\t", " ")
    text = collapse_spaces(text)
    text = replace_ocr_zero_as_letter(text)
    return collapse_spaces(text)


def normalize_keywords(keywords: list) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in keywords or []:
        cleaned = normalize_text(normalize_article_source(str(raw or "")))
        for tok in cleaned.split():
            if len(tok) <= 1:
                continue
            if tok in seen:
                continue
            seen.add(tok)
            out.append(tok)
    return out


def process_row(row: dict) -> tuple[bool, bool, bool]:
    changed_source = False
    changed_canon = False
    changed_keywords = False

    old_source = str(row.get("article_source") or "")
    new_source = normalize_article_source(old_source)
    if new_source != old_source:
        row["article_source"] = new_source
        changed_source = True
    else:
        row["article_source"] = old_source

    old_canon = str(row.get("article_canonique") or "")
    if old_canon.strip():
        new_canon = normalize_text(normalize_article_source(old_canon))
    else:
        new_canon = normalize_text(new_source)
    if new_canon != old_canon:
        row["article_canonique"] = new_canon
        changed_canon = True
    else:
        row["article_canonique"] = old_canon

    old_keywords = list(row.get("mots_cles") or [])
    new_keywords = normalize_keywords(old_keywords)
    if not new_keywords:
        new_keywords = [tok for tok in new_canon.split() if len(tok) > 1][:6]
    if new_keywords != old_keywords:
        row["mots_cles"] = new_keywords
        changed_keywords = True
    else:
        row["mots_cles"] = old_keywords

    return changed_source, changed_canon, changed_keywords


def normalize_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    a_valider = data.get("a_valider") or []

    source_updates = 0
    canon_updates = 0
    keywords_updates = 0
    rows_touched = 0

    for bucket in (items, a_valider):
        if not isinstance(bucket, list):
            continue
        for row in bucket:
            if not isinstance(row, dict):
                continue
            s_changed, c_changed, k_changed = process_row(row)
            if s_changed:
                source_updates += 1
            if c_changed:
                canon_updates += 1
            if k_changed:
                keywords_updates += 1
            if s_changed or c_changed or k_changed:
                rows_touched += 1

    data["items"] = items
    data["a_valider"] = a_valider

    meta = data.get("meta") or {}
    meta["article_source_normalization_epicerie_v1"] = {
        "updated_at": now_iso(),
        "rows_touched": rows_touched,
        "article_source_updated": source_updates,
        "article_canonique_updated": canon_updates,
        "mots_cles_updated": keywords_updates,
    }
    meta["items_count"] = len(items)
    data["meta"] = meta

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "rows_touched": rows_touched,
        "article_source_updated": source_updates,
        "article_canonique_updated": canon_updates,
        "mots_cles_updated": keywords_updates,
        "items_count": len(items),
        "a_valider_count": len(a_valider) if isinstance(a_valider, list) else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize epicerie article_source fields (OCR zeros, spacing) and align canon/keywords."
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[
            "base_produits_epicerie_v1.json",
            "base_produits_epicerie_v1_with_accounts.json",
        ],
        help="Input JSON file(s). Repeat argument to add files.",
    )
    args = parser.parse_args()

    for name in args.input:
        path = Path(name)
        if not path.is_absolute():
            path = (SCRIPT_DIR / name).resolve()
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        stats = normalize_file(path)
        print(
            f"[OK] file={path} rows_touched={stats['rows_touched']} "
            f"article_source_updated={stats['article_source_updated']} "
            f"article_canonique_updated={stats['article_canonique_updated']} "
            f"mots_cles_updated={stats['mots_cles_updated']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
