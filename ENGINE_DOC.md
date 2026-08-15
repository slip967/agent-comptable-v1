# Moteur de traitement des factures — état réel du code

Audit réalisé sur le frontend React, les routes FastAPI et les services d'analyse présents dans le dépôt. Ce document décrit le comportement effectivement implémenté, y compris les écarts entre l'interface et la persistance réelle.

## 1. Architecture réellement active

Deux chaînes d'analyse coexistent.

1. **Moteur principal de la page Analyse IA**
   - La page lance `POST /api/analysis/batch-run` ou l'analyse unitaire `POST /analysis/strong-invoice/{invoice_id}`.
   - Le backend lit des documents `invoice_form` déjà présents dans CouchDB.
   - Chaque ligne est rapprochée des référentiels métiers, scorée, puis classée `auto_ok`, `validation_humaine`, `rejeter` ou `non_comptable`.
   - Un garde-fou au niveau facture décide ensuite entre `VALIDE_AUTO` et `A_CONTROLER`.

2. **Ancienne chaîne upload/OCR/recommandation**
   - `POST /ocr/analyze-invoice` accepte un fichier, l'enregistre temporairement, appelle l'OCR distant OpenRouter, puis supprime le fichier temporaire.
   - `POST /analyze/ocr-text` analyse un texte OCR fourni.
   - `POST /recommend` traite une ligne et peut réutiliser directement une ancienne validation enregistrée via `POST /feedback`.
   - Cette chaîne reste disponible dans l'API, mais ce n'est pas celle utilisée par le traitement principal des lots de la page Analyse IA.

## 2. Pipeline exact du moteur principal

### 2.1 Sélection des factures

`fetch_unprocessed_invoices()` parcourt CouchDB via `/_all_docs?include_docs=true` et conserve uniquement les documents qui vérifient toutes les conditions suivantes :

- `p` ou `type` vaut `invoice_form` ;
- `document_type` vaut `Invoice` ;
- une collection de lignes exploitable existe ;
- l'identifiant n'est pas déjà présent parmi les résultats de lot marqués `persisted` dans le magasin local du moteur ;
- au moins une ligne n'est pas considérée comme une ligne non-article.

La lecture est paginée, avec une taille comprise entre 80 et 200 lignes CouchDB, et un budget de scan compris entre 2 500 et 20 000 documents. Le lot est plafonné à 100 factures.

Important : le moteur sélectionne d'abord au maximum `limit` factures selon l'ordre de parcours CouchDB, puis trie uniquement cet échantillon. Il ne trie donc pas la totalité de la base avant de sélectionner les N premières factures.

### 2.2 Extraction et normalisation

Pour un document CouchDB, les lignes sont recherchées successivement dans :

- `line_items` ;
- `invoice_form.line_items` ;
- `items`, `lines`, `invoice_lines`, `products` ;
- `form.line_items`, `fields.line_items`, `extracted.line_items`, `ocr.line_items` ;
- `data.line_items`, `document.line_items`.

Pour chaque ligne, le moteur construit un payload comprenant :

- texte source et texte nettoyé ;
- quantité et prix unitaire ;
- montant HT (`amount_ht` ou `total_net`) ;
- montant TTC (`amount_ttc` ou `total_gross`) ;
- taux de TVA (`tva` ou `vat_percent`).

Le contexte facture comprend notamment l'identifiant, le numéro, la date, la devise, le fournisseur, le client, les APE client/fournisseur et un métier inféré. Les noms et APE sont cherchés dans les objets `issuer`/`recipient` et dans plusieurs variantes de champs de premier niveau.

### 2.3 Analyse des lignes

Les lignes d'une même facture sont analysées en parallèle, avec un maximum de 6 workers. L'ordre de sortie reste celui des lignes d'entrée.

Pour chaque ligne :

1. le texte est normalisé ;
2. les lignes administratives ou non comptables sont écartées (`total`, TVA, IBAN, paiement, échéance, référence, etc.) ;
3. le matcher interroge les bases métiers avec le fournisseur, le métier, les APE, la TVA, la mémoire fournisseur et les patterns de validations ;
4. une seconde recherche sans filtre métier est ajoutée lorsqu'un métier avait été inféré ;
5. les candidats sont fusionnés et les 3 meilleurs sont conservés ;
6. à défaut de référentiel, une hypothèse contextuelle codée en dur peut proposer un compte pour certains domaines (télécom, carburant, alimentaire, BTP, réparation, etc.) ;
7. la ligne reçoit un compte de charge proposé, un score, un niveau de risque, un statut référentiel et une décision.

