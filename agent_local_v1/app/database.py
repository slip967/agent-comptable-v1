from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
import warnings
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

from .config import MEMORY_COUCH_DB, MEMORY_DOC_PARTITION, MEMORY_PAGE_SIZE
from .loader import normalize_text
from .schemas import AnalysisHistoryRecord, HumanValidationRecord


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEGACY_SQLITE_FILE = DATA_DIR / "agent_memory.sqlite3"
LEGACY_VALIDATIONS_FILE = DATA_DIR / "validation_memory.jsonl"
LEGACY_ANALYSIS_HISTORY_FILE = DATA_DIR / "analysis_history.jsonl"
DATABASE_FILE = f"couchdb://{MEMORY_COUCH_DB}"
LEGACY_IMPORT_VERSION = "couchdb_v1"
MIGRATION_DOC_ID = f"{MEMORY_DOC_PARTITION}:meta:agent_local_memory_store"
VALIDATION_DOC_KIND = "human_validation"
ANALYSIS_DOC_KIND = "analysis_history"
PATTERN_DOC_KIND = "validation_pattern"
META_DOC_KIND = "memory_store_meta"
PATTERN_SCOPE_WEIGHTS = {
    "article_supplier": 1.0,
    "article_metier": 0.75,
    "article_only": 0.45,
}
PATTERN_SCOPE_LABELS = {
    "article_supplier": "article + fournisseur",
    "article_metier": "article + metier",
    "article_only": "article",
}

COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
COUCHDB_USER = os.getenv(
    "COUCHDB_USER",
    os.getenv("COUCHDB_USERNAME", DEFAULT_COUCHDB_USER),
)
COUCHDB_PASS = os.getenv(
    "COUCHDB_PASS",
    os.getenv("COUCHDB_PASSWORD", DEFAULT_COUCHDB_PASS),
)

_APP_FILE = Path(__file__).resolve()
_SEARCH_ROOTS = [
    _APP_FILE.parent,
    _APP_FILE.parent.parent,
    _APP_FILE.parent.parent.parent,
    _APP_FILE.parent.parent.parent.parent,
]

def _resolve_existing_path(raw_value: str | None) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""

    direct = Path(value)
    if direct.exists():
        return str(direct)

    name = direct.name
    if not name:
        return value

    for root in _SEARCH_ROOTS:
        candidate = root / name
        if candidate.exists():
            return str(candidate)

    return value

CLIENT_CERT = _resolve_existing_path(os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT))
CLIENT_KEY = _resolve_existing_path(os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY))
CA_CERT = _resolve_existing_path(os.getenv("CA_CERT", DEFAULT_CA_CERT))


def _normalize_optional_context(value: str | None) -> str:
    return normalize_text(value or "")


def _build_lookup_key(
    article_source: str,
    metier_hint: str | None = None,
    fournisseur_hint: str | None = None,
) -> str:
    article_source_normalized = normalize_text(article_source)
    metier_hint_normalized = _normalize_optional_context(metier_hint)
    fournisseur_hint_normalized = _normalize_optional_context(fournisseur_hint)
    return f"{article_source_normalized}::{metier_hint_normalized}::{fournisseur_hint_normalized}"


def http_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.auth = (COUCHDB_USER, COUCHDB_PASS)

    cert_path = Path(CLIENT_CERT) if CLIENT_CERT else None
    key_path = Path(CLIENT_KEY) if CLIENT_KEY else None
    if cert_path and key_path and cert_path.exists() and key_path.exists():
        session.cert = (str(cert_path), str(key_path))
    elif CLIENT_CERT or CLIENT_KEY:
        warnings.warn(
            f"CouchDB client certificate not loaded because the files are missing: cert={CLIENT_CERT!r}, key={CLIENT_KEY!r}",
            RuntimeWarning,
        )

    ca_path = Path(CA_CERT) if CA_CERT else None
    session.verify = str(ca_path) if ca_path and ca_path.exists() else True
    session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))
    return session


