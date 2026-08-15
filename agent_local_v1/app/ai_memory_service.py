from __future__ import annotations

import json
import threading
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .account_labels import get_account_label
from .human_validation_store import list_validation_items
from .loader import normalize_text


STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_memory_items.json"
_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text("[]", encoding="utf-8")


def _read_items_unlocked() -> list[dict[str, Any]]:
    _ensure_store()
    try:
        payload = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = []
    return payload if isinstance(payload, list) else []


def _write_items_unlocked(items: list[dict[str, Any]]) -> None:
    _ensure_store()
    STORE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _memory_key(item: dict[str, Any]) -> str:
    normalized_label = normalize_text(
        str(item.get("cleaned_text") or item.get("raw_text") or "").strip()
    )
    validation_result = item.get("human_validation_result") or {}
    action = str(validation_result.get("action") or "").strip()
    if action == "correct_account":
        validated_account = str(validation_result.get("corrected_account") or "").strip()
    elif action == "mark_non_comptable":
        validated_account = "NON_COMPTABLE"
    else:
        validated_account = str(item.get("recommended_account") or "").strip()

    supplier = normalize_text(str(item.get("supplier") or "").strip())
    client = normalize_text(str(item.get("client") or "").strip())
    return "::".join([normalized_label, validated_account, supplier, client])


def _extract_activity(item: dict[str, Any]) -> str:
    detected_activity = str(item.get("detected_activity") or "").strip()
    if detected_activity:
        return detected_activity
    if str(item.get("metier_hint") or "").strip():
        return str(item.get("metier_hint") or "").strip()
    top_candidates = item.get("top_candidates") or []
    if isinstance(top_candidates, list):
        for candidate in top_candidates:
            if not isinstance(candidate, dict):
                continue
            base = str(candidate.get("base") or "").strip()
            if base:
                return base
    return ""


