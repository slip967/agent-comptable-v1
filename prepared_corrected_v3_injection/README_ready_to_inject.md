# Corrected V3 Ready To Inject

Ce dossier provient de l'archive `bases_corrected_v3_ready_to_inject.zip` extraite localement.

## Contenu

- total_json_files: `8`
- total_instance_docs: `2179`

- `base_charges_externes_corrected_v3.json`: items=`512` a_valider=`0` instances=`512` metier=`global`
- `base_produits_boucherie_corrected_v3.json`: items=`212` a_valider=`0` instances=`212` metier=`boucherie`
- `base_produits_boulangerie_corrected_v3.json`: items=`200` a_valider=`0` instances=`200` metier=`boulangerie`
- `base_produits_btp_corrected_v3.json`: items=`163` a_valider=`0` instances=`163` metier=`btp`
- `base_produits_epicerie_corrected_v3.json`: items=`444` a_valider=`0` instances=`444` metier=`epicerie`
- `base_produits_restaurant_corrected_v3.json`: items=`219` a_valider=`0` instances=`219` metier=`restaurant`
- `base_produits_transport_corrected_v3.json`: items=`134` a_valider=`0` instances=`134` metier=`transport`
- `base_produits_vtc_corrected_v3.json`: items=`295` a_valider=`0` instances=`295` metier=`vtc`

## Commandes prêtes

Dry-run :

```bash
python 22_import_product_base_instances.py --db ayasmine_test2 --pattern prepared_corrected_v3_injection/base_produits_*_corrected_v3.json prepared_corrected_v3_injection/base_charges_externes_corrected_v3.json --dry-run
```

Import réel :

```bash
python 22_import_product_base_instances.py --db ayasmine_test2 --pattern prepared_corrected_v3_injection/base_produits_*_corrected_v3.json prepared_corrected_v3_injection/base_charges_externes_corrected_v3.json
```

## Notes

- Les fichiers d'origine du workspace ne sont pas modifiés.
- L'import consommera seulement les `items` actifs.
- Les fichiers `_with_accounts` ne sont pas nécessaires pour le script d'import actuel.
