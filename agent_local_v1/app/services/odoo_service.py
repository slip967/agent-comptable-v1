from __future__ import annotations

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from xmlrpc import client as xmlrpc_client

from ..config import (
    ODOO_ACCOUNT_CODE_MAP,
    ODOO_DB,
    ODOO_MOCK_MODE,
    ODOO_PASSWORD,
    ODOO_TAX_SCOPE_BY_ACCOUNT,
    ODOO_URL,
    ODOO_USERNAME,
)


logger = logging.getLogger(__name__)


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


def _company_context(models: Any, uid: int) -> tuple[int | None, dict[str, Any]]:
    """Return the user's active company and an explicit multi-company context."""
    users = _execute_kw(
        models,
        uid,
        "res.users",
        "read",
        [[uid]],
        {"fields": ["company_id", "company_ids"]},
    )
    user = users[0] if users else {}
    raw_company = user.get("company_id")
    company_id = (
        int(raw_company[0])
        if isinstance(raw_company, (list, tuple)) and raw_company
        else int(raw_company)
        if raw_company
        else None
    )
    allowed_company_ids = [int(value) for value in (user.get("company_ids") or [])]
    if company_id and company_id not in allowed_company_ids:
        allowed_company_ids.insert(0, company_id)
    context: dict[str, Any] = {"allowed_company_ids": allowed_company_ids}
    if company_id:
        context["force_company"] = company_id
    return company_id, context


def _validated_account_code(line: dict[str, Any]) -> str:
    """Resolve the final KeyManage account, giving human corrections priority."""
    validation_result = (
        line.get("human_validation_result")
        if isinstance(line.get("human_validation_result"), dict)
        else {}
    )
    corrected_account = str(
        line.get("corrected_account")
        or validation_result.get("corrected_account")
        or ""
    ).strip()
    if corrected_account:
        return corrected_account
    if str(validation_result.get("action") or "").strip() == "correct_account":
        return ""
    return str(
        line.get("recommended_account")
        or line.get("accounting_account")
        or line.get("account")
        or ""
    ).strip()


def _find_account_id(
    models: Any,
    uid: int,
    account_code: str,
    *,
    company_id: int | None,
    context: dict[str, Any],
) -> int | None:
    code = str(account_code or "").strip()
    if not code:
        logger.warning("Export Odoo : aucun code comptable validé reçu pour la ligne.")
        return None

    domain: list[Any] = [("code", "=", code)]
    if company_id:
        domain.append(("company_id", "=", company_id))
    accounts = _execute_kw(
        models,
        uid,
        "account.account",
        "search_read",
        [domain],
        {
            "fields": ["id", "code", "name", "company_id"],
            "limit": 1,
            "context": context,
        },
    )
    if not accounts:
        logger.warning(
            "Export Odoo : compte introuvable pour le code %s dans la société %s ; "
            "la ligne sera créée sans account_id explicite.",
            code,
            company_id or "active",
        )
        return None
    account_id = int(accounts[0]["id"])
    logger.info(
        "Export Odoo : compte %s trouvé, account_id=%s, société=%s.",
        code,
        account_id,
        company_id or "active",
    )
    return account_id


def _mapped_odoo_account_code(keymanage_account_code: str) -> str | None:
    code = str(keymanage_account_code or "").strip()
    if not code:
        logger.warning("Export Odoo : aucun compte final validé reçu pour la ligne.")
        return None
    mapped_code = str(ODOO_ACCOUNT_CODE_MAP.get(code) or "").strip()
    if not mapped_code:
        logger.warning(
            "Export Odoo : aucun mapping explicite défini pour le compte KeyManage %s ; "
            "aucun account_id ne sera imposé.",
            code,
        )
        return None
    logger.info(
        "Export Odoo : mapping comptable appliqué, KeyManage %s -> Odoo %s.",
        code,
        mapped_code,
    )
    return mapped_code


def _tax_scope_from_value(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"service", "services", "prestation", "prestations"}:
        return "service"
    if normalized in {"consu", "goods", "good", "bien", "biens", "product", "produit"}:
        return "consu"
    return None


def _line_tax_scope(line: dict[str, Any], account_code: str) -> tuple[str | None, str]:
    """Resolve goods/service without guessing from the line label."""
    for field in ("tax_scope", "item_type", "line_type", "product_type", "nature"):
        if field not in line:
            continue
        scope = _tax_scope_from_value(line.get(field))
        if scope:
            return scope, f"line.{field}"
        logger.warning(
            "Export Odoo : nature de ligne non reconnue dans %s=%r.",
            field,
            line.get(field),
        )

    configured_scope = _tax_scope_from_value(
        ODOO_TAX_SCOPE_BY_ACCOUNT.get(str(account_code or "").strip())
    )
    if configured_scope:
        return configured_scope, f"account_mapping:{account_code}"
    return None, "unresolved"


