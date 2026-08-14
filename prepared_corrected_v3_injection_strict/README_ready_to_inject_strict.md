# Corrected V3 Strict Injection

## Perimetre

- Bases incluses : `boucherie`, `boulangerie`, `restaurant`, `btp`, `transport`, `charges_externes`
- Bases exclues volontairement : `vtc`, `epicerie`

## Corrections appliquees

- Corrections de comptes `transport` : `11`
- Lignes BTP sorties du lot produit strict : `30`

## Volumes

- `base_produits_boucherie_corrected_v3.json` : `212`
- `base_produits_boulangerie_corrected_v3.json` : `200`
- `base_produits_restaurant_corrected_v3.json` : `219`
- `base_produits_btp_corrected_v3.json` : `133`
- `base_produits_transport_corrected_v3.json` : `134`
- `base_charges_externes_corrected_v3.json` : `512`

## Commande dry-run

```bash
python 22_import_product_base_instances.py --db ayasmine_test2 --pattern prepared_corrected_v3_injection_strict/base_produits_*_corrected_v3.json prepared_corrected_v3_injection_strict/base_charges_externes_corrected_v3.json --dry-run
```

