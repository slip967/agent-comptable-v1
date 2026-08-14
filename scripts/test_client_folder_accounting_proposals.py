#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test moteur sur un dossier client complet.

Connexion CouchDB → recherche des factures d'un client (via partition CouchDB)
→ analyse ligne par ligne → collecte des accounting_proposal → rapport JSON + Markdown.

Usage :
    python scripts/test_client_folder_accounting_proposals.py --client-name "BOULANGERIE L'UNIVERS DU PAIN" --limit 10
    python scripts/test_client_folder_accounting_proposals.py --client-name "BOUCHERIE IFRI" --limit 10
    python scripts/test_client_folder_accounting_proposals.py --client-name "ASSAINIS" --limit 10
    python scripts/test_client_folder_accounting_proposals.py --list-clients
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

# ── path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from couch_config import (
    CA_CERT,
    CLIENT_CERT,
    CLIENT_KEY,
    COUCHDB_PASS,
    COUCHDB_URL,
    COUCHDB_USER,
)

# Engine is inside agent_local_v1/
sys.path.insert(0, str(REPO_ROOT / "agent_local_v1"))
from app.invoice_engine_service import analyze_invoice_lines_strong  # noqa: E402

# ── constants ────────────────────────────────────────────────────────────────
DB_CANDIDATES = ["keymanage_accounting", "keymanage_accouting"]

# Known client dossiers: client name → SIREN (9 digits)
# Source: probe_user_client_lists_in_db_summary.json
KNOWN_CLIENTS: dict[str, str] = {
    # Boulangerie
    "BOULANGERIE L'UNIVERS DU PAIN": "880517875",
    # Boucherie
    "BOUCHERIE DE L'ESPOIR": "821913290",
    "BOUCHERIE IFRI": "892833831",
    # Restaurant
    "AADHI NAVI (MADRAS KITCHEN)": "948467188",
    "COUSCOUS FACTORY": "930689930",
    "LES TISANES": "849602750",
    # BTP
    "AEF (ARTISAN ENERGIE FRANCE)": "914837463",
    "ASSAINIS": "878523547",
    "DEM BAT": "943297747",
    "IBB INTERMEDIARY BUSINESS BATIMENT": "981565930",
    "IRD BAT": "879788230",
    "IRPCH PLOMBERIE": "951421064",
    "MB CONSTRUCTION": "947858304",
    "MONDIAL BATIMENT": "889860938",
    "PRO MRI45 PRO MAINTENANCE RESEAU": "942879321",
    "SAFTA MENUISERIE": "938751021",
    "TRAVAUX NETTS SARL": "908108012",
    # Transport / logistique
    "BS INTERNATIONAL TRANSFERT": "993669621",
    "DAC EXPRESS": "922040506",
    "DELIVERY GREEN": "931479869",
    "HELP DELIVERY": "991148206",
    "MHB TRANSPORTS": "982921744",
    "MMA TRANSPORT": "952192821",
    "MS TRANSPORT": "890852403",
    "PRIM DEMENAGEMENT": "908282098",
    "PROSERVICES AMBULANCES": "891756504",
    "RAF TRANS": "979300076",
}

# Default ordered cascade when no --client-name provided
DEFAULT_CANDIDATE_ORDER = [
    "BOULANGERIE L'UNIVERS DU PAIN",
    "BOUCHERIE IFRI",
    "ASSAINIS",
    "PROSERVICES AMBULANCES",
    "PRIM DEMENAGEMENT",
    "MS TRANSPORT",
    "MB CONSTRUCTION",
    "DELIVERY GREEN",
]

SUPPLIER_FIELD_PATHS: list[tuple[str, ...]] = [
    ("issuer", "name"),
    ("issuer", "company_name"),
    ("issuer", "label"),
]

ANALYSIS_TIMEOUT_S = 90  # per invoice


# ── CouchDB helpers ──────────────────────────────────────────────────────────

def build_session() -> requests.Session:
    session = requests.Session()
    session.auth = (COUCHDB_USER, COUCHDB_PASS)
    session.cert = (CLIENT_CERT, CLIENT_KEY)
    session.verify = CA_CERT
    return session


