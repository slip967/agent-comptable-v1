import json, glob, requests, sys
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=30)
PARTITION = 'fr_bd_452416191'

# 1. Check product bases for this partition
print("=== PARTITION IN EXISTING BASES ===")
for fp in sorted(glob.glob('base_produits_*_v1.json')):
    with open(fp, encoding='utf-8') as f:
        d = json.load(f)
    items = d.get('items', [])
    hits = [i for i in items if PARTITION in (i.get('partitions_sources') or [])]
    hits2 = [i for i in items if any(PARTITION in str(sid) for sid in (i.get('source_invoice_ids') or []))]
    total = len(set([i.get('article_canonique','') for i in hits + hits2]))
    if total:
        ex = (hits + hits2)[0]
        print(f"  {fp}: {total} items | ex: {ex.get('article_source')} account={ex.get('compte_comptable')}")
    else:
        print(f"  {fp}: 0 items")

# 2. Get client info / APE from keymanage_accounting
print(f"\n=== CLIENT INFO FOR {PARTITION} ===")
# Try to find a doc with APE or client profile
for p_val in ['client_profile', 'profile', 'company', 'fournisseur_profile', 'client']:
    q = {'selector': {'p': p_val}, 'limit': 1}
    r = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q, **S)
    docs = r.json().get('docs', [])
    if docs:
        print(f"  p={p_val}: FOUND ID={docs[0]['_id']}")
        print(f"  Keys: {list(docs[0].keys())[:15]}")
        break

# 3. Check activity_account in keymanage_novembre for this SIREN
# SIREN for fr_bd_452416191 = last 9 digits = 452416191
siren = '452416191'
q2 = {'selector': {'p': 'activity_account', '_id': {'$regex': f'.*{siren}.*'}}, 'limit': 3}
r2 = requests.post(f'{COUCHDB_URL}/keymanage_novembre/_find', json=q2, **S)
aa_docs = r2.json().get('docs', [])
print(f"\nactivity_account for SIREN {siren}: {len(aa_docs)}")
for d in aa_docs[:3]:
    print(f"  {d['_id']} | {json.dumps({k: d.get(k) for k in ['p','accounts'] if k in d}, ensure_ascii=False)[:200]}")

# 4. Check what APE does the siren 452416191 use in keymanage_accounting
print(f"\n=== ALL PARTITIONS WITH METRO (across keymanage_accounting) ===")
# Find partitions where label has 'metro' in HA journal
q3 = {
    'selector': {'p': 'entry', 'journal_code': 'HA', 'label': {'$regex': '(?i)metro'}},
    'fields': ['_id'],
    'limit': 100,
    'use_index': 'idx_p'
}
r3 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_find', json=q3, **S)
docs3 = r3.json().get('docs', [])
partitions_with_metro = list({d['_id'].split(':')[0] for d in docs3})
print(f"Partitions with Metro HA entries (sample of 100): {partitions_with_metro[:10]}")
