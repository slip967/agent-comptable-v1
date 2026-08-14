#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TARGETS = {
    "transport": [
        "base_produits_transport_v1.json",
        "base_produits_transport_v1_with_accounts.json",
    ],
    "vtc": [
        "base_produits_vtc_v1.json",
        "base_produits_vtc_v1_with_accounts.json",
    ],
    "restaurant": [
        "base_produits_restaurant_v1.json",
        "base_produits_restaurant_v1_with_accounts.json",
    ],
    "epicerie": [
        "base_produits_epicerie_v1.json",
        "base_produits_epicerie_v1_with_accounts.json",
    ],
}

SUMMARY_MD = ROOT / "normalisation_comptable_metiers_v3_summary.md"
SUMMARY_JSON = ROOT / "normalisation_comptable_metiers_v3_summary.json"

FUEL_PATTERNS = [
    re.compile(r"\bgazole\b", re.I),
    re.compile(r"\bdiesel\b", re.I),
    re.compile(r"\badblue\b", re.I),
    re.compile(r"\bgo\s*\(?(carburant|gazole)?\)?\b", re.I),
]

CARBURANT_PATTERN = re.compile(r"\bcarburant\b", re.I)
CARBURANT_EXCLUDE_PATTERN = re.compile(r"\bfiltre\b", re.I)

TELECOM_COMM_PATTERNS = [
    re.compile(r"communications?", re.I),
    re.compile(r"sms/?mms", re.I),
    re.compile(r"\bhors[- ]forfait\b", re.I),
    re.compile(r"\binternational\b", re.I),
]

TELECOM_SUB_PATTERNS = [
    re.compile(r"\bbbox\b", re.I),
    re.compile(r"\bfreebox\b", re.I),
    re.compile(r"\bfibre\b", re.I),
    re.compile(r"\bwifi\b", re.I),
    re.compile(r"\brepeteur\b", re.I),
    re.compile(r"\babonn", re.I),
    re.compile(r"\binternet\b", re.I),
    re.compile(r"\bcanal\b", re.I),
    re.compile(r"\bdisney premium\b", re.I),
    re.compile(r"\bvos abonnements\b", re.I),
    re.compile(r"\bservices de free\b", re.I),
    re.compile(r"\bmulti[- ]sim\b", re.I),
    re.compile(r"\bsim\b", re.I),
    re.compile(r"\bmobile\b", re.I),
    re.compile(r"\bprime\b", re.I),
    re.compile(r"\bappels illimites\b", re.I),
    re.compile(r"\bforfait.*\b(go|mo)\b", re.I),
    re.compile(r"\bclient\b.*\b(go|mo)\b", re.I),
    re.compile(r"\binternet\b.*\b(go|mo)\b", re.I),
    re.compile(r"\bb ?you\b", re.I),
    re.compile(r"\bsensation\b", re.I),
]

AUTO_SERVICE_PATTERNS = [
    re.compile(r"\blavage\b", re.I),
    re.compile(r"\bcredit lavage\b", re.I),
    re.compile(r"\bvidange\b", re.I),
    re.compile(r"\bmaintenance\b", re.I),
    re.compile(r"main d.?oeuvre", re.I),
    re.compile(r"\bremplacer\b", re.I),
    re.compile(r"\bapres controle\b", re.I),
    re.compile(r"\bdiagnostic\b", re.I),
    re.compile(r"\beffectuer\b", re.I),
    re.compile(r"\bessai\b", re.I),
    re.compile(r"\btest rapide\b", re.I),
    re.compile(r"\bpeindre\b", re.I),
    re.compile(r"\bentretien/?reparation\b", re.I),
    re.compile(r"\breparation carrosserie\b", re.I),
    re.compile(r"\bnettoyage\b", re.I),
    re.compile(r"\bvisite technique\b", re.I),
    re.compile(r"\bdeposer\b", re.I),
    re.compile(r"\bposer\b", re.I),
    re.compile(r"\bdemonter\b", re.I),
    re.compile(r"\bmonter\b", re.I),
    re.compile(r"\bcontrole\b", re.I),
]

