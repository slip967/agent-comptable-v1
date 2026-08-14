# Boucherie Top 50 Triage

Source: `candidate_packs_metier/boucherie_top_500_cleaned_candidates.csv`

Objectif: première sélection manuelle des 50 premiers `article_source` nouveaux pour la base `boucherie`.

## A Garder

1. `PILON DE POULET HALAL UE`
2. `CUISSE DE POULET HALAL UE`
3. `POULET FERMIER JAUNE PAC HALAL`
4. `CORDON BLEU DE POULET AUTHENTIC HALAL`
5. `FOIE DE VEAU`
6. `CUISSEAU DE VEAU`
7. `FOIE DE POULET HALAL`
8. `FRESSURE DE MOUTON CARCASSE ABATS`
9. `FOIE DE VEAU CARCASSE ABATS`
10. `BASSE COTE`
11. `POITRINE DE VEAU`
12. `POULET FERMIER BIO PAC HALAL`
13. `CUISSE DE DINDE HALAL`
14. `FRESSURE DE MOUTON`
15. `CUISSE DE POULET HALAL`
16. `RUMSTEACK BLANC BLEU BELGE`
17. `CREPINE DE VEAU`
18. `PIED DE VEAU`
19. `QUEUE DE BOEUF CARCASSE ABATS`
20. `PANSE D'OVIN SALE`
21. `GÉSIER DE POULET HALAL`
22. `PILON DE POULET HALAL CEE`
23. `BAVETTE ALOYAU BLANC BLEU BELGE`
24. `AILE DE POULET HALAL`
25. `QUEUE DE BOEUF`
26. `QUEUE DE VEAU`
27. `CARRE AGNEAU`
28. `TESTICULE DE MOUTON`
29. `COLLIER AGNEAU`
30. `GÉSIER DE POULET HALAL UE`
31. `LAPIN X4 HALAL`

## A Revoir

1. `POMME DE TERRE GRATIN DAUPHINOIS`
   Raison: accompagnement / hors coeur boucherie.
2. `PANÉ DE VOLAILLE HALAL UE MILANESE`
   Raison: produit transformé, à valider selon périmètre métier.
3. `CORDON BLEU PLT AUTHENTIC HALAL`
   Raison: produit transformé + variante proche du cordon bleu déjà retenu.
4. `TENDER CE HALAL`
   Raison: libellé trop abrégé / OCR douteux.
5. `RUMSTEACK BLANC BLEU BELGE VIANDE HALLAL`
   Raison: variante proche avec bruit orthographique.
6. `DONUT DE FILET DE POULET`
   Raison: produit transformé, à valider.
7. `CREPINE DE VEAU CARCASSE ABATS`
   Raison: variante possible de `CREPINE DE VEAU`.
8. `PDT GRATIN DAUPHINOIS`
   Raison: doublon/variante de gratin dauphinois + hors coeur boucherie.
9. `BAVETTE ALOYAU BLANC BLEU BELGE VIANDE HALLAL`
   Raison: variante proche avec libellé bruité.
10. `CORDON BLEU S/AT HALAL`
    Raison: libellé abrégé / à canoniser.
11. `PIED DE VEAU - CARCASSE ABATS`
    Raison: variante probable de `PIED DE VEAU`.
12. `VEAU`
    Raison: trop générique.
13. `FILET DE POULET HALAL UE origine : NL`
    Raison: variante pays d’origine d’un libellé déjà couvert.
14. `BAVETTE ALOYAU - VIANDE HALLAL BLANC BLEU BELGE`
    Raison: variante proche avec ordre des mots différent.
15. `QUEUE DE VEAU CARCASSE ABATS`
    Raison: variante probable de `QUEUE DE VEAU`.
16. `PAN.DOUBLE DE VEAU`
    Raison: libellé OCR/abrégé, à vérifier.
17. `PILON DE POULET HALAL UE origine : NL`
    Raison: variante pays d’origine d’un libellé déjà couvert.
18. `BASSE COTE SOUS VIDE BEUF`
    Raison: probable OCR fautif sur `boeuf`, à canoniser.
19. `CUISSE DE POULET HALAL UE origine : NL`
    Raison: variante pays d’origine d’un libellé déjà couvert.

## Note

- `A garder` ne veut pas dire `injection brute sans lecture`, mais `bons candidats métier`.
- `A revoir` correspond surtout à:
  - variantes proches à fusionner
  - produits transformés à valider
  - libellés OCR bruités
  - libellés trop génériques
