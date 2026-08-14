# Synthese fuzzy match sur 40 invoice_form

- Base CouchDB: `keymanage_accounting`
- Factures echantillonnees: `40`
- References chargees: `2124`
- Factures precedentes exclues: `10`

## Facture 1
- Invoice ID: `fr_bd_752620443:06be5a48-e177-4676-801e-7c3c40fecc86`
- Numero: `03064`
- Date: `24/06/2024`
- Emetteur: `METRO FRANCE`
- Destinataire: `LA SUPERETTE DE LA PLACE`
- Lignes: `38`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | 1L Javel Classic double action | global | 6063 | Fournitures d'entretien et de petit équipement | 44.83 | rejeter |
| 2 | 1,25L Fleur de Muguet Nettoyant Surfaces | epicerie | 607 | Achats de marchandises | 55.93 | rejeter |
| 3 | 1,25L Frais Nettoyant Surfaces | global | 6068 | Autres matières et fournitures | 67.47 | validation_humaine |
| 4 | 1,25L Jasmin Nettoyant Surfaces | epicerie | 607 | Achats de marchandises | 59.26 | rejeter |
| 5 | 1,25L Muguet Nettoyant Surfaces | epicerie | 607 | Achats de marchandises | 58.72 | rejeter |
| 6 | 10* Classic Normal T.1 | restaurant | 6011 | Achats stockés - Matières premières | 55.02 | rejeter |
| 7 | 1750ml (29+6 Lavages) Original Lessive Liquide | epicerie | 607 | Achats de marchandises | 70.52 | validation_humaine |
| 8 | Caps Active anti odeur | global | 6261 | Télécommunications | 47.84 | rejeter |
| 9 | Premium cotton-tiges 300pcs | epicerie | 607 | Achats de marchandises | 61.13 | rejeter |
| 10 | 500 ML Créme Citron | epicerie | 607 | Achats de marchandises | 66.1 | validation_humaine |
| 11 | 750ML Cuisine Nature Spray | global | 6063 | Fournitures d'entretien et de petit équipement | 58.22 | rejeter |
| 12 | 30M Film Alimentaire | global | 6062 | Fournitures consommables | 61.08 | rejeter |
| 13 | Medium Brosse a Dents Extra Clean | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 14 | 5L (100 Lavages) Couleur Lessive Liquide | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 15 | 5L (100 Lavages) Universelle Lessive Liquide | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 16 | 250ml Creme Beauté | epicerie | 607 | Achats de marchandises | 50.65 | rejeter |
| 17 | 1,50L Water Lily Wave Tout Surface All purpose | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 18 | 220ML Gel Lessive ä la Main Express | global | 6061 | Fournitures non stockables (eau, énergie) | 47.69 | rejeter |
| 19 | 70pcs Mouchoirs Soft White 2 épaisseurs | global | 6062 | Fournitures consommables | 41.48 | rejeter |
| 20 | 72pcs Mouchoirs Original White (3 couches) | global | 6068 | Autres matières et fournitures | 40.67 | rejeter |
| 21 | 550ML (22 Lavages) Essence Marine Adoucissant Sea Minerals (IT) | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 22 | 54 Lavages (2.97L) Lessive Laine | epicerie | 607 | Achats de marchandises | 59.53 | rejeter |
| 23 | *6 Essuie-tout GRAND format Rouleaux 2 plis avec anse | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 24 | 1L Citron d'Eté Nettoyant de Surface | epicerie | 607 | Achats de marchandises | 61.84 | rejeter |
| 25 | 1L Fraicheur Ocean Nettoyant de Surface | epicerie | 607 | Achats de marchandises | 58.31 | rejeter |
| 26 | 24 rouleaux Papier Toilette 3 Plis | global | 6061 | Fournitures non stockables (eau, énergie) | 57.65 | rejeter |
| 27 | 3L Lessive Liquide (50 Lavages) | global | 6061 | Fournitures non stockables (eau, énergie) | 72.81 | validation_humaine |
| 28 | 750ML Citron Liquide vaisselle Fraicheur | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 29 | 750ML Grenade Liquide vaisselle Fraicheur | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 30 | 750ML Lave Vitre CAMSIL | global | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 31 | 750ML Péche Liquide vaisselle Fraicheur | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 32 | 750ML Pomme Liquide vaisselle Fraicheur | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 33 | 1.5L Ultra Javel Eucalyptus Bleekmidel | global | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 34 | 750ML Pro Spray Nettoyant Desinfectant Multi-Surfaces | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 35 | 750ML Pro Spray Nettoyant Multi Surface Brillance (BG) | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 36 | 2L Gel avec Javel 3en1 (Mastro Lindo) con Candeggina | global | 6068 | Autres matières et fournitures | 49.74 | rejeter |
| 37 | 1.4L Floral Passion Assouplissant | global | 6068 | Autres matières et fournitures | 44.72 | rejeter |
| 38 | Cotton-tiges 100 pcs Pamuklu Cubuk 100 adet | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |

