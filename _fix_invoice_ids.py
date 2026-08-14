"""
Fix 2 problèmes de source_invoice_ids :
1. BTP : normaliser les IDs doublés partition:partition:uuid → partition:uuid
2. Epicerie / VTC / charges_externes : retirer les IDs introuvables (PDF METRO)
"""
import json, sys
sys.path.insert(0, '.')
from couch_config import *
import requests
from urllib.parse import quote

s = requests.Session()
s.auth = (COUCHDB_USER, COUCHDB_PASS)
s.cert = (CLIENT_CERT, CLIENT_KEY)
s.verify = CA_CERT

TRULY_MISSING = {
    "fr_bd_831962394:pdf_399315613_METRO_FRANCE_2023_10_03_0_00800002_022918_29_80_pdf",
    "fr_bd_831962394:pdf_399315613_METRO_FRANCE_2023_10_18_0_00800002_024226_142_08_pdf",
    "fr_bd_831962394:pdf_399315613_METRO_FRANCE_2023_10_02_0_00800002_0227762_208_91_pdf",
    "fr_bd_831962394:pdf_399315613_METRO_FRANCE_2023_10_23_002_406554_122_77_pdf",
}


def normalize_id(sid):
    """fr_bd_X:fr_bd_X:uuid → fr_bd_X:uuid"""
    parts = sid.split(":")
    if len(parts) == 3 and parts[0] == parts[1]:
        return parts[0] + ":" + parts[2]
    return sid


def batch_check(db, ids):
    found = set()
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        url = COUCHDB_URL + "/" + quote(db, safe="") + "/_all_docs"
        r = s.post(url, json={"keys": batch}, timeout=30)
        for row in r.json().get("rows", []):
            if "error" not in row and row.get("id"):
                found.add(row["id"])
    return found


# ── 1. Corriger BTP ──────────────────────────────────────────────────────────
print("=== Correction BTP (IDs doublés) ===")
with open("base_produits_btp_v1.json", encoding="utf-8") as f:
    btp = json.load(f)

btp_changed = 0
for item in btp["items"]:
    old_ids = item.get("source_invoice_ids", [])
    new_ids = [normalize_id(sid) for sid in old_ids]
    if new_ids != old_ids:
        item["source_invoice_ids"] = new_ids
        btp_changed += 1

print(f"  {btp_changed} articles corrigés (IDs normalisés)")

# Vérifier que les IDs normalisés existent bien
all_norm = sorted({normalize_id(sid) for it in btp["items"] for sid in it.get("source_invoice_ids", [])})
print(f"  Vérification de {len(all_norm)} IDs normalisés dans keymanage_accounting...")
found_norm = batch_check("keymanage_accounting", all_norm)
still_missing = set(all_norm) - found_norm
if still_missing:
    print(f"  ⚠ Encore {len(still_missing)} IDs introuvables après normalisation :")
    for sid in sorted(still_missing)[:10]:
        print(f"    {sid}")
else:
    print(f"  ✓ Tous les {len(all_norm)} IDs BTP trouvés dans keymanage_accounting")

with open("base_produits_btp_v1.json", "w", encoding="utf-8") as f:
    json.dump(btp, f, ensure_ascii=False, indent=2)
print("  base_produits_btp_v1.json sauvegardé")


# ── 2. Corriger Epicerie / VTC / Charges externes ────────────────────────────
FILES = [
    ("base_produits_epicerie_v1.json", "utf-8"),
    ("base_produits_vtc_v1.json",      "utf-8-sig"),
    ("base_charges_externes_v1.json",  "utf-8"),
]

for fname, enc in FILES:
    with open(fname, encoding=enc) as f:
        data = json.load(f)

    changed = 0
    for item in data["items"]:
        old_ids = item.get("source_invoice_ids", [])
        new_ids = [sid for sid in old_ids if sid not in TRULY_MISSING]
        if len(new_ids) != len(old_ids):
            item["source_invoice_ids"] = new_ids
            changed += 1
            removed = set(old_ids) - set(new_ids)
            print(f"  [{fname}] '{item.get('article_source')}' : {len(removed)} ID(s) retiré(s)")

    if changed:
        out_enc = "utf-8-sig" if enc == "utf-8-sig" else "utf-8"
        with open(fname, "w", encoding=out_enc) as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  {fname} sauvegardé ({changed} articles modifiés)")
    else:
        print(f"  {fname} : aucun changement")

print("\nTerminé.")
