import os


def _get(name: str, default: str = "") -> str:
    """Read env var with a fallback default."""
    return os.getenv(name, default)


# Defaults provided by the user; can still be overridden via env variables.
COUCHDB_URL = _get("COUCHDB_URL", "https://app.quimanage.info")
COUCHDB_USER = _get("COUCHDB_USER", "pdfuser")
COUCHDB_PASS = _get("COUCHDB_PASS", "stock123!!!")

CLIENT_CERT = _get("CLIENT_CERT", r"C:\Users\Dell\Downloads\scripts-master\client01.crt")
CLIENT_KEY = _get("CLIENT_KEY", r"C:\Users\Dell\Downloads\scripts-master\client01.key")
CA_CERT = _get("CA_CERT", r"C:\Users\Dell\Downloads\scripts-master\ca-certificates.crt")


def require_couch_config(extra_required: dict | None = None) -> dict:
    """
    Validate that the core CouchDB config is present; optionally validate extra fields.
    Returns a dict of the collected values for convenience.
    """
    missing: list[str] = []
    base_items = {
        "COUCHDB_URL": COUCHDB_URL,
        "COUCHDB_USER": COUCHDB_USER,
        "COUCHDB_PASS": COUCHDB_PASS,
        "CLIENT_CERT": CLIENT_CERT,
        "CLIENT_KEY": CLIENT_KEY,
        "CA_CERT": CA_CERT,
    }

    for key, val in base_items.items():
        if not val:
            missing.append(key)

    if extra_required:
        for key, val in extra_required.items():
            if not val:
                missing.append(key)

    if missing:
        raise RuntimeError(f"Missing configuration: {', '.join(sorted(set(missing)))}")

    return base_items | (extra_required or {})
