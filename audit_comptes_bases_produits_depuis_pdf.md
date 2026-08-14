# Audit Comptes Bases Produits Depuis PDF

Date: 2026-04-29

Referentiel utilise: [reference_comptes_produits_metier_depuis_pdf.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/reference_comptes_produits_metier_depuis_pdf.json)

## Conclusion

Les bases produits par metier restent coherentes avec la doctrine issue du PDF:

- les vraies bases produits restent en classe `60`
- les lignes de type service ont ete sorties de la base active `transport`
- les quelques comptes paddes ont ete normalises vers leur forme canonique

La regle retenue est donc confirmee:

- `base produit metier = comptes 60...`
- `prestations / abonnements / commissions / frais = hors base produit metier`

## Lecture metier du PDF appliquee au projet

### Ce que le PDF confirme

- page 1:
  les achats de biens restent dans les comptes `60...`
- page 2:
  les prestations de services relevent plutot des classes `61/62`
- page 3:
  les frais de port et accessoires doivent etre traites a part du vrai produit metier
- page 5:
  les emballages consignes suivent un flux comptable specifique

### Consequence pour le projet

- `boucherie`, `restaurant`, `boulangerie`, `transport`, `btp`:
  conserver les vrais produits d'exploitation en classe `60`
- `telecom`, `abonnements`, `commissions`, `livraison`, `frais`, `entretien`, `nettoyage`:
  les orienter vers `charges_externes` si le libelle decrit un service

## Actions realisees apres audit

### Reclassement transport selon la doctrine PDF

Le script [47_reclass_transport_telecom_services.py](/C:/Users/Dell/Downloads/scripts-master/scripts-master/47_reclass_transport_telecom_services.py:1) a ete applique.

Resultat:

- `15` lignes de type telecom/service ont ete sorties de la base active `transport`
- elles ont ete basculees vers `a_valider` dans la base transport
- elles ont ete ajoutees ou rapprochees dans `charges_externes`

Exemples:

- `Forfait Client B&You 260Go 5G`
- `Communications vers l'international`
- `Option multi-SIM Internet`
- `Bbox - location equipement (...)`

### Normalisation ciblee des comptes paddes

Le script [48_normalize_selected_accounts.py](/C:/Users/Dell/Downloads/scripts-master/scripts-master/48_normalize_selected_accounts.py:1) a ete applique.

Normalisations faites:

- `60620000 -> 6062`
- `606200 -> 6062`
- `60610000 -> 6061`
- `606100 -> 6061`
- `622600 -> 6226`

Exemples touches:

- `ADblue` -> `6062`
- `Mise a disposition` -> `6062`
- `SURFAQUARTZ GRIS NATUREL` -> `6061`
- `Livraison` -> `6226`
- `Acrobat Pro` -> `6061`

## Audit des bases actuelles

### Boucherie

- Fichier: [base_produits_boucherie_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_produits_boucherie_v1.json)
- Resultat:
  - `71` items actifs
  - `0` item hors classe `60`
  - `0` compte padde restant
- Verdict: `OK`

### Restaurant

- Fichier: [base_produits_restaurant_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_produits_restaurant_v1.json)
- Resultat:
  - `97` items actifs
  - `0` item hors classe `60`
  - `0` compte padde restant
- Verdict: `OK`

### Transport

- Fichier: [base_produits_transport_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_produits_transport_v1.json)
- Resultat:
  - `13` items actifs
  - `15` lignes sorties de la base active et marquees `a_valider`
  - `0` item hors classe `60`
  - `0` compte padde restant sur les lignes normalisees
- Verdict: `OK apres reclassement PDF`

### Boulangerie

- Fichier: [base_produits_boulangerie_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_produits_boulangerie_v1.json)
- Resultat:
  - `48` items actifs
  - `0` item hors classe `60`
  - `0` compte padde restant
- Verdict: `OK`

### BTP

- Fichier: [base_produits_btp_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_produits_btp_v1.json)
- Resultat:
  - `21` items actifs
  - `0` item hors classe `60`
  - `0` compte padde restant apres normalisation
- Verdict: `OK`

## Impact sur charges externes

Le nettoyage PDF a aussi consolide [base_charges_externes_v1.json](/C:/Users/Dell/Downloads/scripts-master/scripts-master/base_charges_externes_v1.json):

- les telecoms / abonnements issus de `transport` y sont maintenant ranges explicitement
- les comptes `Livraison` et `Acrobat Pro` sont normalises
- la separation `produits metier` vs `services` est maintenant plus nette

## Verdict final

Oui, le PDF peut servir de base doctrinale pour les comptes comptables des bases produits par metier.

Dans l'etat actuel du projet, il confirme que:

- la strategie en classe `60` est la bonne pour les bases produits
- les services doivent sortir des bases produits
- le sous-ensemble `transport` est maintenant nettoye conformement a cette doctrine
- les comptes paddes les plus visibles ont ete remis dans une forme canonique