def _boolean_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "oui", "included", "inclusive", "ttc"}:
        return True
    if normalized in {"0", "false", "no", "non", "excluded", "exclusive", "ht"}:
        return False
    return None


def _line_price_include(line: dict[str, Any]) -> tuple[bool, str]:
    for field in ("price_include", "tax_included", "vat_included", "ttc_included"):
        if field not in line:
            continue
        resolved = _boolean_value(line.get(field))
        if resolved is not None:
            return resolved, f"line.{field}"

    # Le connecteur utilise amount_ht comme price_unit. La taxe Odoo doit donc
    # être non incluse, même lorsque le montant TTC est également disponible.
    if any(line.get(field) not in (None, "") for field in ("amount_ht", "total_ht", "ht", "total_net")):
        return False, "exported_amount_ht"
    return False, "connector_price_unit_ht_default"


def _find_purchase_tax(
    models: Any,
    uid: int,
    vat_rate: float,
    *,
    tax_scope: str,
    price_include: bool,
    company_id: int | None,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    domain: list[Any] = [
        ("type_tax_use", "=", "purchase"),
        ("amount_type", "=", "percent"),
        ("amount", "=", vat_rate),
        ("tax_scope", "=", tax_scope),
        ("price_include", "=", price_include),
        ("active", "=", True),
    ]
    if company_id:
        domain.append(("company_id", "=", company_id))
    taxes = _execute_kw(
        models,
        uid,
        "account.tax",
        "search_read",
        [domain],
        {
            "fields": [
                "id",
                "name",
                "amount",
                "tax_scope",
                "price_include",
                "company_id",
            ],
            "limit": 50,
            "context": context,
        },
    )
    if not taxes:
        return None

    # l10n_fr contient plusieurs taxes au même taux et dans le même périmètre
    # (UE, import, immobilier...). La taxe d'achat nationale standard porte le
    # nom court "<taux>% G" ou "<taux>% S". On ne retient jamais arbitrairement
    # la première taxe lorsque plusieurs variantes existent.
    standard_suffix = "S" if tax_scope == "service" else "G"
    included_suffix = " INC" if price_include else ""
    expected_name = f"{vat_rate:g}% {standard_suffix}{included_suffix}".casefold()
    exact_standard = [
        tax
        for tax in taxes
        if str(tax.get("name") or "").strip().casefold() == expected_name
    ]
    if len(exact_standard) == 1:
        return exact_standard[0]
    if len(exact_standard) > 1:
        logger.warning(
            "Export Odoo : plusieurs taxes standard nommées %s correspondent à achat, "
            "taux=%s, nature=%s, prix_inclus=%s, société=%s ; résolution refusée.",
            expected_name,
            vat_rate,
            tax_scope,
            price_include,
            company_id or "active",
        )
    else:
        logger.warning(
            "Export Odoo : %s taxes correspondent à achat, taux=%s, nature=%s, "
            "prix_inclus=%s, société=%s, mais aucune ne porte le nom standard %s ; "
            "résolution refusée.",
            len(taxes),
            vat_rate,
            tax_scope,
            price_include,
            company_id or "active",
            expected_name,
        )
    return None


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
            try:
                return path.read_bytes(), str(invoice_data.get("pdf_filename") or path.name)
            except OSError as exc:
                invoice_data["pdf_error"] = f"Lecture du PDF impossible : {exc}"
                logger.warning("Export Odoo : lecture du PDF impossible depuis %s : %s", path, exc)
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
    company_id, company_context = _company_context(models, uid)
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
    tax_cache: dict[tuple[float, str, bool, int | None], dict[str, Any] | None] = {}
    account_resolutions: list[dict[str, Any]] = []
    tax_resolutions: list[dict[str, Any]] = []
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
        account_code = _validated_account_code(line)
        logger.info(
            "Export Odoo : ligne %s, code comptable validé reçu=%s.",
            index,
            account_code or "absent",
        )
        odoo_account_code = _mapped_odoo_account_code(account_code)
        account_id = (
            _find_account_id(
                models,
                uid,
                odoo_account_code,
                company_id=company_id,
                context=company_context,
            )
            if odoo_account_code
            else None
        )
        if account_id:
            line_values["account_id"] = account_id
        account_resolutions.append(
            {
                "line": index,
                "account_code": account_code or None,
                "keymanage_account_code": account_code or None,
                "odoo_account_code": odoo_account_code,
                "mapping_found": bool(odoo_account_code),
                "account_id": account_id,
                "found": bool(account_id),
            }
        )
        tax_id: int | None = None
        tax_name: str | None = None
        tax_scope, tax_scope_source = _line_tax_scope(line, account_code)
        price_include, price_include_source = _line_price_include(line)
        if vat_rate > 0:
            if tax_scope:
                tax_key = (vat_rate, tax_scope, price_include, company_id)
                if tax_key not in tax_cache:
                    tax_cache[tax_key] = _find_purchase_tax(
                        models,
                        uid,
                        vat_rate,
                        tax_scope=tax_scope,
                        price_include=price_include,
                        company_id=company_id,
                        context=company_context,
                    )
                tax = tax_cache[tax_key]
                if tax:
                    tax_id = int(tax["id"])
                    tax_name = str(tax.get("name") or "").strip() or None
                    logger.info(
                        "Export Odoo : ligne %s, taxe trouvée=%s, tax_id=%s, taux=%s, "
                        "nature=%s (%s), prix_inclus=%s (%s).",
                        index,
                        tax_name or "sans libellé",
                        tax_id,
                        vat_rate,
                        tax_scope,
                        tax_scope_source,
                        price_include,
                        price_include_source,
                    )
            else:
                logger.warning(
                    "Export Odoo : ligne %s, TVA %s%% non résolue car la nature bien/service "
                    "est absente ; aucun choix arbitraire de taxe ne sera effectué.",
                    index,
                    vat_rate,
                )
        if tax_id:
            line_values["tax_ids"] = [(6, 0, [tax_id])]
        tax_resolutions.append(
            {
                "line": index,
                "vat_rate": vat_rate,
                "tax_scope": tax_scope,
                "tax_scope_source": tax_scope_source,
                "price_include": price_include,
                "price_include_source": price_include_source,
                "tax_id": tax_id,
                "tax_name": tax_name,
                "found": bool(tax_id),
            }
        )
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

    move_id = int(
        _execute_kw(
            models,
            uid,
            "account.move",
            "create",
            [move_values],
            {"context": company_context},
        )
    )
    logger.info("Export Odoo : facture fournisseur créée, move_id=%s.", move_id)
    attachment_id: int | None = None
    pdf = _pdf_payload(invoice_data)
    attachment_error: str | None = str(invoice_data.get("pdf_error") or "").strip() or None
    if pdf:
        pdf_bytes, filename = pdf
        pdf_source = str(invoice_data.get("pdf_source") or filename or "PDF fourni").strip()
        logger.info("Export Odoo : source PDF utilisée=%s.", pdf_source)
        attachment_values = {
            "name": filename or f"facture_{move_id}.pdf",
            "type": "binary",
            "datas": base64.b64encode(pdf_bytes).decode("ascii"),
            "mimetype": "application/pdf",
            "res_model": "account.move",
            "res_id": move_id,
        }
        try:
            attachment_id = int(
                _execute_kw(
                    models,
                    uid,
                    "ir.attachment",
                    "create",
                    [attachment_values],
                    {"context": company_context},
                )
            )
            attachment_error = None
            logger.info(
                "Export Odoo : pièce jointe PDF créée, attachment_id=%s, move_id=%s.",
                attachment_id,
                move_id,
            )
        except OdooExportError as exc:
            attachment_error = str(exc)
            logger.error(
                "Export Odoo : facture move_id=%s créée, mais ajout du PDF impossible : %s",
                move_id,
                exc,
            )
    elif attachment_error:
        logger.warning(
            "Export Odoo : facture move_id=%s créée sans PDF : %s",
            move_id,
            attachment_error,
        )
    else:
        attachment_error = "Document PDF source indisponible."
        logger.warning("Export Odoo : facture move_id=%s créée sans PDF source.", move_id)

    return {
        "move_id": move_id,
        "partner_id": partner_id,
        "attachment_id": attachment_id,
        "attachment_created": bool(attachment_id),
        "attachment_error": attachment_error,
        "company_id": company_id,
        "account_resolutions": account_resolutions,
        "tax_resolutions": tax_resolutions,
        "missing_account_codes": sorted(
            {
                str(item["account_code"])
                for item in account_resolutions
                if item.get("mapping_found") and not item.get("found")
            }
        ),
        "unmapped_account_codes": sorted(
            {
                str(item["keymanage_account_code"])
                for item in account_resolutions
                if item.get("keymanage_account_code") and not item.get("mapping_found")
            }
        ),
    }
