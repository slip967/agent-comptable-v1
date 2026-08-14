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

# 1. Inspect an invoice doc to see all fields
doc_id = 'fr_bd_892833831:00063ada-ba29-4717-b704-992d158ec6ca'
r = s.get(f'{COUCHDB_URL}/{db}/{quote(doc_id, safe="")}', timeout=30)
doc = r.json()

print("=== INVOICE DOC KEYS ===")
print(list(doc.keys()))
print()

# Deep string walker
def show(d, prefix=''):
    if isinstance(d, dict):
        for k, v in d.items():
            show(v, f"{prefix}{k}.")
    elif isinstance(d, list):
        for i, v in enumerate(d[:3]):
            show(v, f"{prefix}[{i}].")
    elif isinstance(d, str) and d:
        print(f"  {prefix[:-1]}: {repr(d[:150])}")

show(doc)
print()
print("form_common_core_ref:", doc.get('form_common_core_ref'))

# 2. Check if form_common_core_ref points to another doc with PDF path
ref = doc.get('form_common_core_ref')
if ref:
    print()
    print("=== LOOKING UP CORE REF DOC ===")
    r2 = s.get(f'{COUCHDB_URL}/{db}/{quote(str(ref), safe="")}', timeout=30)
    if r2.status_code == 200:
        ref_doc = r2.json()
        print("KEYS:", list(ref_doc.keys()))
        show(ref_doc)
    else:
        print("Status:", r2.status_code)
