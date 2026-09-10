from __future__ import annotations

import json

import pytest

from agent_local_v1.app.local_knowledge_bases import LocalKnowledgeBaseStore


def _payload() -> dict:
    return {
        "meta": {"nom": "Base de test"},
        "items": [
            {
                "article_source": "Libellé initial",
                "article_canonique": "libelle initial",
                "mots_cles": ["libelle", "initial"],
                "compte_comptable": "6281",
                "compte_comptable_libelle": "Concours divers - cotisations",
                "ape_context": ["4722Z"],
            }
        ],
    }


def test_update_and_delete_local_knowledge_base_item(tmp_path):
    frontend_data = tmp_path / "frontend" / "public" / "data"
    frontend_data.mkdir(parents=True)
    source = tmp_path / "base_charges_externes_v1.json"
    frontend_copy = frontend_data / source.name
    serialized = json.dumps(_payload(), ensure_ascii=False)
    source.write_text(serialized, encoding="utf-8")
    frontend_copy.write_text(serialized, encoding="utf-8")
    store = LocalKnowledgeBaseStore(root=tmp_path, frontend_data_dir=frontend_data)

    updated = store.update_item(
        base_key="global",
        item_index=0,
        expected_article_source="Libellé initial",
        expected_account="6281",
        expected_account_label="Concours divers - cotisations",
        article_source="Libellé corrigé",
        compte_comptable="6227",
        compte_comptable_libelle="Honoraires juridiques corrigés",
    )

    assert updated["article_source"] == "Libellé corrigé"
    assert updated["article_canonique"] == "libelle corrige"
    assert updated["compte_comptable"] == "6227"
    assert updated["compte_comptable_libelle"] == "Honoraires juridiques corrigés"
    assert updated["account_label"] == "Honoraires juridiques corrigés"
    assert json.loads(source.read_text(encoding="utf-8")) == json.loads(
        frontend_copy.read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="référentiel a changé"):
        store.delete_item(
            base_key="global",
            item_index=0,
            expected_article_source="Libellé initial",
            expected_account="6281",
        )

    deleted = store.delete_item(
        base_key="global",
        item_index=0,
        expected_article_source="Libellé corrigé",
        expected_account="6227",
    )
    assert deleted["article_source"] == "Libellé corrigé"
    assert json.loads(source.read_text(encoding="utf-8"))["items"] == []
    assert json.loads(frontend_copy.read_text(encoding="utf-8"))["items"] == []
