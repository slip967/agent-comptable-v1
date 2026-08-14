import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

DB = 'abt3'

# Info
info = requests.get(f'{COUCHDB_URL}/{DB}', **S).json()
print(f"DB {DB!r}: doc_count={info.get('doc_count')}, partitioned={info.get('props',{}).get('partitioned')}")

# Sample a real doc structure
r = requests.get(f'{COUCHDB_URL}/{DB}/_all_docs?limit=20', **S).json()
real_ids = [row['id'] for row in r.get('rows', []) if not row['id'].startswith('_design')]
if real_ids:
    doc = requests.get(f'{COUCHDB_URL}/{DB}/{real_ids[0]}', **S).json()
    print(f"\nSample ID: {real_ids[0]}")
    print(f"Keys: {list(doc.keys())[:20]}")

# Known Metro partition: fr_bd_452416191
PARTITION = 'fr_bd_452416191'
pinfo = requests.get(f'{COUCHDB_URL}/{DB}/_partition/{PARTITION}', **S)
print(f"\nPartition {PARTITION!r} in {DB}: status={pinfo.status_code}", pinfo.json().get('doc_count', 'N/A'))

# Find invoice_form docs in this partition
q = {
    'selector': {'p': 'invoice_form'},
    'limit': 3,
    'fields': ['_id', 'p', 'issuer', 'line_items', 'date', 'total_ttc', 'invoice_number']
}
r2 = requests.post(f'{COUCHDB_URL}/{DB}/_partition/{PARTITION}/_find', json=q, **S)
print(f"\n=== invoice_form in {PARTITION} ===")
print("Status:", r2.status_code)
docs = r2.json().get('docs', [])
print(f"Found: {len(docs)}")
for doc in docs[:2]:
    print(f"\n  ID: {doc['_id']}")
    print(f"  issuer: {doc.get('issuer')}")
    print(f"  date: {doc.get('date')}")
    line_items = doc.get('line_items', [])
    print(f"  line_items count: {len(line_items)}")
    for li in line_items[:5]:
        print(f"    - {json.dumps(li, ensure_ascii=False)[:200]}")

# Also search for Metro in issuer field across the whole DB
print(f"\n=== SEARCH invoice_form with Metro issuer (global) ===")
q2 = {
    'selector': {
        'p': 'invoice_form',
        'issuer.name': {'$regex': '(?i)metro'}
    },
    'limit': 3,
    'fields': ['_id', 'issuer', 'line_items', 'date']
}
r3 = requests.post(f'{COUCHDB_URL}/{DB}/_find', json=q2, **S)
print("Status:", r3.status_code)
docs3 = r3.json().get('docs', [])
print(f"Found: {len(docs3)}")
for doc in docs3[:2]:
    print(f"\n  ID: {doc['_id']}")
    print(f"  issuer: {doc.get('issuer')}")
    li = doc.get('line_items', [])
    print(f"  line_items: {len(li)}")
    for item in li[:5]:
        print(f"    {json.dumps(item, ensure_ascii=False)[:200]}")
