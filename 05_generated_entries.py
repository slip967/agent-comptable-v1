import couchdb
import io
import importlib.util
import json
import os
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Set, Union

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


class CouchDBRequestsSession(requests.Session):
    """Minimal adapter to mimic couchdb.http.Session with requests."""
    user_agent = "couchdb-python/requests-adapter"

    def request(self, method, url, body=None, headers=None, credentials=None, **kwargs):  # type: ignore[override]
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
            content_type = response.headers.get("content-type", "")
            error_payload = None
            if "application/json" in content_type:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                error_payload = (payload.get("error"), payload.get("reason"))
            else:
                error_payload = response.text

            if response.status_code == 401:
                raise Unauthorized(error_payload)
            if response.status_code == 403:
                raise Forbidden(error_payload)
            if response.status_code == 404:
                raise ResourceNotFound(error_payload)
            if response.status_code == 409:
                raise ResourceConflict(error_payload)
            if response.status_code == 412:
                raise PreconditionFailed(error_payload)
            raise ServerError((response.status_code, error_payload))

        content = response.content or b""
        response.close()
        data_stream = io.BytesIO(content)
        return response.status_code, response.headers, data_stream


class AccountingEntryGenerator:
    def __init__(
        self,
        couch_url: str,
        db_factures: str,
        db_entries: str,
        user_factures: str,
        pass_factures: str,
        user_entries: str,
        pass_entries: str,
        client_cert: str = None,
        client_key: str = None,
        ca_cert: str = None,
        verbose: bool = True,
        report_path: str = "entries_generation_report.txt",
        skipped_jsonl_path: Optional[str] = "skipped_invoices.jsonl",
    ):
        self.verbose = verbose

        self.cert = (client_cert, client_key) if client_cert and client_key else None
        self.verify = ca_cert if ca_cert else True

        self.server_factures = couchdb.Server(
            f"{couch_url}",
            session=self._create_session(user_factures, pass_factures),
        )
        self.db_factures = self.server_factures[db_factures]

        self.server_entries = couchdb.Server(
            f"{couch_url}",
            session=self._create_session(user_entries, pass_entries),
        )
        self.db_entries = self.server_entries[db_entries]

        self.report_path = report_path
        self.skipped_jsonl_path = skipped_jsonl_path

        self._supplier_by_siren: Dict[str, Dict] = {}
        self._org_by_siren: Dict[str, Dict] = {}
        self._activity_by_pair: Dict[Tuple[str, str], Dict] = {}
        self._external_charge_matcher_module = None
        self._external_charge_refs: Optional[List] = None
        self._product_metier_refs: Optional[List] = None
        self._external_charge_matcher_error: Optional[str] = None
        self._scope_metier_by_client: Optional[Dict[str, str]] = None

        # cache common core
        self._common_core_cache: Dict[str, Optional[Dict]] = {}

        # ---------------- STATS (techniques) ----------------
        self.stats = {
            "scan_all_docs": 0,
            "scan_invoice_forms": 0,

            "generated_invoices": 0,
            "generated_entries": 0,

            "supplier_profile_found": 0,
            "supplier_profile_missing": 0,

            "charge_source_external_charge_auto": 0,
            "charge_source_external_charge_validation": 0,
            "charge_source_product_metier_auto": 0,
            "charge_source_product_metier_validation": 0,
            "charge_source_line_item_mixed_auto": 0,
            "charge_source_line_item_mixed_validation": 0,
            "charge_source_supplier_accounts": 0,
            "charge_source_activity_account": 0,

            "activity_pair_found": 0,
            "activity_pair_found_inverse": 0,
            "activity_pair_missing": 0,
        }

        # ---------------- METIER (périmètre éligible uniquement) ----------------
        self.biz = {
            "eligible_invoices_total": 0,     # uniquement 2025 + fournisseur/facture
            "eligible_invoices_treated": 0,
            "eligible_invoices_not_treated": 0,
        }

        # par client: uniquement périmètre éligible
        self.biz_by_client: Dict[str, Dict] = {}

        self._load_reference_data()

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def _create_session(self, username: str, password: str):
        session = CouchDBRequestsSession()
        session.auth = HTTPBasicAuth(username, password)
        if self.cert:
            session.cert = self.cert
        session.verify = self.verify
        return session

    def _biz_client_bucket(self, siren_client: str) -> Dict:
        if siren_client not in self.biz_by_client:
            self.biz_by_client[siren_client] = {
                "eligible": 0,
                "treated": 0,
                "not_treated": 0,
                "charge_via_external_auto": 0,
                "charge_via_external_validation": 0,
                "charge_via_product_auto": 0,
                "charge_via_product_validation": 0,
                "charge_via_mixed_auto": 0,
                "charge_via_mixed_validation": 0,
                "charge_via_supplier": 0,
                "charge_via_ape_direct": 0,
                "charge_via_ape_inverse": 0,
                "reasons": Counter(),
            }
        return self.biz_by_client[siren_client]

    def _load_reference_data(self):
        self._log("Chargement des référentiels (suppliers, kmorganisation, activity_account)...")
        view_result = self.db_entries.view("_all_docs", include_docs=True)

        for row in view_result:
            doc = row.doc or {}
            p = doc.get("p")
            doc_id = doc.get("_id", "")

            if p == "supplier":
                siren = doc.get("siren")
                if siren:
                    self._supplier_by_siren[str(siren)] = doc

            elif p == "kmorganisation":
                if doc_id.startswith("fr_bd_") and ":" in doc_id:
                    prefix = doc_id.split(":", 1)[0]
                    siren = prefix.replace("fr_bd_", "")
                    if siren.isdigit() and len(siren) == 9:
                        self._org_by_siren[siren] = doc

            elif p == "activity_account":
                _id = doc.get("_id", "")
                if _id.startswith("activity_account:"):
                    rest = _id.split("activity_account:", 1)[1]
                    parts = rest.split("_")
                    # format: activity_account:<ape1>_<ape2>_<suffix>
                    if len(parts) >= 2:
                        ape1 = parts[0].strip().upper()
                        ape2 = parts[1].strip().upper()
                        if ape1 and ape2:
                            # NB: si plusieurs docs ont le même couple, le dernier rencontré écrase
                            self._activity_by_pair[(ape1, ape2)] = doc

        self._log(f"  → {len(self._supplier_by_siren)} suppliers")
        self._log(f"  → {len(self._org_by_siren)} kmorganisations")
        self._log(f"  → {len(self._activity_by_pair)} activity_accounts (index COUPLES APE)")

    def get_supplier_profile(self, siren: str) -> Optional[Dict]:
        return self._supplier_by_siren.get(str(siren))

    def get_organization(self, siren: str) -> Optional[Dict]:
        return self._org_by_siren.get(str(siren))

    def get_activity_account_pair(self, client_ape: Optional[str], supplier_ape: Optional[str]) -> Tuple[Optional[Dict], str]:
        """
        Lookup SYMETRIQUE:
          - direct: (client_ape, supplier_ape)
          - inverse: (supplier_ape, client_ape)
        Retourne (doc, mode) avec mode in {"direct","inverse","missing"}.
        """
        if not client_ape or not supplier_ape:
            return None, "missing"

        c = client_ape.strip().upper()
        s = supplier_ape.strip().upper()

        doc = self._activity_by_pair.get((c, s))
        if doc:
            return doc, "direct"

        doc_inv = self._activity_by_pair.get((s, c))
        if doc_inv:
            return doc_inv, "inverse"

        return None, "missing"

    @staticmethod
    def _extract_siren(entity: Dict) -> Optional[str]:
        if not entity:
            return None
        siren = entity.get("siren")
        if siren:
            return str(siren)
        for reg in entity.get("company_registrations", []):
            reg_type = (reg.get("type") or "").lower()
            if reg_type in ("siren", "siret"):
                digits = "".join(filter(str.isdigit, reg.get("value", "")))
                if reg_type == "siret" and len(digits) >= 9:
                    return digits[:9]
                if digits:
                    return digits
        return None

    @staticmethod
    def _extract_supplier_ape_from_issuer(invoice_issuer: Dict) -> Optional[str]:
        if not invoice_issuer:
            return None
        ape = invoice_issuer.get("ape")
        if ape:
            return str(ape).strip().upper()
        for reg in invoice_issuer.get("company_registrations", []):
            if (reg.get("type") or "").upper() == "APE":
                v = reg.get("value")
                if v:
                    return str(v).strip().upper()
        return None

    @staticmethod
    def _to_decimal(value) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    @staticmethod
    def _utc_now_z() -> str:
        return datetime.utcnow().isoformat() + "Z"

    @staticmethod
    def _ddmmyyyy_to_iso(date_str: str) -> str:
        parts = (date_str or "").split("/")
        if len(parts) == 3:
            dd, mm, yyyy = parts
            return f"{yyyy}-{mm}-{dd}"
        return date_str

    @staticmethod
    def _to_float(value) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _to_money(value) -> Optional[float]:
        if value is None:
            return None
        try:
            q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(q)
        except Exception:
            return None

    @staticmethod
    def _approx(a: Optional[float], b: Optional[float], tol: float = 0.03) -> bool:
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol

    def _build_tva_lines_from_invoice(
        self,
        invoice: Dict,
        total_net_hint: Optional[Decimal] = None,
        total_vat_hint: Optional[Decimal] = None,
    ) -> List[Dict]:
        total_net = abs(float(total_net_hint or 0))
        total_vat = abs(float(total_vat_hint or 0))

        # 1) Source prioritaire: line_items (structure la plus fiable)
        by_rate = defaultdict(lambda: {"ht": 0.0, "vat": 0.0})
        has_line_items = False
        for li in invoice.get("line_items") or []:
            rate = self._to_float(li.get("vat_percent"))
            ht = self._to_float(li.get("total_net"))
            vat = self._to_float(li.get("vat_total"))
            if rate is None or ht is None or vat is None:
                continue
            has_line_items = True
            by_rate[rate]["ht"] += abs(ht)
            by_rate[rate]["vat"] += abs(vat)

        if has_line_items and sum(v["vat"] for v in by_rate.values()) > 0:
            lines = []
            for rate, vals in by_rate.items():
                if vals["vat"] <= 0:
                    continue
                lines.append(
                    {
                        "taux": self._to_money(rate),
                        "montant_tva": self._to_money(vals["vat"]),
                        "montant_ht": self._to_money(vals["ht"]),
                    }
                )
            lines.sort(key=lambda x: (x.get("taux") if x.get("taux") is not None else 999.0))
            return lines

        # 2) Fallback: bloc invoice.vat avec désambiguïsation HT/TVA
        vats = invoice.get("vat") or []
        by_rate_vat = defaultdict(lambda: {"ht": 0.0, "vat": 0.0})
        used_vat = False

        for v in vats:
            rate = self._to_float(v.get("vat_percent"))
            amount = abs(self._to_float(v.get("vat_amount")) or 0.0)
            total = abs(self._to_float(v.get("vat_total")) or 0.0)
            if rate is None or rate <= 0:
                continue

            err_amount_is_ht = abs((amount * rate / 100.0) - total)
            err_total_is_ht = abs((total * rate / 100.0) - amount)
            if err_amount_is_ht + 1e-9 < err_total_is_ht:
                ht, vat = amount, total
            elif err_total_is_ht + 1e-9 < err_amount_is_ht:
                ht, vat = total, amount
            else:
                # Cas ambigus (dont amount == total) : on ancre avec les totaux facture.
                if self._approx(amount, total_vat) and total_net > 0:
                    vat = amount
                    ht = amount * 100.0 / rate
                elif self._approx(total, total_vat) and total_net > 0:
                    vat = total
                    ht = total * 100.0 / rate
                elif self._approx(amount, total_net):
                    ht = amount
                    vat = amount * rate / 100.0
                elif self._approx(total, total_net):
                    ht = total
                    vat = total * rate / 100.0
                else:
                    # Mapping dominant observé: vat_amount = HT, vat_total = TVA.
                    ht, vat = amount, total

            by_rate_vat[rate]["ht"] += abs(ht)
            by_rate_vat[rate]["vat"] += abs(vat)
            used_vat = True

        if used_vat:
            positive_rates = [r for r in by_rate_vat if r > 0]
            if len(positive_rates) == 1 and total_vat > 0:
                rate = positive_rates[0]
                by_rate_vat[rate]["vat"] = total_vat
                by_rate_vat[rate]["ht"] = total_net if total_net > 0 else (total_vat * 100.0 / rate)

            lines = []
            for rate, vals in by_rate_vat.items():
                if vals["vat"] <= 0:
                    continue
                lines.append(
                    {
                        "taux": self._to_money(rate),
                        "montant_tva": self._to_money(vals["vat"]),
                        "montant_ht": self._to_money(vals["ht"]),
                    }
                )
            lines.sort(key=lambda x: (x.get("taux") if x.get("taux") is not None else 999.0))
            return lines

        # 3) Dernier fallback: 1 seul taux + totaux facture
        rates = []
        for v in vats:
            rate = self._to_float(v.get("vat_percent"))
            if rate is not None and rate > 0:
                rates.append(rate)
        uniq_rates = sorted({round(r, 6) for r in rates})
        if len(uniq_rates) == 1 and total_vat > 0:
            rate = uniq_rates[0]
            ht = total_net if total_net > 0 else (total_vat * 100.0 / rate)
            return [
                {
                    "taux": self._to_money(rate),
                    "montant_tva": self._to_money(total_vat),
                    "montant_ht": self._to_money(ht),
                }
            ]

        return []

    def _sum_vat_from_lines(
        self,
        invoice: Dict,
        total_net_hint: Optional[Decimal] = None,
        total_vat_hint: Optional[Decimal] = None,
    ) -> Decimal:
        s = Decimal("0")
        for line in self._build_tva_lines_from_invoice(invoice, total_net_hint=total_net_hint, total_vat_hint=total_vat_hint):
            try:
                s += Decimal(str(line.get("montant_tva") or 0))
            except Exception:
                continue
        return s

    # ---------------- Filters ----------------

    def _get_common_core_doc(self, core_id: Optional[str]) -> Optional[Dict]:
        if not core_id:
            return None
        core_id = str(core_id).strip()
        if not core_id:
            return None

        if core_id in self._common_core_cache:
            return self._common_core_cache[core_id]

        try:
            doc = self.db_factures[core_id]
        except Exception:
            doc = None

        self._common_core_cache[core_id] = doc
        return doc

    def _is_supplier_invoice_common_core(self, invoice: Dict) -> bool:
        core_id = (invoice.get("form_common_core_ref", {}) or {}).get("id")
        core_doc = self._get_common_core_doc(core_id)
        if not core_doc:
            return False

        type_contact = (core_doc.get("type_contact") or "").strip().lower()
        type_document = (core_doc.get("type_document") or "").strip().lower()
        return (type_contact == "fournisseur") and (type_document == "facture")

    @staticmethod
    def _is_year_2025(invoice: Dict) -> bool:
        """
        Supporte:
          - invoice_date = "dd/mm/yyyy"
          - invoice_date = "yyyy-mm-dd"
        """
        d = str(invoice.get("invoice_date", "") or "").strip()
        if not d:
            return False

        if "/" in d:
            parts = d.split("/")
            if len(parts) == 3:
                yyyy = parts[2].strip()
                return yyyy == "2025"

        if len(d) >= 10 and d[4] == "-" and d[7] == "-":
            return d[:4] == "2025"

        return False

    # ---------------- JSONL helpers (eligible only) ----------------

    def _write_skipped_jsonl(self, payload: Dict):
        if not self.skipped_jsonl_path:
            return
        try:
            with open(self.skipped_jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            self._log(f"⚠ Impossible d'écrire skipped jsonl: {e}")

    # ---------------- Charge accounts list logic (NO FALLBACK) ----------------

    @staticmethod
    def _normalize_account_obj(a: Dict) -> Dict:
        return {
            "account_number": str((a or {}).get("account_number", "")).strip(),
            "account_description": str((a or {}).get("account_description", "") or "").strip(),
            "account_keywords": str((a or {}).get("account_keywords", "") or "").strip(),
        }

    def _load_external_charge_matcher(self):
        if (
            self._external_charge_matcher_module is not None
            and self._external_charge_refs is not None
            and self._product_metier_refs is not None
        ):
            return self._external_charge_matcher_module, self._external_charge_refs
        if self._external_charge_matcher_error:
            return None, []

        matcher_path = os.path.join(os.path.dirname(__file__), "10_match_reference_v1.py")
        try:
            spec = importlib.util.spec_from_file_location("match_reference_v1_module_for_entries", matcher_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"spec introuvable pour {matcher_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            all_refs = list(module.load_references())
            refs = [ref for ref in all_refs if getattr(ref, "metier", "") == "global"]
            self._product_metier_refs = [ref for ref in all_refs if getattr(ref, "metier", "") not in {"", "global"}]
            self._external_charge_matcher_module = module
            self._external_charge_refs = refs
            return module, refs
        except Exception as exc:
            self._external_charge_matcher_error = str(exc)
            self._log(f"⚠ Matcher charges externes indisponible: {exc}")
            return None, []

    @staticmethod
    def _extract_line_item_text(line_item: Dict) -> str:
        if not isinstance(line_item, dict):
            return ""
        for key in (
            "description",
            "designation",
            "label",
            "libelle",
            "name",
            "item_name",
            "product_name",
            "product_label",
            "article",
            "article_source",
            "text",
            "raw_text",
            "title",
        ):
            value = line_item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _normalize_metier_label(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        raw = str(value).strip().lower()
        mapping = {
            "boulangerie": "boulangerie",
            "boucherie": "boucherie",
            "restaurant": "restaurant",
            "restauration": "restaurant",
            "epicerie": "epicerie",
            "épicerie": "epicerie",
            "transport": "transport",
            "btp": "btp",
            "vtc": "vtc",
        }
        return mapping.get(raw)

    def _load_scope_metier_map(self) -> Dict[str, str]:
        if self._scope_metier_by_client is not None:
            return self._scope_metier_by_client

        scope_map: Dict[str, str] = {}
        scope_dir = os.path.dirname(__file__)
        for filename in os.listdir(scope_dir):
            if not filename.startswith("v1_scope_") or not filename.endswith(".json"):
                continue
            path = os.path.join(scope_dir, filename)
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    payload = json.loads(handle.read())
            except Exception:
                continue
            scope = payload.get("v1_scope") or {}
            client_siren = str(scope.get("client_siren") or "").strip()
            metier = self._normalize_metier_label(scope.get("metier_pilote"))
            if client_siren and metier:
                scope_map[client_siren] = metier

        self._scope_metier_by_client = scope_map
        return scope_map

    def _preferred_metiers_for_context(self, client_siren: str, client_ape: Optional[str]) -> List[str]:
        preferred: List[str] = []
        ape = str(client_ape or "").strip().upper()
        exact_map = {
            "4722Z": ["boucherie"],
            "5610A": ["restaurant"],
            "5610C": ["restaurant"],
            "5621Z": ["restaurant"],
            "5629A": ["restaurant"],
            "1071A": ["boulangerie"],
            "1071C": ["boulangerie"],
            "1071D": ["boulangerie"],
            "4724Z": ["boulangerie"],
            "4932Z": ["vtc", "transport"],
            "4941A": ["transport"],
            "4941B": ["transport"],
            "5229A": ["transport"],
        }
        prefix_map = {
            "41": ["btp"],
            "42": ["btp"],
            "43": ["btp"],
        }
        for metier in exact_map.get(ape, []):
            if metier not in preferred:
                preferred.append(metier)
        for prefix, metiers in prefix_map.items():
            if ape.startswith(prefix):
                for metier in metiers:
                    if metier not in preferred:
                        preferred.append(metier)
        scope_metier = self._load_scope_metier_map().get(str(client_siren))
        if scope_metier and scope_metier not in preferred:
            preferred.append(scope_metier)
        return preferred

    def _patch_external_charge_candidate(self, candidate: Dict, ref, invoice_id: str, supplier_ape: Optional[str]) -> Dict:
        patched = dict(candidate)
        reasons = [part.strip() for part in str(patched.get("raison_match") or "").split(",") if part.strip()]
        score = float(patched.get("score_confiance") or 0.0)

        if supplier_ape:
            ref_ape_context = {str(value).strip().upper() for value in getattr(ref, "ape_context", []) if str(value).strip()}
            if ref_ape_context and supplier_ape.strip().upper() in ref_ape_context:
                score += 5.0
                reasons.append("bonus ape_context fournisseur")

        ref_invoice_ids = set(getattr(ref, "source_invoice_ids", []) or [])
        if invoice_id and invoice_id in ref_invoice_ids:
            score += 2.0
            reasons.append("bonus meme invoice_form source")

        patched["score_confiance"] = round(min(100.0, score), 2)
        patched["raison_match"] = ", ".join(dict.fromkeys(reasons))
        return patched

    @staticmethod
    def _is_exact_article_source_hit(row: Dict) -> bool:
        reason = str((row or {}).get("raison_match") or "")
        if "match exact article_source" in reason:
            return True
        return int((row or {}).get("match_priority") or 0) >= 4

    @staticmethod
    def _has_preferred_metier_bonus(row: Dict) -> bool:
        reason = str((row or {}).get("raison_match") or "")
        return "bonus metier prefere" in reason

    @staticmethod
    def _decide_external_charge_recommendation(top_rows: List[Dict]) -> Tuple[str, List[str], float]:
        if not top_rows:
            return "rejeter", ["aucun_candidat"], 0.0

        alerts: List[str] = []
        top1 = top_rows[0]
        top2_score = float((top_rows[1].get("score_confiance") or 0.0) if len(top_rows) > 1 else 0.0)
        score_gap_top2 = round(float(top1.get("score_confiance") or 0.0) - top2_score, 2)

        decision = str(top1.get("decision_finale") or top1.get("decision") or "validation_humaine")
        if len(top_rows) > 1 and score_gap_top2 < 8.0:
            top2 = top_rows[1]
            top1_account = str(top1.get("compte_comptable") or "").strip()
            top2_account = str(top2.get("compte_comptable") or "").strip()
            top1_profile = str(top1.get("sous_profil") or "").strip()
            top2_profile = str(top2.get("sous_profil") or "").strip()
            top1_exact = AccountingEntryGenerator._is_exact_article_source_hit(top1)
            top2_exact = AccountingEntryGenerator._is_exact_article_source_hit(top2)

            if top1_exact and not top2_exact:
                decision = "auto_ok"
            elif top1_exact and top2_exact and top1_account and top1_account == top2_account:
                decision = "auto_ok"
            elif top1_account != top2_account or top1_profile != top2_profile:
                alerts.append("top_candidates_too_close")
                decision = "validation_humaine"

        if float(top1.get("score_confiance") or 0.0) < 70.0:
            alerts.append("score_trop_faible")
            decision = "validation_humaine"

        return decision, alerts, score_gap_top2

    def _recommend_external_charge_accounts_from_invoice(
        self,
        invoice: Dict,
        supplier_ape: Optional[str],
    ) -> Tuple[Optional[List[Dict]], Optional[Dict], Optional[str]]:
        matcher_module, refs = self._load_external_charge_matcher()
        if matcher_module is None or not refs:
            return None, None, None

        invoice_id = str(invoice.get("_id") or "").strip()
        line_recommendations: List[Dict] = []

        for idx, line_item in enumerate(invoice.get("line_items") or [], start=1):
            line_text = self._extract_line_item_text(line_item)
            if not line_text:
                continue

            tva_hint = self._to_float(line_item.get("vat_percent"))
            scored: List[Dict] = []
            for ref in refs:
                row = matcher_module.score_reference(line_text, ref, metier_hint="global", tva_hint=tva_hint)
                row = self._patch_external_charge_candidate(row, ref, invoice_id=invoice_id, supplier_ape=supplier_ape)
                scored.append(row)

            scored.sort(
                key=lambda row: (
                    -float(row.get("score_confiance") or 0.0),
                    -int(row.get("match_priority") or 0),
                    -matcher_module.decision_rank(row.get("decision_finale")),
                    -matcher_module.coherence_rank(row.get("tva_coherence")),
                    str(row.get("article_source_match") or ""),
                    str(row.get("compte_comptable") or ""),
                )
            )

            top3 = scored[:3]
            if not top3:
                continue
            top1 = top3[0]
            if str(top1.get("decision_finale") or "") == "rejeter":
                continue
            if not matcher_module.is_external_charge_like(line_text) and float(top1.get("score_confiance") or 0.0) < 85.0:
                continue

            decision, alerts, score_gap_top2 = self._decide_external_charge_recommendation(top3)
            line_recommendations.append(
                {
                    "line_index": idx,
                    "line_text": line_text,
                    "tva_hint": tva_hint,
                    "predicted_account": str(top1.get("compte_comptable") or "").strip(),
                    "predicted_sous_profil": str(top1.get("sous_profil") or "").strip(),
                    "predicted_profil_facturation": str(top1.get("profil_facturation") or "").strip(),
                    "predicted_score": float(top1.get("score_confiance") or 0.0),
                    "recommendation_decision": decision,
                    "recommendation_alerts": alerts,
                    "score_gap_top2": score_gap_top2,
                    "top1_reason": str(top1.get("raison_match") or "").strip(),
                    "top3_accounts": [str(row.get("compte_comptable") or "").strip() for row in top3 if str(row.get("compte_comptable") or "").strip()],
                    "top3_articles": [str(row.get("article_source_match") or "").strip() for row in top3 if str(row.get("article_source_match") or "").strip()],
                }
            )

        if not line_recommendations:
            return None, None, None

        accounts_by_number: Dict[str, Dict] = {}
        for rec in line_recommendations:
            account_number = rec["predicted_account"]
            if not account_number:
                continue
            existing = accounts_by_number.get(account_number)
            if existing:
                existing["line_count"] += 1
                if rec["line_text"] not in existing["examples"]:
                    existing["examples"].append(rec["line_text"])
                continue
            accounts_by_number[account_number] = {
                "account_number": account_number,
                "account_description": f"Reco charges externes - {rec['predicted_sous_profil'] or 'a valider'}",
                "account_keywords": rec["line_text"],
                "line_count": 1,
                "examples": [rec["line_text"]],
            }

        if not accounts_by_number:
            return None, None, None

        account_list: List[Dict] = []
        for data in sorted(accounts_by_number.values(), key=lambda row: (-row["line_count"], row["account_number"])):
            account_list.append(
                {
                    "account_number": data["account_number"],
                    "account_description": data["account_description"],
                    "account_keywords": " | ".join(data["examples"][:3]),
                }
            )

        overall_decision = "auto_ok"
        overall_alerts: Set[str] = set()
        for rec in line_recommendations:
            if rec["recommendation_decision"] != "auto_ok":
                overall_decision = "validation_humaine"
            overall_alerts.update(rec["recommendation_alerts"])

        if overall_decision == "auto_ok":
            source_label = "external_charge_recommendation_auto"
        else:
            source_label = "external_charge_recommendation_validation"

        details = {
            "classification": "charge_externe",
            "line_items_considered": len(line_recommendations),
            "decision": overall_decision,
            "alerts": sorted(overall_alerts),
            "recommended_accounts": account_list,
            "line_matches": line_recommendations,
        }
        return account_list, details, source_label

    def _load_product_metier_matcher(self):
        module, _ = self._load_external_charge_matcher()
        if module is None:
            return None, []
        return module, list(self._product_metier_refs or [])

    def _patch_product_metier_candidate(
        self,
        candidate: Dict,
        ref,
        invoice_id: str,
        client_ape: Optional[str],
        preferred_metiers: List[str],
    ) -> Dict:
        patched = dict(candidate)
        reasons = [part.strip() for part in str(patched.get("raison_match") or "").split(",") if part.strip()]
        score = float(patched.get("score_confiance") or 0.0)

        if client_ape:
            ref_ape_context = {str(value).strip().upper() for value in getattr(ref, "ape_context", []) if str(value).strip()}
            if ref_ape_context and client_ape.strip().upper() in ref_ape_context:
                score += 5.0
                reasons.append("bonus ape_context client")

        ref_invoice_ids = set(getattr(ref, "source_invoice_ids", []) or [])
        if invoice_id and invoice_id in ref_invoice_ids:
            score += 2.0
            reasons.append("bonus meme invoice_form source")

        ref_metier = str(getattr(ref, "metier", "") or "").strip()
        if preferred_metiers and ref_metier:
            if ref_metier == preferred_metiers[0]:
                score += 3.0
                reasons.append("bonus metier prefere")
            elif ref_metier in preferred_metiers:
                score += 1.5
                reasons.append("bonus metier probable")

        patched["score_confiance"] = round(min(100.0, score), 2)
        patched["raison_match"] = ", ".join(dict.fromkeys(reasons))
        return patched

    @staticmethod
    def _decide_product_metier_recommendation(top_rows: List[Dict]) -> Tuple[str, List[str], float]:
        if not top_rows:
            return "rejeter", ["aucun_candidat"], 0.0

        alerts: List[str] = []
        top1 = top_rows[0]
        top2_score = float((top_rows[1].get("score_confiance") or 0.0) if len(top_rows) > 1 else 0.0)
        score_gap_top2 = round(float(top1.get("score_confiance") or 0.0) - top2_score, 2)

        decision = str(top1.get("decision_finale") or top1.get("decision") or "validation_humaine")
        if len(top_rows) > 1 and score_gap_top2 < 8.0:
            top2 = top_rows[1]
            top1_account = str(top1.get("compte_comptable") or "").strip()
            top2_account = str(top2.get("compte_comptable") or "").strip()
            top1_metier = str(top1.get("metier") or "").strip()
            top2_metier = str(top2.get("metier") or "").strip()
            top1_exact = AccountingEntryGenerator._is_exact_article_source_hit(top1)
            top2_exact = AccountingEntryGenerator._is_exact_article_source_hit(top2)
            top1_pref = AccountingEntryGenerator._has_preferred_metier_bonus(top1)
            top2_pref = AccountingEntryGenerator._has_preferred_metier_bonus(top2)

            if top1_exact and not top2_exact:
                decision = "auto_ok"
            elif top1_exact and top2_exact and top1_account and top1_account == top2_account:
                decision = "auto_ok"
            elif top1_exact and top2_exact and top1_pref and not top2_pref:
                decision = "auto_ok"
            elif top1_account != top2_account or top1_metier != top2_metier:
                alerts.append("top_candidates_too_close")
                decision = "validation_humaine"

        if float(top1.get("score_confiance") or 0.0) < 70.0:
            alerts.append("score_trop_faible")
            decision = "validation_humaine"

        return decision, alerts, score_gap_top2

    def _recommend_product_metier_accounts_from_invoice(
        self,
        invoice: Dict,
        client_siren: str,
        client_ape: Optional[str],
    ) -> Tuple[Optional[List[Dict]], Optional[Dict], Optional[str]]:
        matcher_module, refs = self._load_product_metier_matcher()
        if matcher_module is None or not refs:
            return None, None, None

        invoice_id = str(invoice.get("_id") or "").strip()
        preferred_metiers = self._preferred_metiers_for_context(client_siren, client_ape)
        metier_hint = preferred_metiers[0] if preferred_metiers else None
        line_recommendations: List[Dict] = []

        for idx, line_item in enumerate(invoice.get("line_items") or [], start=1):
            line_text = self._extract_line_item_text(line_item)
            if not line_text or matcher_module.is_external_charge_like(line_text):
                continue

            tva_hint = self._to_float(line_item.get("vat_percent"))
            scored: List[Dict] = []
            for ref in refs:
                row = matcher_module.score_reference(line_text, ref, metier_hint=metier_hint, tva_hint=tva_hint)
                row = self._patch_product_metier_candidate(
                    row,
                    ref,
                    invoice_id=invoice_id,
                    client_ape=client_ape,
                    preferred_metiers=preferred_metiers,
                )
                scored.append(row)

            scored.sort(
                key=lambda row: (
                    -float(row.get("score_confiance") or 0.0),
                    -int(row.get("match_priority") or 0),
                    -matcher_module.decision_rank(row.get("decision_finale")),
                    -matcher_module.coherence_rank(row.get("metier_coherence")),
                    -matcher_module.coherence_rank(row.get("tva_coherence")),
                    str(row.get("article_source_match") or ""),
                    str(row.get("compte_comptable") or ""),
                )
            )

            top3 = scored[:3]
            if not top3:
                continue
            top1 = top3[0]
            if str(top1.get("decision_finale") or "") == "rejeter":
                continue
            if float(top1.get("score_confiance") or 0.0) < 80.0:
                continue

            decision, alerts, score_gap_top2 = self._decide_product_metier_recommendation(top3)
            line_recommendations.append(
                {
                    "line_index": idx,
                    "line_text": line_text,
                    "tva_hint": tva_hint,
                    "predicted_account": str(top1.get("compte_comptable") or "").strip(),
                    "predicted_metier": str(top1.get("metier") or "").strip(),
                    "predicted_categorie": str(top1.get("categorie") or "").strip(),
                    "predicted_sous_categorie": str(top1.get("sous_categorie") or "").strip(),
                    "predicted_score": float(top1.get("score_confiance") or 0.0),
                    "recommendation_decision": decision,
                    "recommendation_alerts": alerts,
                    "score_gap_top2": score_gap_top2,
                    "top1_reason": str(top1.get("raison_match") or "").strip(),
                    "top3_accounts": [str(row.get("compte_comptable") or "").strip() for row in top3 if str(row.get("compte_comptable") or "").strip()],
                    "top3_metiers": [str(row.get("metier") or "").strip() for row in top3 if str(row.get("metier") or "").strip()],
                    "top3_articles": [str(row.get("article_source_match") or "").strip() for row in top3 if str(row.get("article_source_match") or "").strip()],
                }
            )

        if not line_recommendations:
            return None, None, None

        accounts_by_number: Dict[str, Dict] = {}
        for rec in line_recommendations:
            account_number = rec["predicted_account"]
            if not account_number:
                continue
            existing = accounts_by_number.get(account_number)
            if existing:
                existing["line_count"] += 1
                if rec["line_text"] not in existing["examples"]:
                    existing["examples"].append(rec["line_text"])
                continue
            label = rec["predicted_sous_categorie"] or rec["predicted_categorie"] or "a_valider"
            accounts_by_number[account_number] = {
                "account_number": account_number,
                "account_description": f"Reco produit metier - {rec['predicted_metier']}/{label}",
                "account_keywords": rec["line_text"],
                "line_count": 1,
                "examples": [rec["line_text"]],
            }

        if not accounts_by_number:
            return None, None, None

        account_list: List[Dict] = []
        for data in sorted(accounts_by_number.values(), key=lambda row: (-row["line_count"], row["account_number"])):
            account_list.append(
                {
                    "account_number": data["account_number"],
                    "account_description": data["account_description"],
                    "account_keywords": " | ".join(data["examples"][:3]),
                }
            )

        overall_decision = "auto_ok"
        overall_alerts: Set[str] = set()
        predicted_metiers: Set[str] = set()
        for rec in line_recommendations:
            predicted_metiers.add(rec["predicted_metier"])
            if rec["recommendation_decision"] != "auto_ok":
                overall_decision = "validation_humaine"
            overall_alerts.update(rec["recommendation_alerts"])

        if overall_decision == "auto_ok":
            source_label = "product_metier_recommendation_auto"
        else:
            source_label = "product_metier_recommendation_validation"

        details = {
            "classification": "produit_metier",
            "line_items_considered": len(line_recommendations),
            "decision": overall_decision,
            "alerts": sorted(overall_alerts),
            "preferred_metiers": preferred_metiers,
            "metier_hint_used": metier_hint,
            "predicted_metiers": sorted(value for value in predicted_metiers if value),
            "recommended_accounts": account_list,
            "line_matches": line_recommendations,
        }
        return account_list, details, source_label

    def _merge_line_item_recommendations(
        self,
        external_accounts: Optional[List[Dict]],
        external_details: Optional[Dict],
        external_src: Optional[str],
        product_accounts: Optional[List[Dict]],
        product_details: Optional[Dict],
        product_src: Optional[str],
    ) -> Tuple[Optional[List[Dict]], Optional[Dict], Optional[str]]:
        if external_accounts and not product_accounts:
            return external_accounts, external_details, external_src
        if product_accounts and not external_accounts:
            return product_accounts, product_details, product_src
        if not external_accounts and not product_accounts:
            return None, None, None

        merged_by_number: Dict[str, Dict] = {}
        for source_accounts in (external_accounts or [], product_accounts or []):
            for account in source_accounts:
                account_number = str((account or {}).get("account_number") or "").strip()
                if not account_number:
                    continue
                existing = merged_by_number.get(account_number)
                if not existing:
                    merged_by_number[account_number] = dict(account)
                    continue
                for key in ("account_description", "account_keywords"):
                    existing_value = str(existing.get(key) or "").strip()
                    new_value = str(account.get(key) or "").strip()
                    if new_value and new_value not in existing_value:
                        existing[key] = f"{existing_value} | {new_value}".strip(" |")

        merged_accounts = sorted(
            merged_by_number.values(),
            key=lambda row: str((row or {}).get("account_number") or ""),
        )
        external_decision = str((external_details or {}).get("decision") or "")
        product_decision = str((product_details or {}).get("decision") or "")
        overall_decision = "auto_ok"
        if "validation_humaine" in {external_decision, product_decision}:
            overall_decision = "validation_humaine"

        if overall_decision == "auto_ok":
            source_label = "line_item_recommendation_mixed_auto"
        else:
            source_label = "line_item_recommendation_mixed_validation"

        details = {
            "classification": "mixte_produit_et_charge",
            "decision": overall_decision,
            "recommended_accounts": merged_accounts,
            "external_charge_recommendation": external_details,
            "product_metier_recommendation": product_details,
        }
        return merged_accounts, details, source_label

    def _resolve_charge_accounts_list_no_fallback(
        self,
        supplier_profile: Optional[Dict],
        client_ape: Optional[str],
        supplier_ape: Optional[str],
    ) -> Tuple[Optional[List[Dict]], str]:
        """
        Retourne (accounts_list, source_label).
        Si rien trouvé: (None, reason)
        """

        # 1) supplier_profile.accounts
        supplier_accounts_raw = (supplier_profile or {}).get("accounts") or []
        if supplier_accounts_raw:
            out: List[Dict] = []
            for a in supplier_accounts_raw:
                obj = self._normalize_account_obj(a or {})
                if obj["account_number"]:
                    out.append(obj)
            if out:
                self.stats["charge_source_supplier_accounts"] += 1
                return out, "supplier_accounts"

        # 2) couple APE (symétrique)
        couple_doc, couple_mode = self.get_activity_account_pair(client_ape, supplier_ape)
        if couple_doc:
            self.stats["activity_pair_found"] += 1
            if couple_mode == "inverse":
                self.stats["activity_pair_found_inverse"] += 1
        else:
            self.stats["activity_pair_missing"] += 1

        couple_accounts_raw = (couple_doc or {}).get("accounts") or []
        if couple_accounts_raw:
            out = []
            for a in couple_accounts_raw:
                obj = self._normalize_account_obj(a or {})
                if obj["account_number"]:
                    out.append(obj)
            if out:
                self.stats["charge_source_activity_account"] += 1
                if couple_mode == "inverse":
                    return out, "activity_account_inverse"
                return out, "activity_account"

        # Aucun fallback
        if not client_ape:
            return None, "no_charge_accounts_client_ape_missing"
        if not supplier_ape:
            return None, "no_charge_accounts_supplier_ape_missing"
        return None, "no_charge_accounts_no_match_supplier_or_activity_account"

    # ---------------- Generation ----------------

    def generate_entries_from_invoice(self, invoice: Dict) -> Tuple[List[Dict], Optional[str], bool]:
        """
        Retourne (entries, reason, is_business_eligible)

        - is_business_eligible = False => hors périmètre métier => ignoré totalement dans le report
        - is_business_eligible = True  => périmètre métier éligible:
              - entries non vides => traité
              - entries vides => non traité (reason renseignée)
        """
        entries: List[Dict] = []
        invoice_id = invoice.get("_id", "") or ""

        # HORS PERIMETRE METIER => ignorer
        if not self._is_year_2025(invoice):
            return [], "skip_not_year_2025", False

        # HORS PERIMETRE METIER => ignorer
        if not self._is_supplier_invoice_common_core(invoice):
            return [], "skip_not_common_core_supplier_invoice", False

        # A partir d'ici, on est dans le périmètre métier
        if not invoice_id.startswith("fr_bd_") or ":" not in invoice_id:
            return [], "skip_bad_invoice_id", True

        siren_client = invoice_id.split(":", 1)[0].replace("fr_bd_", "")
        issuer = invoice.get("issuer", {}) or {}
        siren_fournisseur = self._extract_siren(issuer)
        if not siren_fournisseur:
            return [], "skip_no_supplier_siren", True

        # supplier profile (peut être None)
        supplier_profile = self.get_supplier_profile(siren_fournisseur)
        if supplier_profile:
            self.stats["supplier_profile_found"] += 1
        else:
            self.stats["supplier_profile_missing"] += 1

        # org/ape client
        organization = self.get_organization(siren_client)
        client_ape = (organization.get("ape") if organization else None)
        client_ape = str(client_ape).strip().upper() if client_ape else None

        # ape supplier
        supplier_ape = self._extract_supplier_ape_from_issuer(issuer)

        # Résolution comptes de charges SANS fallback
        external_charge_details = None
        product_metier_details = None
        external_accounts, external_charge_details, external_src = self._recommend_external_charge_accounts_from_invoice(
            invoice, supplier_ape
        )
        product_accounts, product_metier_details, product_src = self._recommend_product_metier_accounts_from_invoice(
            invoice, siren_client, client_ape
        )
        charge_accounts_list, line_item_details, charge_src = self._merge_line_item_recommendations(
            external_accounts,
            external_charge_details,
            external_src,
            product_accounts,
            product_metier_details,
            product_src,
        )
        if not charge_accounts_list:
            charge_accounts_list, charge_src = self._resolve_charge_accounts_list_no_fallback(
                supplier_profile, client_ape, supplier_ape
            )
        if not charge_accounts_list:
            return [], charge_src, True

        if charge_src == "external_charge_recommendation_auto":
            self.stats["charge_source_external_charge_auto"] += 1
        elif charge_src == "external_charge_recommendation_validation":
            self.stats["charge_source_external_charge_validation"] += 1
        elif charge_src == "product_metier_recommendation_auto":
            self.stats["charge_source_product_metier_auto"] += 1
        elif charge_src == "product_metier_recommendation_validation":
            self.stats["charge_source_product_metier_validation"] += 1
        elif charge_src == "line_item_recommendation_mixed_auto":
            self.stats["charge_source_line_item_mixed_auto"] += 1
        elif charge_src == "line_item_recommendation_mixed_validation":
            self.stats["charge_source_line_item_mixed_validation"] += 1

        invoice_number = invoice.get("invoice_number")
        invoice_date = invoice.get("invoice_date", "")
        iso_date = self._ddmmyyyy_to_iso(invoice_date)
        nowz = self._utc_now_z()

        total_ttc = self._to_decimal(invoice.get("total_gross", 0))
        total_net = self._to_decimal(invoice.get("total_net", 0))

        if invoice.get("total_vat") is not None:
            total_vat = self._to_decimal(invoice.get("total_vat"))
        else:
            total_vat = self._sum_vat_from_lines(invoice, total_net_hint=total_net)

        if total_net == 0 and total_ttc > 0 and total_vat > 0:
            total_net = total_ttc - total_vat
        if total_vat == 0 and total_ttc > 0 and total_net > 0:
            diff = total_ttc - total_net
            if diff > 0:
                total_vat = diff

        is_credit_note = total_ttc < 0
        abs_ttc = abs(total_ttc)
        abs_net = abs(total_net)
        abs_vat = abs(total_vat)

        # Compte fournisseur: fallback compte fournisseur uniquement si supplier absent
        supplier_account = (supplier_profile or {}).get("number") or "401"
        auxiliary_code = (supplier_profile or {}).get("auxiliary_code", "") or ""
        aux_account = auxiliary_code.strip() if auxiliary_code else None

        supplier_label = (supplier_profile or {}).get("label") or (issuer.get("name") or "Fournisseur inconnu")

        piece_id = f"fr_bd_{siren_client}:piece:generated:{uuid.uuid4().hex}"
        piece_ref = invoice_number

        tva_lines = self._build_tva_lines_from_invoice(invoice, total_net_hint=total_net, total_vat_hint=total_vat)
        if not tva_lines and abs_vat > 0:
            tva_lines = [
                {
                    "taux": None,
                    "montant_tva": self._to_money(abs_vat),
                    "montant_ht": self._to_money(abs_net) if abs_net > 0 else None,
                }
            ]

        invoice_data = {
            "invoice_form_id": invoice_id,
            "core_profile_id": (invoice.get("form_common_core_ref", {}) or {}).get("id"),
            "numero_facture": invoice_number,
            "date_facture": invoice_date,
            "montant_ttc": float(abs_ttc),
            "siren_emetteur": siren_fournisseur,
            "siren_destinataire": siren_client,
            "matched_at": nowz,
            "km_ape": client_ape,
            "supplier_ape": supplier_ape,
            "charge_resolution_source": charge_src,  # supplier_accounts | activity_account | activity_account_inverse
        }
        if external_charge_details:
            invoice_data["external_charge_recommendation"] = external_charge_details
        if product_metier_details:
            invoice_data["product_metier_recommendation"] = product_metier_details
        if line_item_details:
            invoice_data["line_item_recommendation"] = line_item_details

        def mk(debit: float, credit: float) -> Tuple[float, float]:
            return (credit, debit) if is_credit_note else (debit, credit)

        line_seq = 1

        # 1) 401 TTC
        d, c = mk(0.0, float(abs_ttc))
        entries.append(self._make_entry(
            siren_client, iso_date, piece_id, piece_ref, supplier_label, nowz, invoice_data,
            line_seq, debit=d, credit=c, account_number=supplier_account, aux_account=aux_account, tva_lines=tva_lines
        ))
        line_seq += 1

        # 2) 445661 TVA
        if abs_vat > 0:
            d, c = mk(float(abs_vat), 0.0)
            entries.append(self._make_entry(
                siren_client, iso_date, piece_id, piece_ref, supplier_label, nowz, invoice_data,
                line_seq, debit=d, credit=c, account_number="445661", aux_account=None, tva_lines=tva_lines
            ))
            line_seq += 1

        # 3) Charge HT (LISTE)
        d, c = mk(float(abs_net), 0.0)
        entries.append(self._make_entry(
            siren_client, iso_date, piece_id, piece_ref, supplier_label, nowz, invoice_data,
            line_seq, debit=d, credit=c, account_number=charge_accounts_list, aux_account=None, tva_lines=tva_lines
        ))

        self.stats["generated_invoices"] += 1
        self.stats["generated_entries"] += len(entries)

        return entries, None, True

    def _make_entry(
        self,
        siren_client: str,
        iso_date: str,
        piece_id: str,
        piece_ref: str,
        label: str,
        nowz: str,
        invoice_data: Dict,
        line_seq: int,
        debit: float,
        credit: float,
        account_number: Union[str, List[Dict]],
        aux_account: Optional[str],
        tva_lines: List[Dict],
    ) -> Dict:
        return {
            "_id": f"fr_bd_{siren_client}:generated:{uuid.uuid4().hex}",
            "p": "entry",
            "is_generated": True,
            "data": {
                "collection": "Entry",
                "type": "",
                "sub_type": "",
                "subprofile": "experimental",
            },
            "date": iso_date,
            "fiscal_year_uid": "fiscalyear:18d3de9e4c4043f9a98fe54413326414",
            "journal_code": "AC",
            "number": "440",
            "line_seq": line_seq,
            "label": label,
            "piece_ref": piece_ref,
            "piece_date": iso_date,
            "piece_id": piece_id,
            "debit": float(debit),
            "credit": float(credit),
            "account_number": account_number,
            "aux_account": aux_account,
            "matching": None,
            "matching_date": None,
            "tva_lines": tva_lines,
            "created_at": nowz,
            "updated_at": nowz,
            "invoice": invoice_data,
        }

    @staticmethod
    def _parse_clients_arg(clients_arg: Optional[str]) -> Optional[Set[str]]:
        if not clients_arg:
            return None
        raw = clients_arg.replace(",", " ").replace("\n", " ").replace("\t", " ")
        parts = [p.strip() for p in raw.split(" ") if p.strip()]
        out = set()
        for p in parts:
            digits = "".join([c for c in p if c.isdigit()])
            if len(digits) == 9:
                out.add(digits)
        return out if out else None

    def _save_batch(self, entries: List[Dict]) -> Tuple[int, int]:
        if not entries:
            return 0, 0

        try:
            results = self.db_entries.update(entries)
        except Exception as e:
            self._log(f"  ✗ Erreur bulk pour un batch de {len(entries)} docs: {e}")
            return 0, len(entries)

        success = 0
        errors = 0
        for ok, docid, info in results:
            if ok:
                success += 1
            else:
                errors += 1
                if self.verbose:
                    self._log(f"  ✗ Erreur doc {docid}: {info}")

        self._log(f"  → Batch sauvegardé: {success} OK / {errors} erreurs")
        info = self.db_entries.info()
        self._log("DB entries info: name=" + self.db_entries.name + " doc_count=" + str(info.get("doc_count")))
        return success, errors

    def _render_report_txt(self, errors: int):
        def fmt_pct(a: int, b: int) -> str:
            if b <= 0:
                return "0%"
            return f"{(100.0 * a / b):.1f}%"

        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("REPORT METIER - Génération écritures 2025 (périmètre: fournisseur + facture)")
        lines.append(f"Generated at (UTC): {datetime.utcnow().isoformat()}Z")
        lines.append("=" * 80)
        lines.append("")

        eligible = self.biz["eligible_invoices_total"]
        treated = self.biz["eligible_invoices_treated"]
        not_treated = self.biz["eligible_invoices_not_treated"]

        lines.append("Synthèse périmètre métier (uniquement factures 2025 + fournisseur/facture)")
        lines.append(f"  - Factures éligibles métier: {eligible}")
        lines.append(f"  - Factures traitées: {treated} ({fmt_pct(treated, eligible)})")
        lines.append(f"  - Factures non traitées: {not_treated} ({fmt_pct(not_treated, eligible)})")
        lines.append(f"  - Écritures créées (total): {self.stats['generated_entries']}")
        lines.append(f"  - Erreurs bulk: {errors}")
        lines.append(f"  - Reco charges externes (auto): {self.stats['charge_source_external_charge_auto']}")
        lines.append(f"  - Reco charges externes (validation): {self.stats['charge_source_external_charge_validation']}")
        lines.append(f"  - Reco produits metier (auto): {self.stats['charge_source_product_metier_auto']}")
        lines.append(f"  - Reco produits metier (validation): {self.stats['charge_source_product_metier_validation']}")
        lines.append(f"  - Reco mixte ligne facture (auto): {self.stats['charge_source_line_item_mixed_auto']}")
        lines.append(f"  - Reco mixte ligne facture (validation): {self.stats['charge_source_line_item_mixed_validation']}")
        lines.append("")
        lines.append("Couples APE lookup (symétrique)")
        lines.append(f"  - Trouvés (direct ou inverse): {self.stats['activity_pair_found']}")
        lines.append(f"  - Dont via inverse: {self.stats['activity_pair_found_inverse']}")
        lines.append(f"  - Manquants: {self.stats['activity_pair_missing']}")
        lines.append("")

        clients_sorted = sorted(
            self.biz_by_client.items(),
            key=lambda kv: kv[1].get("eligible", 0),
            reverse=True
        )

        lines.append("Détail par client (SIREN) - périmètre éligible uniquement")
        lines.append("")

        for siren_client, b in clients_sorted:
            elig = b["eligible"]
            tr = b["treated"]
            nt = b["not_treated"]

            if elig == 0:
                continue

            lines.append("-" * 80)
            lines.append(f"Client {siren_client}")
            lines.append(f"  - Factures éligibles: {elig}")
            lines.append(f"  - Traitées: {tr} ({fmt_pct(tr, elig)})")
            lines.append(f"  - Non traitées: {nt} ({fmt_pct(nt, elig)})")
            lines.append(f"  - Comptes charges via reco externe (auto): {b['charge_via_external_auto']}")
            lines.append(f"  - Comptes charges via reco externe (validation): {b['charge_via_external_validation']}")
            lines.append(f"  - Comptes via reco produit metier (auto): {b['charge_via_product_auto']}")
            lines.append(f"  - Comptes via reco produit metier (validation): {b['charge_via_product_validation']}")
            lines.append(f"  - Comptes via reco mixte ligne facture (auto): {b['charge_via_mixed_auto']}")
            lines.append(f"  - Comptes via reco mixte ligne facture (validation): {b['charge_via_mixed_validation']}")
            lines.append(f"  - Comptes charges via supplier: {b['charge_via_supplier']}")
            lines.append(f"  - Comptes charges via couple APE (direct): {b['charge_via_ape_direct']}")
            lines.append(f"  - Comptes charges via couple APE (inverse): {b['charge_via_ape_inverse']}")

            if nt > 0:
                lines.append("  - Principales causes (non traitées):")
                for reason, count in b["reasons"].most_common(10):
                    lines.append(f"      * {reason}: {count}")
            lines.append("")

        global_reasons = Counter()
        for _, b in self.biz_by_client.items():
            global_reasons.update(b["reasons"])

        lines.append("=" * 80)
        lines.append("Causes globales (périmètre métier éligible uniquement)")
        for reason, count in global_reasons.most_common(50):
            lines.append(f"  - {reason}: {count}")

        try:
            with open(self.report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            self._log(f"✗ Impossible d'écrire le report txt: {e}")

    def rebuild_all_entries(self, batch_size: int = 1000, clients: Optional[Set[str]] = None):
        self._log(f"\n{'='*60}")
        self._log("Début du traitement (report métier client par client) - NO FALLBACK charges")
        self._log("Périmètre report: uniquement factures 2025 + common core (fournisseur/facture)")
        self._log("Lookup activity_account: SYMETRIQUE (direct + inverse)")
        if clients:
            self._log(f"Filtre clients (SIREN): {', '.join(sorted(clients))}")
        self._log(f"{'='*60}\n")

        view_result = self.db_factures.view("_all_docs", include_docs=True)

        processed_docs = 0
        errors = 0
        batch: List[Dict] = []

        for row in view_result:
            self.stats["scan_all_docs"] += 1

            doc = row.doc or {}
            if doc.get("p") != "invoice_form":
                continue

            self.stats["scan_invoice_forms"] += 1

            invoice_id = doc.get("_id", "") or ""
            if not invoice_id.startswith("fr_bd_") or ":" not in invoice_id:
                # ignore report (pas exploitable)
                continue

            siren_client = invoice_id.split(":", 1)[0].replace("fr_bd_", "")
            if clients and siren_client not in clients:
                # hors scope du run => ignoré
                continue

            entries, reason, is_eligible = self.generate_entries_from_invoice(doc)

            if not is_eligible:
                # hors périmètre métier => ignoré totalement
                continue

            # éligible métier
            self.biz["eligible_invoices_total"] += 1
            bucket = self._biz_client_bucket(siren_client)
            bucket["eligible"] += 1

            if not entries:
                r = reason or "skip_unknown"
                self.biz["eligible_invoices_not_treated"] += 1
                bucket["not_treated"] += 1
                bucket["reasons"][r] += 1

                if self.verbose:
                    self._log(f"Facture ELIGIBLE non traitée: {r} -> {invoice_id} (num={doc.get('invoice_number')})")

                issuer = doc.get("issuer", {}) or {}
                siren_fournisseur = self._extract_siren(issuer)
                supplier_ape = self._extract_supplier_ape_from_issuer(issuer)
                org = self.get_organization(siren_client)
                client_ape = (org.get("ape") if org else None)
                client_ape = str(client_ape).strip().upper() if client_ape else None

                self._write_skipped_jsonl({
                    "invoice_id": invoice_id,
                    "invoice_number": doc.get("invoice_number"),
                    "invoice_date": doc.get("invoice_date"),
                    "client_siren": siren_client,
                    "supplier_siren": siren_fournisseur,
                    "km_ape": client_ape,
                    "supplier_ape": supplier_ape,
                    "reason": r,
                    "business_scope": "eligible_2025_supplier_invoice",
                })
                continue

            # traité
            self.biz["eligible_invoices_treated"] += 1
            bucket["treated"] += 1

            src = ((entries[0] or {}).get("invoice", {}) or {}).get("charge_resolution_source")
            if src == "external_charge_recommendation_auto":
                bucket["charge_via_external_auto"] += 1
            elif src == "external_charge_recommendation_validation":
                bucket["charge_via_external_validation"] += 1
            elif src == "product_metier_recommendation_auto":
                bucket["charge_via_product_auto"] += 1
            elif src == "product_metier_recommendation_validation":
                bucket["charge_via_product_validation"] += 1
            elif src == "line_item_recommendation_mixed_auto":
                bucket["charge_via_mixed_auto"] += 1
            elif src == "line_item_recommendation_mixed_validation":
                bucket["charge_via_mixed_validation"] += 1
            elif src == "supplier_accounts":
                bucket["charge_via_supplier"] += 1
            elif src == "activity_account":
                bucket["charge_via_ape_direct"] += 1
            elif src == "activity_account_inverse":
                bucket["charge_via_ape_inverse"] += 1

            if self.verbose:
                self._log(f"Facture traitée (éligible): {doc.get('invoice_number')} ({invoice_id})")

            batch.extend(entries)

            if len(batch) >= batch_size:
                ok, err = self._save_batch(batch)
                processed_docs += ok
                errors += err
                batch = []

        if batch:
            ok, err = self._save_batch(batch)
            processed_docs += ok
            errors += err

        # Report métier
        self._render_report_txt(errors=errors)

        self._log(f"\n{'='*60}")
        self._log("Traitement terminé (périmètre métier):")
        self._log(f"  - Factures éligibles: {self.biz['eligible_invoices_total']}")
        self._log(f"  - Factures traitées: {self.biz['eligible_invoices_treated']}")
        self._log(f"  - Factures non traitées: {self.biz['eligible_invoices_not_treated']}")
        self._log(f"  - Écritures créées: {self.stats['generated_entries']}")
        self._log(f"  - Erreurs bulk: {errors}")
        self._log(f"  - Report écrit: {os.path.abspath(self.report_path)}")
        if self.skipped_jsonl_path:
            self._log(f"  - Skipped JSONL (eligible only): {os.path.abspath(self.skipped_jsonl_path)}")
        self._log(f"{'='*60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Génère des écritures comptables 2025 (périmètre: fournisseur+facture) - report métier client par client - NO FALLBACK charges - lookup couple APE symétrique."
    )
    parser.add_argument("--db-factures", default=os.getenv("DB_FACTURES", "abt3"), help="Base CouchDB des factures.")
    parser.add_argument(
        "--db-entries",
        default=os.getenv("DB_ENTRIES", "ayasmine_test"),
        help="Base CouchDB où écrire les écritures générées (2025).",
    )
    parser.add_argument("--batch-size", type=int, default=1000, help="Taille des batches CouchDB.")
    parser.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=True, help="Logs détaillés.")
    parser.add_argument(
        "--clients",
        default=os.getenv("CLIENTS", ""),
        help="Liste SIREN clients à traiter (séparateurs: espace, virgule, nouvelle ligne).",
    )
    parser.add_argument(
        "--report-path",
        default=os.getenv("REPORT_PATH", "entries_generation_report.txt"),
        help="Chemin du fichier report txt.",
    )
    parser.add_argument(
        "--skipped-jsonl",
        default=os.getenv("SKIPPED_JSONL", "skipped_invoices.jsonl"),
        help="Chemin du fichier skipped invoices (jsonl) - uniquement périmètre métier éligible. Mettre vide pour désactiver.",
    )
    args = parser.parse_args()

    COUCHDB_URL = os.getenv("COUCHDB_URL", DEFAULT_COUCHDB_URL)

    DB_FACTURES = args.db_factures
    COUCHDB_USER_FACTURES = DEFAULT_COUCHDB_USER
    COUCHDB_PASS_FACTURES = DEFAULT_COUCHDB_PASS

    DB_ENTRIES = args.db_entries
    COUCHDB_USER_ENTRIES = DEFAULT_COUCHDB_USER
    COUCHDB_PASS_ENTRIES = DEFAULT_COUCHDB_PASS

    CLIENT_CERT = os.getenv("CLIENT_CERT", DEFAULT_CLIENT_CERT)
    CLIENT_KEY = os.getenv("CLIENT_KEY", DEFAULT_CLIENT_KEY)
    CA_CERT = os.getenv("CA_CERT", DEFAULT_CA_CERT)

    skipped_jsonl_path = args.skipped_jsonl.strip() if args.skipped_jsonl else ""
    skipped_jsonl_path = skipped_jsonl_path if skipped_jsonl_path else None

    print("Démarrage de la génération des écritures 2025 (report métier, NO FALLBACK charges, couple APE symétrique)...")
    print(f"DB Factures: {DB_FACTURES}")
    print(f"DB Entries (cible): {DB_ENTRIES}")
    print(f"Report: {args.report_path}")
    print(f"Skipped JSONL (eligible only): {skipped_jsonl_path}")
    print(f"{'='*60}\n")

    generator = AccountingEntryGenerator(
        couch_url=COUCHDB_URL,
        db_factures=DB_FACTURES,
        db_entries=DB_ENTRIES,
        user_factures=COUCHDB_USER_FACTURES,
        pass_factures=COUCHDB_PASS_FACTURES,
        user_entries=COUCHDB_USER_ENTRIES,
        pass_entries=COUCHDB_PASS_ENTRIES,
        client_cert=CLIENT_CERT,
        client_key=CLIENT_KEY,
        ca_cert=CA_CERT,
        verbose=args.verbose,
        report_path=args.report_path,
        skipped_jsonl_path=skipped_jsonl_path,
    )

    clients_set = generator._parse_clients_arg(args.clients)
    generator.rebuild_all_entries(batch_size=args.batch_size, clients=clients_set)
