"""
Scan the CouchDB partition to find invoice_form docs that contain a PDF path.
Also searches the 'piece' documents referenced by invoices.
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

PDF_KEYWORDS = ('.pdf', '/root/windows/', '/mnt/clients/', 'z:/', 'fichiers_pdf')

def contains_pdf(val):
    if not isinstance(val, str):
        return False
    v = val.lower()
    return any(kw in v for kw in PDF_KEYWORDS)

def deep_find_pdf(obj, prefix=''):
    """Return list of (field_path, value) for any PDF-like string."""
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

# Scan multiple partitions
SIRENS = ['892833831', '878523547', '880517875', '891756504', '908282098']

for siren in SIRENS:
    print(f"\n=== Scanning siren {siren} ===")
    url = f'{COUCHDB_URL}/{db}/_partition/fr_bd_{siren}/_all_docs'
    startkey = f'fr_bd_{siren}:'
    r = s.get(url, params={'include_docs': 'true', 'limit': '300',
                           'startkey': json.dumps(startkey)}, timeout=60)
    rows = r.json().get('rows', [])

    found_in_siren = 0
    for row in rows:
        doc = row.get('doc', {})
        if doc.get('p') != 'invoice_form':
            continue
        hits = deep_find_pdf(doc)
        if hits:
            print(f"  FOUND in {doc['_id']}")
            for field, val in hits[:3]:
                print(f"    {field}: {val[:120]}")
            found_in_siren += 1
            if found_in_siren >= 2:
                break

    if found_in_siren == 0:
        # Check piece docs which may hold the original file path
        piece_ids = []
        for row in rows[:50]:
            doc = row.get('doc', {})
            pid = doc.get('piece_id') or doc.get('piece_ref')
            if pid and isinstance(pid, str) and 'piece' in pid:
                piece_ids.append(pid)

        if piece_ids:
            print(f"  No PDF in invoice_form. Checking {len(piece_ids[:3])} piece docs...")
            for pid in piece_ids[:3]:
                try:
                    r2 = s.get(f'{COUCHDB_URL}/{db}/{quote(pid, safe="")}', timeout=20)
                    if r2.status_code == 200:
                        pdoc = r2.json()
                        hits = deep_find_pdf(pdoc)
                        if hits:
                            print(f"  FOUND in piece {pid}")
                            for field, val in hits[:3]:
                                print(f"    {field}: {val[:120]}")
                        else:
                            print(f"  piece keys: {list(pdoc.keys())}")
                except Exception as e:
                    print(f"  Error: {e}")
        else:
            print("  No PDF fields found, no piece refs either")
