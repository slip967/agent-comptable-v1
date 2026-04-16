#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

TARGET_FILES = [
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

ARTICLE_PATTERN = re.compile(
    r"^Abonnement aux services d'entreprise\s+[A-ZÉÈÊËÂÀÎÏÔÖÙÛÜÇ]+\s+\d{4}\s+-\s+.*Conseil en entreprise$",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def should_remove(item: dict) -> bool:
    source = str(item.get("article_source") or "").strip()
    source_marker = str(item.get("compte_comptable_source") or "").strip()
    class_marker = str(item.get("classification_version") or "").strip()
    if class_marker == "vtc_hors_scope_transfer_v1":
        return True
    if source_marker == "vtc_hors_scope_transfer_v1" and ARTICLE_PATTERN.match(source):
        return True
    return False


def process_file(path: Path, apply: bool) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError(f"Invalid items in {path}")

    kept = []
    removed = 0
    for item in items:
        if isinstance(item, dict) and should_remove(item):
            removed += 1
            continue
        kept.append(item)

    data["items"] = kept

    meta = data.get("meta") or {}
    meta["items_count"] = len(kept)
    meta["vtc_hors_scope_transfer_revert_v1"] = {
        "updated_at": now_iso(),
        "removed_items": removed,
        "rule": "remove items marked vtc_hors_scope_transfer_v1",
    }
    data["meta"] = meta

    if apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(kept), removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove transferred VTC abonnement rows from charges externes bases.")
    parser.add_argument("--apply", action="store_true", help="Write file changes.")
    args = parser.parse_args()

    for name in TARGET_FILES:
        path = (SCRIPT_DIR / name).resolve()
        if not path.exists():
            print(f"[WARN] missing={path}")
            continue
        kept, removed = process_file(path, apply=args.apply)
        print(f"[INFO] file={path.name} removed={removed} kept={kept}")
    print(f"[INFO] mode={'apply' if args.apply else 'dry_run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
