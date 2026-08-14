import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

# -- Step 1: find distinct values of field "p" using the index
# Use _find with a range on p to get distinct types
print("=== FIND INVOICE-RELATED 'p' VALUES ===")
# Try common invoice-related p values
for p_val in ['purchase_invoice', 'invoice', 'facture', 'purchase_invoice_line', 'invoice_line',
              'product', 'article', 'line_item', 'entry', 'fec_entry', 'invoice_item']:
    q = {'selector': {'p': p_val}, 'limit': 1, 'use_index': 'idx_p'}
    r = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_find', json=q, **S)
    docs = r.json().get('docs', [])
    print(f"  p={p_val!r}: {len(docs)} docs")
    if docs:
        doc = docs[0]
        print(f"    ID: {doc['_id']}")
        print(f"    Keys: {list(doc.keys())[:20]}")
        print(f"    {json.dumps({k: doc.get(k) for k in list(doc.keys())[:12]}, ensure_ascii=False)[:500]}")
        print()

# -- Step 2: also check what ID prefixes exist
print("\n=== SAMPLE ID PREFIXES ===")
# Get 500 IDs to see type variety
r2 = requests.get(f'{COUCHDB_URL}/keymanage_accounting/_all_docs?limit=500', **S).json()
prefixes = {}
for row in r2['rows']:
    _id = row['id']
    if _id.startswith('_design'):
        continue
    prefix = _id.split(':')[0]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1

print("ID prefixes found:")
for p, c in sorted(prefixes.items(), key=lambda x: -x[1]):
    print(f"  {p!r}: {c}")
