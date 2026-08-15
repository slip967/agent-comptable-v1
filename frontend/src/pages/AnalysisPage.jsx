import { useEffect, useRef, useState } from "react";
import { Component } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Database,
  Download,
  FileText,
  Hash,
  LoaderCircle,
  PanelRightOpen,
  Play,
  Save,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  UserSquare2,
  X,
} from "lucide-react";
import {
  analyzeStrongInvoice,
  API_BASE_URL,
  createHumanValidationItem,
  fetchAnalysisControlQueue,
  fetchDossierQueue,
  fetchInvoicePdfPreview,
  fetchRandomInvoices,
} from "../services/api";
import { useAnalysisBatch } from "../context/AnalysisBatchContext";
import {
  formatDecisionStatus,
  formatEvidenceStatus,
  formatHumanReadableText,
  formatMetierText,
  formatQualityStatus,
  formatQueueStatus,
  formatReferentialPanelTitle,
  formatReferentialStatus,
  formatRiskStatus,
} from "../utils/uiText";
const PERFORMANCE_RESET_STORAGE_KEY = "keymanage.performance-reset.v1";
function textOrFallback(value, fallback = "Non renseigné") {
  const text = String(value || "").trim();
  return text || fallback;
}
function formatAmount(value, currency = "EUR") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Non renseigné";
  }
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
function formatCompactAmount(value, currency = "EUR") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return null;
  }
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: currency || "EUR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}
function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0%";
  }
  return `${Math.round(Number(value) * 10) / 10}%`;
}
function formatAccount(account, label) {
  const code = textOrFallback(account, "-");
  const cleanLabel = String(label || "").trim();
  return cleanLabel ? `${code} - ${cleanLabel}` : code;
}
function toDisplayMetier(value) {
  return formatMetierText(value);
}
function referentialLabel(status) {
  return formatReferentialStatus(status);
}
function evidenceStatusLabel(status) {
  return formatEvidenceStatus(status);
}
function decisionLabel(decision) {
  return formatDecisionStatus(decision);
}
function riskLabel(risk) {
  return formatRiskStatus(risk);
}
function qualityLabel(status) {
  return formatQualityStatus(status);
}
function referentialPanelTitle(status) {
  return formatReferentialPanelTitle(status);
}
function hasSecurityViolation(line) {
  return !!line && line.referential_status !== "found_exact" && line.decision === "auto_ok";
}
function isRejectedAccountingLine(line) {
  if (!line) return false;
  const confidence = Number(line?.confidence ?? line?.score ?? 0);
  const decision = String(line?.decision || "").trim().toLowerCase();
  const referentialStatus = String(line?.referential_status || "").trim().toLowerCase();
  return confidence < 50 || decision === "rejeter" || referentialStatus === "unknown";
}
function canDirectlyValidateAccountingLine(line) {
  if (!line) return false;
  const confidence = Number(line?.confidence ?? line?.score ?? 0);
  const referentialStatus = String(line?.referential_status || "").trim().toLowerCase();
  const decision = String(line?.decision || "").trim().toLowerCase();
  return !isRejectedAccountingLine(line) && (confidence >= 90 || referentialStatus === "found_exact" || decision === "auto_ok");
}
function resolveFriendlyError(error, fallback) {
  const name = String(error?.name || "").trim();
  const message = String(error?.message || error || "").trim();
  const status = error?.status;
  if (name === "AbortError" || /aborted|timed? ?out/i.test(message)) {
    return "Analyse trop longue. Cette facture est peut-\u00eatre trop volumineuse. Essayez une facture plus petite ou relancez le backend.";
  }
  if (status === 404) {
    if (/introuvable/i.test(message)) return message;
    return "Facture introuvable (404). V\u00e9rifiez que la facture existe dans CouchDB.";
  }
  if (status === 408 || status === 504) return "Analyse trop longue (timeout serveur). Essayez une facture plus petite.";
  if (status === 500) return "Erreur moteur c\u00f4t\u00e9 backend (500). Consultez les logs FastAPI.";
  if (!message) return fallback;
  if (/couchdb/i.test(message)) return "CouchDB indisponible.";
  if (/aucune ligne exploitable/i.test(message)) return "Aucune ligne exploitable trouv\u00e9e.";
  if (/erreur moteur pendant l'analyse/i.test(message)) return "Erreur moteur pendant l'analyse.";
  if (/backend fastapi inaccessible/i.test(message)) return message;
  return message;
}
function pillClass(kind, value) {
  if (kind === "referential") {
    if (value === "found_exact") {
      return "status-pill ready";
    }
    if (value === "found_fuzzy" || value === "missing_candidate") {
      return "status-pill review";
    }
    if (value === "non_comptable") {
      return "status-pill info";
    }
    return "status-pill danger";
  }
  if (kind === "decision") {
    if (value === "auto_ok") {
      return "status-pill ready";
    }
    if (value === "validation_humaine") {
      return "status-pill review";
    }
    if (value === "non_comptable") {
      return "status-pill info";
    }
    return "status-pill danger";
  }
  if (kind === "risk") {
    if (value === "faible") {
      return "status-pill ready";
    }
    if (value === "moyen") {
      return "status-pill review";
    }
    return "status-pill danger";
  }
  if (kind === "quality") {
    return value === "fiable" ? "status-pill ready" : "status-pill review";
  }
  if (kind === "proof") {
    return value ? "status-pill ready" : "status-pill review";
  }
  if (kind === "evidence") {
    if (value === "complete") {
      return "status-pill ready";
    }
    if (value === "partial") {
      return "status-pill review";
    }
    return "status-pill danger";
  }
  return "status-pill info";
}
function getEvidence(line = {}) {
  return {
    sourceInvoiceIds: Array.isArray(line.source_invoice_ids)
      ? line.source_invoice_ids.filter(Boolean)
      : [],
    invoicePathsSources: Array.isArray(line.invoice_paths_sources)
      ? line.invoice_paths_sources.filter(Boolean)
      : [],
    partitionsSources: Array.isArray(line.partitions_sources)
      ? line.partitions_sources.filter(Boolean)
      : [],
    apeContext: Array.isArray(line.ape_context)
      ? line.ape_context.filter(Boolean)
      : [],
  };
}
function getProofCounts(line = {}) {
  const evidence = getEvidence(line);
  return {
    invoiceCount: evidence.sourceInvoiceIds.length,
    pdfCount: evidence.invoicePathsSources.length,
    partitionCount: evidence.partitionsSources.length,
  };
}
function evidenceCompact(line) {
  const { invoiceCount, pdfCount } = getProofCounts(line);
  if (!invoiceCount && !pdfCount) {
    return {
      hasProof: false,
      label: "Aucune preuve",
    };
  }
  return {
    hasProof: true,
    label: `${invoiceCount} facture${invoiceCount > 1 ? "s" : ""} · ${pdfCount} PDF`,
  };
}
function fileNameFromPath(path) {
  const text = String(path || "").trim();
  if (!text) {
    return "Document PDF";
  }
  const chunks = text.split(/[\\/]/);
  return chunks[chunks.length - 1] || text;
}
function copyToClipboard(text, onDone) {
  const value = String(text || "").trim();
  if (!value) {
    return;
  }
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(value).then(() => onDone?.());
    return;
  }
  onDone?.();
}
function buildProofPayload(line) {
  const evidence = getEvidence(line);
  return [
    `Article: ${textOrFallback(line.raw_text)}`,
    `Compte: ${formatAccount(line.recommended_account, line.recommended_account_label)}`,
    `APE: ${evidence.apeContext.join(", ") || "Non renseigné"}`,
    `Partitions: ${evidence.partitionsSources.join(", ") || "Non renseigné"}`,
    `Factures sources: ${evidence.sourceInvoiceIds.join(", ") || "Non renseigné"}`,
    `Documents PDF: ${evidence.invoicePathsSources.join(", ") || "Non renseigné"}`,
  ].join("\n");
}

