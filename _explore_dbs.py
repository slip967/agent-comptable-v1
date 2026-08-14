import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

# Check other DBs for Metro invoice forms with product-level detail
for dbname in ['database', 'ayasmine_test2', 'datasource']:
    print(f"\n=== DB: {dbname} ===")
    info = requests.get(f'{COUCHDB_URL}/{dbname}', **S).json()
    print(f"  doc_count: {info.get('doc_count', 'N/A')}")

    # Sample 1 real doc
    r = requests.get(f'{COUCHDB_URL}/{dbname}/_all_docs?limit=10', **S).json()
    real_ids = [row['id'] for row in r.get('rows', []) if not row['id'].startswith('_design')]
    if real_ids:
        doc = requests.get(f'{COUCHDB_URL}/{dbname}/{real_ids[0]}', **S).json()
        print(f"  Sample doc ID: {real_ids[0]}")
        print(f"  Keys: {list(doc.keys())[:20]}")
        pval = doc.get('p') or doc.get('type') or doc.get('doc_type') or doc.get('kind', '?')
        print(f"  p/type: {pval}")

    # Search for Metro in this DB
    for p_try in ['invoice_form', 'invoice', 'purchase_invoice', 'facture']:
        q = {'selector': {'p': p_try}, 'limit': 1}
        r2 = requests.post(f'{COUCHDB_URL}/{dbname}/_find', json=q, **S)
        docs = r2.json().get('docs', [])
        if docs:
            print(f"  p={p_try!r}: FOUND")
            doc = docs[0]
            print(f"    Keys: {list(doc.keys())[:20]}")
            print(f"    Sample: {json.dumps({k: doc.get(k) for k in list(doc.keys())[:10]}, ensure_ascii=False)[:400]}")
