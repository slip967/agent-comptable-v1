import json
from collections import Counter

with open('base_produits_epicerie_v1.json', encoding='utf-8') as f:
    d = json.load(f)

COMPTES_CHARGES = {'606', '6061', '6062', '6063', '6068', '615', '616',
                   '613', '614', '62', '63', '64', '65', '626', '627', '628'}

def est_charge(item):
    compte = str(item.get('compte_comptable') or '')
    for c in COMPTES_CHARGES:
        if compte.startswith(c):
            return True
    return False

charges = [i for i in d['items'] if est_charge(i)]
restes  = [i for i in d['items'] if not est_charge(i)]

print('Total epicerie       :', len(d['items']))
print('A deplacer -> charges:', len(charges))
print('Restes en epicerie   :', len(restes))

cpt = Counter(str(i.get('compte_comptable')) for i in charges)
print('\nComptes des items a deplacer:')
for c, n in cpt.most_common():
    print('  ' + c + ': ' + str(n) + ' items')

print('\nExemples (10 premiers):')
for i in charges[:10]:
    src = i.get('article_source', '')
    acc = str(i.get('compte_comptable', ''))
    tva = str(i.get('taux_tva', ''))
    print('  ' + repr(src) + '  [' + acc + ' / ' + tva + '%]')