def _couch_request(
    sess: requests.Session,
    db: str,
    method: str,
    path: str = "",
    *,
    allow_404: bool = False,
    **kwargs,
) -> dict:
    if path:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}/{path}"
    else:
        url = f"{COUCHDB_URL}/{quote(db, safe='')}"
    response = sess.request(method, url, timeout=120, **kwargs)
    if response.status_code == 404 and allow_404:
        return {}
    response.raise_for_status()
    if response.content:
        return response.json()
    return {}


def _fetch_existing_revs(sess: requests.Session, db: str, ids: list[str]) -> dict[str, str]:
    revs: dict[str, str] = {}
    if not ids:
        return revs

    for start in range(0, len(ids), 300):
        chunk = ids[start : start + 300]
        result = _couch_request(sess, db, "POST", "_all_docs", json={"keys": chunk})
        for row in result.get("rows", []):
            doc_id = str(row.get("id") or "").strip()
            value = row.get("value") or {}
            rev = str(value.get("rev") or "").strip()
            if doc_id and rev:
                revs[doc_id] = rev
    return revs


def _fetch_docs_by_ids(sess: requests.Session, db: str, ids: list[str]) -> dict[str, dict]:
    docs_by_id: dict[str, dict] = {}
    if not ids:
        return docs_by_id

    for start in range(0, len(ids), 300):
        chunk = ids[start : start + 300]
        result = _couch_request(
            sess,
            db,
            "POST",
            "_all_docs",
            json={"keys": chunk, "include_docs": True},
        )
        for row in result.get("rows", []):
            doc = row.get("doc")
            if not isinstance(doc, dict):
                continue
            doc_id = str(doc.get("_id") or "").strip()
            if doc_id:
                docs_by_id[doc_id] = doc
    return docs_by_id


def _bulk_upsert_docs(sess: requests.Session, db: str, docs: list[dict]) -> None:
    if not docs:
        return

    revs = _fetch_existing_revs(sess, db, [str(doc["_id"]) for doc in docs if doc.get("_id")])
    prepared: list[dict] = []
    for doc in docs:
        current = dict(doc)
        rev = revs.get(str(current.get("_id") or ""))
        if rev:
            current["_rev"] = rev
        prepared.append(current)

    for start in range(0, len(prepared), 200):
        chunk = prepared[start : start + 200]
        _couch_request(sess, db, "POST", "_bulk_docs", json={"docs": chunk})