def resolve_db(session: requests.Session) -> str:
    for name in DB_CANDIDATES:
        try:
            r = session.get(f"{COUCHDB_URL}/{quote(name, safe='')}", timeout=30)
            if r.status_code == 200:
                print(f"  [DB] Base trouvée : {name}")
                return name
        except requests.RequestException:
            continue
    raise RuntimeError(f"Aucune base disponible parmi {DB_CANDIDATES}")


def unwrap_value(value: Any) -> Any:
    """Recursively unwrap CouchDB OCR-wrapped values: {'value': X, 'bbox': ...} → X."""
    current = value
    while isinstance(current, dict) and "value" in current:
        current = current.get("value")
    return current


def _nested_get(doc: dict, path: tuple[str, ...]) -> str:
    obj: Any = doc
    for key in path:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(key)
        if obj is None:
            return ""
    obj = unwrap_value(obj)
    if isinstance(obj, dict):
        for k in ("name", "company_name", "label"):
            v = unwrap_value(obj.get(k))
            if v and str(v).strip():
                return str(v).strip()
        return ""
    return str(obj).strip() if obj is not None else ""


def extract_supplier_name(doc: dict) -> str:
    for path in SUPPLIER_FIELD_PATHS:
        v = _nested_get(doc, path)
        if v:
            return v
    return ""


def extract_invoice_number(doc: dict) -> str:
    v = unwrap_value(doc.get("invoice_number"))
    return str(v or "").strip()


def extract_invoice_date(doc: dict) -> str:
    v = unwrap_value(doc.get("invoice_date"))
    return str(v or "").strip()


def is_invoice_form_invoice(doc: dict) -> bool:
    if str(doc.get("p") or "").strip() != "invoice_form":
        return False
    if str(doc.get("document_type") or "").strip().lower() != "invoice":
        return False
    return isinstance(doc.get("line_items"), list)


# ── Partition-based search ───────────────────────────────────────────────────

def fetch_partition_invoices(
    session: requests.Session,
    db: str,
    siren: str,
    limit: int = 10,
) -> list[dict]:
    """
    Use CouchDB partition queries to fetch invoice_form docs for a specific SIREN.
    Partition key is fr_bd_{siren}.
    """
    partition = f"fr_bd_{siren}"
    url = f"{COUCHDB_URL}/{quote(db, safe='')}/_partition/{quote(partition, safe='')}/_all_docs"
    matches: list[dict] = []
    startkey = f"{partition}:"
    page_size = 200

    print(f"  [PARTITION] Interrogation partition {partition} …")

    while len(matches) < limit:
        r = session.get(
            url,
            params={
                "include_docs": "true",
                "startkey": json.dumps(startkey),
                "limit": str(page_size),
            },
            timeout=120,
        )
        r.raise_for_status()
        rows = r.json().get("rows") or []

        if not rows:
            break

        for row in rows:
            doc = row.get("doc") or {}
            if not isinstance(doc, dict):
                continue
            if is_invoice_form_invoice(doc):
                matches.append(doc)
                if len(matches) >= limit:
                    break

        if len(rows) < page_size:
            break

        last_id = str(rows[-1].get("id") or "").strip()
        if not last_id:
            break
        startkey = last_id + "\ufff0"

    print(f"  [PARTITION] {len(matches)} facture(s) trouvée(s) dans la partition {partition}")
    return matches


def resolve_siren(client_name: str) -> str | None:
    """Try to find SIREN by exact match, then case-insensitive, then partial."""
    # Exact
    if client_name in KNOWN_CLIENTS:
        return KNOWN_CLIENTS[client_name]
    # Case-insensitive
    upper = client_name.strip().upper()
    for k, v in KNOWN_CLIENTS.items():
        if k.upper() == upper:
            return v
    # Partial
    for k, v in KNOWN_CLIENTS.items():
        if upper in k.upper():
            return v
    return None


