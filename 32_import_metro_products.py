"""
32_import_metro_products.py

Import Metro France products from keymanage_accounting invoice_forms into:
  - base_produits_restaurant_v1.json  (food / matières premières / marchandises)
  - base_charges_externes_v1.json     (fournitures d'entretien et équipement)

Source : keymanage_accounting, partition fr_bd_452416191
Client : SARL LE 62, SIREN 452416191, APE 5610C (Restauration rapide, Rennes)
Supplier: Metro France, SIREN 399315613, APE 4639B (Commerce de gros alimentaire)

Account mapping (normalized, sans zéros de remplissage):
  601*, 602*, 607*, 6061 → base_produits_restaurant_v1.json
  606*, 6062, 6063, 6068 → base_charges_externes_v1.json
  account=None + TVA 5.5% → restaurant
  account=None + TVA 20%  → charges_externes

Usage:
  python 32_import_metro_products.py          # dry-run (no modification)
  python 32_import_metro_products.py --apply  # apply to JSON files
"""

import json
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timezone

import requests

sys.path.insert(0, '.')
from couch_config import COUCHDB_URL, COUCHDB_USER, COUCHDB_PASS, CLIENT_CERT, CLIENT_KEY, CA_CERT

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

APPLY = '--apply' in sys.argv

S = dict(
    auth=(COUCHDB_USER, COUCHDB_PASS),
    cert=(CLIENT_CERT, CLIENT_KEY),
    verify=CA_CERT,
    timeout=60,
)

PARTITION = 'fr_bd_452416191'
CLIENT_APE = '5610C'          # SARL LE 62 – Restauration rapide
TYPE_FOURNISSEUR = 'grossiste alimentaire'
MAX_NEW_ITEMS_PER_BASE = 50   # max nouveaux items Metro ajoutés par base

BASE_RESTAURANT = 'base_produits_restaurant_v1.json'
BASE_CHARGES    = 'base_charges_externes_v1.json'

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_val(field):
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get('value')
    return field