def _fetch_docs_by_selector(
    selector: dict,
    *,
    fields: list[str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    sess = http_session()
    docs: list[dict] = []
    bookmark: str | None = None
    page_size = MEMORY_PAGE_SIZE if limit is None else max(1, min(limit, MEMORY_PAGE_SIZE))

    while True:
        payload: dict[str, object] = {
            "selector": selector,
            "limit": page_size,
        }
        if fields:
            payload["fields"] = fields
        if bookmark:
            payload["bookmark"] = bookmark

        result = _couch_request(sess, MEMORY_COUCH_DB, "POST", "_find", json=payload)
        chunk = result.get("docs") or []
        if not chunk:
            break
        docs.extend(doc for doc in chunk if isinstance(doc, dict))
        if limit is not None and len(docs) >= limit:
            return docs[:limit]

        new_bookmark = str(result.get("bookmark") or "").strip()
        if len(chunk) < page_size or not new_bookmark or new_bookmark == bookmark:
            break
        bookmark = new_bookmark

    return docs


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _read_legacy_sqlite_payloads(table_name: str) -> list[dict]:
    if not LEGACY_SQLITE_FILE.exists():
        return []

    with sqlite3.connect(LEGACY_SQLITE_FILE) as conn:
        rows = conn.execute(f"SELECT payload_json FROM {table_name}").fetchall()

    payloads: list[dict] = []
    for row in rows:
        try:
            payloads.append(json.loads(row[0]))
        except Exception:
            continue
    return payloads


def _coerce_validation_record(row: dict) -> HumanValidationRecord | None:
    payload = dict(row)
    article_source = str(payload.get("article_source") or "").strip()
    created_at = str(payload.get("created_at") or "").strip()
    decision_humaine = str(payload.get("decision_humaine") or "").strip()
    if not article_source or not created_at or not decision_humaine:
        return None

    payload.setdefault("fournisseur_hint", None)
    payload["article_source_normalized"] = payload.get("article_source_normalized") or normalize_text(
        article_source
    )
    payload["lookup_key"] = payload.get("lookup_key") or _build_lookup_key(
        article_source,
        payload.get("metier_hint"),
        payload.get("fournisseur_hint"),
    )
    return HumanValidationRecord(**payload)


def _coerce_analysis_history_record(row: dict) -> AnalysisHistoryRecord | None:
    payload = dict(row)
    article_source = str(payload.get("article_source") or "").strip()
    created_at = str(payload.get("created_at") or "").strip()
    decision = str(payload.get("decision") or "").strip()
    if not article_source or not created_at or not decision:
        return None

    payload.setdefault("fournisseur_hint", None)
    payload.setdefault("include_charges", True)
    payload.setdefault("source", "engine")
    payload.setdefault("candidats", [])
    payload["article_source_normalized"] = payload.get("article_source_normalized") or normalize_text(
        article_source
    )
    payload["lookup_key"] = payload.get("lookup_key") or _build_lookup_key(
        article_source,
        payload.get("metier_hint"),
        payload.get("fournisseur_hint"),
    )
    return AnalysisHistoryRecord(**payload)


def _validation_doc_id(record: HumanValidationRecord) -> str:
    digest_source = "|".join(
        [
            record.lookup_key,
            record.article_source,
            record.created_at,
            record.decision_humaine,
            record.compte_comptable_final or "",
        ]
    )
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:20]
    return f"{MEMORY_DOC_PARTITION}:validation:{digest}"


def _analysis_doc_id(record: AnalysisHistoryRecord) -> str:
    digest_source = "|".join(
        [
            record.lookup_key,
            record.article_source,
            record.created_at,
            record.decision,
            record.source,
            record.compte_comptable or "",
        ]
    )
    digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:20]
    return f"{MEMORY_DOC_PARTITION}:analysis:{digest}"


def _validation_doc(record: HumanValidationRecord) -> dict:
    payload = record.model_dump()
    return {
        "_id": _validation_doc_id(record),
        "p": VALIDATION_DOC_KIND,
        "data": {
            "collection": "AgentLocalMemory",
            "type": "HumanValidation",
            "sub_type": "accounting",
        },
        "lookup_key": record.lookup_key,
        "article_source": record.article_source,
        "article_source_normalized": record.article_source_normalized,
        "fournisseur_hint": record.fournisseur_hint,
        "fournisseur_hint_normalized": _normalize_optional_context(record.fournisseur_hint),
        "metier_hint": record.metier_hint,
        "metier_hint_normalized": _normalize_optional_context(record.metier_hint),
        "decision_humaine": record.decision_humaine,
        "compte_comptable_final": record.compte_comptable_final,
        "created_at": record.created_at,
        "payload": payload,
    }


def _analysis_doc(record: AnalysisHistoryRecord) -> dict:
    payload = record.model_dump()
    return {
        "_id": _analysis_doc_id(record),
        "p": ANALYSIS_DOC_KIND,
        "data": {
            "collection": "AgentLocalMemory",
            "type": "AnalysisHistory",
            "sub_type": record.source,
        },
        "lookup_key": record.lookup_key,
        "article_source": record.article_source,
        "article_source_normalized": record.article_source_normalized,
        "fournisseur_hint": record.fournisseur_hint,
        "fournisseur_hint_normalized": _normalize_optional_context(record.fournisseur_hint),
        "metier_hint": record.metier_hint,
        "metier_hint_normalized": _normalize_optional_context(record.metier_hint),
        "decision": record.decision,
        "source": record.source,
        "compte_comptable": record.compte_comptable,
        "score_confiance": record.score_confiance,
        "created_at": record.created_at,
        "payload": payload,
    }