# ── Analysis ─────────────────────────────────────────────────────────────────

def analyze_doc(doc: dict) -> dict | None:
    """
    Call the existing engine on one invoice doc.
    Returns the serialised StrongAnalysisResponse as dict, or None on error.
    """
    try:
        result = analyze_invoice_lines_strong(doc)
        # Convert pydantic model to dict
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "dict"):
            return result.dict()
        return dict(result)
    except Exception as exc:
        raise exc


# ── Report helpers ────────────────────────────────────────────────────────────

def _safe(v: Any, default: Any = "") -> Any:
    return v if v is not None else default


def build_invoice_record(doc: dict, analysis: dict, client_name: str = "") -> dict:
    proposal = analysis.get("accounting_proposal") or {}
    summary = proposal.get("summary") or {}
    return {
        "invoice_id": _safe(doc.get("_id")),
        "invoice_number": extract_invoice_number(doc),
        "date": extract_invoice_date(doc),
        "supplier": extract_supplier_name(doc),
        "client": client_name,
        "line_count": len(doc.get("line_items") or []),
        "proposal_status": _safe(proposal.get("proposal_status")),
        "summary": summary,
        "accounting_proposal": proposal,
    }


def _decision_icon(decision: str) -> str:
    return {
        "auto_ok": "✅",
        "validation_humaine": "🔶",
        "rejeter": "❌",
        "non_comptable": "⬜",
    }.get(decision, "❓")


def _risk_icon(risk: str) -> str:
    return {"faible": "🟢", "moyen": "🟡", "eleve": "🔴"}.get(risk, "⚪")


