"""
_fix_4bases.py
Boucherie   : déplace 2 items (6062/6068) → charges_externes
Boulangerie : 6061/5.5% → garde + compte 6061→601
              6061/20%, 6068, 6063 → charges_externes
Restaurant  : 606x/20% → charges_externes
              606x/5.5% (non-6061) → compte →607
BTP         : rien
"""
import json
from datetime import datetime, timezone

FP_CHG = 'base_charges_externes_v1.json'

BASES = {
    'boucherie':  'base_produits_boucherie_v1.json',
    'boulangerie':'base_produits_boulangerie_v1.json',
    'restaurant': 'base_produits_restaurant_v1.json',
}

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

# Comptes "charges" non-alimentaires selon TVA
def est_charge_nonfood(item, comptes_charges):
    compte = str(item.get('compte_comptable') or '')
    tva    = item.get('taux_tva')
    for c in comptes_charges:
        if compte.startswith(c):
            # 6061/5.5% = alimentaire/boisson → pas une charge
            if compte.startswith('6061') and tva != 20.0:
                return False
            return True
    return False

def est_food_mauvais_compte(item, comptes_charges, comptes_ok):
    """Alimentaire (TVA 5.5%) avec compte de charge → corriger."""
    compte = str(item.get('compte_comptable') or '')
    tva    = item.get('taux_tva')
    for c in comptes_ok:
        if compte.startswith(c):
            return False
    for c in comptes_charges:
        if compte.startswith(c) and tva != 20.0 and not compte.startswith('6061'):
            return True
    return False

# Règles par métier
RULES = {
    'boucherie': {
        'comptes_ok':     ['601', '602', '607'],
        'comptes_charges':['6062', '6063', '6068'],
        'fix_compte':     '601',
        'fix_libelle':    'Achats de matières premières',
    },
    'boulangerie': {
        'comptes_ok':     ['601', '602', '607'],
        'comptes_charges':['6061', '6062', '6063', '6068'],
        'fix_compte':     '601',
        'fix_libelle':    'Achats de matières premières',
    },
    'restaurant': {
        'comptes_ok':     ['601', '602', '607', '6061'],
        'comptes_charges':['6062', '6063', '6068'],
        'fix_compte':     '607',
        'fix_libelle':    'Achats de marchandises',
    },
}

chg = load(FP_CHG)
existing_chg = {i['article_canonique'] for i in chg['items']}
nouveaux_chg = []

for metier, fp in BASES.items():
    r = RULES[metier]
    d = load(fp)
    before = len(d['items'])

    a_deplacer = []
    a_corriger = []
    a_garder   = []

    for item in d['items']:
        if est_charge_nonfood(item, r['comptes_charges']):
            a_deplacer.append(item)
        elif est_food_mauvais_compte(item, r['comptes_charges'], r['comptes_ok']):
            a_corriger.append(item)
        else:
            a_garder.append(item)

    # Corriger comptes
    for item in a_corriger:
        item['compte_comptable']        = r['fix_compte']
        item['compte_comptable_libelle'] = r['fix_libelle']

    # Préparer déplacements vers charges_externes
    deplace_count = 0
    doublon_count = 0
    for item in a_deplacer:
        canon = item.get('article_canonique', '')
        if canon in existing_chg:
            doublon_count += 1
        else:
            item_copy = dict(item)
            item_copy['categorie']      = 'charge_externe'
            item_copy['sous_categorie'] = 'fourniture'
            nouveaux_chg.append(item_copy)
            existing_chg.add(canon)
            deplace_count += 1

    d['items'] = a_garder + a_corriger
    save(fp, d)

    print(f'{metier.upper()} ({fp})')
    print(f'  {before} → {len(d["items"])} items')
    print(f'  déplacés → charges_externes : {deplace_count}  (doublons ignorés: {doublon_count})')
    print(f'  comptes corrigés            : {len(a_corriger)}')
    for item in a_deplacer[:5]:
        print(f'    - déplacé: {item["article_source"]!r}  [{item.get("compte_comptable")}/{item.get("taux_tva")}%]')
    for item in a_corriger[:5]:
        print(f'    - corrigé: {item["article_source"]!r}  [6061→{r["fix_compte"]}]')
    print()

# Sauvegarder charges_externes
chg['items'] = chg['items'] + nouveaux_chg
save(FP_CHG, chg)
print(f'base_charges_externes_v1.json : +{len(nouveaux_chg)} nouveaux → {len(chg["items"])} items total')
print('\nDone.')
