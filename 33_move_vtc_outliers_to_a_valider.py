#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
import unicodedata
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

OUTLIER_ARTICLES = {
    "FR COCA COLA 24X33CL",
    "OASIS TROPICAL 24X33CL",
    "OASIS POMME POIRE 24X33CL",
    "COCA COLA CHERRY 24X33CL",
    "Coca Cola",
    "FR FANTA ORANGE 24X33CL",
    "Coca",
    "FANTA COCA AMERICAN 12*355ML",
    "HEINEKEN 20*25CL",
    "HEINEKEN 5D 12X25CL",
    "OASIS TROPICAL/POMME/FRAISE/CASIS/FRA 24*33CL",
    "REDBULL EDITION 24*250ML *",
}


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def resolve_path(name: str) -> Path:
    path = Path(name)
    if path.is_absolute():
        return path
    direct = (Path.cwd() / name).resolve()
    if direct.exists():
        return direct
    return (SCRIPT_DIR / name).resolve()


def process_file(path: Path) -> tuple[int, int, int]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []
    a_valider = payload.get("a_valider") or []

    if not isinstance(items, list):
        items = []
    if not isinstance(a_valider, list):
        a_valider = []

    outlier_keys = {normalize_text(x) for x in OUTLIER_ARTICLES}
    existing_av_keys = {
        normalize_text(str(row.get("article_source") or ""))
        for row in a_valider
        if isinstance(row, dict)
    }

    kept = []
    moved = 0
    already_in_a_valider = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        article = str(row.get("article_source") or "").strip()
        key = normalize_text(article)
        if key in outlier_keys:
            moved += 1
            if key in existing_av_keys:
                already_in_a_valider += 1
                continue
            moved_row = dict(row)
            moved_row["validation_status"] = "a_controler_decision_comptable"
            moved_row["validation_reason"] = "hors_perimetre_vtc_potentiel"
            moved_row["validation_note"] = (
                "Exclu de la base de reference VTC; a traiter a part selon decision comptable."
            )
            a_valider.append(moved_row)
            existing_av_keys.add(key)
        else:
            kept.append(row)

    payload["items"] = kept
    payload["a_valider"] = a_valider

    meta = payload.get("meta") or {}
    meta["items_count"] = len(kept)
    meta["vtc_outliers_to_review"] = {
        "moved_to_a_valider": moved,
        "already_in_a_valider": already_in_a_valider,
        "rule": "manual_outliers_requested_by_accounting",
    }
    payload["meta"] = meta

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(kept), len(a_valider), moved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move known non-VTC outlier article_source rows from items to a_valider."
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[
            "base_produits_vtc_v1.json",
            "base_produits_vtc_v1_with_accounts.json",
        ],
        help="VTC base json path (repeatable).",
    )
    args = parser.parse_args()

    for name in args.input:
        path = resolve_path(name)
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        items_count, a_valider_count, moved = process_file(path)
        print(
            f"[OK] file={path} items={items_count} a_valider={a_valider_count} moved={moved}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
