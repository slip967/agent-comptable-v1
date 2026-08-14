#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter

from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)


ROOT = Path(__file__).resolve().parent
COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv("COUCHDB_USER", DEFAULT_COUCHDB_USER)
COUCHDB_PASS = os.getenv("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)
DEFAULT_DB = os.getenv("DB_FACTURES", "abt3")

BASE_FILES = [
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
]
QUALITY_REPORT = ROOT / "copy_keymanage_metier_docs_report_quality_v3.json"
SUMMARY_MD = ROOT / "restauration_btp_fuzzy_sources_summary.md"
SUMMARY_JSON = ROOT / "restauration_btp_fuzzy_sources_summary.json"

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
    "sans",
    "dans",
    "sac",
    "sacs",
    "piece",
    "pieces",
    "paquet",
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
    return [tok for tok in normalize_text(value).split() if tok]


def semantic_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for tok in tokenize(value):
        if tok in STOP_WORDS:
            continue
        if tok.isdigit():
            continue
        if len(tok) == 1:
            continue
        if len(tok) <= 2 and not any(ch.isdigit() for ch in tok):
            continue
        tokens.append(tok)
    return tokens


def unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def build_btp_partitions() -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    payload = load_json(QUALITY_REPORT)
    partitions: list[str] = []
    partition_to_ape: dict[str, str] = {}
    ape_to_partitions: dict[str, list[str]] = defaultdict(list)
    for row in payload.get("partitions", []):
        selected = [str(x or "").strip().lower() for x in (row.get("selected_metiers") or row.get("inferred_metiers") or [])]
        if "btp" not in selected:
            continue
        partition = str(row.get("partition_prefix") or "").strip()
        ape = str(row.get("client_ape") or "").strip()
        if not partition:
            continue
        partitions.append(partition)
        if ape:
            partition_to_ape[partition] = ape
            if partition not in ape_to_partitions[ape]:
                ape_to_partitions[ape].append(partition)
    return unique_strings(partitions), partition_to_ape, dict(ape_to_partitions)


def build_label_bucket_index(
    session: requests.Session,
    db_name: str,
    partition_prefix: str,
) -> list[dict]:
    endpoint = f"{COUCHDB_URL}/{quote(db_name, safe='')}/_partition/{quote(partition_prefix, safe='')}/_find"
    selector = {"p": "invoice_form"}
    bookmark = None

    buckets: dict[str, dict] = {}

    while True:
        payload = {
            "selector": selector,
            "fields": ["_id", "invoice_date", "line_items"],
            "limit": 500,
        }
        if bookmark:
            payload["bookmark"] = bookmark

        response = session.post(endpoint, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        docs = data.get("docs") or []
        if not docs:
            break

        for doc in docs:
            invoice_id = str(doc.get("_id") or "").strip()
            invoice_date = str(doc.get("invoice_date") or "").strip()
            for line in doc.get("line_items") or []:
                if not isinstance(line, dict):
                    continue
                desc = str(line.get("description") or "").strip()
                if not desc:
                    continue
                account = str(line.get("accounting_account") or "").strip()
                if not account.startswith("60"):
                    continue

                normalized = normalize_text(desc)
                if not normalized:
                    continue

                bucket = buckets.setdefault(
                    normalized,
                    {
                        "label": desc,
                        "normalized": normalized,
                        "tokens": semantic_tokens(desc),
                        "invoice_rows": [],
                    },
                )
                bucket["invoice_rows"].append((invoice_id, invoice_date))

        next_bookmark = data.get("bookmark")
        if not next_bookmark or next_bookmark == bookmark:
            break
        bookmark = next_bookmark

    out: list[dict] = []
    for bucket in buckets.values():
        uniq: dict[str, str] = {}
        for invoice_id, invoice_date in bucket["invoice_rows"]:
            if invoice_id not in uniq:
                uniq[invoice_id] = invoice_date
        sorted_ids = sorted(
            uniq.items(),
            key=lambda row: (parse_date(row[1]) or datetime.max, row[0]),
        )
        out.append(
            {
                "label": bucket["label"],
                "normalized": bucket["normalized"],
                "tokens": bucket["tokens"],
                "invoice_ids": [row[0] for row in sorted_ids][:3],
            }
        )
    return out


def score_match(item_tokens: list[str], item_norm: str, candidate: dict) -> tuple[float, dict]:
    cand_tokens = candidate["tokens"]
    if not item_tokens or not cand_tokens:
        return 0.0, {"overlap": [], "coverage_item": 0.0, "coverage_candidate": 0.0, "contains": False}

    overlap = sorted(set(item_tokens) & set(cand_tokens))
    if len(overlap) < 2:
        return 0.0, {"overlap": overlap, "coverage_item": 0.0, "coverage_candidate": 0.0, "contains": False}

    coverage_item = len(overlap) / max(1, len(set(item_tokens)))
    coverage_candidate = len(overlap) / max(1, len(set(cand_tokens)))
    contains = item_norm in candidate["normalized"] or candidate["normalized"] in item_norm

    score = (coverage_item * 0.70) + (coverage_candidate * 0.20) + (0.10 if contains else 0.0)
    if len(overlap) >= 3:
        score += 0.05
    return score, {
        "overlap": overlap,
        "coverage_item": coverage_item,
        "coverage_candidate": coverage_candidate,
        "contains": contains,
    }


def choose_candidate(item: dict, partition_buckets: dict[str, list[dict]], ape_to_partitions: dict[str, list[str]], all_partitions: list[str]) -> dict | None:
    item_norm = normalize_text(str(item.get("article_source") or item.get("article_canonique") or ""))
    item_tokens = semantic_tokens(str(item.get("article_source") or item.get("article_canonique") or ""))
    if len(item_tokens) < 2:
        return None

    existing_partitions = unique_strings(list(item.get("partitions_sources") or item.get("source_partition_ids") or []))
    existing_apes = unique_strings(list(item.get("contexte_ape") or item.get("ape_context") or []))

    search_partitions = existing_partitions[:]
    if not search_partitions and existing_apes:
        for ape in existing_apes:
            search_partitions.extend(ape_to_partitions.get(ape, []))
    search_partitions = unique_strings(search_partitions or all_partitions)

    candidates: list[dict] = []
    for partition in search_partitions:
        for bucket in partition_buckets.get(partition, []):
            score, details = score_match(item_tokens, item_norm, bucket)
            if score < 0.78:
                continue
            candidates.append(
                {
                    "partition": partition,
                    "score": score,
                    "bucket": bucket,
                    "details": details,
                }
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: (
            -row["score"],
            -len(row["details"]["overlap"]),
            -row["details"]["coverage_item"],
            row["bucket"]["normalized"],
        )
    )
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    if second and best["bucket"]["normalized"] != second["bucket"]["normalized"] and (best["score"] - second["score"]) < 0.08:
        return None
    return best


def reorder_item(item: dict) -> dict:
    preferred_order = [
        "article_source",
        "article_canonique",
        "mots_cles",
        "ids_factures_sources",
        "source_invoice_ids",
        "contexte_ape",
        "ape_context",
        "partitions_sources",
        "source_partition_ids",
        "compte_comptable",
        "taux_tva",
        "tva_rate",
        "categorie",
        "sous_categorie",
        "type_fournisseur",
        "fournisseur_type",
    ]
    ordered: dict = {}
    for key in preferred_order:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def process_file(
    path: Path,
    partition_buckets: dict[str, list[dict]],
    partition_to_ape: dict[str, str],
    ape_to_partitions: dict[str, list[str]],
    all_partitions: list[str],
    dry_run: bool,
) -> dict:
    payload = load_json(path)
    items = payload.get("items") or []
    changed = 0
    ids_added = 0
    examples: list[dict] = []
    updated_items: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            updated_items.append(item)
            continue
        before_ids = unique_strings(list(item.get("ids_factures_sources") or item.get("source_invoice_ids") or []))
        if before_ids:
            updated_items.append(item)
            continue

        chosen = choose_candidate(item, partition_buckets, ape_to_partitions, all_partitions)
        if not chosen:
            updated_items.append(item)
            continue

        invoice_ids = unique_strings(chosen["bucket"]["invoice_ids"])
        if not invoice_ids:
            updated_items.append(item)
            continue

        new_item = dict(item)
        new_item["ids_factures_sources"] = invoice_ids
        new_item["source_invoice_ids"] = invoice_ids

        existing_partitions = unique_strings(list(new_item.get("partitions_sources") or new_item.get("source_partition_ids") or []))
        merged_partitions = unique_strings(existing_partitions + [chosen["partition"]])
        new_item["partitions_sources"] = merged_partitions
        new_item["source_partition_ids"] = merged_partitions

        existing_ape = unique_strings(list(new_item.get("contexte_ape") or new_item.get("ape_context") or []))
        if not existing_ape and partition_to_ape.get(chosen["partition"]):
            existing_ape = [partition_to_ape[chosen["partition"]]]
        new_item["contexte_ape"] = existing_ape
        new_item["ape_context"] = existing_ape

        new_item["statut_restauration_btp_fuzzy"] = "ids_factures_restaures_match_lexical"
        new_item["match_btp_fuzzy_label"] = chosen["bucket"]["label"]
        new_item["match_btp_fuzzy_partition"] = chosen["partition"]
        new_item["match_btp_fuzzy_score"] = round(chosen["score"], 4)
        new_item["match_btp_fuzzy_overlap"] = chosen["details"]["overlap"]

        changed += 1
        ids_added += len(invoice_ids)
        if len(examples) < 8:
            examples.append(
                {
                    "article_source": item.get("article_source"),
                    "matched_label": chosen["bucket"]["label"],
                    "partition": chosen["partition"],
                    "score": round(chosen["score"], 4),
                    "invoice_ids": invoice_ids,
                    "overlap": chosen["details"]["overlap"],
                }
            )
        updated_items.append(reorder_item(new_item))

    payload["items"] = updated_items
    meta = payload.get("meta") or {}
    meta["restauration_btp_fuzzy_sources"] = {
        "applied_at": now_iso(),
        "dry_run": dry_run,
        "source_db_factures": DEFAULT_DB,
        "match_rule": "token_overlap_strict + partition_scope_btp",
        "items_changed": changed,
        "invoice_ids_added": ids_added,
    }
    meta["updated_at"] = now_iso()
    payload["meta"] = meta

    if not dry_run:
        dump_json(path, payload)

    return {
        "file": path.name,
        "items_total": len(items),
        "items_changed": changed,
        "invoice_ids_added": ids_added,
        "examples": examples,
    }


def write_reports(result: dict) -> None:
    SUMMARY_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Restauration BTP Fuzzy Sources",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- dry_run: `{str(result['dry_run']).lower()}`",
        f"- source_db_factures: `{result['source_db_factures']}`",
        f"- items_changed: `{result['items_changed']}`",
        f"- invoice_ids_added: `{result['invoice_ids_added']}`",
        "",
    ]
    for file_result in result["files"]:
        lines.append(
            f"- {file_result['file']}: changed=`{file_result['items_changed']}` ids_added=`{file_result['invoice_ids_added']}`"
        )
    if result["examples"]:
        lines.append("")
        lines.append("Exemples :")
        for example in result["examples"]:
            lines.append(
                f"- `{example['article_source']}` -> `{example['matched_label']}` "
                f"(partition=`{example['partition']}`, score=`{example['score']}`, overlap=`{example['overlap']}`)"
            )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaure des ids_factures_sources manquants sur la base BTP par match lexical controle.")
    parser.add_argument("--db-factures", default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_partitions, partition_to_ape, ape_to_partitions = build_btp_partitions()
    session = http_session()
    partition_buckets: dict[str, list[dict]] = {}
    for partition in all_partitions:
        partition_buckets[partition] = build_label_bucket_index(
            session=session,
            db_name=args.db_factures,
            partition_prefix=partition,
        )

    file_results = []
    total_changed = 0
    total_ids = 0
    examples: list[dict] = []
    for name in BASE_FILES:
        result = process_file(
            path=(ROOT / name),
            partition_buckets=partition_buckets,
            partition_to_ape=partition_to_ape,
            ape_to_partitions=ape_to_partitions,
            all_partitions=all_partitions,
            dry_run=args.dry_run,
        )
        file_results.append(result)
        total_changed += result["items_changed"]
        total_ids += result["invoice_ids_added"]
        for example in result["examples"]:
            if len(examples) < 8:
                examples.append(example)

    summary = {
        "generated_at": now_iso(),
        "dry_run": args.dry_run,
        "source_db_factures": args.db_factures,
        "files": file_results,
        "items_changed": total_changed,
        "invoice_ids_added": total_ids,
        "examples": examples,
    }
    write_reports(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
