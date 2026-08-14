#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from product_base_instances_lib import build_instances_from_source


ROOT = Path(__file__).resolve().parent
DEFAULT_ZIP = Path(r"C:\Users\Dell\Downloads\bases_corrected_v3_ready_to_inject.zip")
OUTPUT_DIR = ROOT / "prepared_corrected_v3_injection"
MANIFEST_PATH = OUTPUT_DIR / "manifest_corrected_v3_injection.json"
README_PATH = OUTPUT_DIR / "README_ready_to_inject.md"

EXPECTED_JSONS = {
    "base_produits_boucherie_corrected_v3.json",
    "base_produits_boulangerie_corrected_v3.json",
    "base_produits_btp_corrected_v3.json",
    "base_produits_epicerie_corrected_v3.json",
    "base_produits_restaurant_corrected_v3.json",
    "base_produits_transport_corrected_v3.json",
    "base_produits_vtc_corrected_v3.json",
    "base_charges_externes_corrected_v3.json",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ensure_clean_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def extract_zip(zip_path: Path, output_dir: Path) -> list[Path]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(output_dir)
    return sorted(output_dir.iterdir())


def build_manifest(output_dir: Path, zip_path: Path) -> dict:
    json_files = sorted([path for path in output_dir.glob("*.json") if path.name in EXPECTED_JSONS])
    files_summary = []
    total_instances = 0

    for path in json_files:
        payload = load_json(path)
        items = payload.get("items") or []
        a_valider = payload.get("a_valider") or []
        meta = payload.get("meta") or {}
        _, docs = build_instances_from_source(path)
        total_instances += len(docs)
        files_summary.append(
            {
                "file": path.name,
                "metier": meta.get("metier"),
                "profile_id": meta.get("profile_id"),
                "partition_prefix": meta.get("partition_prefix"),
                "items_count": len(items),
                "a_valider_count": len(a_valider),
                "instance_docs_count": len(docs),
            }
        )

    missing = sorted(EXPECTED_JSONS - {row["file"] for row in files_summary})
    extras = sorted(
        path.name
        for path in output_dir.glob("*.json")
        if path.name not in EXPECTED_JSONS
    )

    return {
        "generated_from": "74_extract_corrected_v3_for_injection.py",
        "zip_source": str(zip_path),
        "output_dir": str(output_dir),
        "expected_json_files": sorted(EXPECTED_JSONS),
        "missing_json_files": missing,
        "extra_json_files": extras,
        "files_summary": files_summary,
        "total_json_files": len(files_summary),
        "total_instance_docs": total_instances,
    }


def build_readme(manifest: dict) -> str:
    lines = [
        "# Corrected V3 Ready To Inject",
        "",
        "Ce dossier provient de l'archive `bases_corrected_v3_ready_to_inject.zip` extraite localement.",
        "",
        "## Contenu",
        "",
        f"- total_json_files: `{manifest['total_json_files']}`",
        f"- total_instance_docs: `{manifest['total_instance_docs']}`",
        "",
    ]

    for row in manifest["files_summary"]:
        lines.append(
            f"- `{row['file']}`: items=`{row['items_count']}` a_valider=`{row['a_valider_count']}` "
            f"instances=`{row['instance_docs_count']}` metier=`{row['metier']}`"
        )

    lines.extend(
        [
            "",
            "## Commandes prêtes",
            "",
            "Dry-run :",
            "",
            "```bash",
            "python 22_import_product_base_instances.py --db ayasmine_test2 "
            "--pattern prepared_corrected_v3_injection/base_produits_*_corrected_v3.json "
            "prepared_corrected_v3_injection/base_charges_externes_corrected_v3.json --dry-run",
            "```",
            "",
            "Import réel :",
            "",
            "```bash",
            "python 22_import_product_base_instances.py --db ayasmine_test2 "
            "--pattern prepared_corrected_v3_injection/base_produits_*_corrected_v3.json "
            "prepared_corrected_v3_injection/base_charges_externes_corrected_v3.json",
            "```",
            "",
            "## Notes",
            "",
            "- Les fichiers d'origine du workspace ne sont pas modifiés.",
            "- L'import consommera seulement les `items` actifs.",
            "- Les fichiers `_with_accounts` ne sont pas nécessaires pour le script d'import actuel.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait et prépare l'archive corrected_v3 pour injection.")
    parser.add_argument("--zip", default=str(DEFAULT_ZIP), help="Chemin de l'archive ZIP.")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise SystemExit(f"Archive introuvable: {zip_path}")

    ensure_clean_output_dir(OUTPUT_DIR)
    extract_zip(zip_path, OUTPUT_DIR)
    manifest = build_manifest(OUTPUT_DIR, zip_path)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    README_PATH.write_text(build_readme(manifest), encoding="utf-8")

    print(f"[OK] output_dir={OUTPUT_DIR}")
    print(f"[OK] manifest={MANIFEST_PATH.name}")
    print(f"[OK] readme={README_PATH.name}")
    print(f"[OK] total_json_files={manifest['total_json_files']} total_instance_docs={manifest['total_instance_docs']}")
    if manifest["missing_json_files"]:
        print(f"[WARN] missing_json_files={manifest['missing_json_files']}")
    if manifest["extra_json_files"]:
        print(f"[INFO] extra_json_files={manifest['extra_json_files']}")


if __name__ == "__main__":
    main()
