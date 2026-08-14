# Provenance A Valider BTP / Transport

Ce rapport recolle les lignes `a_valider` avec leur meilleure provenance locale disponible.

Niveaux de provenance utilises :
- `candidate pack` : nb de factures, nb d'occurrences, partitions
- `invoice sample` : echantillon d'`invoice_id` quand retrouve localement
- `notes` : fallback quand la ligne a ete promue plus tard vers `a_valider`

## BTP

- base: `base_produits_btp_v1.json`
- lignes a_valider: `45`
- matches candidate pack: `45`
- matches invoice sample: `0`
- counts recuperes depuis notes: `45`

### 1. `Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `4`
- line_occurrences: `4`
- partitions: `['fr_bd_792041840']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=4, line_occurrences=4) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 2. `Amenée-repli de l'atelier de forage des micropieux`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 3. `Dépose et repose cheminement de cables`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 4. `Dépose et repose de luminaires au dessus des acces`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 5. `Dépose et repose de luminaires plafond des porches`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 6. `Dépose et repose des anémométres pour store`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 7. `ECO PARTICIPATION PMCB BPE`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_903252617']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 8. `Fo et pose d'un coffret d'installation électrique provisoire`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 9. `Fo et pose de cable 3G2,5`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 10. `Fo et pose de cäble 3G6`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 11. `Fo et pose de cäble 5G16`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 12. `Fo et pose de fourreau diamétre 25`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 13. `Fo et pose de fourreau diamétre 40`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 14. `Réalisation de la Mission G3`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 15. `Réalisation de réseaux enterrés pour passage de câbles`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_792041840']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 16. `Travaux de sous-traitance - électricité`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6041`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 17. `Travaux exécutés - Sous-traitance`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `604`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 18. `Casque de chantier Océanic 2 RB40 taille 53-61 cm blanc`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 19. `Démontage et remontage de filins acier inox`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 20. `Dépose / repose des fixations des filins acier inox`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 21. `Implantation des micropieux`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 22. `Installation de chantier`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 23. `Jugulaire sans mentonniére pour casque SC5101 et SC5101A3`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_844858571']`
- sample_account: `60620000`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 24. `Luminaires au dessus des accés - Suivant CCTP`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6065`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 25. `Luminaires plafond des porches - Suivant CCTP`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6065`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 26. `Montage d'échafaudage - CHANTIER 5 RUE DE L'ABBE DELHOTEL 55600 AVIOTH`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_823981568']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 27. `PLIAGE GALVA 15/10 EXCEDENTAIRE (PATTES ANTI RELEVE DETAIL 3 Long : 3000 Dev : 227`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 28. `PLIAGE GALVA 15/10 EXCEDENTAIRE 30X30X30 Long : 4000 Dev : 90`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 29. `PLIAGE GALVA 15/10 EXCEDENTAIRE OMEGA Long : 4000 Dev : 147`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 30. `PN CHANTIER INTERDIT 330X200 621209`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6068`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 31. `Plaque de platre BA13 Placoflam A2 2,5x1,2m R=0,04 m2.k/w`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 32. `Prestation de sous traitance`

- selection_source: `raise_to_200_btp_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_903252617']`
- sample_account: `604`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Ajout cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv.`

### 33. `Essai de contrôle sur un micropieu de l'ouvrage selon EC7`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `4`
- line_occurrences: `4`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=4, line_occurrences=4) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 34. `Amenée-repli de l'atelier de l'injection`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 35. `Electricité`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 36. `Fo et pose de grosse boites de dérivation`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 37. `Jour de location`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_844858571']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 38. `TA-E 80X60 W0 GOUL DISTRI AU METRE`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_844858571']`
- sample_account: `60610000`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=3, line_occurrences=3) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 39. `Anémométre pour store - suivant CCTP`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `3`
- partitions: `['fr_bd_842785719']`
- sample_account: `6068`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 40. `Ascenseur`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `604`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 41. `BAST SAP/EPI TRCL2 63X160 3M00`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 42. `BOB. PROTECT. ULTIBAT 75M.`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 43. `Campagne de test d'arrachement`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6062`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 44. `CONTRE PLAQUE FILME PLUS 15MM 250X125X15MM`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_842785719']`
- sample_account: `6061`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

### 45. `CROISILLONS EN T 3MM 250 PIECES`

- selection_source: `top_up_target_200_btp_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_509118329']`
- sample_account: `607`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel btp (invoice_count=2, line_occurrences=2) | Top-up final cible 200 depuis candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

