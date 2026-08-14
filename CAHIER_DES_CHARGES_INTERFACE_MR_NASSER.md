# Cahier Des Charges Interface - Agent Comptable AI

Etat d'avancement au 22 avril 2026

## 1. Objet Du Document

Ce document recense le perimetre deja realise dans l'interface de l'application `Agent Comptable AI`.

L'objectif est de presenter a M. Nasser :
- ce qui est deja disponible a l'ecran pour l'utilisateur,
- les parcours deja couverts,
- les informations deja exposees par l'interface,
- la logique de validation et de relecture actuellement accessible.

Le document porte sur l'interface frontend connectee au backend local de recommandation comptable.

## 2. Objectif Produit Cote Interface

L'interface a pour but de permettre un usage comptable ligne par ligne avec quatre besoins principaux :
- lancer une analyse comptable a partir d'un libelle de facture,
- comprendre la recommandation produite par le moteur,
- valider, corriger ou rejeter la decision,
- consulter l'historique et la file de validations humaines.

L'interface integre aussi un assistant IA contextuel pour expliquer les decisions et guider l'utilisateur sur l'action suivante.

## 3. Perimetre Fonctionnel Deja Livre

### 3.1. Coque Applicative Et Navigation

L'interface dispose deja d'une coque applicative complete avec :
- un en-tete produit `Agent Comptable AI`,
- un indicateur d'etat du systeme `en ligne / hors ligne`,
- un bouton d'ouverture rapide de l'assistant,
- un changement de theme `clair / sombre`,
- un changement de mode `simple / expert`,
- une navigation par onglets entre `Analyse`, `Dashboard` et `Historique`.

Les preferences utilisateur suivantes sont deja memorisees localement :
- dernier theme choisi,
- dernier mode d'affichage choisi,
- dernier onglet ouvert.

## 4. Ecran Analyse

### 4.1. Formulaire D'Entree

L'ecran `Analyse` permet deja d'envoyer une ligne au backend.

Les champs actuellement disponibles sont :
- `Libelle de ligne facture` obligatoire,
- `Fournisseur` optionnel,
- `Metier` optionnel,
- `TVA` optionnelle,
- case a cocher `Inclure les charges externes dans la recherche`.

Le formulaire a ete clarifie pour montrer que :
- le libelle seul suffit a lancer une analyse,
- le metier et la TVA peuvent etre ajoutes plus tard,
- le fournisseur peut enrichir le contexte sans etre obligatoire.

### 4.2. Etats D'Interaction

L'ecran gere deja :
- l'etat de chargement `Analyse en cours...`,
- les erreurs API,
- l'etat vide avant toute analyse.

## 5. Panneau Resultat

### 5.1. Restitution Principale

Quand une analyse est disponible, l'interface affiche deja :
- le libelle analyse,
- une explication textuelle de la decision,
- la source de la reponse,
- la decision finale,
- le compte comptable propose,
- la categorie,
- la sous-categorie,
- le score de confiance.

### 5.2. Sources De Decision

La source du resultat est deja visible avec une distinction entre :
- `Moteur`,
- `Memoire`,
- `IA`.

Quand la recommandation provient de la memoire, un bandeau specifique est affiche pour indiquer qu'une validation humaine precedente a ete reutilisee.

### 5.3. Entry Ranker Et Signaux

L'interface affiche deja un bloc `Entry Ranker` qui expose les signaux utilises pour la decision.

Les familles de signaux deja visibles sont :
- `Signal fort`,
- `Signal moyen`,
- `Signal faible`.

Pour chaque signal, l'interface montre deja :
- le nom du signal,
- sa valeur,
- sa contribution au score,
- une explication.

Exemples de signaux deja visibles :
- validation humaine precedente,
- fournisseur deja vu,
- TVA coherente,
- metier coherent,
- similarite texte.

## 6. Actions Utilisateur Sur Le Resultat

### 6.1. Feedback Direct

Depuis le panneau resultat, l'utilisateur peut deja :
- `Valider`,
- `Modifier`,
- `Rejeter`.

