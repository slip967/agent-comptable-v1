from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any
from xmlrpc import client as xmlrpc_client

from ..config import (
    ODOO_DB,
    ODOO_MOCK_MODE,
    ODOO_PASSWORD,
    ODOO_URL,
    ODOO_USERNAME,
)


class OdooConfigurationError(RuntimeError):
    """Raised when the Odoo connector is not configured for live usage."""


class OdooAuthenticationError(RuntimeError):
    """Raised when Odoo rejects the configured credentials."""


class OdooExportError(RuntimeError):
    """Raised when an XML-RPC operation fails during invoice export."""


def _validate_settings() -> None:
    if ODOO_MOCK_MODE:
        raise OdooConfigurationError("L'export Odoo réel est désactivé par ODOO_MOCK_MODE.")
    missing = [
        name
        for name, value in (
            ("ODOO_URL", ODOO_URL),
            ("ODOO_DB", ODOO_DB),
            ("ODOO_USERNAME", ODOO_USERNAME),
            ("ODOO_PASSWORD", ODOO_PASSWORD),
        )
        if not str(value or "").strip()
    ]
    if missing:
        raise OdooConfigurationError(
            "Configuration Odoo incomplète : " + ", ".join(missing)
        )


def _models_proxy():
    return xmlrpc_client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object",
        allow_none=True,
    )


def get_odoo_uid() -> int:
    """Authenticate against Odoo and return the numeric user identifier."""
    _validate_settings()
    try:
        common = xmlrpc_client.ServerProxy(
            f"{ODOO_URL}/xmlrpc/2/common",
            allow_none=True,
        )
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    except (OSError, xmlrpc_client.Error) as exc:
        raise OdooAuthenticationError(f"Connexion à Odoo impossible : {exc}") from exc
    if not uid:
        raise OdooAuthenticationError(
            "Authentification Odoo refusée. Vérifiez la base, l'utilisateur et le mot de passe."
        )
    return int(uid)


def _execute_kw(
    models: Any,
    uid: int,
    model: str,
    method: str,
    args: list[Any],
    kwargs: dict[str, Any] | None = None,
) -> Any:
    try:
        return models.execute_kw(
            ODOO_DB,
            uid,
            ODOO_PASSWORD,
            model,
            method,
            args,
            kwargs or {},
        )
    except (OSError, xmlrpc_client.Error) as exc:
        raise OdooExportError(f"Odoo {model}.{method} a échoué : {exc}") from exc


def _get_or_create_partner_with_connection(
    partner_name: str,
    vat_siret: str | None,
    *,
    uid: int,
    models: Any,
) -> int:
    name = str(partner_name or "").strip()
    vat = str(vat_siret or "").strip()
    if not name:
        raise OdooExportError("Le nom du fournisseur est requis pour l'export Odoo.")

    if vat:
        domain: list[Any] = ["|", ("name", "=ilike", name), ("vat", "=", vat)]
    else:
        domain = [("name", "=ilike", name)]
    partners = _execute_kw(
        models,
        uid,
        "res.partner",
        "search_read",
        [domain],
        {"fields": ["id", "name", "vat"], "limit": 1},
    )
    if partners:
        return int(partners[0]["id"])

    values: dict[str, Any] = {
        "name": name,
        "supplier_rank": 1,
        "company_type": "company",
    }
    if vat:
        values["vat"] = vat
    return int(_execute_kw(models, uid, "res.partner", "create", [values]))


def get_or_create_partner(partner_name: str, vat_siret: str | None = None) -> int:
    """Return an existing supplier partner or create it in Odoo."""
    uid = get_odoo_uid()
    return _get_or_create_partner_with_connection(
        partner_name,
        vat_siret,
        uid=uid,
        models=_models_proxy(),
    )


def _first_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            return value
    return default


def _amount_ht(line: dict[str, Any]) -> float:
    raw = _first_value(
        line,
        "amount_ht",
        "total_ht",
        "ht",
        "total_net",
        "price_unit",
        default=0,
    )
    try:
        return round(float(raw or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _amount_ttc(line: dict[str, Any]) -> float | None:
    raw = _first_value(line, "amount_ttc", "total_ttc", "ttc", "total_gross")
    if raw is None:
        return None
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


def _vat_rate(line: dict[str, Any]) -> float:
    raw = _first_value(
        line,
        "vat_rate",
        "vat_percent",
        "taux_tva",
        "tax_rate",
        "tva",
    )
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        rate = 0.0
    if rate > 0:
        return round(rate, 4)

    amount_ht = _amount_ht(line)
    amount_ttc = _amount_ttc(line)
    if amount_ht > 0 and amount_ttc is not None and amount_ttc > amount_ht:
        return round(((amount_ttc / amount_ht) - 1) * 100, 4)
    return 0.0


def _find_currency_id(models: Any, uid: int, currency_name: str = "EUR") -> int:
    currencies = _execute_kw(
        models,
        uid,
        "res.currency",
        "search_read",
        [[("name", "=", currency_name)]],
        {"fields": ["id", "name"], "limit": 1},
    )
    if not currencies:
        raise OdooExportError(
            f"La devise {currency_name} est introuvable dans Odoo. Activez-la avant l'export."
        )
    return int(currencies[0]["id"])


def _find_purchase_tax_id(models: Any, uid: int, vat_rate: float) -> int | None:
    taxes = _execute_kw(
        models,
        uid,
        "account.tax",
        "search_read",
        [[("type_tax_use", "=", "purchase"), ("amount", "=", vat_rate)]],
        {"fields": ["id", "name", "amount"], "limit": 1},
    )
    return int(taxes[0]["id"]) if taxes else None


def _pdf_payload(invoice_data: dict[str, Any]) -> tuple[bytes, str] | None:
    pdf_bytes = invoice_data.get("pdf_bytes")
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    if isinstance(pdf_bytes, bytes) and pdf_bytes:
        filename = str(invoice_data.get("pdf_filename") or "facture.pdf").strip()
        return pdf_bytes, filename

    pdf_path = str(invoice_data.get("pdf_path") or "").strip()
    if pdf_path:
        path = Path(pdf_path)
        if path.is_file():
            return path.read_bytes(), str(invoice_data.get("pdf_filename") or path.name)
    return None


def _odoo_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], pattern).date().isoformat()
        except ValueError:
            continue
    return None


