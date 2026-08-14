#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
SUMMARY_JSON = SCRIPT_DIR / "cleanup_article_sources_summary.json"
SUMMARY_MD = SCRIPT_DIR / "cleanup_article_sources_summary.md"

TARGET_FILES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boucherie_v1_with_accounts.json",
    "base_produits_restaurant_v1.json",
    "base_produits_restaurant_v1_with_accounts.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_boulangerie_v1_with_accounts.json",
    "base_produits_btp_v1.json",
    "base_produits_btp_v1_with_accounts.json",
    "base_produits_transport_v1.json",
    "base_produits_transport_v1_with_accounts.json",
    "base_charges_externes_v1.json",
    "base_charges_externes_v1_with_accounts.json",
]

EXACT_REPLACEMENTS = {
    "COCACOLA B0ITE SLIM 33CL": "COCACOLA BOITE SLIM 33CL",
    "SCHEPPES AGRUM 24X25CL VIDE": "SCHWEPPES AGRUM 24X25CL VIDE",
    "GIGOT AGN S/0S S/V NZ HAL": "GIGOT AGN S/OS S/V NZ HAL",
    "GIGOT AGN A/0S HAL PAC S/V NZ": "GIGOT AGN A/OS HAL PAC S/V NZ",
    "HUILE MOT 229-52 v rac 5W30": "HUILE MOT 229-52 vrac 5W30",
    "ADBLUE vraC": "ADBLUE vrac",
    "Pack de 100.00 € de crédit lavage a valoir sur les stations partenaires": "Crédit lavage 100 EUR",
    "CARTOUCHE DE FILTRE Facturé selon bareme de temps Facturé selon temps passé": "CARTOUCHE DE FILTRE",
    "CC: REVISION A7 Maintenance VIDANGE MOTEUR FILTRE": "REVISION A7 VIDANGE MOTEUR FILTRE",
    "Déposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu avant (Roues completes démontées) Sur véh. avec étrier fixe": "Garnitures de frein essieu avant",
    "Bouclier avant complet desassembler, assembler, selon constat rempi. piece(s). (pare-chocs depose)": "Bouclier avant complet",
    "Deposer, poser les inserts decoratifs et les pieces rapportees, concerne pour remise en etat. carrosserie/ mise en peinture": "Inserts décoratifs carrosserie",
    "Remplacer les garnitures de frein et les disques de frein de l'essieu avant (roues complètes démontées) sur véh. avec étrier fixe": "Garnitures et disques de frein essieu avant",
    "Deposer, poser, remplacer selon besoin tous les habillages du compartiment moteur et toutes les garnitures sur soubassement": "Habillages compartiment moteur",
    "Deposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu arriere (Roues completes demontees)": "Garnitures de frein essieu arrière",
    "Remplacer la jambe de suspension gauche de l'essieu avant sur veh. a suspension electrohydrauligue": "Jambe de suspension gauche",
    "Réparation selon rapport d'expertise - Travaux effectués: Contrôle des trains avant et arrière, Remplacement, peinture (Aile avant droite, Capot moteur avant, Charnière droite de capot, Pare-chocs avant, Support avant d'aile avant droit, Pare boue avant droit partie avant, Pare boue avant droit partie arrière, Tirant de bras de suspension avant droit, Bras inférieur de suspension avant, Protection sous moteur, Boîtier de direction, Equilibreur droit de capot, Jante avant droite, Porte moyeu avant droit, Bras supérieur de suspension, Amortisseur avant droit et avant gauche, Pneumatique avant droit, Projecteur droit, Support de capteur latéral droit d'aide au stationnement, Joint de porte avant droite, Rétroviseur droit, Répétiteur de rétroviseur), Réparation, peinture (Haut de caisse droit, Elargisseur de bas de caisse, Porte avant droite, Doublure de passage de roue avant droit)": "Réparation carrosserie avant droit",
    "Supplément a la maintenance: Nettoyer, graisser le mécanisme de toit ouvrant panoramique": "Nettoyage mécanisme toit ouvrant",
    "Remplacer les garnitures de frein et les disques de frein de l'essieu arrière (roues complètes démontées)": "Garnitures et disques de frein essieu arrière",
    "Supplément a la maintenance B: effectuer la vidange d'huile dans la boite de vitesses automatique Sur véh. avec boite de vitesses 725.0": "Vidange boite de vitesses automatique",
    "BuTure Booster Batterie 2500A 20000Mah Démarreurs De Batterie avec Compresseur (Jusqu'a 8 Essence Ou Diesel), avec Écran LCD, Compresseur d'air Portable avec Gonfleur De Pneus Voiture 150psi": "Booster Batterie 2500A 20000mAh avec compresseur",
    "LOYER PRINCIPAL Du 01/01/2025 Au 31/03/2025 Indice 06 4TR2022": "LOYER PRINCIPAL 01/01/2025-31/03/2025",
    "Nettoyage en cours et en fin de chantier. Nettoyage fin de chantier et mise en décharge de déchets du chantier.": "Nettoyage fin de chantier",
    "Déposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu arrière (Roues complètes démontées)": "Garnitures de frein essieu arrière",
    "Remplacer les garnitures de frein et les disques de frein de l'essieu arriere (roues complètes démontées)": "Garnitures et disques de frein essieu arrière",
    "Box 2éme ETAGE 4.5m2 / 11m3 Forfait mensuel": "Box 2eme ETAGE 4.5m2 11m3 Forfait mensuel",
    "Box 2éme ETAGE 4.5m2 / 11m3 Forfait mensuel 69.17 EUR": "Box 2eme ETAGE 4.5m2 11m3 Forfait mensuel 69.17 EUR",
}

