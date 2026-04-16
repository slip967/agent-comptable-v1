import os, re, unicodedata, uuid, hashlib, json
import sys
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import date as _date
import csv
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from couch_config import (
    CA_CERT as DEFAULT_CA_CERT,
    CLIENT_CERT as DEFAULT_CLIENT_CERT,
    CLIENT_KEY as DEFAULT_CLIENT_KEY,
    COUCHDB_PASS as DEFAULT_COUCHDB_PASS,
    COUCHDB_URL as DEFAULT_COUCHDB_URL,
    COUCHDB_USER as DEFAULT_COUCHDB_USER,
)

# Ensure connection defaults are present for connect_to_db.
os.environ.setdefault("COUCHDB_URL", DEFAULT_COUCHDB_URL)
os.environ.setdefault("COUCHDB_USER", DEFAULT_COUCHDB_USER)
os.environ.setdefault("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
os.environ.setdefault("CLIENT_CERT", DEFAULT_CLIENT_CERT)
os.environ.setdefault("CLIENT_KEY", DEFAULT_CLIENT_KEY)
os.environ.setdefault("CA_CERT", DEFAULT_CA_CERT)

DB_NAME    = os.getenv("DB_ENTRIES", os.getenv("DB_NAME", "ayasmine_test"))
FEC_FILE   = os.getenv("FEC_FILE", r"C:\Users\Dell\Downloads\519665103FEC20241231 (1).txt")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))


class _PartitionView:
    def __init__(self, db, partition_prefix: str):
        self._db = db
        self._partition_prefix = partition_prefix

    def get_query_result(self, selector: dict, limit: int = 1, include_docs: bool = True):
        return self._db.get_query_result(
            selector,
            partition_key=self._partition_prefix,
            limit=limit,
            include_docs=include_docs,
        )


class _RequestsCouchDB:
    def __init__(self, session: requests.Session, couch_url: str, db_name: str):
        self.r_session = session
        self.database_url = f"{couch_url.rstrip('/')}/{quote(db_name, safe='')}"

    def _request(self, method: str, path: str = "", **kwargs):
        path = path.lstrip("/")
        url = f"{self.database_url}/{path}" if path else self.database_url
        resp = self.r_session.request(method, url, timeout=180, **kwargs)
        resp.raise_for_status()
        if resp.content and resp.headers.get("Content-Type", "").startswith("application/json"):
            return resp.json()
        return {"ok": True}

    def get_partition(self, partition_prefix: str):
        return _PartitionView(self, partition_prefix)

    def get_query_result(
        self,
        selector: dict,
        partition_key: str | None = None,
        limit: int = 1,
        include_docs: bool = True,
    ):
        payload = {"selector": selector, "limit": limit}
        path = "_find"
        if partition_key:
            path = f"_partition/{quote(partition_key, safe='')}/_find"
        res = self._request("POST", path, json=payload)
        return res.get("docs", [])

    def bulk_docs(self, docs: list[dict]):
        return self._request("POST", "_bulk_docs", json={"docs": docs, "new_edits": True})

    def save(self, doc: dict):
        return self._request("PUT", quote(doc["_id"], safe=""), json=doc)

    def create_document(self, doc: dict):
        return self.save(doc)


