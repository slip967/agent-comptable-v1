"""
_cleanup_bases_v1.py
Supprime les articles incomprehensibles/generiques identifies par _audit_bases_v1.py
"""
import json, glob

TO_DELETE = {
    'base_produits_vtc_v1.json': {
        'article_canonique': {
            'divers',
            'a000 9893660',
            'a001 9899451 09',
            'n',
            'remise commerciale',
            'remise sur frais de livraison relais exp',
            'remise sur galaxy s24',
        }
    },
    'base_charges_externes_v1.json': {
        'article_canonique': {
            'livraison',
            'forfait',
        },
        'compte_comptable': {
            '706100',  # compte produit (revenus) dans une base de charges
        }
    },
}

for fp, rules in TO_DELETE.items():
    try:
        with open(fp, encoding='utf-8') as f:
            d = json.load(f)
    except UnicodeDecodeError:
        with open(fp, encoding='utf-8-sig') as f:
            d = json.load(f)

    before = len(d['items'])
    removed = []

    def should_delete(item):
        canon = item.get('article_canonique', '')
        compte = str(item.get('compte_comptable') or '')
        if 'article_canonique' in rules and canon in rules['article_canonique']:
            return True
        if 'compte_comptable' in rules and compte in rules['compte_comptable']:
            return True
        return False

    kept = [i for i in d['items'] if not should_delete(i)]
    removed = [i for i in d['items'] if should_delete(i)]

    d['items'] = kept
    d['meta']['items_count'] = len(kept)

    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print(f'{fp}: {before} -> {len(kept)} items (-{len(removed)} supprimes)')
    for item in removed:
        print(f'  - {item["article_source"]!r}  compte={item.get("compte_comptable")}')