def normalize(s):
    """Lowercase, remove accents, collapse whitespace."""
    s = unicodedata.normalize('NFD', str(s).lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def normalize_account(acc):
    """
    Strip trailing zeros from account codes, keeping at least 3 digits.
    e.g. 607000 → 607, 60700 → 607, 6011 → 6011, 6063 → 6063
    """
    if not acc:
        return None
    acc = str(acc).strip()
    while len(acc) > 3 and acc.endswith('0'):
        acc = acc[:-1]
    return acc


def account_prefix(acc):
    """First 3 digits of normalized account."""
    if not acc:
        return None
    return normalize_account(acc)[:3]


def classify_account(raw_acc, tva):
    """
    Returns (target_base, categorie, sous_categorie) based on account and TVA.
    """
    acc = normalize_account(raw_acc) if raw_acc else None
    prefix = acc[:3] if acc else None

    # Food / raw materials / merchandise
    if prefix in ('601', '602', '607'):
        cat = 'exploitation_metier'
        if prefix == '601':
            sous = 'matiere_premiere'
        elif prefix == '602':
            sous = 'approvisionnement'
        else:  # 607
            sous = 'marchandise'
        return BASE_RESTAURANT, cat, sous

    # Beverages classified under 6061 (non-standard but observed)
    if acc and acc.startswith('606') and acc[:4] == '6061':
        return BASE_RESTAURANT, 'exploitation_metier', 'boisson'

    # External charges / fournitures
    if acc and acc.startswith('606'):
        return BASE_CHARGES, 'charge_externe', 'fourniture'

    # Unknown account → fallback by TVA
    if tva is not None:
        if float(tva) <= 10.0:
            return BASE_RESTAURANT, 'exploitation_metier', 'matiere_premiere'
        else:
            return BASE_CHARGES, 'charge_externe', 'fourniture'

    # No account, no TVA → restaurant by default
    return BASE_RESTAURANT, 'exploitation_metier', 'matiere_premiere'


# ─────────────────────────────────────────────
# Step 1: Fetch all invoice_forms for partition
# ─────────────────────────────────────────────

print(f"[1] Fetching Metro invoice_forms from partition {PARTITION}...")

all_forms = []
bookmark = None
while True:
    q = {
        'selector': {'p': 'invoice_form'},
        'limit': 200,
        'fields': ['_id', 'issuer', 'invoice_date', 'invoice_number',
                   'line_items', 'form_common_core_ref'],
    }
    if bookmark:
        q['bookmark'] = bookmark

    r = requests.post(
        f'{COUCHDB_URL}/keymanage_accounting/_partition/{PARTITION}/_find',
        json=q, **S,
    )
    body = r.json()
    docs = body.get('docs', [])
    if not docs:
        break
    all_forms.extend(docs)
    bookmark = body.get('bookmark')
    print(f"  … fetched {len(all_forms)} forms", end='\r')
    if len(docs) < 200:
        break

print(f"\n  Total invoice_forms: {len(all_forms)}")

# Filter Metro
def issuer_name(issuer):
    if not issuer or not isinstance(issuer, dict):
        return ''
    return str(
        get_val(issuer.get('name')) or
        get_val(issuer.get('legal_name')) or ''
    ).strip()

metro_forms = [f for f in all_forms if 'metro' in issuer_name(f.get('issuer', {})).lower()]
print(f"  Metro forms: {len(metro_forms)}")

# ─────────────────────────────────────────────
# Step 2: Bulk-fetch core_profile docs for PDF paths
# ─────────────────────────────────────────────

print("\n[2] Fetching core_profile docs for PDF paths...")

core_ids = []
for form in metro_forms:
    fcr = form.get('form_common_core_ref') or {}
    cid = fcr.get('id') if isinstance(fcr, dict) else None
    if cid:
        core_ids.append(cid)

core_ids = list(set(core_ids))
print(f"  Unique core_profile IDs: {len(core_ids)}")

# Batch requests (CouchDB _all_docs with POST keys)
BATCH = 100
core_path_map = {}   # core_id → pdf_path

for i in range(0, len(core_ids), BATCH):
    batch = core_ids[i:i + BATCH]
    r2 = requests.post(
        f'{COUCHDB_URL}/keymanage_accounting/_all_docs?include_docs=true',
        json={'keys': batch}, **S,
    )
    rows = r2.json().get('rows', [])
    for row in rows:
        doc = row.get('doc')
        if not doc:
            continue
        fcc = doc.get('form_common_core', {}) or {}
        ingest = fcc.get('ingest', {}) or {}
        path = ingest.get('path') or ingest.get('file_name')
        core_path_map[row['id']] = path

print(f"  Paths resolved: {len(core_path_map)}")

# ─────────────────────────────────────────────
# Step 3: Aggregate unique products
# ─────────────────────────────────────────────

print("\n[3] Aggregating unique products from line items...")

# products[desc_norm] = {
#   'article_source': str (most common capitalization),
#   'accounts': Counter,
#   'account_labels': Counter,
#   'tvas': Counter,
#   'invoice_ids': list,
#   'pdf_paths': list,
# }
products = {}

for form in metro_forms:
    form_id = form['_id']
    fcr = form.get('form_common_core_ref') or {}
    core_id = fcr.get('id') if isinstance(fcr, dict) else None
    pdf_path = core_path_map.get(core_id) if core_id else None

    for li in (form.get('line_items') or []):
        desc_raw = get_val(li.get('description'))
        if not desc_raw or not str(desc_raw).strip():
            continue
        desc_raw = str(desc_raw).strip()

        item_type = (get_val(li.get('item_type')) or '').lower()
        if item_type == 'service':
            continue  # skip services

        desc_norm = normalize(desc_raw)
        tva = get_val(li.get('vat_percent'))
        account = get_val(li.get('accounting_account'))
        account_label = get_val(li.get('accounting_account_label'))

        if desc_norm not in products:
            products[desc_norm] = {
                'article_source': desc_raw.upper(),
                'articles_raw': Counter(),
                'accounts': Counter(),
                'account_labels': {},
                'tvas': Counter(),
                'invoice_ids': [],
                'pdf_paths': [],
            }

        p = products[desc_norm]
        p['articles_raw'][desc_raw.upper()] += 1
        if account:
            p['accounts'][str(account)] += 1
            if account_label and str(account) not in p['account_labels']:
                p['account_labels'][str(account)] = account_label
        if tva is not None:
            p['tvas'][float(tva)] += 1
        if form_id not in p['invoice_ids']:
            p['invoice_ids'].append(form_id)
        if pdf_path and pdf_path not in p['pdf_paths']:
            p['pdf_paths'].append(pdf_path)

print(f"  Unique products: {len(products)}")

# ─────────────────────────────────────────────
# Step 4: Load existing bases & build dup sets
# ─────────────────────────────────────────────

print("\n[4] Loading existing product bases...")

def load_base(fp):
    with open(fp, encoding='utf-8') as f:
        return json.load(f)

base_restaurant = load_base(BASE_RESTAURANT)
base_charges    = load_base(BASE_CHARGES)

existing_restaurant = {item['article_canonique'] for item in base_restaurant['items']}
existing_charges    = {item['article_canonique'] for item in base_charges['items']}

print(f"  {BASE_RESTAURANT}: {len(base_restaurant['items'])} items existing")
print(f"  {BASE_CHARGES}: {len(base_charges['items'])} items existing")

# ─────────────────────────────────────────────
# Step 5: Build new items to inject
# ─────────────────────────────────────────────

print("\n[5] Building new items...")

new_restaurant = []
new_charges    = []
skipped_dup    = 0
skipped_nodata = 0

for desc_norm, p in products.items():
    # Pick dominant account and TVA
    raw_account = p['accounts'].most_common(1)[0][0] if p['accounts'] else None
    tva = p['tvas'].most_common(1)[0][0] if p['tvas'] else None
    account_norm = normalize_account(raw_account)
    account_label = (p['account_labels'].get(raw_account) if raw_account else None)

    # Most common capitalization for display
    article_source = p['articles_raw'].most_common(1)[0][0]
    mots_cles = [m for m in desc_norm.split() if len(m) >= 2]

    if not article_source or not mots_cles:
        skipped_nodata += 1
        continue

    target_base, categorie, sous_categorie = classify_account(raw_account, tva)

    item = {
        'article_source': article_source,
        'article_canonique': desc_norm,
        'mots_cles': mots_cles,
        'source_invoice_ids': p['invoice_ids'],
        'ids_factures_sources': p['invoice_ids'],
        'invoice_paths_sources': p['pdf_paths'],
        'ape_context': [CLIENT_APE],
        'partitions_sources': [PARTITION],
        'compte_comptable': account_norm,
        'compte_comptable_libelle': account_label,
        'taux_tva': tva,
        'categorie': categorie,
        'sous_categorie': sous_categorie,
        'type_fournisseur': TYPE_FOURNISSEUR,
    }

    if target_base == BASE_RESTAURANT:
        if desc_norm in existing_restaurant:
            skipped_dup += 1
        elif len(new_restaurant) < MAX_NEW_ITEMS_PER_BASE:
            new_restaurant.append(item)
            existing_restaurant.add(desc_norm)   # prevent double-add in same run
    else:
        if desc_norm in existing_charges:
            skipped_dup += 1
        elif len(new_charges) < MAX_NEW_ITEMS_PER_BASE:
            new_charges.append(item)
            existing_charges.add(desc_norm)

print(f"  New → {BASE_RESTAURANT}: {len(new_restaurant)}")
print(f"  New → {BASE_CHARGES}: {len(new_charges)}")
print(f"  Skipped (already exists): {skipped_dup}")
print(f"  Skipped (no data): {skipped_nodata}")

# ─────────────────────────────────────────────
# Step 6: Preview samples
# ─────────────────────────────────────────────

print("\n[6] Sample new restaurant items:")
for it in new_restaurant[:5]:
    print(f"  {it['article_source']!r} | compte={it['compte_comptable']} | tva={it['taux_tva']}%")

print("\nSample new charges_externes items:")
for it in new_charges[:5]:
    print(f"  {it['article_source']!r} | compte={it['compte_comptable']} | tva={it['taux_tva']}%")

# ─────────────────────────────────────────────
# Step 7: Apply (only with --apply flag)
# ─────────────────────────────────────────────

if not APPLY:
    print("\n[DRY-RUN] No files modified. Run with --apply to save.")
    sys.exit(0)

now_iso = datetime.now(timezone.utc).isoformat()

def save_base(fp, base_data, new_items):
    if not new_items:
        print(f"  {fp}: nothing to add, skipping.")
        return
    base_data['items'].extend(new_items)
    base_data['meta']['items_count'] = len(base_data['items'])
    base_data['meta']['updated'] = now_iso
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(base_data, f, ensure_ascii=False, indent=2)
    print(f"  Saved {fp}: {len(base_data['items'])} items total (+{len(new_items)} new)")

print("\n[7] Writing files...")
save_base(BASE_RESTAURANT, base_restaurant, new_restaurant)
save_base(BASE_CHARGES,    base_charges,    new_charges)
print("\nDone.")