def _extract_ape(item: dict[str, Any]) -> str:
    for key in (
        "client_ape",
        "client_ape_hint",
        "supplier_ape",
        "supplier_ape_hint",
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    ape_context = item.get("ape_context") or []
    if isinstance(ape_context, list):
        for value in ape_context:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def _should_build_memory_item(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip()
    return status in {
        "validated",
        "corrected",
        "non_comptable",
        "enrichment_proposed",
    }


def _memory_status(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip()
    if status == "non_comptable":
        return "non_comptable_candidate"
    return "candidate"


def _validated_account(item: dict[str, Any]) -> tuple[str, str]:
    validation_result = item.get("human_validation_result") or {}
    action = str(validation_result.get("action") or "").strip()
    if action == "correct_account":
        account = str(validation_result.get("corrected_account") or "").strip()
        label = str(validation_result.get("corrected_account_label") or "").strip()
        return account, label or get_account_label(account)
    if action == "mark_non_comptable":
        return "", "Non comptable"
    account = str(item.get("recommended_account") or "").strip()
    label = str(item.get("account_label") or "").strip() or get_account_label(account)
    return account, label


def _build_memory_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if not _should_build_memory_item(item):
        return None

    raw_text = str(item.get("raw_text") or "").strip()
    normalized_label = normalize_text(str(item.get("cleaned_text") or raw_text))
    if not normalized_label:
        return None

    validated_account, validated_label = _validated_account(item)
    memory_status = _memory_status(item)
    created_at = str(item.get("created_at") or _now_iso())
    last_seen_at = str(
        ((item.get("human_validation_result") or {}).get("validated_at"))
        or created_at
        or _now_iso()
    )
    return {
        "memory_id": _memory_key(item),
        "created_at": created_at,
        "source": "human_validation",
        "validation_id": str(item.get("validation_id") or "").strip(),
        "normalized_label": normalized_label,
        "raw_text_examples": [raw_text] if raw_text else [],
        "validated_account": validated_account,
        "validated_account_label": validated_label,
        "engine_account": str(item.get("recommended_account") or "").strip(),
        "activity": _extract_activity(item),
        "supplier": str(item.get("supplier") or "").strip(),
        "client": str(item.get("client") or "").strip(),
        "ape": _extract_ape(item),
        "validation_count": 1,
        "status": memory_status,
        "last_seen_at": last_seen_at,
    }


def _merge_memory_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for item in items:
        memory_id = str(item.get("memory_id") or "").strip()
        if not memory_id:
            continue
        existing = merged.get(memory_id)
        if existing is None:
            merged[memory_id] = deepcopy(item)
            continue

        existing["validation_count"] = int(existing.get("validation_count") or 0) + int(
            item.get("validation_count") or 1
        )
        existing["last_seen_at"] = max(
            str(existing.get("last_seen_at") or ""),
            str(item.get("last_seen_at") or ""),
        )
        existing["created_at"] = min(
            str(existing.get("created_at") or ""),
            str(item.get("created_at") or ""),
        )

        examples = list(existing.get("raw_text_examples") or [])
        for example in item.get("raw_text_examples") or []:
            text = str(example or "").strip()
            if text and text not in examples:
                examples.append(text)
        existing["raw_text_examples"] = examples[:5]
        if existing.get("status") != "non_comptable_candidate":
            existing["status"] = str(item.get("status") or existing.get("status") or "candidate")
    return list(merged.values())


def rebuild_memory_from_validations() -> dict[str, Any]:
    validation_items = list_validation_items(limit=10000)
    built_items = []
    for item in validation_items:
        memory_item = _build_memory_item(item)
        if memory_item is not None:
            built_items.append(memory_item)

    merged_items = _merge_memory_items(built_items)
    with _LOCK:
        _write_items_unlocked(merged_items)

    return {
        "ok": True,
        "rebuilt_at": _now_iso(),
        "items_count": len(merged_items),
    }


def upsert_memory_from_validation_item(item: dict[str, Any]) -> dict[str, Any] | None:
    memory_item = _build_memory_item(item)
    if memory_item is None:
        return None

    with _LOCK:
        items = _read_items_unlocked()
        items.append(memory_item)
        merged_items = _merge_memory_items(items)
        _write_items_unlocked(merged_items)
        for current in merged_items:
            if str(current.get("memory_id") or "") == str(memory_item.get("memory_id") or ""):
                return current
    return memory_item


def list_memory_items(limit: int = 200) -> list[dict[str, Any]]:
    with _LOCK:
        items = _read_items_unlocked()

    if not items:
        rebuilt = rebuild_memory_from_validations()
        if rebuilt.get("items_count"):
            with _LOCK:
                items = _read_items_unlocked()

    ordered_items = sorted(
        items,
        key=lambda item: (
            str(item.get("last_seen_at") or ""),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    return ordered_items[: max(int(limit or 200), 1)]


def resolve_ai_memory_rule(
    *,
    raw_text: str,
    supplier: str | None = None,
    memory_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return the strongest unambiguous expert rule for an invoice line.

    A normalized label match always has priority. Supplier-only rules are used
    only when the supplier history points to one unambiguous account, avoiding
    an arbitrary account assignment when a supplier legitimately uses several
    expense accounts.
    """
    normalized_label = normalize_text(str(raw_text or "").strip())
    normalized_supplier = normalize_text(str(supplier or "").strip())
    if not normalized_label:
        return None

    items = memory_items if memory_items is not None else list_memory_items(limit=10000)
    label_matches: list[tuple[float, int, str, dict[str, Any]]] = []
    supplier_matches: list[dict[str, Any]] = []

    for item in items or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in {"candidate", "non_comptable_candidate"}:
            continue

        item_label = normalize_text(str(item.get("normalized_label") or "").strip())
        item_supplier = normalize_text(str(item.get("supplier") or "").strip())
        account = str(item.get("validated_account") or "").strip()
        if status != "non_comptable_candidate" and not account:
            continue

        # A supplier-scoped expert rule must never become a global rule merely
        # because the invoice supplier is missing from the current context.
        supplier_compatible = not item_supplier or (
            bool(normalized_supplier) and item_supplier == normalized_supplier
        )
        similarity = SequenceMatcher(None, normalized_label, item_label).ratio() if item_label else 0.0
        if supplier_compatible and (similarity == 1.0 or similarity >= 0.94):
            label_matches.append(
                (
                    similarity,
                    int(item.get("validation_count") or 1),
                    str(item.get("last_seen_at") or ""),
                    item,
                )
            )

        if (
            normalized_supplier
            and item_supplier == normalized_supplier
            and status == "candidate"
            and account
        ):
            supplier_matches.append(item)

    if label_matches:
        similarity, _, _, selected = max(label_matches, key=lambda row: (row[0], row[1], row[2]))
        resolved = deepcopy(selected)
        resolved["match_type"] = "label_exact" if similarity == 1.0 else "label_similar"
        resolved["match_similarity"] = round(similarity, 4)
        return resolved

    if not supplier_matches:
        return None

    account_stats: dict[str, dict[str, Any]] = {}
    total = 0
    for item in supplier_matches:
        account = str(item.get("validated_account") or "").strip()
        count = max(int(item.get("validation_count") or 1), 1)
        total += count
        stats = account_stats.setdefault(account, {"count": 0, "items": []})
        stats["count"] += count
        stats["items"].append(item)

    ranked = sorted(account_stats.items(), key=lambda row: (-int(row[1]["count"]), row[0]))
    if not ranked:
        return None
    top_account, top_stats = ranked[0]
    top_count = int(top_stats["count"])
    second_count = int(ranked[1][1]["count"]) if len(ranked) > 1 else 0
    share = top_count / total if total else 0.0
    unambiguous = len(ranked) == 1 or (top_count > second_count and top_count >= 2 and share >= 0.75)
    if not unambiguous:
        return None

    selected = max(
        top_stats["items"],
        key=lambda item: (
            int(item.get("validation_count") or 1),
            str(item.get("last_seen_at") or ""),
        ),
    )
    resolved = deepcopy(selected)
    resolved["validated_account"] = top_account
    resolved["match_type"] = "supplier"
    resolved["match_similarity"] = 1.0
    resolved["supplier_account_share"] = round(share, 4)
    return resolved
