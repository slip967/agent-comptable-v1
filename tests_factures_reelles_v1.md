# Tests Sur Factures Reelles V1

Ce rapport verifie, pour chaque article des bases V1, la presence de jusqu'a 3 `invoice_id` source.

| Base | Metier | Items | Sources OK | A revoir |
|---|---|---:|---:|---:|
| base_produits_boucherie_v1.json | boucherie | 2 | 2 | 0 |
| base_produits_boulangerie_v1.json | boulangerie | 25 | 25 | 0 |
| base_produits_btp_v1.json | btp | 9 | 9 | 0 |
| base_produits_epicerie_v1.json | epicerie | 0 | 0 | 0 |
| base_charges_externes_v1.json | global | 28 | 28 | 0 |
| base_produits_restaurant_v1.json | restaurant | 2 | 2 | 0 |
| base_produits_transport_v1.json | transport | 1 | 1 | 0 |
| base_produits_vtc_v1.json | vtc | 0 | 0 | 0 |

## Lecture

- `source_ok` : l'article a au moins un `source_invoice_id` rattache a une facture reelle.
- `a_revoir` : l'article n'a pas encore de source facture fiable.
- Detail complet : `tests_factures_reelles_v1.csv`
