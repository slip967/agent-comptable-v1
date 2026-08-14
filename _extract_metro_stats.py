import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)
PARTITION = 'fr_bd_452416191'

def get_val(field):
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get('value')
    return field

# Get core_profile to find APE
q = {'selector': {'p': 'core_profile'}, 'limit': 3}
r = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q, **S)
cps = r.json().get('docs', [])
print(f"core_profile docs: {len(cps)}")
for cp in cps:
    print(f"  ID: {cp['_id']}")
    print(f"  Keys: {list(cp.keys())[:20]}")
    print(f"  Sample: {json.dumps({k: cp.get(k) for k in list(cp.keys())[:15]}, ensure_ascii=False)[:500]}")
    print()

# Now fetch ALL Metro invoice forms
print("\n=== FETCHING ALL METRO INVOICE FORMS ===")
all_forms = []
bookmark = None
while True:
    q2 = {
        'selector': {'p': 'invoice_form'},
        'limit': 200,
        'fields': ['_id', 'issuer', 'invoice_date', 'invoice_number', 'line_items',
                   'form_common_core_ref', 'entry_ids']
    }
    if bookmark:
        q2['bookmark'] = bookmark
    r2 = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q2, **S)
    data = r2.json()
    docs = data.get('docs', [])
    if not docs:
        break
    all_forms.extend(docs)
    bookmark = data.get('bookmark')
    if len(docs) < 200:
        break

print(f"Total invoice_forms: {len(all_forms)}")

# Filter Metro
def issuer_name(issuer):
    if not issuer or not isinstance(issuer, dict):
        return ''
    return str(get_val(issuer.get('name')) or get_val(issuer.get('legal_name')) or '').strip()

metro_forms = [f for f in all_forms if 'metro' in issuer_name(f.get('issuer',{})).lower()]
print(f"Metro forms: {len(metro_forms)}")

# Extract all line items
from collections import defaultdict
products = defaultdict(list)  # description_norm -> list of {invoice_id, tva, account, account_label, date, path}

for form in metro_forms:
    form_id = form['_id']
    date = get_val(form.get('invoice_date'))
    # PDF path from form_common_core_ref
    fcr = form.get('form_common_core_ref', {}) or {}
    pdf_path = None
    if isinstance(fcr, dict):
        ingest = fcr.get('ingest', {}) or {}
        if isinstance(ingest, dict):
            pdf_path = ingest.get('path') or ingest.get('file_name')

    for li in (form.get('line_items') or []):
        desc = get_val(li.get('description'))
        if not desc or not str(desc).strip():
            continue
        desc = str(desc).strip().upper()
        item_type = get_val(li.get('item_type')) or ''
        if item_type.lower() == 'service':
            continue  # skip services, keep "bien" and unknown

        tva = get_val(li.get('vat_percent'))
        account = get_val(li.get('accounting_account'))
        account_label = get_val(li.get('accounting_account_label'))

        # Normalize
        import unicodedata, re
        def normalize(s):
            s = unicodedata.normalize('NFD', str(s).lower())
            s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
            s = re.sub(r'[^a-z0-9\s]', ' ', s)
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        desc_norm = normalize(desc)
        products[desc_norm].append({
            'article_source': desc,
            'invoice_id': form_id,
            'tva': tva,
            'account': str(account) if account else None,
            'account_label': account_label,
            'date': date,
            'pdf_path': pdf_path,
        })

print(f"\nUnique products: {len(products)}")

# Stats on accounts
from collections import Counter
account_counts = Counter()
tva_counts = Counter()
for desc_norm, entries in products.items():
    acc = entries[0].get('account') or 'None'
    tva = entries[0].get('tva')
    account_counts[acc] += 1
    tva_counts[str(tva)] += 1

print("\nAccount distribution:")
for acc, cnt in account_counts.most_common(15):
    print(f"  {acc}: {cnt} products")

print("\nTVA distribution:")
for tva, cnt in tva_counts.most_common(10):
    print(f"  {tva}%: {cnt} products")

# Sample some products
print("\nSample products (first 20):")
for i, (desc_norm, entries) in enumerate(list(products.items())[:20]):
    e = entries[0]
    print(f"  {e['article_source']!r} | account={e['account']} | tva={e['tva']}% | invoices={len(entries)}")
