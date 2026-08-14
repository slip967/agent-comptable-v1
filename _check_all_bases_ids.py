"""
Vérifie la provenance des source_invoice_ids pour toutes les bases produits métier
(boucherie, boulangerie, epicerie, vtc, btp + charges_externes)
en cherchant dans keymanage_accounting ET abt3.
"""
import sys, json
sys.path.insert(0, '.')
from couch_config import *
import requests
from urllib.parse import quote

BASES = [
    "base_produits_boucherie_v1.json",
    "base_produits_boulangerie_v1.json",
    "base_produits_epicerie_v1.json",
    "base_produits_vtc_v1.json",
    "base_produits_btp_v1.json",
    "base_charges_externes_v1.json",
]

BATCH_SIZE = 200

s = requests.Session()
s.auth = (COUCHDB_USER, COUCHDB_PASS)
s.cert = (CLIENT_CERT, CLIENT_KEY)
s.verify = CA_CERT


def batch_check(db_name, ids):
    """Retourne l'ensemble des IDs trouvés dans db_name."""
    found = set()
    for i in range(0, len(ids), BATCH_SIZE):
        batch = ids[i:i+BATCH_SIZE]
        url = COUCHDB_URL + "/" + quote(db_name, safe="") + "/_all_docs"
        r = s.post(url, json={"keys": batch}, timeout=30)
        r.raise_for_status()
        for row in r.json().get("rows", []):
            if "error" not in row and row.get("id"):
                found.add(row["id"])
    return found


for base_file in BASES:
    try:
        with open(base_file, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n=== {base_file} : ERREUR LECTURE ({e}) ===")
        continue

    items = data.get("items", [])
    metier = data.get("meta", {}).get("metier", base_file)

    all_ids = set()
    for item in items:
        for sid in item.get("source_invoice_ids", []):
            all_ids.add(sid)

    all_ids_list = sorted(all_ids)
    total = len(all_ids_list)

    print(f"\n=== {metier} ({base_file}) ===")
    print(f"  {len(items)} articles, {total} IDs uniques")

    if total == 0:
        print("  (aucun ID à vérifier)")
        continue

    found_key = batch_check("keymanage_accounting", all_ids_list)
    found_abt3 = batch_check("abt3", all_ids_list)

    both     = found_key & found_abt3
    only_key = found_key - found_abt3
    only_abt = found_abt3 - found_key
    nowhere  = all_ids - found_key - found_abt3

    print(f"  Dans keymanage_accounting seulement : {len(only_key)}")
    print(f"  Dans abt3 seulement                 : {len(only_abt)}")
    print(f"  Dans les deux DBs                   : {len(both)}")
    print(f"  INTROUVABLES                        : {len(nowhere)}")

    if nowhere:
        print(f"  Articles avec IDs introuvables ({len([it for it in items if any(sid in nowhere for sid in it.get('source_invoice_ids',[]))])}):")
        for item in items:
            ids = item.get("source_invoice_ids", [])
            missing_here = [sid for sid in ids if sid in nowhere]
            if missing_here:
                print(f"    - '{item.get('article_source', '?')}'")
                for sid in missing_here:
                    print(f"        {sid}")

print("\nFin de la vérification.")
