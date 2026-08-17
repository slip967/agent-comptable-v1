from __future__ import annotations

import base64
import json
import re
import tempfile
from pathlib import Path
from typing import Any

import requests
from fastapi import HTTPException, UploadFile

from .agent import OpenRouterModelUnavailableError, run_agent
from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_APP_URL,
    OPENROUTER_VISION_FALLBACK_MODELS,
    OPENROUTER_VISION_MODEL,
)
from .database import get_supplier_memory, get_validation_patterns
from .account_labels import get_account_label
from .local_knowledge_bases import DISPLAY_LABELS, local_knowledge_bases
from .schemas import (
    AccountingDecision,
    InvoiceAISignals,
    InvoiceAnalysisResponse,
    InvoiceLineAnalysis,
    InvoiceTopCandidate,
    OCRInvoiceExtraction,
    OCRInvoiceLine,
    OCRInvoiceIssuer,
    OCRInvoiceLineItem,
    OCRInvoiceRecipient,
    OCRTextAnalysisInput,
)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL_UNAVAILABLE_DETAIL = (
    "Modele OpenRouter indisponible. Veuillez changer OPENROUTER_MODEL."
)
OPENROUTER_VISION_MODEL_UNAVAILABLE_DETAIL = (
    "Modele OpenRouter indisponible. Veuillez changer OPENROUTER_VISION_MODEL "
    "ou analyser le texte OCR deja extrait."
)
ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
COMMON_TVA_RATES = (0.0, 5.5, 10.0, 20.0)
PDF_OCR_ENGINES = ("mistral-ocr", "cloudflare-ai")
SUPPLIER_PREFIX_RE = re.compile(r"^\s*(?:fournisseur|emetteur|émetteur|vendor)\s*:\s*(.+?)\s*$", re.IGNORECASE)
RECIPIENT_PREFIX_RE = re.compile(r"^\s*(?:destinataire|client|recipient)\s*:\s*(.+?)\s*$", re.IGNORECASE)
ARTICLE_PREFIX_RE = re.compile(r"^\s*(?:article|produit|description)\s*:\s*(.+?)\s*$", re.IGNORECASE)


OCR_SYSTEM_PROMPT = (
    "Tu es un extracteur OCR de factures fournisseur. "
    "Tu recois une facture PDF ou image et tu dois extraire un JSON strict. "
    "Tu ne dois retourner que les informations visibles sur le document. "
    "Tu dois retourner une structure complete de facture, avec emetteur, destinataire, lignes, TVA, totaux et paiement si visibles. "
    "Les line_items doivent contenir uniquement les achats/services detectes, pas les blocs administratifs ni les totaux. "
    "Pour chaque line_item, copie le texte visible sans correction dans raw_line_text. "
    "Produis aussi label et description comme un libelle produit ou service clair et exploitable. "
    "Decode les abreviations metier cryptiques uniquement lorsque le contexte permet de le faire sans ambiguite "
    "(par exemple M.FIB en Manche Fibre, STK en Stock). Si une abreviation est incertaine, conserve-la et n'invente rien. "
    "Si une information est absente, retourne null."
)

OCR_USER_PROMPT = (
    "Analyse cette facture et retourne un JSON valide avec ce schema metier : "
    "invoice_number, invoice_date, document_type, issuer{}, recipient{}, line_items[], "
    "flag_articles_atypiques, vat[], discount_percent, discount_amount, cash_discount_percent, "
    "cash_discount_amount, deposit_amount, down_payment_amount, total_net, total_vat, total_gross, "
    "accounting_summary[], payment{}, currency. "
    "Pour chaque line_item, retourne au minimum raw_line_text, label, description, quantity, unit_price, total_net, "
    "total_gross et vat_percent si visibles. raw_line_text doit rester la transcription exacte du document; "
    "label et description contiennent la version lisible et explicitee."
)


