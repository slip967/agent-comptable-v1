#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

COHERENCE_PATTERNS = [
    "coca",
    "cola",
    "redb",
    "rhum",
    "damois",
    "pelegr",
    "pellegr",
    "mirinda",
    "schwep",
    "chwef",
    "lipton",
    "orangina",
    "heink",
    "heinek",
    "monster",
    "monste",
    "emballag",
    "bock",
]


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def is_coherent_epicerie(item: dict) -> bool:
    article = str(item.get("article_source") or "")
    canon = str(item.get("article_canonique") or "")
    text = normalize_text(f"{article} {canon}")
    return any(pattern in text for pattern in COHERENCE_PATTERNS)


def cleanup_file(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    if not isinstance(items, list):
        return 0, 0

    kept = []
    rejected = list(data.get("a_valider") or [])
    moved = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        if is_coherent_epicerie(item):
            kept.append(item)
        else:
            moved += 1
            row = dict(item)
            row["validation_status"] = "a_revoir_ocr_noise"
            row["validation_reason"] = "label_incoherent_for_epicerie"
            rejected.append(row)

    data["items"] = kept
    data["a_valider"] = rejected

    meta = data.get("meta") or {}
    meta["items_count"] = len(kept)
    meta["cleanup_epicerie_ocr_noise"] = {
        "moved_to_a_valider": moved,
        "kept_items": len(kept),
        "coherence_patterns": COHERENCE_PATTERNS,
    }
    data["meta"] = meta

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(kept), moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Move incoherent OCR epicerie lines from items to a_valider.")
    parser.add_argument(
        "--input",
        action="append",
        default=[
            "base_produits_epicerie_v1.json",
            "base_produits_epicerie_v1_with_accounts.json",
        ],
        help="JSON file to clean (repeatable).",
    )
    args = parser.parse_args()

    for name in args.input:
        path = Path(name)
        if not path.is_absolute():
            path = (SCRIPT_DIR / name).resolve()
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        kept, moved = cleanup_file(path)
        print(f"[OK] file={path} kept={kept} moved_to_a_valider={moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