### 2.4 Proposition comptable

Le backend construit une `AccountingProposal` contenant les lignes de charge proposées. Il ne construit pas lui-même une écriture comptable complète débit/crédit.

Le frontend complète cette proposition au moment de l'affichage ou de la validation :

- débit du compte de charge recommandé pour le HT ;
- débit du compte `44566` pour la TVA déductible calculée ;
- crédit du compte fournisseur générique `401` pour le TTC.

Le compte de tiers n'est donc ni extrait ni individualisé par fournisseur : `401` est une valeur générique ajoutée côté React. Le journal, la date comptable, la pièce et un auxiliaire fournisseur ne sont pas déterminés par le backend.

## 3. Scoring et arbitrage

### 3.1 Score d'un candidat référentiel

Le score final est une moyenne pondérée renormalisée sur les signaux disponibles :

| Signal | Poids nominal |
|---|---:|
| Mémoire du fournisseur | 50 % |
| Validation humaine antérieure | 20 % |
| Similarité textuelle | 15 % |
| Couple APE client/fournisseur | 10 % |
| Cohérence TVA | 7,5 % |
| Cohérence métier | 7,5 % |

La somme nominale dépasse 100 %, mais seuls les signaux présents sont additionnés puis renormalisés à 100 %.

Le score textuel de départ vaut notamment :

- 100 pour une égalité brute avec `article_source` ;
- 96 pour une égalité normalisée avec `article_source` ;
- 90 pour une égalité normalisée avec `article_canonique` ;
- sinon, un score issu de la similarité de chaînes, du recouvrement de tokens et de bonus/malus contextuels.

Des bonus/malus supplémentaires interviennent avant le ranker, par exemple TVA identique `+4`, TVA différente `-4`, deux APE directs `+10`, un APE direct `+6`, contexte APE incohérent `-6`.

### 3.2 Décision interne du matcher

Le matcher classe initialement le candidat ainsi :

- `rejeter` si le métier est incohérent ;
- `auto_ok` si score final >= 92, confirmation forte, preuve réelle et TVA cohérente ;
- `validation_humaine` si score final >= 70 ;
- `rejeter` sinon.

Une confirmation forte existe si au moins une condition est satisfaite : score texte >= 90, mémoire fournisseur >= 0,75, validation humaine >= 0,72 ou signal APE >= 0,85.

Les garde-fous finaux rétrogradent vers la validation humaine si la TVA est incohérente ou si TVA/métier est seulement « à vérifier ».

### 3.3 Décision du moteur fort par ligne

Le moteur fort recalcule ensuite sa propre décision à partir du meilleur candidat :

- match exact brut d'`article_source` : `found_exact` puis `auto_ok` ;
- autre candidat avec score >= 50 : `found_fuzzy` ;
- `found_fuzzy` avec score >= 90 : `auto_ok` ;
- `found_fuzzy` entre 50 et 89,99 : `validation_humaine` ;
- hypothèse contextuelle avec score >= 50 : `validation_humaine` ;
- sinon : `rejeter`.

Un match exact voit sa confiance forcée à au moins 92. Les égalités seulement normalisées à 96/90 ne sont pas considérées comme `found_exact` par `_is_exact_candidate()` ; elles restent `found_fuzzy`.

### 3.4 Arbitrage final au niveau facture

Une facture devient `VALIDE_AUTO` uniquement si, pour **toutes** ses lignes comptables :

- `referential_status == found_exact` ;
- `decision == auto_ok` ;
- confiance >= 90 ;
- preuve `complete` ou `partial` ;
- l'équation `HT + TVA = TTC` est vérifiée à 0,02 près ;
- l'identifiant de facture n'est pas déjà enregistré.

Si une seule condition échoue, toute la facture devient `A_CONTROLER` et part vers la validation humaine. Une confiance moyenne inférieure à 50 marque la décision globale comme rejetée, mais le statut de workflow reste malgré tout `A_CONTROLER`.

Les lignes `non_comptable` sont exclues de cet arbitrage.

## 4. File d'attente, tri et exécution

Quatre stratégies sont disponibles :

