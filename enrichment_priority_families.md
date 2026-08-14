# Priorites d'enrichissement des familles

- Base d'analyse: lot des `40` factures re-testees avec le moteur durci.
- Perimetre retenu: lignes en `rejeter` ou lignes sous `70` de score.

| Famille | Nb lignes | Bases candidates frequentes | Comptes proposes frequents | Score moyen | Decision dominante | Recommandation | Exemples |
|---|---:|---|---|---:|---|---|---|
| BTP / peinture / mastic / diluant / filtre / moteur / plaquette | 75 | BTP (47), VTC (23), Charges externes (3) | 6061 (35), 6062 (13), 615 (10) | 50.12 | rejeter | ajouter synonymes | PEINTURE SLV DEBBER, Divers EPANGE, AGRAFE, AGRAFE, AUGE CABAS 42 LITRES NOIRE |
| produits METRO / alimentation generale | 26 | Epicerie (13), Charges externes (5), VTC (3) | 607 (12), 6068 (6), 6061 (4) | 62.44 | rejeter | enrichir base JSON | 500 ML Créme Citron, 30M Film Alimentaire, 250ml Creme Beauté, 1L Citron d'Eté Nettoyant de Surface, 24 rouleaux Papier Toilette 3 Plis |
| autres / a analyser | 18 | BTP (13), Charges externes (4), VTC (1) | 6061 (12), 6063 (3), 6068 (2) | 52.48 | rejeter | garder en validation humaine | Divers, RUBON, RUBON, TOMPON, COUTEAU |
| hygiene / entretien / droguerie | 15 | Charges externes (9), Epicerie (5), Restaurant (1) | 607 (5), 6068 (4), 6063 (2) | 52.74 | rejeter | garder en validation humaine | 1L Javel Classic double action, 1,25L Fleur de Muguet Nettoyant Surfaces, 1,25L Frais Nettoyant Surfaces, 1,25L Jasmin Nettoyant Surfaces, 1,25L Muguet Nettoyant Surfaces |
| recharges telephoniques | 9 | Epicerie (9) | 607 (9) | 52.94 | rejeter | ajouter regle metier | Recharge SFR La Carte llimitee 19,99€, Recharge SYMA 5£, Recharge LEBARA Bonus Temps 10€, Recharge LEBARA Nationale Doublée 10£, Recharge LYCAMOBILE 10€ |
| carburant / gazole / lavage | 1 | Epicerie (1) | 607 (1) | 59.53 | rejeter | enrichir base JSON | 54 Lavages (2.97L) Lessive Laine |
| materiel boucherie / coutellerie | 1 | BTP (1) | 6063 (1) | 58.53 | rejeter | ajouter synonymes | PLATOIR LAME INOX 28X12 CM MONDELIN |
| telecom / forfaits / bbox / b&you | 1 | Epicerie (1) | 607 (1) | 75.00 | rejeter | ajouter regle metier | Recharge SYMACOM FORFAIT BLOQUE |

## Conclusion courte

- Le moteur s'est ameliore sur la prudence: il garde moins de faux candidats en `validation_humaine` et rejette plus franchement les lignes faibles.
- Ce qui reste faible: les boissons/produits d'epicerie, les recharges telephoniques revendues en magasin, et les libelles atelier/carrosserie tres abbreviés.
- Familles a enrichir en priorite: `produits METRO / alimentation generale`, `recharges telephoniques`, puis `BTP / peinture / mastic / diluant / filtre / moteur / plaquette`.
- Regles metier a ajouter ensuite: filtrage des lignes non comptables, boost `Epicerie -> 607` pour boissons/recharges, et dictionnaire de synonymes OCR pour atelier/carrosserie.

