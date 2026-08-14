from __future__ import annotations


ACCOUNT_LABELS: dict[str, str] = {
    "601": "Achats stockés - matières premières",
    "6011": "Matières premières",
    "601100": "Matières premières",
    "6012": "Fournitures",
    "6013": "Matières et fournitures consommables",
    "6021": "Matières consommables",
    "6022": "Fournitures consommables",
    "6025": "Emballages",
    "6041": "Achats d'études et prestations de services",
    "606": "Achats non stockés de matières et fournitures",
    "6061": "Fournitures non stockables (eau, énergie)",
    "606100": "Fournitures non stockables (eau, énergie)",
    "6062": "Fournitures consommables",
    "6063": "Fournitures d'entretien et de petit équipement",
    "6064": "Fournitures administratives",
    "6065": "Petit équipement",
    "6066": "Fournitures diverses",
    "6067": "Fournitures de bureau",
    "6068": "Autres matières et fournitures",
    "607": "Achats de marchandises",
    "6071": "Marchandises",
    "609": "Rabais, remises et ristournes obtenus sur achats",
    "6097": "RRR obtenus sur achats de marchandises",
    "6112": "Sous-traitance générale",
    "613": "Locations",
    "6132": "Locations immobilières",
    "615": "Entretien et réparations",
    "6152": "Entretien et réparations sur biens immobiliers",
    "6161": "Primes d'assurance",
    "6226": "Honoraires",
    "6227": "Frais d'actes et de contentieux",
    "6228": "Divers honoraires et rémunérations",
    "624": "Transports de biens",
    "6251": "Voyages et déplacements",
    "626": "Frais postaux et de télécommunications",
    "6261": "Télécommunications",
    "627": "Services bancaires et assimilés",
    "6278": "Autres frais et commissions bancaires",
    "6281": "Concours divers - cotisations",
    "6285": "Frais de recrutement",
    "6351": "Impôts directs",
    "706100": "Prestations de services",
}


def normalize_account_code(account: str | None) -> str:
    return str(account or "").strip().replace(" ", "")


def get_account_label(account: str | None) -> str | None:
    code = normalize_account_code(account)
    if not code:
        return None
    if code in ACCOUNT_LABELS:
        return ACCOUNT_LABELS[code]

    candidate = code
    while len(candidate) > 4 and candidate.endswith("00"):
        candidate = candidate[:-2]
        if candidate in ACCOUNT_LABELS:
            return ACCOUNT_LABELS[candidate]

    if len(code) > 4 and code[:4] in ACCOUNT_LABELS:
        return ACCOUNT_LABELS[code[:4]]
    if len(code) > 3 and code[:3] in ACCOUNT_LABELS:
        return ACCOUNT_LABELS[code[:3]]

    return None
