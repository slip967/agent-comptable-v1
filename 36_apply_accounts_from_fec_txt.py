#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


DEFAULT_FEC_FILES = {
    "904981941": r"c:\Users\Dell\Downloads\904981941FEC20241231.txt",
    "839181104": r"c:\Users\Dell\Downloads\839181104FEC20241231.txt",
    "844082156": r"c:\Users\Dell\Downloads\844082156FEC20241231.txt",
}

DEFAULT_REFERENCE_FILES = {
    "904981941": "v1_904981941_reference_base_exploitation_v1.json",
    "839181104": "v1_839181104_reference_base_exploitation_v1.json",
    "844082156": "v1_844082156_reference_base_exploitation_v1.json",
}

TARGETS = [
    {"base": "epicerie", "sirens": {"904981941"}, "files": ["base_produits_epicerie_v1.json", "base_produits_epicerie_v1_with_accounts.json"]},
    {"base": "vtc", "sirens": {"839181104", "844082156"}, "files": ["base_produits_vtc_v1.json", "base_produits_vtc_v1_with_accounts.json"]},
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def normalize_invoice_number(value: str) -> str:
    text = (value or "").strip().upper()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"^(FACTURE|FACT|FAC|INVOICE|INV|F)(?=[A-Z0-9])", "", text)
    text = re.sub(r"[^A-Z0-9]+", "", text)
    if text.isdigit():
        text = text.lstrip("0") or "0"
    return text


