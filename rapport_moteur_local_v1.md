# Rapport Moteur Local V1

Ce rapport consolide les resultats locaux du moteur de recommandation comptable sur les charges externes et les produits metier.

## Synthese Globale

- Elements evalues : `67`
- `auto_ok` : `67`
- `validation_humaine` : `0`
- `rejeter` : `0`
- Taux de validation automatique global : `100.0%`

## Charges Externes

- Elements evalues : `28`
- Taux bon compte : `96.43%`
- Taux bon sous-profil : `96.43%`
- `auto_ok` : `28`
- `validation_humaine` : `0`

## Produits Metier

- Elements evalues : `39`
- Taux de match : `100.0%`
- Taux bon compte : `100.0%`
- Taux bon metier : `100.0%`
- `auto_ok` : `39`
- `validation_humaine` : `0`

## Repartition Par Metier

| Metier | Items | auto_ok | validation_humaine | Bon compte | Bon metier |
|---|---|---|---|---|---|
| Boucherie | 2 | 2 | 0 | 100.0% | 100.0% |
| Boulangerie | 25 | 25 | 0 | 100.0% | 100.0% |
| BTP | 9 | 9 | 0 | 100.0% | 100.0% |
| Restaurant | 2 | 2 | 0 | 100.0% | 100.0% |
| Transport | 1 | 1 | 0 | 100.0% | 100.0% |

## Cas Ambigus Charges Externes

Aucun cas ambigu sur les charges externes.

## Cas Ambigus Produits Metier

Aucun cas ambigu sur les produits metier.

## Sources

- Charges externes : `v1_519665103_external_charge_recommendations_v1.json`
- Produits metier : `v1_519665103_product_metier_recommendations_v1.json`
