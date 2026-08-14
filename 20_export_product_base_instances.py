#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path

from product_base_instances_lib import build_instance_doc, load_source

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "product_base_instances"


def export_instances(source: Path, output_dir: Path) -> tuple[Path, int]:
    meta, items = load_source(source)
    profile_id = str(meta.get("profile_id") or source.stem).strip()
    target_dir = output_dir / profile_id
    target_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        file_name, payload = build_instance_doc(
            source_file=source,
            meta=meta,
            item=item,
            index=index,
        )
        (target_dir / file_name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written += 1

    return target_dir, written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exporte une base produits v1 en un fichier JSON par article_source."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Fichier source base_produits_*_v1.json ou base_charges_externes_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Dossier racine de sortie pour les instances JSON.",
    )
    args = parser.parse_args()

    source = Path(args.input).resolve()
    if not source.exists():
        raise SystemExit(f"Fichier introuvable: {source}")
    if source.name.endswith("_with_accounts.json"):
        raise SystemExit("Utilise un fichier v1.json simple, pas un _with_accounts.json.")

    output_dir = Path(args.output_dir).resolve()
    target_dir, written = export_instances(source, output_dir)
    print(f"[OK] source={source.name}")
    print(f"[OK] target_dir={target_dir}")
    print(f"[OK] files_written={written}")


if __name__ == "__main__":
    main()
