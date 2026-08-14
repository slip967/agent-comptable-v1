# Controle Metier Final

Date: 2026-04-29

## Synthese

- Recette automatisee: `26/26` tests en `OK_auto`
- Verdict metier global: `lot valide`
- Reserve bloquante: `aucune`
- Reserve non bloquante restante: `0`

## Cas valides sans reserve

### Boucherie

- `PILON DE POULET HALAL UE`
- `FOIE DE VEAU`
- `BAVETTE ALOYAU BLANC BLEU BELGE`

### Restaurant

- `Tiramisu Choco-nut`
- `50 COUV BTE SALADE KRAFT GM`
- `HUILE DE TOURNESOL BINGOIL 1L`
- `COCACOLA BOITE SLIM 33CL`

### Transport

- `Gazole`
- `ADblue`

### Boulangerie

- `FARINE LABEL ROUGE L EMOTION 100 % IDF SAC 25 KG`
- `LEVURE LEVAMAX ECOPACK (30x500G) 15 KG`
- `OEUF COQUILLE TEINTE GROS 63/73 CT 360`
- `BEURRE GD TOURAGE FLECHARD CT 5X2KG`

### BTP

- `Beton pompe`
- `COULAGE PLANCHER`
- `Ingredients Peinture`
- `Tuyaux`

### Charges externes

- `Livraison`
- `Frais de livraison`
- `Frais de gestion`
- `Commission Deliveroo`
- `Fourniture d'electricite`
- `Acrobat Pro`
- `AGIOS - AGIOS`
- `Nettoyage en cours et en fin de chantier. Nettoyage fin de chantier et mise en decharge de dechets du chantier.`
- `Forfait Client B&You 260Go 5G`

## Corrections appliquees pendant la cloture

### Nettoyage transport selon doctrine PDF

- les lignes telecom/service ont ete sorties de la base active `transport`
- elles ont ete orientees vers `charges_externes`
- cela inclut notamment:
  - `Forfait Client B&You 260Go 5G`
  - `Communications vers l'international`

### Normalisation ciblee des comptes

- `ADblue`: `60620000 -> 6062`
- `Livraison`: `622600 -> 6226`
- `Acrobat Pro`: `606100 -> 6061`
- `Mise a disposition`: `606200 -> 6062`
- `SURFAQUARTZ GRIS NATUREL`: `60610000 -> 6061`

### Corrections deja effectuees avant cette passe

- `Ingredients Peinture`:
  - compte ajoute: `6068`
  - statut apres correction: `OK_auto`

- Runner de recette:
  - correction de lecture de la bonne source de decision quand un test metier retombe cote `charges_externes`

- Logique d'integration:
  - correction de la regle `boisson != emballage`

- Base restaurant locale:
  - `COCACOLA BOITE SLIM 33CL` corrige en `matiere_premiere`
  - `fournisseur_type` corrige vers `grossiste alimentaire`

## Conclusion

Le lot peut etre considere comme `metierement valide` pour la V1.

A ce stade, il n'y a plus de reserve metier ouverte dans la recette ciblee.