def _build_migration_meta(
    *,
    validations_imported: int,
    analyses_imported: int,
) -> dict:
    return {
        "_id": MIGRATION_DOC_ID,
        "p": META_DOC_KIND,
        "data": {
            "collection": "AgentLocalMemory",
            "type": "MigrationMeta",
            "sub_type": "legacy_import",
        },
        "migration_version": LEGACY_IMPORT_VERSION,
        "legacy_sqlite_file": str(LEGACY_SQLITE_FILE),
        "legacy_validations_file": str(LEGACY_VALIDATIONS_FILE),
        "legacy_analysis_history_file": str(LEGACY_ANALYSIS_HISTORY_FILE),
        "validations_imported": validations_imported,
        "analyses_imported": analyses_imported,
    }


def _build_pattern_scopes(
    article_source_normalized: str,
    metier_hint_normalized: str,
    fournisseur_hint_normalized: str,
) -> list[tuple[str, str]]:
    scopes = [("article_only", article_source_normalized)]
    if metier_hint_normalized:
        scopes.append(("article_metier", f"{article_source_normalized}::{metier_hint_normalized}"))
    if fournisseur_hint_normalized:
        scopes.append(("article_supplier", f"{article_source_normalized}::{fournisseur_hint_normalized}"))
    return scopes


def _pattern_doc_id(scope: str, pattern_key: str) -> str:
    digest = hashlib.sha1(f"{scope}|{pattern_key}".encode("utf-8")).hexdigest()[:20]
    return f"{MEMORY_DOC_PARTITION}:pattern:{scope}:{digest}"


def _make_pattern_doc(
    *,
    scope: str,
    pattern_key: str,
    article_source_normalized: str,
    metier_hint_normalized: str,
    fournisseur_hint_normalized: str,
) -> dict:
    return {
        "_id": _pattern_doc_id(scope, pattern_key),
        "p": PATTERN_DOC_KIND,
        "data": {
            "collection": "AgentLocalMemory",
            "type": "ValidationPattern",
            "sub_type": scope,
        },
        "scope": scope,
        "scope_label": PATTERN_SCOPE_LABELS.get(scope, scope),
        "pattern_key": pattern_key,
        "article_source_normalized": article_source_normalized,
        "metier_hint_normalized": metier_hint_normalized,
        "fournisseur_hint_normalized": fournisseur_hint_normalized,
        "support_total": 0,
        "reject_total": 0,
        "decision_counts": {},
        "account_counts": {},
        "recommended_account_counts": {},
        "latest_feedback_at": "",
        "latest_compte_comptable_final": "",
        "latest_recommended_account": "",
    }


def _increment_counter(mapping: dict, key: str | None, amount: int = 1) -> dict:
    current = dict(mapping or {})
    normalized_key = str(key or "").strip()
    if not normalized_key:
        return current
    current[normalized_key] = int(current.get(normalized_key) or 0) + amount
    return current


def _build_pattern_explanation(scopes: list[dict[str, object]]) -> str:
    if not scopes:
        return ""

    scope_bits: list[str] = []
    total_hits = 0
    for scope in scopes:
        label = str(scope.get("scope_label") or scope.get("scope") or "").strip()
        count = int(scope.get("count") or 0)
        support_total = int(scope.get("support_total") or 0)
        total_hits += count
        if label and count > 0 and support_total > 0:
            scope_bits.append(f"{label} ({count}/{support_total})")

    if not scope_bits:
        return ""

    return (
        f"Ce compte a deja ete retenu {total_hits} fois sur des validations humaines similaires via "
        f"{', '.join(scope_bits)}."
    )


