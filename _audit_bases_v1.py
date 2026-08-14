"""
_audit_bases_v1.py
Audit complet des bases produits V1 :
  1. Articles sources suspects / incompréhensibles
  2. Comptes comptables incohérents avec le métier
"""
import json, glob, re, unicodedata

# ─── Termes génériques à supprimer ───────────────────────────────────────────
GENERIQUES = {
    'divers', 'acompte', 'avoir', 'remise', 'escompte', 'inconnu',
    'total', 'sous total', 'sous-total', 'n/a', 'na', 'autre', 'autres',
    'non defini', 'non renseigne', 'annulation', 'annule', 'credit',
    'debit', 'regularisation', 'ajustement', 'correction', 'erreur',
    'test', 'xxx', 'yyy', 'zzz', 'tbd', 'todo', 'neant', 'aucun',
    'aucune', 'forfait', 'prestation', 'service', 'product', 'article',
    'marchandise', 'livraison', 'frais', 'charge', 'produit',
}

# ─── Comptes attendus par métier ─────────────────────────────────────────────
METIER_COMPTES = {
    'boucherie':    (['601', '602', '607'], ['606', '615', '62', '63', '64', '65']),
    'boulangerie':  (['601', '602', '607'], ['606', '615', '62', '63']),
    'btp':          (['601', '602', '605', '606', '607'], ['615', '62', '63']),
    'epicerie':     (['601', '602', '607'], ['606', '615', '62']),
    'restaurant':   (['601', '602', '607', '606'], ['615', '62', '63']),
    'transport':    (['601', '602', '606', '607', '615', '616', '61', '62', '63', '64'], []),
    'vtc':          (['601', '602', '606', '607', '615', '616', '61', '62', '63', '64'], []),
    'global':       (['606', '615', '616', '61', '62', '63', '64', '65'], []),  # charges_externes
}

def normalize(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def is_suspect(article_source, article_canonique, mots_cles):
    canon = article_canonique or normalize(article_source or '')

    # 1. Terme générique exact
    if canon in GENERIQUES:
        return 'terme_generique'

    # 2. Trop court (1 seul mot de moins de 3 lettres)
    mots = [m for m in (mots_cles or canon.split()) if m]
    if len(mots) == 1 and len(mots[0]) <= 2:
        return 'trop_court'

    # 3. Uniquement des chiffres
    if re.fullmatch(r'[\d\s\-/\.]+', canon):
        return 'chiffres_seulement'

    # 4. Ressemble à une référence interne (ex: "120186/CONSOLE" est OK, "B657F0DA" non)
    if re.fullmatch(r'[a-f0-9\-]{8,}', canon.replace(' ', '')):
        return 'hash_ou_ref'

    return None

def compte_ok(compte, metier):
    if not compte:
        return False, 'compte_manquant'
    prefixes_ok, _ = METIER_COMPTES.get(metier, (['6'], []))
    for p in prefixes_ok:
        if compte.startswith(p):
            return True, ''
    return False, f'compte_{compte}_inattendu_pour_{metier}'

# ─── Analyse ─────────────────────────────────────────────────────────────────
files = sorted(glob.glob('base_produits_*_v1.json')) + ['base_charges_externes_v1.json']

all_suspects = {}   # fp -> list of (index, reason, item)
all_bad_comptes = {}

for fp in files:
    try:
        with open(fp, encoding='utf-8') as f:
            d = json.load(f)
    except UnicodeDecodeError:
        with open(fp, encoding='utf-8-sig') as f:
            d = json.load(f)

    metier = d.get('meta', {}).get('metier', 'global')
    items = d.get('items', [])
    suspects = []
    bad_comptes = []

    for i, item in enumerate(items):
        src = item.get('article_source', '')
        canon = item.get('article_canonique', '')
        mots = item.get('mots_cles', [])
        compte = item.get('compte_comptable')

        reason = is_suspect(src, canon, mots)
        if reason:
            suspects.append((i, reason, src, compte))

        ok, why = compte_ok(str(compte) if compte else '', metier)
        if not ok:
            bad_comptes.append((i, src, compte, why))

    all_suspects[fp] = suspects
    all_bad_comptes[fp] = bad_comptes

# ─── Rapport ─────────────────────────────────────────────────────────────────
print("=" * 70)
print("RAPPORT D'AUDIT DES BASES PRODUITS V1")
print("=" * 70)

total_suspects = 0
total_bad = 0

for fp in files:
    suspects = all_suspects[fp]
    bad = all_bad_comptes[fp]
    total_suspects += len(suspects)
    total_bad += len(bad)

    try:
        with open(fp, encoding='utf-8') as f:
            d = json.load(f)
    except UnicodeDecodeError:
        with open(fp, encoding='utf-8-sig') as f:
            d = json.load(f)
    n = len(d.get('items', []))

    print(f"\n{fp}  ({n} items)")
    print(f"  Articles suspects : {len(suspects)}")
    for idx, reason, src, compte in suspects[:20]:
        print(f"    [{idx}] {src!r}  (compte={compte})  → {reason}")
    if len(suspects) > 20:
        print(f"    ... et {len(suspects)-20} autres")

    print(f"  Comptes incohérents : {len(bad)}")
    for idx, src, compte, why in bad[:10]:
        print(f"    [{idx}] {src!r}  compte={compte}  → {why}")
    if len(bad) > 10:
        print(f"    ... et {len(bad)-10} autres")

print(f"\n{'='*70}")
print(f"TOTAL suspects à supprimer : {total_suspects}")
print(f"TOTAL comptes incohérents  : {total_bad}")
print("=" * 70)
