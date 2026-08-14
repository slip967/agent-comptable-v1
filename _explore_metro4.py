import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)

# Check if DB is partitioned
info = requests.get(f'{COUCHDB_URL}/keymanage_accounting', **S).json()
print("DB partitioned:", info.get('props', {}).get('partitioned', False))
print("DB doc_count:", info.get('doc_count'))

# Known partition from Metro entries: fr_bd_452416191
PARTITION = 'fr_bd_452416191'

# Count docs in this partition
r = requests.get(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}', **S)
print(f"\nPartition {PARTITION!r} status:", r.status_code)
if r.status_code == 200:
    pinfo = r.json()
    print("  doc_count:", pinfo.get('doc_count'))

# Query within partition: find 401 entries with METRO label (purchase invoices)
print(f"\n=== METRO 401 ENTRIES IN PARTITION {PARTITION} ===")
q = {
    'selector': {
        'journal_code': 'HA',
        'account_number': '401',
        'label': {'$regex': '(?i)metro'}
    },
    'fields': ['_id', 'piece_id', 'label', 'account_number', 'date', 'piece_ref', 'credit', 'debit', 'tva_lines', 'aux_account'],
    'limit': 20
}
r2 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q, **S)
print("Status:", r2.status_code)
docs_401 = r2.json().get('docs', [])
print(f"Found {len(docs_401)} Metro 401 entries")
piece_ids = list({d['piece_id'] for d in docs_401 if d.get('piece_id')})
print(f"Unique piece_ids: {len(piece_ids)}")
for d in docs_401[:3]:
    print(f"  piece_id={d.get('piece_id')} | label={d.get('label')} | date={d.get('date')} | credit={d.get('credit')}")

# For those pieces, find the 6xx product lines
print(f"\n=== 6xx PRODUCT ENTRIES FOR THOSE PIECES ===")
if piece_ids:
    q2 = {
        'selector': {
            'piece_id': {'$in': piece_ids[:10]},
            'account_number': {'$regex': '^6'}
        },
        'fields': ['_id', 'piece_id', 'label', 'account_number', 'debit', 'tva_lines', 'date', 'piece_ref'],
        'limit': 30
    }
    r3 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q2, **S)
    print("Status:", r3.status_code)
    docs_6xx = r3.json().get('docs', [])
    print(f"Found {len(docs_6xx)} product lines")
    for d in docs_6xx[:10]:
        tva = d.get('tva_lines', [])
        taux = tva[0].get('taux') if tva else None
        print(f"  label={d.get('label')!r} | account={d.get('account_number')} | debit={d.get('debit')} | tva={taux}%")