function pluralize(count, singular, plural) {
  return `${count} ${count > 1 ? plural : singular}`;
}
function queueStatusLabel(status) {
  return formatQueueStatus(status);
}
function queueStatusTone(status) {
  if (status === "accounted" || status === "comptabilisee" || status === "COMPTABILISÉE") {
    return "ready";
  }
  if (status === "to_control") {
    return "review";
  }
  if (status === "new_articles") {
    return "info";
  }
  if (status === "low_risk") {
    return "ready";
  }
  if (status === "no_lines") {
    return "danger";
  }
  if (status === "analysis_failed") {
    return "danger";
  }
  return "slate";
}
function queueBadgeTone(badge) {
  const text = String(badge || "").toLowerCase();
  if (text.includes("valider") || text.includes("control")) {
    return "review";
  }
  if (text.includes("nouvel") || text.includes("nouveaux")) {
    return "slate";
  }
  if (text.includes("faible") || text.includes("analyse")) {
    return "ready";
  }
  if (text.includes("sans ligne") || text.includes("rejet")) {
    return "danger";
  }
  return "info";
}
function pdfStatusLabel(status) {
  return (
    {
      available: "PDF disponible",
      missing_file: "PDF absent",
      no_path: "Sans PDF",
      inaccessible: "Accès réseau KO",
      unknown: "PDF inconnu",
    }[status] || "PDF inconnu"
  );
}
function pdfStatusTone(status) {
  if (status === "available") {
    return "ready";
  }
  if (status === "missing_file") {
    return "review";
  }
  if (status === "no_path") {
    return "neutral";
  }
  if (status === "inaccessible") {
    return "danger";
  }
  return "info";
}
function canOpenPdf(invoice) {
  return invoice?.pdf_status === "available";
}
function isPdfOpenableFromDebug(debug) {
  if (!debug || typeof debug !== "object") {
    return false;
  }
  if (debug.exists_on_disk) {
    return true;
  }
  if (String(debug.resolved_kind || "").trim().toLowerCase() === "couch_attachment") {
    return true;
  }
  const relatedDocSuccess =
    debug.related_doc_success && typeof debug.related_doc_success === "object"
      ? debug.related_doc_success
      : null;
  if (
    relatedDocSuccess &&
    (relatedDocSuccess.used_attachment ||
      relatedDocSuccess.exists_on_disk ||
      relatedDocSuccess.resolved_kind)
  ) {
    return true;
  }
  return false;
}
function normalizePdfStatus(value) {
  const status = String(value || "").trim().toLowerCase();
  if (["available", "missing_file", "no_path", "inaccessible", "unknown"].includes(status)) {
    return status;
  }
  return "unknown";
}
async function reconcileBatchPdfStatuses(items = []) {
  const resolvedItems = await Promise.all(
    items.map(async (item) => {
      if (canOpenPdf(item)) {
        return item;
      }
      const invoiceId = getInvoiceId(item);
      if (!invoiceId) {
        return item;
      }
      try {
        const debug = await fetchInvoicePdfDebug(invoiceId);
        if (isPdfOpenableFromDebug(debug)) {
          return {
            ...item,
            pdf_status: "available",
            pdf_message: "PDF disponible",
          };
        }
        if (String(debug?.error_reason || debug?.error || "").trim()) {
          return {
            ...item,
            pdf_status: "missing_file",
            pdf_message: String(debug?.error_reason || debug?.error).trim(),
          };
        }
      } catch {
        // Keep the batch status as-is if the diagnostic cannot be fetched.
      }
      return item;
    }),
  );
  return resolvedItems;
}
function buildQueueCounts(items = []) {
  const counts = {
    all: items.length,
    to_control: 0,
    new_articles: 0,
    low_risk: 0,
    not_analyzed: 0,
    high_risk: 0,
  };
  items.forEach((item) => {
    if (item.queue_status === "to_control" || item.queue_status === "new_articles") {
      counts.to_control += 1;
    }
    if (item.queue_status === "new_articles") {
      counts.new_articles += 1;
    }
    if (item.queue_status === "low_risk") {
      counts.low_risk += 1;
    }
    if (item.queue_status === "not_analyzed") {
      counts.not_analyzed += 1;
    }
    if (item.queue_status === "no_lines") {
      counts.high_risk += 1;
    }
    if (item.queue_status === "analysis_failed") {
      counts.high_risk += 1;
    }
  });
  return counts;
}
function mapSampleInvoiceToQueueItem(invoice) {
  const noLines =
    invoice?.status === "sans_lignes_exploitables" ||
    Number(invoice?.exploitable_lines_count || 0) === 0;
  return {
    id: invoice?.invoice_id,
    supplier: invoice?.supplier || null,
    client: invoice?.client || null,
    date: invoice?.invoice_date || null,
    due_date: invoice?.due_date || null,
    total_ttc: invoice?.total_ttc ?? null,
    invoice_number: invoice?.invoice_number || null,
    line_count: Number(invoice?.line_items_count || 0),
    exploitable_lines_count: Number(invoice?.exploitable_lines_count || 0),
    client_ape: invoice?.client_ape || null,
    supplier_ape: invoice?.supplier_ape || null,
    queue_status: noLines ? "no_lines" : "not_analyzed",
    badges: [noLines ? "Sans lignes exploitables" : "À analyser"],
    ready: !noLines,
    preview: null,
  };
}
function formatDurationLabel(ms) {
  const value = Number(ms || 0);
  if (!value || Number.isNaN(value)) {
    return null;
  }
  if (value < 1000) {
    return `${value} ms`;
  }
  return `${Math.round(value / 10) / 100} s`;
}
function mapBatchResultToQueueItem(result) {
  const pdfStatus = normalizePdfStatus(result?.pdf_status);
  const analysisPayload =
    result?.analysis_payload && typeof result.analysis_payload === "object"
      ? result.analysis_payload
      : null;
  const summary = result?.status === "failed" ? null : {
    total_lines: Number(result?.total_lines || 0),
    auto_ok: Number(result?.auto_ok || 0),
    validation_humaine: Number(result?.validation_humaine || 0),
    rejeter: Number(result?.rejeter || 0),
    non_comptable: Number(result?.non_comptable || 0),
    average_confidence: Number(result?.average_confidence || 0),
  };
  const totalLines = Number(result?.total_lines || 0);
  const failed = String(result?.status || "").toLowerCase() === "failed";
  const analysisDuration = formatDurationLabel(result?.duration_ms);
  const invoiceNumber = String(result?.invoice_number || "").trim();
  const supplier = String(result?.supplier || "").trim();
  const client = String(result?.client || "").trim();
  const workflowStatus = String(result?.workflow_status || "").trim().toUpperCase();
  const globalDecision = String(result?.global_decision || "").trim();
  const isAutoValidated = ["VALIDE_AUTO", "COMPTABILISEE", "COMPTABILISÉE"].includes(workflowStatus);
  const isToControl = workflowStatus === "A_CONTROLER";
  const badges = [];
  if (failed) {
    badges.push("Analyse échouée");
    if (String(result?.error_message || "").trim()) {
      badges.push(formatHumanReadableText(String(result.error_message).trim(), ""));
    }
  } else {
    badges.push(`${totalLines} ${totalLines > 1 ? "lignes" : "ligne"}`);
    if (isAutoValidated) {
      badges.push("Validée auto");
    } else if (isToControl) {
      badges.push(globalDecision || "À contrôler");
    } else {
      badges.push("Analysée");
    }
  }
  if (analysisDuration) {
    badges.push(analysisDuration);
  }
  const queueStatus = failed
    ? "analysis_failed"
    : totalLines <= 0
      ? "no_lines"
      : isAutoValidated
        ? "low_risk"
        : isToControl
          ? "to_control"
          : "not_analyzed";
  return {
    id: result?.invoice_id,
    supplier: supplier || null,
    client: client || null,
    date: result?.invoice_date || null,
    due_date: result?.due_date || analysisPayload?.invoice?.due_date || null,
    total_ttc: result?.total_ttc ?? analysisPayload?.invoice?.total_ttc ?? analysisPayload?.invoice?.amount_ttc ?? null,
    invoice_number: invoiceNumber || null,
    line_count: totalLines || Number(result?.line_items_count || 0),
    exploitable_lines_count: totalLines || Number(result?.exploitable_lines_count || 0),
    client_ape: result?.client_ape || null,
    supplier_ape: result?.supplier_ape || null,
    queue_status: queueStatus,
    badges: badges.filter(Boolean),
    ready: !failed && totalLines > 0,
    preview: failed
      ? formatHumanReadableText(String(result?.error_message || "Erreur pendant l'analyse.").trim(), "")
      : `Lot ${String(result?.job_id || "").slice(-6)} · ${Number(result?.auto_ok || 0)} auto-validée${Number(result?.auto_ok || 0) > 1 ? "s" : ""} · ${Number(result?.validation_humaine || 0)} à valider`,
    batch_status: result?.status || "completed",
    batch_job_id: result?.job_id || null,
    batch_duration_ms: Number(result?.duration_ms || 0),
    batch_summary: summary,
    workflow_status: workflowStatus || null,
    global_decision: globalDecision || null,
    global_risk_level: String(result?.global_risk_level || "").trim() || null,
    can_validate_accounting: result?.can_validate_accounting !== false,
    routing_reasons: Array.isArray(result?.routing_reasons) ? result.routing_reasons : [],
    pdf_status: pdfStatus,
    pdf_message: String(result?.pdf_message || "").trim() || null,
    analysis_result: analysisPayload,
  };
}
function filterQueueItemsByStatus(items = [], filter = "all") {
  const list = Array.isArray(items) ? items : [];
  if (!filter || filter === "all") {
    return list;
  }
  return list.filter((item) => {
    const status = String(item?.queue_status || item?.analysis_status || "not_analyzed").trim();
    if (filter === "to_control") {
      return status === "to_control";
    }
    if (filter === "new_articles") {
      return status === "new_articles";
    }
    if (filter === "low_risk") {
      return status === "low_risk";
    }
    if (filter === "not_analyzed") {
      return status === "not_analyzed";
    }
    return true;
  });
}
function sortQueueItems(items = [], strategy = "DUE_DATE") {
  const list = [...(Array.isArray(items) ? items : [])];
  const timestamp = (value) => {
    const parsed = value ? new Date(value) : null;
    return parsed && !Number.isNaN(parsed.getTime()) ? parsed.getTime() : Number.POSITIVE_INFINITY;
  };
  const amount = (item) => {
    const value = item?.total_ttc
      ?? item?.amount_ttc
      ?? item?.total_gross
      ?? item?.analysis_result?.invoice?.total_ttc
      ?? item?.analysis_result?.invoice?.amount_ttc;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const invoiceDate = (item) => item?.invoice_date || item?.date || item?.created_at;
  const dueDate = (item) => item?.due_date || item?.payment_due_date || item?.date_echeance || invoiceDate(item);
  const stableId = (item) => String(getInvoiceId(item) || "");
  const selected = String(strategy || "DUE_DATE").toUpperCase();

  return list.sort((left, right) => {
    if (selected === "CHRONO") {
      return timestamp(invoiceDate(left)) - timestamp(invoiceDate(right)) || stableId(left).localeCompare(stableId(right));
    }
    if (selected === "SUPPLIER") {
      return String(left?.supplier || left?.supplier_name || "").localeCompare(
        String(right?.supplier || right?.supplier_name || ""),
        "fr",
        { sensitivity: "base" },
      ) || timestamp(invoiceDate(left)) - timestamp(invoiceDate(right)) || stableId(left).localeCompare(stableId(right));
    }
    if (selected === "AMOUNT") {
      return amount(right) - amount(left) || timestamp(invoiceDate(left)) - timestamp(invoiceDate(right)) || stableId(left).localeCompare(stableId(right));
    }
    return timestamp(dueDate(left)) - timestamp(dueDate(right))
      || timestamp(invoiceDate(left)) - timestamp(invoiceDate(right))
      || stableId(left).localeCompare(stableId(right));
  });
}
function mergeQueueItemsByInvoiceId(existing = [], incoming = []) {
  const byId = new Map();
  existing.forEach((item) => {
    const id = getInvoiceId(item);
    if (id) {
      byId.set(id, item);
    }
  });
  incoming.forEach((item) => {
    const id = getInvoiceId(item);
    if (!id) {
      return;
    }
    const previous = byId.get(id) || {};
    byId.set(id, {
      ...previous,
      ...item,
      badges: Array.isArray(item.badges) && item.badges.length
        ? item.badges
        : Array.isArray(previous.badges)
          ? previous.badges
          : [],
    });
  });
  return Array.from(byId.values());
}
function dedupeQueueItemsByInvoiceId(items = []) {
  return mergeQueueItemsByInvoiceId([], items);
}
function mergeBatchResults(existingInvoices = [], newResults = []) {
  const mappedResults = Array.isArray(newResults) ? newResults.map(mapBatchResultToQueueItem) : [];
  persistAutoValidatedBatchEntries(mappedResults);
  return mergeQueueItemsByInvoiceId(existingInvoices, mappedResults);
}
function proposalStatusLabel(status) {
  return (
    {
      auto_ok: "Auto-validée",
      validation_required: "À valider",
      rejected: "Rejeté",
      partial: "Partiel",
    }[status] || "Inconnu"
  );
}
function proposalStatusTone(status) {
  if (status === "auto_ok") return "ready";
  if (status === "validation_required") return "review";
  if (status === "rejected") return "danger";
  return "info";
}
function toFiniteNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const normalized = typeof value === "string"
    ? value.replace(/\s/g, "").replace(",", ".")
    : value;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}
function normalizeAccountingJournalLine(line = {}) {
  const debit = toFiniteNumber(line.debit ?? line.debit_amount ?? line.amount_debit) ?? 0;
  const credit = toFiniteNumber(line.credit ?? line.credit_amount ?? line.amount_credit) ?? 0;
  return {
    side: line.side || line.sens || (credit > 0 ? "Crédit" : "Débit"),
    account:
      line.account ||
      line.compte ||
      line.accounting_account ||
      line.compte_comptable ||
      "",
    label:
      line.label ||
      line.account_label ||
      line.accounting_account_label ||
      line.libelle ||
      line.libelle_compte ||
      "",
    description: line.description || line.raw_text || line.article_source || "",
    debit,
    credit,
  };
}
function buildJournalLinesFromAccountingProposal(proposal, line = {}, invoiceRecord = {}) {
  const existingLists = [
    proposal?.journal_lines,
    proposal?.accounting_lines,
    proposal?.entries,
    proposal?.ecriture?.lines,
    proposal?.lines_debit_credit,
    line?.journal_lines,
    line?.accounting_lines,
  ];
  const existing = existingLists.find(
    (candidate) => Array.isArray(candidate) && candidate.length,
  );
  if (existing) {
    return existing.map(normalizeAccountingJournalLine);
  }
  const amountHt = toFiniteNumber(line.amount_ht ?? line.total_net ?? line.net_amount) ?? 0;
  const amountTtc = toFiniteNumber(line.amount_ttc ?? line.total_gross ?? line.gross_amount) ?? 0;
  const vatRate = toFiniteNumber(line.tva ?? line.vat_percent ?? line.taux_tva) ?? 0;
  const vatAmount = amountHt && vatRate
    ? Number((amountHt * vatRate / 100).toFixed(2))
    : 0;
  const total = amountTtc || (amountHt + vatAmount) || amountHt || 0;
  const debitBase = amountHt || total;
  const journalLines = [
    {
      side: "Débit",
      account: line.recommended_account || line.account || "",
      label: line.recommended_account_label || line.account_label || "Compte proposé",
      description: line.raw_text || line.cleaned_text || "Ligne facture",
      debit: debitBase,
      credit: 0,
    },
  ];
  if (vatAmount > 0) {
    journalLines.push({
      side: "Débit",
      account: "44566",
      label: "TVA déductible",
      description: "TVA sur facture fournisseur",
      debit: vatAmount,
      credit: 0,
    });
  }
  journalLines.push({
    side: "Crédit",
    account: "401",
    label: "Fournisseurs",
    description: line.supplier || invoiceRecord.supplier || "Fournisseur",
    debit: 0,
    credit: total,
  });
  return journalLines;
}

