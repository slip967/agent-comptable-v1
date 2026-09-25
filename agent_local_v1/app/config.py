from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = APP_DIR.parent
PROJECT_DIR = PACKAGE_DIR.parent

load_dotenv(PACKAGE_DIR / ".env", override=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_OPENROUTER_VISION_MODEL = "google/gemini-2.0-flash-lite-001"

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
OPENROUTER_MODEL_FALLBACKS = [
    model.strip()
    for model in os.getenv("OPENROUTER_MODEL_FALLBACKS", "").split(",")
    if model.strip()
]
OPENROUTER_VISION_MODEL = (
    os.getenv("OPENROUTER_VISION_MODEL", os.getenv("OPENROUTER_OCR_MODEL", DEFAULT_OPENROUTER_VISION_MODEL)).strip()
    or DEFAULT_OPENROUTER_VISION_MODEL
)
OPENROUTER_VISION_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "OPENROUTER_VISION_FALLBACK_MODELS",
        os.getenv("OPENROUTER_OCR_FALLBACK_MODELS", ""),
    ).split(",")
    if model.strip()
]
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "http://localhost:8000").strip()
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Agent Comptable Local").strip()
REFERENCE_SOURCE = os.getenv("REFERENCE_SOURCE", "local_json").strip().lower() or "local_json"
REFERENCE_COUCH_DB = os.getenv("REFERENCE_COUCH_DB", "ayasmine_test2").strip() or "ayasmine_test2"
try:
    REFERENCE_PAGE_SIZE = max(50, int(os.getenv("REFERENCE_PAGE_SIZE", "500").strip() or "500"))
except ValueError:
    REFERENCE_PAGE_SIZE = 500
MEMORY_SOURCE = os.getenv("MEMORY_SOURCE", "couchdb").strip().lower() or "couchdb"
MEMORY_COUCH_DB = os.getenv("MEMORY_COUCH_DB", REFERENCE_COUCH_DB).strip() or REFERENCE_COUCH_DB
MEMORY_DOC_PARTITION = os.getenv("MEMORY_DOC_PARTITION", "agent_local_v1").strip() or "agent_local_v1"
COUCHDB_DATABASE = os.getenv("COUCHDB_DATABASE", "abt3").strip() or "abt3"
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069").strip().rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "keymanage_db").strip()
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "").strip()
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "").strip()
ODOO_MOCK_MODE = os.getenv("ODOO_MOCK_MODE", "False").strip().lower() in {"1", "true", "yes", "on"}


def _parse_account_code_map(raw_value: str) -> dict[str, str]:
    """Parse a JSON object or comma-separated KEYMANAGE:ODOO pairs."""
    value = str(raw_value or "").strip()
    if not value:
        return {}
    if value.startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(source).strip(): str(target).strip()
            for source, target in parsed.items()
            if str(source).strip() and str(target).strip()
        }
    mappings: dict[str, str] = {}
    for entry in value.split(","):
        source, separator, target = entry.partition(":")
        if separator and source.strip() and target.strip():
            mappings[source.strip()] = target.strip()
    return mappings


ODOO_ACCOUNT_CODE_MAP = _parse_account_code_map(
    os.getenv("ODOO_ACCOUNT_CODE_MAP", "")
)
ODOO_TAX_SCOPE_BY_ACCOUNT = _parse_account_code_map(
    os.getenv("ODOO_TAX_SCOPE_BY_ACCOUNT", "")
)
try:
    MEMORY_PAGE_SIZE = max(50, int(os.getenv("MEMORY_PAGE_SIZE", "400").strip() or "400"))
except ValueError:
    MEMORY_PAGE_SIZE = 400


def _parse_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


FRONTEND_ORIGINS = _parse_origins(
    os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )
)
