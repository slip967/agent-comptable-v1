"""
_fix_remaining_accounts.py
- Boulangerie : 6061/5.5% → 601  |  601100 → 601
- Restaurant  : (6061 boissons gardés tels quels)
"""
import json
from datetime import datetime, timezone

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

# ─── Boulangerie ──────────────────────────────────────────────────────────────
fp = 'base_produits_boulangerie_v1.json'
d  = load(fp)
corriges = 0

for item in d['items']:
    compte = str(item.get('compte_comptable') or '')
    tva    = item.get('taux_tva')

    # 6061/5.5% = ingrédients boulangerie → 601
    if compte.startswith('6061') and tva != 20.0:
        item['compte_comptable']         = '601'
        item['compte_comptable_libelle'] = 'Achats de matières premières'
        corriges += 1

    # 601100 = variante padded de 601
    elif compte == '601100':
        item['compte_comptable']         = '601'
        item['compte_comptable_libelle'] = 'Achats de matières premières'
        corriges += 1

save(fp, d)

from collections import Counter
cpt = Counter(str(i.get('compte_comptable')) for i in d['items'])
print('BOULANGERIE après correction (' + str(len(d['items'])) + ' items):')
print('  Comptes corrigés : ' + str(corriges))
for c, n in cpt.most_common():
    print('  ' + c + ': ' + str(n))

# ─── Restaurant : rapport final ───────────────────────────────────────────────
fp2 = 'base_produits_restaurant_v1.json'
d2  = load(fp2)
cpt2 = Counter(str(i.get('compte_comptable')) for i in d2['items'])
print('\nRESTAURANT (' + str(len(d2['items'])) + ' items, comptes actuels):')
for c, n in cpt2.most_common():
    print('  ' + c + ': ' + str(n))
# Les 6061 en restaurant sont des boissons → sous_categorie=boisson → OK

print('\nDone.')
