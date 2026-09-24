@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%agent_local_v1"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

echo [1/3] Demarrage des services Docker (Odoo + PostgreSQL)...
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
  docker compose -f "%PROJECT_ROOT%docker-compose.yml" up -d
) else (
  docker-compose -f "%PROJECT_ROOT%docker-compose.yml" up -d
)
if errorlevel 1 (
  echo ERREUR: Docker Compose n'a pas pu demarrer.
  exit /b 1
)

set "PYTHON_EXE=python"
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo [2/3] Demarrage du backend FastAPI sur http://127.0.0.1:8000...
start "KeyManage AI - Backend" /D "%BACKEND_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo [3/3] Demarrage du frontend React...
start "KeyManage AI - Frontend" /D "%FRONTEND_DIR%" cmd /k npm run dev

echo.
echo KeyManage AI est en cours de demarrage.
echo Frontend : http://localhost:5173
echo Backend  : http://127.0.0.1:8000/docs
echo Odoo     : http://localhost:8069

endlocal