## Facture 2
- Invoice ID: `fr_bd_752620443:06dc073e-442c-4461-addf-a89829171a85`
- Numero: `FA20254012`
- Date: `20/11/2025`
- Emetteur: `IDF DISTRIBUTION`
- Destinataire: `LA SUPERETTE DE LA PLACE`
- Lignes: `43`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | LIPTON ICE TEA FRAMBOISE 50CL FR X12 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 2 | LIPTON ICE TEA PASTEQUE MENTHE 50CL FR X12 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 3 | LIPTON ICE TEA PECHE 50CL FR X12 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 4 | CRISTALINE 50CL FR X24 | vtc | 6068 | Autres matières et fournitures | 67.53 | validation_humaine |
| 5 | MONSTER ENERGY DRINK 50CL EUR 6X4 | global | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 6 | COCA COLA CHERRY 50CL FR X12 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 7 | COCA COLA ZERO 50CL FR X12 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 8 | COCA COLA 1.5L EUR X6 | epicerie | 607 | Achats de marchandises | 64.38 | validation_humaine |
| 9 | CALYPSO OCEAN BLUE 473ML FR X12 | epicerie | 607 | Achats de marchandises | 45.81 | rejeter |
| 10 | FANTA ORANGE 33CL EUR X24 SLIM | restaurant | 6061 | Fournitures non stockables (eau, énergie) | 72.81 | validation_humaine |
| 11 | FANTA FRAISE KIWI 33CL EUR X24 FAT | restaurant | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 12 | FANTA TROPICAL 33CL EUR X24 SLIM | restaurant | 6061 | Fournitures non stockables (eau, énergie) | 72.81 | validation_humaine |
| 13 | HAWAI TROPICAL 33CL FR X24 SLIM | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 14 | SCHWEPPES AGRUMES 33CL FR X24 SLIM | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 15 | COCA COLA 33CL EUR X24 SLIM | restaurant | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 16 | OASIS FRAISE FRAMBOISE 33CL FR X24 SLIM | restaurant | 6061 | Fournitures non stockables (eau, énergie) | 69.26 | validation_humaine |
| 17 | OASIS POMME POIRE 33CL FR X24 SLIM | vtc | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 18 | OASIS POMME CASSIS FRAMBOISE 33CL FR X24 SLIM | restaurant | 6061 | Fournitures non stockables (eau, énergie) | 69.26 | validation_humaine |
| 19 | OASIS TROPICAL 33CL FR X24 SLIM | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 20 | FANTA STRAWBERRY 355ML US X12 FAT | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 21 | FANTA PINEAPPLE 355ML US X12 FAT | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 22 | FANTA BERRY 355ML US X12 FAT | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 23 | SEVEN UP CHERRY 33CL FR X24 SLIM | restaurant | 6061 | Fournitures non stockables (eau, énergie) | 68.78 | validation_humaine |
| 24 | LIPTON ICE TEA PECHE 1.5L EUR X9 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 25 | ORANGINA 1.5L EUR X6 | epicerie | 607 | Achats de marchandises | 61.47 | rejeter |
| 26 | SCHWEPPES AGRUMES 1.5L FR X6 | global | 6068 | Autres matières et fournitures | 65.69 | validation_humaine |
| 27 | BOGA LIME 1.5L FR X6 | boulangerie | 601 | Achats stockés - Matières premières (et fournitures) | 57.85 | rejeter |
| 28 | BOGA CIDRE 1.5L FR X6 | boulangerie | 601 | Achats stockés - Matières premières (et fournitures) | 56.45 | rejeter |
| 29 | SELECTO 1.5L FR X6 | global | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 30 | TROPICO 1.25L FR X6 | global | 6068 | Autres matières et fournitures | 68.65 | validation_humaine |
| 31 | COCA COLA CHERRY 1.5L EUR X6 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 32 | MIRINDA ANANAS 1.5L FR X6 | epicerie | 601 | Achats stockés - Matières premières (et fournitures) | 67.33 | validation_humaine |
| 33 | COCA COLA ZERO 1.5L EUR X9 | epicerie | 607 | Achats de marchandises | 62.94 | validation_humaine |
| 34 | OASIS FRAISE FRAMBOISE 2L FR X6 | vtc | 6068 | Autres matières et fournitures | 54.04 | rejeter |
| 35 | OASIS POMME POIRE 2L FR X6 | vtc | 6068 | Autres matières et fournitures | 72.81 | validation_humaine |
| 36 | OASIS POMME CASSIS 2L FR X6 | vtc | 6068 | Autres matières et fournitures | 60.78 | rejeter |
| 37 | OASIS PECHE ABRICOT 2L FR X6 | epicerie | 607 | Achats de marchandises | 59.57 | rejeter |
| 38 | OASIS TROPICAL 2L FR X6 | epicerie | 607 | Achats de marchandises | 66.56 | validation_humaine |
| 39 | CAPRI SUN MULTIFRUITS FR 10X200ML*4 | global | 6068 | Autres matières et fournitures | 61.37 | rejeter |
| 40 | SAN PELLEGRINO 1L FR X6 | epicerie | 607 | Achats de marchandises | 61.9 | rejeter |
| 41 | PERRIER 1L FR X6 | epicerie | 607 | Achats de marchandises | 68.69 | validation_humaine |
| 42 | EVIAN 1.5L X6 | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 43 | CRISTALINE 1.5L FR X6 | epicerie | 607 | Achats de marchandises | 67.78 | validation_humaine |