REGEX_REPLACEMENTS = [
    (re.compile(r"\bB0ITE\b"), "BOITE"),
    (re.compile(r"S/0S"), "S/OS"),
    (re.compile(r"A/0S"), "A/OS"),
    (re.compile(r"\bv rac\b", re.IGNORECASE), "vrac"),
    (re.compile(r"\b2éme\b", re.IGNORECASE), "2eme"),
    (re.compile(r"\s{2,}"), " "),
]


def load_helper_module():
    spec = importlib.util.spec_from_file_location("triage_helper_module", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_label(label: str) -> str:
    updated = str(label or "").strip()
    updated = EXACT_REPLACEMENTS.get(updated, updated)
    for pattern, repl in REGEX_REPLACEMENTS:
        updated = pattern.sub(repl, updated)
    return updated.strip()


def update_item(helper, item: dict) -> tuple[bool, str | None, str | None]:
    original = str(item.get("article_source") or "").strip()
    if not original:
        return False, None, None
    cleaned = clean_label(original)
    changed = cleaned != original
    item["article_source"] = cleaned
    item["article_canonique"] = helper.normalize_text(cleaned)
    item["mots_cles"] = helper.tokenize(cleaned)[:6]
    if changed:
        item["article_source_original"] = original
        note = str(item.get("notes") or "").strip()
        cleanup_note = "article_source_cleanup_v1"
        if cleanup_note not in note:
            item["notes"] = f"{note} | {cleanup_note}".strip(" |")
        return True, original, cleaned
    return False, None, None


def process_file(helper, path: str) -> dict:
    payload = json.loads((SCRIPT_DIR / path).read_text(encoding="utf-8-sig"))
    existing_norms = {}
    collisions = []
    changes = []

    for bucket in ("items", "a_valider"):
        for idx, item in enumerate(payload.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            changed, original, cleaned = update_item(helper, item)
            cleaned_norm = helper.normalize_text(item.get("article_source") or "")
            if cleaned_norm:
                previous = existing_norms.get(cleaned_norm)
                current_ref = f"{bucket}[{idx}]"
                if previous and previous != current_ref:
                    collisions.append(
                        {
                            "bucket": bucket,
                            "index": idx,
                            "cleaned_label": item.get("article_source"),
                            "conflicts_with": previous,
                        }
                    )
                else:
                    existing_norms[cleaned_norm] = current_ref
            if changed:
                changes.append({"from": original, "to": cleaned})

    payload.setdefault("meta", {})
    payload["meta"]["article_source_cleanup_v1"] = {
        "updated_at": helper.now_iso(),
        "changed_count": len(changes),
        "collision_count": len(collisions),
    }
    (SCRIPT_DIR / path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"changed_count": len(changes), "changes": changes, "collisions": collisions}


def write_markdown(summary: dict) -> None:
    lines = ["# Nettoyage article_source", ""]
    for file_name, data in summary.items():
        lines.append(f"## {file_name}")
        lines.append(f"- changés: {data['changed_count']}")
        lines.append(f"- collisions: {len(data['collisions'])}")
        for change in data["changes"][:12]:
            lines.append(f"- {change['from']} -> {change['to']}")
        lines.append("")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    helper = load_helper_module()
    summary = {path: process_file(helper, path) for path in TARGET_FILES}
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(summary)
    total = sum(data["changed_count"] for data in summary.values())
    print(json.dumps({"total_changed": total, "files": {k: v["changed_count"] for k, v in summary.items()}}, ensure_ascii=False, indent=2))
    print(f"[OK] summary_json={SUMMARY_JSON}")
    print(f"[OK] summary_md={SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
