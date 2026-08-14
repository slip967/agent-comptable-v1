import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

# -- Step 1: get IDs only (no include_docs) - fast even on 1.5M docs
print("=== SAMPLE REAL DOC IDs (no body) ===")
r = requests.get(f'{COUCHDB_URL}/keymanage_accounting/_all_docs?limit=200', **S).json()
real_ids = [row['id'] for row in r['rows'] if not row['id'].startswith('_design')]
print(f"Real doc IDs sampled: {len(real_ids)}")
print("First 5:", real_ids[:5])

# -- Step 2: fetch first real doc to see structure
if real_ids:
    doc = requests.get(f'{COUCHDB_URL}/keymanage_accounting/{real_ids[0]}', **S).json()
    print("\n=== FIRST REAL DOC STRUCTURE ===")
    print("Keys:", list(doc.keys()))
    print(json.dumps({k: doc.get(k) for k in list(doc.keys())[:20]}, ensure_ascii=False)[:1000])

# -- Step 3: check available indexes
print("\n=== AVAILABLE INDEXES ===")
idx = requests.get(f'{COUCHDB_URL}/keymanage_accounting/_index', **S).json()
for i in idx.get('indexes', [])[:10]:
    print(f"  name={i.get('name')} fields={i.get('def',{}).get('fields')}")

# -- Step 4: try to find docs with "metro" in a partition key (IDs often contain partition)
metro_ids = [i for i in real_ids if 'metro' in i.lower()]
print(f"\n=== IDs containing 'metro': {len(metro_ids)} ===")
print(metro_ids[:10])
