import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent

BASE_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_boulangerie_v1_with_accounts.json",
    "base_produits_restaurant_v1.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_produits_vtc_v1.json",
    "base_produits_vtc_v1_with_accounts.json",
    "base_produits_epicerie_v1.json",
    "base_produits_epicerie_v1_with_accounts.json",
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

PACK_BY_METIER = {
    "boucherie": ROOT / "candidate_packs_metier" / "boucherie_top_500_cleaned_candidates.json",
    "boulangerie": ROOT / "candidate_packs_metier" / "boulangerie_top_500_cleaned_candidates.json",
    "restaurant": ROOT / "candidate_packs_metier" / "restaurant_top_500_cleaned_candidates.json",
    "transport": ROOT / "candidate_packs_metier" / "transport_top_500_cleaned_candidates.json",
    "btp": ROOT / "candidate_packs_metier" / "btp_top_500_cleaned_candidates.json",
    "charges_externes": ROOT / "candidate_packs_metier" / "charges_externes_top_500_cleaned_candidates.json",
}

TRANSPORT_VTC_PROVENANCE = ROOT / "vtc_article_sources_with_siren.json"
EPICERIE_PROVENANCE = ROOT / "epicerie_article_sources_with_partition.json"
BTP_TRANSPORT_PENDING_PROVENANCE = ROOT / "a_valider_btp_transport_provenance.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    ascii_value = re.sub(r"[^a-z0-9]+", " ", ascii_value)
    return re.sub(r"\s+", " ", ascii_value).strip()