def _connect_to_db_cloudant(db_name: str):
    couch_url = os.environ.get("COUCHDB_URL", DEFAULT_COUCHDB_URL).rstrip("/")
    couch_user = os.environ.get("COUCHDB_USER", DEFAULT_COUCHDB_USER)
    couch_pass = os.environ.get("COUCHDB_PASS", DEFAULT_COUCHDB_PASS)
    client_cert = os.environ.get("CLIENT_CERT", DEFAULT_CLIENT_CERT)
    client_key = os.environ.get("CLIENT_KEY", DEFAULT_CLIENT_KEY)
    ca_cert = os.environ.get("CA_CERT", DEFAULT_CA_CERT)

    try:
        session = requests.Session()
        session.auth = (couch_user, couch_pass)
        session.cert = (client_cert, client_key)
        session.verify = ca_cert
        session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=3))

        login = session.post(
            f"{couch_url}/_session",
            data={"name": couch_user, "password": couch_pass},
            timeout=30,
        )
        login.raise_for_status()

        db_url = f"{couch_url}/{quote(db_name, safe='')}"
        db_info = session.get(db_url, timeout=30)
        if db_info.status_code == 404:
            print(f'CONNEXION  : Database "{db_name}" not found.')
            return None
        db_info.raise_for_status()

        print("CONNEXION  : Session CouchDB ouverte avec succes.")
        print(f'CONNEXION  : Database "{db_name}" accessed successfully.')
        return _RequestsCouchDB(session, couch_url, db_name)
    except Exception as e:
        print(f"CONNEXION  : Error connecting to CouchDB: {e}")
        return None


try:
    from connexion import connect_to_db  # type: ignore
except (ModuleNotFoundError, ImportError):
    # Some environments keep the legacy `connexion.py` under /root/data.
    connexion_dir = os.getenv("CONNEXION_DIR", "/root/data")
    if os.path.exists(os.path.join(connexion_dir, "connexion.py")):
        sys.path.insert(0, connexion_dir)
        from connexion import connect_to_db  # type: ignore
    else:
        connect_to_db = _connect_to_db_cloudant  # type: ignore[assignment]

getcontext().prec = 28
CENTS = Decimal("0.01")

REQUIRED_COLUMNS_2013 = [
    "JournalCode","JournalLib","EcritureNum","EcritureDate",
    "CompteNum","CompteLib","CompAuxNum","CompAuxLib",
    "PieceRef","PieceDate","EcritureLib","Debit","Credit",
    "EcritureLet","DateLet","ValidDate","Montantdevise","Idevise"
]

ACCOUNT_WITH_AUX_RE = re.compile(r"^(?P<base>[1-7]\d{2,})(?::?(?P<aux>[A-Za-z0-9._\-]+))?$")

VAT_ACCOUNT_RATE = {
    "44566": Decimal("20.0"), "44571": Decimal("20.0"),
    "44562": Decimal("10.0"), "44572": Decimal("10.0"),
    "44563": Decimal("5.5"),  "44573": Decimal("5.5"),
}

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def siren_from_filename(path: str) -> str:
    m = re.search(r"(\d{9})", os.path.basename(path))
    if not m:
        raise ValueError("Cannot extract 9-digit SIREN from filename.")
    return m.group(1)

def partition_prefix_from_filename(path: str) -> str:
    return f"fr_bd_{siren_from_filename(path)}"

def new_doc_id(partition_prefix: str) -> str:
    return f"{partition_prefix}:{uuid.uuid4().hex}"

