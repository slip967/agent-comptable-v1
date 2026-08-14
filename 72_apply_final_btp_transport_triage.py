#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_PATH = SCRIPT_DIR / "45_integrate_triaged_candidates_into_bases.py"
SUMMARY_JSON = SCRIPT_DIR / "apply_final_btp_transport_triage_summary.json"
SUMMARY_MD = SCRIPT_DIR / "apply_final_btp_transport_triage_summary.md"


TARGETS = {
    "btp": {
        "product_file": "base_produits_btp_v1.json",
        "charges_file": "base_charges_externes_v1.json",
        "keep_labels": (
            "Casque de chantier Oceanic 2 RB40 taille 53-61 cm blanc",
            "Jugulaire sans mentonniere pour casque SC5101 et SC5101A3",
            "Luminaires au dessus des acces - Suivant CCTP",
            "Luminaires plafond des porches - Suivant CCTP",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE (PATTES ANTI RELEVE DETAIL 3 Long : 3000 Dev : 227",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE 30X30X30 Long : 4000 Dev : 90",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE OMEGA Long : 4000 Dev : 147",
            "PN CHANTIER INTERDIT 330X200 621209",
            "Plaque de platre BA13 Placoflam A2 2,5x1,2m R=0,04 m2.k/w",
            "TA-E 80X60 W0 GOUL DISTRI AU METRE",
            "Anemometre pour store - suivant CCTP",
            "BAST SAP/EPI TRCL2 63X160 3M00",
            "BOB. PROTECT. ULTIBAT 75M.",
            "CONTRE PLAQUE FILME PLUS 15MM 250X125X15MM",
            "CROISILLONS EN T 3MM 250 PIECES",
        ),
        "move_labels": (
            "Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau",
            "Amenée-repli de l'atelier de forage des micropieux",
            "Dépose et repose cheminement de cables",
            "Dépose et repose de luminaires au dessus des acces",
            "Dépose et repose de luminaires plafond des porches",
            "Dépose et repose des anémométres pour store",
            "ECO PARTICIPATION PMCB BPE",
            "Fo et pose d'un coffret d'installation électrique provisoire",
            "Fo et pose de cable 3G2,5",
            "Fo et pose de cäble 3G6",
            "Fo et pose de cäble 5G16",
            "Fo et pose de fourreau diamétre 25",
            "Fo et pose de fourreau diamétre 40",
            "Réalisation de la Mission G3",
            "Réalisation de réseaux enterrés pour passage de câbles",
            "Travaux de sous-traitance - électricité",
            "Travaux exécutés - Sous-traitance",
            "Démontage et remontage de filins acier inox",
            "Dépose / repose des fixations des filins acier inox",
            "Implantation des micropieux",
            "Installation de chantier",
            "Montage d'échafaudage - CHANTIER 5 RUE DE L'ABBE DELHOTEL 55600 AVIOTH",
            "Prestation de sous traitance",
            "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
            "Amenée-repli de l'atelier de l'injection",
            "Fo et pose de grosse boites de dérivation",
            "Jour de location",
            "Campagne de test d'arrachement",
        ),
        "exclude_labels": (
            "Electricité",
            "Ascenseur",
        ),
    },
    "btp_with_accounts": {
        "product_file": "base_produits_btp_v1_with_accounts.json",
        "charges_file": "base_charges_externes_v1_with_accounts.json",
        "keep_labels": (
            "Casque de chantier Oceanic 2 RB40 taille 53-61 cm blanc",
            "Jugulaire sans mentonniere pour casque SC5101 et SC5101A3",
            "Luminaires au dessus des acces - Suivant CCTP",
            "Luminaires plafond des porches - Suivant CCTP",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE (PATTES ANTI RELEVE DETAIL 3 Long : 3000 Dev : 227",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE 30X30X30 Long : 4000 Dev : 90",
            "PLIAGE GALVA 15/10 EXCEDENTAIRE OMEGA Long : 4000 Dev : 147",
            "PN CHANTIER INTERDIT 330X200 621209",
            "Plaque de platre BA13 Placoflam A2 2,5x1,2m R=0,04 m2.k/w",
            "TA-E 80X60 W0 GOUL DISTRI AU METRE",
            "Anemometre pour store - suivant CCTP",
            "BAST SAP/EPI TRCL2 63X160 3M00",
            "BOB. PROTECT. ULTIBAT 75M.",
            "CONTRE PLAQUE FILME PLUS 15MM 250X125X15MM",
            "CROISILLONS EN T 3MM 250 PIECES",
        ),
        "move_labels": (
            "Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau",
            "Amenée-repli de l'atelier de forage des micropieux",
            "Dépose et repose cheminement de cables",
            "Dépose et repose de luminaires au dessus des acces",
            "Dépose et repose de luminaires plafond des porches",
            "Dépose et repose des anémométres pour store",
            "ECO PARTICIPATION PMCB BPE",
            "Fo et pose d'un coffret d'installation électrique provisoire",
            "Fo et pose de cable 3G2,5",
            "Fo et pose de cäble 3G6",
            "Fo et pose de cäble 5G16",
            "Fo et pose de fourreau diamétre 25",
            "Fo et pose de fourreau diamétre 40",
            "Réalisation de la Mission G3",
            "Réalisation de réseaux enterrés pour passage de câbles",
            "Travaux de sous-traitance - électricité",
            "Travaux exécutés - Sous-traitance",
            "Démontage et remontage de filins acier inox",
            "Dépose / repose des fixations des filins acier inox",
            "Implantation des micropieux",
            "Installation de chantier",
            "Montage d'échafaudage - CHANTIER 5 RUE DE L'ABBE DELHOTEL 55600 AVIOTH",
            "Prestation de sous traitance",
            "Essai de contrôle sur un micropieu de l'ouvrage selon EC7",
            "Amenée-repli de l'atelier de l'injection",
            "Fo et pose de grosse boites de dérivation",
            "Jour de location",
            "Campagne de test d'arrachement",
        ),
        "exclude_labels": (
            "Electricité",
            "Ascenseur",
        ),
    },
    "transport": {
        "product_file": "base_produits_transport_v1.json",
        "charges_file": "base_charges_externes_v1.json",
        "keep_labels": (
            "Garnitures de frein essieu avant",
            "Bloc optique avant droit remplacer",
            "Bouclier avant complet",
            "Inserts décoratifs carrosserie",
            "Ingredients Peinture",
            "Garnitures et disques de frein essieu avant",
            "Habillages compartiment moteur",
            "Garnitures de frein essieu arrière",
            "Paliers (tous) pour suspension du moteur remplacer (Moteur depose)",
            "Remplacement(s): huile moteur, filtre a huile moteur, filtre ä huile d'embrayage",
            "Jambe de suspension gauche",
            "Remplacer le bloc optique avant gauche",
            "Supplement a la maintenance remplacer le filtre a poussieres",
            "Supplement a la maintenance: remplacer la cartouche de filtre a air",
            "B: remplacer le liquide de frein",
            "Ingredient peinture",
            "LUBRIFIANT TOIT OUVRANT(PDP)",
            "Garnitures et disques de frein essieu arriere",
            "RENOV.ULTIME MEGUIARS 473 ML (PROMO)",
            "ULTIM.BRILLANCE MEGUIARS 709ML (PROMO)",
            "VIS DE FERMETURE",
            "022 H.MOT 229-52 vrac 5W30",
            "120186/CONSOLE",
            "Cloison sous aile avant gauche remplacer",
            "H.MOT 229.5 1L OW40",
            "JEU DE CART. FILTR. CARB",
            "Polish",
            "RAIL DE RECOUVREMENT",
            "RESSORT",
            "Remplacer la pile de la clé-émetteur 022 PILE 2032",
            "TUBE DE GUIDAGE",
            "TUBE DE TROP-PLEIN",
            "VIS 6 PANS AVEC BRIDE",
        ),
        "move_labels": (
            "Effectuer un essai sur route",
            "Effectuer un test rapide",
            "Deposer, poser completement le pare-chocs avant",
            "Déposer, poser 2 blocs optiques avant",
            "Effectuer la maintenance A avec pack plus",
            "Peindre aile avant droite niveau 1-M MET/UNI (peinture deux couches)",
            "Peindre la porte avant droite niveau 1-M MET/UNI (peinture deux couches)",
            "Pose kit réparation optique avant gauche",
            "Revêtement du bouclier avant appliquer peinture finition et marier teintes par pistolage véh. avec pack Carrosserie AMG",
            "REVISION A7 VIDANGE MOTEUR FILTRE",
            "Demonter, monter 4 roues completes",
            "Deposer, poser, remplacer selon besoin la pompe a liquide de refroidissement (Moteur depose)",
            "Direction assistee remplacer",
            "Effectuer la dépose de roue pour la roue complete",
            "Effectuer la maintenance B avec pack plus",
            "Maintenance A avec pack plus",
            "Peindre l'aile avant gauche niveau 1-M MET/UNI (peinture deux couches)",
            "Programmer et coder le calculateur (Apres test rapide)",
            "Regler le projecteur a LED",
            "Remplacer le liquide de refroidissement avec antigel, controler l'etancheite",
            "Revetement du bouclier avant appliquer peinture finition et marier teintes par pistolage",
            "Supplement a la maintenance: Facturé selon temps passé",
            "Supplément ä la maintenance",
            "demonter, monter 2 roues",
            "B: remplacer le liquide de frein - Supplément a la maintenance",
            "Deposer, poser, selon constat 4 garnitures de frein de l'essieu arriere (Roues completes demontees)",
            "Démonter, monter 2 roues complètes",
            "Effectuer la maintenance avec pack plus",
            "Main d'oeuvre atelier",
            "Pack Remote - Commande à distance vitres/toit ouvrant 360 jours, Verrouillage et déverrouillage à distance des portes 360 jours, Alerte voiturier 360 jours, Personnalisation 360 jours, Emplacement du véhicule 360 jours, Géolocalisation du véhicule 360 jours, Localiser le véhicule 360 jours, Localisation du véhicule 360 jours. Chassis: WDD2130041A652450. Ce produit est valable un an à partir de la date d'activation",
            "Regler le projecteur a LED (Apres test rapide)",
            "Réparation carrosserie avant droit",
            "Vidange boite de vitesses automatique",
            "Nettoyage mécanisme toit ouvrant",
            "Visite technique périodique",
            "Lavage express",
        ),
        "exclude_labels": (
            "Supplement a la maintenance: Vous allez recevoir un email 5 Etoiles",
            "NCS, MO-S",
            "VIS",
        ),
    },
    "transport_with_accounts": {
        "product_file": "base_produits_transport_v1_with_accounts.json",
        "charges_file": "base_charges_externes_v1_with_accounts.json",
        "keep_labels": (
            "Garnitures de frein essieu avant",
            "Bloc optique avant droit remplacer",
            "Bouclier avant complet",
            "Inserts décoratifs carrosserie",
            "Ingredients Peinture",
            "Garnitures et disques de frein essieu avant",
            "Habillages compartiment moteur",
            "Garnitures de frein essieu arrière",
            "Paliers (tous) pour suspension du moteur remplacer (Moteur depose)",
            "Remplacement(s): huile moteur, filtre a huile moteur, filtre ä huile d'embrayage",
            "Jambe de suspension gauche",
            "Remplacer le bloc optique avant gauche",
            "Supplement a la maintenance remplacer le filtre a poussieres",
            "Supplement a la maintenance: remplacer la cartouche de filtre a air",
            "B: remplacer le liquide de frein",
            "Ingredient peinture",
            "LUBRIFIANT TOIT OUVRANT(PDP)",
            "Garnitures et disques de frein essieu arriere",
            "RENOV.ULTIME MEGUIARS 473 ML (PROMO)",
            "ULTIM.BRILLANCE MEGUIARS 709ML (PROMO)",
            "VIS DE FERMETURE",
            "022 H.MOT 229-52 vrac 5W30",
            "120186/CONSOLE",
            "Cloison sous aile avant gauche remplacer",
            "H.MOT 229.5 1L OW40",
            "JEU DE CART. FILTR. CARB",
            "Polish",
            "RAIL DE RECOUVREMENT",
            "RESSORT",
            "Remplacer la pile de la clé-émetteur 022 PILE 2032",
            "TUBE DE GUIDAGE",
            "TUBE DE TROP-PLEIN",
            "VIS 6 PANS AVEC BRIDE",
        ),
        "move_labels": (
            "Effectuer un essai sur route",
            "Effectuer un test rapide",
            "Deposer, poser completement le pare-chocs avant",
            "Déposer, poser 2 blocs optiques avant",
            "Effectuer la maintenance A avec pack plus",
            "Peindre aile avant droite niveau 1-M MET/UNI (peinture deux couches)",
            "Peindre la porte avant droite niveau 1-M MET/UNI (peinture deux couches)",
            "Pose kit réparation optique avant gauche",
            "Revêtement du bouclier avant appliquer peinture finition et marier teintes par pistolage véh. avec pack Carrosserie AMG",
            "REVISION A7 VIDANGE MOTEUR FILTRE",
            "Demonter, monter 4 roues completes",
            "Deposer, poser, remplacer selon besoin la pompe a liquide de refroidissement (Moteur depose)",
            "Direction assistee remplacer",
            "Effectuer la dépose de roue pour la roue complete",
            "Effectuer la maintenance B avec pack plus",
            "Maintenance A avec pack plus",
            "Peindre l'aile avant gauche niveau 1-M MET/UNI (peinture deux couches)",
            "Programmer et coder le calculateur (Apres test rapide)",
            "Regler le projecteur a LED",
            "Remplacer le liquide de refroidissement avec antigel, controler l'etancheite",
            "Revetement du bouclier avant appliquer peinture finition et marier teintes par pistolage",
            "Supplement a la maintenance: Facturé selon temps passé",
            "Supplément ä la maintenance",
            "demonter, monter 2 roues",
            "B: remplacer le liquide de frein - Supplément a la maintenance",
            "Deposer, poser, selon constat 4 garnitures de frein de l'essieu arriere (Roues completes demontees)",
            "Démonter, monter 2 roues complètes",
            "Effectuer la maintenance avec pack plus",
            "Main d'oeuvre atelier",
            "Pack Remote - Commande à distance vitres/toit ouvrant 360 jours, Verrouillage et déverrouillage à distance des portes 360 jours, Alerte voiturier 360 jours, Personnalisation 360 jours, Emplacement du véhicule 360 jours, Géolocalisation du véhicule 360 jours, Localiser le véhicule 360 jours, Localisation du véhicule 360 jours. Chassis: WDD2130041A652450. Ce produit est valable un an à partir de la date d'activation",
            "Regler le projecteur a LED (Apres test rapide)",
            "Réparation carrosserie avant droit",
            "Vidange boite de vitesses automatique",
            "Nettoyage mécanisme toit ouvrant",
            "Visite technique périodique",
            "Lavage express",
        ),
        "exclude_labels": (
            "Supplement a la maintenance: Vous allez recevoir un email 5 Etoiles",
            "NCS, MO-S",
            "VIS",
        ),
    },
}


def load_rules_module():
    spec = importlib.util.spec_from_file_location("triage_rules_module", RULES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {RULES_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(module, value: str) -> str:
    return module.normalize_text(str(value or ""))


def build_charge_item(module, source_item: dict, origin: str) -> dict:
    article_source = str(source_item.get("article_source") or "").strip()
    compte = str(source_item.get("compte_comptable") or "").strip()
    charge_item = deepcopy(source_item)
    charge_item["categorie"] = "charges_externes"
    charge_item["fournisseur_type"] = "service"

    if origin.startswith("transport"):
        classification = module.classify_charge(article_source, compte)
        charge_item["sous_profil"] = classification["sous_profil"]
        charge_item["nature_charge"] = classification["nature_charge"]
        charge_item["profil_facturation"] = classification["profil_facturation"]
        charge_item["profil_facturation_champs"] = module.default_charges_champs(
            classification["profil_facturation"]
        )
        charge_item["sous_categorie"] = module.CHARGES_SOUS_CATEGORIE_MAP.get(
            classification["sous_profil"], "charges_generales"
        )
        charge_item["classification_reason"] = classification["classification_reason"]
        charge_item["classification_version"] = "charges_externes_rules_v1_transport_final_triage"
    else:
        charge_item["sous_profil"] = "autres_charges_externes"
        charge_item["nature_charge"] = "prestation"
        charge_item["profil_facturation"] = "intervention_ponctuelle"
        charge_item["profil_facturation_champs"] = module.default_charges_champs("intervention_ponctuelle")
        charge_item["sous_categorie"] = module.CHARGES_SOUS_CATEGORIE_MAP.get(
            "autres_charges_externes", "charges_generales"
        )
        charge_item["classification_reason"] = "manual_reclass:prestation_technique_chantier"
        charge_item["classification_version"] = "charges_externes_rules_v1_btp_final_triage"

    note = str(charge_item.get("notes") or "").strip()
    suffix = (
        "Reclasse depuis a_valider transport vers charges_externes apres triage final."
        if origin.startswith("transport")
        else "Reclasse depuis a_valider btp vers charges_externes apres triage final."
    )
    charge_item["notes"] = f"{note} | {suffix}".strip(" |")
    charge_item["reclassement_source"] = "final_btp_transport_triage_v1"
    charge_item["origine_base_metier"] = "transport" if origin.startswith("transport") else "btp"
    charge_item.pop("validation_status", None)
    charge_item.pop("validation_reason", None)
    charge_item.pop("validation_note", None)
    return charge_item


def build_active_item(source_item: dict, origin: str) -> dict:
    item = deepcopy(source_item)
    for key in ("validation_status", "validation_reason", "validation_note"):
        item.pop(key, None)
    note = str(item.get("notes") or "").strip()
    suffix = (
        "Promu depuis a_valider vers items apres triage final transport."
        if origin.startswith("transport")
        else "Promu depuis a_valider vers items apres triage final btp."
    )
    item["notes"] = f"{note} | {suffix}".strip(" |")
    item["promotion_source"] = "final_btp_transport_triage_v1"
    return item


def process_target(module, key: str, cfg: dict) -> dict:
    product_path = SCRIPT_DIR / cfg["product_file"]
    charges_path = SCRIPT_DIR / cfg["charges_file"]

    keep_keys = {normalize(module, label) for label in cfg["keep_labels"]}
    move_keys = {normalize(module, label) for label in cfg["move_labels"]}
    exclude_keys = {normalize(module, label) for label in cfg["exclude_labels"]}

    product_payload = json.loads(product_path.read_text(encoding="utf-8"))
    charges_payload = json.loads(charges_path.read_text(encoding="utf-8"))

    product_items = product_payload.get("items") or []
    product_a_valider = product_payload.get("a_valider") or []
    charges_items = charges_payload.get("items") or []

    product_existing = {
        normalize(module, str(item.get("article_source") or "")) for item in product_items if isinstance(item, dict)
    }
    charges_existing = {
        normalize(module, str(item.get("article_source") or "")) for item in charges_items if isinstance(item, dict)
    }

    kept_a_valider = []
    promoted = []
    moved = []
    excluded = []
    duplicates_removed = []

    for item in product_a_valider:
        if not isinstance(item, dict):
            kept_a_valider.append(item)
            continue

        label = str(item.get("article_source") or "").strip()
        norm_label = normalize(module, label)

        if norm_label in keep_keys:
            if norm_label in product_existing:
                duplicates_removed.append(label)
            else:
                promoted_item = build_active_item(item, key)
                product_items.append(promoted_item)
                product_existing.add(norm_label)
                promoted.append(label)
            continue

        if norm_label in move_keys:
            if norm_label not in charges_existing:
                charge_item = build_charge_item(module, item, key)
                charges_items.append(charge_item)
                charges_existing.add(norm_label)
                moved.append(label)
            else:
                duplicates_removed.append(label)
            continue

        if norm_label in exclude_keys:
            excluded.append(label)
            continue

        kept_a_valider.append(item)

    product_payload["items"] = product_items
    product_payload["a_valider"] = kept_a_valider
    product_payload.setdefault("meta", {})
    product_payload["meta"]["items_count"] = len(product_items)
    product_payload["meta"]["a_valider_count"] = len(kept_a_valider)
    product_payload["meta"]["total_entries_count"] = len(product_items) + len(kept_a_valider)
    product_payload["meta"]["final_btp_transport_triage_v1"] = {
        "updated_at": module.now_iso(),
        "promoted_to_items": promoted,
        "moved_to_charges_externes": moved,
        "excluded": excluded,
        "duplicates_removed": duplicates_removed,
        "charges_target": charges_path.name,
    }

    charges_payload["items"] = charges_items
    charges_payload.setdefault("meta", {})
    charges_payload["meta"]["items_count"] = len(charges_items)
    charges_payload["meta"]["final_btp_transport_triage_v1"] = {
        "updated_at": module.now_iso(),
        "added_from_product_a_valider": moved,
        "source_product_file": product_path.name,
    }
    module.refresh_charges_profile_enrichment(charges_payload)

    product_path.write_text(json.dumps(product_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    charges_path.write_text(json.dumps(charges_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "target": key,
        "product_file": product_path.name,
        "charges_file": charges_path.name,
        "promoted_count": len(promoted),
        "moved_count": len(moved),
        "excluded_count": len(excluded),
        "duplicates_removed_count": len(duplicates_removed),
        "product_items_after": len(product_items),
        "product_a_valider_after": len(kept_a_valider),
        "charges_items_after": len(charges_items),
        "promoted_labels": promoted,
        "moved_labels": moved,
        "excluded_labels": excluded,
        "duplicates_removed_labels": duplicates_removed,
    }


def write_summary(results: list[dict]) -> None:
    SUMMARY_JSON.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Apply Final BTP / Transport Triage", ""]
    for result in results:
        lines.extend(
            [
                f"## {result['target']}",
                "",
                f"- product_file: `{result['product_file']}`",
                f"- charges_file: `{result['charges_file']}`",
                f"- promoted_count: `{result['promoted_count']}`",
                f"- moved_count: `{result['moved_count']}`",
                f"- excluded_count: `{result['excluded_count']}`",
                f"- duplicates_removed_count: `{result['duplicates_removed_count']}`",
                f"- product_items_after: `{result['product_items_after']}`",
                f"- product_a_valider_after: `{result['product_a_valider_after']}`",
                f"- charges_items_after: `{result['charges_items_after']}`",
                "",
            ]
        )
    SUMMARY_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    module = load_rules_module()
    results = [process_target(module, key, cfg) for key, cfg in TARGETS.items()]
    write_summary(results)
    print(f"Wrote {SUMMARY_JSON.name}")
    print(f"Wrote {SUMMARY_MD.name}")
    for result in results:
        print(
            f"{result['target']}: promoted={result['promoted_count']} moved={result['moved_count']} "
            f"excluded={result['excluded_count']} a_valider_after={result['product_a_valider_after']}"
        )


if __name__ == "__main__":
    main()
