# Agent Comptable Local V1

V1 locale pour recommander un compte comptable a partir d'une ligne de facture.

Architecture:

- `tools.py` appelle le matcher local existant (`10_match_reference_v1.py`)
- `agent.py` appelle OpenRouter pour arbitrer entre les meilleurs candidats
- `main.py` expose une API FastAPI simple
- `memory.py` stocke les validations humaines locales et peut rejouer un exact match deja valide

## 1. Installation

```bash
cd scripts-master/agent_local_v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Variables d'environnement

Copier `.env.example` vers `.env`, puis remplir la cle OpenRouter.

## 3. Lancement local

```bash
cd ..
uvicorn agent_local_v1.app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 4. Test

```bash
curl -X POST "http://127.0.0.1:8000/recommend" ^
  -H "Content-Type: application/json" ^
  -d "{\"article_source\":\"Electricite mars 2025\",\"metier_hint\":\"vtc\",\"tva_hint\":20}"
```

## 5. Memoire locale

Enregistrer une validation humaine:

```bash
curl -X POST "http://127.0.0.1:8000/feedback" ^
  -H "Content-Type: application/json" ^
  -d "{\"article_source\":\"Frais de service pour les courses Uber\",\"metier_hint\":\"vtc\",\"decision_humaine\":\"valider\",\"compte_comptable_final\":\"6061\",\"categorie_finale\":\"exploitation_metier\",\"sous_categorie_finale\":\"autres_exploitation_vtc\"}"
```

Consulter les statistiques memoire:

```bash
curl "http://127.0.0.1:8000/memory/stats"
```

Si la meme ligne revient avec le meme metier, `/recommend` reutilise la derniere validation humaine en exact match.

## 6. Ordre de travail conseille

1. verifier `/health`
2. tester `POST /recommend` sans OpenRouter
3. ajouter la cle OpenRouter
4. comparer les decisions sur 10 vraies lignes
5. enregistrer quelques validations via `/feedback`
6. passer ensuite au cloud
