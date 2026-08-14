"""
Vérifie que chaque article_source BTP provient réellement d'un line_item
dans les invoice_form CouchDB référencés par source_invoice_ids.
Articles introuvables dans leurs factures = probablement inventés.
"""
import json, sys
sys.path.insert(0, '.')
from couch_config import *
import requests
from urllib.parse import quote
import unicodedata, re

s = requests.Session()
s.auth = (COUCHDB_USER, COUCHDB_PASS)
s.cert = (CLIENT_CERT, CLIENT_KEY)
s.verify = CA_CERT

with open('base_produits_btp_v1.json', encoding='utf-8') as f:
    data = json.load(f)
items = data['items']


def get_val(v):
    if isinstance(v, dict) and 'value' in v:
        return v['value']
    return v


def normalize(s):
    if not s:
        return ''
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'\s+', ' ', s)
    return s


def fetch_doc(doc_id):
    parts = doc_id.split(':')
    if len(parts) == 2:
        partition, uuid = parts
    elif len(parts) == 3 and parts[0] == parts[1]:
        partition, uuid = parts[0], parts[2]
    else:
        return None
    url = COUCHDB_URL + '/keymanage_accounting/' + quote(doc_id, safe='')
    r = s.get(url, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None


def get_line_items(doc):
    """Extraire toutes les descriptions de line_items d'un invoice_form."""
    descriptions = []
    # invoice_form peut être à la racine ou imbriqué
    for key in ('invoice_form', 'form_common_core', 'line_items'):
        pass
    # Chercher line_items récursivement dans le doc
    def extract(obj):
        if isinstance(obj, dict):
            if 'line_items' in obj:
                for li in (obj['line_items'] or []):
                    if isinstance(li, dict):
                        desc = get_val(li.get('description', li.get('label', '')))
                        if desc:
                            descriptions.append(str(desc))
            for v in obj.values():
                extract(v)
        elif isinstance(obj, list):
            for item in obj:
                extract(item)
    extract(doc)
    return descriptions


print('Vérification de ' + str(len(items)) + ' articles BTP...')
print()

invented = []
verified = []
no_ids   = []

for item in items:
    art = item.get('article_source', '')
    src_ids = item.get('source_invoice_ids', [])

    if not src_ids:
        no_ids.append(art)
        continue

    art_norm = normalize(art)
    found_in_any = False

    for sid in src_ids[:3]:  # vérifier max 3 factures par article
        doc = fetch_doc(sid)
        if not doc:
            continue
        descs = get_line_items(doc)
        for desc in descs:
            if art_norm in normalize(desc) or normalize(desc) in art_norm:
                found_in_any = True
                break
        if found_in_any:
            break

    if found_in_any:
        verified.append(art)
    else:
        invented.append((art, item.get('compte_comptable', ''), src_ids))

print('Verifies (trouves dans factures) : ' + str(len(verified)))
print('Inventes/introuvables            : ' + str(len(invented)))
print('Sans IDs                         : ' + str(len(no_ids)))
print()

if invented:
    print('Articles NON trouves dans leurs factures CouchDB:')
    for art, compte, ids in invented:
        print('  [' + compte + '] ' + art)
        for sid in ids:
            print('    ' + sid)