def _aggregate_pattern_docs(pattern_docs: list[dict]) -> dict[str, dict[str, object]]:
    aggregated: dict[str, dict[str, object]] = {}

    for doc in pattern_docs:
        scope = str(doc.get("scope") or "").strip()
        support_total = int(doc.get("support_total") or 0)
        reject_total = int(doc.get("reject_total") or 0)
        account_counts = doc.get("account_counts") or {}
        if not scope or support_total <= 0 or not isinstance(account_counts, dict):
            continue

        acceptance_ratio = support_total / max(support_total + reject_total, 1)
        scope_weight = float(PATTERN_SCOPE_WEIGHTS.get(scope, 0.4))
        scope_label = str(doc.get("scope_label") or PATTERN_SCOPE_LABELS.get(scope, scope))

        for account, raw_count in account_counts.items():
            normalized_account = str(account or "").strip()
            count = int(raw_count or 0)
            if not normalized_account or count <= 0:
                continue

            share = count / support_total
            count_strength = min(count, 4) / 4.0
            support_strength = min(support_total, 6) / 6.0
            scope_value = (
                0.05
                + (0.45 * share)
                + (0.35 * count_strength)
                + (0.15 * support_strength)
            ) * acceptance_ratio

            stats = aggregated.setdefault(
                normalized_account,
                {
                    "weighted_score": 0.0,
                    "total_scope_weight": 0.0,
                    "total_count": 0,
                    "scopes": [],
                },
            )
            stats["weighted_score"] = float(stats["weighted_score"]) + (scope_weight * scope_value)
            stats["total_scope_weight"] = float(stats["total_scope_weight"]) + scope_weight
            stats["total_count"] = int(stats["total_count"]) + count
            stats["scopes"].append(
                {
                    "scope": scope,
                    "scope_label": scope_label,
                    "count": count,
                    "support_total": support_total,
                    "reject_total": reject_total,
                    "share": round(share, 4),
                    "acceptance_ratio": round(acceptance_ratio, 4),
                }
            )

    pattern_stats: dict[str, dict[str, object]] = {}
    for account, stats in aggregated.items():
        total_scope_weight = float(stats.get("total_scope_weight") or 0.0)
        if total_scope_weight <= 0:
            continue

        score = min(1.0, float(stats["weighted_score"]) / total_scope_weight)
        scopes = list(stats.get("scopes") or [])
        scopes.sort(
            key=lambda item: (
                -float(PATTERN_SCOPE_WEIGHTS.get(str(item.get("scope") or ""), 0.0)),
                -int(item.get("count") or 0),
            )
        )
        pattern_stats[account] = {
            "score": round(score, 4),
            "count": int(stats.get("total_count") or 0),
            "scope_count": len(scopes),
            "scopes": scopes,
            "explanation": _build_pattern_explanation(scopes),
        }

    return pattern_stats


def _build_fallback_pattern_docs(
    article_source_normalized: str,
    metier_hint_normalized: str,
    fournisseur_hint_normalized: str,
) -> list[dict]:
    validation_docs = _fetch_docs_by_selector(
        {
            "p": VALIDATION_DOC_KIND,
            "article_source_normalized": article_source_normalized,
        },
        fields=[
            "article_source_normalized",
            "metier_hint_normalized",
            "fournisseur_hint_normalized",
            "decision_humaine",
            "compte_comptable_final",
        ],
    )
    if not validation_docs:
        return []

    grouped: dict[str, dict] = {}
    desired_scopes = _build_pattern_scopes(
        article_source_normalized,
        metier_hint_normalized,
        fournisseur_hint_normalized,
    )
    for scope, pattern_key in desired_scopes:
        grouped[_pattern_doc_id(scope, pattern_key)] = _make_pattern_doc(
            scope=scope,
            pattern_key=pattern_key,
            article_source_normalized=article_source_normalized,
            metier_hint_normalized=metier_hint_normalized,
            fournisseur_hint_normalized=fournisseur_hint_normalized,
        )

    for row in validation_docs:
        row_metier = str(row.get("metier_hint_normalized") or "").strip()
        row_supplier = str(row.get("fournisseur_hint_normalized") or "").strip()
        decision_humaine = str(row.get("decision_humaine") or "").strip()
        final_account = str(row.get("compte_comptable_final") or "").strip()

        applicable_scopes = [("article_only", article_source_normalized)]
        if metier_hint_normalized and row_metier == metier_hint_normalized:
            applicable_scopes.append(("article_metier", f"{article_source_normalized}::{metier_hint_normalized}"))
        if fournisseur_hint_normalized and row_supplier == fournisseur_hint_normalized:
            applicable_scopes.append(
                ("article_supplier", f"{article_source_normalized}::{fournisseur_hint_normalized}")
            )

        for scope, pattern_key in applicable_scopes:
            doc_id = _pattern_doc_id(scope, pattern_key)
            current = grouped.get(doc_id)
            if not current:
                continue
            current["decision_counts"] = _increment_counter(
                current.get("decision_counts") or {},
                decision_humaine,
            )
            if decision_humaine == "rejeter" or not final_account:
                current["reject_total"] = int(current.get("reject_total") or 0) + 1
            else:
                current["support_total"] = int(current.get("support_total") or 0) + 1
                current["account_counts"] = _increment_counter(
                    current.get("account_counts") or {},
                    final_account,
                )

    return list(grouped.values())