def parse_invoice_ids_sample(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def partitions_from_invoice_ids(invoice_ids: list[str]) -> list[str]:
    partitions = []
    seen = set()
    for invoice_id in invoice_ids:
        partition = invoice_id.split(":", 1)[0].strip()
        if partition and partition not in seen:
            seen.add(partition)
            partitions.append(partition)
    return partitions


def merge_unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_candidate_maps() -> dict:
    candidate_maps = {}
    for metier, path in PACK_BY_METIER.items():
        payload = load_json(path)
        mapping = {}
        for entry in payload.get("top_all", []):
            mapping[normalize_label(entry.get("article_source", ""))] = entry
        candidate_maps[metier] = mapping
    return candidate_maps


def build_vtc_map() -> dict:
    payload = load_json(TRANSPORT_VTC_PROVENANCE)
    mapping = {}
    for entry in payload.get("items", []):
        mapping[normalize_label(entry.get("article_source", ""))] = entry
    return mapping


def build_epicerie_map() -> dict:
    payload = load_json(EPICERIE_PROVENANCE)
    mapping = {}
    for entry in payload.get("items", []):
        mapping[normalize_label(entry.get("article_source", ""))] = entry
    return mapping


def build_pending_maps() -> dict:
    payload = load_json(BTP_TRANSPORT_PENDING_PROVENANCE)
    result = {"btp": {}, "transport": {}}
    for metier_payload in payload.get("metiers", []):
        metier = metier_payload.get("metier")
        if metier not in result:
            continue
        for record in metier_payload.get("records", []):
            result[metier][normalize_label(record.get("article_source", ""))] = record
    return result


def infer_metier_from_filename(file_name: str) -> str:
    if "charges_externes" in file_name:
        return "charges_externes"
    for metier in ["boucherie", "boulangerie", "restaurant", "transport", "btp", "vtc", "epicerie"]:
        if metier in file_name:
            return metier
    raise ValueError(f"Metier introuvable pour {file_name}")


def build_provenance_bundle(
    normalized_label: str,
    metier: str,
    item: dict,
    candidate_maps: dict,
    vtc_map: dict,
    epicerie_map: dict,
    pending_maps: dict,
) -> dict:
    existing_invoice_ids = item.get("source_invoice_ids", []) or []
    if isinstance(existing_invoice_ids, str):
        existing_invoice_ids = parse_invoice_ids_sample(existing_invoice_ids)

    invoice_ids = list(existing_invoice_ids)
    partitions = []
    invoice_count = None
    line_occurrences = None
    sample_account = None
    source_markers = []

    candidate = candidate_maps.get(metier, {}).get(normalized_label)
    if candidate:
        partitions.extend(candidate.get("partitions", []))
        invoice_count = candidate.get("invoice_count")
        line_occurrences = candidate.get("line_occurrences")
        sample_account = candidate.get("sample_account")
        source_markers.append("candidate_pack")

    if metier == "transport":
        vtc_entry = vtc_map.get(normalized_label)
        if vtc_entry:
            invoice_ids.extend(parse_invoice_ids_sample(vtc_entry.get("source_invoice_ids_sample")))
            partitions.extend([f"fr_bd_{siren}" for siren in vtc_entry.get("sirens", [])])
            sample_account = sample_account or vtc_entry.get("compte_comptable")
            source_markers.append("vtc_article_sources_with_siren")

        pending_entry = pending_maps.get("transport", {}).get(normalized_label)
        if pending_entry:
            invoice_ids.extend(parse_invoice_ids_sample(pending_entry.get("invoice_ids_sample")))
            partitions.extend(pending_entry.get("candidate_partitions", []))
            partitions.extend(pending_entry.get("invoice_sample_partitions", []))
            invoice_count = invoice_count or pending_entry.get("candidate_invoice_count")
            line_occurrences = line_occurrences or pending_entry.get("candidate_line_occurrences")
            sample_account = sample_account or pending_entry.get("candidate_sample_account")
            source_markers.append("pending_provenance_transport")

    if metier == "epicerie":
        epi_entry = epicerie_map.get(normalized_label)
        if epi_entry:
            invoice_ids.extend(epi_entry.get("source_invoice_ids", []))
            if epi_entry.get("partition") and epi_entry.get("partition") != "multi":
                partitions.append(epi_entry.get("partition"))
            sample_account = sample_account or epi_entry.get("compte_comptable")
            source_markers.append("epicerie_article_sources_with_partition")

    if metier == "btp":
        pending_entry = pending_maps.get("btp", {}).get(normalized_label)
        if pending_entry:
            invoice_ids.extend(parse_invoice_ids_sample(pending_entry.get("invoice_ids_sample")))
            partitions.extend(pending_entry.get("candidate_partitions", []))
            partitions.extend(pending_entry.get("invoice_sample_partitions", []))
            invoice_count = invoice_count or pending_entry.get("candidate_invoice_count")
            line_occurrences = line_occurrences or pending_entry.get("candidate_line_occurrences")
            sample_account = sample_account or pending_entry.get("candidate_sample_account")
            source_markers.append("pending_provenance_btp")

    if metier == "charges_externes":
        # Les lignes venues de BTP/transport reclassees peuvent parfois retrouver une provenance pending.
        for pending_metier in ["btp", "transport"]:
            pending_entry = pending_maps.get(pending_metier, {}).get(normalized_label)
            if pending_entry:
                invoice_ids.extend(parse_invoice_ids_sample(pending_entry.get("invoice_ids_sample")))
                partitions.extend(pending_entry.get("candidate_partitions", []))
                partitions.extend(pending_entry.get("invoice_sample_partitions", []))
                invoice_count = invoice_count or pending_entry.get("candidate_invoice_count")
                line_occurrences = line_occurrences or pending_entry.get("candidate_line_occurrences")
                sample_account = sample_account or pending_entry.get("candidate_sample_account")
                source_markers.append(f"pending_provenance_{pending_metier}")

    invoice_ids = merge_unique(invoice_ids)
    partitions = merge_unique(partitions + partitions_from_invoice_ids(invoice_ids))

    if invoice_count is None and invoice_ids:
        invoice_count = len(invoice_ids)
    if line_occurrences is None and invoice_count is not None:
        line_occurrences = invoice_count

    if not sample_account:
        sample_account = item.get("compte_comptable")

    if invoice_ids:
        statut = "ids_factures_restaures"
    elif partitions:
        statut = "partitions_restaurees_sans_ids_facture"
    else:
        statut = "provenance_locale_non_retrouvee"

    return {
        "invoice_ids": invoice_ids[:30],
        "partitions": partitions,
        "invoice_count": invoice_count,
        "line_occurrences": line_occurrences,
        "sample_account": sample_account,
        "sources": source_markers,
        "status": statut,
    }


def reorder_item(item: dict) -> dict:
    preferred_order = [
        "article_source",
        "article_canonique",
        "mots_cles",
        "ids_factures_sources",
        "source_invoice_ids",
        "nombre_ids_factures_sources",
        "partitions_sources",
        "source_partition_ids",
        "nombre_factures_sources",
        "nombre_occurrences_lignes",
        "compte_comptable",
        "compte_comptable_source",
        "compte_comptable_match_score",
        "compte_comptable_match_reason",
        "taux_tva",
        "tva_rate",
        "categorie",
        "sous_categorie",
        "type_fournisseur",
        "fournisseur_type",
        "contexte_ape",
        "ape_context",
        "statut_restauration_provenance",
        "sources_restauration_provenance",
        "notes",
    ]
    ordered = {}
    for key in preferred_order:
        if key in item:
            ordered[key] = item[key]
    for key, value in item.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def enrich_item(
    item: dict,
    metier: str,
    candidate_maps: dict,
    vtc_map: dict,
    epicerie_map: dict,
    pending_maps: dict,
) -> tuple[dict, dict]:
    normalized_label = normalize_label(item.get("article_source", ""))
    provenance = build_provenance_bundle(
        normalized_label,
        metier,
        item,
        candidate_maps,
        vtc_map,
        epicerie_map,
        pending_maps,
    )

    item["source_invoice_ids"] = provenance["invoice_ids"]
    item["source_partition_ids"] = provenance["partitions"]
    item["ids_factures_sources"] = provenance["invoice_ids"]
    item["nombre_ids_factures_sources"] = len(provenance["invoice_ids"])
    item["partitions_sources"] = provenance["partitions"]
    item["nombre_factures_sources"] = provenance["invoice_count"]
    item["nombre_occurrences_lignes"] = provenance["line_occurrences"]
    item["statut_restauration_provenance"] = provenance["status"]
    item["sources_restauration_provenance"] = provenance["sources"]
    item["taux_tva"] = item.get("tva_rate")
    item["contexte_ape"] = item.get("ape_context", [])
    item["type_fournisseur"] = item.get("fournisseur_type")

    if not item.get("compte_comptable") and provenance.get("sample_account"):
        item["compte_comptable"] = provenance["sample_account"]
        item["compte_comptable_source"] = "restauration_provenance_locale_v1"
        item["compte_comptable_match_reason"] = "compte réinjecté depuis provenance locale"

    return reorder_item(item), provenance


def update_meta(payload: dict, summary: dict) -> None:
    meta = payload.setdefault("meta", {})
    meta["restauration_provenance_et_aliases_fr_v1"] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "resume": summary,
        "note": "Les clés techniques existantes sont conservées pour la compatibilité moteur; des alias français ont été ajoutés par article.",
    }
    meta["note_aliases_fr"] = "ids_factures_sources, partitions_sources, nombre_factures_sources, nombre_occurrences_lignes, taux_tva, contexte_ape, type_fournisseur"


