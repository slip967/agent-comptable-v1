import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

for dbname in ['keymanage', 'keymanage_novembre']:
    print(f"\n{'='*50}\n DB: {dbname}")
    info = requests.get(f'{COUCHDB_URL}/{dbname}', **S).json()
    print(f"  doc_count: {info.get('doc_count')}, partitioned: {info.get('props',{}).get('partitioned')}")

    # Sample IDs
    r = requests.get(f'{COUCHDB_URL}/{dbname}/_all_docs?limit=15', **S).json()
    real_ids = [row['id'] for row in r.get('rows', []) if not row['id'].startswith('_design')]
    print(f"  Sample IDs: {real_ids[:5]}")

    if real_ids:
        doc = requests.get(f'{COUCHDB_URL}/{dbname}/{real_ids[0]}', **S).json()
        print(f"  Keys: {list(doc.keys())[:20]}")
        pval = doc.get('p') or doc.get('type') or doc.get('doc_type', '?')
        print(f"  p/type: {pval}")

    # Check partition fr_bd_452416191
    PARTITION = 'fr_bd_452416191'
    pr = requests.get(f'{COUCHDB_URL}/{dbname}/_partition/{PARTITION}', **S)
    if pr.status_code == 200:
        pd = pr.json()
        print(f"  Partition {PARTITION!r}: doc_count={pd.get('doc_count')}")
        # Find invoice_form
        q = {'selector': {'p': 'invoice_form'}, 'limit': 2,
             'fields': ['_id','p','issuer','line_items','date']}
        r2 = requests.post(f'{COUCHDB_URL}/{dbname}/_partition/{PARTITION}/_find', json=q, **S)
        docs = r2.json().get('docs', [])
        print(f"  invoice_form docs: {len(docs)}")
        for doc in docs[:1]:
            print(f"    ID: {doc['_id']}")
            li = doc.get('line_items', [])
            print(f"    issuer: {doc.get('issuer')}")
            print(f"    line_items: {len(li)}")
            for item in li[:3]:
                print(f"      {json.dumps(item, ensure_ascii=False)[:200]}")
    else:
        print(f"  Partition {PARTITION!r}: not found (status={pr.status_code})")
        # Try listing available partitions from sample IDs
        prefixes = list({row['id'].split(':')[0] for row in r.get('rows',[]) if ':' in row['id'] and not row['id'].startswith('_')})
        print(f"  Available partitions in sample: {prefixes[:10]}")

        # Find invoice_form globally
        q = {'selector': {'p': 'invoice_form', 'issuer.name': {'$regex': '(?i)metro'}}, 'limit': 2,
             'fields': ['_id','issuer','line_items','date']}
        r3 = requests.post(f'{COUCHDB_URL}/{dbname}/_find', json=q, **S)
        docs3 = r3.json().get('docs', [])
        print(f"  Metro invoice_form (global): {len(docs3)}")
