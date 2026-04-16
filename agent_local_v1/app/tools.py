from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .config import PROJECT_DIR


MATCHER_PATH = PROJECT_DIR / "10_match_reference_v1.py"


class MatcherTool:
    def __init__(self) -> None:
        self._module = None
        self._refs = None

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
        article_source: str,
        metier_hint: str | None = None,
        tva_hint: float | None = None,
        top_n: int = 3,
        include_charges: bool = True,
    ) -> list[dict[str, Any]]:
        module = self._load_module()
        refs = self.load_references()
        return module.match_text(
            refs=refs,
            text=article_source,
            metier=metier_hint,
            top_n=top_n,
            tva_hint=tva_hint,
            include_charges=include_charges,
        )


matcher_tool = MatcherTool()
