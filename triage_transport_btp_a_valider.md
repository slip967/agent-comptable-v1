# Triage Transport / BTP - A Valider

Date: 2026-05-05

Objectif: distinguer les lignes qui doivent rester dans une base produits métier
de celles qui relèvent plutôt de `charges_externes` car elles décrivent un service,
un abonnement, une communication, une location ou une prestation.

## Regle retenue

- `base_produits_*` : achats / consommables / materiaux / pieces / carburants / produits d'exploitation
- `base_charges_externes_*` : abonnements, telecom, services, prestations, locations, options, maintenance contractuelle

## BTP

### A deplacer vers charges_externes

1. `Essai de contrôle sur un micropieu de l'ouvrage selon EC7`
   Motif: prestation technique de controle, pas produit / materiau.

2. `Travaux de terrassement et étanchéité de la zone comportant des infiltrations d'eau`
   Motif: prestation de travaux, pas achat de produit BTP simple.

3. `Amenée-repli de l'atelier de forage des micropieux`
   Motif: service logistique / chantier, pas produit.

4. `Implantation des micropieux`
   Motif: prestation technique de chantier, pas produit.

### A garder dans base_produits_btp

Aucune sur ce lot `a_valider`.

### Conclusion BTP

Le lot `a_valider` BTP ressemble a des prestations chantier. Recommendation:
le sortir de `base_produits_btp` et le reclasser dans `charges_externes`
avec un sous-profil du type `prestations_techniques_chantier` ou `travaux_et_sous_traitance`.

## Transport

### A deplacer vers charges_externes

#### Forfaits / abonnements mobile

1. `Forfait Client B&You 260Go 5G`
2. `Forfait Client B&You 230Go`
3. `Forfait Spécial client 350Go 5G Av. smartphone`
4. `Forfait Sensation 150Go 5G Avantages Smartphone`
5. `Forfait Sensation client 70Go`
6. `Vos abonnements, forfaits et options`

Motif: services telecom recurrents, pas produits transport.

#### Communications / appels

7. `Communications vers l'international`
8. `Vos communications (du 02/12 au 01/01)`
9. `Vos communications (du 02/07 au 01/08)`
10. `Vos communications (du 02/09 au 01/10)`
11. `Appels a tarification majorée (Numéros spéciaux)`
12. `Appels tarification majorée - Numéros spéciaux`

Motif: services telecom, pas consommables d'exploitation transport.

#### Internet / options data

13. `Avantage Internet 60Go`
14. `Avantage Internet 80Go`
15. `Avantage Internet 100Go`
16. `Option multi-SIM Internet`
17. `Option Week-end internet illimité`
18. `Internet 10Go France`
19. `Evolution d'offre - Appels illimités mobiles France_ (du 02/07 au 01/08)`

Motif: options telecom / data.

#### Equipement box / fibre / TV

20. `Bbox - location équipement (du 02/07 au 01/08)`
21. `Bbox - location équipement (du 02/09 au 01/10)`
22. `Bbox - location équipement (du 02/05 au 01/06)`
23. `Bbox - location équipement (du 02/12 au 01/01)`
24. `Bbox - location équipement (du 02/02 au 01/03)`
25. `Bbox - location équipement (du 02/10 au 01/11)`
26. `Bbox - location équipement (du 02/11 au 01/12)`
27. `Bbox fibre jusqu'a1 Gb/s (du 02/05 au 01/06)`
28. `Bbox fibre jusqu'a1 Gb/s (du 02/07 au 01/08)`
29. `Bbox fibre jusqu'a1 Gb/s (du 02/12 au 01/01)`
30. `Multi-TV FTTH (du 02/07 au 01/08)`
31. `Multi-TV FTTH (du 02/09 au 01/10)`
32. `Multi-TV FTTH (du 02/05 au 01/06)`
33. `Multi-TV FTTH (du 02/12 au 01/01)`

Motif: location / telecom / services multimedia, pas produits transport.

#### Securite / services divers telecom

34. `Solutions Sécurité Smartphone avec Norton`
35. `Pack sécurité Norton`
36. `Applications - contenus - services`
37. `Services de télécommunications (forfait, communications, autres services)`

Motif: services et options telecom, pas achat métier transport.

### A garder dans base_produits_transport

Aucune sur ce lot `a_valider`.

### Conclusion Transport

Les `37` lignes `a_valider` ne semblent pas relever de `base_produits_transport`.
Elles devraient plutot etre transferees vers `charges_externes`, idealement
dans un sous-profil du type `telecom_et_abonnements`.

## Recommendation finale

- `BTP`: deplacer les `4` lignes `a_valider` vers `charges_externes`
- `Transport`: deplacer les `37` lignes `a_valider` vers `charges_externes`
- garder `base_produits_transport` pour carburant, lavage, entretien, pieces et consommables vehicule
- garder `base_produits_btp` pour materiaux, consommables chantier, quincaillerie, beton, mortier, outils et fournitures