RESTAURANT_BEVERAGE_PATTERNS = [
    re.compile(r"\bcoca\b", re.I),
    re.compile(r"\bcocacola\b", re.I),
    re.compile(r"\bfanta\b", re.I),
    re.compile(r"\boasis\b", re.I),
    re.compile(r"\bperrier\b", re.I),
    re.compile(r"\bfuzetea\b", re.I),
    re.compile(r"\bhawai\b", re.I),
    re.compile(r"\blipton\b", re.I),
    re.compile(r"\bcristal", re.I),
    re.compile(r"\beau\b", re.I),
]

RESTAURANT_INGREDIENT_PATTERNS = [
    re.compile(r"\bharissa\b", re.I),
    re.compile(r"\bolive\b", re.I),
    re.compile(r"\bhuile\b", re.I),
    re.compile(r"\bthon\b", re.I),
    re.compile(r"\bail\b", re.I),
    re.compile(r"\bpersil\b", re.I),
    re.compile(r"\bcanelle\b", re.I),
    re.compile(r"\bcolorant\b", re.I),
]

RESTAURANT_MEAT_PATTERNS = [
    re.compile(r"\bpoulet\b", re.I),
    re.compile(r"\bmerguez\b", re.I),
    re.compile(r"\bviande\b", re.I),
    re.compile(r"\bsaucisse\b", re.I),
]

EPICERIE_RECHARGE_PATTERNS = [
    re.compile(r"\brecharge\b", re.I),
    re.compile(r"\blycamobile\b", re.I),
    re.compile(r"\blebara\b", re.I),
    re.compile(r"\bsyma", re.I),
    re.compile(r"\bsfr\b", re.I),
    re.compile(r"\borange\b", re.I),
    re.compile(r"\bpcs creacard\b", re.I),
]

EPICERIE_BEVERAGE_PATTERNS = [
    re.compile(r"\bcoca\b", re.I),
    re.compile(r"\bcocacola\b", re.I),
    re.compile(r"\bfanta\b", re.I),
    re.compile(r"\boasis\b", re.I),
    re.compile(r"\bcristal", re.I),
    re.compile(r"\bvolvic\b", re.I),
    re.compile(r"\bevian\b", re.I),
    re.compile(r"\bvimto\b", re.I),
    re.compile(r"\bhawai\b", re.I),
    re.compile(r"\bice tea\b", re.I),
    re.compile(r"\beau\b", re.I),
]

