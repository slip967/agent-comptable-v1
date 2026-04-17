from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = APP_DIR.parent
PROJECT_DIR = PACKAGE_DIR.parent

load_dotenv(PACKAGE_DIR / ".env", override=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "http://localhost:8000").strip()
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Agent Comptable Local").strip()


def _parse_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


FRONTEND_ORIGINS = _parse_origins(
    os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )
)