## TRANSPORT

- base: `base_produits_transport_v1.json`
- lignes a_valider: `73`
- matches candidate pack: `21`
- matches invoice sample: `72`
- counts recuperes depuis notes: `73`

### 1. `Effectuer un essai sur route`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `6`
- line_occurrences: `6`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=255, line_occurrences=255) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 2. `Effectuer un test rapide`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `6`
- line_occurrences: `6`
- partitions: `['fr_bd_839181104']`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:4f21d748-62b5-4e21-98fc-3dfa53b23900 | fr_bd_839181104:def27868-2a83-4a65-8752-0f85199cf04c | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=255, line_occurrences=255) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 3. `Garnitures de frein essieu avant`

- article_source_original: `Déposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu avant (Roues completes démontées) Sur véh. avec étrier fixe`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `254`
- line_occurrences: `254`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:4f21d748-62b5-4e21-98fc-3dfa53b23900 | fr_bd_839181104:def27868-2a83-4a65-8752-0f85199cf04c`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=254, line_occurrences=254) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 4. `Bloc optique avant droit remplacer`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 5. `Bouclier avant complet`

- article_source_original: `Bouclier avant complet desassembler, assembler, selon constat rempi. piece(s). (pare-chocs depose)`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 6. `Deposer, poser completement le pare-chocs avant`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f | fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 7. `Inserts décoratifs carrosserie`

- article_source_original: `Deposer, poser les inserts decoratifs et les pieces rapportees, concerne pour remise en etat. carrosserie/ mise en peinture`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 8. `Déposer, poser 2 blocs optiques avant`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 9. `Effectuer la maintenance A avec pack plus`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:87f4cf8e-677e-4507-ad7d-61c7f2da0367 | fr_bd_839181104:c0371fe7-cfc4-4a5a-9216-2790df432ff4 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335 | fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 10. `Ingrédients Peinture`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `4`
- line_occurrences: `4`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f | fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 11. `Peindre aile avant droite niveau 1-M MET/UNI (peinture deux couches)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 12. `Peindre la porte avant droite niveau 1-M MET/UNI (peinture deux couches)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 13. `Pose kit réparation optique avant gauche`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 14. `Garnitures et disques de frein essieu avant`

- article_source_original: `Remplacer les garnitures de frein et les disques de frein de l'essieu avant (roues complètes démontées) sur véh. avec étrier fixe`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335 | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 15. `Revêtement du bouclier avant appliquer peinture finition et marier teintes par pistolage véh. avec pack Carrosserie AMG`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `253`
- line_occurrences: `253`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=253, line_occurrences=253) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 16. `REVISION A7 VIDANGE MOTEUR FILTRE`

- article_source_original: `CC: REVISION A7 Maintenance VIDANGE MOTEUR FILTRE`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:81090a41-8165-4d15-9a52-344fac370798 | fr_bd_824332985:f8930368-2f91-4033-bfc8-d5879b0d7c00`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 17. `Demonter, monter 4 roues completes`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:4f21d748-62b5-4e21-98fc-3dfa53b23900 | fr_bd_839181104:def27868-2a83-4a65-8752-0f85199cf04c`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 18. `Deposer, poser, remplacer selon besoin la pompe a liquide de refroidissement (Moteur depose)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 19. `Habillages compartiment moteur`

- article_source_original: `Deposer, poser, remplacer selon besoin tous les habillages du compartiment moteur et toutes les garnitures sur soubassement`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 20. `Garnitures de frein essieu arrière`

- article_source_original: `Deposer, poser, remplacer selon constat 4 garnitures de frein de l'essieu arriere (Roues completes demontees)`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4 | fr_bd_824332985:ba9ad8e8-9481-4102-a517-de5d6ea216f6`
- invoice_sample_partitions: `['fr_bd_839181104', 'fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 21. `Direction assistee remplacer`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 22. `Effectuer la dépose de roue pour la roue complete`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 23. `Effectuer la maintenance B avec pack plus`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4 | fr_bd_839181104:5ad9fe47-8a27-404b-926d-96c008c0fe69 | fr_bd_839181104:63c4f300-dc0b-4a95-a4df-d21295501ca7`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 24. `Maintenance A avec pack plus`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:89da0a20-1bae-474e-86f1-cfd078cdd5f1 | fr_bd_824332985:b5cd6dd6-89a5-42f2-91d0-7713dcdb2f11`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 25. `Paliers (tous) pour suspension du moteur remplacer (Moteur depose)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 26. `Peindre l'aile avant gauche niveau 1-M MET/UNI (peinture deux couches)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 27. `Programmer et coder le calculateur (Apres test rapide)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137 | fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 28. `Regler le projecteur a LED`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:3524efe6-e397-4f33-869b-3d6795fc8137`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 29. `Remplacement(s): huile moteur, filtre a huile moteur, filtre ä huile d'embrayage`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:78a1fca5-03d7-4971-bdcc-fa28b3beae04 | fr_bd_839181104:f3f943e3-18e5-4d9f-a5da-eeb7d8187eee`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 30. `Jambe de suspension gauche`

