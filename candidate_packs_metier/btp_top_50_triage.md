# BTP Top 50 Triage

Source: `candidate_packs_metier/btp_top_500_cleaned_candidates.csv`

Objectif: première sélection manuelle des 50 premiers `article_source` nouveaux pour la base `btp`.

## A Garder

1. `Béton pompé`
2. `COFFRAGE, SCIAGE, PONCAGE.`
3. `Mise à disposition`
4. `COULAGE PLANCHER`
5. `SURFAQUARTZ GRIS NATUREL`
6. `COULAGE PLANCHER finition brut`
7. `Tuyaux`
8. `Béton pompé (en m3)`
9. `COURONNE.250MM.COREX GR 16Q 68`
10. `Ingrédients Peinture`
11. `Mise a disposition d'une Pompe Béton (FORFAIT)`
12. `COULAGE DALLAGE finition hélicoptére`

## A Revoir

1. `CUISSE POULET HALAL *10 KG BELGE`
   Raison: hors périmètre BTP.
2. `AILE POULET HALAL BLANC BELGE`
   Raison: hors périmètre BTP.
3. `PILON POULET HALAL VRAC BELGE`
   Raison: hors périmètre BTP.
4. `FILET POULET HALAL*10 KG Roumanie`
   Raison: hors périmètre BTP.
5. `FOIE VOLAILLE HALAL BELGE`
   Raison: hors périmètre BTP.
6. `FILET POULET HALAL*10 KG S/AT BELGE`
   Raison: hors périmètre BTP.
7. `ESCALOPE VOLAILLE MILANESE Halal ITALIEN`
   Raison: hors périmètre BTP.
8. `CORDON BLEU VOLAILLE HALAL 1000G S/AT`
   Raison: hors périmètre BTP.
9. `POULET Label Rouge HALAL`
   Raison: hors périmètre BTP.
10. `FILET DINDE HALAL Import`
    Raison: hors périmètre BTP.
11. `CUISSE POULET Label Rouge Halal Blanche`
    Raison: hors périmètre BTP.
12. `FILET DINDE HALAL *10 KG FRANCE`
    Raison: hors périmètre BTP.
13. `Gazole`
    Raison: à valider si tu veux intégrer le carburant chantier dans la base métier.
14. `Carburant GO`
    Raison: à valider si tu veux intégrer le carburant chantier dans la base métier.
15. `Carburant`
    Raison: à valider si tu veux intégrer le carburant chantier dans la base métier.
16. `DIESEL`
    Raison: à valider si tu veux intégrer le carburant chantier dans la base métier.
17. `POULET PAC HALAL 1200G`
    Raison: hors périmètre BTP.
18. `PILON POULET HALAL FRANCE`
    Raison: hors périmètre BTP.
19. `POULET PAC HALAL 1300G`
    Raison: hors périmètre BTP.
20. `Remise`
    Raison: pas un article.
21. `Utilisateur standard`
    Raison: hors périmètre base produits.
22. `CUISSE POULET DesOsse*10 KG BELGE`
    Raison: hors périmètre BTP.
23. `CUISSE DINDE HALAL`
    Raison: hors périmètre BTP.
24. `CUISSE POULET Label Rouge Halal JAUNE`
    Raison: hors périmètre BTP.
25. `Article non spécifié`
    Raison: inutilisable.
26. `COLLIER BASSE COTE - ORIGINE:BELGIQUE - VACHE BLANC BLEU BELGE`
    Raison: hors périmètre BTP.
27. `AGNEAU - ORIGINE:ROYAUME-UNI - AGNEAU MOINS DE 12 M - VIANDE HALLAL`
    Raison: hors périmètre BTP.
28. `CUISSE POULET HALAL *10 KG BELGE Origine:Belgique`
    Raison: hors périmètre BTP.
29. `Eco contribution`
    Raison: pas un produit métier BTP.
30. `Forfait 2h 100 Mo`
    Raison: hors périmètre base produits BTP.
31. `Offre Spéciale - Réduction sur la position 1`
    Raison: ligne commerciale, pas un article.
32. `Repas`
    Raison: hors périmètre.
33. `ECO-PART DEEE`
    Raison: à traiter à part, pas un article produit chantier.
34. `CUISSE POULET HALAL *10 KG BELGE Origine France N abattoir 89.069.001`
    Raison: hors périmètre BTP.
35. `FILET POULET HALAL * 10 KG S/AT BELGE Origine : Belgique`
    Raison: hors périmètre BTP.
36. `Avantage SFR Family! - Contrôle parental`
    Raison: hors périmètre BTP.
37. `E-Services (Espace client, Bilan annuel, Auto-relevé)`
    Raison: hors périmètre base produits.
38. `Forfait 150 Go 5G`
    Raison: hors périmètre base produits.
39. `IT-Livanto OL`
    Raison: libellé ambigu à vérifier.
40. `Supreme+ 98`
    Raison: à valider seulement si le carburant est retenu dans le périmètre.

## Note

- La base `btp` reste fortement polluée par des libellés alimentaires.
- Le noyau vraiment exploitable aujourd’hui est surtout:
  - béton
  - coulage
  - coffrage / sciage / ponçage
  - tuyaux
  - mise à disposition de pompe
  - quelques références matériaux/chantier à confirmer
