import json

PARTITION = 'fr_bd_452416191'
LIMIT = 50

for fp in ['base_produits_restaurant_v1.json', 'base_charges_externes_v1.json']:
    with open(fp, encoding='utf-8') as f:
        d = json.load(f)

    non_metro = [i for i in d['items'] if PARTITION not in (i.get('partitions_sources') or [])]
    metro = [i for i in d['items'] if PARTITION in (i.get('partitions_sources') or [])]
    metro_kept = metro[:LIMIT]
    removed = len(metro) - len(metro_kept)

    d['items'] = non_metro + metro_kept
    d['meta']['items_count'] = len(d['items'])

    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    total = len(d['items'])
    print(fp + ': ' + str(len(non_metro)) + ' existants + ' + str(len(metro_kept)) + ' Metro = ' + str(total) + ' total (supprimes: ' + str(removed) + ')')