- `DUE_DATE` : échéance croissante, avec repli sur la date de facture ;
- `CHRONO` : date de facture croissante ;
- `SUPPLIER` : fournisseur A-Z, puis date de facture ;
- `AMOUNT` : TTC décroissant, puis date de facture.

Le backend traite les factures du lot avec un seul worker (`batch_workers = 1`) afin de respecter exactement l'ordre trié. En revanche, les lignes internes à chaque facture utilisent jusqu'à 6 workers.

Arrêt et reprise :

- « Arrêter » pose `stop_requested` ; l'arrêt devient effectif après la facture en cours ;
- « Enregistrer » marque les résultats partiels comme persistés et route les factures à contrôler ;
- « Continuer » reprend à l'index `processed` du même échantillon trié ;
- un curseur `next_startkey` permet au prochain lot de poursuivre le parcours CouchDB.

Les résultats et jobs sont stockés dans `agent_local_v1/data/batch_analysis_results.json`, pas dans les documents facture CouchDB.

### Temps réel réellement implémenté

Le frontend ouvre bien un `EventSource` et sait recevoir `INVOICE_PROCESSED`/`INVOICE_ERROR`. Le backend définit aussi `_publish_invoice_result()`. Toutefois, cette fonction n'est appelée nulle part dans la boucle actuelle, et aucun événement terminal n'est publié non plus.

En pratique, la mise à jour en cours de lot est assurée par le polling de `GET /api/analysis/batch-jobs/{job_id}` toutes les 2,5 secondes. Le SSE n'envoie que le snapshot initial et des keep-alive. Le comportement est donc quasi temps réel par polling, pas un streaming par facture pleinement opérationnel.

## 5. Routage et persistance

### Facture à contrôler

Chaque ligne nécessitant un contrôle est ajoutée à `agent_local_v1/data/human_validation_queue.json`. Si aucune ligne ne satisfait le prédicat de contrôle, toutes les lignes comptables de la facture sont ajoutées. Des événements sont écrits dans `agent_local_v1/data/history_events.json`.

### Facture auto-validée ou validée par un humain

Les écritures visibles dans « Écritures validées » sont principalement enregistrées dans le `localStorage` du navigateur sous `keymanage.validated-accounting-entries.v1`. L'API `fetchValidatedEntries()` complète cette liste avec les éléments de la file humaine dont le statut vaut `validated`.

Il n'existe pas, dans le flux inspecté, de persistance backend unique d'une écriture comptable complète dans CouchDB. `_save_job_results_unlocked()` marque les résultats du JSON de lot comme `persisted` et effectue le routage ; il ne met pas à jour le document facture CouchDB.

## 6. Mémoire et apprentissage

Deux mémoires distinctes coexistent. La mémoire JSON issue de la Validation humaine est désormais raccordée directement au moteur fort ; la mémoire CouchDB historique reste utilisée comme signal du matcher générique.

### Mémoire historique consommée par le matcher

Le moteur principal appelle `get_supplier_memory()` et `get_validation_patterns()`. Ces fonctions lisent les validations de la base mémoire CouchDB (`MEMORY_COUCH_DB`, par défaut la base de référence). Elles renforcent :

- le compte déjà dominant pour un fournisseur ;
- un compte déjà validé pour un libellé/métier/fournisseur similaire ;
- le score final via les signaux fournisseur et validation humaine.

L'ancienne route `POST /feedback` alimente cette mémoire et permet même à `POST /recommend` de reprendre un précédent compte à 100 % de confiance.

### Mémoire créée par la Validation humaine actuelle

La page Validation humaine appelle `POST /api/human-validation/items/{id}/decision`. Cette route :

- met à jour `human_validation_queue.json` ;
- ajoute un événement historique ;
- écrit un résumé dans `ai_memory_items.json` pour les actions valider, corriger, non comptable ou proposer un enrichissement.

Le moteur charge désormais un instantané de `ai_memory_items.json` au démarrage de chaque lot. L'analyse unitaire relit cette mémoire à chaque appel. Avant le matcher générique :

- un libellé normalisé identique ou très proche réutilise le compte validé par l'expert ;
- une règle fournisseur est appliquée uniquement si le compte mémorisé est unique ou nettement dominant, afin d'éviter une affectation arbitraire ;
- une ligne mémorisée comme non comptable est reconnue comme telle ;
- une correspondance mémoire obtient une confiance de 100 %, une décision `auto_ok` et une justification indiquant l'origine humaine.

