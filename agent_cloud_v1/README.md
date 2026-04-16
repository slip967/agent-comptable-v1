# Agent Comptable Cloud V1

Le dossier contient maintenant deux entrees cloud:

- `line_item_app.py`: entree recommandee, reutilise l'API ligne par ligne stabilisee dans `agent_local_v1`
- `app.py`: prototype historique facture complete base sur `05_generated_entries.py`

## 1) Installation

```bash
cd scripts-master/agent_cloud_v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Variables d'environnement

Copier `.env.example` vers `.env` si tu lances localement, ou configurer ces variables dans Render:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `OPENROUTER_APP_URL`
- `OPENROUTER_APP_NAME`

## 3) Lancement local du cloud-ready line agent

```bash
cd scripts-master
uvicorn agent_cloud_v1.line_item_app:app --host 0.0.0.0 --port 8000 --reload
```

## 4) Test du line agent

```bash
curl -X POST "http://127.0.0.1:8000/recommend" ^
  -H "Content-Type: application/json" ^
  -d "{\"article_source\":\"Electricite mars 2025\",\"tva_hint\":20}"
```

Endpoints disponibles sur cette entree:

- `GET /health`
- `POST /recommend`
- `POST /feedback`
- `GET /memory/stats`

## 5) Prototype facture complete historique

Si tu veux garder le moteur facture complete existant:

```bash
cd scripts-master
uvicorn agent_cloud_v1.app:app --host 0.0.0.0 --port 8000 --reload
```

Le endpoint principal reste:

- `POST /recommend`

avec:

- `invoice`
- `client_siren`
- `client_ape`
- `supplier_ape`

## 6) Deploiement Render recommande

Le plus simple pour deployer la version cloud du line agent:

- Build command: `pip install -r agent_cloud_v1/requirements.txt`
- Start command: `uvicorn agent_cloud_v1.line_item_app:app --host 0.0.0.0 --port $PORT`

Tu peux aussi utiliser le fichier [render.yaml](C:\Users\Dell\Downloads\scripts-master\scripts-master\agent_cloud_v1\render.yaml).

## 7) Note memoire

La memoire locale actuelle ecrit dans `agent_local_v1/data/validation_memory.jsonl`.

En cloud, cette memoire fichier est bien pour une V1 de demo, mais pas pour une vraie persistence.
Pour la V2, il faudra la basculer vers SQLite/Postgres.
