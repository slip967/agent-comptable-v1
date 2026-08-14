"""
Broad scan: search ANY doc in keymanage_accounting for a PDF path.
Uses CouchDB _all_docs with no partition filter.
"""
import sys, json, pathlib
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

PDF_KEYWORDS = ['.pdf', '/root/windows/', '/mnt/clients/', 'fichiers_pdf']

def contains_pdf(val):
    if not isinstance(val, str) or not val:
        return False
    v = val.lower()
    return any(kw in v for kw in PDF_KEYWORDS)

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

# Full scan in batches of 200
url = f'{COUCHDB_URL}/{db}/_all_docs'
startkey = ''
batch = 200
total = 0
found_count = 0

print("Starting full scan...")
while found_count < 3:
    params = {'include_docs': 'true', 'limit': str(batch)}
    if startkey:
        params['startkey'] = json.dumps(startkey)
        params['skip'] = '1'
    r = s.get(url, params=params, timeout=60)
    data = r.json()
    rows = data.get('rows', [])
    if not rows:
        break
    total += len(rows)
    for row in rows:
        doc = row.get('doc')
        if not isinstance(doc, dict):
            continue
        hits = deep_find_pdf(doc)
        if hits:
            print(f"\nFOUND PDF in doc: {doc.get('_id')}")
            print(f"  p={doc.get('p','?')}")
            for field, val in hits[:3]:
                print(f"  {field}: {val[:120]}")
            found_count += 1
            if found_count >= 3:
                break
    last_id = rows[-1].get('id', '')
    if not last_id or len(rows) < batch:
        break
    startkey = last_id
    if total % 1000 == 0:
        print(f"  ... scanned {total} docs, found {found_count} PDF docs so far")

print(f"\nTotal docs scanned: {total}")
if found_count == 0:
    print("No document with a PDF path found in CouchDB.")
    print("Conclusion: PDF paths are NOT stored in CouchDB documents.")
    print("The 'Voir PDF' feature requires an alternative source (local disk mapping, separate index, etc.)")
