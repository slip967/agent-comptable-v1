from __future__ import annotations

import importlib.util
import json
import re
from threading import RLock
from pathlib import Path
from typing import Any

from .account_labels import get_account_label
from .config import PROJECT_DIR
from .loader import BASE_FILES, METIER_BY_FILE, normalize_text
from .schemas import KnowledgeBaseSummaryItem, KnowledgeBasesSummaryResponse


MATCHER_PATH = PROJECT_DIR / "10_match_reference_v1.py"

DISPLAY_LABELS = {
    "boulangerie": "Boulangerie",
    "boucherie": "Boucherie",
    "restaurant": "Restaurant",
    "btp": "BTP",
    "transport": "Transport",
    "epicerie": "Epicerie",
    "vtc": "VTC",
    "global": "Charges externes",
}


class LocalKnowledgeBaseStore:
    def __init__(self, root: Path = PROJECT_DIR, frontend_data_dir: Path | None = None) -> None:
        self._root = root
        self._frontend_data_dir = frontend_data_dir or root / "frontend" / "public" / "data"
        self._lock = RLock()
        self._module = None
        self._refs = None
        self._summary = None

    def _resolve_file(self, base_key: str) -> tuple[str, Path]:
        key = str(base_key or "").strip().lower()
        filename = next(
            (
                name
                for name in BASE_FILES
                if key in {name.lower(), METIER_BY_FILE.get(name, "").lower()}
            ),
            None,
        )
        if filename is None:
            raise KeyError("Base métier introuvable")
        return filename, self._root / filename

    @staticmethod
    def _read_payload(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise KeyError("Fichier de base métier introuvable")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("Structure JSON de base métier invalide")
        return payload

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def _write_payload(self, filename: str, payload: dict[str, Any]) -> None:
        self._atomic_write(self._root / filename, payload)
        frontend_copy = self._frontend_data_dir / filename
        if frontend_copy.exists():
            self._atomic_write(frontend_copy, payload)
        self._refs = None
        self._summary = None

    def get_bases(self) -> dict[str, Any]:
        bases = []
        with self._lock:
            for filename in BASE_FILES:
                path = self._root / filename
                if not path.exists():
                    continue
                payload = self._read_payload(path)
                metier_key = METIER_BY_FILE.get(filename, "")
                rows = [
                    {**item, "_item_index": index}
                    for index, item in enumerate(payload.get("items", []))
                    if isinstance(item, dict)
                ]
                bases.append(
                    {
                        "key": metier_key,
                        "label": DISPLAY_LABELS.get(metier_key, metier_key.title()),
                        "file": filename,
                        "meta": payload.get("meta") or {},
                        "items": rows,
                    }
                )
        return {"bases": bases}

    @staticmethod
    def _checked_item(
        payload: dict[str, Any],
        item_index: int,
        expected_article_source: str,
        expected_account: str | None,
        expected_account_label: str | None = None,
    ) -> dict[str, Any]:
        items = payload["items"]
        if item_index < 0 or item_index >= len(items) or not isinstance(items[item_index], dict):
            raise KeyError("Article source introuvable")
        item = items[item_index]
        if str(item.get("article_source") or "").strip() != str(expected_article_source or "").strip():
            raise ValueError("Le référentiel a changé. Rechargez la page avant de recommencer.")
        if expected_account is not None and str(item.get("compte_comptable") or "").strip() != str(expected_account).strip():
            raise ValueError("Le compte a changé. Rechargez la page avant de recommencer.")
        if expected_account_label is not None:
            current_label = str(
                item.get("compte_comptable_libelle")
                or item.get("account_label")
                or get_account_label(item.get("compte_comptable"))
                or ""
            ).strip()
            if current_label != str(expected_account_label).strip():
                raise ValueError("Le libellé du compte a changé. Rechargez la page avant de recommencer.")
        return item

    def update_item(
        self,
        *,
        base_key: str,
        item_index: int,
        expected_article_source: str,
        expected_account: str | None,
        expected_account_label: str | None,
        article_source: str,
        compte_comptable: str,
        compte_comptable_libelle: str,
    ) -> dict[str, Any]:
        clean_source = str(article_source or "").strip()
        clean_account = str(compte_comptable or "").strip()
        clean_account_label = str(compte_comptable_libelle or "").strip()
        if not clean_source:
            raise ValueError("Le libellé de l'article est obligatoire")
        if not re.fullmatch(r"\d{3,8}", clean_account):
            raise ValueError("Le compte comptable doit contenir entre 3 et 8 chiffres")
        if not clean_account_label:
            raise ValueError("Le libellé du compte est obligatoire")

        with self._lock:
            filename, path = self._resolve_file(base_key)
            payload = self._read_payload(path)
            item = self._checked_item(
                payload,
                item_index,
                expected_article_source,
                expected_account,
                expected_account_label,
            )
            source_changed = clean_source != str(item.get("article_source") or "").strip()
            account_changed = clean_account != str(item.get("compte_comptable") or "").strip()
            item["article_source"] = clean_source
            item["compte_comptable"] = clean_account
            if source_changed:
                normalized = normalize_text(clean_source)
                item["article_canonique"] = normalized
                item["mots_cles"] = normalized.split()
            if account_changed:
                old_label = str(expected_account_label or "").strip()
                if clean_account_label == old_label:
                    clean_account_label = get_account_label(clean_account) or clean_account_label
            item["compte_comptable_libelle"] = clean_account_label
            item["account_label"] = clean_account_label
            self._write_payload(filename, payload)
            return {**item, "_item_index": item_index}

    def delete_item(
        self,
        *,
        base_key: str,
        item_index: int,
        expected_article_source: str,
        expected_account: str | None,
    ) -> dict[str, Any]:
        with self._lock:
            filename, path = self._resolve_file(base_key)
            payload = self._read_payload(path)
            item = self._checked_item(
                payload, item_index, expected_article_source, expected_account
            )
            deleted = dict(item)
            del payload["items"][item_index]
            self._write_payload(filename, payload)
            return deleted

    def _load_module(self):
        if self._module is not None:
            return self._module

        spec = importlib.util.spec_from_file_location("match_reference_v1", MATCHER_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Impossible de charger {MATCHER_PATH}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module = module
        return module

    def load_references(self):
        if self._refs is not None:
            return self._refs

        module = self._load_module()
        self._refs = module.load_references()
        return self._refs

    def match_line(
        self,
        *,
        article_source: str,
        fournisseur_hint: str | None = None,
        metier_hint: str | None = None,
        client_ape_hint: str | None = None,
        supplier_ape_hint: str | None = None,
        tva_hint: float | None = None,
        top_n: int = 3,
        include_charges: bool = True,
        supplier_account_stats: dict[str, dict[str, object]] | None = None,
        validation_pattern_stats: dict[str, dict[str, object]] | None = None,
    ) -> list[dict[str, Any]]:
        module = self._load_module()
        refs = self.load_references()
        return module.match_text(
            refs=refs,
            text=article_source,
            fournisseur_hint=fournisseur_hint,
            metier=metier_hint,
            client_ape_hint=client_ape_hint,
            supplier_ape_hint=supplier_ape_hint,
            top_n=top_n,
            tva_hint=tva_hint,
            include_charges=include_charges,
            supplier_account_stats=supplier_account_stats,
            validation_pattern_stats=validation_pattern_stats,
        )

    def get_summary(self) -> KnowledgeBasesSummaryResponse:
        if self._summary is not None:
            return self._summary

        root = self._root
        items: list[KnowledgeBaseSummaryItem] = []
        total_articles = 0

        for filename in BASE_FILES:
            path = root / filename
            if not path.exists():
                continue

            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = [item for item in payload.get("items", []) if isinstance(item, dict)]
            article_count = len(rows)
            total_articles += article_count

            with_invoice_sources = sum(1 for row in rows if row.get("source_invoice_ids"))
            with_partitions = sum(1 for row in rows if row.get("partitions_sources"))
            metier_key = METIER_BY_FILE.get(filename, "")
            readiness = (
                "pret"
                if article_count > 0
                and with_invoice_sources == article_count
                and with_partitions == article_count
                else "a_controler"
            )

            items.append(
                KnowledgeBaseSummaryItem(
                    key=metier_key,
                    label=DISPLAY_LABELS.get(metier_key, metier_key.title()),
                    file=filename,
                    articles=article_count,
                    with_invoice_sources=with_invoice_sources,
                    with_partitions=with_partitions,
                    readiness=readiness,
                )
            )

        self._summary = KnowledgeBasesSummaryResponse(
            total_bases=len(items),
            total_articles=total_articles,
            items=items,
        )
        return self._summary


local_knowledge_bases = LocalKnowledgeBaseStore()
