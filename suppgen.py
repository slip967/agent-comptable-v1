import couchdb
import io
import json
import os
from datetime import datetime
from typing import List, Tuple

import requests
from requests.auth import HTTPBasicAuth
from couchdb.http import (
    Forbidden, PreconditionFailed, ResourceConflict,
    ResourceNotFound, ServerError, Unauthorized
)

from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)


# ---------------- Session Adapter ----------------

class CouchDBRequestsSession(requests.Session):
    user_agent = "couchdb-python/requests-adapter"

    def request(self, method, url, body=None, headers=None, credentials=None, **kwargs):
        headers = headers.copy() if headers else {}
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", self.user_agent)

        data = None
        if body is not None:
            if hasattr(body, "read"):
                data = body
            elif isinstance(body, (bytes, str)):
                data = body
            else:
                data = json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")

        if credentials:
            kwargs["auth"] = credentials
        kwargs["headers"] = headers
        if data is not None:
            kwargs["data"] = data

        response = super().request(method, url, **kwargs)

        if response.status_code >= 400:
            raise ServerError((response.status_code, response.text))

        content = response.content or b""
        response.close()
        return response.status_code, response.headers, io.BytesIO(content)


# ---------------- Purger ----------------

class GeneratedEntriesPurger:

    def __init__(self, couch_url, db_name, user, password,
                 client_cert=None, client_key=None, ca_cert=None,
                 verbose=True):

        self.verbose = verbose

        self.cert = (client_cert, client_key) if client_cert and client_key else None
        self.verify = ca_cert if ca_cert else True

        session = CouchDBRequestsSession()
        session.auth = HTTPBasicAuth(user, password)
        session.cert = self.cert
        session.verify = self.verify

        self.server = couchdb.Server(couch_url, session=session)
        self.db = self.server[db_name]

    def _log(self, msg):
        if self.verbose:
            print(msg)

    def find_generated_entries(self) -> List[dict]:

        selector = {
            "selector": {
                "p": "entry",
                "is_generated": True
            },
            "fields": ["_id", "_rev", "invoice.invoice_form_id"],
            "limit": 1000000
        }

        results = list(self.db.find(selector))
        return results

    def purge(self, dry_run=False, batch_size=1000):

        self._log("Recherche des écritures générées...")

        docs = self.find_generated_entries()
        total = len(docs)

        self._log(f"{total} écritures générées trouvées.")

        if dry_run:
            self._log("Mode DRY-RUN activé. Aucune suppression effectuée.")
            return

        deleted = 0
        errors = 0

        batch = []

        for doc in docs:
            batch.append({
                "_id": doc["_id"],
                "_rev": doc["_rev"],
                "_deleted": True
            })

            if len(batch) >= batch_size:
                ok, err = self._bulk_delete(batch)
                deleted += ok
                errors += err
                batch = []

        if batch:
            ok, err = self._bulk_delete(batch)
            deleted += ok
            errors += err

        self._log("--------------------------------------------------")
        self._log(f"Suppression terminée.")
        self._log(f"  - Supprimées: {deleted}")
        self._log(f"  - Erreurs: {errors}")
        self._log("--------------------------------------------------")

    def _bulk_delete(self, batch: List[dict]) -> Tuple[int, int]:

        try:
            results = self.db.update(batch)
        except Exception as e:
            self._log(f"Erreur bulk delete: {e}")
            return 0, len(batch)

        success = 0
        errors = 0

        for ok, docid, info in results:
            if ok:
                success += 1
            else:
                errors += 1
                self._log(f"Erreur suppression doc {docid}: {info}")

        return success, errors


# ---------------- Main ----------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Purge des écritures générées (is_generated=true).")
    parser.add_argument("--db-entries", default=os.getenv("DB_ENTRIES", "abt3fec2"))
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=True)

    args = parser.parse_args()

    COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL)
    USER = DEFAULT_COUCHDB_USER
    PASS = DEFAULT_COUCHDB_PASS

    CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
    CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
    CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

    print("Purge des écritures générées...")
    print(f"Base cible: {args.db_entries}")
    print("--------------------------------------------------")

    purger = GeneratedEntriesPurger(
        couch_url=COUCHDB_URL,
        db_name=args.db_entries,
        user=USER,
        password=PASS,
        client_cert=CLIENT_CERT,
        client_key=CLIENT_KEY,
        ca_cert=CA_CERT,
        verbose=args.verbose,
    )

    purger.purge(dry_run=args.dry_run, batch_size=args.batch_size)
