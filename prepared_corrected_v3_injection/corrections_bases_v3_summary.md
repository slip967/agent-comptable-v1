# Rapport corrections bases V3

## Synthèse par fichier

- base_produits_boucherie_clean_v2.json / clean_or_account_fix: 56
- base_produits_boulangerie_clean_v2.json / clean_or_account_fix: 182
- base_produits_btp_clean_v2.json / clean_or_account_fix: 83
- base_produits_epicerie_clean_v2.json / clean_or_account_fix: 412
- base_produits_epicerie_clean_v2.json / move_to_charges: 4
- base_produits_restaurant_clean_v2.json / clean_or_account_fix: 199
- base_produits_transport_clean_v2.json / clean_or_account_fix: 80
- base_produits_vtc_clean_v2.json / clean_or_account_fix: 117
- base_produits_vtc_clean_v2.json / move_to_charges: 37

## Lignes déplacées vers charges externes

- base_produits_epicerie_clean_v2.json: `Transaction CHATTOLA` -> compte `607`, sous_profil `autres_charges_externes`
- base_produits_epicerie_clean_v2.json: `OASIS FRAIS/FRAMB SLIM33CLX6` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_epicerie_clean_v2.json: `ATTIEKE FRAIS (a Peser)` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_epicerie_clean_v2.json: `Main d' uvre (2 jours d'intervention) Récupération du fluide, Dépose des unités, passage du cable électrique, passage des tuyaux frigorifique et mise en service` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `APPLE.COM/BILL LE 21/01/24 REF CB.XXXXX0648` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Remise offre couplage` -> compte `6068`, sous_profil `autres_charges_externes`
- base_produits_vtc_clean_v2.json: `Frais de service pour les courses Uber` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Prix de la course (frais de service Uber inclus)` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Carte 1021245 apple.com/bill le 21/08/23 cb.xxx xx0648 origine irl 854 eur` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Redevance OTC` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Remise Commerciale` -> compte `609`, sous_profil `autres_charges_externes`
- base_produits_vtc_clean_v2.json: `APPLE.COM/BILL` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `CONTRAT SERVICE EXTEND PLUS` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Deposer, poser les inserts decoratifs et les pieces rapportees, concerne pour remise en etat. carrosserie/ mise en peinture` -> compte `6062`, sous_profil `autres_charges_externes`
- base_produits_vtc_clean_v2.json: `Vos communications (du 02/04 au 01/05)` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE STORE R27 LE 27/12/24 REF CB.XXXXX5891` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE STORE R59 LE 16/01/24` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE STORE R59 LE 16/01/24 REF CB.XXXXX0648` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Remise offre couplage (TVA 20)` -> compte `6061`, sous_profil `autres_charges_externes`
- base_produits_vtc_clean_v2.json: `Vos services fournis par des tiers - Appels a tarification majorée` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE - APPLE` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE STORE R315` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `APPLE.COM/BILL Carte 0017` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `BIENS.SERVICE` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `CRISTALINE EAU 24 50CL` -> compte `6061`, sous_profil `energie_eau`
- base_produits_vtc_clean_v2.json: `Carte 1006672 apple store r67 le 04/09/23 cb.xxx xx0648 origine fra 85900 eur` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Carte 1081803 apple.com/bill le 21/10/23` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Carte apple store` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Carte apple.com/bill` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Eau de Parfum Pour lui Amber Malaki 80 mL Vaporisateur` -> compte `6061`, sous_profil `energie_eau`
- base_produits_vtc_clean_v2.json: `Eau de Parfum Pour lui Oud Malaki 80 mL Vaporisateur` -> compte `6061`, sous_profil `energie_eau`
- base_produits_vtc_clean_v2.json: `Frais (BHN/PTT)` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Frais de réservation` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Mauboussin - Pour Lui Cristal Oud 100ml - Eau De Parfum Homme - Senteur Orientale` -> compte `6061`, sous_profil `energie_eau`
- base_produits_vtc_clean_v2.json: `PAIEMENT CB 1901 FR PARIS APPLE STORE R675 CARTE 01732670` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Remise sur Galaxy S24` -> compte `6097`, sous_profil `autres_charges_externes`
- base_produits_vtc_clean_v2.json: `Service non spécifié` -> compte `6227`, sous_profil `frais_administratifs_et_bancaires`
- base_produits_vtc_clean_v2.json: `Vos communications (du 02/08 au 01/09)` -> compte `6261`, sous_profil `telecom_et_abonnements`
- base_produits_vtc_clean_v2.json: `Vos communications (du 02/10 au 01/11)` -> compte `6261`, sous_profil `telecom_et_abonnements`