# Boulangerie Top 50 Triage

Source: `candidate_packs_metier/boulangerie_top_500_cleaned_candidates.csv`

Objectif: première sélection manuelle des 50 premiers `article_source` nouveaux pour la base `boulangerie`.

## A Garder

1. `CRISTALI 50CL PET`
2. `CRISTALINE 50CL P/24`
3. `OEUF COQUILLE TEINTE GROS 63/73 CT 360`
4. `BEURRE GD TOURAGE FLECHARD CT 5X2KG`
5. `SUCRE CRISTAL FIN SAC 25KG`
6. `FARINE LABEL ROUGE L EMOTION 100 % IDF SAC 25 KG`
7. `CRISTAL T65 25KG`
8. `LAIT UHT 1/2 ECREME BRIQ PACK 12X1L`
9. `CHEVRE BUCHETTE 180G LA PIECE`
10. `FROMAGE BLANC 2.8%MG SEAU 5KG`
11. `EMMENTAL RAPE UE 1KG`
12. `SAL ICEBERG MC PC DEMIPALX28 C1 ESESPAGNE`
13. `PAIN CHOCOLAT BEURRE 75G *`
14. `BEURRE DOUX 82% BLOC 25KG`
15. `CREME UHT 35% 1L MC BK AP`
16. `SEL FIN DE 25 KG`
17. `BEURRE SEC G.TOUR 2KG FLECH`
18. `BLANC OEUF LIQUIDE FERME DU PRE 1KG`
19. `CROISSANT BEURRE 65G *`
20. `EAU CRISTALINE PET 6X1.5L`
21. `LEVURE LEVAMAX ECOPACK (30x500G) 15 KG`
22. `COCACOLA BOITE SLIM 33CL`
23. `SAUMON FUME TRANCHE 800G`

## A Revoir

1. `CUISSE DE POULET FERMIER HALAL`
   Raison: hors périmètre boulangerie.
2. `BASSE SANS POITRINE DE VEAU`
   Raison: hors périmètre boulangerie.
3. `FILET DE POULET FERMIER HALAL`
   Raison: hors périmètre boulangerie.
4. `COQUELET HALAL`
   Raison: hors périmètre boulangerie.
5. `CUISSE POULET HALAL CEE 10KG`
   Raison: hors périmètre boulangerie.
6. `POULET PAC HALAL`
   Raison: hors périmètre boulangerie.
7. `POULET FERMIER HALAL PAC`
   Raison: hors périmètre boulangerie.
8. `FILET DE POULET HALAL CEE`
   Raison: hors périmètre boulangerie.
9. `CARRE DE VEAU SANS ROGNONS`
   Raison: hors périmètre boulangerie.
10. `FILET DE DINDE HALAL`
    Raison: hors périmètre boulangerie.
11. `FILET DE POULET HALAL UE`
    Raison: hors périmètre boulangerie.
12. `CUISSE DE POULET HALAL UE 10KG`
    Raison: hors périmètre boulangerie.
13. `PILONS DE POULET ID HALAL`
    Raison: hors périmètre boulangerie.
14. `CHICKEN WINGS HALAL`
    Raison: hors périmètre boulangerie.
15. `POMME DE TERRE GRENAILLE`
    Raison: à garder seulement si le périmètre inclut snacking/sandwicherie.
16. `SPICY HALAL`
    Raison: libellé trop flou / hors périmètre probable.
17. `FOIE DE POULET CEE HALAL`
    Raison: hors périmètre boulangerie.
18. `FOIE DE POULET HALAL UE`
    Raison: hors périmètre boulangerie.
19. `AGNEAU MOINS DE 12 MOIS`
    Raison: hors périmètre boulangerie.
20. `BASSE COTE VIANDE HALLAL`
    Raison: hors périmètre boulangerie.
21. `PILON DE POULET ID HALAL`
    Raison: hors périmètre boulangerie.
22. `BANANE`
    Raison: à valider selon le périmètre snacking/pâtisserie.
23. `CHORIZO TR BQ 500G`
    Raison: à valider si la base couvre salé/snacking.
24. `DECRO`
    Raison: libellé ambigu.
25. `Vente LeParisien`
    Raison: ce n'est pas un achat produit.
26. `Vente EQUIPE SEM`
    Raison: ce n'est pas un achat produit.
27. `AILES DE POULET HALAL CEE`
    Raison: hors périmètre boulangerie.
28. `Vente LP DIM`
    Raison: ce n'est pas un achat produit.
29. `CORDON DE VOLAILLE HALAL`
    Raison: hors périmètre boulangerie.
30. `JAUNE OEUF LIQUIDE FERME DU PRE 1KG`
    Raison: probablement bon candidat, mais à harmoniser avec `BLANC OEUF LIQUIDE`.
31. `LIPTON PECHE BTE 33CL SLIM`
    Raison: à valider selon le périmètre boissons.
32. `VEAU CREPINE ORIGINE :FRANCE`
    Raison: hors périmètre boulangerie.
33. `VEAU FOIE ORIGINE :PAYS-BAS`
    Raison: hors périmètre boulangerie.
34. `JAVEL EXTRAIT 2.6% BIDON 5L`
    Raison: à garder seulement si les consommables de nettoyage sont acceptés en base métier.
35. `GROSEILLE RGE 125G PAYS-BAS C1 PAYS BAS`
    Raison: peut être utile en pâtisserie, à valider.

## Note

- La base `boulangerie` est encore très polluée par des libellés viande.
- Le vrai noyau utile est:
  - farines
  - beurres
  - œufs
  - lait / crème
  - levure
  - eau / boissons
  - quelques produits snacking si tu choisis d’élargir le périmètre
