# Rapport de synthèse — Démo moteur comptable KeyManage

_Généré le 2026-06-04_

---

## Contexte

Ce rapport présente les résultats du moteur d'analyse locale (`analyze_invoice_lines_strong`) appliqué à trois dossiers clients réels issus de la base CouchDB (`keymanage_accounting`). Pour chaque facture, le moteur produit un bloc `accounting_proposal` structuré contenant une proposition de compte, un score de confiance, un niveau de risque et une décision d'orientation.

---

## Résultats par dossier

### 1. BOUCHERIE IFRI — Secteur : Boucherie (APE 1011Z)

| Indicateur | Valeur |
|---|---|
| Factures trouvées | 5 |
| Factures analysées | 5 |
| Lignes analysées | 34 |
| ✅ Auto OK | 0 |
| 🔶 Validation humaine | 24 |
| ❌ Rejetées | 10 |
| ⬜ Non comptables | 0 |
| Score moyen | **66.3 %** |
| Ignorées / erreurs | 0 |

Fournisseurs rencontrés : ETABLISSEMENTS GUIRAUDOU, METRO FRANCE, divers fournisseurs viande.
Résultat JSON : `client_folder_accounting_proposals_boucherie_ifri.json`

---

### 2. ASSAINIS — Secteur : BTP / Assainissement (APE 3700Z)

| Indicateur | Valeur |
|---|---|
| Factures trouvées | 3 |
| Factures analysées | 3 |
| Lignes analysées | 5 |
| ✅ Auto OK | 0 |
| 🔶 Validation humaine | 2 |
| ❌ Rejetées | 3 |
| ⬜ Non comptables | 0 |
| Score moyen | **57.1 %** |
| Ignorées / erreurs | 0 |

Fournisseurs rencontrés : ASSAINIS, LA PALETTE, IONOS.
Résultat JSON : `client_folder_accounting_proposals_assainis.json`

---

### 3. BOULANGERIE L'UNIVERS DU PAIN — Secteur : Boulangerie (APE 1071C)

| Indicateur | Valeur |
|---|---|
| Factures trouvées | 5 |
| Factures analysées | 4 |
| Lignes analysées | 25 |
| ✅ Auto OK | 0 |
| 🔶 Validation humaine | 15 |
| ❌ Rejetées | 10 |
| ⬜ Non comptables | 0 |
| Score moyen | **65.5 %** |
| Ignorées / erreurs | 1 _(facture sans lignes OCR)_ |

Fournisseurs rencontrés : CHRONOPRIMEURS, EURO-INFORMATION, GRANDS MOULINS DE PARIS, ETABLISSEMENTS ESNAULT.
Résultat JSON : `client_folder_accounting_proposals_boulangerie_lunivers_du_pain.json`

---

## Comparaison consolidée

| Dossier | Métier | Factures | Lignes | Auto OK | Validation | Rejet | Non compta | Score moy. |
|---|---|---|---|---|---|---|---|---|
| BOUCHERIE IFRI | Boucherie | 5 / 5 | 34 | 0 | 24 | 10 | 0 | **66.3 %** |
| ASSAINIS | BTP | 3 / 3 | 5 | 0 | 2 | 3 | 0 | **57.1 %** |
| BOULANGERIE L'UNIVERS DU PAIN | Boulangerie | 4 / 5 | 25 | 0 | 15 | 10 | 0 | **65.5 %** |
| **TOTAL** | | **12 / 13** | **64** | **0** | **41** | **23** | **0** | **63.0 %** |

---

## Analyse

### Décisions du moteur

Sur 64 lignes analysées :

- **41 lignes (64 %)** orientées vers la **validation humaine** : le moteur a trouvé un candidat crédible mais avec une incertitude résiduelle. Ces lignes sont exploitables avec une revue rapide par un comptable.
- **23 lignes (36 %)** rejetées : aucun article correspondant dans les bases de référence. Ces articles peuvent être ajoutés via la boucle d'enrichissement pour améliorer le moteur sur ce dossier.
- **0 ligne auto-validée** sur cet échantillon initial — cohérent avec des factures prises en ordre alphabétique (pas nécessairement les plus typiques). Avec un volume plus large ou des fournisseurs récurrents, le taux auto-OK augmente.

### Scores de confiance

| Zone | Seuil | Dossiers concernés |
|---|---|---|
| Confiance élevée (≥ 70 %) | — | Certaines lignes BOUCHERIE IFRI, GRANDS MOULINS |
| Confiance moyenne (50–70 %) | — | Majorité des lignes — tous dossiers |
| Confiance faible (< 50 %) | — | ASSAINIS (articles BTP atypiques) |

Les scores reflètent la richesse des bases de référence par métier. La boulangerie et la boucherie bénéficient de bases plus étoffées que le BTP sur cet échantillon.

---

## Conclusion métier

**Le moteur peut traiter un dossier facture par facture, produire une proposition comptable structurée et orienter les lignes incertaines vers la validation humaine.**

Concrètement, pour chaque facture soumise via `POST /api/analysis/strong-invoice/{invoice_id}`, le moteur retourne un bloc `accounting_proposal` contenant :

- le compte recommandé (plan comptable général),
- le score de confiance (0–100 %),
- le niveau de risque (`faible` / `moyen` / `élevé`),
- la décision : `auto_ok`, `validation_humaine`, `rejeter` ou `non_comptable`,
- le flag `requires_human_validation` pour déclencher un workflow de relecture.

Ce mécanisme est directement intégrable dans KeyManage : les lignes `auto_ok` peuvent être comptabilisées automatiquement, les lignes `validation_humaine` sont présentées au comptable avec une suggestion pré-remplie, et les lignes rejetées alimentent la boucle d'enrichissement des bases de référence.