def export_invoice_to_odoo(invoice_data: dict[str, Any]) -> dict[str, Any]:
    """Create an Odoo 17 vendor bill and optionally attach its source PDF."""
    uid = get_odoo_uid()
    models = _models_proxy()
    currency_id = _find_currency_id(models, uid, "EUR")
    supplier = str(
        _first_value(invoice_data, "supplier", "supplier_name", "partner_name", default="")
        or ""
    ).strip()
    vat_siret = str(
        _first_value(
            invoice_data,
            "vat_siret",
            "supplier_siret",
            "supplier_vat",
            "siret",
            default="",
        )
        or ""
    ).strip()
    partner_id = _get_or_create_partner_with_connection(
        supplier,
        vat_siret,
        uid=uid,
        models=models,
    )

    source_lines = invoice_data.get("lines") or invoice_data.get("invoice_line_ids") or []
    if not isinstance(source_lines, list) or not source_lines:
        raise OdooExportError("La facture ne contient aucune ligne exportable vers Odoo.")
    invoice_lines = []
    tax_cache: dict[float, int | None] = {}
    for index, source_line in enumerate(source_lines, start=1):
        line = source_line if isinstance(source_line, dict) else {}
        label = str(
            _first_value(
                line,
                "label",
                "description",
                "cleaned_text",
                "raw_text",
                "article_source",
                default=f"Ligne {index}",
            )
            or f"Ligne {index}"
        ).strip()
        amount_ht = _amount_ht(line)
        amount_ttc = _amount_ttc(line)
        vat_rate = _vat_rate(line)
        line_values: dict[str, Any] = {
            "name": label,
            "price_unit": amount_ht,
            "quantity": 1.0,
        }
        tax_id: int | None = None
        if vat_rate > 0:
            if vat_rate not in tax_cache:
                tax_cache[vat_rate] = _find_purchase_tax_id(models, uid, vat_rate)
            tax_id = tax_cache[vat_rate]
        if tax_id:
            line_values["tax_ids"] = [(6, 0, [tax_id])]
        invoice_lines.append((0, 0, line_values))

        if vat_rate > 0 and not tax_id:
            fallback_vat = (
                round(amount_ttc - amount_ht, 2)
                if amount_ttc is not None and amount_ttc > amount_ht
                else round(amount_ht * vat_rate / 100, 2)
            )
            if fallback_vat > 0:
                invoice_lines.append(
                    (
                        0,
                        0,
                        {
                            "name": f"TVA {vat_rate:g}% — taxe d'achat Odoo introuvable",
                            "price_unit": fallback_vat,
                            "quantity": 1.0,
                        },
                    )
                )

    move_values: dict[str, Any] = {
        "move_type": "in_invoice",
        "partner_id": partner_id,
        "currency_id": currency_id,
        "invoice_line_ids": invoice_lines,
    }
    invoice_number = str(
        _first_value(invoice_data, "invoice_number", "reference", "ref", default="") or ""
    ).strip()
    if invoice_number:
        move_values["ref"] = invoice_number
    invoice_date = _odoo_date(invoice_data.get("invoice_date"))
    if invoice_date:
        move_values["invoice_date"] = invoice_date

    move_id = int(_execute_kw(models, uid, "account.move", "create", [move_values]))
    attachment_id: int | None = None
    pdf = _pdf_payload(invoice_data)
    if pdf:
        pdf_bytes, filename = pdf
        attachment_values = {
            "name": filename or f"facture_{move_id}.pdf",
            "type": "binary",
            "datas": base64.b64encode(pdf_bytes).decode("ascii"),
            "mimetype": "application/pdf",
            "res_model": "account.move",
            "res_id": move_id,
        }
        attachment_id = int(
            _execute_kw(models, uid, "ir.attachment", "create", [attachment_values])
        )

    return {
        "move_id": move_id,
        "partner_id": partner_id,
        "attachment_id": attachment_id,
    }