def _load_legacy_validation_records() -> list[HumanValidationRecord]:
    rows = _read_legacy_sqlite_payloads("validations")
    rows.extend(_read_jsonl(LEGACY_VALIDATIONS_FILE))
    records: list[HumanValidationRecord] = []
    seen: set[str] = set()
    for row in rows:
        try:
            record = _coerce_validation_record(row)
        except Exception:
            continue
        if record is None:
            continue
        doc_id = _validation_doc_id(record)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        records.append(record)
    return records


def _load_legacy_analysis_records() -> list[AnalysisHistoryRecord]:
    rows = _read_legacy_sqlite_payloads("analysis_history")
    rows.extend(_read_jsonl(LEGACY_ANALYSIS_HISTORY_FILE))
    records: list[AnalysisHistoryRecord] = []
    seen: set[str] = set()
    for row in rows:
        try:
            record = _coerce_analysis_history_record(row)
        except Exception:
            continue
        if record is None:
            continue
        doc_id = _analysis_doc_id(record)
        if doc_id in seen:
            continue
        seen.add(doc_id)
        records.append(record)
    return records


def _migrate_legacy_sources() -> None:
    sess = http_session()
    existing = _couch_request(
        sess,
        MEMORY_COUCH_DB,
        "GET",
        quote(MIGRATION_DOC_ID, safe=""),
        allow_404=True,
    )
    if existing and existing.get("migration_version") == LEGACY_IMPORT_VERSION:
        return

    validations = _load_legacy_validation_records()
    analyses = _load_legacy_analysis_records()

    docs: list[dict] = [_validation_doc(record) for record in validations]
    docs.extend(_analysis_doc(record) for record in analyses)
    docs.append(
        _build_migration_meta(
            validations_imported=len(validations),
            analyses_imported=len(analyses),
        )
    )
    _bulk_upsert_docs(sess, MEMORY_COUCH_DB, docs)


def ensure_database() -> None:
    _migrate_legacy_sources()


def insert_validation_record(record: HumanValidationRecord) -> None:
    ensure_database()
    sess = http_session()
    _bulk_upsert_docs(sess, MEMORY_COUCH_DB, [_validation_doc(record)])


def insert_analysis_history_record(record: AnalysisHistoryRecord) -> None:
    ensure_database()
    sess = http_session()
    _bulk_upsert_docs(sess, MEMORY_COUCH_DB, [_analysis_doc(record)])


def upsert_analysis_history_records(records: list[AnalysisHistoryRecord]) -> None:
    if not records:
        return

    ensure_database()
    sess = http_session()
    _bulk_upsert_docs(
        sess,
        MEMORY_COUCH_DB,
        [_analysis_doc(record) for record in records],
    )