- article_source_original: `Remplacer la jambe de suspension gauche de l'essieu avant sur veh. a suspension electrohydrauligue`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 31. `Remplacer le bloc optique avant gauche`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 32. `Remplacer le liquide de refroidissement avec antigel, controler l'etancheite`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 33. `Revetement du bouclier avant appliquer peinture finition et marier teintes par pistolage`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 34. `Supplement a la maintenance remplacer le filtre a poussieres`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:81090a41-8165-4d15-9a52-344fac370798 | fr_bd_824332985:f8930368-2f91-4033-bfc8-d5879b0d7c00`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 35. `Supplement a la maintenance: Vous allez recevoir un email 5 Etoiles`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:81090a41-8165-4d15-9a52-344fac370798 | fr_bd_824332985:f8930368-2f91-4033-bfc8-d5879b0d7c00`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 36. `Supplement a la maintenance: remplacer la cartouche de filtre a air`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:81090a41-8165-4d15-9a52-344fac370798 | fr_bd_824332985:f8930368-2f91-4033-bfc8-d5879b0d7c00`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 37. `Supplément a la maintenance: Facturé selon temps passé`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:5ad9fe47-8a27-404b-926d-96c008c0fe69 | fr_bd_839181104:63c4f300-dc0b-4a95-a4df-d21295501ca7`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 38. `Supplément ä la maintenance`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:4f21d748-62b5-4e21-98fc-3dfa53b23900 | fr_bd_839181104:def27868-2a83-4a65-8752-0f85199cf04c`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 39. `demonter, monter 2 roues`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24dee091-5e2c-42d7-bcf5-633036f27d0e | fr_bd_839181104:baa533f1-ba21-4f51-a27d-1847e34beaf4`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 40. `B: remplacer le liquide de frein`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `615`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:edc2d1b0-8181-4c10-b2fa-555103bc0347`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 41. `B: remplacer le liquide de frein - Supplément a la maintenance`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:197c5231-d241-415e-a96c-b058a5661bf0`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 42. `Deposer, poser, selon constat 4 garnitures de frein de l'essieu arriere (Roues completes demontees)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:ab813727-dd49-4799-bc5c-529683c0e6ad`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 43. `Démonter, monter 2 roues complètes`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335 | fr_bd_824332985:ba9ad8e8-9481-4102-a517-de5d6ea216f6`
- invoice_sample_partitions: `['fr_bd_839181104', 'fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 44. `Effectuer la maintenance avec pack plus`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:edc2d1b0-8181-4c10-b2fa-555103bc0347`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 45. `Ingrédient peinture`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_831060876:35a45ee1-867a-4fe8-bbcd-5af400b08c63`
- invoice_sample_partitions: `['fr_bd_831060876']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 46. `LUBRIFIANT TOIT OUVRANT(PDP)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 47. `Main d'oeuvre atelier`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `615`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:2b913b34-bb3a-42b5-aeb8-6aba064a70f6`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 48. `Pack Remote - Commande à distance vitres/toit ouvrant 360 jours, Verrouillage et déverrouillage à distance des portes 360 jours, Alerte voiturier 360 jours, Personnalisation 360 jours, Emplacement du véhicule 360 jours, Géolocalisation du véhicule 360 jours, Localiser le véhicule 360 jours, Localisation du véhicule 360 jours. Chassis: WDD2130041A652450. Ce produit est valable un an à partir de la date d'activation`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6068`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:d1888ec4-8710-4c67-9676-25bf9b3b61ba`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 49. `Regler le projecteur a LED (Apres test rapide)`

- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json.`

### 50. `Garnitures et disques de frein essieu arrière`

- article_source_original: `Remplacer les garnitures de frein et les disques de frein de l'essieu arrière (roues complètes démontées)`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 51. `Réparation carrosserie avant droit`

- article_source_original: `Réparation selon rapport d'expertise - Travaux effectués: Contrôle des trains avant et arrière, Remplacement, peinture (Aile avant droite, Capot moteur avant, Charnière droite de capot, Pare-chocs avant, Support avant d'aile avant droit, Pare boue avant droit partie avant, Pare boue avant droit partie arrière, Tirant de bras de suspension avant droit, Bras inférieur de suspension avant, Protection sous moteur, Boîtier de direction, Equilibreur droit de capot, Jante avant droite, Porte moyeu avant droit, Bras supérieur de suspension, Amortisseur avant droit et avant gauche, Pneumatique avant droit, Projecteur droit, Support de capteur latéral droit d'aide au stationnement, Joint de porte avant droite, Rétroviseur droit, Répétiteur de rétroviseur), Réparation, peinture (Haut de caisse droit, Elargisseur de bas de caisse, Porte avant droite, Doublure de passage de roue avant droit)`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_831060876:35a45ee1-867a-4fe8-bbcd-5af400b08c63`
- invoice_sample_partitions: `['fr_bd_831060876']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 52. `Vidange boite de vitesses automatique`

- article_source_original: `Supplément a la maintenance B: effectuer la vidange d'huile dans la boite de vitesses automatique Sur véh. avec boite de vitesses 725.0`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 53. `Nettoyage mécanisme toit ouvrant`

- article_source_original: `Supplément a la maintenance: Nettoyer, graisser le mécanisme de toit ouvrant panoramique`
- selection_source: `raise_to_200_transport_pending_v1`
- candidate_pack_found: `False`
- invoice_count: `251`
- line_occurrences: `251`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=251, line_occurrences=251) | Ajout cible 200 depuis base_produits_vtc_v1.json. | article_source_cleanup_v1`

### 54. `Visite technique périodique`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `256`
- line_occurrences: `256`
- partitions: `[]`
- sample_account: `6068`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:6a503dac-2e59-46d4-aa9d-7877a728737e | fr_bd_839181104:adc6998b-5b71-4743-85ab-0bccb90586d3 | fr_bd_839181104:c7b924bd-e5b2-4838-a1c2-ebf7225c1bb5 | fr_bd_839181104:cbadadea-d523-4c9f-9610-aa3c3109d220 | fr_bd_839181104:dc554816-330a-4b97-a482-d7df1bcdc9b6`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=256, line_occurrences=256) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 55. `NCS, MO-S`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `254`
- line_occurrences: `254`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:24849255-432f-4b88-bf5a-c8540cf41182 | fr_bd_839181104:7f363eb2-124a-430f-b890-c1d278504d01 | fr_bd_839181104:885da885-e645-497a-adc7-59af690140d2 | fr_bd_839181104:eaf922fb-9174-46de-9069-b1e1442fdce2`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=254, line_occurrences=254) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 56. `RENOV.ULTIME MEGUIARS 473 ML (PROMO)`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:289c50d3-842c-4f9d-b26e-32116eeaf846 | fr_bd_839181104:6a714ce1-c3b9-492c-9198-75b818c50fa5 | fr_bd_839181104:6b863ae7-0217-4324-847a-bc3108eac22e | fr_bd_839181104:fe84cafe-bf3b-424f-986f-ff8d5758b545`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=254, line_occurrences=254) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 57. `ULTIM.BRILLANCE MEGUIARS 709ML (PROMO)`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `6063`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:289c50d3-842c-4f9d-b26e-32116eeaf846 | fr_bd_839181104:6a714ce1-c3b9-492c-9198-75b818c50fa5 | fr_bd_839181104:6b863ae7-0217-4324-847a-bc3108eac22e | fr_bd_839181104:fe84cafe-bf3b-424f-986f-ff8d5758b545`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=254, line_occurrences=254) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 58. `VIS DE FERMETURE`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `4`
- line_occurrences: `4`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:5ad9fe47-8a27-404b-926d-96c008c0fe69 | fr_bd_839181104:63c4f300-dc0b-4a95-a4df-d21295501ca7 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=254, line_occurrences=254) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 59. `022 H.MOT 229-52 vrac 5W30`

- article_source_original: `022 H.MOT 229-52 v rac 5W30`
- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:5ad9fe47-8a27-404b-926d-96c008c0fe69 | fr_bd_839181104:63c4f300-dc0b-4a95-a4df-d21295501ca7 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json | article_source_cleanup_v1`

