# Regles De Correspondance V1

## Objectif

Ce document fixe les regles minimales pour proposer un rattachement d'article a partir d'une ligne de facture reelle.

## 1. Selection De La Base

- Si la facture concerne un metier connu, interroger d'abord la base metier correspondante.
- Si la ligne ressemble a un service, abonnement, loyer, frais, entretien, transport ou contribution, interroger `base_charges_externes_v1.json`.
- Si le metier n'est pas certain, commencer par la base metier la plus probable, puis verifier la base charges externes.

## 1.bis Sous-Profils Charges Externes

- Les charges externes doivent etre segmentees en sous-profils exploitables : `telecom_et_abonnements`, `energie_electricite`, `energie_gaz`, `assurances`, `loyers_et_charges_locatives`, `entretien_et_maintenance`, `transport_et_logistique`, `cotisations_professionnelles`, `frais_administratifs_et_bancaires`.
- Chaque sous-profil peut porter une logique de releve differente dans le profil de facturation.
- Pour les sous-profils `telecom_et_abonnements`, `energie_electricite` et `energie_gaz`, relever au minimum la periode, la part abonnement et la part consommation si elles sont presentes.
- Pour `assurances`, relever la periode couverte et la prime.
- Pour `loyers_et_charges_locatives`, relever la periode, le loyer et les charges lorsqu'elles sont detaillees.

## 2. Priorite Des Matchs

- Priorite 1 : match exact sur `article_source`.
- Priorite 2 : match normalise sur `article_source`.
- Priorite 3 : match normalise sur `article_canonique`.
- Priorite 4 : match par mots cles (`mots_cles`) si au moins 2 mots significatifs coincident.

## 3. Normalisation Du Texte

- Mettre en minuscules.
- Supprimer les accents pour le matching.
- Remplacer la ponctuation par des espaces.
- Reduire les espaces multiples.
- Ignorer les differences de casse simples.

## 4. Regles De Validation

- Un article est `source_ok` s'il a au moins un `source_invoice_id`.
- Un article sans `source_invoice_id` doit etre marque `a_revoir` et ne doit pas etre utilise comme reference forte.
- Si plusieurs lignes matchent, preferer celle qui a le plus de `source_invoice_ids`.
- Si deux lignes restent equivalentes, preferer celle dont `article_source` est le plus proche du libelle facture.

## 5. Controle TVA Et Coherence

- TVA `5.5` : attendu surtout sur les produits alimentaires.
- TVA `20.0` : attendu surtout sur les services, abonnements, entretien, emballages et frais.
- TVA `0.0` : a verifier manuellement si le libelle ne correspond pas a un cas attendu.
- Si le libelle ressemble a un produit alimentaire mais que la TVA parait atypique, marquer `a_revoir`.

## 6. Cas A Revoir

- Libelle mal encode.
- Libelle trop generique : `facture`, `solde`, `prestation`, `services`.
- Ligne administrative ou bruit OCR.
- Ligne presente dans une mauvaise base metier.
- Ligne sans source facture reelle.

## 7. Sortie Attendue Du Matcher

Pour chaque ligne de facture, retourner :

- `base_cible`
- `article_source_match`
- `article_canonique`
- `score_confiance`
- `raison_match`
- `tva_coherence`
- `metier_coherence`
- `alertes`
- `source_invoice_ids`
- `decision_initiale`
- `decision_finale`

## 8. Decision

- `auto_ok` : match exact ou tres fort avec source facture.
- `validation_humaine` : match partiel, ambigu ou TVA douteuse.
- `rejeter` : aucune reference fiable.

## 9. Application Des Controles

- Si la TVA de la ligne est incoherente avec la reference, la sortie finale doit passer en `validation_humaine`.
- Si le metier attendu est incoherent avec la reference proposee, la sortie finale doit passer en `validation_humaine`.
- Une ligne reste `auto_ok` seulement si le match est fort et que les controles de coherence ne remontent pas d'alerte bloquante.
