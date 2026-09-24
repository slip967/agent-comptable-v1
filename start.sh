#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR="$PROJECT_ROOT/agent_local_v1"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "[1/3] Démarrage des services Docker (Odoo + PostgreSQL)..."
if docker compose version >/dev/null 2>&1; then
  docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose -f "$PROJECT_ROOT/docker-compose.yml" up -d
else
  echo "ERREUR : Docker Compose est introuvable." >&2
  exit 1
fi

if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  PYTHON_BIN=python
fi

echo "[2/3] Démarrage du backend FastAPI sur http://127.0.0.1:8000..."
(
  cd "$BACKEND_DIR"
  "$PYTHON_BIN" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

echo "[3/3] Démarrage du frontend React..."
(
  cd "$FRONTEND_DIR"
  npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Frontend : http://localhost:5173"
echo "Backend  : http://127.0.0.1:8000/docs"
echo "Odoo     : http://localhost:8069"

wait "$BACKEND_PID" "$FRONTEND_PID"
