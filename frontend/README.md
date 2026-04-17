# Frontend React V1

Interface React/Vite pour appeler le backend FastAPI local ou cloud.

## 1. Installation

```bash
cd frontend
npm install
```

## 2. Variables d'environnement

Copier `.env.example` vers `.env`.

En local:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

En cloud:

```env
VITE_API_BASE_URL=https://agent-comptable-v1.onrender.com
```

## 3. Lancement local

```bash
npm run dev
```

Le frontend tourne ensuite sur `http://127.0.0.1:5173`.

## 4. Parcours V1

- saisir une ligne de facture
- envoyer au backend via `/recommend`
- afficher la decision comptable et le top 3
- enregistrer une validation humaine via `/feedback`
