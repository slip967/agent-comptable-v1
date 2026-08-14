# Verification rapide avant injection

## Methode

Chaque ligne a ete verifiee sur 4 points :

- appartenance a la bonne base
- coherence du `compte_comptable`
- proprete du libelle
- coherence categorie / sous-categorie

Verdicts utilises :

- `OK`
- `A surveiller`
- `A corriger`

## Transport

| Article source | Compte | Verdict | Commentaire |
|---|---:|---|---|
| `Gazole` | `6063` | `OK` | Produit transport clair, compte carburant coherent. |
| `GAZOLE Carburant` | `6063` | `OK` | Variante de carburant, compte corrige correctement. |
| `Carburant GO (Gazole)` | `6063` | `OK` | Libelle metier coherent, bon rattachement. |
| `GO (Gazole)` | `6063` | `OK` | Variante courte acceptable dans une base reference. |
| `Gazole Excellium` | `6063` | `OK` | Carburant premium, compte coherent. |
| `Gazole Premier` | `6063` | `OK` | Carburant premium, compte coherent. |
| `ADblue` | `6063` | `OK` | Consommable exploitation vehicule, compte coherent. |
| `ADBLUE vrac` | `6063` | `OK` | Meme logique que `ADblue`, bonne famille. |
| `ADBLUE 10L (PDP)` | `6063` | `OK` | Consommable vehicule, libelle exploitable. |
| `AdBlue Pompe` | `6063` | `OK` | Consommable vehicule, bon rattachement transport. |
| `PATE POUR FREINS` | `6062` | `OK` | Petite fourniture / consommable atelier vehicule, correction utile. |
| `PATE POUR FREINS (PDP)` | `6062` | `OK` | Variante propre, meme doctrine que ci-dessus. |

### Conclusion transport

- Les lignes carburant / gazole / adblue sont maintenant coherentes pour une injection stricte.
- Je n'ai pas retrouve dans ce lot strict de lignes telecom / forfait / bbox / maintenance atelier generique qui devraient sortir vers `charges_externes`.

## BTP

| Article source | Compte | Verdict | Commentaire |
|---|---:|---|---|
| `Palette HMFC ciments 95x115 cm` | `6063` | `OK` | Matiere / support logistique chantier coherent dans une base produit BTP. |
| `POUR PANNEAUX FIBRE CIMENT POUR SYSTEME UNI RIVET 11MM` | `6063` | `OK` | Fourniture technique chantier coherente. |
| `DISQUE DIAMASTER 160X3,2/2,40X20 Z4 COUPE PANNEAUX ETERNIT` | `6063` | `OK` | Consommable technique chantier pertinent. |
| `Brique lisse pleine rouge rieussequel 220 105 50 mm` | `6063` | `OK` | Materiau BTP clair. |
| `GRAVATS : Briques, terre, ciment, béton, pierres, sable...` | `6062` | `A surveiller` | Ligne exploitable, mais le libelle ressemble a une designation de benne / dechetterie plus qu'a un vrai produit standard. A garder seulement si ce cas existe souvent dans ton usage. |

### Conclusion BTP

- Les lignes de type `COULAGE ...`, `FORFAIT ...`, `PARKING ...`, `Pompe Beton ...` ont deja ete retirees du lot strict.
- Le noyau restant est globalement plus propre pour une injection produit.
- Seule la ligne `GRAVATS ...` merite encore une petite reserve metier.

## Verdict global

- `Transport` : `OK` pour injection dans ce lot strict.
- `BTP` : `OK` globalement, avec une reserve mineure sur quelques libelles tres operationnels comme `GRAVATS ...`.
- `VTC` et `epicerie` restent hors de ce lot strict, ce qui est la bonne decision pour l'instant.
