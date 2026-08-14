"""
_migrate_epicerie_to_charges.py
1. Déplace 126 articles non-alimentaires de base_produits_epicerie_v1.json
   vers base_charges_externes_v1.json
2. Corrige les 115 articles alimentaires (6061/5.5%) → compte 607
   en base_produits_epicerie_v1.json
"""
import json
from datetime import datetime, timezone

FP_EPI = 'base_produits_epicerie_v1.json'
FP_CHG = 'base_charges_externes_v1.json'

def load(fp):
    try:
        with open(fp, encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError:
        with open(fp, encoding='utf-8-sig') as f:
            return json.load(f)

def save(fp, d):
    d['meta']['items_count'] = len(d['items'])
    d['meta']['updated'] = datetime.now(timezone.utc).isoformat()
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

epi = load(FP_EPI)
chg = load(FP_CHG)

COMPTES_NON_FOOD = {'6062', '6063', '6064', '6065', '6066', '6068'}

def est_a_deplacer(item):
    compte = str(item.get('compte_comptable') or '')
    tva    = item.get('taux_tva')
    # 6061 TVA 20% = utilities (électricité, eau…)
    if compte.startswith('6061') and tva == 20.0:
        return True
    # 606x non-food (hors 6061)
    for c in COMPTES_NON_FOOD:
        if compte.startswith(c):
            return True
    return False

def est_food_mauvais_compte(item):
    compte = str(item.get('compte_comptable') or '')
    tva    = item.get('taux_tva')
    return compte.startswith('6061') and tva != 20.0

# ─── Séparation ───────────────────────────────────────────────────────────────
a_deplacer   = [i for i in epi['items'] if est_a_deplacer(i)]
a_corriger   = [i for i in epi['items'] if est_food_mauvais_compte(i)]
a_garder_tel = [i for i in epi['items'] if not est_a_deplacer(i) and not est_food_mauvais_compte(i)]

print(f"Épicerie avant           : {len(epi['items'])} items")
print(f"  → à déplacer (charges) : {len(a_deplacer)}")
print(f"  → à corriger (6061→607): {len(a_corriger)}")
print(f"  → inchangés            : {len(a_garder_tel)}")

# ─── 1. Déplacer vers charges_externes ───────────────────────────────────────
existing_chg = {i['article_canonique'] for i in chg['items']}
nouveaux_chg = []
deja_chg     = []

for item in a_deplacer:
    canon = item.get('article_canonique', '')
    if canon in existing_chg:
        deja_chg.append(item)
    else:
        # Ajuster categorie/sous_categorie
        item_copy = dict(item)
        item_copy['categorie']      = 'charge_externe'
        item_copy['sous_categorie'] = 'fourniture'
        nouveaux_chg.append(item_copy)
        existing_chg.add(canon)

print(f"\nCharges_externes avant   : {len(chg['items'])} items")
print(f"  + nouveaux             : {len(nouveaux_chg)}")
print(f"  déjà présents (skip)   : {len(deja_chg)}")

# ─── 2. Corriger comptes 6061→607 en épicerie ────────────────────────────────
LIBELLE_607 = 'Achats de marchandises'
corriges = []
for item in a_corriger:
    item['compte_comptable']        = '607'
    item['compte_comptable_libelle'] = LIBELLE_607
    corriges.append(item)

print(f"\nCorrections 6061→607     : {len(corriges)} items")

# ─── 3. Sauvegarder ──────────────────────────────────────────────────────────
# Épicerie = inchangés + corrigés (les a_deplacer sont retirés)
epi['items'] = a_garder_tel + corriges
save(FP_EPI, epi)
print(f"\nÉpicerie après           : {len(epi['items'])} items")

# Charges = existants + nouveaux
chg['items'] = chg['items'] + nouveaux_chg
save(FP_CHG, chg)
print(f"Charges_externes après   : {len(chg['items'])} items")

# ─── 4. Détail des comptes corrigés ──────────────────────────────────────────
from collections import Counter
cpt_corriges = Counter(i.get('sous_categorie') for i in corriges)
print(f"\nSous-catégories des {len(corriges)} items corrigés 6061→607:")
for k, v in cpt_corriges.most_common():
    print(f"  {k}: {v}")

print("\nDone.")