Ces actions sont connectees au backend via `/feedback`.

### 6.2. Mode Modifier

Le mode `Modifier` est deja un vrai mode d'edition manuelle.

L'utilisateur peut deja corriger :
- `compte_comptable`,
- `categorie`,
- `sous_categorie`,
- `commentaire`.

Le formulaire de correction gere deja :
- l'enregistrement de la correction,
- l'annulation,
- le rechargement de la decision corrigee.

## 7. Mode Expert Et Top 3 Candidats

### 7.1. Affichage En Mode Expert

Le mode `expert` affiche deja le `Top 3` des candidats retournes par le moteur.

Pour chaque candidat, l'interface montre deja :
- le rang,
- le compte comptable,
- le score,
- le libelle de reference retenu,
- la categorie,
- la sous-categorie,
- le metier,
- la decision candidate,
- la coherence TVA,
- la coherence metier.

### 7.2. Panneau Detail Candidat

Le candidat selectionne peut deja etre ouvert dans un panneau lateral qui affiche :
- le compte,
- le score final,
- le score texte,
- la TVA,
- le metier,
- la classification complete,
- la raison de match,
- les signaux du score,
- les alertes,
- les pieces sources rattachees quand elles existent.

Depuis ce panneau, l'utilisateur peut deja :
- utiliser un candidat dans le mode `Modifier`,
- demander l'avis de l'assistant sur le candidat actif.

### 7.3. Mode Simple

Le mode `simple` masque volontairement :
- le `Top 3`,
- les details moteurs,
- les panneaux experts.

L'interface informe deja l'utilisateur que ces informations restent accessibles en basculant en mode expert.

## 8. Dashboard

### 8.1. Vision D'Ensemble

L'onglet `Dashboard` propose deja une vue de pilotage avec :
- un statut global,
- un titre de synthese,
- un texte de resume,
- des indicateurs rapides.

Les metriques de synthese deja visibles sont :
- `Taux auto OK`,
- `A traiter`,
- `Memoire`,
- `Rejets`.

### 8.2. Cartes KPI

Le dashboard affiche deja des cartes de suivi pour :
- `Historique charge`,
- `Auto OK recents`,
- `Validation humaine`,
- `Analyses memoire`,
- `Rejets recents`.

Chaque carte comporte deja :
- un label metier,
- une valeur principale,
- un texte d'aide court,
- une tonalite visuelle differenciee.

### 8.3. File Humaine

Le dashboard integre deja une vraie `File humaine` de validations.

Pour chaque ligne a traiter, l'utilisateur voit deja :
- le libelle,
- le compte propose,
- le score,
- la date,
- l'explication.

Chaque ligne de file peut deja :
- etre chargee dans l'espace d'analyse,
- etre `Validee`,
- etre `Corrigee`.

## 9. Historique

### 9.1. Liste D'Historique

L'onglet `Historique` permet deja de consulter les analyses ligne par ligne.

L'utilisateur dispose deja de :
- une recherche rapide,
- un filtre par decision,
- un bouton de rafraichissement,
- une liste d'analyses recentes.

Chaque ligne d'historique affiche deja :
- le libelle,
- le score,
- la decision,
- le compte,
- la date,
- l'explication.

### 9.2. Detail D'Une Ligne

Le panneau detail de l'historique affiche deja :
- le libelle,
- l'explication,
- la decision,
- le compte,
- le score,
- le metier,
- le fournisseur,
- la source,
- la TVA,
- la categorie,
- la sous-categorie,
- l'option `inclure charges`,
- l'horodatage,
- la cle de recherche.

### 9.3. Signaux Conserves

Quand des signaux ont ete stockes avec l'analyse, l'interface sait deja afficher :
- les signaux de ranking conserves,
- leur famille,
- leur valeur,
- leur contribution,
- leur explication.

### 9.4. Top 3 Conserve

L'historique conserve deja le `Top 3` des nouvelles analyses, quand il existe.

