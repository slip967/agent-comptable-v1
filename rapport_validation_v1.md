# Rapport De Validation V1

Ce rapport synthetise le comportement du matcher V1 sur le jeu de tests issu des bases produits et charges externes.

## Synthese

- Lignes testees : `67`
- Taux de `auto_ok` : `100.0%`
- `auto_ok` : `67`
- `validation_humaine` : `0`
- `rejeter` : `0`
- Score de confiance moyen : `100.0`
- Score de confiance minimum : `100.0`

## Controle TVA

- `coherente` : `67`
- `a_verifier` : `0`
- `incoherente` : `0`

## Controle Metier

- `coherente` : `67`
- `a_verifier` : `0`
- `incoherente` : `0`

## Repartition Par Metier

| Metier | Lignes | auto_ok | validation_humaine | rejeter | Score moyen | Score min |
|---|---|---|---|---|---|---|
| Charges externes | 28 | 28 | 0 | 0 | 100.0 | 100.0 |
| Boulangerie | 25 | 25 | 0 | 0 | 100.0 | 100.0 |
| BTP | 9 | 9 | 0 | 0 | 100.0 | 100.0 |
| Boucherie | 2 | 2 | 0 | 0 | 100.0 | 100.0 |
| Restaurant | 2 | 2 | 0 | 0 | 100.0 | 100.0 |
| Transport | 1 | 1 | 0 | 0 | 100.0 | 100.0 |

## Nature Des Matchs

- Correspondance exacte avec le libelle source : `67` soit `100.0%`
- Correspondance normalisee avec le libelle source : `0`
- Correspondance normalisee avec le libelle canonique : `0`
- Correspondance fuzzy ou par mots cles : `0`
- Alertes detectees : `0`

## Repartition Des References

### Categories

| Categorie | Lignes |
|---|---|
| Exploitation metier | 39 |
| Charges externes | 28 |

### Sous Categories

| Sous categorie | Lignes |
|---|---|
| Matiere premiere | 30 |
| Frais de service | 19 |
| Consommables chantier | 6 |
| Locations | 5 |
| Charges generales | 3 |
| Emballage | 3 |
| Entretien / reparation | 1 |

### Comptes Comptables

| Compte | Lignes |
|---|---|
| 6227 | 13 |
| 6068 | 11 |
| 6061 | 10 |
| 60610000 | 8 |
| 6226 | 8 |
| 6062 | 3 |
| 6132 | 3 |
| 6011 | 2 |
| 606200 | 2 |
| 613 | 2 |
| 601 | 1 |
| 60225 | 1 |
| 606100 | 1 |
| 6152 | 1 |
| 6281 | 1 |

### Sous Profils Charges Externes

| Sous profil | Lignes |
|---|---|
| Cotisations professionnelles | 10 |
| Transport et logistique | 6 |
| Frais administratifs et bancaires | 4 |
| Loyers et charges locatives | 4 |
| Entretien et maintenance | 2 |
| Telecom et abonnements | 2 |

## Exemples De Matchs

| Metier | Article source | Match propose | Compte | Sous profil | TVA | Score |
|---|---|---|---|---|---|---|
| Boucherie | BASSE COTE BOEUF | BASSE COTE BOEUF | 6011 | - | 5.5 | 100.0 |
| Boulangerie | CANADIENNE D'OEUFS X180 | CANADIENNE D'OEUFS X180 | 601 | - | 5.5 | 100.0 |
| BTP | 1PX COLLE POUDRE INT MAX30X30CM GRIS25KG | 1PX COLLE POUDRE INT MAX30X30CM GRIS25KG | 6068 | - | 20.0 | 100.0 |
| Charges externes | ABONNEMENT TRIM. MOBITPE MOBILE du 01/04/25 au 30/06/25 | ABONNEMENT TRIM. MOBITPE MOBILE du 01/04/25 au 30/06/25 | 6226 | Telecom et abonnements | 20.0 | 100.0 |
| Restaurant | FILM ALIMENTAIRE 45CM X 300M EN BOITE DISTRIBUTRICE AVEC LAME | FILM ALIMENTAIRE 45CM X 300M EN BOITE DISTRIBUTRICE AVEC LAME | 606200 | - | 20.0 | 100.0 |
| Transport | Entree CTTE (Camionnette) | Entree CTTE (Camionnette) | 6068 | - | 20.0 | 100.0 |

## Cas A Revoir

- Nombre de lignes a revoir : `0`
- Detail CSV : `rapport_validation_v1_a_revoir.csv`

Aucun cas a revoir sur ce lot de validation.
