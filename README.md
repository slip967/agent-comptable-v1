# KeyManage AI

KeyManage AI est une plateforme de **comptabilité augmentée Human-in-the-Loop**. Elle automatise l’extraction et l’analyse des factures, propose les imputations comptables, applique des règles de confiance et transmet les cas incertains à un expert pour validation.

Le projet couvre le cycle complet : file d’analyse, contrôle humain, écritures validées, historique, indicateurs de performance, mémoire des corrections et export des factures fournisseurs vers Odoo.

## Architecture technique

| Couche | Technologies | Rôle |
|---|---|---|
| Frontend | React, Vite, Tailwind/CSS | Interface Analyse IA, Validation humaine, Historique, Performance et Écritures validées |
| Backend | Python, FastAPI, Uvicorn | API, orchestration des lots, workflow comptable et persistance locale |
| OCR / IA | OpenRouter, modèles texte et vision | Extraction des lignes, normalisation et proposition comptable |
| Données | CouchDB et stores JSON locaux | Factures sources, référentiels, mémoire IA et état de session |
| ERP | Odoo 17 via XML-RPC | Création des factures fournisseurs et pièces jointes PDF |
| Infrastructure locale | Docker Compose, PostgreSQL 15 | Exécution d’Odoo et de sa base PostgreSQL |

## Arborescence principale

```text
.
├── agent_local_v1/       # Backend FastAPI
│   ├── app/
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # Application React/Vite
│   ├── src/
│   ├── package.json
│   └── .env.example
├── tests/                # Suite de 32 tests Pytest
├── docker-compose.yml    # Odoo 17 + PostgreSQL 15
├── start.bat             # Démarrage rapide Windows
├── start.sh              # Démarrage rapide macOS/Linux
└── .env.example          # Vue d’ensemble de la configuration
```

> Le backend du dépôt se nomme `agent_local_v1` ; il correspond au dossier `backend` dans cette documentation.

## Prérequis

- Docker Desktop avec Docker Compose ;
- Python 3.10 ou supérieur ;
- Node.js 18 ou supérieur et npm ;
- une instance CouchDB accessible avec les bases métier attendues ;
- une clé OpenRouter valide pour les analyses IA réelles.

## Installation

### 1. Cloner et ouvrir le projet

```bash
git clone <url-du-depot>
cd agent-comptable-v1
```

### 2. Configurer les variables d’environnement

Les fichiers `.env` réels sont ignorés par Git. Ne commitez jamais de clé API, mot de passe ou chemin confidentiel.

Sous PowerShell :

```powershell
Copy-Item agent_local_v1/.env.example agent_local_v1/.env
Copy-Item frontend/.env.example frontend/.env
```

Sous macOS/Linux :

```bash
cp agent_local_v1/.env.example agent_local_v1/.env
cp frontend/.env.example frontend/.env
```

Renseignez au minimum `OPENROUTER_API_KEY`, `COUCHDB_DATABASE`, les paramètres Odoo et, si nécessaire, les correspondances de chemins PDF.

### 3. Installer les dépendances

Backend :

```bash
python -m venv .venv
```

Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r agent_local_v1/requirements.txt
pip install pytest
```

macOS/Linux :

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r agent_local_v1/requirements.txt
pip install pytest
```

Frontend :

```bash
cd frontend
npm install
cd ..
```

## Démarrage rapide en un clic

Les scripts démarrent, dans l’ordre :

1. Odoo 17 et PostgreSQL avec Docker Compose ;
2. le backend FastAPI sur `http://127.0.0.1:8000` ;
3. le frontend React sur `http://localhost:5173`.

Windows :

```powershell
.\start.bat
```

macOS/Linux :

```bash
chmod +x start.sh
./start.sh
```

Odoo est disponible sur `http://localhost:8069`. Lors de la première ouverture, créez ou sélectionnez la base indiquée par `ODOO_DB`.

## Démarrage manuel

Terminal 1 — Odoo et PostgreSQL :

```bash
docker compose up -d
```

Terminal 2 — backend FastAPI :

```bash
cd agent_local_v1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Documentation interactive de l’API : `http://127.0.0.1:8000/docs`.

Terminal 3 — frontend React :

```bash
cd frontend
npm run dev
```

## Tests et validation

La suite actuelle contient **32 tests unitaires et d’intégration** couvrant notamment le moteur de facture, le tri des lots, la mémoire IA, la réinitialisation de session, les signaux métier et l’export Odoo XML-RPC.

Depuis la racine du projet :

```bash
pytest -v
```

Équivalent recommandé si plusieurs installations Python coexistent :

```bash
python -m pytest -v
```

Validation du frontend :

```bash
cd frontend
npm run build
```

## Sécurité et livraison

- Les `.env`, clés privées, certificats, journaux et environnements virtuels sont exclus par `.gitignore`.
- Les fichiers `.env.example` ne contiennent que des valeurs fictives.
- La réinitialisation de session de test doit conserver CouchDB intacte.
- Vérifiez les paramètres Odoo et CouchDB avant tout déploiement hors poste local.

## Arrêt des services Docker

```bash
docker compose down
```

Les volumes Docker sont conservés. Pour une suppression volontaire des volumes Odoo/PostgreSQL, utilisez `docker compose down -v` uniquement après sauvegarde et validation explicite.
