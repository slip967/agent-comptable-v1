"""
_audit_4bases.py - Audit btp, restaurant, boulangerie, boucherie
"""
import json
from collections import Counter

BASES = {
    'boucherie':  ('base_produits_boucherie_v1.json',  ['601','602','607'], ['606','6062','6063','6068','615','62','63']),
    'boulangerie':('base_produits_boulangerie_v1.json', ['601','602','607'], ['606','6062','6063','6068','615','62','63']),
    'btp':        ('base_produits_btp_v1.json',         ['601','602','605','606','607','615','61','62','63'], []),
    'restaurant': ('base_produits_restaurant_v1.json',  ['601','602','607','606','6061'], ['615','62','63']),
}

import re, unicodedata

GENERIQUES = {
    'divers','acompte','avoir','remise','escompte','inconnu','total',
    'sous total','n/a','na','autre','autres','non defini','annulation',
    'annule','credit','debit','regularisation','ajustement','correction',
    'erreur','test','xxx','yyy','zzz','neant','aucun','aucune',
    'forfait','prestation','service','article','marchandise','livraison',
    'frais','charge','produit','remise commerciale',
}

def normalize(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def is_suspect(item):
    canon = item.get('article_canonique') or normalize(item.get('article_source',''))
    mots = item.get('mots_cles') or canon.split()
    mots = [m for m in mots if m]
    if canon in GENERIQUES:
        return 'terme_generique'
    if len(mots) == 1 and len(mots[0]) <= 2:
        return 'trop_court'
    if re.fullmatch(r'[\d\s\-/\.]+', canon):
        return 'chiffres_seulement'
    return None

for metier, (fp, comptes_ok_prefixes, comptes_charges_prefixes) in BASES.items():
    with open(fp, encoding='utf-8') as f:
        d = json.load(f)
    items = d['items']

    suspects = [(i, item, is_suspect(item)) for i, item in enumerate(items) if is_suspect(item)]

    def est_charge(item):
        compte = str(item.get('compte_comptable') or '')
        for c in comptes_charges_prefixes:
            if compte.startswith(c):
                return True
        return False

    def compte_ok(item):
        compte = str(item.get('compte_comptable') or '')
        if not compte or compte == 'None':
            return False
        for c in comptes_ok_prefixes:
            if compte.startswith(c):
                return True
        return False

    a_deplacer = [item for item in items if est_charge(item)]
    mauvais_cpt = [item for item in items if not compte_ok(item) and not est_charge(item)]
    tva_dist = Counter(item.get('taux_tva') for item in items)
    cpt_dist = Counter(str(item.get('compte_comptable')) for item in items)

    print('=' * 65)
    print(f'  {metier.upper()} — {fp}  ({len(items)} items)')
    print('=' * 65)
    print(f'  Articles suspects        : {len(suspects)}')
    for _, item, reason in suspects[:5]:
        print(f'    - {item["article_source"]!r}  compte={item.get("compte_comptable")}  → {reason}')

    print(f'  À déplacer charges_ext   : {len(a_deplacer)}')
    for item in a_deplacer[:8]:
        print(f'    - {item["article_source"]!r}  [{item.get("compte_comptable")} / {item.get("taux_tva")}%]')

    print(f'  Comptes à corriger       : {len(mauvais_cpt)}')
    cpt_bad = Counter(str(i.get('compte_comptable')) for i in mauvais_cpt)
    for c, n in cpt_bad.most_common(8):
        print(f'    {c}: {n} items')
    for item in mauvais_cpt[:3]:
        print(f'    ex: {item["article_source"]!r}  [{item.get("compte_comptable")} / {item.get("taux_tva")}%]')

    print(f'\n  Distribution comptes:')
    for c, n in cpt_dist.most_common(8):
        print(f'    {c}: {n}')
    print(f'  Distribution TVA: {dict(tva_dist.most_common())}')
    print()