## Facture 3
- Invoice ID: `fr_bd_752620443:0848a811-ad67-43c7-87b3-6c77650d2631`
- Numero: `E775004544-44-2024-2`
- Date: `27/10/2024`
- Emetteur: `WORLDLINE PREPAID SERVICES FRANCE`
- Destinataire: `LA SUPERETTE DE LA PLACE`
- Lignes: `9`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | Recharge SFR La Carte llimitee 19,99€ | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 2 | Recharge SYMA 5£ | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 3 | Recharge LEBARA Bonus Temps 10€ | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 4 | Recharge LEBARA Nationale Doublée 10£ | epicerie | 607 | Achats de marchandises | 44.0 | rejeter |
| 5 | Recharge LYCAMOBILE 10€ | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 6 | Recharge LYCAMOBILE Pass National S | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 7 | Recharge LYCAMOBILE Pass National M | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 8 | Recharge LYCAMOBILE Web Pass M 4,9 | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |
| 9 | Recharge LYCAMOBILE Pass National XX | epicerie | 607 | Achats de marchandises | 54.06 | rejeter |

## Facture 4
- Invoice ID: `fr_bd_752620443:09b7913a-3903-46a4-8eb5-32d4188b6bf5`
- Numero: `6210819399`
- Date: `12/05/2024`
- Emetteur: `WORLDLINE PREPAID SERVICES FRANCE`
- Destinataire: `LA SUPERETTE DE LA PLACE`
- Lignes: `10`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | Recharge SFR La Carte Illimitee 19,99£ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 2 | Recharge ORANGE 5 + 1£ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 3 | Recharge ORANGE 10 + 2€ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 4 | Recharge SYMA 5£ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 5 | Recharge SYMACOM FORFAIT BLOQUE | epicerie | 607 | Achats de marchandises | 75.0 | validation_humaine |
| 6 | Recharge LEBARA Bonus Temps 5€ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 7 | Recharge LYCAMOBILE 5€ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 8 | Recharge LYCAMOBILE 10€ | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 9 | Recharge LYCAMOBILE Pass National S | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |
| 10 | Recharge LYCAMOBILE Pass National M | epicerie | 607 | Achats de marchandises | 88.75 | validation_humaine |