def update_validation_patterns(
    record: HumanValidationRecord,
    recommended_account: str | None = None,
) -> None:
    ensure_database()

    article_source_normalized = record.article_source_normalized or normalize_text(record.article_source)
    metier_hint_normalized = _normalize_optional_context(record.metier_hint)
    fournisseur_hint_normalized = _normalize_optional_context(record.fournisseur_hint)
    scopes = _build_pattern_scopes(
        article_source_normalized,
        metier_hint_normalized,
        fournisseur_hint_normalized,
    )
    if not scopes:
        return

    sess = http_session()
    doc_ids = [_pattern_doc_id(scope, pattern_key) for scope, pattern_key in scopes]
    existing_docs = _fetch_docs_by_ids(sess, MEMORY_COUCH_DB, doc_ids)

    docs_to_save: list[dict] = []
    normalized_recommended_account = str(recommended_account or "").strip()
    normalized_final_account = str(record.compte_comptable_final or "").strip()

    for scope, pattern_key in scopes:
        doc_id = _pattern_doc_id(scope, pattern_key)
        current = dict(
            existing_docs.get(doc_id)
            or _make_pattern_doc(
                scope=scope,
                pattern_key=pattern_key,
                article_source_normalized=article_source_normalized,
                metier_hint_normalized=metier_hint_normalized,
                fournisseur_hint_normalized=fournisseur_hint_normalized,
            )
        )

        current["decision_counts"] = _increment_counter(
            current.get("decision_counts") or {},
            record.decision_humaine,
        )
        current["latest_feedback_at"] = record.created_at
        current["latest_compte_comptable_final"] = normalized_final_account
        current["latest_recommended_account"] = normalized_recommended_account

        if record.decision_humaine == "rejeter" or not normalized_final_account:
            current["reject_total"] = int(current.get("reject_total") or 0) + 1
        else:
            current["support_total"] = int(current.get("support_total") or 0) + 1
            current["account_counts"] = _increment_counter(
                current.get("account_counts") or {},
                normalized_final_account,
            )

        if normalized_recommended_account:
            current["recommended_account_counts"] = _increment_counter(
                current.get("recommended_account_counts") or {},
                normalized_recommended_account,
            )

        docs_to_save.append(current)

    _bulk_upsert_docs(sess, MEMORY_COUCH_DB, docs_to_save)


def fetch_validation_records(lookup_keys: set[str]) -> list[HumanValidationRecord]:
    if not lookup_keys:
        return []

    ensure_database()
    docs = _fetch_docs_by_selector(
        {
            "p": VALIDATION_DOC_KIND,
            "lookup_key": {"$in": sorted(lookup_keys)},
        },
        fields=["payload", "created_at"],
    )

    records: list[HumanValidationRecord] = []
    for doc in docs:
        try:
            records.append(HumanValidationRecord(**(doc.get("payload") or {})))
        except Exception:
            continue
    records.sort(key=lambda item: item.created_at, reverse=True)
    return records


def fetch_analysis_history_records(limit: int | None = 20) -> list[AnalysisHistoryRecord]:
    ensure_database()
    docs = _fetch_docs_by_selector(
        {"p": ANALYSIS_DOC_KIND},
        fields=["payload", "created_at"],
    )

    records: list[AnalysisHistoryRecord] = []
    for doc in docs:
        try:
            records.append(AnalysisHistoryRecord(**(doc.get("payload") or {})))
        except Exception:
            continue
    records.sort(key=lambda item: item.created_at, reverse=True)
    if limit is None:
        return records
    return records[:limit]


def fetch_latest_validation_timestamps() -> dict[str, str]:
    ensure_database()
    docs = _fetch_docs_by_selector(
        {"p": VALIDATION_DOC_KIND},
        fields=["lookup_key", "created_at"],
    )

    latest: dict[str, str] = {}
    for doc in docs:
        lookup_key = str(doc.get("lookup_key") or "").strip()
        created_at = str(doc.get("created_at") or "").strip()
        if not lookup_key or not created_at:
            continue
        previous = latest.get(lookup_key)
        if previous is None or created_at > previous:
            latest[lookup_key] = created_at
    return latest


def count_validation_stats() -> tuple[int, int]:
    ensure_database()
    docs = _fetch_docs_by_selector(
        {"p": VALIDATION_DOC_KIND},
        fields=["decision_humaine", "compte_comptable_final"],
    )

    total_records = len(docs)
    reusable_records = 0
    for doc in docs:
        decision_humaine = str(doc.get("decision_humaine") or "").strip()
        compte = str(doc.get("compte_comptable_final") or "").strip()
        if decision_humaine != "rejeter" and compte:
            reusable_records += 1
    return total_records, reusable_records


