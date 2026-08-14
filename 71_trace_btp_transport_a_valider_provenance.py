#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_JSON = SCRIPT_DIR / "a_valider_btp_transport_provenance.json"
OUTPUT_MD = SCRIPT_DIR / "a_valider_btp_transport_provenance.md"


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_row_map(rows: list[dict]) -> dict[str, dict]:
    row_map: dict[str, dict] = {}
    for row in rows:
        key = normalize_text(row.get("article_source") or "")
        if key and key not in row_map:
            row_map[key] = row
    return row_map


def parse_note_counts(notes: str) -> tuple[int | None, int | None]:
    text = str(notes or "")
    match = re.search(r"invoice_count=(\d+),\s*line_occurrences=(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def partition_list_from_invoice_sample(sample: str) -> list[str]:
    partitions: list[str] = []
    seen = set()
    for part in str(sample or "").split("|"):
        part = part.strip()
        if not part:
            continue
        partition = part.split(":", 1)[0].strip()
        if partition and partition not in seen:
            seen.add(partition)
            partitions.append(partition)
    return partitions


def trace_metier(metier: str, base_name: str, pack_name: str, vtc_map: dict[str, dict]) -> dict:
    base_payload = load_json(SCRIPT_DIR / base_name)
    pack_payload = load_json(SCRIPT_DIR / "candidate_packs_metier" / pack_name)
    pack_rows = pack_payload.get("top_all") or []
    pack_map = build_row_map(pack_rows)

    records: list[dict] = []
    stats = {
        "count": 0,
        "candidate_pack_matches": 0,
        "invoice_sample_matches": 0,
        "counts_recovered_from_notes": 0,
    }

    for item in base_payload.get("a_valider") or []:
        stats["count"] += 1
        article_source = str(item.get("article_source") or "").strip()
        article_source_original = str(item.get("article_source_original") or "").strip()
        note_text = str(item.get("notes") or "")
        invoice_count_from_notes, line_occ_from_notes = parse_note_counts(note_text)
        if invoice_count_from_notes is not None:
            stats["counts_recovered_from_notes"] += 1

        candidate_row = None
        for key in (normalize_text(article_source), normalize_text(article_source_original)):
            if key and key in pack_map:
                candidate_row = pack_map[key]
                break
        if candidate_row:
            stats["candidate_pack_matches"] += 1

        invoice_sample_row = None
        if metier == "transport":
            for key in (normalize_text(article_source_original), normalize_text(article_source)):
                if key and key in vtc_map:
                    invoice_sample_row = vtc_map[key]
                    break
        if invoice_sample_row:
            stats["invoice_sample_matches"] += 1

        candidate_partitions = candidate_row.get("partitions") if candidate_row else []
        invoice_sample = invoice_sample_row.get("source_invoice_ids_sample") if invoice_sample_row else ""
        invoice_sample_partitions = partition_list_from_invoice_sample(invoice_sample)

        records.append(
            {
                "article_source": article_source,
                "article_source_original": article_source_original or None,
                "selection_source": item.get("selection_source"),
                "validation_reason": item.get("validation_reason"),
                "validation_note": item.get("validation_note"),
                "candidate_pack_found": bool(candidate_row),
                "candidate_invoice_count": candidate_row.get("invoice_count") if candidate_row else invoice_count_from_notes,
                "candidate_line_occurrences": candidate_row.get("line_occurrences") if candidate_row else line_occ_from_notes,
                "candidate_partitions": candidate_partitions,
                "candidate_sample_account": candidate_row.get("sample_account") if candidate_row else item.get("compte_comptable"),
                "invoice_sample_found": bool(invoice_sample_row),
                "invoice_source_file": "vtc_article_sources_with_siren.json" if invoice_sample_row else None,
                "invoice_ids_sample": invoice_sample or None,
                "invoice_ids_sample_count": invoice_sample_row.get("source_invoice_ids_count") if invoice_sample_row else None,
                "invoice_sample_partitions": invoice_sample_partitions,
                "notes": note_text or None,
            }
        )

    return {
        "metier": metier,
        "base_file": base_name,
        "candidate_pack_file": pack_name,
        "stats": stats,
        "records": records,
    }


def build_markdown(payload: dict) -> str:
    lines = [
        "# Provenance A Valider BTP / Transport",
        "",
        "Ce rapport recolle les lignes `a_valider` avec leur meilleure provenance locale disponible.",
        "",
        "Niveaux de provenance utilises :",
        "- `candidate pack` : nb de factures, nb d'occurrences, partitions",
        "- `invoice sample` : echantillon d'`invoice_id` quand retrouve localement",
        "- `notes` : fallback quand la ligne a ete promue plus tard vers `a_valider`",
        "",
    ]

    for metier_payload in payload.get("metiers") or []:
        stats = metier_payload["stats"]
        lines.extend(
            [
                f"## {metier_payload['metier'].upper()}",
                "",
                f"- base: `{metier_payload['base_file']}`",
                f"- lignes a_valider: `{stats['count']}`",
                f"- matches candidate pack: `{stats['candidate_pack_matches']}`",
                f"- matches invoice sample: `{stats['invoice_sample_matches']}`",
                f"- counts recuperes depuis notes: `{stats['counts_recovered_from_notes']}`",
                "",
            ]
        )

        for idx, record in enumerate(metier_payload["records"], 1):
            lines.append(f"### {idx}. `{record['article_source']}`")
            lines.append("")
            if record.get("article_source_original"):
                lines.append(f"- article_source_original: `{record['article_source_original']}`")
            lines.append(f"- selection_source: `{record.get('selection_source')}`")
            lines.append(f"- candidate_pack_found: `{record['candidate_pack_found']}`")
            lines.append(f"- invoice_count: `{record.get('candidate_invoice_count')}`")
            lines.append(f"- line_occurrences: `{record.get('candidate_line_occurrences')}`")
            lines.append(f"- partitions: `{record.get('candidate_partitions')}`")
            lines.append(f"- sample_account: `{record.get('candidate_sample_account')}`")
            lines.append(f"- invoice_sample_found: `{record['invoice_sample_found']}`")
            if record.get("invoice_ids_sample"):
                lines.append(f"- invoice_ids_sample: `{record['invoice_ids_sample']}`")
                lines.append(f"- invoice_sample_partitions: `{record['invoice_sample_partitions']}`")
            if record.get("notes"):
                lines.append(f"- notes: `{record['notes']}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    vtc_payload = load_json(SCRIPT_DIR / "vtc_article_sources_with_siren.json")
    vtc_map = build_row_map(vtc_payload.get("items") or [])

    metiers = [
        trace_metier("btp", "base_produits_btp_v1.json", "btp_top_500_cleaned_candidates.json", vtc_map),
        trace_metier("transport", "base_produits_transport_v1.json", "transport_top_500_cleaned_candidates.json", vtc_map),
    ]

    payload = {"generated_from": "71_trace_btp_transport_a_valider_provenance.py", "metiers": metiers}
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(payload), encoding="utf-8")

    print(f"Wrote {OUTPUT_JSON.name}")
    print(f"Wrote {OUTPUT_MD.name}")
    for metier in metiers:
        stats = metier["stats"]
        print(
            f"{metier['metier']}: count={stats['count']} candidate_pack_matches={stats['candidate_pack_matches']} "
            f"invoice_sample_matches={stats['invoice_sample_matches']} notes_count_matches={stats['counts_recovered_from_notes']}"
        )


if __name__ == "__main__":
    main()
