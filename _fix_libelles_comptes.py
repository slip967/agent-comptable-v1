"""
Vérifie et corrige les compte_comptable_libelle dans toutes les bases produits.
Référence : Plan Comptable Général (PCG) français.
"""
import json

BASES = [
    ("base_produits_boucherie_v1.json",   "utf-8"),
    ("base_produits_boulangerie_v1.json", "utf-8"),
    ("base_produits_epicerie_v1.json",    "utf-8"),
    ("base_produits_vtc_v1.json",         "utf-8-sig"),
    ("base_produits_btp_v1.json",         "utf-8"),
    ("base_produits_restaurant_v1.json",  "utf-8"),
    ("base_produits_transport_v1.json",   "utf-8"),
    ("base_charges_externes_v1.json",     "utf-8"),
]

# Libellés canoniques PCG
CANONICAL = {
    # 60 – Achats
    "601":    "Achats stockés - Matières premières (et fournitures)",
    "6011":   "Achats stockés - Matières premières",
    "6012":   "Fournitures",
    "6013":   "Matières et fournitures consommables",
    "602":    "Achats stockés - Autres approvisionnements",
    "6021":   "Matières consommables",
    "6022":   "Approvisionnements",
    "6025":   "Emballages",
    "6041":   "Achats d'études et prestations de services",
    "606":    "Achats non stockés de matières et fournitures",
    "6061":   "Fournitures non stockables (eau, énergie)",
    "606100": "Fournitures non stockables (eau, énergie)",
    "6062":   "Fournitures consommables",
    "6063":   "Fournitures d'entretien et de petit équipement",
    "6064":   "Fournitures administratives",
    "6065":   "Petit équipement",
    "6066":   "Fournitures diverses",
    "6067":   "Fournitures de bureau",
    "6068":   "Autres matières et fournitures",
    "607":    "Achats de marchandises",
    "6071":   "Marchandises",
    # 61 – Services extérieurs
    "611":    "Sous-traitance générale",
    "6112":   "Sous-traitance générale",
    "613":    "Locations",
    "6132":   "Locations immobilières",
    "615":    "Entretien et réparations",
    "6152":   "Entretien et réparations sur biens immobiliers",
    "6155":   "Entretien et réparations sur biens mobiliers",
    "616":    "Primes d'assurance",
    "6161":   "Primes d'assurance",
    # 62 – Autres services extérieurs
    "622":    "Rémunérations d'intermédiaires et honoraires",
    "6226":   "Honoraires",
    "6227":   "Frais d'actes et de contentieux",
    "6228":   "Divers honoraires et rémunérations",
    "624":    "Transports de biens",
    "625":    "Déplacements, missions et réceptions",
    "6251":   "Voyages et déplacements",
    "626":    "Frais postaux et de télécommunications",
    "6261":   "Télécommunications",
    "627":    "Services bancaires et assimilés",
    "6278":   "Autres frais et commissions bancaires",
    "628":    "Divers",
    "6281":   "Concours divers (cotisations)",
    "6285":   "Frais de recrutement",
    # 63 – Impôts et taxes
    "635":    "Autres impôts, taxes et versements assimilés",
    "6351":   "Impôts directs",
}

total_fixed = 0

for fname, enc in BASES:
    with open(fname, encoding=enc) as f:
        data = json.load(f)

    fixed_in_file = 0
    errors = []

    for item in data["items"]:
        c = item.get("compte_comptable", "")
        l = item.get("compte_comptable_libelle", "")
        expected = CANONICAL.get(c)

        if expected is None:
            # Compte inconnu du référentiel → signaler seulement
            errors.append(f"  [INCONNU]  {c!r:12} libellé actuel: {l!r}")
            continue

        if l != expected:
            errors.append(
                f"  [CORRIGE]  {c:12} {l!r:60}  →  {expected!r}"
            )
            item["compte_comptable_libelle"] = expected
            fixed_in_file += 1

    metier = data.get("meta", {}).get("metier", fname)
    print(f"\n=== {metier} ({fname}) ===")
    if errors:
        for e in errors:
            print(e)
    else:
        print("  [OK] Tous les libelles sont corrects")
    print(f"  → {fixed_in_file} correction(s)")

    if fixed_in_file > 0:
        out_enc = "utf-8-sig" if enc == "utf-8-sig" else "utf-8"
        with open(fname, "w", encoding=out_enc) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    total_fixed += fixed_in_file

print(f"\n{'='*60}")
print(f"Total : {total_fixed} libellés corrigés")
