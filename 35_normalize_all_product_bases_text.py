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
ALLOWED_DISPLAY_CHARS_RE = re.compile(r"[^0-9A-Za-zÀ-ÿ\s/\-.,:()']")
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
    value = re.sub(rf"(?<=\b)0(?=[{LETTER_RANGE}])", "O", value)
    value = re.sub(rf"(?<=[{LETTER_RANGE}])0(?=[{LETTER_RANGE}])", "O", value)
    value = re.sub(rf"\b([{LETTER_RANGE}]+)0\b", r"\1O", value)
    return value


def sanitize_display_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u00A0", " ").replace("\t", " ")
    text = collapse_spaces(text)
    text = replace_ocr_zero_as_letter(text)
    text = ALLOWED_DISPLAY_CHARS_RE.sub(" ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+([,.:;])", r"\1", text)
    text = re.sub(r"\)\.\)", "))", text)
    text = re.sub(r"[,.:;]\)$", ")", text)
    text = re.sub(r"\){2,}", ")", text)
    text = re.sub(r"([,.:;]){2,}", r"\1", text)
    text = re.sub(r"[,.:;]+$", "", text)
    text = collapse_spaces(text)
    return text


def build_keywords(article_canonique: str, existing_keywords: list) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for raw in existing_keywords or []:
        cleaned = normalize_text(sanitize_display_text(str(raw or "")))
        for tok in cleaned.split():
            if len(tok) <= 1 or tok in STOP_WORDS:
                continue
            if tok in seen:
                continue
            seen.add(tok)
            out.append(tok)

    if out:
        return out[:10]

    rebuilt = []
    for tok in article_canonique.split():
        if len(tok) <= 1 or tok in STOP_WORDS:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        rebuilt.append(tok)
    return rebuilt[:10]


def normalize_row(row: dict) -> tuple[bool, bool, bool]:
    source_changed = False
    canon_changed = False
    keywords_changed = False

    old_source = str(row.get("article_source") or "")
    new_source = sanitize_display_text(old_source)
    if new_source != old_source:
        row["article_source"] = new_source
        source_changed = True
    else:
        row["article_source"] = old_source

    old_canon = str(row.get("article_canonique") or "")
    new_canon = normalize_text(new_source) if new_source else normalize_text(old_canon)
    if new_canon != old_canon:
        row["article_canonique"] = new_canon
        canon_changed = True
    else:
        row["article_canonique"] = old_canon

    old_keywords = list(row.get("mots_cles") or [])
    new_keywords = build_keywords(row["article_canonique"], old_keywords)
    if new_keywords != old_keywords:
        row["mots_cles"] = new_keywords
        keywords_changed = True
    else:
        row["mots_cles"] = old_keywords

    return source_changed, canon_changed, keywords_changed


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
            s_changed, c_changed, k_changed = normalize_row(row)
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
    meta["text_normalization_v2"] = {
        "updated_at": now_iso(),
        "rows_touched": rows_touched,
        "article_source_updated": source_updates,
        "article_canonique_updated": canon_updates,
        "mots_cles_updated": keywords_updates,
        "rule": "remove special chars (including % * +), fix OCR 0/O in words, normalize canon + keywords",
    }
    meta["items_count"] = len(items) if isinstance(items, list) else 0
    data["meta"] = meta

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "rows_touched": rows_touched,
        "article_source_updated": source_updates,
        "article_canonique_updated": canon_updates,
        "mots_cles_updated": keywords_updates,
    }


def default_product_files() -> list[str]:
    out = []
    for p in sorted(SCRIPT_DIR.glob("base_produits_*_v1.json")):
        out.append(str(p))
    for p in sorted(SCRIPT_DIR.glob("base_produits_*_v1_with_accounts.json")):
        out.append(str(p))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize all product metier bases (article_source/article_canonique/mots_cles)."
    )
    parser.add_argument(
        "--input",
        action="append",
        default=None,
        help="Input JSON file(s). If omitted, all base_produits_* files are processed.",
    )
    args = parser.parse_args()

    paths = args.input or default_product_files()
    if not paths:
        print("[WARN] no files matched.")
        return 0

    for name in paths:
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