def build_markdown_report(
    client_arg: str,
    tested_candidates: list[str],
    selected_candidate: str,
    invoice_records: list[dict],
    errors: list[dict],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_invoices = len(invoice_records)
    total_lines = sum(r["line_count"] for r in invoice_records)

    # Global counters
    auto_ok = sum(r["summary"].get("auto_ok", 0) for r in invoice_records)
    validation_humaine = sum(r["summary"].get("validation_humaine", 0) for r in invoice_records)
    rejected = sum(r["summary"].get("rejected", 0) for r in invoice_records)
    non_comptable = sum(r["summary"].get("non_comptable", 0) for r in invoice_records)
    confs = [
        r["summary"].get("average_confidence", 0)
        for r in invoice_records
        if r["summary"].get("total_lines", 0) > 0
    ]
    avg_conf = round(sum(confs) / len(confs), 1) if confs else 0.0

    lines_md = []
    lines_md.append(f"# Rapport dossier client — {client_arg}")
    lines_md.append(f"\n_Généré le {now}_\n")
    lines_md.append("---\n")

    lines_md.append("## 1. Dossier testé\n")
    lines_md.append(f"- **Recherche initiale** : `{client_arg}`")
    lines_md.append(f"- **Candidats testés** : {', '.join(f'`{c}`' for c in tested_candidates)}")
    lines_md.append(f"- **Dossier retenu** : **{selected_candidate or 'Aucun'}**\n")

    lines_md.append("## 2. Résumé global\n")
    lines_md.append(f"| Indicateur | Valeur |")
    lines_md.append(f"|---|---|")
    lines_md.append(f"| Factures analysées | {total_invoices} |")
    lines_md.append(f"| Lignes totales | {total_lines} |")
    lines_md.append(f"| ✅ Auto OK | {auto_ok} |")
    lines_md.append(f"| 🔶 Validation humaine | {validation_humaine} |")
    lines_md.append(f"| ❌ Rejetées | {rejected} |")
    lines_md.append(f"| ⬜ Non comptables | {non_comptable} |")
    lines_md.append(f"| Score moyen | {avg_conf:.1f}% |")
    lines_md.append(f"| Erreurs / ignorées | {len(errors)} |\n")

    lines_md.append("## 3. Factures analysées\n")
    for idx, rec in enumerate(invoice_records, 1):
        sup = rec["supplier"] or "Fournisseur inconnu"
        cli = rec["client"] or "Client inconnu"
        num = rec["invoice_number"] or "—"
        date = rec["date"] or "—"
        status = rec["proposal_status"] or "—"
        sm = rec["summary"]
        lines_md.append(f"### Facture {idx} — {sup}")
        lines_md.append(f"- **N°** : {num}  |  **Date** : {date}")
        lines_md.append(f"- **Client** : {cli}")
        lines_md.append(f"- **ID** : `{rec['invoice_id']}`")
        lines_md.append(f"- **Statut proposal** : `{status}`")
        lines_md.append(
            f"- **Lignes** : {sm.get('total_lines', 0)} total "
            f"| ✅ {sm.get('auto_ok', 0)} auto "
            f"| 🔶 {sm.get('validation_humaine', 0)} à valider "
            f"| ❌ {sm.get('rejected', 0)} rejet "
            f"| ⬜ {sm.get('non_comptable', 0)} non compta. "
            f"| Score : {sm.get('average_confidence', 0):.1f}%\n"
        )

        ap_lines = (rec.get("accounting_proposal") or {}).get("lines") or []
        if ap_lines:
            lines_md.append("#### Lignes principales\n")
            lines_md.append("| # | Article | Compte | Score | Risque | Décision | Auto-post | Humain |")
            lines_md.append("|---|---|---|---|---|---|---|---|")
            for li, apl in enumerate(ap_lines[:15], 1):
                raw = str(apl.get("raw_text") or "").strip()[:45]
                account = apl.get("recommended_account") or "—"
                conf = f"{apl.get('confidence', 0):.0f}%"
                risk = _risk_icon(apl.get("risk_level", "")) + " " + (apl.get("risk_level") or "—")
                dec = _decision_icon(apl.get("decision", "")) + " " + (apl.get("decision") or "—")
                auto_p = "✅" if apl.get("can_auto_post") else "✗"
                human = "🔶 oui" if apl.get("requires_human_validation") else "non"
                lines_md.append(f"| {li} | {raw} | {account} | {conf} | {risk} | {dec} | {auto_p} | {human} |")
            if len(ap_lines) > 15:
                lines_md.append(f"\n_… {len(ap_lines) - 15} lignes supplémentaires non affichées._")
            lines_md.append("")

        # Line-type examples
        examples: dict[str, dict | None] = {
            "found_exact": None,
            "found_fuzzy": None,
            "missing_candidate": None,
            "non_comptable": None,
        }
        for apl in ap_lines:
            rs = apl.get("referential_status") or ""
            if rs in examples and examples[rs] is None:
                examples[rs] = apl

        example_items = [(k, v) for k, v in examples.items() if v is not None]
        if example_items:
            lines_md.append("#### Exemples par type de ligne\n")
            for ref_status, apl in example_items:
                label = {
                    "found_exact": "Article trouvé (exact)",
                    "found_fuzzy": "Article proche (fuzzy)",
                    "missing_candidate": "Article absent — hypothèse",
                    "non_comptable": "Ligne non comptable",
                }.get(ref_status, ref_status)
                raw = (apl.get("raw_text") or "").strip()
                account = apl.get("recommended_account") or "—"
                account_label = apl.get("account_label") or ""
                conf = f"{apl.get('confidence', 0):.1f}%"
                lines_md.append(f"- **{label}** : _{raw}_ → compte **{account}** {account_label} (score {conf})")
            lines_md.append("")

    if errors:
        lines_md.append("## 4. Factures ignorées ou en erreur\n")
        lines_md.append("| ID | Raison |")
        lines_md.append("|---|---|")
        for err in errors:
            lines_md.append(f"| `{err['invoice_id']}` | {err['reason']} |")
        lines_md.append("")

    lines_md.append("## 5. Conclusion\n")
    if total_invoices == 0:
        lines_md.append(
            "Aucune facture n'a pu être analysée pour ce dossier. "
            "Le dossier ne contient pas encore de factures reconnues par le moteur, "
            "ou les noms de client dans CouchDB ne correspondent pas aux recherches effectuées.\n"
        )
    else:
        lines_md.append(
            f"Le moteur a analysé **{total_invoices} facture(s)** du dossier **{selected_candidate}** "
            f"représentant **{total_lines} lignes**.\n"
        )
        if auto_ok > 0:
            lines_md.append(
                f"- **{auto_ok} ligne(s) auto-validables** : le moteur les reconnaît avec certitude "
                f"et pourrait les intégrer automatiquement dans un workflow KeyManage."
            )
        if validation_humaine > 0:
            lines_md.append(
                f"- **{validation_humaine} ligne(s) nécessitent une validation humaine** : "
                f"l'article est proche d'une référence connue mais pas identique, "
                f"ou le contexte métier est insuffisant pour automatiser."
            )
        if rejected > 0:
            lines_md.append(
                f"- **{rejected} ligne(s) rejetées** : aucun candidat fiable trouvé dans les bases de connaissance. "
                f"Ces articles peuvent être ajoutés via la boucle d'enrichissement."
            )
        if non_comptable > 0:
            lines_md.append(
                f"- **{non_comptable} ligne(s) non comptables** : lignes de total, TVA, entête, etc., "
                f"correctement filtrées par le moteur."
            )
        lines_md.append(
            f"\n**Conclusion** : Ce dossier est exploitable pour une démo KeyManage. "
            f"Le moteur retourne pour chaque facture une proposition d'écriture comptable structurée "
            f"(`accounting_proposal`) avec score de confiance, niveau de risque, décision et flag de validation humaine. "
            f"L'intégration dans le workflow KeyManage peut être déclenchée directement depuis le bloc "
            f"`accounting_proposal` retourné par `POST /api/analysis/strong-invoice/{{invoice_id}}`."
        )

    return "\n".join(lines_md) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    client_name: str | None,
    siren: str | None,
    limit: int,
    output_json: Path,
    output_md: Path,
) -> None:
    print("\n" + "=" * 60)
    print("  Test dossier client — moteur accounting_proposal")
    print("=" * 60 + "\n")

    session = build_session()
    db = resolve_db(session)

    # ── Resolve client + SIREN ────────────────────────────────────────────
    if siren and not client_name:
        # Find name for this SIREN if possible
        client_name = next(
            (k for k, v in KNOWN_CLIENTS.items() if v == siren.strip()), siren
        )
    elif client_name and not siren:
        siren = resolve_siren(client_name)
        if not siren:
            print(f"⚠️  Client « {client_name} » non trouvé dans les dossiers connus.")
            print(f"\n   Dossiers disponibles :")
            for name in sorted(KNOWN_CLIENTS):
                print(f"     - {name}  (SIREN {KNOWN_CLIENTS[name]})")
            print(
                "\n   Essayez --list-clients pour voir la liste complète, "
                "ou passez --siren directement."
            )
            _write_empty_report(
                output_json, output_md,
                client_name or "(auto)", [], "",
                "Client non trouvé dans KNOWN_CLIENTS. Utilisez --list-clients pour voir les noms valides.",
            )
            return
    elif not client_name and not siren:
        # Auto: try candidates in order
        for candidate in DEFAULT_CANDIDATE_ORDER:
            candidate_siren = KNOWN_CLIENTS.get(candidate)
            if not candidate_siren:
                continue
            docs_tmp = fetch_partition_invoices(session, db, candidate_siren, limit=limit)
            if docs_tmp:
                client_name = candidate
                siren = candidate_siren
                break
        if not siren:
            print("⚠️  Aucun dossier par défaut n'a renvoyé de factures.")
            _write_empty_report(output_json, output_md, "(auto)", [], "", "Aucun dossier par défaut trouvé.")
            return
    else:
        # Both provided — validate they match
        resolved = resolve_siren(client_name)
        if resolved and siren != resolved:
            print(f"  Note: SIREN fourni ({siren}) utilisé ; le SIREN connu pour {client_name} est {resolved}.")

    assert siren is not None
    assert client_name is not None

    print(f"\n[DOSSIER] {client_name}  (SIREN {siren})")

    docs = fetch_partition_invoices(session, db, siren, limit=limit)

    if not docs:
        print(f"\n⚠️  Aucune facture invoice_form trouvée dans la partition fr_bd_{siren}.")
        _write_empty_report(
            output_json, output_md,
            client_name, [client_name], "",
            f"Aucune facture invoice_form dans la partition fr_bd_{siren}.",
        )
        return

    print(f"\n✅ {len(docs)} facture(s) récupérée(s) → analyse en cours …")

    invoice_records: list[dict] = []
    errors: list[dict] = []

    for idx, doc in enumerate(docs, 1):
        invoice_id = str(doc.get("_id") or "").strip()
        invoice_number = extract_invoice_number(doc)
        supplier = extract_supplier_name(doc)
        line_count = len(doc.get("line_items") or [])

        print(f"\n[{idx}/{len(docs)}] {invoice_id}")
        print(f"         Fournisseur : {supplier or '—'}")
        print(f"         N°          : {invoice_number or '—'}")
        print(f"         Lignes      : {line_count}")

        if line_count == 0:
            print("         → Ignorée (aucune ligne)")
            errors.append({
                "invoice_id": invoice_id,
                "reason": "Aucune line_item trouvée dans le document.",
            })
            continue

        t0 = time.time()
        try:
            analysis = analyze_doc(doc)
            elapsed = round(time.time() - t0, 1)
            proposal = analysis.get("accounting_proposal") or {}
            summary = proposal.get("summary") or {}
            print(
                f"         ✅ Analysée en {elapsed}s | "
                f"status={proposal.get('proposal_status', '—')} | "
                f"auto_ok={summary.get('auto_ok', 0)} | "
                f"validation={summary.get('validation_humaine', 0)} | "
                f"conf={summary.get('average_confidence', 0):.1f}%"
            )
            invoice_records.append(build_invoice_record(doc, analysis, client_name))

        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            reason = str(exc)
            if elapsed >= ANALYSIS_TIMEOUT_S * 0.9:
                reason = f"Timeout ({elapsed}s) — facture trop volumineuse ou backend lent."
            print(f"         ⚠️  Erreur ({elapsed}s) : {reason[:120]}")
            errors.append({"invoice_id": invoice_id, "reason": reason[:300]})

    # ── Global summary ──────────────────────────────────────────────────────
    total_lines = sum(r["line_count"] for r in invoice_records)
    auto_ok = sum(r["summary"].get("auto_ok", 0) for r in invoice_records)
    validation_humaine = sum(r["summary"].get("validation_humaine", 0) for r in invoice_records)
    rejected = sum(r["summary"].get("rejected", 0) for r in invoice_records)
    non_comptable = sum(r["summary"].get("non_comptable", 0) for r in invoice_records)
    confs = [
        r["summary"].get("average_confidence", 0)
        for r in invoice_records
        if r["summary"].get("total_lines", 0) > 0
    ]
    avg_conf = round(sum(confs) / len(confs), 1) if confs else 0.0

    # ── JSON report ─────────────────────────────────────────────────────────
    report = {
        "generated_at": datetime.now().isoformat(),
        "client": client_name,
        "siren": siren,
        "tested_candidates": [client_name],
        "selected_candidate": client_name,
        "total_invoices_found": len(docs),
        "total_invoices_analyzed": len(invoice_records),
        "total_lines": total_lines,
        "global_summary": {
            "auto_ok": auto_ok,
            "validation_humaine": validation_humaine,
            "rejected": rejected,
            "non_comptable": non_comptable,
            "average_confidence": avg_conf,
        },
        "invoices": invoice_records,
        "errors_or_skipped": errors,
    }
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Markdown report ──────────────────────────────────────────────────────
    md_content = build_markdown_report(
        client_name, [client_name], client_name, invoice_records, errors,
    )
    output_md.write_text(md_content, encoding="utf-8")

    # ── Console summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RÉSULTATS")
    print("=" * 60)
    print(f"  Dossier                : {client_name}  (SIREN {siren})")
    print(f"  Factures trouvées      : {len(docs)}")
    print(f"  Factures analysées     : {len(invoice_records)}")
    print(f"  Lignes totales         : {total_lines}")
    print(f"  Auto OK                : {auto_ok}")
    print(f"  Validation humaine     : {validation_humaine}")
    print(f"  Rejetées               : {rejected}")
    print(f"  Non comptables         : {non_comptable}")
    print(f"  Score moyen            : {avg_conf:.1f}%")
    print(f"  Erreurs / ignorées     : {len(errors)}")
    print(f"\n  Rapport JSON           : {output_json}")
    print(f"  Rapport Markdown       : {output_md}")
    print("=" * 60 + "\n")


