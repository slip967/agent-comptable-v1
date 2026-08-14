import requests, sys, json
sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

S = dict(auth=(COUCHDB_USER, COUCHDB_PASS), cert=(CLIENT_CERT, CLIENT_KEY), verify=CA_CERT, timeout=40)
PARTITION = 'fr_bd_452416191'

def get_val(field):
    """Extract .value from a possibly nested CouchDB field."""
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get('value')
    return field

def issuer_name(issuer):
    if not issuer:
        return ''
    if isinstance(issuer, dict):
        name = get_val(issuer.get('name')) or get_val(issuer.get('legal_name')) or ''
        return str(name).strip()
    return str(issuer).strip()

# Fetch invoice_forms in batches (200 limit per request, use bookmark pagination)
all_forms = []
bookmark = None
while True:
    q = {
        'selector': {'p': 'invoice_form'},
        'limit': 200,
        'fields': ['_id', 'issuer', 'invoice_date', 'invoice_number', 'line_items', 'entry_ids', 'accounting_summary']
    }
    if bookmark:
        q['bookmark'] = bookmark
    r = requests.post(f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find', json=q, **S)
    data = r.json()
    docs = data.get('docs', [])
    if not docs:
        break
    all_forms.extend(docs)
    bookmark = data.get('bookmark')
    print(f"Fetched {len(all_forms)} invoice_forms so far...")
    if len(docs) < 200:
        break

print(f"\nTotal invoice_forms in {PARTITION}: {len(all_forms)}")

# Identify issuers
from collections import Counter
issuers = Counter()
for f in all_forms:
    name = issuer_name(f.get('issuer', {}))
    issuers[name.upper()[:40]] += 1
print("\nTop issuers:")
for name, cnt in issuers.most_common(15):
    print(f"  {name!r}: {cnt}")

# Metro forms
metro_forms = [f for f in all_forms if 'metro' in issuer_name(f.get('issuer',{})).lower()]
print(f"\nMetro forms: {len(metro_forms)}")

# Inspect one Metro form line_items
if metro_forms:
    mf = metro_forms[0]
    print(f"\nExample Metro form: {mf['_id']}")
    print(f"Date: {get_val(mf.get('invoice_date'))}")
    print(f"Invoice#: {get_val(mf.get('invoice_number'))}")
    li_list = mf.get('line_items', [])
    print(f"Line items: {len(li_list)}")
    for li in li_list[:5]:
        desc = get_val(li.get('description'))
        qty = get_val(li.get('quantity'))
        unit_price = get_val(li.get('unit_price'))
        total_net = get_val(li.get('total_net'))
        tva = get_val(li.get('vat_percent')) or get_val(li.get('tva_percent'))
        account = get_val(li.get('account')) or get_val(li.get('compte_comptable'))
        item_type = get_val(li.get('item_type'))
        print(f"  desc={desc!r} | qty={qty} | unit={unit_price} | net={total_net} | tva={tva} | account={account} | type={item_type}")
    print("\nFull first line_item keys:", list(li_list[0].keys()) if li_list else [])
