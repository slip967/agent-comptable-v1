# Restaurant Top 50 Triage

Source: `candidate_packs_metier/restaurant_top_500_cleaned_candidates.csv`

Objectif: première sélection manuelle des 50 premiers `article_source` nouveaux pour la base `restaurant`.

## A Garder

1. `POULET PAC HALAL`
2. `Tiramisu Choco-nut`
3. `Diplomate Fraise`
4. `SAUCISSE WUDY XXL HALAL`
5. `Tiramisu Caramel Beurre-salé`
6. `Misu Coco-Rocher`
7. `50 COUV BTE SALADE KRAFT GM`
8. `CUISSE POULET HALAL CEE 10KG`
9. `DONUTS FILET POULET`
10. `CAROTTE MC 5KG 20/40 GB40 FR C1france`
11. `CUISSE DE POULET HALAL UE 10KG`
12. `DONUT DE FILET DE POULET`
13. `FILET DE POULET HALAL UE`
14. `COCACOLA BOITE SLIM 33CL`
15. `PILONS DE POULET ID HALAL`
16. `FILET DE POULET HALAL CEE`
17. `CRISTALI 50CL PET`
18. `PILON DE POULET ID HALAL`
19. `MPRO BOBINE 2P 450F X6`
20. `MERGUEZ BOEUF/AGN HALAL`
21. `AILE DE POULET 3 PHALANGES HALAL UE`
22. `COCA COLA VC 33CL`
23. `OASIS TROPICAL SLIM BTE 33CL`
24. `AILES DE POULET 3 PHALANGES HALAL CEE`
25. `MC PENNE RIGATE 5KG`
26. `Tiramisu Toffee-Choc`
27. `MC OLIV.VERTES RONDELLE A10`
28. `50 BTE SALADE KRAFT 1300ML`
29. `BOULE A PIZZA CRU 280GX35`
30. `MC OLIV.NOIRES RONDELLE A10`
31. `CAISSE COCA 24X33CL PLEIN`
32. `50 COUV BTE SALADE KRAFT PM`
33. `HAWAI TROPICAL BOITE 33CL`
34. `CREME FRAICHE GRAND FERMAGE 5L 15%`
35. `COCA CHERRY 33CLx24 EU`
36. `COCA SANS SUCRES VC 33CL`
37. `FUZETEA MENTH/CITRON VERT 33CL`
38. `OASIS TROPICAL 33CL x 24`
39. `MPRO 250 SERV 2P BLC 40X40`
40. `VIANDE HACHEE EGRENEE 4MM BOEUF ISLAM CONTROL 1KG`
41. `PERRIER BOITE SLIM 33CL`
42. `AIL PELE BOCAL 1 KG`
43. `PLT BLC PAC NU HAL 1.2KG*10 FR`
44. `SALADE ICEBERG`
45. `50 SAC PAP KRAFT POIG 26X14X32`
46. `FRITES MY FRIES CLASSIC 6/6`
47. `LIPTON PECHE BTE 33CL SLIM`
48. `COCA COLA 33cl x 24 EU`
49. `HARICOTS VERTS E.F.2.5KG MC`
50. `MC TOMATES CONCASSEES 4/4`
51. `ARO DECAPANT FOUR DEGRAIS 5L`
52. `HUILE DE TOURNESOL BINGOIL 1L`

## A Revoir

1. `BOUCHERIE`
   Raison: libellé trop générique / pas un article exploitable.
2. `BAV ALOY HAL UE`
   Raison: libellé trop abrégé, à canoniser avant intégration.
3. `Montant total de la commande TTC`
   Raison: ce n'est pas un article.
4. `Contribution tarifaire d'acheminement (CTA)`
   Raison: hors périmètre base produits.
5. `Spotify Premium (1 mois)`
   Raison: abonnement / hors périmètre restaurant.
6. `MERGUEZ DE BOEUF/AGN HALAL`
   Raison: variante proche de `MERGUEZ BOEUF/AGN HALAL`.

## Note

- La base `restaurant` peut accepter:
  - matières premières
  - boissons
  - emballages / consommables service
  - produits de nettoyage directement liés à l’exploitation cuisine
- Les lignes trop génériques, les totaux et les abonnements restent à écarter.