def _write_empty_report(
    output_json: Path,
    output_md: Path,
    client_name: str,
    tested: list[str],
    selected: str,
    note: str,
) -> None:
    report = {
        "generated_at": datetime.now().isoformat(),
        "client": client_name,
        "tested_candidates": tested,
        "selected_candidate": selected,
        "total_invoices_found": 0,
        "total_invoices_analyzed": 0,
        "total_lines": 0,
        "global_summary": {
            "auto_ok": 0,
            "validation_humaine": 0,
            "rejected": 0,
            "non_comptable": 0,
            "average_confidence": 0,
        },
        "invoices": [],
        "errors_or_skipped": [],
        "note": note,
    }
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(
        build_markdown_report(client_name, tested, selected, [], []),
        encoding="utf-8",
    )
    print(f"\n  Rapport JSON  : {output_json}")
    print(f"  Rapport MD    : {output_md}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test moteur sur un dossier client — génère accounting_proposal pour chaque facture.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemples :
  python scripts/test_client_folder_accounting_proposals.py --list-clients
  python scripts/test_client_folder_accounting_proposals.py --client-name "BOULANGERIE L'UNIVERS DU PAIN" --limit 10
  python scripts/test_client_folder_accounting_proposals.py --client-name "BOUCHERIE IFRI" --limit 5
  python scripts/test_client_folder_accounting_proposals.py --client-name "ASSAINIS" --limit 10
  python scripts/test_client_folder_accounting_proposals.py --siren 880517875 --limit 10
        """,
    )
    parser.add_argument(
        "--client-name",
        default=None,
        help="Nom du dossier client. Utilise --list-clients pour voir les noms valides.",
    )
    parser.add_argument(
        "--siren",
        default=None,
        help="SIREN (9 chiffres) du dossier client, alternative au nom.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Nombre maximum de factures à analyser (défaut: 10).",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Chemin du rapport JSON.",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Chemin du rapport Markdown.",
    )
    parser.add_argument(
        "--list-clients",
        action="store_true",
        help="Afficher la liste des dossiers clients connus et quitter.",
    )
    args = parser.parse_args()

    if args.list_clients:
        print("\nDossiers clients connus :")
        print(f"  {'Nom':<45} {'SIREN'}")
        print(f"  {'-'*45} {'-'*9}")
        for name in sorted(KNOWN_CLIENTS):
            print(f"  {name:<45} {KNOWN_CLIENTS[name]}")
        print()
        return

    client_name = args.client_name.strip() if args.client_name else None
    siren_arg = args.siren.strip() if args.siren else None

    # Default output paths at repo root
    if args.output_json:
        output_json = Path(args.output_json).resolve()
    else:
        slug = (client_name or siren_arg or "auto").lower().replace(" ", "_").replace("'", "")
        output_json = REPO_ROOT / f"client_folder_accounting_proposals_{slug}.json"

    if args.output_md:
        output_md = Path(args.output_md).resolve()
    else:
        slug = (client_name or siren_arg or "auto").lower().replace(" ", "_").replace("'", "")
        output_md = REPO_ROOT / f"client_folder_accounting_proposals_{slug}_summary.md"

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    run(
        client_name=client_name,
        siren=siren_arg,
        limit=max(1, args.limit),
        output_json=output_json,
        output_md=output_md,
    )


if __name__ == "__main__":
    main()
