import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=60)

# The DB has partitioned docs: ID = {partition}:{uuid}
# p=entry are FEC journal entries with a 'label' field

# Search for Metro in labels of FEC entries
print("=== SEARCH METRO IN ENTRY LABELS ===")
q = {
    'selector': {
        'p': 'entry',
        'label': {'$regex': '(?i)metro'}
    },
    'limit': 5,
    'use_index': 'idx_p'
}
r = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_find', json=q, **S)
data = r.json()
docs = data.get('docs', [])
print(f"Found: {len(docs)} docs with 'metro' in label")
for doc in docs:
    print('  ID:', doc['_id'])
    print('  partition:', doc['_id'].split(':')[0])
    print('  label:', doc.get('label'))
    print('  Keys:', list(doc.keys()))
    print('  ', json.dumps({k: doc.get(k) for k in list(doc.keys())[:20]}, ensure_ascii=False)[:600])
    print()

# Also try aux_account for Metro
print("\n=== SEARCH METRO IN AUX_ACCOUNT ===")
q2 = {
    'selector': {
        'p': 'entry',
        'aux_account': {'$regex': '(?i)metro'}
    },
    'limit': 3,
    'use_index': 'idx_p'
}
r2 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_find', json=q2, **S)
docs2 = r2.json().get('docs', [])
print(f"Found: {len(docs2)} docs with 'metro' in aux_account")
for doc in docs2[:2]:
    print('  ID:', doc['_id'])
    print('  aux_account:', doc.get('aux_account'))
    print('  label:', doc.get('label'))
    print()

# List all partitions from the _all_docs by scanning more IDs
print("\n=== SEARCH FOR METRO IN ID PARTITIONS (range query) ===")
r3 = requests.get(f'{COUCHDB_URL}/keymanage_accounting/_all_docs?startkey=%22fr_metro%22&endkey=%22fr_metro%EF%BF%BD%22&limit=5', **S)
print('Status:', r3.status_code)
print('Result:', json.dumps(r3.json(), ensure_ascii=False)[:500])
