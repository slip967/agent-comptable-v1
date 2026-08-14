# Charges Externes Top 50 Triage

Source: `candidate_packs_metier/charges_externes_top_500_cleaned_candidates.csv`

Objectif: première sélection manuelle des 50 premiers `article_source` nouveaux pour la base `charges_externes`.

## A Garder

1. `Livraison`
2. `Indemnité forfaitaire frais de recouvrement 40 EUR (article D4415 Code du commerce)`
3. `Commission sur vente EQUIPE SEM`
4. `Commission sur vente LeParisien`
5. `Commission sur vente LP DIM`
6. `Commission Deliveroo`
7. `Débit : frais supplémentaires`
8. `Prestation émetteur Bimpli - 2nd génération`
9. `Frais de transaction Bimpli (1ère génération)`
10. `Prestation émetteur Bimpli (1ère génération)`
11. `Frais de transaction Bimpli - 2nd génération`
12. `Indemnité forfaitaire frais de recouvrement`
13. `Paiements supplémentaires`
14. `Forfait Client B&You 260Go 5G`
15. `Frais de livraison`
16. `Prestation émetteur - 2nd génération`
17. `Contribution tarifaire d'acheminement (CTA)`
18. `Frais de gestion`
19. `Frais hebdomadaire de gestion`
20. `Fourniture d'électricité`
21. `Frais de transaction - 2nd génération`
22. `Frais d'abonnement`
23. `Contribution au Service Public de l'Electricité (CSPE)`
24. `Acrobat Pro`
25. `AGIOS - AGIOS`
26. `Aide énergie`
27. `Contribution Tarifaire d'Acheminement électricité (CTA)`
28. `Frais de service Airbnb`
29. `Commission Deliveroo - Livraison`
30. `Nettoyage en cours et en fin de chantier. Nettoyage fin de chantier et mise en décharge de déchets du chantier.`
31. `Frais de service`

## A Revoir

1. `GARDE - GARDE`
   Raison: probable cotisation réelle, mais libellé à fusionner/canoniser.
2. `GARDE`
   Raison: probable cotisation réelle, mais trop court et à fusionner.
3. `RSD - RSD`
   Raison: variante à rapprocher de `COTI.RSD`.
4. `IBAUF - Interbev Boeuf AM`
   Raison: bon candidat, mais à fusionner avec les autres variantes `Interbev`.
5. `IBAFF - Interbev Boeuf AM`
   Raison: variante de cotisation Interbev à harmoniser.
6. `IVAFF - Interbev Veau AM`
   Raison: variante de cotisation Interbev à harmoniser.
7. `IVGUF - Interbev Veau MG`
   Raison: variante de cotisation Interbev à harmoniser.
8. `IVAUF - Interbev Veau AM`
   Raison: variante de cotisation Interbev à harmoniser.
9. `INTERBEV Boeuf`
   Raison: probable bon candidat, mais à fusionner avec les variantes codées.
10. `IBGUF - Interbev Boeuf MG`
    Raison: variante de cotisation Interbev à harmoniser.
11. `SORTIE VOLAILLES`
    Raison: à valider entre transport/logistique et base métier produit.
12. `Interbev Boeuf AM`
    Raison: bon candidat, mais à fusionner avec les variantes `IB...`.
13. `R.S.D.`
    Raison: variante à fusionner avec `COTI.RSD`.
14. `INTERBEV Ovin`
    Raison: bon candidat, mais à fusionner avec les autres lignes Interbev.
15. `Interbev Veau AM`
    Raison: bon candidat, mais à fusionner avec les variantes `IV...`.
16. `Prest.Decro.`
    Raison: probablement réel, mais libellé trop abrégé à canoniser.
17. `Avantage client box`
    Raison: ligne commerciale / remise ou avantage, à valider.
18. `Forfait Client B&You 260Go 5G`
    Raison: bon candidat si tu acceptes télécom dans charges externes, sinon à exclure.
19. `EAU CRISTALINE PET 6X1.5L`
    Raison: produit, pas charge externe.
20. `CRISTALI 50CL PET`
    Raison: produit, pas charge externe.
21. `RIOBA ABC ORANGE TO 25CL`
    Raison: produit, pas charge externe.
22. `Vente LeParisien`
    Raison: ligne de vente, pas charge.
23. `Vente EQUIPE SEM`
    Raison: ligne de vente, pas charge.
24. `Vente LP DIM`
    Raison: ligne de vente, pas charge.
25. `Vente EQUIPE DIM`
    Raison: ligne de vente, pas charge.
26. `Montant net facturable par Deliveroo`
    Raison: probablement ligne de synthèse, pas une charge exploitable telle quelle.
27. `Gazole`
    Raison: à valider selon si tu veux intégrer le carburant dans la base charges externes globale.

## Note

- Le pack `charges_externes` est utile, mais il demande plus de normalisation que les bases produits.
- Les meilleures familles qui remontent sont:
  - cotisations / interprofessions
  - commissions marketplace
  - frais administratifs / recouvrement
  - télécom
  - énergie / utilités
  - livraison / logistique
- Avant intégration, il faut surtout fusionner les variantes `GARDE`, `RSD`, `INTERBEV`, `IV...`, `IB...`.
