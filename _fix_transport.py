"""
_fix_transport.py
- 14 items télécom (626/6261) → déplacer dans charges_externes
- 3 items pièces auto avec compte 626 → corriger en 6062 ou 615
- 7 items pièces auto avec compte 6061 → corriger en 6062
- 6062/6063/615 : intouchables (comptes corrects pour transport)
"""
import json
from datetime import datetime, timezone

FP_TRANSPORT = 'base_produits_transport_v1.json'
FP_CHG       = 'base_charges_externes_v1.json'

TELECOM_KEYWORDS = ['sms', 'mms', 'forfait', 'opérateur', 'smartphone', 'internet',
                    'norton', 'anti-spam', 'box', 'dose lg', 'week-end internet']

# Pièces auto avec compte 626 (mis en télécom par erreur)
AUTO_626 = {
    'FILTRE POUSSIERE':                          ('6062', 'Fournitures consommables'),
    'GARNITURE DE FREIN':                        ('6062', 'Fournitures consommables'),
    'REMPLACEMENT DES PLAQUETTES DE FREIN AR':   ('615',  'Entretien et réparations'),
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

def est_telecom(item):
    compte = str(item.get('compte_comptable') or '')
    if not (compte.startswith('626') or compte.startswith('6261') or compte.startswith('6262')):
        return False
    label = (item.get('article_source') or '').lower()
    canon = (item.get('article_canonique') or '').lower()
    return any(kw in label or kw in canon for kw in TELECOM_KEYWORDS)

transport = load(FP_TRANSPORT)
chg       = load(FP_CHG)
existing  = {i['article_canonique'] for i in chg['items']}
nouveaux  = []

garder    = []
corriges  = []
deplaces  = []

for item in transport['items']:
    compte = str(item.get('compte_comptable') or '')
    source = item.get('article_source', '')

    # 1) Télécom 626/6261 → charges_externes
    if est_telecom(item):
        deplaces.append(item)
        canon = item.get('article_canonique', '')
        if canon not in existing:
            item_copy = dict(item)
            item_copy['categorie']      = 'charge_externe'
            item_copy['sous_categorie'] = 'téléphonie'
            nouveaux.append(item_copy)
            existing.add(canon)
        continue

    # 2) Pièces auto avec compte 626 → corriger
    if source in AUTO_626:
        new_cpt, new_lib = AUTO_626[source]
        item['compte_comptable']         = new_cpt
        item['compte_comptable_libelle'] = new_lib
        corriges.append(('626→' + new_cpt, source))
        garder.append(item)
        continue

    # 3) Pièces auto avec compte 6061 (sauf Uber 0%) → corriger en 6062
    if compte.startswith('6061') and item.get('taux_tva') not in (0.0, None):
        item['compte_comptable']         = '6062'
        item['compte_comptable_libelle'] = 'Fournitures consommables'
        corriges.append(('6061→6062', source))
        garder.append(item)
        continue

    garder.append(item)

transport['items'] = garder
save(FP_TRANSPORT, transport)

chg['items'] = chg['items'] + nouveaux
save(FP_CHG, chg)

print('TRANSPORT (' + FP_TRANSPORT + ')')
print('  ' + str(len(garder) + len(deplaces) + len(corriges) - sum(1 for _ in corriges)) + ' → ' + str(len(garder)) + ' items')
print('  Déplacés → charges_externes : ' + str(len(deplaces)))
for i in deplaces:
    print('    - ' + repr(i['article_source']) + ' [' + str(i.get('compte_comptable')) + ']')
print('  Comptes corrigés : ' + str(len(corriges)))
for old_new, src in corriges:
    print('    - ' + repr(src) + '  [' + old_new + ']')

print()
print('base_charges_externes_v1.json : +' + str(len(nouveaux)) + ' nouveaux → ' + str(len(chg['items'])) + ' items total')

from collections import Counter
cpt = Counter(str(i.get('compte_comptable')) for i in transport['items'])
print()
print('Distribution comptes après fix:')
for c, n in cpt.most_common():
    print('  ' + c + ': ' + str(n))

print('\nDone.')
