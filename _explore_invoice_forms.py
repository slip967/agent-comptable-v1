import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)
PARTITION = 'fr_bd_452416191'

# Fetch the invoice_form doc
doc_id = 'fr_bd_452416191:01328315-f05c-465c-989e-9541b4eee9f1'
doc = requests.get(f'{COUCHDB_URL}/keymanage_accounting/{doc_id}', **S).json()
print("=== invoice_form STRUCTURE ===")
print(f"Keys: {list(doc.keys())}")
print(json.dumps({k: doc.get(k) for k in ['p','issuer','date','invoice_number','total_ttc','line_items']}, ensure_ascii=False, indent=2)[:2000])

# Count total invoice_form docs in this partition
q_count = {'selector': {'p': 'invoice_form'}, 'limit': 200,
           'fields': ['_id', 'issuer', 'date', 'total_ttc']}
r2 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q_count, **S)
all_forms = r2.json().get('docs', [])
print(f"\nTotal invoice_form in partition {PARTITION}: {len(all_forms)}")

# Check issuers
from collections import Counter
issuers = Counter()
for f in all_forms:
    issuer = f.get('issuer', {})
    if isinstance(issuer, dict):
        name = issuer.get('name', '') or issuer.get('company_name', '') or ''
    else:
        name = str(issuer or '')
    issuers[name.upper()[:30]] += 1
print("\nTop issuers:")
for name, count in issuers.most_common(15):
    print(f"  {name!r}: {count}")

# Find Metro invoice_forms specifically
print("\n=== METRO invoice_forms ===")
metro_forms = []
for f in all_forms:
    issuer = f.get('issuer', {})
    if isinstance(issuer, dict):
        name = issuer.get('name', '') or issuer.get('company_name', '') or ''
    else:
        name = str(issuer or '')
    if 'metro' in name.lower():
        metro_forms.append(f)
print(f"Metro forms found: {len(metro_forms)}")
for mf in metro_forms[:3]:
    print(f"  ID: {mf['_id']}, issuer: {mf.get('issuer')}, date: {mf.get('date')}, ttc: {mf.get('total_ttc')}")