### 60. `022 H.MOT 229-52 vrac 5W30`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 61. `120186/CONSOLE`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:231e61cc-2a4b-48fa-ab40-b84fa9d78cc6 | fr_bd_839181104:f256b17b-2cc4-4024-a519-4e0db6ba770f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 62. `Cloison sous aile avant gauche remplacer`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `60620000`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9c2b78bd-6554-4a2e-921e-b318065ec19c | fr_bd_839181104:9de9581f-69fb-4d78-8621-22fa33e0b332 | fr_bd_839181104:44ae349c-7513-4ade-8c00-e6123ce5a404`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 63. `H.MOT 229.5 1L OW40`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6063`
- invoice_sample_found: `False`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 64. `JEU DE CART. FILTR. CARB`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `615`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_824332985:89da0a20-1bae-474e-86f1-cfd078cdd5f1 | fr_bd_824332985:b5cd6dd6-89a5-42f2-91d0-7713dcdb2f11`
- invoice_sample_partitions: `['fr_bd_824332985']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 65. `Lavage express`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:78a1fca5-03d7-4971-bdcc-fa28b3beae04 | fr_bd_839181104:f3f943e3-18e5-4d9f-a5da-eeb7d8187eee`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 66. `Polish`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:9d066b06-45a2-4e30-82fe-108ccdc4d229 | fr_bd_839181104:da068424-20d5-4fc2-a5de-454d875f45c3`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 67. `RAIL DE RECOUVREMENT`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:c78279c1-937c-4e75-aac2-b73fceaab4be | fr_bd_839181104:e1704d1f-bb69-45ad-8363-e9dd9463340b`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 68. `RESSORT`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:4280f625-680b-4620-bc39-100e3d0a46ad | fr_bd_839181104:6b1a83b3-7662-413a-a55f-592b9cef8c6f`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 69. `Remplacer la pile de la clé-émetteur 022 PILE 2032`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:4f21d748-62b5-4e21-98fc-3dfa53b23900 | fr_bd_839181104:def27868-2a83-4a65-8752-0f85199cf04c`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 70. `TUBE DE GUIDAGE`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 71. `TUBE DE TROP-PLEIN`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `2`
- line_occurrences: `2`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 72. `VIS`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `False`
- invoice_count: `252`
- line_occurrences: `252`
- partitions: `[]`
- sample_account: `6062`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`

### 73. `VIS 6 PANS AVEC BRIDE`

- selection_source: `top_up_target_200_transport_v1`
- candidate_pack_found: `True`
- invoice_count: `3`
- line_occurrences: `3`
- partitions: `['fr_bd_839181104']`
- sample_account: `606200`
- invoice_sample_found: `True`
- invoice_ids_sample: `fr_bd_839181104:2ec3664c-792e-438a-8699-fff8e46292e9 | fr_bd_839181104:dd776d5a-19e4-4947-854b-e713b9dbb25f | fr_bd_839181104:f1b3dd25-637b-4cde-956f-23e1dcfad510 | fr_bd_839181104:fc642081-1c3e-41ac-9274-b7cc6536c335`
- invoice_sample_partitions: `['fr_bd_839181104']`
- notes: `Integre depuis triage manuel transport (invoice_count=252, line_occurrences=252) | Top-up final cible 200 depuis base_produits_vtc_v1.json`