def normalize_fec_date(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return ""


def normalize_ref_date(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 10 and raw[2] == "/" and raw[5] == "/":
        return f"{raw[6:10]}-{raw[3:5]}-{raw[0:2]}"
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return raw
    return ""


def normalize_account(value: Any) -> str:
    return str(value or "").strip()


def is_relevant_account(account: str) -> bool:
    # Keep expense accounts from FEC (class 6 only).
    return bool(account) and account.isdigit() and account.startswith("6")


def normalize_journal_code(value: str) -> str:
    return (value or "").strip().strip("[]").upper()


def read_reference_invoice_index(path: Path, siren: str):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    key_to_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    num_to_ids: dict[str, set[str]] = defaultdict(set)
    id_to_num_date: dict[str, tuple[str, str]] = {}

    for item in data.get("items") or []:
        for ex in item.get("examples") or []:
            invoice_id = str(ex.get("invoice_id") or "").strip()
            inv_num = normalize_invoice_number(str(ex.get("invoice_number") or ""))
            inv_date = normalize_ref_date(str(ex.get("invoice_date") or ""))
            if not invoice_id or not inv_num:
                continue
            if not invoice_id.startswith(f"fr_bd_{siren}:"):
                continue
            if inv_date:
                key_to_ids[(inv_num, inv_date)].add(invoice_id)
            num_to_ids[inv_num].add(invoice_id)
            id_to_num_date[invoice_id] = (inv_num, inv_date)
    return key_to_ids, num_to_ids, id_to_num_date


def read_fec_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        for row in reader:
            journal_code = normalize_journal_code(str(row.get("JournalCode") or ""))
            journal_type = str(row.get("JournalType") or "").strip().lower()
            if journal_code != "AC" and "achat" not in journal_type:
                continue
            account = normalize_account(row.get("CompteNum"))
            if not is_relevant_account(account):
                continue
            num_doc = normalize_invoice_number(str(row.get("NumDoc") or ""))
            piece_ref = normalize_invoice_number(str(row.get("PieceRef") or ""))
            inv_num = num_doc or piece_ref
            if not inv_num:
                continue
            inv_date = normalize_fec_date(str(row.get("PieceDate") or ""))
            rows.append(
                {
                    "invoice_number_norm": inv_num,
                    "invoice_date_iso": inv_date,
                    "account": account,
                }
            )
    return rows


def build_invoice_account_counters(siren: str, fec_path: Path, ref_path: Path):
    key_to_ids, num_to_ids, _ = read_reference_invoice_index(ref_path, siren)
    fec_rows = read_fec_rows(fec_path)
    counters_by_invoice: dict[str, Counter] = defaultdict(Counter)

    matched_by_num_date = 0
    matched_by_num_only = 0
    unmatched = 0

    for row in fec_rows:
        inv_num = row["invoice_number_norm"]
        inv_date = row["invoice_date_iso"]
        account = row["account"]

        targets: set[str] = set()
        if inv_num and inv_date:
            targets = set(key_to_ids.get((inv_num, inv_date), set()))
            if targets:
                matched_by_num_date += 1
        if not targets and inv_num:
            num_ids = set(num_to_ids.get(inv_num, set()))
            if len(num_ids) == 1:
                targets = num_ids
                matched_by_num_only += 1
        if not targets:
            unmatched += 1
            continue
        for invoice_id in targets:
            counters_by_invoice[invoice_id][account] += 1

    stats = {
        "siren": siren,
        "fec_rows_considered": len(fec_rows),
        "matched_by_num_date_rows": matched_by_num_date,
        "matched_by_num_only_rows": matched_by_num_only,
        "unmatched_rows": unmatched,
        "invoice_ids_with_signal": len(counters_by_invoice),
    }
    return counters_by_invoice, stats


def pick_best_account(source_invoice_ids: list[str], counters_by_invoice: dict[str, Counter]):
    aggregate = Counter()
    used = []
    for invoice_id in source_invoice_ids:
        key = str(invoice_id or "").strip()
        if not key:
            continue
        counter = counters_by_invoice.get(key)
        if not counter:
            continue
        used.append(key)
        aggregate.update(counter)
    if not aggregate:
        return "", 0.0, 0, 0, used
    ranked = aggregate.most_common()
    top_account, top_votes = ranked[0]
    total = sum(aggregate.values())
    confidence = (top_votes / total) if total else 0.0
    return top_account, confidence, top_votes, total, used


def update_base_file(path: Path, allowed_sirens: set[str], counters_by_invoice: dict[str, Counter], min_confidence: float):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    changed = 0
    unchanged = 0
    no_signal = 0
    skipped_outside_scope = 0
    report_rows = []

    for idx, row in enumerate(data.get("items") or [], start=1):
        if not isinstance(row, dict):
            continue
        source_ids = [str(x).strip() for x in (row.get("source_invoice_ids") or []) if str(x).strip()]
        if not source_ids:
            no_signal += 1
            continue

        scoped_ids = []
        for invoice_id in source_ids:
            prefix = invoice_id.split(":", 1)[0] if ":" in invoice_id else ""
            if prefix.startswith("fr_bd_"):
                siren = prefix.replace("fr_bd_", "", 1)
                if siren in allowed_sirens:
                    scoped_ids.append(invoice_id)

        if not scoped_ids:
            skipped_outside_scope += 1
            continue

        best, confidence, top_votes, total_votes, used_ids = pick_best_account(scoped_ids, counters_by_invoice)
        if not best or confidence < min_confidence:
            no_signal += 1
            continue

        old = normalize_account(row.get("compte_comptable"))
        if old == best:
            unchanged += 1
            continue

        row["compte_comptable"] = best
        row["compte_comptable_source"] = "fec_20241231_txt_v1"
        row["compte_comptable_match_score"] = int(round(confidence * 100))
        row["compte_comptable_match_reason"] = (
            f"from_fec_txt_20241231 confidence={confidence:.2f} "
            f"votes={top_votes}/{total_votes} invoices={min(len(used_ids), 5)}"
        )
        changed += 1

        report_rows.append(
            {
                "file": path.name,
                "item_index": str(idx),
                "article_source": str(row.get("article_source") or ""),
                "old_account": old,
                "new_account": best,
                "confidence": f"{confidence:.2f}",
                "top_votes": str(top_votes),
                "total_votes": str(total_votes),
                "source_invoice_ids": " | ".join(scoped_ids[:8]),
            }
        )

    meta = data.get("meta") or {}
    meta["accounts_alignment_from_fec_txt_v1"] = {
        "updated_at": now_iso(),
        "changed_items": changed,
        "unchanged_items": unchanged,
        "no_signal_items": no_signal,
        "skipped_outside_scope": skipped_outside_scope,
        "min_confidence": min_confidence,
        "source_fec_files": DEFAULT_FEC_FILES,
    }
    data["meta"] = meta
    return data, {
        "changed": changed,
        "unchanged": unchanged,
        "no_signal": no_signal,
        "skipped_outside_scope": skipped_outside_scope,
        "total_items": len(data.get("items") or []),
    }, report_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply compte_comptable updates to epicerie/vtc product bases from provided FEC txt files."
    )
    parser.add_argument("--apply", action="store_true", help="Write updates to JSON files.")
    parser.add_argument("--min-confidence", type=float, default=0.50, help="Minimum confidence to apply account.")
    parser.add_argument(
        "--report-csv",
        default="fec_txt_accounts_alignment_report.csv",
        help="Output CSV report (when changes exist).",
    )
    args = parser.parse_args()

    all_counters: dict[str, Counter] = defaultdict(Counter)
    fec_stats = []

    for siren, fec_file in DEFAULT_FEC_FILES.items():
        fec_path = Path(fec_file)
        ref_path = SCRIPT_DIR / DEFAULT_REFERENCE_FILES[siren]
        if not fec_path.exists():
            print(f"[WARN] missing FEC file for siren={siren}: {fec_path}")
            continue
        if not ref_path.exists():
            print(f"[WARN] missing reference file for siren={siren}: {ref_path}")
            continue
        counters, stats = build_invoice_account_counters(siren=siren, fec_path=fec_path, ref_path=ref_path)
        fec_stats.append(stats)
        for invoice_id, counter in counters.items():
            all_counters[invoice_id].update(counter)

    report_rows = []
    total_changed = 0

    for target in TARGETS:
        base_name = target["base"]
        allowed_sirens = set(target["sirens"])
        for file_name in target["files"]:
            path = SCRIPT_DIR / file_name
            if not path.exists():
                print(f"[WARN] missing base file: {path}")
                continue
            updated_data, stats, rows = update_base_file(
                path=path,
                allowed_sirens=allowed_sirens,
                counters_by_invoice=all_counters,
                min_confidence=max(0.0, min(1.0, args.min_confidence)),
            )
            report_rows.extend(rows)
            total_changed += stats["changed"]
            if args.apply:
                path.write_text(json.dumps(updated_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(
                f"[INFO] base={base_name} file={path.name} changed={stats['changed']} "
                f"unchanged={stats['unchanged']} no_signal={stats['no_signal']} "
                f"skipped_outside_scope={stats['skipped_outside_scope']}"
            )

    report_path = SCRIPT_DIR / args.report_csv
    if report_rows:
        with report_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "file",
                    "item_index",
                    "article_source",
                    "old_account",
                    "new_account",
                    "confidence",
                    "top_votes",
                    "total_votes",
                    "source_invoice_ids",
                ],
            )
            writer.writeheader()
            writer.writerows(report_rows)
        print(f"[OK] report_csv={report_path}")
    else:
        print("[INFO] report_csv=none (no changes)")

    mode = "apply" if args.apply else "dry_run"
    print(f"[INFO] mode={mode}")
    for st in fec_stats:
        print(
            "[INFO] siren={siren} fec_rows={fec_rows_considered} matched_num_date={matched_by_num_date_rows} "
            "matched_num_only={matched_by_num_only_rows} unmatched={unmatched_rows} invoice_ids_with_signal={invoice_ids_with_signal}".format(
                **st
            )
        )
    print(f"[INFO] invoice_ids_with_any_signal={len(all_counters)}")
    print(f"[INFO] total_changed={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