Le detail historique peut deja afficher :
- les candidats conserves,
- leur rang,
- leur compte,
- leur score,
- leur libelle,
- leur classification,
- leur raison de match.

### 9.5. Actions Depuis L'Historique

Depuis une ligne d'historique, l'utilisateur peut deja :
- charger la ligne dans l'espace d'analyse,
- la valider directement,
- la corriger directement.

## 10. Assistant IA Contextuel

### 10.1. Disponibilite

L'assistant IA est deja present en widget lateral toujours disponible.

Il peut deja :
- s'ouvrir,
- se reduire,
- etre vide manuellement,
- rester accessible pendant toute la navigation.

### 10.2. Contexte Charge

L'assistant charge deja un contexte courant comprenant au minimum :
- le libelle en cours,
- la decision actuelle,
- le compte propose,
- le score,
- le fournisseur quand il existe,
- le candidat actif si un candidat a ete selectionne.

### 10.3. Raccourcis Metier

Des prompts rapides sont deja proposes selon le contexte :
- avant analyse,
- pendant une correction,
- apres resultat,
- quand un candidat est selectionne.

Exemples deja presents :
- `Mode d'emploi`,
- `Que remplir ?`,
- `Explique la decision`,
- `Etape suivante`,
- `Que penser du candidat selectionne ?`,
- `Que dois-je corriger ici ?`

### 10.4. Conversation Et Actions

Le widget permet deja :
- d'envoyer un message libre,
- de lire l'historique des messages,
- de distinguer les messages utilisateur et assistant,
- d'afficher une action suggeree par l'assistant,
- d'executer directement cette action si elle est fournie.

Les actions suggerees deja prevues sont :
- `analyser`,
- `valider`,
- `modifier`,
- `rejeter`,
- `neutre`.

## 11. Design, Lisibilite Et UX

Les travaux interface deja realises incluent aussi plusieurs ameliorations de lisibilite et d'usage :
- theme clair / sombre,
- meilleure lisibilite en mode sombre,
- cartes dashboard plus propres et mieux proportionnees,
- contrastes renforces sur les chiffres, labels et cartes detail,
- barre de scroll de l'assistant rendue lisible en mode sombre,
- separation claire entre mode simple et mode expert,
- badges visuels pour les decisions,
- mise en avant de la source `Moteur / Memoire / IA`,
- scroll et composition du widget assistant corriges,
- conservation d'une presentation sobre et orientee produit metier.

L'interface dispose aussi de regles responsive pour rester exploitable sur des largeurs plus faibles.

## 12. Connexions Backend Deja Exploitees Par L'Interface

L'interface est deja connectee aux services suivants :
- `GET /health`
- `GET /memory/stats`
- `GET /analysis/history`
- `GET /validation-queue`
- `POST /recommend`
- `POST /feedback`
- `POST /assistant`

Cela signifie que l'interface n'est pas une maquette statique : elle consomme deja des donnees reelles du moteur local.

## 13. Resume De Ce Qui Est Deja Disponible Pour Une Demo

Aujourd'hui, l'interface permet deja de montrer un vrai parcours utilisateur :
- saisir une ligne de facture,
- obtenir une recommandation comptable,
- comprendre la source et les signaux du score,
- comparer les meilleurs candidats,
- valider, corriger ou rejeter la decision,
- consulter la file humaine,
- relire l'historique detaille,
- interroger un assistant IA contextuel.

## 14. Positionnement Actuel

L'interface est deja au stade d'un front metier operationnel pour :
- la demonstration,
- le test utilisateur,
- la validation fonctionnelle,
- le travail iteratif avec le backend.

Elle couvre deja les briques visibles les plus importantes du produit cote utilisateur :
- analyse,
- explication,
- validation humaine,
- memoire,
- historique,
- assistant IA.

## 15. Prochaine Etape Logique

La suite logique n'est plus de construire la coque de base, mais de renforcer progressivement :
- l'apprentissage apres correction humaine,
- les signaux metier plus forts,
- les regles de ranking,
- les donnees d'entree metier,
- l'industrialisation du traitement en lot.

