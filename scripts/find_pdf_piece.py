"""
Scan piece docs for PDF paths, and also check the rantransport invoice JSON
to understand where PDF paths come from in the real data.
"""
import sys, json
sys.path.insert(0, 'agent_local_v1/app')
sys.path.insert(0, 'agent_local_v1')
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, CA_CERT, CLIENT_CERT, CLIENT_KEY, COUCHDB_USER, COUCHDB_PASS
from urllib.parse import quote
import requests

s = requests.Session()
s.verify = CA_CERT
s.cert = (CLIENT_CERT, CLIENT_KEY)
s.auth = (COUCHDB_USER, COUCHDB_PASS)

db = 'keymanage_accounting'

PDF_KEYWORDS = ('.pdf', '/root/windows/', '/mnt/clients/', 'z:/', 'fichiers_pdf', '/e/')

def contains_pdf(val):
    if not isinstance(val, str):
        return False
    v = val.lower()
    return any(kw.lower() in v for kw in PDF_KEYWORDS)

def deep_find_pdf(obj, prefix=''):
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            results.extend(deep_find_pdf(v, f'{prefix}{k}.'))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            results.extend(deep_find_pdf(v, f'{prefix}[{i}].'))
    elif isinstance(obj, str) and contains_pdf(obj):
        results.append((prefix.rstrip('.'), obj))
    return results

# Scan piece docs for siren 892833831
siren = '892833831'
url = f'{COUCHDB_URL}/{db}/_partition/fr_bd_{siren}/_all_docs'
print("Fetching piece docs...")
r = s.get(url, params={'include_docs': 'true', 'limit': '300',
                       'startkey': json.dumps(f'fr_bd_{siren}:piece:'),
                       'endkey': json.dumps(f'fr_bd_{siren}:piece:\ufff0')}, timeout=60)
rows = r.json().get('rows', [])
print(f"Got {len(rows)} piece docs")

for row in rows[:5]:
    doc = row.get('doc', {})
    print(f"\n--- piece doc: {doc.get('_id')} ---")
    print("  keys:", [k for k in doc.keys() if not k.startswith('_')])
    hits = deep_find_pdf(doc)
    if hits:
        for field, val in hits:
            print(f"  PDF FOUND {field}: {val[:120]}")
    else:
        # show all string fields
        for k, v in doc.items():
            if k.startswith('_'):
                continue
            if isinstance(v, str) and v:
                print(f"  {k}: {repr(v[:100])}")

# Also look at the existing purchase invoices JSON
print("\n\n=== Checking rantransport_824332985_purchase_invoices.json ===")
import pathlib
p = pathlib.Path('rantransport_824332985_purchase_invoices.json')
if p.exists():
    data = json.loads(p.read_text(encoding='utf-8'))
    docs = data if isinstance(data, list) else data.get('docs', data.get('rows', []))
    for doc in docs[:3]:
        hits = deep_find_pdf(doc)
        if hits:
            print(f"PDF in doc {doc.get('_id','?')}:")
            for field, val in hits[:3]:
                print(f"  {field}: {val[:120]}")
