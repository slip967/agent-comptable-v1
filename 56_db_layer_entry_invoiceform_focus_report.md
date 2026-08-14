# Focus DB Layer `entry` / `invoice_form`

Date: 2026-05-05

Objectif: verifier s'il reste du gisement exploitable directement depuis la couche
DB `invoice_form` + `entry` pour enrichir encore `boucherie`, `transport` et `btp`.

## Constat global

### Boucherie

- Partitions retenues: `5`
- Partitions principales:
  - `fr_bd_837602275`
  - `fr_bd_832065999`
  - `fr_bd_828612630`
  - `fr_bd_931589238`
  - `fr_bd_519665103`
- Couverture DB:
  - `invoice_form_copied` important
  - `entry_copied` present et riche sur plusieurs partitions

Conclusion:
`boucherie` reste le metier le plus exploitable dans la couche DB, car on a encore
beaucoup de `article_source` produits coherents et un support `entry` reel.

### Transport

- Partitions retenues: `10`
- Exemple de partitions:
  - `fr_bd_839181104`
  - `fr_bd_888020088`
  - `fr_bd_831060876`
- Couverture DB:
  - `invoice_form_copied` present
  - `entry_copied` = `0` sur les partitions retenues

Conclusion:
le stock restant dans `transport` vient surtout de `invoice_form`, avec beaucoup
de telecom, abonnements, options, box, communications ou bruit OCR.
Le gisement produit propre devient faible.

### BTP

- Partitions retenues: `9`
- Exemple de partitions:
  - `fr_bd_903252617`
  - `fr_bd_842785719`
  - `fr_bd_844858571`
- Couverture DB:
  - `invoice_form_copied` present
  - `entry_copied` = `0` sur les partitions retenues

Conclusion:
le stock restant dans `btp` vient surtout de `invoice_form`, avec un melange
de vraies fournitures chantier et de prestations / travaux / libelles techniques.
Le gisement encore injectable existe, mais il est plus faible que `boucherie`.

## Decision de cette passe

- `boucherie`: oui, nouvelle vague d'ajout depuis la couche DB
- `transport`: pas d'ajout produit automatique supplementaire sur cette passe
- `btp`: pas d'ajout produit automatique supplementaire sur cette passe

## Pourquoi

- `boucherie` conserve encore un stock riche et frequent de libelles produits
- `transport` est presque epuise cote vrais produits; le reste est surtout telecom ou service
- `btp` garde encore un peu de stock, mais plus ambigu et moins frequent que `boucherie`