def fetch_supplier_account_stats(
    fournisseur_hint: str | None,
    metier_hint: str | None = None,
) -> dict[str, dict[str, object]]:
    normalized_supplier = _normalize_optional_context(fournisseur_hint)
    if not normalized_supplier:
        return {}

    normalized_metier = _normalize_optional_context(metier_hint)
    ensure_database()
    docs = _fetch_docs_by_selector(
        {
            "p": VALIDATION_DOC_KIND,
            "fournisseur_hint_normalized": normalized_supplier,
        },
        fields=[
            "fournisseur_hint_normalized",
            "metier_hint_normalized",
            "compte_comptable_final",
            "decision_humaine",
            "created_at",
        ],
    )

    account_stats: dict[str, dict[str, object]] = {}
    total_matches = 0
    for doc in docs:
        if str(doc.get("decision_humaine") or "").strip() == "rejeter":
            continue

        row_metier = str(doc.get("metier_hint_normalized") or "").strip()
        if normalized_metier and row_metier and row_metier != normalized_metier:
            continue

        account = str(doc.get("compte_comptable_final") or "").strip()
        if not account:
            continue

        total_matches += 1
        if account not in account_stats:
            account_stats[account] = {
                "count": 0,
                "latest_validation_at": str(doc.get("created_at") or "").strip(),
            }

        stats = account_stats[account]
        stats["count"] = int(stats["count"]) + 1
        stats["latest_validation_at"] = max(
            str(stats.get("latest_validation_at") or ""),
            str(doc.get("created_at") or "").strip(),
        )

    if total_matches == 0:
        return {}

    top_count = max(int(stats["count"]) for stats in account_stats.values())
    dominant_accounts = {
        account
        for account, stats in account_stats.items()
        if int(stats["count"]) == top_count
    }

    for account, stats in account_stats.items():
        count = int(stats["count"])
        stats["share"] = round(count / total_matches, 4)
        stats["total_matches"] = total_matches
        stats["is_dominant"] = count == top_count and len(dominant_accounts) == 1

    return account_stats


def get_supplier_memory(
    fournisseur_hint: str | None,
    metier_hint: str | None = None,
) -> dict[str, dict[str, object]]:
    return fetch_supplier_account_stats(
        fournisseur_hint=fournisseur_hint,
        metier_hint=metier_hint,
    )


def fetch_validation_pattern_stats(
    article_source: str,
    fournisseur_hint: str | None = None,
    metier_hint: str | None = None,
) -> dict[str, dict[str, object]]:
    article_source_normalized = normalize_text(article_source)
    if not article_source_normalized:
        return {}

    metier_hint_normalized = _normalize_optional_context(metier_hint)
    fournisseur_hint_normalized = _normalize_optional_context(fournisseur_hint)
    scopes = _build_pattern_scopes(
        article_source_normalized,
        metier_hint_normalized,
        fournisseur_hint_normalized,
    )
    sess = http_session()
    doc_ids = [_pattern_doc_id(scope, pattern_key) for scope, pattern_key in scopes]
    docs_by_id = _fetch_docs_by_ids(sess, MEMORY_COUCH_DB, doc_ids)
    pattern_docs = [
        docs_by_id.get(_pattern_doc_id(scope, pattern_key))
        for scope, pattern_key in scopes
        if docs_by_id.get(_pattern_doc_id(scope, pattern_key))
    ]
    if not pattern_docs:
        pattern_docs = _build_fallback_pattern_docs(
            article_source_normalized,
            metier_hint_normalized,
            fournisseur_hint_normalized,
        )

    return _aggregate_pattern_docs(pattern_docs)


def get_validation_patterns(
    article_source: str,
    fournisseur_hint: str | None = None,
    metier_hint: str | None = None,
) -> dict[str, dict[str, object]]:
    return fetch_validation_pattern_stats(
        article_source=article_source,
        fournisseur_hint=fournisseur_hint,
        metier_hint=metier_hint,
    )