def main() -> None:
    candidate_maps = build_candidate_maps()
    vtc_map = build_vtc_map()
    epicerie_map = build_epicerie_map()
    pending_maps = build_pending_maps()

    report = {}

    for file_name in BASE_FILES:
        path = ROOT / file_name
        payload = load_json(path)
        metier = infer_metier_from_filename(file_name)
        counters = {
            "items_total": 0,
            "items_avec_ids_factures": 0,
            "items_avec_partitions": 0,
            "items_sans_provenance_locale": 0,
        }

        for section in ["items", "a_valider"]:
            if section not in payload:
                continue
            enriched_section = []
            for raw_item in payload.get(section, []):
                enriched_item, provenance = enrich_item(
                    dict(raw_item),
                    metier,
                    candidate_maps,
                    vtc_map,
                    epicerie_map,
                    pending_maps,
                )
                enriched_section.append(enriched_item)
                counters["items_total"] += 1
                if provenance["invoice_ids"]:
                    counters["items_avec_ids_factures"] += 1
                if provenance["partitions"]:
                    counters["items_avec_partitions"] += 1
                if provenance["status"] == "provenance_locale_non_retrouvee":
                    counters["items_sans_provenance_locale"] += 1
            payload[section] = enriched_section

        update_meta(payload, counters)
        dump_json(path, payload)
        report[file_name] = counters

    (ROOT / "restauration_provenance_et_aliases_fr_v1_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Restauration provenance et alias FR V1",
        "",
    ]
    for file_name, counters in report.items():
        lines.append(f"## {file_name}")
        lines.append("")
        lines.append(f"- entrées totales : `{counters['items_total']}`")
        lines.append(f"- entrées avec `ids_factures_sources` : `{counters['items_avec_ids_factures']}`")
        lines.append(f"- entrées avec `partitions_sources` : `{counters['items_avec_partitions']}`")
        lines.append(f"- entrées sans provenance locale retrouvée : `{counters['items_sans_provenance_locale']}`")
        lines.append("")
    (ROOT / "restauration_provenance_et_aliases_fr_v1_summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
