import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)
PARTITION = 'fr_bd_452416191'

# Sample docs
r = requests.get(
    f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_all_docs?include_docs=true&limit=5', **S
).json()
for row in r['rows']:
    doc = row['doc']
    pval = doc.get('p', '?')
    print(f"ID: {doc['_id']}")
    print(f"p: {pval} | keys: {list(doc.keys())[:15]}")
    print()

# Check for other p values
for pv in ['invoice_form', 'piece', 'core_profile', 'invoice', 'supplier_profile', 'invoice_line']:
    q = {'selector': {'p': pv}, 'limit': 1}
    r2 = requests.post(
        f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q, **S
    )
    docs = r2.json().get('docs', [])
    found_id = docs[0]['_id'] if docs else ''
    print(f"p={pv!r}: {len(docs)} docs {found_id}")