EXACT_ACCOUNT_OVERRIDES = {
    "transport": {
        "KIT DE REPARATION SUPPORT BAGUETTE ENJOLIVEUSE": ("6062", "piece_auto"),
    },
    "vtc": {
        "DS FORFAIT DOSE LG (PDP PD)": ("6062", "piece_auto"),
        "FORFAIT1 000 KM -ADV750N -2022": ("6062", "piece_auto"),
        "FORFAIT TAXI PLAQUETTES AR": ("615", "prestation_auto"),
        "Forfait entretien/réparation": ("615", "prestation_auto"),
        "KIT DE REPARATION SUPPORT BAGUETTE ENJOLIVEUSE": ("6062", "piece_auto"),
        "Montant forfaitaire collecté pour le compte et sur ordre de l'Organisme Technique Central (arrêté ministériel du 4 octobre 1991) modifié": ("615", "prestation_auto"),
        "OPPO Find X3 Pro 5G 256Go Noir": ("6068", "restauration_correction_ciblee"),
        "Galaxy S24 Indigo 128 Go, IMEI: 355680657471025": ("6063", "restauration_correction_ciblee"),
        "SanDisk Ultra 128 Go Clé USB 3.0 jusqu'à 130 Mo/s": ("6063", "restauration_correction_ciblee"),
    },
    "epicerie": {
        "SPRING ROLL pastry Pate a Samoussa 30 pcs/sht x 550g": ("6011", "restauration_correction_ciblee"),
        "SPRING ROLL pastry Pate a Samoussa 30 pcs/sht x 550g SPRING HOME DS27": ("601", "restauration_correction_ciblee"),
    },
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return re.sub(r"\s+", " ", value)


def build_text(item: dict) -> str:
    return " ".join(
        [
            str(item.get("article_source") or ""),
            str(item.get("article_canonique") or ""),
            " ".join(item.get("mots_cles") or []),
        ]
    )


def matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def infer_account(metier: str, item: dict) -> tuple[str | None, str | None]:
    text = build_text(item)
    source = str(item.get("article_source") or "").strip()

    override = EXACT_ACCOUNT_OVERRIDES.get(metier, {}).get(source)
    if override:
        return override

    if metier in {"transport", "vtc"}:
        if matches_any(text, TELECOM_COMM_PATTERNS):
            return ("626", "telecom_communications")
        if matches_any(text, TELECOM_SUB_PATTERNS):
            return ("6261", "telecom_abonnements")
        if matches_any(text, FUEL_PATTERNS) or (
            CARBURANT_PATTERN.search(text) and not CARBURANT_EXCLUDE_PATTERN.search(text)
        ):
            return ("6063", "carburant_et_adblue")
        if matches_any(text, AUTO_SERVICE_PATTERNS):
            return ("615", "prestation_auto")
        return (None, None)

    if metier == "restaurant":
        if matches_any(text, RESTAURANT_MEAT_PATTERNS):
            return ("6011", "matiere_premiere_viande")
        if matches_any(text, RESTAURANT_BEVERAGE_PATTERNS):
            return ("607", "revente_boissons")
        if matches_any(text, RESTAURANT_INGREDIENT_PATTERNS):
            return ("601", "matiere_premiere_cuisine")
        return (None, None)

    if metier == "epicerie":
        if matches_any(text, EPICERIE_RECHARGE_PATTERNS):
            return ("607", "revente_recharges")
        if matches_any(text, EPICERIE_BEVERAGE_PATTERNS):
            return ("607", "revente_boissons")
        return (None, None)

    return (None, None)


def update_meta(payload: dict, summary: dict) -> None:
    payload.setdefault("meta", {})
    payload["meta"]["normalisation_comptable_metiers_v3"] = summary
    payload["meta"]["updated_at"] = now_iso()


def process_file(path: Path, metier: str) -> dict:
    payload = load_json(path)
    stats = {
        "file": path.name,
        "metier": metier,
        "changed": 0,
        "by_rule": Counter(),
        "by_transition": Counter(),
        "examples": [],
    }

    for section in ["items", "a_valider"]:
        for item in payload.get(section, []) or []:
            if not isinstance(item, dict):
                continue
            current = str(item.get("compte_comptable") or "").strip()
            target, rule = infer_account(metier, item)
            if not target or target == current:
                continue
            item["compte_comptable"] = target
            stats["changed"] += 1
            stats["by_rule"][rule] += 1
            stats["by_transition"][f"{current}->{target}"] += 1
            if len(stats["examples"]) < 12:
                stats["examples"].append(
                    {
                        "section": section,
                        "article_source": item.get("article_source"),
                        "old": current,
                        "new": target,
                        "rule": rule,
                    }
                )

    update_meta(
        payload,
        {
            "applied_at": now_iso(),
            "metier": metier,
            "changed": stats["changed"],
            "by_rule": dict(stats["by_rule"]),
            "by_transition": dict(stats["by_transition"]),
        },
    )
    dump_json(path, payload)
    stats["by_rule"] = dict(stats["by_rule"])
    stats["by_transition"] = dict(stats["by_transition"])
    return stats


def write_reports(file_summaries: list[dict]) -> None:
    summary = {
        "generated_at": now_iso(),
        "files": file_summaries,
        "total_changed": sum(item["changed"] for item in file_summaries),
        "by_metier": dict(
            Counter({item["metier"]: sum(x["changed"] for x in file_summaries if x["metier"] == item["metier"]) for item in file_summaries})
        ),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Normalisation Comptable Metiers V3",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- total_changed: `{summary['total_changed']}`",
        "",
    ]
    for file_summary in file_summaries:
        lines.append(
            f"- {file_summary['file']}: changed=`{file_summary['changed']}` "
            f"rules=`{file_summary['by_rule']}` transitions=`{file_summary['by_transition']}`"
        )
    lines.append("")
    lines.append("Exemples :")
    for file_summary in file_summaries:
        for example in file_summary["examples"][:4]:
            lines.append(
                f"- `{file_summary['file']}` / `{example['article_source']}` : "
                f"`{example['old']} -> {example['new']}` ({example['rule']})"
            )

    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    file_summaries: list[dict] = []
    for metier, files in TARGETS.items():
        for name in files:
            file_summaries.append(process_file(ROOT / name, metier))
    write_reports(file_summaries)
    print(json.dumps({"files": file_summaries, "total_changed": sum(item["changed"] for item in file_summaries)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
