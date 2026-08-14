"""
Vérifie les source_invoice_ids de la base BTP dans keymanage_accounting et abt3.
Liste les articles avec des IDs introuvables.
"""
import json, sys
sys.path.insert(0, '.')
from couch_config import *
import requests
from urllib.parse import quote

s = requests.Session()
s.auth = (COUCHDB_USER, COUCHDB_PASS)
s.cert = (CLIENT_CERT, CLIENT_KEY)
s.verify = CA_CERT

with open('base_produits_btp_v1.json', encoding='utf-8') as f:
    data = json.load(f)
items = data['items']

all_ids = sorted({sid for it in items for sid in it.get('source_invoice_ids', [])})
print('IDs uniques a verifier: ' + str(len(all_ids)))

def batch_check(db, ids):
    found = set()
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        url = COUCHDB_URL + '/' + quote(db, safe='') + '/_all_docs'
        r = s.post(url, json={'keys': batch}, timeout=30)
        r.raise_for_status()
        for row in r.json().get('rows', []):
            if 'error' not in row and row.get('id'):
                found.add(row['id'])
    return found

found_key  = batch_check('keymanage_accounting', all_ids)
found_abt3 = batch_check('abt3', all_ids)
found_all  = found_key | found_abt3
nowhere    = set(all_ids) - found_all

print('Dans keymanage_accounting : ' + str(len(found_key)))
print('Dans abt3                 : ' + str(len(found_abt3)))
print('INTROUVABLES              : ' + str(len(nowhere)))

if nowhere:
    print()
    print('Articles avec IDs introuvables:')
    for it in items:
        miss = [sid for sid in it.get('source_invoice_ids', []) if sid in nowhere]
        if miss:
            print('  [' + it.get('compte_comptable','') + '] ' + it.get('article_source','?'))
            all_ids_item = it.get('source_invoice_ids', [])
            total_ids = len(all_ids_item)
            miss_count = len(miss)
            print('    ' + str(miss_count) + '/' + str(total_ids) + ' IDs manquants:')
            for m in miss:
                print('      ' + m)
else:
    print('Tous les IDs sont valides.')
