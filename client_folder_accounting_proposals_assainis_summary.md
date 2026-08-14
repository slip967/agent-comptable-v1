# Rapport dossier client — ASSAINIS

_Généré le 2026-06-04 17:47_

---

## 1. Dossier testé

- **Recherche initiale** : `ASSAINIS`
- **Candidats testés** : `ASSAINIS`
- **Dossier retenu** : **ASSAINIS**

## 2. Résumé global

| Indicateur | Valeur |
|---|---|
| Factures analysées | 3 |
| Lignes totales | 5 |
| ✅ Auto OK | 0 |
| 🔶 Validation humaine | 2 |
| ❌ Rejetées | 3 |
| ⬜ Non comptables | 0 |
| Score moyen | 57.1% |
| Erreurs / ignorées | 0 |

## 3. Factures analysées

### Facture 1 — ASSAINIS
- **N°** : FA-0005352  |  **Date** : 31/08/2025
- **Client** : ASSAINIS
- **ID** : `fr_bd_878523547:00177ada-9dbc-4af8-829c-0aaa26c6892f`
- **Statut proposal** : `validation_required`
- **Lignes** : 2 total | ✅ 0 auto | 🔶 0 à valider | ❌ 2 rejet | ⬜ 0 non compta. | Score : 48.7%

#### Lignes principales

| # | Article | Compte | Score | Risque | Décision | Auto-post | Humain |
|---|---|---|---|---|---|---|---|
| 1 | CABINE AUTONOME STD - Votre location comprend | 6068 | 38% | 🔴 eleve | ❌ rejeter | ✗ | 🔶 oui |
| 2 | TRANS/ALL - TRANSPORT ALLER WC | 624 | 60% | 🔴 eleve | ❌ rejeter | ✗ | 🔶 oui |

### Facture 2 — LA PALETTE
- **N°** : C1108421  |  **Date** : 29/09/2025
- **Client** : ASSAINIS
- **ID** : `fr_bd_878523547:003a8055-494a-49b6-aaa6-1c5e77e379f2`
- **Statut proposal** : `validation_required`
- **Lignes** : 2 total | ✅ 0 auto | 🔶 1 à valider | ❌ 1 rejet | ⬜ 0 non compta. | Score : 60.5%

#### Lignes principales

| # | Article | Compte | Score | Risque | Décision | Auto-post | Humain |
|---|---|---|---|---|---|---|---|
| 1 | PROJECTEUR HALOGENE 400W SUR PIEDS | 6061 | 54% | 🔴 eleve | ❌ rejeter | ✗ | 🔶 oui |
| 2 | 10 SACS GRAVATS TISSES 10U | 6063 | 66% | 🟡 moyen | 🔶 validation_humaine | ✗ | 🔶 oui |

#### Exemples par type de ligne

- **Article proche (fuzzy)** : _10 SACS GRAVATS TISSES 10U_ → compte **6063** Fournitures d'entretien et de petit équipement (score 66.5%)

### Facture 3 — IONOS
- **N°** : 202538691702  |  **Date** : 12/01/2025
- **Client** : ASSAINIS
- **ID** : `fr_bd_878523547:0044d4e3-9bec-47a4-809e-79098e071c67`
- **Statut proposal** : `validation_required`
- **Lignes** : 1 total | ✅ 0 auto | 🔶 1 à valider | ❌ 0 rejet | ⬜ 0 non compta. | Score : 62.2%

#### Lignes principales

| # | Article | Compte | Score | Risque | Décision | Auto-post | Humain |
|---|---|---|---|---|---|---|---|
| 1 | Frais d'abonnement - Contrat : 83812539 - ION | 6227 | 62% | 🟡 moyen | 🔶 validation_humaine | ✗ | 🔶 oui |

#### Exemples par type de ligne

- **Article proche (fuzzy)** : _Frais d'abonnement - Contrat : 83812539 - IONOS List Local Essential (11.01.2025-11.02.2025)_ → compte **6227** Frais d'actes et de contentieux (score 62.2%)

## 5. Conclusion

Le moteur a analysé **3 facture(s)** du dossier **ASSAINIS** représentant **5 lignes**.

- **2 ligne(s) nécessitent une validation humaine** : l'article est proche d'une référence connue mais pas identique, ou le contexte métier est insuffisant pour automatiser.
- **3 ligne(s) rejetées** : aucun candidat fiable trouvé dans les bases de connaissance. Ces articles peuvent être ajoutés via la boucle d'enrichissement.

**Conclusion** : Ce dossier est exploitable pour une démo KeyManage. Le moteur retourne pour chaque facture une proposition d'écriture comptable structurée (`accounting_proposal`) avec score de confiance, niveau de risque, décision et flag de validation humaine. L'intégration dans le workflow KeyManage peut être déclenchée directement depuis le bloc `accounting_proposal` retourné par `POST /api/analysis/strong-invoice/{invoice_id}`.