def _strip_bom_variants(s: str) -> str:
    """
    Remove BOM markers, including mojibake when a UTF-8 BOM was decoded as cp1252/latin-1.
    """
    if not s:
        return ""
    s = s.lstrip("\ufeff")
    for prefix in ("ï»¿", "ÿþ", "þÿ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s

def norm_header(s: str) -> str:
    if s is None:
        return ""
    s = _strip_bom_variants(s).replace("\xa0", " ")
    return unicodedata.normalize("NFKC", s).strip()

def detect_delimiter(header_line: str) -> str:
    if header_line is None:
        return "|"
    s = _strip_bom_variants(header_line).replace("\xa0", " ")
    candidates = ["|", "\t", ";", ","]
    counts = {d: s.count(d) for d in candidates}
    best = max(counts.items(), key=lambda kv: kv[1])
    if best[1] <= 0:
        raise ValueError("Bad format: could not detect delimiter in header line.")
    return best[0]

def dec(val: str) -> Decimal:
    s = (val or "").strip()
    if s == "": return Decimal("0.00")
    s = s.replace(" ", "").replace("\xa0", "").replace(",", ".")
    return Decimal(s).quantize(CENTS, rounding=ROUND_HALF_UP)

def parse_date(s: str):
    if not s or not s.strip(): return None
    s = s.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def _to_date(d: str|None) -> _date|None:
    if not d:
        return None
    try:
        y, m, day = d.split("-")
        return _date(int(y), int(m), int(day))
    except Exception:
        return None


def normalize_journal_code(code: str) -> str:
    code = (code or "").strip()
    if len(code) >= 3 and code[0] == "[" and code[-1] == "]":
        code = code[1:-1].strip()
    return code

def split_compte_to_base_aux(compte_num: str, comp_aux_num: str|None, comp_aux_lib: str|None):
    compte_num = (compte_num or "").strip()
    base = compte_num
    aux_code = None
    aux_label = None
    if comp_aux_num and comp_aux_num.strip():
        m = ACCOUNT_WITH_AUX_RE.match(compte_num)
        base = m.group("base") if m else compte_num
        aux_code = comp_aux_num.strip()
        aux_label = (comp_aux_lib or aux_code).strip()
        return base, aux_code, aux_label
    m = ACCOUNT_WITH_AUX_RE.match(compte_num)
    if m:
        base = m.group("base")
        aux_code = m.group("aux")
        if aux_code:
            aux_label = (comp_aux_lib or aux_code).strip()
    return base, aux_code, aux_label

def aux_profile_from_base(base: str):
    if base.startswith("401"):   return ("supplier","Supplier")
    if base.startswith("411"):   return ("client","Client")
    if base.startswith("421"):   return ("employee","Employee")
    return (None, None)

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    # NFKD + remove combining marks => remove accents (é -> e)
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def _norm_col_key(s: str) -> str:
    """
    Normalise un nom de colonne pour le matcher:
    - trim + NFKC
    - lower
    - strip accents
    - conserve uniquement [a-z0-9]
    """
    s = norm_header(s or "")
    s = _strip_accents(s.lower())
    return "".join(ch for ch in s if ch.isalnum())


_CANONICAL_COL_CANDIDATES: dict[str, list[str]] = {
    # FEC (standard) + exports "libellés" (ex: "Code journal", "N° de compte", etc.)
    "JournalCode": ["journalcode", "codejournal"],
    "JournalLib": ["journallib", "descriptiondujournal", "libellejournal", "libelledournal"],
    "EcritureNum": ["ecriturenum", "numerodecriture", "numerecriture", "piece"],
    "EcritureDate": ["ecrituredate", "dateauformatl47", "date"],
    "CompteNum": ["comptenum", "ndecompte", "nodecompte", "numerodecompte"],
    "CompteLib": ["comptelib", "intituleducompte", "libelleducompte"],
    "CompAuxNum": ["compauxnum", "compteauxiliaire", "auxiliaire"],
    "CompAuxLib": ["compauxlib", "intituleducompteauxiliaire", "libelleducompteauxiliaire"],
    "PieceRef": ["pieceref", "piece"],
    "PieceDate": ["piecedate", "datedepiece"],
    "EcritureLib": ["ecriturelib", "libelle"],
    "Debit": ["debit"],
    "Credit": ["credit"],
    "EcritureLet": ["ecriturelet", "lettrage"],
    "DateLet": ["datelet", "datedelettrage"],
    "ValidDate": ["validdate", "datevalidation"],
    "Montantdevise": ["montantdevise"],
    "Idevise": ["idevise", "devise", "codedevise"],
}


def _candidate_encodings(encoding: str | None) -> list[str]:
    enc = (encoding or "").strip()
    if enc and enc.lower() != "auto":
        return [enc]
    # Try UTF first, then common "ANSI" encodings used by accounting exports.
    return ["utf-8-sig", "utf-8", "utf-16", "cp1252", "iso-8859-15", "latin-1"]


def load_fec(path, *, encoding: str | None = None):
    auto_mode = (encoding or "").strip().lower() in ("", "auto")
    last_err: Exception | None = None

    for enc in _candidate_encodings(encoding):
        try:
            rows = []
            with open(path, "r", encoding=enc, newline="") as f:
                header_line = f.readline()
                if not header_line:
                    raise ValueError("Empty file.")

                delim = detect_delimiter(header_line)

                header_parts = next(csv.reader([header_line], delimiter=delim))
                raw_cols = [norm_header(c) for c in header_parts]
                key_to_idx = {}
                for i, c in enumerate(raw_cols):
                    k = _norm_col_key(c)
                    if k and k not in key_to_idx:
                        key_to_idx[k] = i

                idx_by_canonical: dict[str, int] = {}
                for canonical in REQUIRED_COLUMNS_2013:
                    for candidate in _CANONICAL_COL_CANDIDATES.get(canonical, []):
                        if candidate in key_to_idx:
                            idx_by_canonical[canonical] = key_to_idx[candidate]
                            break

                # Minimal sanity checks (allows non-standard headers with extra columns)
                essential = ["JournalCode", "EcritureDate", "CompteNum"]
                missing_essential = [c for c in essential if c not in idx_by_canonical]
                if missing_essential:
                    raise ValueError(
                        f"Missing essential columns: {missing_essential}\nSeen: {raw_cols}"
                    )

                # Amount columns can be provided as Debit/Credit or via Montant+Sens.
                montant_idx = None
                sens_idx = None
                if "Debit" not in idx_by_canonical or "Credit" not in idx_by_canonical:
                    for k in ("montantassocieausens", "montantseulpositifounegatif"):
                        if k in key_to_idx:
                            montant_idx = key_to_idx[k]
                            break
                    sens_idx = key_to_idx.get("sens")

                reader = csv.reader(f, delimiter=delim)
                for lineno, parts in enumerate(reader, start=2):
                    if not parts or all((p or "").strip() == "" for p in parts):
                        continue

                    def _get(canon: str) -> str:
                        idx = idx_by_canonical.get(canon)
                        if idx is None or idx >= len(parts):
                            return ""
                        return (parts[idx] or "").strip()

                    row = {c: _get(c) for c in REQUIRED_COLUMNS_2013}

                    # Derive Debit/Credit if not present in source.
                    if ("Debit" not in idx_by_canonical or "Credit" not in idx_by_canonical) and montant_idx is not None:
                        amt_raw = (parts[montant_idx] or "").strip()
                        sens = (parts[sens_idx] or "").strip().upper() if sens_idx is not None and sens_idx < len(parts) else ""
                        if amt_raw:
                            amt = dec(amt_raw)
                            if sens.startswith("C") or (not sens and amt < 0):
                                row["Debit"] = "0"
                                row["Credit"] = str(abs(amt))
                            else:
                                row["Debit"] = str(abs(amt))
                                row["Credit"] = "0"

                    # Ensure EcritureNum exists (grouping key). Prefer PieceRef, fallback to line number.
                    if not (row.get("EcritureNum") or "").strip():
                        row["EcritureNum"] = (row.get("PieceRef") or "").strip() or f"LINE_{lineno}"

                    # Common fallbacks for robustness
                    if not (row.get("PieceRef") or "").strip():
                        row["PieceRef"] = (row.get("EcritureNum") or "").strip()
                    if not (row.get("PieceDate") or "").strip():
                        row["PieceDate"] = (row.get("EcritureDate") or "").strip()
                    if not (row.get("JournalLib") or "").strip():
                        row["JournalLib"] = (row.get("JournalCode") or "").strip()
                    if not (row.get("CompteLib") or "").strip():
                        row["CompteLib"] = (row.get("CompteNum") or "").strip()

                    row["Debit"] = dec(row.get("Debit"))
                    row["Credit"] = dec(row.get("Credit"))
                    row["EcritureDate_ISO"] = parse_date(row.get("EcritureDate"))
                    row["PieceDate_ISO"] = parse_date(row.get("PieceDate"))
                    row["JournalCode"] = normalize_journal_code(row.get("JournalCode"))

                    rows.append(row)

            if enc.lower() not in ("utf-8-sig", "utf-8") and auto_mode:
                print(f"[FEC] Encodage détecté: {enc}")
            return rows, REQUIRED_COLUMNS_2013

        except UnicodeError as e:
            last_err = e
            continue
        except ValueError as e:
            # Try next encoding (headers/format may be garbled under a wrong encoding)
            last_err = e
            continue
        except Exception as e:
            last_err = e
            if auto_mode:
                continue
            break

    raise last_err or ValueError("Unable to read FEC file.")

def estimate_tva_multirate(entry_rows):
    tva_by_key = defaultdict(Decimal)
    tva_unknown = Decimal(0)
    for r in entry_rows:
        acc = (r.get("CompteNum") or "")
        if not acc.startswith("445"): continue
        amt_abs = (r["Debit"] + r["Credit"]).copy_abs()
        key5 = acc[:5] if len(acc) >= 5 else acc
        if key5 in VAT_ACCOUNT_RATE:
            tva_by_key[key5] += amt_abs
        else:
            tva_unknown += amt_abs

    lines = []
    for key5, tva_amt in tva_by_key.items():
        rate = VAT_ACCOUNT_RATE[key5]
        if rate > 0:
            ht = (tva_amt * Decimal(100) / rate).quantize(CENTS)
            lines.append({"taux": float(rate), "montant_tva": float(tva_amt), "montant_ht": float(ht)})
        else:
            lines.append({"taux": None, "montant_tva": float(tva_amt), "montant_ht": None})

    if tva_unknown > 0:
        ht_total = Decimal(0)
        for r in entry_rows:
            acc = (r.get("CompteNum") or "")
            if acc.startswith(("6","7")):
                ht_total += (r["Debit"] + r["Credit"]).copy_abs()
        claimed_ht = sum(Decimal(str(l["montant_ht"])) for l in lines if l["montant_ht"] is not None)
        residual_ht = (ht_total - claimed_ht) if ht_total > claimed_ht else Decimal(0)
        lines.append({
            "taux": None,
            "montant_tva": float(tva_unknown),
            "montant_ht": float(residual_ht) if residual_ht > 0 else None
        })
    return lines

def make_piece_id(partition_prefix: str, journal_code: str|None, piece_ref: str|None, piece_date: str|None):
    if not piece_ref:
        return None
    base = f"{journal_code or ''}|{piece_ref}|{piece_date or ''}"
    md5hex = hashlib.md5(base.encode("utf-8")).hexdigest()
    return f"{partition_prefix}:piece:{md5hex}"



def find_one_in_partition(db, partition_prefix: str, selector: dict):
    try:
        part = db.get_partition(partition_prefix)
        res = part.get_query_result(selector, limit=1, include_docs=True)
        items = list(res)
        if items:
            return items[0]
    except Exception:
        pass

    try:
        res = db.get_query_result(selector, partition_key=partition_prefix, limit=1, include_docs=True)
        items = list(res)
        if items:
            return items[0]
    except Exception:
        pass

    try:
        url = f"{db.database_url}/_partition/{partition_prefix}/_find"
        payload = {"selector": selector, "limit": 1}
        r = db.r_session.post(url, data=json.dumps(payload))
        r.raise_for_status()
        docs = r.json().get("docs", [])
        if docs:
            return docs[0]
    except Exception:
        pass

    return None

def bulk_upload(db, docs, chunk_size=CHUNK_SIZE):
    ok = 0
    errs = []
    for i in range(0, len(docs), chunk_size):
        batch = docs[i:i+chunk_size]
        try:
            res = db.bulk_docs(batch)
            for item in res:
                if "ok" in item or "rev" in item:
                    ok += 1
                else:
                    errs.append(item)
        except Exception as e:
            errs.append({"error": str(e), "batch_start": i, "batch_len": len(batch)})
    return ok, errs

def main(
    db_name: str = DB_NAME,
    fec_file: str = FEC_FILE,
    chunk_size: int = CHUNK_SIZE,
    siren: str | None = None,
    encoding: str | None = None,
    partition_prefix: str | None = None,
):
    db = connect_to_db(db_name)
    if db is None:
        print("ABORT: cannot connect to CouchDB.")
        return

    rows, _cols = load_fec(fec_file, encoding=encoding)

    forced_prefix = (partition_prefix or "").strip()
    if forced_prefix:
        if ":" in forced_prefix:
            raise SystemExit("--partition-prefix ne doit pas contenir ':' (CouchDB partitioned IDs).")
        partition_prefix = forced_prefix
    elif siren:
        partition_prefix = f"fr_bd_{siren}"
    else:
        try:
            partition_prefix = partition_prefix_from_filename(fec_file)
        except ValueError:
            raise SystemExit(
                "SIREN introuvable: passe --siren 123456789 (ou --partition-prefix) "
                "ou renomme le fichier pour inclure un SIREN (9 chiffres)."
            )

    years = { int(r["EcritureDate_ISO"][:4]) for r in rows if r["EcritureDate_ISO"] }
    exercice_year = (years.pop() if len(years)==1 else None)

    entries = defaultdict(list)
    for r in rows:
        entries[(r.get("JournalCode") or "", (r.get("EcritureNum") or "").strip())].append(r)
    seq_counters = defaultdict(int)

    journaux = {}
    accounts = {}
    aux_contacts = {}
    entry_docs = []
    treso_usage = defaultdict(Counter)

    for r in rows:
        jc = (r.get("JournalCode") or "").strip()
        jl = (r.get("JournalLib") or "").strip()

        if jc not in journaux:
            journaux[jc] = {
                "_id": new_doc_id(partition_prefix),
                "p": "journal",
                "data": { "collection": "Journal", "type": "", "sub_type": "" },
                "code": jc,
                "label": jl or jc,
                "journal_type": None,
                "treasury_account": None,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }

        base, aux_code, aux_label = split_compte_to_base_aux(
            r.get("CompteNum"), r.get("CompAuxNum"), r.get("CompAuxLib")
        )

        if base and base not in accounts:
            accounts[base] = {
                "_id": new_doc_id(partition_prefix),
                "p": "account",
                "data": { "collection": "Account", "type": "", "sub_type": "" },
                "number": base,
                "label": (r.get("CompteLib") or "").strip() or base,
                "auxiliary": False,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }

        if aux_code:
            key = f"{base}:{aux_code}"
            if key not in aux_contacts:
                profile, type_cap = aux_profile_from_base(base)
                if profile is None:  # default if base not 401/411/421
                    profile, type_cap = "client", "Client"
                aux_contacts[key] = {
                    "_id": new_doc_id(partition_prefix),
                    "p": profile,  # "client" | "employee" | "supplier"
                    "data": { "collection": "Contact", "type": type_cap, "sub_type": "" },
                    "sub_profile": [
                        {
                            "name_sub_profile": "Auxiliary",
                            "uid_sub_profile": f"auxiliary:{uuid.uuid4().hex}",
                            "grouped": False,
                        }
                    ],
                    "number": base,
                    "auxiliary_code": aux_code,
                    "label": aux_label or aux_code,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            accounts[base]["auxiliary"] = True

        acc = (r.get("CompteNum") or "").strip()
        if jc and (acc.startswith("512") or acc.startswith("531")):
            treso_usage[jc][acc[:3]] += 1

        edate = r.get("EcritureDate_ISO")
        enum  = (r.get("EcritureNum") or "").strip()
        seq_counters[(jc, enum)] += 1
        seq = seq_counters[(jc, enum)]
        piece_ref  = (r.get("PieceRef") or "").strip() or None
        piece_date = r.get("PieceDate_ISO")
        piece_uid  = make_piece_id(partition_prefix, jc, piece_ref, piece_date)

        entry_docs.append({
            "_id": new_doc_id(partition_prefix),
            "p": "entry",
            "data": { "collection": "Entry", "type": "", "sub_type": "" },
            "date": edate,
            "fiscal_year_uid": None,
            "journal_code": jc,
            "number": enum,
            "line_seq": seq,
            "label": (r.get("EcritureLib") or "").strip() or None,
            "piece_ref": piece_ref,
            "piece_date": piece_date,
            "piece_id": piece_uid,
            "debit": float(r["Debit"]),
            "credit": float(r["Credit"]),
            "account_number": base or None,
            "aux_account": aux_code if aux_code else None,
            "matching": (r.get("EcritureLet") or "").strip() or None,
            "matching_date": (parse_date(r.get("DateLet")) if r.get("DateLet") else None),
            "tva_lines": [],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

    tva_by_entry = {}
    for key, erows in entries.items():
        tva_by_entry[key] = estimate_tva_multirate(erows)
    for e in entry_docs:
        e["tva_lines"] = tva_by_entry.get((e["journal_code"], e["number"]), [])

    for jc, jdoc in journaux.items():
        if jc == "AN":
            jdoc["treasury_account"] = None
            continue
        cnt = treso_usage.get(jc, Counter())
        if not cnt:
            continue
        if "512" in cnt: jdoc["treasury_account"] = "512"
        elif "531" in cnt: jdoc["treasury_account"] = "531"
        else: jdoc["treasury_account"] = max(cnt.items(), key=lambda kv: kv[1])[0]

    kmorg_doc = find_one_in_partition(db, partition_prefix, {"p": "kmorganisation"})
    fiscal_years_final = []

    new_fy = None
    if exercice_year is not None:
        new_fy = {
            "year": int(exercice_year),
            "opening_date": f"{exercice_year}-01-01",
            "closing_date": f"{exercice_year}-12-31",
            "uid": f"fiscalyear:{uuid.uuid4().hex}",
        }

    if kmorg_doc:
        fy = kmorg_doc.get("fiscal_years")
        legacy = kmorg_doc.get("exercice")

        if not isinstance(fy, list):
            fy = []

        if isinstance(legacy, list):
            for x in legacy:
                if isinstance(x, dict) and ("annee" in x or "date_ouverture" in x or "date_fermeture" in x):
                    fy.append({
                        "year": x.get("annee"),
                        "opening_date": x.get("date_ouverture"),
                        "closing_date": x.get("date_fermeture"),
                        "uid": f"fiscalyear:{uuid.uuid4().hex}",
                    })
            kmorg_doc.pop("exercice", None)

        if new_fy:
            already = any(str(it.get("year")) == str(new_fy["year"]) for it in fy if it and "year" in it)
            if not already:
                fy.append(new_fy)

        for it in fy:
            if isinstance(it, dict) and "uid" not in it:
                it["uid"] = f"fiscalyear:{uuid.uuid4().hex}"

        kmorg_doc["fiscal_years"] = fy
        kmorg_doc["updated_at"] = now_iso()
        db.save(kmorg_doc)
        fiscal_years_final = fy
    else:
        if not new_fy:
            dates_iso = [r.get("EcritureDate_ISO") for r in rows if r.get("EcritureDate_ISO")]
            if dates_iso:
                dmin = min(dates_iso)
                dmax = max(dates_iso)
                y = int(dmin[:4])
                new_fy = {
                    "year": y,
                    "opening_date": f"{y}-01-01",
                    "closing_date": f"{y}-12-31",
                    "uid": f"fiscalyear:{uuid.uuid4().hex}",
                }

        kmorg_new = {
            "_id": new_doc_id(partition_prefix),
            "p": "kmorganisation",
            "data": { "collection": "Contact", "type": "Kmorganisation", "sub_type": "" },
            "fiscal_years": ([new_fy] if new_fy else []),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        db.create_document(kmorg_new)
        fiscal_years_final = kmorg_new["fiscal_years"]

    _ranges = []
    for it in fiscal_years_final:
        if not isinstance(it, dict):
            continue
        sd = _to_date(it.get("opening_date"))
        ed = _to_date(it.get("closing_date"))
        uid = it.get("uid")
        if sd and ed and uid:
            _ranges.append((sd, ed, uid))

    def match_fy_uid(iso: str|None) -> str|None:
        d = _to_date(iso)
        if not d or not _ranges:
            return None
        for sd, ed, uid in _ranges:
            if sd <= d <= ed:
                return uid
        if d:
            y = d.year
            for it in fiscal_years_final:
                if int(it.get("year") or -1) == y and it.get("uid"):
                    return it["uid"]
        return None

    for e in entry_docs:
        e["fiscal_year_uid"] = match_fy_uid(e.get("date"))

    import_doc = {
        "_id": new_doc_id(partition_prefix),
        "p": "import_fec",
        "data": { "collection": "ImportFEC", "type": "", "sub_type": "" },
        "import_date": now_iso(),
        "source_file": os.path.basename(fec_file),
        "user": "admin@n1",
        "stats": {
            "total_lines": len(rows),
            "journals": len(journaux),
            "entries": len(entry_docs),
            "accounts_created": len(accounts) + len(aux_contacts),
        },
        "warnings": [],
        "errors": []
    }

    to_upload = []
    to_upload.extend(journaux.values())
    to_upload.extend(entry_docs)
    to_upload.extend(accounts.values())
    to_upload.extend(aux_contacts.values())
    to_upload.append(import_doc)

    print(f"Uploading {len(to_upload)} documents to '{db_name}' ...")
    ok, errs = bulk_upload(db, to_upload, chunk_size)

    per_p = Counter(doc["p"] for doc in to_upload)
    print("\n--- Upload summary ---")
    print(f"Docs attempted: {len(to_upload)} | OK: {ok} | Errors: {len(errs)}")
    for k, v in per_p.items():
        print(f"  {k:15s}: {v}")
    if errs:
        print("\nSome errors (up to 5):")
        for e in errs[:5]:
            print(" -", e)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse un FEC et charge les documents dans CouchDB.")
    parser.add_argument("--db-entries", "--db", dest="db_name", default=DB_NAME, help="Nom de la base CouchDB cible.")
    parser.add_argument("--fec-file", "--fec", dest="fec_file", default=FEC_FILE, help="Chemin local du fichier FEC.")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Taille des batches _bulk_docs.")
    parser.add_argument(
        "--siren",
        default=os.getenv("CLIENT_SIREN"),
        help="SIREN client pour forcer le partition prefix (fr_bd_<SIREN>).",
    )
    parser.add_argument(
        "--partition-prefix",
        default=os.getenv("PARTITION_PREFIX", ""),
        help="Partition prefix CouchDB à utiliser (override). Ex: fr_bd_452416191",
    )
    parser.add_argument(
        "--encoding",
        default=os.getenv("FEC_ENCODING", "auto"),
        help="Encodage du fichier (auto, utf-8-sig, cp1252, iso-8859-15, ...).",
    )
    args = parser.parse_args()
    main(
        db_name=args.db_name,
        fec_file=args.fec_file,
        chunk_size=args.chunk_size,
        siren=args.siren,
        encoding=args.encoding,
        partition_prefix=args.partition_prefix,
    )