function buildValidatedEntryFromBatchResult(queueItem = {}) {
  const result = queueItem?.analysis_result || {};
  const invoice = result?.invoice || {};
  const proposal = result?.accounting_proposal || {};
  const lines = Array.isArray(result?.lines) ? result.lines : [];
  const primaryLine = lines.find((line) => String(line?.decision || "").toLowerCase() !== "non_comptable") || lines[0] || {};
  const invoiceId = getInvoiceId(queueItem) || invoice?.invoice_id || result?.invoice_id;
  if (!invoiceId || String(queueItem?.workflow_status || "").toUpperCase() !== "VALIDE_AUTO") {
    return null;
  }
  const evidence = getEvidence(primaryLine);
  const journalLines = buildJournalLinesFromAccountingProposal(
    proposal,
    primaryLine,
    queueItem,
  );
  return {
    status: "VALIDE_AUTO",
    accounting_status: "VALIDE_AUTO",
    validated_at: queueItem?.date || result?.analyzed_at || new Date().toISOString(),
    invoice_id: invoiceId,
    invoice_number: invoice?.invoice_number || queueItem?.invoice_number || "",
    supplier: primaryLine?.supplier || invoice?.supplier || queueItem?.supplier || "",
    client: primaryLine?.client || invoice?.client || queueItem?.client || "",
    line_id: primaryLine?.line_id || `${invoiceId}:auto`,
    raw_text: primaryLine?.raw_text || queueItem?.preview || "Facture validée automatiquement",
    cleaned_text: primaryLine?.cleaned_text || "",
    amount_ht: primaryLine?.amount_ht ?? null,
    amount_ttc: primaryLine?.amount_ttc ?? null,
    tva: primaryLine?.tva ?? null,
    recommended_account: primaryLine?.recommended_account || proposal?.main_account || "",
    recommended_account_label: primaryLine?.recommended_account_label || proposal?.main_account_label || "",
    confidence: Number(primaryLine?.confidence || result?.summary?.average_confidence || queueItem?.batch_summary?.average_confidence || 0),
    decision: primaryLine?.decision || "auto_ok",
    risk_level: primaryLine?.risk_level || "faible",
    referential_status: primaryLine?.referential_status || "found_exact",
    evidence_status: primaryLine?.evidence_status || "complete",
    source_invoice_ids: evidence.sourceInvoiceIds,
    invoice_paths_sources: evidence.invoicePathsSources,
    partitions_sources: evidence.partitionsSources,
    ape_context: evidence.apeContext,
    journal_lines: journalLines,
    debit_credit_lines: journalLines,
    accounting_proposal: proposal || null,
    line_analysis: primaryLine,
    auto_validated: true,
  };
}
function persistAutoValidatedBatchEntries(items = []) {
  if (!Array.isArray(items) || typeof window === "undefined") {
    return;
  }
  items.forEach((item) => {
    const entry = buildValidatedEntryFromBatchResult(item);
    if (entry?.invoice_id) {
      saveAccountingEntryLocally(entry.invoice_id, entry);
    }
  });
}
function saveAccountingEntryLocally(invoiceId, entry) {
  if (!invoiceId || !entry || typeof window === "undefined") {
    return;
  }
  const storageKey = "keymanage.validated-accounting-entries.v1";
  try {
    const current = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
    window.localStorage.setItem(
      storageKey,
      JSON.stringify({
        ...current,
        [invoiceId]: entry,
      }),
    );
  } catch {
    // Best-effort local persistence; React state is still updated immediately.
  }
  window.dispatchEvent(
    new CustomEvent("keymanage:validated-accounting-entry", {
      detail: { invoiceId, entry },
    }),
  );
}
function getInvoiceId(invoice) {
  return (
    invoice?.invoice_id ||
    invoice?.id ||
    invoice?._id ||
    invoice?.doc_id ||
    null
  );
}
function downloadJson(data, filename) {
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
function getLineGroupKey(line = {}) {
  return [
    String(line?.raw_text || "").trim(),
    String(line?.cleaned_text || "").trim(),
    String(line?.quantity ?? ""),
    String(line?.unit_price ?? ""),
    String(line?.amount_ht ?? ""),
    String(line?.amount_ttc ?? ""),
    String(line?.tva ?? ""),
    String(line?.recommended_account || "").trim(),
    String(line?.decision || "").trim(),
    String(line?.evidence_status || "").trim(),
  ].join("||");
}
function buildDisplayLines(lines = []) {
  const grouped = [];
  const byKey = new Map();
  lines.forEach((line, index) => {
    const key = getLineGroupKey(line);
    const existing = byKey.get(key);
    if (existing) {
      existing.occurrenceCount += 1;
      existing.sourceIndexes.push(index);
      return;
    }
    const row = {
      key,
      line,
      index,
      occurrenceCount: 1,
      sourceIndexes: [index],
    };
    byKey.set(key, row);
    grouped.push(row);
  });
  return grouped;
}
function buildLineMeta(line, currency = "EUR", occurrenceCount = 1) {
  const parts = [];
  const quantity = line?.quantity;
  const amountHt = formatCompactAmount(line?.amount_ht, currency);
  const amountTtc = formatCompactAmount(line?.amount_ttc, currency);
  if (quantity !== null && quantity !== undefined && !Number.isNaN(Number(quantity))) {
    parts.push(`Qte ${Number(quantity)}`);
  }
  if (amountHt) {
    parts.push(`HT ${amountHt}`);
  }
  if (amountTtc) {
    parts.push(`TTC ${amountTtc}`);
  }
  if (occurrenceCount > 1) {
    parts.push(`${occurrenceCount} occurrences`);
  }
  return parts.join(" · ");
}
function emptyQueueMessage({ hasLoadedQueue, queueReturnedEmpty, totalItems, filter }) {
  if (!hasLoadedQueue) {
    return "Sélectionnez un dossier client ci-dessus pour charger ses factures.";
  }
  if (queueReturnedEmpty || totalItems === 0) {
    return "Aucune facture disponible depuis CouchDB.";
  }
  if (filter !== "all") {
    return "Aucune facture dans cette categorie.";
  }
  return "Aucune facture disponible.";
}
function SummaryCard({ label, value, detail, tone = "info" }) {
  return (
    <div className={`analysis-summary-card ${tone}`}>
      <div className="analysis-summary-label">{label}</div>
      <div className="analysis-summary-value">{value}</div>
      <div className="analysis-summary-detail">{detail}</div>
    </div>
  );
}
function InfoTip({ text, placement = "right" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    function handleOutside(event) {
      if (ref.current && !ref.current.contains(event.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);
  return (
    <span
      ref={ref}
      className={`audit-tip-wrap${open ? " open" : ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={() => setOpen((v) => !v)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && setOpen((v) => !v)}
      aria-label="Aide"
    >
      <span className="audit-tip-icon" aria-hidden="true">?</span>
      {open ? (
        <span className={`audit-tip-bubble audit-tip-${placement}`} role="tooltip">
          {text}
        </span>
      ) : null}
    </span>
  );
}
function DetailRow({ label, value, highlight = false, tip, tipPlacement = "right" }) {
  return (
    <div className="analysis-detail-row">
      <span className="analysis-detail-key">
        {label}
        {tip ? <InfoTip text={tip} placement={tipPlacement} /> : null}
      </span>
      <span className={`analysis-detail-val${highlight ? " highlight" : ""}`}>
        {textOrFallback(value)}
      </span>
    </div>
  );
}
class DrawerErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      message: "",
    };
  }
  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message:
        String(error?.message || "").trim() ||
        "Impossible d'afficher le détail de cette ligne.",
    };
  }
  componentDidCatch(error, info) {
    console.error("[AnalysisPage] inspect drawer render error", error, info);
  }
  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({
        hasError: false,
        message: "",
      });
    }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="analysis-inline-error">
          {this.state.message || "Impossible d'afficher le détail de cette ligne."}
        </div>
      );
    }
    return this.props.children;
  }
}
export default function AnalysisPage() {
  const [searchQueueItems, setSearchQueueItems] = useState([]);
  const [searchQueueCounts, setSearchQueueCounts] = useState({
    all: 0,
    to_control: 0,
    new_articles: 0,
    low_risk: 0,
    not_analyzed: 0,
    high_risk: 0,
  });
  const [invoiceFilter, setInvoiceFilter] = useState("all");
  const [queueErrorMessage, setQueueErrorMessage] = useState("");
  const [hasLoadedSearchQueue, setHasLoadedSearchQueue] = useState(false);
  const [searchQueueReturnedEmpty, setSearchQueueReturnedEmpty] = useState(false);
  const [searchQueueErrorMessage, setSearchQueueErrorMessage] = useState("");
  const [selectedInvoiceId, setSelectedInvoiceId] = useState("");
  const [analysisResult, setAnalysisResult] = useState(null);
  const [selectedLineIndex, setSelectedLineIndex] = useState(0);
  const [loadingInvoices, setLoadingInvoices] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [showDocuments, setShowDocuments] = useState(false);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [activeDossier, setActiveDossier] = useState(null);
  const [showJsonRaw, setShowJsonRaw] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [pdfViewerPages, setPdfViewerPages] = useState([]);
  const [pdfViewerLabel, setPdfViewerLabel] = useState("");
  const [analysisSlowWarning, setAnalysisSlowWarning] = useState(false);
  const [cardAnalyzingId, setCardAnalyzingId] = useState("");
  const slowWarningTimerRef = useRef(null);
  const [queueFilters, setQueueFilters] = useState({
    supplier: "",
    client: "",
    ape: "",
  });
  const [batchLimitInput, setBatchLimitInput] = useState("50");
  const [sortStrategy, setSortStrategy] = useState("DUE_DATE");
  const [resetSessionConfirmOpen, setResetSessionConfirmOpen] = useState(false);
  const [resettingTestSession, setResettingTestSession] = useState(false);
  const {
    queueItems,
    queueCounts,
    invoiceAnalysisCache,
    hasLoadedQueue,
    queueReturnedEmpty,
    loadingBatch,
    batchJob,
    batchRequestedLimit,
    batchJobError,
    persistedBatchCount,
    showingRecordedInvoices,
    batchControlState,
    batchActionMessage,
    batchSuccessMessage,
    handleLoadBatchAnalysis,
    handleStopBatchAnalysis,
    handleResumeBatchAnalysis,
    handleSaveBatchAnalysis,
    handleShowAllRecordedInvoices,
    handleClearBatchResults,
    handleResetTestSession,
    patchQueueItem,
    cacheAnalysisResult,
  } = useAnalysisBatch();
  const combinedInvoiceItems = dedupeQueueItemsByInvoiceId([
    ...searchQueueItems,
    ...queueItems,
  ]);
  const selectedInvoiceRecord =
    combinedInvoiceItems.find((item) => getInvoiceId(item) === selectedInvoiceId) || null;
  const queueEmptyLabel = emptyQueueMessage({
    hasLoadedQueue,
    queueReturnedEmpty,
    totalItems: queueItems.length,
    filter: invoiceFilter,
  });
  const searchQueueEmptyLabel = emptyQueueMessage({
    hasLoadedQueue: hasLoadedSearchQueue,
    queueReturnedEmpty: searchQueueReturnedEmpty,
    totalItems: searchQueueItems.length,
    filter: invoiceFilter,
  });
  const invoiceHeader = analysisResult?.invoice || selectedInvoiceRecord || {};
  const proposalSummary = analysisResult?.accounting_proposal?.summary || {};
  const proposalLines = Array.isArray(analysisResult?.accounting_proposal?.lines) ? analysisResult.accounting_proposal.lines : [];
  const lines = analysisResult?.lines || [];
  const displayLines = buildDisplayLines(lines);
  const selectedLine = lines[selectedLineIndex] || null;
  const selectedEvidence = getEvidence(selectedLine || {});
  const selectedTopCandidates = Array.isArray(selectedLine?.top_candidates)
    ? selectedLine.top_candidates.filter(
        (candidate) => candidate && typeof candidate === "object",
      )
    : [];
  const selectedPrimaryCandidate = selectedTopCandidates[0] || null;
  const selectedProofCounts = getProofCounts(selectedLine || {});
  const selectedHasSecurityViolation = hasSecurityViolation(selectedLine);
  const selectedDisplayGroup =
    displayLines.find((row) => row.sourceIndexes.includes(selectedLineIndex)) || null;
  const handleSelectInvoice = (invoice) => {
    const id = getInvoiceId(invoice);
    if (!id) {
      console.warn("[AnalysisPage] handleSelectInvoice: no id found", invoice);
      return;
    }
    const cachedAnalysis = invoiceAnalysisCache?.[id] || invoice?.analysis_result || null;
    setSelectedInvoiceId(id);
    setAnalysisResult(cachedAnalysis);
    setSelectedLineIndex(0);
    setDetailDrawerOpen(false);
    setErrorMessage("");
    setSuccessMessage("");
    setActionMessage("");
  };
  useEffect(() => {
    const selectSearchInvoice = (invoiceId, providedInvoice = null) => {
      const expectedId = String(invoiceId || "").trim();
      if (!expectedId) return;
      const existingInvoice = combinedInvoiceItems.find(
        (item) => String(getInvoiceId(item) || "").trim() === expectedId,
      );
      const invoice = existingInvoice || providedInvoice;
      if (!invoice) return;
      if (existingInvoice) {
        setSearchQueueItems([]);
        setHasLoadedSearchQueue(false);
      } else {
        setSearchQueueItems([{ ...invoice, invoice_id: expectedId }]);
        setHasLoadedSearchQueue(true);
      }
      setSearchQueueReturnedEmpty(false);
      setInvoiceFilter("all");
      handleSelectInvoice(invoice);
      window.sessionStorage.removeItem("keymanage.analysis.search-selection.v1");
      window.setTimeout(() => {
        document.querySelector(".analysis-invoice-card.active")?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 80);
    };
    const handleGlobalSearchSelection = (event) => {
      selectSearchInvoice(event?.detail?.invoiceId, event?.detail?.invoice);
    };
    window.addEventListener("keymanage:analysis-search-select", handleGlobalSearchSelection);
    const storedSelection = window.sessionStorage.getItem("keymanage.analysis.search-selection.v1");
    if (storedSelection) {
      try {
        const parsedSelection = JSON.parse(storedSelection);
        selectSearchInvoice(parsedSelection?.invoiceId, parsedSelection?.invoice);
      } catch {
        selectSearchInvoice(storedSelection);
      }
    }
    return () => {
      window.removeEventListener("keymanage:analysis-search-select", handleGlobalSearchSelection);
    };
  }, [queueItems, searchQueueItems, invoiceAnalysisCache]);
  useEffect(() => {
    if (selectedInvoiceId && !combinedInvoiceItems.some((item) => getInvoiceId(item) === selectedInvoiceId)) {
      setSelectedInvoiceId("");
      setSearchQueueItems([]);
      setHasLoadedSearchQueue(false);
      setSearchQueueReturnedEmpty(true);
      setAnalysisResult(null);
      setSelectedLineIndex(0);
      setDetailDrawerOpen(false);
    }
  }, [combinedInvoiceItems, selectedInvoiceId]);
  const loadControlQueue = async ({
    status = invoiceFilter,
    supplier = queueFilters.supplier,
    client = queueFilters.client,
    ape = queueFilters.ape,
  } = {}) => {
    setLoadingInvoices(true);
    setSearchQueueErrorMessage("");
    setErrorMessage("");
    setSuccessMessage("");
    setActionMessage("");
    setHasLoadedSearchQueue(true);
    setSearchQueueReturnedEmpty(false);
    try {
      const payload = await fetchAnalysisControlQueue({
        status,
        limit: 12,
        supplier,
        client,
        ape,
      });
      const items = Array.isArray(payload?.items) ? payload.items : [];
      setSearchQueueItems(items);
      setSearchQueueCounts(
        payload?.counts && typeof payload.counts === "object"
          ? payload.counts
          : buildQueueCounts(items),
      );
      setSearchQueueReturnedEmpty(items.length === 0);
      if (!items.some((item) => getInvoiceId(item) === selectedInvoiceId) && !queueItems.some((item) => getInvoiceId(item) === selectedInvoiceId)) {
        setSelectedInvoiceId("");
      }
    } catch (error) {
      setSearchQueueItems([]);
      setSearchQueueCounts({
        all: 0,
        to_control: 0,
        new_articles: 0,
        low_risk: 0,
        not_analyzed: 0,
        high_risk: 0,
      });
      setSearchQueueReturnedEmpty(true);
      setSearchQueueErrorMessage(
        String(error?.message || "").trim() ||
          "Impossible de charger les factures depuis CouchDB. Verifiez le backend FastAPI.",
      );
    } finally {
      setLoadingInvoices(false);
    }
  };
  const openLineDrawer = (index) => {
    if (!lines[index]) {
      setErrorMessage("Impossible d'ouvrir le détail de cette ligne.");
      return;
    }
    setSelectedLineIndex(index);
    setShowDocuments(false);
    setDetailDrawerOpen(true);
  };
  const openProposalLineDrawer = (proposalLine, fallbackIndex = 0) => {
    const lineId = String(proposalLine?.line_id || "").trim();
    let lineIndex = -1;
    if (/^line_\d+$/i.test(lineId)) {
      lineIndex = Number(lineId.replace(/^line_/i, "")) - 1;
    }
    if (lineIndex < 0 || !lines[lineIndex]) {
      lineIndex = lines.findIndex((line) => {
        if (!line || typeof line !== "object") {
          return false;
        }
        return (
          String(line.raw_text || "").trim() === String(proposalLine?.raw_text || "").trim() &&
          String(line.cleaned_text || "").trim() === String(proposalLine?.cleaned_text || "").trim() &&
          String(line.recommended_account || "").trim() ===
            String(proposalLine?.recommended_account || "").trim()
        );
      });
    }
    if (lineIndex < 0 || !lines[lineIndex]) {
      lineIndex = fallbackIndex;
    }
    openLineDrawer(lineIndex);
  };
  const closeLineDrawer = () => {
    setDetailDrawerOpen(false);
    setShowDocuments(false);
  };
  const handleQueueFilterChange = (nextFilter) => {
    setInvoiceFilter(nextFilter);
    setErrorMessage("");
    setSuccessMessage("");
    setActionMessage("");
  };
  const handleQueueFilterInput = (key, value) => {
    setQueueFilters((current) => ({
      ...current,
      [key]: value,
    }));
  };
  const handleQueueSearch = () => {
    setSelectedInvoiceId("");
    loadControlQueue({
      status: invoiceFilter,
      supplier: queueFilters.supplier,
      client: queueFilters.client,
      ape: queueFilters.ape,
    });
  };



  const runInvoiceAnalysis = async (invoiceId, shouldScroll = true) => {
    if (!invoiceId) {
      setErrorMessage("Selectionne d'abord une facture CouchDB.");
      return;
    }
    const invoiceRecord = combinedInvoiceItems.find((item) => getInvoiceId(item) === invoiceId) || null;
    const lineCount = Number(invoiceRecord?.line_count || 0);
    const timeoutMs = Math.min(300000, Math.max(120000, lineCount * 12000 || 120000));
    const requestUrl = `${API_BASE_URL}/analysis/strong-invoice/${encodeURIComponent(invoiceId)}`;
    const startedAt = performance.now();
    setLoadingAnalysis(true);
    setAnalysisSlowWarning(false);
    setErrorMessage("");
    setSuccessMessage("");
    setActionMessage("");
    setDetailDrawerOpen(false);
    setShowJsonRaw(false);
    // After 6 s, show a gentle "this may take a moment" message
    slowWarningTimerRef.current = setTimeout(() => {
      setAnalysisSlowWarning(true);
    }, 6000);
    console.log("[AnalysisPage] runInvoiceAnalysis:start", {
      selectedInvoice: invoiceRecord,
      invoice_id: invoiceId,
      line_count: lineCount,
      url: requestUrl,
      timeout_ms: timeoutMs,
    });
    try {
      console.log("[AnalysisPage] runInvoiceAnalysis:request_begin", {
        invoice_id: invoiceId,
        url: requestUrl,
      });
      const payload = await analyzeStrongInvoice(invoiceId, timeoutMs);
      const durationMs = Math.round(performance.now() - startedAt);
      console.log("[AnalysisPage] runInvoiceAnalysis:success", {
        invoice_id: invoiceId,
        http_status: 200,
        duration_ms: durationMs,
        lines: payload?.lines?.length ?? 0,
        hasProposal: !!payload?.accounting_proposal,
      });
      if (!payload || typeof payload !== "object") {
        throw new Error("Reponse vide du backend.");
      }
      setAnalysisResult(payload);
      setSelectedInvoiceId(invoiceId);
      cacheAnalysisResult(invoiceId, payload);
      setSelectedLineIndex(0);
      setShowDocuments(false);
      setActionMessage("");
      setSuccessMessage(
        payload?.lines?.length
          ? "Facture analysée avec le moteur local."
          : "Aucune ligne exploitable trouvée.",
      );
      if (shouldScroll) {
        window.requestAnimationFrame(() => {
          document.getElementById("decision-ia")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        });
      }
    } catch (error) {
      const durationMs = Math.round(performance.now() - startedAt);
      console.error("[AnalysisPage] runInvoiceAnalysis:error", {
        selectedInvoice: invoiceRecord,
        invoice_id: invoiceId,
        line_count: lineCount,
        url: requestUrl,
        duration_ms: durationMs,
        name: error?.name,
        status: error?.status,
        message: error?.message,
        error,
      });
      setActionMessage("");
      setErrorMessage(
        resolveFriendlyError(error, "Analyse impossible pour cette facture."),
      );
    } finally {
      clearTimeout(slowWarningTimerRef.current);
      setAnalysisSlowWarning(false);
      setLoadingAnalysis(false);
    }
  };
  const handleValidateAccountingEntry = (line) => {
    if (!line || !analysisResult) {
      setErrorMessage("Aucune écriture comptable à valider.");
      return;
    }
    const invoice = analysisResult?.invoice || {};
    const invoiceRecord = selectedInvoiceRecord || {};
    const invoiceId = selectedInvoiceId || getInvoiceId(invoice) || getInvoiceId(invoiceRecord);
    if (!invoiceId) {
      setErrorMessage("Identifiant de facture manquant.");
      return;
    }
    const now = new Date().toISOString();
    const evidence = getEvidence(line);
    const journalLines = buildJournalLinesFromAccountingProposal(
      analysisResult?.accounting_proposal,
      line,
      invoiceRecord,
    );
    const accountingEntry = {
      status: "COMPTABILISÉE",
      validated_at: now,
      invoice_id: invoiceId,
      invoice_number:
        invoice.invoice_number ||
        invoice.number ||
        invoiceRecord.invoice_number ||
        invoiceRecord.reference ||
        "",
      supplier: line.supplier || invoice.supplier || invoiceRecord.supplier || "",
      client: line.client || invoice.client || invoiceRecord.client || "",
      line_id: line.line_id || `${invoiceId}:${selectedLineIndex + 1}`,
      raw_text: line.raw_text || "",
      cleaned_text: line.cleaned_text || "",
      amount_ht: line.amount_ht ?? null,
      amount_ttc: line.amount_ttc ?? null,
      tva: line.tva ?? null,
      recommended_account: line.recommended_account || "",
      recommended_account_label: line.recommended_account_label || "",
      confidence: Number(line.confidence || 0),
      decision: line.decision || "",
      risk_level: line.risk_level || "",
      referential_status: line.referential_status || "",
      evidence_status: line.evidence_status || "",
      source_invoice_ids: evidence.sourceInvoiceIds,
      invoice_paths_sources: evidence.invoicePathsSources,
      partitions_sources: evidence.partitionsSources,
      ape_context: evidence.apeContext,
      journal_lines: journalLines,
      debit_credit_lines: journalLines,
      accounting_proposal: analysisResult?.accounting_proposal || null,
      line_analysis: line,
    };
    const updatedLine = {
      ...line,
      accounting_status: "COMPTABILISÉE",
      accounting_validated_at: now,
      accounting_entry: accountingEntry,
    };
    const updatedLines = (analysisResult.lines || []).map((item, index) =>
      index === selectedLineIndex ? updatedLine : item,
    );
    const updatedProposal = analysisResult.accounting_proposal
      ? {
          ...analysisResult.accounting_proposal,
          status: "COMPTABILISÉE",
          accounting_status: "COMPTABILISÉE",
          accounting_validated_at: now,
          validated_entry: accountingEntry,
          lines: Array.isArray(analysisResult.accounting_proposal.lines)
            ? analysisResult.accounting_proposal.lines.map((item, index) => {
                const sameLineId = item?.line_id && item.line_id === line.line_id;
                return sameLineId || index === selectedLineIndex
                  ? {
                      ...item,
                      accounting_status: "COMPTABILISÉE",
                      accounting_validated_at: now,
                    }
                  : item;
              })
            : analysisResult.accounting_proposal.lines,
        }
      : analysisResult.accounting_proposal;
    const updatedResult = {
      ...analysisResult,
      status: "COMPTABILISÉE",
      accounting_status: "COMPTABILISÉE",
      accounting_validated_at: now,
      accounting_entry: accountingEntry,
      lines: updatedLines,
      accounting_proposal: updatedProposal,
    };
    const queuePatch = {
      status: "COMPTABILISÉE",
      queue_status: "accounted",
      accounting_status: "COMPTABILISÉE",
      accounting_validated_at: now,
      accounting_entry: accountingEntry,
      analysis_result: updatedResult,
      badges: ["Comptabilisée"],
    };
    const validatedInvoiceLines = (updatedLines.length ? updatedLines : [updatedLine]).map((invoiceLine, index) => ({
      ...invoice,
      ...invoiceRecord,
      ...invoiceLine,
      invoice_id: invoiceId,
      invoice_group_id: invoiceId,
      invoice_number: accountingEntry.invoice_number,
      supplier: invoiceLine.supplier || accountingEntry.supplier,
      client: invoiceLine.client || accountingEntry.client,
      status: "COMPTABILISEE",
      workflow_status: "COMPTABILISEE",
      accounting_status: "COMPTABILISEE",
      validated_at: now,
      line_id: invoiceLine.line_id || (invoiceId + ":" + (index + 1)),
      accounting_entry: invoiceLine.line_id === line.line_id || index === selectedLineIndex ? accountingEntry : invoiceLine.accounting_entry,
    }));
    validatedInvoiceLines.forEach((invoiceLine, index) =>
      saveAccountingEntryLocally(invoiceId + ":" + (invoiceLine.line_id || invoiceLine.id || ("line-" + index)), invoiceLine),
    );;
    setAnalysisResult(updatedResult);
    cacheAnalysisResult(invoiceId, updatedResult);
    patchQueueItem(invoiceId, queuePatch);
    setSearchQueueItems((current) =>
      current.map((item) =>
        getInvoiceId(item) === invoiceId ? { ...item, ...queuePatch } : item,
      ),
    );
    setDetailDrawerOpen(false);
    setShowDocuments(false);
    setActionMessage("");
    setErrorMessage("");
    setSuccessMessage("Écriture comptable validée et enregistrée localement.");
  };
  const handleLineAction = async (actionType, line) => {
    if (!line) {
      return;
    }
    if (actionType === "validation") {
      const invoice = analysisResult?.invoice || {};
      const invoiceRecord = selectedInvoiceRecord || {};
      const invoiceLines = Array.isArray(analysisResult?.lines) && analysisResult.lines.length
        ? analysisResult.lines
        : [line];
      const invoiceId = selectedInvoiceId || getInvoiceId(invoice) || getInvoiceId(invoiceRecord) || "";
      const invoiceNumber = invoice.invoice_number || invoice.number || invoiceRecord.invoice_number || invoiceRecord.reference || "";
      const buildValidationPayload = (invoiceLine, index) => {
        const evidence = getEvidence(invoiceLine);
        return {
          created_at: new Date().toISOString(),
          source: "analyse_ia",
          invoice_id: invoiceId,
          invoice_group_id: invoiceId,
          invoice_number: invoiceNumber,
          invoice_line_count: invoiceLines.length,
          line_count: invoiceLines.length,
          supplier: invoiceLine.supplier || invoice.supplier || invoiceRecord.supplier || "",
          client: invoiceLine.client || invoice.client || invoiceRecord.client || "",
          invoice_date: invoice.date || invoice.invoice_date || invoiceRecord.date || "",
          line_id: invoiceLine.line_id || (invoiceId + ":" + (index + 1)),
          raw_text: invoiceLine.raw_text || "",
          cleaned_text: invoiceLine.cleaned_text || "",
          amount_ht: invoiceLine.amount_ht ?? null,
          amount_ttc: invoiceLine.amount_ttc ?? null,
          tva: invoiceLine.tva ?? null,
          client_ape: invoiceLine.client_ape || invoice.client_ape || invoiceRecord.client_ape || "",
          supplier_ape: invoiceLine.supplier_ape || invoice.supplier_ape || invoiceRecord.supplier_ape || "",
          metier_hint: invoiceLine.metier_hint || invoice.metier_hint || invoiceRecord.metier_hint || "",
          detected_activity: invoiceLine.detected_activity || "",
          recommended_account: invoiceLine.recommended_account || "",
          account_label: invoiceLine.recommended_account_label || "",
          confidence: Number(invoiceLine.confidence || 0),
          risk_level: invoiceLine.risk_level || "",
          decision: invoiceLine.decision || "",
          referential_status: invoiceLine.referential_status || "",
          evidence_status: invoiceLine.evidence_status || "",
          quality_status: invoiceLine.quality_status || "",
          decision_reason: invoiceLine.decision_reason || "",
          top_candidates: Array.isArray(invoiceLine.top_candidates) ? invoiceLine.top_candidates : [],
          source_invoice_ids: evidence.sourceInvoiceIds,
          invoice_paths_sources: evidence.invoicePathsSources,
          partitions_sources: evidence.partitionsSources,
          ape_context: evidence.apeContext,
          pdf_available: Boolean(selectedInvoiceId),
          status: "pending_validation",
        };
      };
      try {
        setActionMessage("");
        await Promise.all(invoiceLines.map((invoiceLine, index) =>
          createHumanValidationItem(buildValidationPayload(invoiceLine, index)),
        ));
        setActionMessage("Facture envoyée en validation humaine avec " + invoiceLines.length + "/" + invoiceLines.length + " lignes.");
      } catch (error) {
        setErrorMessage(String(error?.message || "").trim() || "Impossible d'envoyer la facture en validation humaine.");
      }
      return;
    }
    if (actionType === "non_comptable") {
      setActionMessage("La ligne a ete marquee comme non comptable dans ce test moteur.");
    }
  };
  async function handleOpenPdf(invoiceId, label = "") {
    if (!invoiceId) {
      setErrorMessage("Identifiant de facture manquant.");
      return;
    }
    setErrorMessage("");
    setCardAnalyzingId(`pdf:${invoiceId}`);
    try {
      const preview = await fetchInvoicePdfPreview(invoiceId);
      const pageCount = Math.max(0, Number(preview?.page_count || 0));
      if (!pageCount) throw new Error("Document source non disponible pour cette facture.");
      const previewBase = `${API_BASE_URL}/api/analysis/invoice-pdf-preview/${encodeURIComponent(invoiceId)}/pages`;
      setPdfViewerPages(Array.from({ length: pageCount }, (_, index) => `${previewBase}/${index + 1}`));
      setPdfViewerLabel(label || "Aperçu de la facture");
      setShowPdfViewer(true);
    } catch (error) {
      setErrorMessage(String(error?.message || "Document source non disponible pour cette facture.").trim());
    } finally {
      setCardAnalyzingId("");
    }
  }
  async function handleInvoiceCardPdfClick(invoice) {
    const invoiceId = getInvoiceId(invoice);
    await handleOpenPdf(
      invoiceId,
      invoice?.invoice_number || invoice?.supplier || invoice?.supplier_name || "Aperçu de la facture",
    );
  }
  function closePdfViewer() {
    setShowPdfViewer(false);
    setPdfViewerPages([]);
    setPdfViewerLabel("");
  }
  const normalizedBatchLimit = Math.max(1, Math.floor(Number(batchLimitInput) || Number(batchRequestedLimit) || 50));
  const batchTotalForDisplay = Math.max(
    0,
    Number(batchJob?.sampled_count || batchJob?.selected_count || batchJob?.limit || batchRequestedLimit || normalizedBatchLimit || 0),
  );
  const handleBatchLimitInputChange = (event) => {
    const nextValue = event.target.value;
    if (nextValue === "") {
      setBatchLimitInput("");
      return;
    }
    const nextNumber = Math.max(1, Math.floor(Number(nextValue) || 1));
    setBatchLimitInput(String(nextNumber));
  };
  const handleStartBatchWithLimit = () => {
    const nextLimit = Math.max(1, Math.floor(Number(batchLimitInput) || Number(batchRequestedLimit) || 50));
    setBatchLimitInput(String(nextLimit));
    try {
      window.sessionStorage?.removeItem(PERFORMANCE_RESET_STORAGE_KEY);
      window.dispatchEvent(new Event("keymanage:batch-analysis-started"));
    } catch {
      // Storage and custom events are optional in restricted browser contexts.
    }
    handleLoadBatchAnalysis(nextLimit, sortStrategy);
  };
  const handleClearLocalListAndReset = () => {
    handleClearBatchResults();
    try {
      window.sessionStorage?.setItem(PERFORMANCE_RESET_STORAGE_KEY, "1");
      window.dispatchEvent(new Event("keymanage:local-analysis-reset"));
    } catch {
      // Keep the local list reset even when browser storage is unavailable.
    }
  };
  const handleResetSession = async () => {
    if (resettingTestSession) return;
    setResettingTestSession(true);
    setErrorMessage("");
    setActionMessage("");
    try {
      setSelectedInvoiceId("");
      setAnalysisResult(null);
      setDetailDrawerOpen(false);
      const payload = await handleResetTestSession();
      setResetSessionConfirmOpen(false);
      setSuccessMessage(payload?.message || "Session de test réinitialisée sans modification de CouchDB.");
    } catch (error) {
      setErrorMessage(
        String(error?.message || "Impossible de réinitialiser la session de test.").trim(),
      );
    } finally {
      setResettingTestSession(false);
    }
  };
  const currentBatchJobId = String(batchJob?.job_id || "").trim();
  const currentBatchItems = currentBatchJobId
    ? queueItems.filter(
        (item) => String(item?.batch_job_id || "").trim() === currentBatchJobId,
      )
    : [];
  const visibleSourceItems = hasLoadedSearchQueue ? searchQueueItems : queueItems;
  const visibleQueueItems = currentBatchItems.length
    ? visibleSourceItems.filter(
        (item) => String(item?.batch_job_id || "").trim() !== currentBatchJobId,
      )
    : visibleSourceItems;
  const filteredCurrentBatchItems = sortQueueItems(filterQueueItemsByStatus(currentBatchItems, invoiceFilter), sortStrategy);
  const filteredVisibleQueueItems = sortQueueItems(filterQueueItemsByStatus(visibleQueueItems, invoiceFilter), sortStrategy);

  const isBatchRunning = loadingBatch || ["queued", "running", "stopping", "already_running"].includes(String(batchJob?.status || "").toLowerCase());

  const renderInvoiceQueueCard = (invoice, keyPrefix = "queue", queuePosition = null) => {
    const invoiceId = getInvoiceId(invoice);
    const lineCount = Number(invoice?.line_count || invoice?.line_items_count || invoice?.lines?.length || invoice?.line_items?.length || 0);
    const supplier = textOrFallback(invoice?.supplier || invoice?.supplier_name, "Fournisseur inconnu");
    const invoiceNumber = textOrFallback(invoice?.invoice_number, "Numéro inconnu");
    const client = textOrFallback(invoice?.client, "Client non renseigné");
    const rawDate = invoice?.invoice_date || invoice?.date || invoice?.analyzed_at || invoice?.created_at;
    const parsedDate = rawDate ? new Date(rawDate) : null;
    const dateLabel = parsedDate && !Number.isNaN(parsedDate.getTime())
      ? new Intl.DateTimeFormat("fr-FR").format(parsedDate)
      : textOrFallback(rawDate, "Date inconnue");
    const pdfLoading = cardAnalyzingId === `pdf:${invoiceId}`;
    return (
      <article
        key={`${keyPrefix}-${invoiceId || invoice?.invoice_number || supplier}`}
        className={`analysis-invoice-card analysis-invoice-card-legacy${invoiceId === selectedInvoiceId ? " active" : ""}`}
      >
        <div className="analysis-invoice-card-headline">
          <div className="analysis-invoice-card-heading-copy">
            <h3 className="analysis-invoice-card-title">{supplier}</h3>
            <p className="analysis-invoice-reference">{invoiceNumber} - {lineCount} ligne{lineCount > 1 ? "s" : ""}</p>
          </div>
          <div className="analysis-invoice-card-badges">
            {Number.isInteger(queuePosition) ? <span className="analysis-queue-position">#{queuePosition + 1}</span> : null}
            <span className={`status-pill ${queueStatusTone(invoice?.status)}`}>
              {queueStatusLabel(invoice?.status)}
            </span>
          </div>
        </div>
        <div className="analysis-invoice-card-meta-row">
          <span><UserSquare2 size={14} /> {client}</span>
          <span><CalendarDays size={14} /> {dateLabel}</span>
        </div>
        <div className="analysis-invoice-card-actions analysis-invoice-card-actions-legacy">
          <button type="button" className="analysis-card-action-btn analysis-card-pdf" onClick={() => void handleInvoiceCardPdfClick(invoice)} disabled={!invoiceId || pdfLoading}>
            {pdfLoading ? <LoaderCircle size={14} className="spin" /> : <FileText size={14} />} {pdfLoading ? "Ouverture..." : "Voir PDF"}
          </button>
          <button type="button" className="analysis-card-action-btn analysis-card-analyze" onClick={() => runInvoiceAnalysis(invoiceId)} disabled={!invoiceId || loadingAnalysis}>
            <BrainCircuit size={14} /> Analyser
          </button>
        </div>
      </article>
    );
  };
  return (
    <div className="analysis-page font-sans antialiased text-slate-800">      <section className="card surface-card analysis-search-card">
        <div className="analysis-search-card-title">
          <span className="analysis-search-badge"><SearchCheck size={15} /> Recherche CouchDB</span>
        </div>
        <hr className="analysis-search-divider border-t border-slate-200/70" />
        <div className="analysis-search-fields">
          <label><span className="analysis-field-label">Fournisseur</span><span className="analysis-field-input"><span className="analysis-icon-frame supplier"><Building2 size={16} /></span><input value={queueFilters.supplier} onChange={(event) => handleQueueFilterInput("supplier", event.target.value)} placeholder="Ex : Bouygues Telecom" /></span></label>
          <label><span className="analysis-field-label">Client</span><span className="analysis-field-input client"><span className="analysis-icon-frame client"><UserSquare2 size={16} /></span><input value={queueFilters.client} onChange={(event) => handleQueueFilterInput("client", event.target.value)} placeholder="Ex : Boucherie Mouad" /></span></label>
          <label><span className="analysis-field-label">Code APE</span><span className="analysis-field-input ape"><span className="analysis-icon-frame ape"><Hash size={16} /></span><input value={queueFilters.ape} onChange={(event) => handleQueueFilterInput("ape", event.target.value)} placeholder="Ex : 4722Z" /></span></label>
        </div>
        <button type="button" className="primary-btn analysis-search-submit" onClick={handleQueueSearch} disabled={loadingInvoices}>
          {loadingInvoices ? <LoaderCircle size={16} className="spin" /> : <SearchCheck size={16} />} {loadingInvoices ? "Recherche en cours..." : "Rechercher dans CouchDB"}
        </button>
      </section>
      <section className="card surface-card analysis-control-panel">
        <div className="section-header">
          <div>
            <h1 className="analysis-control-title">File de contrôle comptable</h1>
          </div>
        </div>
        <div className="analysis-queue-filters">
          {[
            ["all", "Toutes", queueCounts?.all ?? queueItems.length],
            ["to_control", "À contrôler", queueCounts?.to_control ?? 0],
            ["new_articles", "Nouveaux articles", queueCounts?.new_articles ?? 0],
            ["low_risk", "Faible risque", queueCounts?.low_risk ?? 0],
            ["not_analyzed", "Non analysées", queueCounts?.not_analyzed ?? 0],
          ].map(([value, label, count]) => (
            <button
              key={value}
              type="button"
              className={invoiceFilter === value ? "analysis-queue-filter active" : "analysis-queue-filter"}
              onClick={() => handleQueueFilterChange(value)}
            >
              {label} ({count})
            </button>
          ))}
        </div>
        <div className="analysis-sort-control" role="group" aria-label="Stratégie de traitement">
          <label htmlFor="analysis-sort-strategy">Stratégie de traitement :</label>
          <select
            id="analysis-sort-strategy"
            value={sortStrategy}
            onChange={(event) => setSortStrategy(event.target.value)}
            disabled={isBatchRunning}
          >
            <option value="DUE_DATE">📅 Urgence (Date d'échéance)</option>
            <option value="CHRONO">⏱️ Chronologique (Date d'émission)</option>
            <option value="SUPPLIER">🏢 Par Fournisseur (Traitement par lots)</option>
            <option value="AMOUNT">💰 Par Montant TTC (Priorité enjeux)</option>
          </select>
        </div>
        <hr className="analysis-filter-divider border-t border-slate-200/70" />
        <div className="analysis-toolbar analysis-action-toolbar">
          <div className="analysis-action-row">
            <label className="analysis-limit-control">
              <span>NOMBRE À TRAITER</span>
              <input className="analysis-batch-limit-input" type="number" min="1" value={batchLimitInput} onChange={handleBatchLimitInputChange} aria-label="Nombre à traiter" />
            </label>
            <button type="button" className="primary-btn compact" onClick={handleStartBatchWithLimit} disabled={loadingBatch}><Database size={15} /> Analyser un nouveau lot</button>
            <button type="button" className="success-btn compact" onClick={handleResumeBatchAnalysis}><BrainCircuit size={15} /> Continuer l'analyse</button>
            <button type="button" className="danger-btn compact" onClick={handleStopBatchAnalysis}><X size={15} /> Arrêter l'analyse</button>
          </div>
          <div className="analysis-action-row analysis-management-row">
            <button type="button" className="warning-btn compact" onClick={handleSaveBatchAnalysis}><Save size={15} /> Enregistrer l'analyse</button>
            <button type="button" className="secondary-btn compact" onClick={handleShowAllRecordedInvoices} disabled={loadingBatch}><SearchCheck size={15} /> Afficher toutes les factures enregistrées</button>
            <button type="button" className="danger-btn compact" onClick={() => setResetSessionConfirmOpen(true)} disabled={resettingTestSession}>{resettingTestSession ? <LoaderCircle size={14} className="spin" /> : <RotateCcw size={14} />} {resettingTestSession ? "Réinitialisation..." : "Réinitialiser la session de test"}</button>
            {persistedBatchCount > 0 ? <button type="button" className="secondary-btn compact local-clear-btn" onClick={handleClearLocalListAndReset} disabled={loadingBatch}><X size={14} /> Vider la liste locale</button> : null}
          </div>
        </div>
        <div className="analysis-invoice-count">{persistedBatchCount || queueItems.length} facture(s) disponible(s).</div>
        {batchActionMessage || batchSuccessMessage || errorMessage || successMessage || actionMessage ? (
          <div className="analysis-notice-stack">
            {batchActionMessage ? <div className="analysis-inline-note">{batchActionMessage}</div> : null}
            {batchSuccessMessage ? <div className="analysis-success-message">{batchSuccessMessage}</div> : null}
            {errorMessage ? <div className="analysis-inline-error">{errorMessage}</div> : null}
            {successMessage ? <div className="analysis-success-message">{successMessage}</div> : null}
            {actionMessage ? <div className="analysis-inline-note">{actionMessage}</div> : null}
          </div>
        ) : null}
        {resetSessionConfirmOpen ? (
          <div className="ve-modal-backdrop" role="presentation">
            <section className="ve-modal-panel ve-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="reset-session-title">
              <header className="ve-modal-head">
                <div>
                  <h2 id="reset-session-title" className="ve-modal-title">Réinitialiser la session de test</h2>
                  <p className="ve-modal-subtitle">Cette action remet à zéro la session de test sans toucher à CouchDB. Les résultats d’analyse, la file de validation humaine et l’historique local seront vidés.</p>
                </div>
                <button type="button" className="ve-modal-close" onClick={() => setResetSessionConfirmOpen(false)} disabled={resettingTestSession} aria-label="Fermer"><X size={18} /></button>
              </header>
              <div className="ve-modal-body">
                <div className="ve-confirm-actions">
                  <button type="button" className="secondary-btn compact" onClick={() => setResetSessionConfirmOpen(false)} disabled={resettingTestSession}>Annuler</button>
                  <button type="button" className="danger-btn compact" onClick={() => void handleResetSession()} disabled={resettingTestSession}>
                    {resettingTestSession ? <LoaderCircle size={14} className="spin" /> : <RotateCcw size={14} />} Confirmer la réinitialisation
                  </button>
                </div>
              </div>
            </section>
          </div>
        ) : null}
            {isBatchRunning ? (
              <div className="analysis-batch-status-stack">
                <div className="analysis-summary-grid">
                  <SummaryCard
                    label="Statut"
                    value={batchJob?.status === "running" || batchJob?.status === "queued" ? "En cours" : batchJob?.status === "stopping" ? "Arrêt en cours" : "Déjà lancé"}
                    detail={batchJob?.message || "Préparation du lot..."}
                    tone="review"
                  />
                  <SummaryCard label="Traitées" value={batchJob?.processed || 0} detail={`${batchTotalForDisplay} facture(s) chargée(s)`} tone="info" />
                  <SummaryCard label="Succès" value={batchJob?.success || 0} detail="Analyses complètes" tone="success" />
                  <SummaryCard label="Échecs" value={batchJob?.failed || 0} detail={formatDurationLabel(batchJob?.duration_ms) || "0 ms"} tone={Number(batchJob?.failed || 0) > 0 ? "danger" : "info"} />
                </div>
                <div className="analysis-batch-progress-panel">
                  <div className="analysis-batch-progress-head">
                    <h3>Factures traitées dans ce lot</h3>
                    <p>Les cartes apparaissent au fur et à mesure que chaque facture est finalisée.</p>
                  </div>
                  {filteredCurrentBatchItems.length ? (
                    <div className="analysis-invoice-carousel analysis-invoice-carousel-inline">
                      {filteredCurrentBatchItems.map((invoice, index) => renderInvoiceQueueCard(invoice, `batch-${currentBatchJobId}`, index))}
                    </div>
                  ) : (
                    <div className="analysis-carousel-empty analysis-carousel-empty-subtle">
                      <strong>Les premières factures apparaîtront ici dès qu'elles seront analysées.</strong>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
            {searchQueueErrorMessage ? (
              <div className="analysis-inline-error">{searchQueueErrorMessage}</div>
            ) : null}
            {queueErrorMessage ? (
              <div className="analysis-inline-error">
                {queueErrorMessage}
                {(String(queueErrorMessage).includes("8000") || String(queueErrorMessage).toLowerCase().includes("fastapi")) ? (
                  <span style={{display:"block",marginTop:4,fontSize:"0.75rem",opacity:0.8}}>
                    Vérifiez que le backend FastAPI tourne sur le port 8000.
                  </span>
                ) : null}
              </div>
            ) : null}
            <div className="analysis-invoice-carousel">
               {loadingBatch && !filteredVisibleQueueItems.length && !filteredCurrentBatchItems.length ? (
                <div className="analysis-carousel-empty">
                  <LoaderCircle size={18} className="spin" />
                  <strong>Analyse du lot en cours...</strong>
                </div>
              ) : filteredVisibleQueueItems.length ? (
                filteredVisibleQueueItems.map((invoice, index) =>
                  renderInvoiceQueueCard(invoice, "queue", index),
                )
              ) : hasLoadedSearchQueue || hasLoadedQueue || persistedBatchCount > 0 ? (
                <div className="analysis-carousel-empty">
                  <strong>{hasLoadedSearchQueue ? searchQueueEmptyLabel : queueEmptyLabel}</strong>
                </div>
              ) : null}
            </div>
        </section>
        {loadingAnalysis ? (
          <section className="card surface-card analysis-loading-panel">
          <LoaderCircle size={22} className="spin" />
          <div>
            <strong>Analyse en cours...</strong>
            <p>
              Le moteur inspecte la facture ligne par ligne et privilegie la
              validation humaine en cas de doute.
            </p>
          </div>
          </section>
        ) : null}
        {analysisResult ? (
          <>
          <section className="card surface-card" id="accounting-proposal">
            <div className="section-header">
              <h2 className="section-title">Proposition comptable</h2>
              <p className="section-text">
                Proposition générée directement à partir de l'analyse courante,
                sans etape supplementaire dans l'interface.
              </p>
            </div>
            {analysisResult?.accounting_proposal ? (
              <div className="ap-inline-shell">
                <div className="ap-modal-status-row">
                  <span className={`status-pill ${proposalStatusTone(analysisResult.accounting_proposal.proposal_status)}`}>
                    {proposalStatusLabel(analysisResult.accounting_proposal.proposal_status)}
                  </span>
                  <span className="ap-modal-generated-by">
                    {textOrFallback(analysisResult.accounting_proposal.supplier)}
                    {" ? "}
                    {textOrFallback(analysisResult.accounting_proposal.client)}
                    {analysisResult.accounting_proposal.invoice_number
                      ? ` · Facture ${analysisResult.accounting_proposal.invoice_number}`
                      : ""}
                  </span>
                </div>
                <div className="ap-summary-cards">
                  {[
                    { label: "Lignes", value: proposalSummary.total_lines ?? 0 },
                    { label: "Auto-validées", value: proposalSummary.auto_ok ?? 0 },
                    { label: "À valider", value: proposalSummary.validation_humaine ?? 0 },
                    { label: "Rejetées", value: proposalSummary.rejected ?? 0 },
                    { label: "Non compta.", value: proposalSummary.non_comptable ?? 0 },
                    { label: "Score moyen", value: formatPercent(proposalSummary.average_confidence ?? 0) },
                  ].map(({ label, value }) => (
                    <div key={label} className="ap-summary-card">
                      <div className="ap-summary-card-label">{label}</div>
                      <div className="ap-summary-card-value">{value}</div>
                    </div>
                  ))}
                </div>
                <div className="ap-lines-table-shell">
                  <table className="ap-lines-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Article facture</th>
                        <th>Compte proposé</th>
                        <th>HT</th>
                        <th>TTC</th>
                        <th>Score</th>
                        <th>Risque</th>
                        <th>Décision</th>
                        <th>Validation humaine</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {proposalLines.map((apLine, idx) => (
                        <tr key={apLine.line_id || idx}>
                          <td>{idx + 1}</td>
                          <td>
                            <div className="ap-line-article">
                              {textOrFallback(apLine.raw_text)}
                              <span className="ap-cleaned">{apLine.cleaned_text}</span>
                            </div>
                          </td>
                          <td>
                            {apLine.recommended_account ? (
                              <>
                                <div className="ap-account-code">{apLine.recommended_account}</div>
                                <div className="ap-account-label">{apLine.account_label || ""}</div>
                              </>
                            ) : (
                              <span className="ap-bool-no">-</span>
                            )}
                          </td>
                          <td>{formatAmount(apLine.amount_ht, invoiceHeader?.currency)}</td>
                          <td>{formatAmount(apLine.amount_ttc, invoiceHeader?.currency)}</td>
                          <td>{formatPercent(apLine.confidence)}</td>
                          <td>
                            <span className={pillClass("risk", apLine.risk_level)}>
                              {riskLabel(apLine.risk_level)}
                            </span>
                          </td>
                          <td>
                            <span className={pillClass("decision", apLine.decision)}>
                              {decisionLabel(apLine.decision)}
                            </span>
                          </td>
                          <td>
                            {apLine.requires_human_validation
                              ? <span className={pillClass("decision", "validation_humaine")}>Oui</span>
                              : <span className="ap-bool-no">Non</span>}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="secondary-btn compact analysis-inspect-btn"
                              onClick={() => openProposalLineDrawer(apLine, idx)}
                            >
                              <PanelRightOpen size={14} />
                              Inspecter
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="ap-json-section">
                  <button
                    type="button"
                    className="ap-json-toggle"
                    onClick={() => setShowJsonRaw((v) => !v)}
                  >
                    {showJsonRaw ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    JSON brut - accounting_proposal
                  </button>
                  {showJsonRaw ? (
                    <pre className="ap-json-pre">
                      {JSON.stringify(analysisResult.accounting_proposal, null, 2)}
                    </pre>
                  ) : null}
                </div>
                <div className="ap-modal-footer">
                  <button
                    type="button"
                    className="secondary-btn compact"
                    onClick={() =>
                      copyToClipboard(
                        JSON.stringify(analysisResult.accounting_proposal, null, 2),
                        () => setActionMessage("JSON accounting_proposal copié dans le presse-papiers."),
                      )
                    }
                  >
                    <ClipboardCheck size={15} />
                    Copier JSON
                  </button>
                  <button
                    type="button"
                    className="secondary-btn compact"
                    onClick={() =>
                      downloadJson(
                        analysisResult.accounting_proposal,
                        `accounting_proposal_${(analysisResult.accounting_proposal.invoice_id || "export").replace(/:/g, "_")}.json`,
                      )
                    }
                  >
                    <Download size={15} />
                    Télécharger JSON
                  </button>
                </div>
              </div>
            ) : (
              <div className="analysis-system-notice">
                Aucune proposition comptable disponible pour cette facture.
              </div>
            )}
          </section>
          {detailDrawerOpen && selectedLine ? (
            <div className="analysis-detail-drawer-backdrop" onClick={closeLineDrawer}>
              <aside
                className="analysis-detail-drawer"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="analysis-detail-drawer-head">
                  <div className="section-header">
                    <h2 className="section-title">Fiche d'audit ligne</h2>
                    <p className="section-text">
                      Decision moteur, contexte et preuves documentaires.
                    </p>
                  </div>
                  <div className="analysis-drawer-head-actions">
                    <button
                      type="button"
                      className="secondary-btn compact analysis-pdf-btn"
                      title="Ouvrir le PDF source de la facture"
                      onClick={() => handleOpenPdf(selectedInvoiceId)}
                    >
                      <FileText size={14} />
                      Voir PDF facture
                    </button>
                    <button
                      type="button"
                      className="analysis-detail-drawer-close"
                      onClick={closeLineDrawer}
                    >
                      <X size={18} />
                    </button>
                  </div>
                </div>
                <DrawerErrorBoundary resetKey={`${selectedInvoiceId}:${selectedLineIndex}`}>
                  <div className="analysis-engine-detail-stack analysis-detail-drawer-body">
                  <div className="analysis-decision-hero audit-hero-compact">
                    <div className="audit-hero-main">
                      <div className="decision-label">Compte recommandé</div>
                      <div
                        className="decision-value audit-account-value"
                        title={
                          selectedLine.recommended_account
                            ? formatAccount(
                                selectedLine.recommended_account,
                                selectedLine.recommended_account_label,
                              )
                            : "Aucun compte proposé"
                        }
                      >
                        {selectedLine.recommended_account
                          ? formatAccount(
                              selectedLine.recommended_account,
                              selectedLine.recommended_account_label,
                            )
                          : "Aucun compte proposé"}
                      </div>
                      <div className="audit-hero-sublines">
                        <span className="analysis-decision-subline">
                          <strong>Ligne :</strong> {textOrFallback(selectedLine.raw_text)}
                        </span>
                        {selectedDisplayGroup?.occurrenceCount > 1 ? (
                          <span className="analysis-decision-subline">
                            <strong>Occurrences identiques :</strong> {selectedDisplayGroup.occurrenceCount}
                          </span>
                        ) : null}
                        <span className="analysis-decision-subline">
                          <strong>Activité :</strong> {toDisplayMetier(selectedLine.detected_activity)}
                          {" · "}
                          <strong>Référentiel :</strong> {referentialLabel(selectedLine.referential_status)}
                        </span>
                      </div>
                    </div>
                    <div className="analysis-decision-side">
                      <div className="score-badge audit-score-badge">{formatPercent(selectedLine.confidence)}</div>
                      <span className={pillClass("decision", selectedLine.decision)}>
                        {decisionLabel(selectedLine.decision)}
                      </span>
                    </div>
                  </div>
                  <div className="analysis-proof-mini-grid">
                    <div className="analysis-proof-mini-card">
                      <span>Factures sources</span>
                      <strong>{selectedProofCounts.invoiceCount}</strong>
                    </div>
                    <div className="analysis-proof-mini-card">
                      <span>Documents PDF</span>
                      <strong>{selectedProofCounts.pdfCount}</strong>
                    </div>
                    <div className="analysis-proof-mini-card">
                      <span>Partitions</span>
                      <strong>{selectedProofCounts.partitionCount}</strong>
                    </div>
                    <div className="analysis-proof-mini-card">
                      <span>APE</span>
                      <strong>{selectedEvidence.apeContext.join(", ") || "Non renseigné"}</strong>
                    </div>
                    <div className="analysis-proof-mini-card">
                      <span>Statut qualite</span>
                      <strong>{qualityLabel(selectedLine.quality_status)}</strong>
                    </div>
                  </div>
                  <div className="analysis-engine-actions">                    <button
                      type="button"
                      className="success-btn compact"
                      onClick={() => handleValidateAccountingEntry(selectedLine)}
                    >
                      <ClipboardCheck size={15} />
                      Valider l'écriture comptable
                    </button>
                    <button
                      type="button"
                      className="secondary-btn compact"
                      onClick={() => handleLineAction("validation", selectedLine)}
                    >
                      <ShieldCheck size={15} />
                      Envoyer en validation humaine
                    </button>
                    <button
                      type="button"
                      className="secondary-btn compact"
                      onClick={() => handleLineAction("non_comptable", selectedLine)}
                    >
                      <ShieldAlert size={15} />
                      Marquer non comptable
                    </button>
                    <button
                      type="button"
                      className="secondary-btn compact"
                      onClick={() =>
                        copyToClipboard(buildProofPayload(selectedLine), () =>
                          setActionMessage("Preuves copi??es dans le presse-papiers."),
                        )
                      }
                    >
                      <ClipboardCheck size={15} />
                      Copier preuves
                    </button>
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Ligne originale</div>
                    <div className="analysis-detail-grid">
                      <DetailRow label="Texte brut" value={selectedLine.raw_text} />
                      <DetailRow label="Texte nettoye" value={selectedLine.cleaned_text} />
                      <DetailRow label="Montant HT" value={formatAmount(selectedLine.amount_ht, invoiceHeader?.currency)} />
                      <DetailRow label="Montant TTC" value={formatAmount(selectedLine.amount_ttc, invoiceHeader?.currency)} />
                      <DetailRow label="TVA" value={formatPercent(selectedLine.tva)} />
                    </div>
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Decision moteur</div>
                    <div className="analysis-detail-grid">
                      <DetailRow
                        label="Statut referentiel"
                        value={referentialLabel(selectedLine.referential_status)}
                        tip={
                          {
                            found_exact: "Trouvé exact : article identifié dans les bases métiers.",
                            found_fuzzy: "Proche : article similaire trouvé, mais pas identique.",
                            missing_candidate: "Absent : hypothèse contextuelle prudente, validation requise.",
                            unknown: "Inconnu : aucune référence fiable trouvée.",
                            non_comptable: "Non comptable : ligne hors périmètre de matching.",
                          }[selectedLine.referential_status] ||
                          "Aucune référence fiable n'a été trouvée."
                        }
                      />
                      <DetailRow
                        label="Compte recommande"
                        value={
                          selectedLine.recommended_account
                            ? formatAccount(
                                selectedLine.recommended_account,
                                selectedLine.recommended_account_label,
                              )
                            : "Non renseigné"
                        }
                        highlight
                        tip="Compte proposé d'après le meilleur candidat des bases métiers. À valider si le statut n'est pas « Trouvé exact »."
                        tipPlacement="left"
                      />
                      <DetailRow
                        label="Score"
                        value={formatPercent(selectedLine.confidence)}
                        tip="Similarité entre la ligne facture et le meilleur article des bases métiers. Plus il est élevé, plus le match est fiable."
                      />
                      <DetailRow
                        label="Risque"
                        value={riskLabel(selectedLine.risk_level)}
                        tipPlacement="left"
                        tip={
                          {
                            faible: "Faible : match fiable, contexte et preuves cohérents.",
                            moyen: "Moyen : article proche mais non exact. Validation humaine requise.",
                            eleve: "Élevé : éléments insuffisants ou contexte métier incohérent.",
                          }[selectedLine.risk_level] ||
                          "Moyen : article proche mais non exact. Validation humaine requise."
                        }
                      />
                      <DetailRow
                        label="Decision"
                        value={decisionLabel(selectedLine.decision)}
                        tip={
                          {
                            auto_ok: "Auto-validée : ligne suffisamment fiable, automatisation possible.",
                            validation_humaine: "À valider : auto-validation bloquée, vérification humaine requise.",
                            rejeter: "Rejeté : aucun candidat fiable trouvé.",
                            non_comptable: "Non comptable : hors périmètre de matching.",
                          }[selectedLine.decision] ||
                          "À valider : vérification humaine requise."
                        }
                      />
                      <DetailRow
                        label="Preuves"
                        value={evidenceStatusLabel(selectedLine.evidence_status)}
                        tipPlacement="left"
                        tip="Preuves issues des factures sources, PDF, partitions et APE du référentiel. Plus elles sont nombreuses, plus la décision est fiable."
                      />
                    </div>
                    <p className="detail-text">{textOrFallback(selectedLine.decision_reason)}</p>
                    {selectedHasSecurityViolation ? (
                      <div className="analysis-warning-card">
                        <AlertTriangle size={16} />
                        Règle sécurité violée : Auto-validée interdite hors found_exact
                      </div>
                    ) : null}
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">
                      {referentialPanelTitle(selectedLine.referential_status)}
                    </div>
                    <div className="analysis-detail-grid">
                      <DetailRow
                        label="Article source"
                        value={selectedPrimaryCandidate?.article_source || selectedLine.raw_text}
                      />
                      <DetailRow
                        label="Article canonique"
                        value={selectedPrimaryCandidate?.article_canonique || selectedLine.cleaned_text}
                      />
                      <DetailRow
                        label="Compte + libelle"
                        value={
                          selectedLine.recommended_account
                            ? formatAccount(
                                selectedLine.recommended_account,
                                selectedLine.recommended_account_label,
                              )
                            : "Non renseigné"
                        }
                        highlight
                      />
                      <DetailRow label="TVA referentiel" value={formatPercent(selectedLine.taux_tva)} />
                      <DetailRow label="Categorie" value={selectedLine.categorie} />
                      <DetailRow label="Sous-categorie" value={selectedLine.sous_categorie} />
                      <DetailRow label="Type fournisseur" value={selectedLine.type_fournisseur} />
                    </div>
                    {selectedLine.referential_status === "missing_candidate" ? (
                      <p className="detail-text">
                        Cet article n&apos;est pas présent dans les référentiels validés.
                        Le compte proposé est une hypothèse contextuelle à valider.
                      </p>
                    ) : null}
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Contexte métier</div>
                    <div className="analysis-detail-grid">
                      <DetailRow label="Fournisseur" value={selectedLine.supplier} />
                      <DetailRow label="Client" value={selectedLine.client} />
                      <DetailRow label="APE client" value={selectedLine.client_ape} />
                      <DetailRow label="APE fournisseur" value={selectedLine.supplier_ape} />
                      <DetailRow label="Métier suggéré" value={toDisplayMetier(selectedLine.metier_hint)} />
                      <DetailRow label="Activité détectée" value={toDisplayMetier(selectedLine.detected_activity)} />
                    </div>
                    {!selectedLine.client_ape && !selectedLine.supplier_ape ? (
                      <p className="analysis-inline-note">Contexte APE absent.</p>
                    ) : null}
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Top candidats</div>
                    <div className="analysis-candidate-list">
                      {selectedTopCandidates.length ? (
                        selectedTopCandidates.map((candidate, index) => (
                          <article
                            key={`${candidate.account}-${candidate.article_source}-${index}`}
                            className="analysis-candidate-item"
                          >
                            <div className="analysis-candidate-rank">#{index + 1}</div>
                            <div>
                              <div className="analysis-candidate-title">
                                {formatAccount(candidate.account, candidate.account_label)}
                              </div>
                              <div className="analysis-candidate-meta">
                                {textOrFallback(candidate.article_source)} - Base{" "}
                                {toDisplayMetier(candidate.base)} - Score{" "}
                                {formatPercent(candidate.score)}
                              </div>
                              <p className="analysis-candidate-reason">
                                {textOrFallback(candidate.reason)}
                              </p>
                              <div className="analysis-candidate-extra">
                                <span>Categorie : {textOrFallback(candidate.categorie)}</span>
                                <span>Sous-categorie : {textOrFallback(candidate.sous_categorie)}</span>
                                <span>Type fournisseur : {textOrFallback(candidate.type_fournisseur)}</span>
                              </div>
                            </div>
                          </article>
                        ))
                      ) : (
                        <span className="analysis-token muted">Aucun candidat fiable</span>
                      )}
                    </div>
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Factures sources</div>
                    <div className="analysis-token-list">
                      {selectedEvidence.sourceInvoiceIds.length ? (
                        selectedEvidence.sourceInvoiceIds.slice(0, 3).map((item) => (
                          <span key={item} className="analysis-token">
                            {item}
                          </span>
                        ))
                      ) : (
                        <span className="analysis-token muted">Non renseigné</span>
                      )}
                    </div>
                    {selectedEvidence.sourceInvoiceIds.length > 3 ? (
                      <p className="analysis-inline-note">
                        +{selectedEvidence.sourceInvoiceIds.length - 3} autres
                      </p>
                    ) : null}
                  </div>
                  <div className="detail-card">
                    <div className="analysis-detail-card-head">
                      <div className="detail-label">Documents PDF</div>
                      <button
                        type="button"
                        className="secondary-btn compact"
                        onClick={() => setShowDocuments((current) => !current)}
                      >
                        {showDocuments ? "Masquer documents" : "Voir documents sources"}
                      </button>
                    </div>
                    {selectedEvidence.invoicePathsSources.length ? (
                      showDocuments ? (
                        <div className="analysis-document-list">
                          {selectedEvidence.invoicePathsSources.map((path) => (
                            <div key={path} className="analysis-document-item">
                              <div>
                                <strong>{fileNameFromPath(path)}</strong>
                                <p title={path}>Chemin complet disponible via copie.</p>
                              </div>
                              <button
                                type="button"
                                className="secondary-btn compact"
                                onClick={() =>
                                  copyToClipboard(path, () =>
                                    setActionMessage("Chemin PDF copie dans le presse-papiers."),
                                  )
                                }
                              >
                                <ClipboardCheck size={14} />
                                Copier chemin
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="analysis-token muted">
                          {selectedProofCounts.pdfCount} document
                          {selectedProofCounts.pdfCount > 1 ? "s" : ""} disponible
                          {selectedProofCounts.pdfCount > 1 ? "s" : ""}
                        </span>
                      )
                    ) : (
                      <span className="analysis-token muted">Non renseigné</span>
                    )}
                  </div>
                  <div className="detail-card">
                    <div className="detail-label">Statut qualite</div>
                    <div className="analysis-detail-grid">
                      <DetailRow label="Preuves" value={evidenceStatusLabel(selectedLine.evidence_status)} />
                      <DetailRow label="Qualité" value={qualityLabel(selectedLine.quality_status)} />
                      <DetailRow
                        label="APE referentiel"
                        value={selectedEvidence.apeContext.join(", ")}
                      />
                      <DetailRow
                        label="Partitions"
                        value={selectedEvidence.partitionsSources.join(", ")}
                      />
                    </div>
                  </div>
                  </div>
                </DrawerErrorBoundary>
              </aside>
            </div>
          ) : null}
          </>
        ) : null}
        {showPdfViewer && pdfViewerPages.length > 0 ? (
          <div className="ve-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closePdfViewer()}>
            <section className="ve-modal-panel ve-pdf-modal-panel analysis-pdf-preview-modal" role="dialog" aria-modal="true">
              <header className="ve-modal-head">
                <div>
                  <h2 className="ve-modal-title">Aperçu de la facture</h2>
                  <p className="ve-modal-subtitle">{pdfViewerLabel}</p>
                </div>
                <button type="button" className="ve-modal-close" onClick={closePdfViewer} aria-label="Fermer"><X size={19} /></button>
              </header>
              <div className="ve-pdf-preview-pages">
                {pdfViewerPages.map((pageUrl, index) => (
                  <img key={pageUrl} src={pageUrl} alt={`Page ${index + 1} de la facture`} className="ve-pdf-preview-page" />
                ))}
              </div>
            </section>
          </div>
        ) : null}
      </div>
  );
}











