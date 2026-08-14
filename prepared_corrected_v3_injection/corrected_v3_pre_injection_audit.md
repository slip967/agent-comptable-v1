# Audit Corrected V3 Before Injection

## Controle global

- `8` fichiers JSON produits controles
- `0` fichier manquant
- `0` `a_valider` dans toutes les bases
- `0` doublon detecte par `article_source` normalise
- `0` doublon detecte par `article_canonique`
- `0` item sans `compte_comptable`

## Volumes

- `boucherie`: `212`
- `boulangerie`: `200`
- `btp`: `163`
- `epicerie`: `444`
- `restaurant`: `219`
- `transport`: `134`
- `vtc`: `295`
- `charges_externes`: `512`

## Points rassurants

- Les structures JSON sont compatibles avec le builder d'import.
- Les `meta` sont presentes.
- Les `items` sont exploitables directement par `22_import_product_base_instances.py`.
- Le `dry-run` d'import est bon avec `2179` docs prets.

## Points de vigilance

### BTP

Quelques lignes ressemblent encore a des prestations plus qu'a de vrais produits :
- `COULAGE PARKING S/SOL`
- `COULAGE PLANCHER FORFAIT`
- `FORFAIT COULAGE DALLAGE Finition helicoptere`
- `M.A.D Pompe Beton (FORFAIT)`
- `PARKING Coulage Radier`

### Transport

Quelques comptes / libelles meritent un controle :
- `Gazole`, `GAZOLE Carburant`, `Carburant GO (Gazole)`, `GO (Gazole)`, `Gazole Excellium`, `Gazole Premier`
  note : ils sont en `6061`, ce qui parait discutable pour du carburant
- `PATE POUR FREINS`
  note : compte `626` suspect pour un produit transport

### VTC

C'est la base la plus sensible avant injection. On retrouve encore beaucoup de lignes qui ressemblent a :
- prestations atelier / carrosserie
- maintenance / revision
- telecom / box / tv
- forfaits

Exemples :
- `Visite technique periodique`
- `Chaines de tele payantes - FREEBOX TV Bouquet Maghreb`
- `Bloc optique avant droit remplacer`
- `Deposer, poser completement le pare-chocs avant`
- `Peindre aile avant droite niveau 1-M MET/UNI (peinture deux couches)`
- `FORFAIT1 000 KM -ADV750N -2022`

### Epicerie

La base est globalement meilleure, mais quelques lignes paraissent hors coeur produit :
- lessives / adoucissants
- quelques lignes services ou telecom deja mentionnees dans le resume v3

Note :
- certains faux positifs viennent d'une simple heuristique texte
- exemple : `AUBERGINE ...` remonte a cause de `uber` contenu dans le mot, donc ce n'est pas un vrai probleme

## Recommandation

### Injection prudente recommandee

Lot tres correct pour injection :
- `boucherie`
- `boulangerie`
- `restaurant`

Lot injectable avec reserve :
- `btp`
- `transport`

Lot a relire avant injection si on veut rester strict metier :
- `vtc`
- `epicerie`

## Conclusion

Si l'objectif est d'injecter rapidement sans trop de risque :
- injecter d'abord `boucherie`, `boulangerie`, `restaurant`, `btp`, `transport`, `charges_externes`
- garder `vtc` et `epicerie` pour une passe de validation complementaire