def _display_metier(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized == "global":
        return "charges_externes"
    return normalized


def _normalize_score(value: float | int | None) -> float:
    try:
        return round(float(value or 0.0), 1)
    except Exception:
        return 0.0


def _allowed_extension(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Formats acceptes: .pdf, .png, .jpg, .jpeg",
        )
    return suffix


def _guess_content_type(filename: str, upload: UploadFile) -> str:
    suffix = _allowed_extension(filename)
    if suffix == ".pdf":
        return "application/pdf"
    return IMAGE_MIME_TYPES.get(suffix, upload.content_type or "image/jpeg")


def _save_temp_file(upload: UploadFile, suffix: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(upload.file.read())
        tmp.flush()
    finally:
        tmp.close()
    return Path(tmp.name)


def _cleanup_temp_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _file_to_data_url(path: Path, content_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def _extract_embedded_pdf_text(path: Path) -> str:
    """Fallback non-OCR: extracts selectable text already embedded in a PDF."""
    parts: list[str] = []

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for page in reader.pages:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                parts.append(text)
    except Exception:
        parts = []

    if parts:
        return "\n".join(parts).strip()

    try:
        import fitz

        with fitz.open(str(path)) as document:
            for page in document:
                text = page.get_text("text") or ""
                text = text.strip()
                if text:
                    parts.append(text)
    except Exception:
        return ""

    return "\n".join(parts).strip()


def _openrouter_headers() -> dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY manquante dans .env. L'OCR distant est indisponible.",
        )

    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_NAME,
    }


def _extract_annotations_text(response_json: dict[str, Any]) -> str:
    messages = response_json.get("choices") or []
    if not messages:
        error_annotations = (
            ((response_json.get("error") or {}).get("metadata") or {}).get("file_annotations") or []
        )
        annotations = error_annotations
    else:
        annotations = ((messages[0].get("message") or {}).get("annotations")) or []

    parts: list[str] = []
    for annotation in annotations:
        file_payload = annotation.get("file") if isinstance(annotation, dict) else None
        content = file_payload.get("content") if isinstance(file_payload, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
    return "\n".join(parts).strip()


def _extract_json_from_text(content: str) -> dict[str, Any] | None:
    if not content:
        return None

    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _is_openrouter_provider_error(detail: str) -> bool:
    message = str(detail or "").lower()
    return (
        "no endpoints found" in message
        or "no allowed providers" in message
        or ("provider" in message and "available" in message)
    )


def _looks_like_invoice_line(raw_line: str) -> bool:
    line = str(raw_line or "").strip()
    if len(line) < 3:
        return False
    if SUPPLIER_PREFIX_RE.match(line) or RECIPIENT_PREFIX_RE.match(line):
        return False

    normalized = line.lower()
    forbidden = (
        "total",
        "tva",
        "ttc",
        "ht",
        "iban",
        "siret",
        "adresse",
        "telephone",
        "tel",
        "email",
        "facture",
        "client",
        "date",
        "echeance",
        "paiement",
        "page",
        "siege",
        "objet",
        "votre contact",
        "france",
        "capital",
        "www.",
    )
    if any(token in normalized for token in forbidden):
        return False

    return bool(re.search(r"[a-zA-Z]", line))


def _parse_french_amount(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", str(value))
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _match_text(pattern: str, raw_text: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, raw_text, flags)
    if not match:
        return None
    return re.sub(r"\s+", " ", str(match.group(1) or "")).strip(" -:;|")


def _extract_prefixed_value(pattern: re.Pattern[str], raw_text: str) -> str | None:
    for line in raw_text.splitlines():
        match = pattern.match(line)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" -:;|")
            if value:
                return value
    return None


def _infer_supplier_name(raw_text: str) -> str | None:
    prefixed = _extract_prefixed_value(SUPPLIER_PREFIX_RE, raw_text)
    if prefixed:
        return prefixed

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return None
    first = re.sub(r"\s+-\s+.*$", "", lines[0]).strip()
    if first:
        return first
    return None


def _infer_recipient_name(raw_text: str) -> str | None:
    prefixed = _extract_prefixed_value(RECIPIENT_PREFIX_RE, raw_text)
    if prefixed:
        return prefixed

    header_match = re.search(r"Description\s+Qte\s+PU\s+HT\s+TVA\s+Total\s+HT\s*\n(.+)", raw_text, re.IGNORECASE)
    if header_match:
        candidate = header_match.group(1).strip()
        if candidate and "ALEO AGENCY" not in candidate.upper():
            return candidate

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.search(r"\b\d{5}\b", line) and index > 0:
            previous = lines[index - 1].strip()
            if previous and not re.search(r"(siege|siret|email|page|facture|france)", previous, re.IGNORECASE):
                return previous
    return None


def _extract_line_items_from_text(raw_text: str) -> list[OCRInvoiceLineItem]:
    lines = [re.sub(r"\s+", " ", line).strip(" -:;|") for line in raw_text.splitlines()]
    line_items: list[OCRInvoiceLineItem] = []
    for line in lines:
        match = ARTICLE_PREFIX_RE.match(line)
        if not match:
            continue
        description = re.sub(r"\s+", " ", match.group(1)).strip(" -:;|")
        if description:
            line_items.append(
                OCRInvoiceLineItem(
                    description=description,
                    item_type=None,
                    quantity=None,
                    unit=None,
                    unit_price=None,
                    total_net=None,
                    total_gross=None,
                    vat_percent=None,
                )
            )

    if line_items:
        return line_items[:20]

    amount_block = re.search(
        r"(?P<quantity>\d+,\d{2})\s+(?P<unit_price>\d+,\d{2})\s*\n"
        r"\s*(?P<unit>[^\n]+?)\s*\n"
        r"\s*(?P<vat_percent>\d+,\d{2})\s*%\s*\n"
        r"\s*\(?(?P<vat_total>\d+,\d{2})\)?\s*\n"
        r"\s*(?P<total_net>\d+,\d{2})",
        raw_text,
        re.IGNORECASE,
    )

    if amount_block and "PACK ALEO VOYAGER" in raw_text.upper():
        description_parts: list[str] = []
        capture = False
        for line in lines:
            upper_line = line.upper()
            if upper_line == "PACK ALEO VOYAGER":
                capture = True
            if capture:
                if upper_line.startswith("CRÉATION") or upper_line.startswith("CREATION"):
                    break
                if line and not line.startswith("•"):
                    description_parts.append(line)

        description = " ".join(description_parts).strip() or "PACK ALEO VOYAGER"
        total_net = _parse_french_amount(amount_block.group("total_net"))
        vat_total = _parse_french_amount(amount_block.group("vat_total"))
        line_items.append(
            OCRInvoiceLineItem(
                description=description,
                item_type="service",
                quantity=_parse_french_amount(amount_block.group("quantity")),
                unit=amount_block.group("unit").strip(),
                unit_price=_parse_french_amount(amount_block.group("unit_price")),
                vat_percent=_parse_french_amount(amount_block.group("vat_percent")),
                vat_total=vat_total,
                total_net=total_net,
                total_gross=round(total_net + vat_total, 2) if total_net is not None and vat_total is not None else None,
            )
        )
        return line_items

    for index, line in enumerate(lines):
        normalized = line.lower()
        if not line or "total" in normalized:
            continue

        if re.search(r"\b\d+,\d{2}\s+%?\s*\(?\d+,\d{2}\)?\s+\d+,\d{2}\b", line):
            description_parts = [
                candidate
                for candidate in lines[max(0, index - 12) : index]
                if _looks_like_invoice_line(candidate)
                and not candidate.startswith("•")
                and not re.search(r"(page \d+|description qte|facture|siret|email)", candidate, re.IGNORECASE)
            ]
            description = description_parts[-1] if description_parts else line
            amounts = re.findall(r"\d+,\d{2}", line)
            vat_percent = _parse_french_amount(amounts[-3]) if len(amounts) >= 3 else None
            total_net = _parse_french_amount(amounts[-1]) if amounts else None
            line_items.append(
                OCRInvoiceLineItem(
                    description=description,
                    quantity=_parse_french_amount(_match_text(r"\b(\d+,\d{2})\b", line)),
                    vat_percent=vat_percent,
                    total_net=total_net,
                    total_gross=total_net,
                )
            )

    if line_items:
        return line_items[:20]

    for line in lines:
        if _looks_like_invoice_line(line):
            line_items.append(
                OCRInvoiceLineItem(
                    description=line,
                    item_type=None,
                    quantity=None,
                    unit=None,
                    unit_price=None,
                    total_net=None,
                    total_gross=None,
                    vat_percent=None,
                )
            )
        if len(line_items) >= 20:
            break

    return line_items


def _fallback_extract_from_text(filename: str, raw_text: str) -> OCRInvoiceExtraction:
    line_items = _extract_line_items_from_text(raw_text)
    date_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{2,4})\b", raw_text)
    invoice_number = (
        _match_text(r"\b([A-Z]{2,5}\s+FACT-\d{8}-\d+)\b", raw_text)
        or _match_text(r"\b(FACT-\d{8}-\d+)\b", raw_text)
    )
    total_net = _parse_french_amount(_match_text(r"Total\s+net\s+HT\s+([\d\s.,]+)\s*€?", raw_text))
    total_vat = _parse_french_amount(_match_text(r"TVA\s+[\d\s.,]+%\s+([\d\s.,]+)\s*€?", raw_text))
    total_gross = _parse_french_amount(
        _match_text(r"Montant\s+total\s+TTC\s+([\d\s.,]+)\s*€?", raw_text)
        or _match_text(r"Total\s+a?\s+regler\s+([\d\s.,]+)\s*€?", raw_text)
    )
    payment_method = _match_text(r"Moyen\s+de\s+r[èe]glement\s*:\s*(.+)", raw_text)
    payment_due_date = _match_text(r"Date\s+limite\s+de\s+r[èe]glement\s*:\s*(\d{2}[/-]\d{2}[/-]\d{2,4})", raw_text)
    return OCRInvoiceExtraction(
        filename=filename,
        raw_ocr_text=raw_text,
        invoice_number=invoice_number,
        invoice_date=date_match.group(1) if date_match else None,
        issuer=OCRInvoiceIssuer(name=_infer_supplier_name(raw_text)),
        recipient=OCRInvoiceRecipient(name=_infer_recipient_name(raw_text)),
        line_items=line_items,
        total_net=total_net,
        total_vat=total_vat,
        total_gross=total_gross,
        payment={"payment_method": payment_method, "payment_due_date": payment_due_date},
        currency="EUR" if "€" in raw_text else None,
    )


def _build_ocr_lines(invoice: OCRInvoiceExtraction) -> list[OCRInvoiceLine]:
    lines: list[OCRInvoiceLine] = []
    for item in invoice.line_items:
        source_text = str(item.raw_line_text or item.description or "").strip()
        cleaned_label = str(item.label or item.description or source_text).strip()
        if not source_text and not cleaned_label:
            continue
        amount = item.total_gross
        if amount is None:
            amount = item.total_net
        if amount is None:
            amount = item.unit_price
        lines.append(
            OCRInvoiceLine(
                raw_text=source_text or cleaned_label,
                raw_line_text=source_text or cleaned_label,
                label=cleaned_label or source_text,
                description=cleaned_label or source_text,
                quantity=item.quantity,
                amount=amount,
            )
        )
    return lines


def _extract_invoice_with_openrouter(path: Path, filename: str, content_type: str) -> OCRInvoiceExtraction:
    if content_type == "application/pdf":
        embedded_text = _extract_embedded_pdf_text(path)
        if embedded_text:
            return _fallback_extract_from_text(filename, embedded_text)

    data_url = _file_to_data_url(path, content_type)

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Utilise le plugin file-parser avec mistral-ocr et retourne uniquement le texte OCR brut du PDF."
                if content_type == "application/pdf"
                else OCR_USER_PROMPT
            ),
        },
    ]
    plugins: list[dict[str, Any]] | None = None
    pdf_engine_sequence: tuple[str | None, ...] = (None,)
    if content_type == "application/pdf":
        content.append(
            {
                "type": "file",
                "file": {
                    "filename": filename,
                    "file_data": data_url,
                },
            }
        )
        pdf_engine_sequence = PDF_OCR_ENGINES
    else:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
        )

    model_sequence = [OPENROUTER_VISION_MODEL, *OPENROUTER_VISION_FALLBACK_MODELS]

    candidate_models: list[str] = []
    for model in model_sequence:
        if model and model not in candidate_models:
            candidate_models.append(model)

    last_provider_error: str | None = None

    for selected_model in candidate_models:
        for pdf_engine in pdf_engine_sequence:
            if content_type == "application/pdf" and pdf_engine:
                plugins = [
                    {
                        "id": "file-parser",
                        "pdf": {"engine": pdf_engine},
                    }
                ]
            else:
                plugins = None

            payload: dict[str, Any] = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": OCR_SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                "temperature": 0,
            }
            if content_type != "application/pdf":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "invoice_ocr_extraction",
                        "strict": True,
                        "schema": OCRInvoiceExtraction.model_json_schema(),
                    },
                }
            if plugins:
                payload["plugins"] = plugins

            try:
                response = requests.post(
                    OPENROUTER_URL,
                    headers=_openrouter_headers(),
                    json=payload,
                    timeout=180,
                )
            except requests.RequestException as exc:
                last_provider_error = f"OpenRouter est inaccessible pour le modele vision '{selected_model}'."
                if content_type == "application/pdf":
                    continue
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            response_json = response.json()

            if not response.ok:
                annotations_text = _extract_annotations_text(response_json)
                if annotations_text:
                    return _fallback_extract_from_text(filename, annotations_text)

                detail = ((response_json.get("error") or {}).get("message")) or "Erreur OpenRouter pendant l'OCR."
                if _is_openrouter_provider_error(str(detail)):
                    engine_note = f" avec moteur PDF '{pdf_engine}'" if pdf_engine else ""
                    last_provider_error = (
                        f"Aucun provider OpenRouter n'est disponible pour le modele vision "
                        f"'{selected_model}'{engine_note}."
                    )
                    continue
                raise HTTPException(status_code=502, detail=str(detail))

            annotations_text = _extract_annotations_text(response_json)
            content_text = (
                ((response_json.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            )

            if content_type == "application/pdf":
                raw_text = annotations_text or str(content_text).strip()
                if raw_text:
                    return _fallback_extract_from_text(filename, raw_text)
                engine_label = pdf_engine or "OpenRouter"
                raise HTTPException(
                    status_code=502,
                    detail=f"{engine_label} n'a retourne aucun texte exploitable pour ce PDF.",
                )

            try:
                extracted = OCRInvoiceExtraction.model_validate_json(content_text)
                if not extracted.filename:
                    extracted.filename = filename
                return extracted
            except Exception:
                parsed = _extract_json_from_text(str(content_text))
                if parsed is not None:
                    extracted = OCRInvoiceExtraction.model_validate(parsed)
                    if not extracted.filename:
                        extracted.filename = filename
                    return extracted

            if annotations_text:
                return _fallback_extract_from_text(filename, annotations_text)

            raise HTTPException(
                status_code=502,
                detail="OpenRouter a repondu, mais le JSON OCR n'a pas pu etre interprete.",
            )

    if content_type == "application/pdf":
        embedded_text = _extract_embedded_pdf_text(path)
        if embedded_text:
            return _fallback_extract_from_text(filename, embedded_text)

    detail = last_provider_error or OPENROUTER_VISION_MODEL_UNAVAILABLE_DETAIL
    raise HTTPException(
        status_code=502,
        detail=(
            f"{detail} Modeles testes: {', '.join(candidate_models)}. "
            f"{OPENROUTER_VISION_MODEL_UNAVAILABLE_DETAIL} "
            "Si le PDF est scanne, colle le texte OCR dans le bloc dedie."
        ),
    )


def _derive_invoice_tva_hint(invoice: OCRInvoiceExtraction) -> float | None:
    try:
        if invoice.total_net is not None and invoice.total_gross is not None and float(invoice.total_net) > 0:
            effective_rate = (
                (float(invoice.total_gross) - float(invoice.total_net)) / float(invoice.total_net)
            ) * 100.0
        else:
            effective_rate = None
    except Exception:
        effective_rate = None

    if effective_rate is None:
        for vat_line in invoice.vat:
            if vat_line.vat_percent is not None:
                return float(vat_line.vat_percent)
        for item in invoice.line_items:
            if item.vat_percent is not None:
                return float(item.vat_percent)
        return None

    closest = min(COMMON_TVA_RATES, key=lambda candidate: abs(candidate - effective_rate))
    if abs(closest - effective_rate) <= 0.8:
        return closest
    return None


def _select_primary_candidate(
    decision: AccountingDecision,
) -> Any | None:
    if decision.compte_comptable:
        for candidate in decision.candidats:
            if candidate.compte_comptable == decision.compte_comptable:
                return candidate
    return decision.candidats[0] if decision.candidats else None


def _build_signal_flags(
    decision: AccountingDecision,
    primary_candidate: Any | None,
) -> InvoiceAISignals:
    candidate_reason = str(getattr(primary_candidate, "raison_match", "") or "").lower()
    signal_values = {
        str(signal.key or "").strip(): float(signal.value or 0.0)
        for signal in decision.signals
    }

    return InvoiceAISignals(
        article_match=(
            "match exact article_source" in candidate_reason
            or "match normalise article_source" in candidate_reason
            or signal_values.get("text_match", 0.0) >= 0.78
        ),
        metier_match=str(getattr(primary_candidate, "metier_coherence", "") or "") == "coherente",
        tva_match=str(getattr(primary_candidate, "tva_coherence", "") or "") == "coherente",
        ape_match=signal_values.get("ape_pair_context", 0.0) >= 0.6,
        memory_match=(
            signal_values.get("supplier_memory", 0.0) >= 0.55
            or signal_values.get("human_validation", 0.0) >= 0.55
        ),
        invoice_sources_found=bool(
            getattr(primary_candidate, "source_invoice_ids", [])
            or getattr(primary_candidate, "ids_factures_sources", [])
            or []
        ),
    )


def _build_top_candidates(decision: AccountingDecision) -> list[InvoiceTopCandidate]:
    items: list[InvoiceTopCandidate] = []
    for candidate in decision.candidats[:3]:
        src_ids = list(candidate.source_invoice_ids or [])
        ids_fac = list(candidate.ids_factures_sources or src_ids)
        account_label = (
            getattr(candidate, "compte_comptable_libelle", None)
            or getattr(candidate, "account_label", None)
            or get_account_label(candidate.compte_comptable)
        )
        items.append(
            InvoiceTopCandidate(
                account=candidate.compte_comptable or None,
                account_label=account_label,
                compte_comptable_libelle=account_label,
                article_source=candidate.article_source_match,
                article_canonique=candidate.article_canonique or None,
                base=DISPLAY_LABELS.get(
                    str(getattr(candidate, "metier", "") or "").strip().lower(),
                    _display_metier(getattr(candidate, "metier", None)) or getattr(candidate, "metier", ""),
                ),
                score=_normalize_score(candidate.score_confiance),
                reason=candidate.raison_match,
                categorie=candidate.categorie or None,
                sous_categorie=candidate.sous_categorie or None,
                taux_tva=getattr(candidate, "taux_tva", None),
                type_fournisseur=getattr(candidate, "type_fournisseur", None) or None,
                source_invoice_ids=src_ids,
                ids_factures_sources=ids_fac,
                invoice_paths_sources=list(candidate.invoice_paths_sources or []),
                partitions_sources=list(candidate.partitions_sources or []),
                ape_context=list(candidate.ape_context or []),
            )
        )
    return items


def _derive_status(decision: AccountingDecision, confidence: float) -> str:
    if decision.decision == "auto_ok" and confidence >= 85:
        return "Auto OK"
    if decision.decision == "validation_humaine":
        return "Validation humaine"
    if decision.decision == "auto_ok":
        return "Validation humaine"
    return "Inconnu"


def _derive_risk_level(
    *,
    status: str,
    confidence: float,
    primary_candidate: Any | None,
    decision: AccountingDecision,
) -> str:
    top_scores = [_normalize_score(candidate.score_confiance) for candidate in decision.candidats[:2]]
    score_gap = top_scores[0] - top_scores[1] if len(top_scores) >= 2 else top_scores[0] if top_scores else 0.0
    alerts = list(getattr(primary_candidate, "alertes", []) or [])
    candidate_reason = str(getattr(primary_candidate, "raison_match", "") or "").lower()
    has_invoice_sources = bool(
        getattr(primary_candidate, "source_invoice_ids", [])
        or getattr(primary_candidate, "ids_factures_sources", [])
        or []
    )
    has_exact_match = "match exact article_source" in candidate_reason or "match normalise article_source" in candidate_reason

    if status == "Inconnu":
        return "eleve"
    if status == "Auto OK" and confidence >= 90:
        return "faible"
    if confidence >= 90 and has_exact_match and has_invoice_sources:
        return "faible"
    if confidence < 70 or not has_invoice_sources or "tva_incoherente" in alerts:
        return "eleve"
    if 70 <= confidence < 90:
        return "moyen"
    if status == "Validation humaine" or score_gap < 10:
        return "moyen"
    return "faible"


def _build_suggestions(
    *,
    status: str,
    risk_level: str,
    signals: InvoiceAISignals,
    decision: AccountingDecision,
) -> list[str]:
    suggestions: list[str] = []
    if status == "Auto OK":
        suggestions.append("Auto-validation possible")
    if status == "Validation humaine":
        suggestions.append("Envoyer en validation humaine")
    if signals.invoice_sources_found:
        suggestions.append("Ajouter à la mémoire IA")
    if risk_level == "eleve":
        suggestions.append("Article ambigu détecté")
    if not signals.article_match or decision.decision == "rejeter":
        suggestions.append("Créer règle métier")

    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _build_invoice_line_analysis(
    *,
    raw_text: str,
    decision: AccountingDecision,
) -> InvoiceLineAnalysis:
    primary_candidate = _select_primary_candidate(decision)
    confidence = _normalize_score(decision.score_confiance)
    status = _derive_status(decision, confidence)
    risk_level = _derive_risk_level(
        status=status,
        confidence=confidence,
        primary_candidate=primary_candidate,
        decision=decision,
    )
    signals = _build_signal_flags(decision, primary_candidate)
    top_candidates = _build_top_candidates(decision)
    account_label = (
        getattr(primary_candidate, "compte_comptable_libelle", None)
        or getattr(primary_candidate, "account_label", None)
        or get_account_label(decision.compte_comptable)
    )
    suggestions = _build_suggestions(
        status=status,
        risk_level=risk_level,
        signals=signals,
        decision=decision,
    )

    return InvoiceLineAnalysis(
        raw_text=raw_text,
        recommended_account=decision.compte_comptable,
        recommended_account_label=account_label,
        compte_comptable_libelle=account_label,
        metier=_display_metier(getattr(primary_candidate, "metier", None)),
        confidence=confidence,
        risk_level=risk_level,
        status=status,
        explanation=decision.explication,
        justification=decision.explication,
        decision_source=decision.source,
        category=decision.categorie,
        subcategory=decision.sous_categorie,
        taux_tva=getattr(primary_candidate, "taux_tva", None),
        type_fournisseur=getattr(primary_candidate, "type_fournisseur", None) or None,
        source_invoice_ids=list(getattr(primary_candidate, "source_invoice_ids", []) or []),
        ids_factures_sources=list(getattr(primary_candidate, "ids_factures_sources", []) or getattr(primary_candidate, "source_invoice_ids", []) or []),
        invoice_paths_sources=list(getattr(primary_candidate, "invoice_paths_sources", []) or []),
        partitions_sources=list(getattr(primary_candidate, "partitions_sources", []) or []),
        ape_context=list(getattr(primary_candidate, "ape_context", []) or []),
        signals=signals,
        top_candidates=top_candidates,
        suggestions=suggestions,
    )


def _analyze_extracted_invoice(
    extracted: OCRInvoiceExtraction,
    *,
    metier_hint: str | None = None,
    client_ape_hint: str | None = None,
    supplier_ape_hint: str | None = None,
    fournisseur_hint: str | None = None,
) -> InvoiceAnalysisResponse:
    invoice_tva_hint = _derive_invoice_tva_hint(extracted)
    ocr_lines = _build_ocr_lines(extracted)
    supplier_hint = fournisseur_hint or extracted.issuer.name or None

    analysis: list[InvoiceLineAnalysis] = []
    line_cache: dict[str, InvoiceLineAnalysis] = {}

    for line in ocr_lines:
        raw_text = str(line.raw_text or "").strip()
        if not raw_text:
            continue

        cache_key = raw_text.lower()
        cached = line_cache.get(cache_key)
        if cached is not None:
            analysis.append(cached)
            continue

        try:
            supplier_account_stats = get_supplier_memory(
                fournisseur_hint=supplier_hint,
                metier_hint=metier_hint,
            )
        except Exception:
            supplier_account_stats = {}

        try:
            validation_pattern_stats = get_validation_patterns(
                article_source=raw_text,
                fournisseur_hint=supplier_hint,
                metier_hint=metier_hint,
            )
        except Exception:
            validation_pattern_stats = {}
        candidates = local_knowledge_bases.match_line(
            article_source=raw_text,
            fournisseur_hint=supplier_hint,
            metier_hint=metier_hint,
            client_ape_hint=client_ape_hint,
            supplier_ape_hint=supplier_ape_hint,
            tva_hint=invoice_tva_hint,
            top_n=3,
            include_charges=True,
            supplier_account_stats=supplier_account_stats,
            validation_pattern_stats=validation_pattern_stats,
        )

        try:
            decision = AccountingDecision.model_validate(
                run_agent(
                    article_source=raw_text,
                    candidates=candidates,
                    fournisseur_hint=supplier_hint,
                    metier_hint=metier_hint,
                    tva_hint=invoice_tva_hint,
                    raise_on_model_unavailable=False,
                )
            )
        except OpenRouterModelUnavailableError as exc:
            raise HTTPException(
                status_code=502,
                detail=OPENROUTER_MODEL_UNAVAILABLE_DETAIL,
            ) from exc

        line_result = _build_invoice_line_analysis(raw_text=raw_text, decision=decision)
        line_cache[cache_key] = line_result
        analysis.append(line_result)

    return InvoiceAnalysisResponse(
        invoice=extracted,
        ocr_lines=ocr_lines,
        analysis=analysis,
    )


def analyze_ocr_text_payload(payload: OCRTextAnalysisInput) -> InvoiceAnalysisResponse:
    raw_text = str(payload.ocr_text or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Le champ ocr_text est vide.")

    extracted = _fallback_extract_from_text(payload.filename or "ocr-text.txt", raw_text)
    if payload.fournisseur_hint:
        extracted.issuer.name = payload.fournisseur_hint

    return _analyze_extracted_invoice(
        extracted,
        metier_hint=payload.metier_hint,
        client_ape_hint=payload.ape_client,
        supplier_ape_hint=payload.ape_fournisseur,
        fournisseur_hint=payload.fournisseur_hint,
    )


def analyze_invoice_upload(upload: UploadFile) -> InvoiceAnalysisResponse:
    filename = upload.filename or "invoice"
    suffix = _allowed_extension(filename)
    content_type = _guess_content_type(filename, upload)
    temp_path: Path | None = None

    try:
        temp_path = _save_temp_file(upload, suffix)
        extracted = _extract_invoice_with_openrouter(temp_path, filename, content_type)
        return _analyze_extracted_invoice(extracted)
    finally:
        _cleanup_temp_file(temp_path)