## Facture 5
- Invoice ID: `fr_bd_752620443:0a410e55-30d9-4886-8620-f475b9fe38c4`
- Numero: `0/0 (051) 0009/008033`
- Date: `11/05/2024`
- Emetteur: `METRO FRANCE`
- Destinataire: `LA SUPERETTE DE LA PLACE`
- Lignes: `14`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | FANTA CITRON BTE SLIM 33CL | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 2 | NUTELLA 400G | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 3 | LAIT UHT 1/2ECR 1L PPX BK (P | boulangerie | 601 | Achats stockés - Matières premières (et fournitures) | 81.25 | validation_humaine |
| 4 | LAIT UHT VIVA 1L BK VITAMINE | boulangerie | 601 | Achats stockés - Matières premières (et fournitures) | 81.25 | validation_humaine |
| 5 | LAIT UHT ENTIER 1L PPX BK (P | boulangerie | 601 | Achats stockés - Matières premières (et fournitures) | 81.25 | validation_humaine |
| 6 | LAIT FERMENTE 1L BK LUXLAIT | boulangerie | 607 | Achats de marchandises | 81.25 | validation_humaine |
| 7 | D.FRUIT POMME 16X100G ANDROS | epicerie | 601 | Achats stockés - Matières premières (et fournitures) | 72.81 | validation_humaine |
| 8 | 0EUF 6 G SOL ROCHAMBEAU | epicerie | 601 | Achats stockés - Matières premières (et fournitures) | 72.81 | validation_humaine |
| 9 | BEURRE DX PLQ.250GX4 PRESIDENT | epicerie | 601 | Achats stockés - Matières premières (et fournitures) | 72.81 | validation_humaine |
| 10 | CHEVRE STE MAURE 20OG SOIGNZ | global | 6063 | Fournitures d'entretien et de petit équipement | 72.81 | validation_humaine |
| 11 | PAIN MIE NATURE LC 55OG ROCHAM | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 12 | PAIN CHOCOLAT LC 36OG ROCH | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 13 | PAIN LAIT LC 350G ROCH C | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |
| 14 | BRI0CHE TRESSEE LC 600G | epicerie | 607 | Achats de marchandises | 72.81 | validation_humaine |

## Facture 6
- Invoice ID: `fr_bd_877701128:007b2be1-8720-41cc-a6ba-cdf9c4a8428f`
- Numero: `3636`
- Date: `20/03/2025`
- Emetteur: `FA 91`
- Destinataire: `MONSIEUR TOUATI`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | FILTRE A AIR | vtc | 615 | Entretien et réparations | 72.81 | validation_humaine |
| 2 | PEINTURE SLV DEBBER | vtc | 615 | Entretien et réparations | 48.79 | rejeter |
| 3 | Divers EPANGE | btp | 6061 | Fournitures non stockables (eau, énergie) | 52.66 | rejeter |

## Facture 7
- Invoice ID: `fr_bd_877701128:00acfb8d-7750-445d-b09c-c3ed6c8bf0f4`
- Numero: `3677`
- Date: `25/03/2025`
- Emetteur: `FA 91`
- Destinataire: `K`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | AGRAFE | btp | 6061 | Fournitures non stockables (eau, énergie) | 47.19 | rejeter |
| 2 | AGRAFE | btp | 6061 | Fournitures non stockables (eau, énergie) | 47.19 | rejeter |

## Facture 8
- Invoice ID: `fr_bd_877701128:011a9336-c05a-4f15-a5cd-b3fbdec17a02`
- Numero: `022 - 075570`
- Date: `16/10/2025`
- Emetteur: `BRICOMAN`
- Destinataire: `FA 91`
- Lignes: `7`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | AUGE CABAS 42 LITRES NOIRE | btp | 6063 | Fournitures d'entretien et de petit équipement | 56.8 | rejeter |
| 2 | COUTEAUX A ENDUIRE BIMAT MONDELIN 24CM | btp | 6011 | Achats stockés - Matières premières | 46.06 | rejeter |
| 3 | COUTEAUXA ENDUIRE BI MAT MONDELIN 12CM | btp | 6011 | Achats stockés - Matières premières | 46.06 | rejeter |
| 4 | PLATOIR LAME INOX 28X12 CM MONDELIN | btp | 6063 | Fournitures d'entretien et de petit équipement | 58.53 | rejeter |
| 5 | TALOCHE 27X18 NOIR MANCHE BOIS POINTUE | btp | 6021 | Matières consommables | 53.12 | rejeter |
| 6 | TALOCHE PRO ABS 26X35 RECTANG. MONDELIN | btp | 6063 | Fournitures d'entretien et de petit équipement | 50.45 | rejeter |
| 7 | SEAU 16L PLASTIQUE NOIR AVEC POIGNEE | btp | 6063 | Fournitures d'entretien et de petit équipement | 83.56 | validation_humaine |

## Facture 9
- Invoice ID: `fr_bd_877701128:011f5f04-6a4a-4b62-a8f8-1fde29e66ebd`
- Numero: `3201`
- Date: `03/02/2025`
- Emetteur: `FA 91`
- Destinataire: `PREMIEUM CARS`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE MIPA | vtc | 6062 | Fournitures consommables | 48.23 | rejeter |
| 2 | PAPIER P80 DISQUE MIRKA | vtc | 615 | Entretien et réparations | 48.68 | rejeter |
| 3 | PAPIER DE PONÇAGE MIRKA P800 | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |

## Facture 10
- Invoice ID: `fr_bd_877701128:01b6815b-2bb9-4f14-9dbb-eda12356f6bc`
- Numero: `3535`
- Date: `10/03/2025`
- Emetteur: `FA 91`
- Destinataire: `UNIVERS CARS`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 58.44 | rejeter |
| 2 | COQUE RETRO | vtc | 6068 | Autres matières et fournitures | 51.24 | rejeter |

## Facture 11
- Invoice ID: `fr_bd_877701128:0216a4da-fc2d-4cab-a2cb-f4b88d4a7d96`
- Numero: `2964`
- Date: `04/01/2025`
- Emetteur: `FA 91`
- Destinataire: `COMPTOIR ATHIS`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | BOMBESL | btp | 6061 | Fournitures non stockables (eau, énergie) | 53.82 | rejeter |

## Facture 12
- Invoice ID: `fr_bd_877701128:028d140d-96d4-4a82-8ccb-f1731d3b1f87`
- Numero: `441`
- Date: `28/02/2025`
- Emetteur: `FA 91`
- Destinataire: `AUTO MECA 91`
- Lignes: `8`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE BD MIPA | vtc | 6062 | Fournitures consommables | 48.49 | rejeter |
| 2 | RUBON | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 3 | RUBON | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 4 | MASTICALU | btp | 6061 | Fournitures non stockables (eau, énergie) | 49.44 | rejeter |
| 5 | PAPIER P800 GERKO | btp | 6063 | Fournitures d'entretien et de petit équipement | 50.53 | rejeter |
| 6 | TOMPON | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 7 | COUTEAU | global | 6063 | Fournitures d'entretien et de petit équipement | 59.31 | rejeter |
| 8 | PRIMER PLASTIC | btp | 6061 | Fournitures non stockables (eau, énergie) | 47.56 | rejeter |

## Facture 13
- Invoice ID: `fr_bd_877701128:0389e848-687d-4ea8-b110-9e7fe73dfbc1`
- Numero: `3009`
- Date: `08/01/2025`
- Emetteur: `FA 91`
- Destinataire: `CENTRE AUTO LES IRIS`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | 150G PEINTURE SLV MIPA | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |

## Facture 14
- Invoice ID: `fr_bd_877701128:03944ed5-11ad-402f-99db-801e9bb48c51`
- Numero: `3170`
- Date: `30/01/2025`
- Emetteur: `FA 91`
- Destinataire: `NBZCARROSSERIE`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | DILUANT 30L | btp | 6061 | Fournitures non stockables (eau, énergie) | 48.76 | rejeter |

## Facture 15
- Invoice ID: `fr_bd_877701128:03c11e22-7d20-47be-b8ca-71e603feeaf4`
- Numero: `3193`
- Date: `01/02/2025`
- Emetteur: `FA 91`
- Destinataire: `MONSIEUR CLIENT HABITEUL`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PLAQUETTE AV | transport | 6062 | Fournitures consommables | 69.3 | validation_humaine |

## Facture 16
- Invoice ID: `fr_bd_877701128:03f92c81-f05d-4107-89da-03a245bfbe20`
- Numero: `3373`
- Date: `19/02/2025`
- Emetteur: `FA 91`
- Destinataire: `COMPTOIR CLIENT`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | Divers 250G SLV | btp | 6061 | Fournitures non stockables (eau, énergie) | 51.53 | rejeter |
| 2 | EPONGE | btp | 6063 | Fournitures d'entretien et de petit équipement | 60.7 | rejeter |

## Facture 17
- Invoice ID: `fr_bd_877701128:0427b221-a8bc-4294-bc70-f5b1655d9206`
- Numero: `N3122`
- Date: `24/01/2025`
- Emetteur: `FA 91`
- Destinataire: `MONSIEUR DIAMONDE`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE BD MIPA | vtc | 6062 | Fournitures consommables | 48.49 | rejeter |
| 2 | 1KG PEINTURE SLV MIPA | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 3 | SPATULE JAPONAISE | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.68 | rejeter |

## Facture 18
- Invoice ID: `fr_bd_877701128:04a5aa28-d8e5-4d01-8e5c-2b7ebaf66d1f`
- Numero: `3400`
- Date: `22/02/2025`
- Emetteur: `FA 91`
- Destinataire: `HMCARSCARROSSERIE`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV | btp | 6061 | Fournitures non stockables (eau, énergie) | 50.94 | rejeter |

## Facture 19
- Invoice ID: `fr_bd_877701128:04b19a63-8b5c-4f43-87e4-7bd6e532b797`
- Numero: `3007`
- Date: `08/01/2025`
- Emetteur: `FA 91`
- Destinataire: `BEINTRANSPORTS`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | EPONGE2000 | btp | 6061 | Fournitures non stockables (eau, énergie) | 49.06 | rejeter |
| 2 | PATE | vtc | 626 | Frais postaux et de télécommunications | 59.31 | rejeter |
| 3 | EPONGE NOIR | global | 6068 | Autres matières et fournitures | 52.82 | rejeter |

## Facture 20
- Invoice ID: `fr_bd_877701128:054d9c8f-3f82-47e1-bf4b-d4e817d71a2f`
- Numero: `3354`
- Date: `17/02/2025`
- Emetteur: `FA 91`
- Destinataire: `CLIENT COMPTOIR`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | FILTRE CABINE | vtc | 615 | Entretien et réparations | 60.05 | rejeter |
| 2 | PEINTURE SULVENTE 300G MIPA | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |

## Facture 21
- Invoice ID: `fr_bd_877701128:0550ab88-106e-4d51-9aec-4a3514c04328`
- Numero: `625060369`
- Date: `28/06/2025`
- Emetteur: `SEVA`
- Destinataire: `FA 91`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | Moteur d'occasion HYUNDAI IX 35 PHASE 1 1.7 CRDI - 16V TURBO LP:100993 Garantie commerciale : 6 mois CODE MOTEUR:D4FD/Z57712AZ00 - Numéro moteur : Z57712AZ00 - KILOMETRAGE 283092 Km - MOTEUR GARANTIE 6 MOIS HORS FRAIS DE MONTAGE ET FRAIS DE PORT, -VOITUREDONNEUSE:HYUNDAI IX 35 PHASE1 -VIN : U5YZU81UABL087048 MOTEUR TOUJOURS MONTER SUR LE VEHICULE (DELAI 72H POUR DEMONTAGE) MOTEUR TESTER AVANT DEMONTAGE GARANTIE APPLIQUE UNIQUEMENT SUR LE MOTEUR - MOTEUR VENDUE SANS ALTERNATEUR, SANS DEMARREUR, SANS COMPRESSEUR DE CLIM ET SANS BOITE TOUTES PIECES LAISSER SUR LE MOTEUR EST FOURNIS A TITRE GRACIEUX ET NE FONT PARTIES DE LA GARANTIE - LA GARANTIE PRENDRA EFFET SOUS PRESENTATION DE FACTURE DES PIECES QUI DOIVENT ETRE SYSTEMATIQUEMENT REMPLACES PAR D'AUTRES NEUF: VIDANGE COMPLET, BOUGIES D'ALLUM | global | 6068 | Autres matières et fournitures | 43.75 | rejeter |

## Facture 22
- Invoice ID: `fr_bd_877701128:0576cef8-4e89-4f1c-922d-44da132de48f`
- Numero: `3114`
- Date: `23/01/2025`
- Emetteur: `FA 91`
- Destinataire: `AI`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | 1KG SLV DEBEER | btp | 6011 | Achats stockés - Matières premières | 48.57 | rejeter |
| 2 | PEINTURESLV DEBBER | btp | 6061 | Fournitures non stockables (eau, énergie) | 48.31 | rejeter |

## Facture 23
- Invoice ID: `fr_bd_877701128:061a8a79-836d-4eec-a48a-5ca19c4e015b`
- Numero: `N3340`
- Date: `15/02/2025`
- Emetteur: `FA 91`
- Destinataire: `TH`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | feu arr gauche ford | transport | 6062 | Fournitures consommables | 52.97 | rejeter |

## Facture 24
- Invoice ID: `fr_bd_877701128:06c4b355-792e-4653-ae2a-3e90fadf22fe`
- Numero: `N3090`
- Date: `20/01/2025`
- Emetteur: `FA 91`
- Destinataire: `TH`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | BOMBE SLV | btp | 6061 | Fournitures non stockables (eau, énergie) | 52.44 | rejeter |

## Facture 25
- Invoice ID: `fr_bd_877701128:074b8bdd-984d-4d0d-a4be-fd3d3abe455c`
- Numero: `3769`
- Date: `31/03/2025`
- Emetteur: `FA 91`
- Destinataire: `KDSAUTO`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV MIPA | vtc | 6062 | Fournitures consommables | 48.44 | rejeter |

## Facture 26
- Invoice ID: `fr_bd_877701128:0916ab8a-9c03-4efc-abf8-9908fcae80ca`
- Numero: `3395`
- Date: `21/02/2025`
- Emetteur: `FA 91`
- Destinataire: `BOUTELBABOUDJMA`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | KIT VERNIS Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 48.64 | rejeter |

## Facture 27
- Invoice ID: `fr_bd_877701128:0952224c-e2d7-419e-8893-a91ffb959568`
- Numero: `3436`
- Date: `27/02/2025`
- Emetteur: `FA 91`
- Destinataire: `PREMIEUM CARS`
- Lignes: `8`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE A EAU | vtc | 6063 | Fournitures d'entretien et de petit équipement | 54.96 | rejeter |
| 2 | PEINTURE SLV MIPA | vtc | 6062 | Fournitures consommables | 48.44 | rejeter |
| 3 | Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 58.44 | rejeter |
| 4 | PAPIER | global | 6061 | Fournitures non stockables (eau, énergie) | 60.7 | rejeter |
| 5 | DURCISSEUR | btp | 6061 | Fournitures non stockables (eau, énergie) | 54.69 | rejeter |
| 6 | EPONGE | btp | 6063 | Fournitures d'entretien et de petit équipement | 60.7 | rejeter |
| 7 | SKOTCH BRIDJ | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 8 | BOMBE GRANULET | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |

## Facture 28
- Invoice ID: `fr_bd_877701128:09d78ffc-d620-4e50-a53a-30fff5e74d8e`
- Numero: `3683`
- Date: `25/03/2025`
- Emetteur: `FA 91`
- Destinataire: `SAM`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV DEBBER 300G | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 2 | Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 58.44 | rejeter |
| 3 | EPANGE | btp | 6061 | Fournitures non stockables (eau, énergie) | 50.94 | rejeter |

## Facture 29
- Invoice ID: `fr_bd_877701128:0a67c3b1-b3d3-46b0-b375-675a097de771`
- Numero: `2977`
- Date: `06/01/2025`
- Emetteur: `FA 91`
- Destinataire: `PREMIEUMCARS`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PPS Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 54.69 | rejeter |
| 2 | RUBONADH Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 49.38 | rejeter |
| 3 | CACHE PORTE Divers | btp | 6063 | Fournitures d'entretien et de petit équipement | 51.06 | rejeter |

## Facture 30
- Invoice ID: `fr_bd_877701128:0b7c2823-ad46-4341-9464-b7cf687e72a1`
- Numero: `3358`
- Date: `18/02/2025`
- Emetteur: `FA 91`
- Destinataire: `GARAGEAUTO CHOISY`
- Lignes: `7`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | DILUANT | btp | 6061 | Fournitures non stockables (eau, énergie) | 53.82 | rejeter |
| 2 | PAPIER DE PONSSAGE MIRKA P800 | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 3 | BOMBE D'APPRET MIPA | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 4 | EPONGE BLANC | vtc | 6068 | Autres matières et fournitures | 53.69 | rejeter |
| 5 | MASTIC PREMIEUM | btp | 6061 | Fournitures non stockables (eau, énergie) | 50.2 | rejeter |
| 6 | PEINTURE SULVENTE 300G MIPA | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 7 | PLATEAU | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.9 | rejeter |

## Facture 31
- Invoice ID: `fr_bd_877701128:0bba71cf-c2b0-4ccb-adb5-67344a287eb7`
- Numero: `2976`
- Date: `06/01/2025`
- Emetteur: `FA 91`
- Destinataire: `GSU`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PISTOLET PEINTURE 1.3 | vtc | 615 | Entretien et réparations | 57.97 | rejeter |

## Facture 32
- Invoice ID: `fr_bd_877701128:0bcb4b00-2c12-4625-ba96-0ad877184c71`
- Numero: `3100`
- Date: `22/01/2025`
- Emetteur: `FA 91`
- Destinataire: `GMCAUTO`
- Lignes: `4`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | DILUANT PEINTURE TROTON DILUANT | vtc | 615 | Entretien et réparations | 48.16 | rejeter |
| 2 | VERNIS MAT Divers | btp | 6061 | Fournitures non stockables (eau, énergie) | 48.64 | rejeter |
| 3 | PAPIER DE PONSSAGE MIRKA P80 P80MIRK | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 4 | 400GS PEINTURE SLV | vtc | 615 | Entretien et réparations | 48.71 | rejeter |

## Facture 33
- Invoice ID: `fr_bd_877701128:0c03e008-03b9-4688-bc3b-2ad634c5435a`
- Numero: `3254`
- Date: `10/02/2025`
- Emetteur: `FA 91`
- Destinataire: `RS MOTORS`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV MIPA | vtc | 6062 | Fournitures consommables | 48.44 | rejeter |

## Facture 34
- Invoice ID: `fr_bd_877701128:0cb0a033-57d5-4a30-b806-bbf6752868f8`
- Numero: `N2976`
- Date: `06/01/2025`
- Emetteur: `FA 91`
- Destinataire: `GSU`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PISTOLET PEINTURE 1.3 | vtc | 615 | Entretien et réparations | 57.97 | rejeter |

## Facture 35
- Invoice ID: `fr_bd_877701128:0cf38c62-bdb0-4574-9eb7-784a574b4c95`
- Numero: `3753`
- Date: `29/03/2025`
- Emetteur: `FA 91`
- Destinataire: `GARAGE GHAUTO`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV MIPA | vtc | 6062 | Fournitures consommables | 48.44 | rejeter |
| 2 | COLLE A JOINT GRIS | btp | 601 | Achats stockés - Matières premières (et fournitures) | 70.27 | validation_humaine |
| 3 | COLLE A PARE BRISE | btp | 601 | Achats stockés - Matières premières (et fournitures) | 60.52 | rejeter |

## Facture 36
- Invoice ID: `fr_bd_877701128:0dfd3ba6-8228-4dd2-a4fd-5546b927aabd`
- Numero: `3078`
- Date: `17/01/2025`
- Emetteur: `FA 91`
- Destinataire: `KANE AUTO`
- Lignes: `2`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | KITE VERNIS | btp | 6061 | Fournitures non stockables (eau, énergie) | 48.76 | rejeter |
| 2 | PAPIER P80 P150 P240 P320 P400 | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |

## Facture 37
- Invoice ID: `fr_bd_877701128:0e819a0e-fc90-4806-b4eb-cf398f3c0d49`
- Numero: `3398`
- Date: `21/02/2025`
- Emetteur: `FA 91`
- Destinataire: `INCONNU`
- Lignes: `5`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | VERNIS | btp | 6061 | Fournitures non stockables (eau, énergie) | 50.94 | rejeter |
| 2 | KIT APPRET DE CHARGE MIPA | global | 6062 | Fournitures consommables | 51.37 | rejeter |
| 3 | 1KG SULVENTE DEBBER | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 4 | PEINTURE SLV DEBBER | vtc | 615 | Entretien et réparations | 48.79 | rejeter |
| 5 | MASTIC FINITION GERKO | vtc | 6062 | Fournitures consommables | 46.42 | rejeter |

## Facture 38
- Invoice ID: `fr_bd_877701128:0e843349-de91-4244-8632-1c46aa6acff7`
- Numero: `N3019`
- Date: `10/01/2025`
- Emetteur: `FA 91`
- Destinataire: `FIXACAR`
- Lignes: `1`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | KITAPPPRET | btp | 6061 | Fournitures non stockables (eau, énergie) | 49.06 | rejeter |

## Facture 39
- Invoice ID: `fr_bd_877701128:0fa5b8bb-8ca7-4549-94c0-608a2ea0a89d`
- Numero: `N3412`
- Date: `24/02/2025`
- Emetteur: `FA 91`
- Destinataire: `FIXA CAR`
- Lignes: `3`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | PEINTURE SLV DEBBER | vtc | 615 | Entretien et réparations | 48.79 | rejeter |
| 2 | PEINTURE SLV DEBBER | vtc | 615 | Entretien et réparations | 48.79 | rejeter |
| 3 | PEINTURE MIPA SLV | vtc | 6062 | Fournitures consommables | 49.3 | rejeter |

## Facture 40
- Invoice ID: `fr_bd_877701128:0fdc07e8-ca3b-4adc-b230-425df12d2f4c`
- Numero: `N3586`
- Date: `14/03/2025`
- Emetteur: `FA 91`
- Destinataire: `M3AM`
- Lignes: `8`

| # | Line item | Top 1 metier | Compte | Libelle | Score | Decision |
|---|---|---|---|---|---:|---|
| 1 | 200G SLV DEBEER | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 2 | 200G SLV DEBEER | btp | 6061 | Fournitures non stockables (eau, énergie) | 46.06 | rejeter |
| 3 | CACHE PORTE | btp | 6063 | Fournitures d'entretien et de petit équipement | 53.3 | rejeter |
| 4 | GANT DE TRAVAILE GERKO | global | 6068 | Autres matières et fournitures | 50.61 | rejeter |
| 5 | PEINTURE SLV MIPA | vtc | 6062 | Fournitures consommables | 48.44 | rejeter |
| 6 | NOIR GRANULEE NOIR | global | 6068 | Autres matières et fournitures | 54.17 | rejeter |
| 7 | BOMBE PRIMERE PLASTIQUE | btp | 6063 | Fournitures d'entretien et de petit équipement | 51.3 | rejeter |
| 8 | BOMBE DILUANT RACCORD | btp | 606 | Achats non stockés de matières et fournitures | 48.69 | rejeter |