La route de validation actuelle n'appelle toujours pas `POST /feedback` : les deux mémoires restent techniquement séparées, mais les corrections de l'interface sont maintenant effectivement réinjectées dans le moteur principal via le fichier JSON.

## 7. Données extraites et données produites

### En-tête de facture

- identifiant, numéro, date et devise ;
- fournisseur, client/dossier ;
- APE fournisseur et client ;
- métier/activité inféré ;
- nombre total de lignes et nombre de lignes exploitables.

### Ligne de facture

- code produit, description brute et nettoyée, type d'article ;
- quantité, unité, prix unitaire, remise ;
- HT, TTC, taux et montant de TVA ;
- compte de charge recommandé et son libellé ;
- catégorie, sous-catégorie, activité, type fournisseur ;
- score, risque, décision, justification ;
- statut référentiel et qualité des preuves ;
- trois meilleurs candidats ;
- identifiants, chemins, partitions et APE des factures sources.

### Totaux et paiement disponibles dans le schéma OCR

- totaux HT, TVA et TTC ;
- remises, escompte, acompte et paiement anticipé ;
- mode, échéance et montant du paiement ;
- IBAN/BIC, coordonnées et adresses ;
- synthèse comptable éventuellement fournie par l'OCR.

Tous ces champs ne sont pas utilisés par le moteur fort. Celui-ci exploite principalement le libellé de ligne, les montants HT/TTC, le taux de TVA, le fournisseur, le client, les APE et le métier.

## 8. Points de vigilance prioritaires

1. **Base active contraire au garde-fou annoncé** : le fichier `agent_local_v1/.env` configure actuellement `COUCHDB_DATABASE=keymanage_accounting`. Le moteur de lot lit donc effectivement cette base. Aucun fallback de lecture seule séparé n'est imposé dans `invoice_engine_service.py`.
2. **SSE incomplet** : les fonctions de publication existent mais ne sont pas appelées ; seul le polling fonctionne réellement.
3. **Deux mémoires séparées** : le moteur fort consomme désormais le JSON de Validation humaine, mais ce JSON et la mémoire CouchDB de `/feedback` ne sont pas consolidés dans un magasin unique.
4. **Persistance comptable surtout locale** : les écritures validées et l'écriture débit/crédit synthétique vivent principalement dans le navigateur.
5. **Compte fournisseur générique** : le compte tiers est toujours `401` côté frontend, sans auxiliaire ni extraction fournisseur.
6. **Deux seuils historiques** : la chaîne OCR legacy affiche `Auto OK` à partir de 85 si la décision vaut déjà `auto_ok`, tandis que le moteur principal exige les garde-fous facture beaucoup plus stricts décrits ci-dessus.

## 9. Fichiers clés

- `agent_local_v1/app/invoice_engine_service.py` : extraction, analyse forte, routage facture.
- `10_match_reference_v1.py` : matching, signaux, score et décision candidat.
- `agent_local_v1/app/signal_ranker.py` : poids et renormalisation des signaux.
- `agent_local_v1/app/analysis_batch_service.py` : sélection, tri, jobs, arrêt/reprise et stockage des résultats.
- `agent_local_v1/app/routers/analysis_router.py` : API de lot et endpoint SSE.
- `agent_local_v1/app/routers/human_validation_router.py` : décisions humaines.
- `agent_local_v1/app/human_validation_store.py` : file humaine JSON.
- `agent_local_v1/app/ai_memory_service.py` : mémoire UI issue des validations.
- `agent_local_v1/app/database.py` et `memory.py` : mémoire CouchDB consommée par le matcher legacy/fort.
- `agent_local_v1/app/invoice_analysis.py` : chaîne upload/OCR legacy.
- `frontend/src/context/AnalysisBatchContext.jsx` : état React, SSE et polling.
- `frontend/src/pages/AnalysisPage.jsx` : contrôles de lot, inspection et génération débit/crédit frontend.
- `frontend/src/pages/ValidationPage.jsx` : validation/correction et transfert vers les écritures validées.
- `frontend/src/utils/validatedEntries.js` : persistance locale des écritures validées.
- `frontend/src/pages/HistoryPage.jsx` : affichage des événements de workflow.
- `frontend/src/pages/MemoryPage.jsx` : agrégation des métriques de lot, validation, historique et mémoire.
