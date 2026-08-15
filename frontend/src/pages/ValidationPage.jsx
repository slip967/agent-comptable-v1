import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,

  CheckCircle2,
  FileText,
  LoaderCircle,
  PanelRightOpen,
  RefreshCcw,
  Trash2,
  X,
} from "lucide-react";

import pcgClass6 from "../data/pcg_classe6.json";
import { useGlobalSearch } from "../context/SearchContext";
import { matchesGlobalSearch } from "../utils/search";

import {
  API_BASE_URL,
  deleteHumanValidationItem,
  fetchHumanValidationItems,
  fetchInvoicePdfPreview,
  submitHumanValidationDecision,
} from "../services/api";
import { formatAccount } from "../utils/accountLabels";
import { isSuccessfulOrMissingDeletion } from "../utils/apiErrors";
import { cleanDisplayData, cleanDisplayText } from "../utils/textCleaner";
import { addPersistentHiddenId, readPersistentHiddenIds } from "../utils/persistentHiddenItems";
import { persistValidatedInvoice, readRolledBackInvoices } from "../utils/validatedEntries";
import {
  formatDecisionStatus,
  formatEvidenceStatus,
  formatHumanReadableText,
  formatHumanValidationStatus,
  formatReferentialStatus,
  formatRiskStatus,
} from "../utils/uiText";

const VALIDATION_HIDDEN_ITEMS_KEY = "keymanage.validation.hidden-items.v1";
const PCG_CLASS_6_GROUPS = cleanDisplayData(pcgClass6.classes || []).map((group) => ({
  ...group,
  category: cleanDisplayText(group.category),
  accounts: (group.accounts || []).map((account) => ({
    ...account,
    label: cleanDisplayText(account.label),
  })),
}));

/*
 * The PCG data is loaded from pcg_classe6.json above. The normalized shape is
 * intentionally kept compatible with the existing combobox and accordion.
 */
/*
const PCG_CLASS_6_GROUPS = [
  {
    category: "60 · Achats",
    accounts: [
      { code: "601", label: "Achats stockés - Matières premières" },
      { code: "6011", label: "Achats stockés - Matières premières" },
      { code: "602", label: "Achats stockés - Autres approvisionnements" },
      { code: "607", label: "Achats de marchandises" },
    ],
  },
  {
    category: "61 · Services extérieurs",
    accounts: [
      { code: "611", label: "Sous-traitance générale" },
      { code: "612", label: "Redevances de crédit-bail" },
      { code: "613", label: "Locations" },
      { code: "615", label: "Entretien et réparations" },
      { code: "616", label: "Primes d'assurances" },
    ],
  },
  {
    category: "62 · Autres services extérieurs",
    accounts: [
      { code: "621", label: "Personnel extérieur à l'entreprise" },
      { code: "622", label: "Rémunérations d'intermédiaires et honoraires" },
      { code: "623", label: "Publicité, publications et relations publiques" },
      { code: "624", label: "Transports de biens et transports collectifs" },
      { code: "625", label: "Déplacements, missions et réceptions" },
      { code: "626", label: "Frais postaux et télécommunications" },
      { code: "627", label: "Services bancaires et assimilés" },
      { code: "628", label: "Divers" },
      { code: "6281", label: "Concours divers (cotisations)" },
    ],
  },
  {
    category: "63 · Impôts, taxes et versements assimilés",
    accounts: [
      { code: "631", label: "Impôts, taxes et versements assimilés sur rémunérations" },
      { code: "633", label: "Impôts, taxes et versements assimilés sur rémunérations" },
      { code: "635", label: "Autres impôts, taxes et versements assimilés" },
    ],
  },
  {
    category: "64 · Charges de personnel",
    accounts: [
      { code: "641", label: "Rémunérations du personnel" },
      { code: "645", label: "Charges de sécurité sociale et de prévoyance" },
      { code: "647", label: "Autres charges sociales" },
    ],
  },
  {
    category: "65 · Autres charges de gestion courante",
    accounts: [
      { code: "651", label: "Redevances pour concessions, brevets et licences" },
      { code: "654", label: "Pertes sur créances irrécouvrables" },
      { code: "658", label: "Charges diverses de gestion courante" },
    ],
  },
  {
    category: "66 · Charges financières",
    accounts: [
      { code: "661", label: "Charges d'intérêts" },
      { code: "665", label: "Escomptes accordés" },
      { code: "666", label: "Pertes de change" },
    ],
  },
  {
    category: "67 · Charges exceptionnelles",
    accounts: [
      { code: "671", label: "Charges exceptionnelles sur opérations de gestion" },
      { code: "675", label: "Valeurs comptables des éléments d'actif cédés" },
      { code: "678", label: "Autres charges exceptionnelles" },
    ],
  },
];
*/

function textOrFallback(value, fallback = "Non renseigné") {
  return cleanDisplayText(value, fallback);
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0%";
  }
  return `${Math.round(Number(value) * 10) / 10}%`;
}

function formatAmount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Non renseigné";
  }
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function averageConfidenceForItem(item) {
  const invoiceAverage = Number(item?.invoice_average_confidence);
  if (Number.isFinite(invoiceAverage) && invoiceAverage > 0) {
    return invoiceAverage;
  }
  const confidence = Number(item?.confidence);
  return Number.isFinite(confidence) ? confidence : 0;
}

function validationGateForItem(item) {
  const average = averageConfidenceForItem(item);
  const backendCanValidate = item?.can_validate_accounting !== false;
  const backendDecision = String(item?.invoice_global_decision || "").toLowerCase();
  const rejected = average < 50 || backendDecision.includes("rejet");
  return {
    average,
    canValidateAccounting: backendCanValidate && !rejected,
    globalDecision: rejected ? "Rejetée" : "À valider",
    globalRisk: rejected ? "Élevé" : "Moyen",
  };
}

function statusLabel(status) {
  return formatHumanValidationStatus(status);
}

function decisionLabel(decision) {
  return formatDecisionStatus(decision);
}

function referentialLabel(status) {
  return formatReferentialStatus(status);
}

function evidenceLabel(status) {
  return formatEvidenceStatus(status);
}

function statusClass(status) {
  if (status === "validated") return "status-pill ready";
  if (status === "corrected" || status === "enrichment_proposed") return "status-pill info";
  if (status === "non_comptable") return "status-pill neutral";
  if (status === "rejected") return "status-pill danger";
  return "status-pill review";
}

function metricValue(counts, key) {
  return Number(counts?.[key] || 0);
}

function fileNameFromPath(path) {
  return String(path || "").split(/[\\/]/).filter(Boolean).pop() || "Document PDF";
}

function isTestValidationItem(item) {
  const rawText = String(item?.raw_text || item?.cleaned_text || "").trim().toUpperCase();
  return rawText === "TEST VALIDATION";
}

function isAutoRoutedItem(item) {
  const status = String(
    item?.workflow_status || item?.invoice_status || item?.status || ""
  ).trim().toUpperCase();

  return ["VALIDE_AUTO", "VALIDE", "COMPTABILISEE", "COMPTABILIS?E"].includes(status);
}

function isPdfOpenableFromDebug(debug) {
  if (!debug || typeof debug !== "object") return false;
  if (debug.exists_on_disk) return true;
  if (String(debug.resolved_kind || "").trim().toLowerCase() === "couch_attachment") return true;
  const related = debug.related_doc_success && typeof debug.related_doc_success === "object"
    ? debug.related_doc_success
    : null;
  return Boolean(related && (related.used_attachment || related.exists_on_disk || related.resolved_kind));
}


function getPdfInvoiceId(item) {
  const lines = Array.isArray(item?.lines) ? item.lines : [];
  const candidates = [
    item?.invoice_id,
    item?.source_invoice_id,
    item?.doc_id,
    item?.invoice_group_id,
    ...lines.flatMap((line) => [line?.invoice_id, line?.source_invoice_id, line?.doc_id]),
  ];
  return String(candidates.find((candidate) => String(candidate || "").trim()) || "").trim();
}
function getValidationId(item) {
  return String(item?.validation_id || item?.id || item?._id || item?.line_id || "").trim();
}

function getInvoiceKey(item) {
  return String(
    item?.invoice_id ||
      item?.invoice_number ||
      item?.source_invoice_id ||
      item?.doc_id ||
      item?.validation_id ||
      "",
  ).trim();
}

function uniqueValues(values) {
  return Array.from(
    new Set(
      values
        .flat()
        .map((value) => String(value || "").trim())
        .filter(Boolean),
    ),
  );
}

function invoiceLineCount(item) {
  const explicit = Number(item?.invoice_line_count ?? item?.line_count ?? item?.lines_count);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  if (Array.isArray(item?.lines) && item.lines.length) return item.lines.length;
  return 1;
}

function groupRiskLevel(lines) {
  const priority = { "Élevé": 3, "eleve": 3, "moyen": 2, "faible": 1 };
  return lines.reduce((current, line) => {
    const risk = String(line?.risk_level || "").toLowerCase();
    const currentScore = priority[String(current || "").toLowerCase()] || 0;
    return (priority[risk] || 0) > currentScore ? line.risk_level : current;
  }, lines[0]?.risk_level || "moyen");
}

function groupEvidenceStatus(lines) {
  const priority = { complete: 3, partial: 2, missing: 1 };
  return lines.reduce((current, line) => {
    const evidence = String(line?.evidence_status || "missing").toLowerCase();
    const currentScore = priority[String(current || "").toLowerCase()] || 0;
    return (priority[evidence] || 0) > currentScore ? line.evidence_status : current;
  }, "missing");
}

function groupValidationItemsByInvoice(items) {
  const groups = new Map();

  items.forEach((item, index) => {
    const key = getInvoiceKey(item) || `validation-${index}`;
    if (!groups.has(key)) {
      groups.set(key, {
        ...item,
        validation_id: key,
        invoice_group_id: key,
        lines: [],
      });
    }
    groups.get(key).lines.push(item);
  });

  return Array.from(groups.values()).map((group) => {
    const lines = group.lines;
    const primary = lines[0] || group;
    const confidenceValues = lines
      .map((line) => Number(line?.confidence))
      .filter((value) => Number.isFinite(value));
    const averageConfidence = confidenceValues.length
      ? confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length
      : averageConfidenceForItem(primary);
    const count = Math.max(invoiceLineCount(primary), lines.length);

    return {
      ...primary,
      validation_id: group.invoice_group_id,
      invoice_group_id: group.invoice_group_id,
      status: primary.status || "pending_validation",
      raw_text: primary.supplier || primary.invoice_number || primary.raw_text,
      invoice_average_confidence: averageConfidence,
      confidence: averageConfidence,
      risk_level: groupRiskLevel(lines),
      evidence_status: groupEvidenceStatus(lines),
      invoice_line_count: count,
      line_count: count,
      source_invoice_ids: uniqueValues(lines.flatMap((line) => line?.source_invoice_ids || [])),
      invoice_paths_sources: uniqueValues(lines.flatMap((line) => line?.invoice_paths_sources || [])),
      lines,
    };
  });
}

function countValidationInvoices(items) {
  return groupValidationItemsByInvoice(items).reduce((acc, invoice) => {
    const status = String(invoice?.status || "pending_validation");
    acc[status] = Number(acc[status] || 0) + 1;
    return acc;
  }, {});
}

export default function ValidationPage() {
  const { searchQuery, clearSearch } = useGlobalSearch();
  const [items, setItems] = useState([]);
  const [activeValidationFilter, setActiveValidationFilter] = useState("pending_validation");
  const [counts, setCounts] = useState({});
  const [selectedItem, setSelectedItem] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [pdfViewerPages, setPdfViewerPages] = useState([]);
  const [pdfViewerLabel, setPdfViewerLabel] = useState("");
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [pdfLoadingId, setPdfLoadingId] = useState("");
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [pcgOpen, setPcgOpen] = useState(false);
  const [accountQuery, setAccountQuery] = useState("");
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [correctionDraft, setCorrectionDraft] = useState({
    corrected_account: "",
    corrected_account_label: "",
    comment: "",
  });
  const [selectedLineIndex, setSelectedLineIndex] = useState(0);

  const selectedLines = Array.isArray(selectedItem?.lines) && selectedItem.lines.length
    ? selectedItem.lines
    : selectedItem
      ? [selectedItem]
      : [];
  const selectedPrimaryLine = selectedLines[selectedLineIndex] || selectedLines[0] || selectedItem || {};
  const isManualLineAnalysis = Boolean(
    selectedItem?.manual === true ||
    selectedItem?.manual_line_analysis ||
      selectedItem?.manualLineAnalysis ||
      selectedItem?.analysis_mode === "manual_line" ||
      selectedItem?.analysisMode === "manual_line" ||
      selectedItem?.line_analysis_mode === "manual",
  );
  const selectedValidationGate = selectedItem ? validationGateForItem(selectedItem) : null;
  const selectedCandidates = Array.isArray(selectedPrimaryLine?.top_candidates)
    ? selectedPrimaryLine.top_candidates
    : [];

  const pcgSuggestions = useMemo(() => {
    const query = String(accountQuery || "").trim().toLowerCase();
    if (!query) return [];
    return PCG_CLASS_6_GROUPS.flatMap((group) =>
      group.accounts.map((account) => ({ ...account, category: group.category })),
    )
      .filter((account) =>
        [account.code, account.label, account.category].some((value) =>
          String(value || "").toLowerCase().includes(query),
        ),
      )
      .slice(0, 8);
  }, [accountQuery]);

  const applyPcgAccount = (account) => {
    if (!account) return;
    setAccountQuery(account.code);
    setCorrectionDraft((current) => ({
      ...current,
      corrected_account: account.code,
      corrected_account_label: account.label,
    }));
    setSelectedItem((current) => {
      if (!current) return current;
      const lines = Array.isArray(current.lines) ? current.lines : [];
      return {
        ...current,
        lines: lines.map((line, index) =>
          index === selectedLineIndex
            ? {
                ...line,
                recommended_account: account.code,
                account_label: account.label,
                recommended_account_label: account.label,
                corrected_account: account.code,
                corrected_account_label: account.label,
              }
            : line,
        ),
      };
    });
  };
  const kpis = useMemo(
    () => [
      { key: "pending_validation", label: "À valider", value: metricValue(counts, "pending_validation"), tone: "pending" },
      { key: "validated", label: "Validées", value: metricValue(counts, "validated"), tone: "validated" },
      { key: "corrected", label: "Corrigées", value: metricValue(counts, "corrected"), tone: "corrected" },
      { key: "non_comptable", label: "Non comptables", value: metricValue(counts, "non_comptable"), tone: "neutral" },
      { key: "rejected", label: "Rejetées", value: metricValue(counts, "rejected"), tone: "rejected" },
    ],
    [counts],
  );

  const groupedInvoices = useMemo(() => groupValidationItemsByInvoice(items), [items]);

  const filteredItems = useMemo(
    () => groupedInvoices
      .filter((item) => String(item?.status || "pending_validation") === activeValidationFilter)
      .filter((item) => matchesGlobalSearch(item, searchQuery)),
    [activeValidationFilter, groupedInvoices, searchQuery],
  );

  const rollbackInvoiceToValidationItems = (invoice = {}) => {
    const sourceLines = Array.isArray(invoice.lines) && invoice.lines.length ? invoice.lines : [invoice];
    const invoiceKey = getInvoiceKey(invoice) || String(invoice.invoice_group_id || "").trim();
    return sourceLines.map((line, index) => {
      const lineId = String(
        line?.validation_id ||
          line?.id ||
          line?._id ||
          line?.line_id ||
          `${invoiceKey}:rollback:${index}`,
      ).trim();
      return {
        ...invoice,
        ...line,
        id: lineId,
        validation_id: line?.validation_id || lineId,
        invoice_id: line?.invoice_id || invoice.invoice_id || invoice.invoice_group_id,
        invoice_group_id: invoice.invoice_group_id || invoice.invoice_id || invoiceKey,
        invoice_number: line?.invoice_number || invoice.invoice_number,
        supplier: line?.supplier || invoice.supplier,
        client: line?.client || invoice.client,
        status: "A_VALIDER",
        workflow_status: "A_VALIDER",
        accounting_status: "A_VALIDER",
      };
    });
  };
  const loadItems = async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const payload = await fetchHumanValidationItems({ limit: 1000 });
      const hiddenIds = new Set(readPersistentHiddenIds(VALIDATION_HIDDEN_ITEMS_KEY));
      const cleanedItems = cleanDisplayData(Array.isArray(payload?.items) ? payload.items : []);
      const loadedItems = Array.isArray(cleanedItems)
        ? cleanedItems.filter((item) => !isTestValidationItem(item) && !isAutoRoutedItem(item))
        : [];
      const nextItems = loadedItems.filter((item) =>
        !hiddenIds.has(getValidationId(item)),
      );
      setItems(nextItems);
      setCounts(countValidationInvoices(nextItems));
    } catch (error) {
      setErrorMessage(
        cleanDisplayText(error?.message) ||
          "Impossible de charger la file de validation humaine.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);


  useEffect(() => {
    const resetAfterSessionClear = () => {
      setItems([]);
      setCounts({});
      setSelectedItem(null);
      setSelectedLineIndex(0);
      setErrorMessage("");
      setSuccessMessage("");
      try {
        window.localStorage.removeItem(VALIDATION_HIDDEN_ITEMS_KEY);
      } catch {
        // Keep the UI reset available in restricted browser contexts.
      }
    };
    window.addEventListener("keymanage:all-saved-invoices-purged", resetAfterSessionClear);
    window.addEventListener("keymanage:test-session-reset", resetAfterSessionClear);
    return () => {
      window.removeEventListener("keymanage:all-saved-invoices-purged", resetAfterSessionClear);
      window.removeEventListener("keymanage:test-session-reset", resetAfterSessionClear);
    };
  }, []);
  const submitDecision = async (action, extraPayload = {}) => {
    const targetLines = action === "correct_account" ? [selectedPrimaryLine] : selectedLines;
    const ids = targetLines.map(getValidationId).filter(Boolean);
    if (!ids.length) return;

    setErrorMessage("");
    setSuccessMessage("");
    try {
      const results = await Promise.all(
        ids.map((validationId) =>
          submitHumanValidationDecision(validationId, {
            action,
            validated_by: "human_user",
            ...extraPayload,
          }),
        ),
      );
      const firstPayload = results[0] || {};
      const updatedStatus = firstPayload?.status || firstPayload?.item?.status;
      const targetIds = new Set(ids);
      const updatedLines = selectedLines.map((line) => {
        if (!targetIds.has(getValidationId(line))) return line;
        return {
          ...line,
          status: action === "validate" ? "COMPTABILISEE" : updatedStatus || line.status,
          workflow_status: action === "validate" ? "COMPTABILISEE" : line.workflow_status,
          accounting_status: action === "validate" ? "COMPTABILISEE" : line.accounting_status,
          human_validation_result: firstPayload?.human_validation_result || line.human_validation_result,
          ...(action === "correct_account"
            ? {
                recommended_account: extraPayload.corrected_account || line.recommended_account,
                account_label: extraPayload.corrected_account_label || line.account_label,
              }
            : {}),
        };
      });

      if (action === "validate") {
        persistValidatedInvoice(
          { ...selectedItem, status: "COMPTABILISEE", workflow_status: "COMPTABILISEE" },
          updatedLines,
          firstPayload,
        );
        ids.forEach((validationId) => addPersistentHiddenId(VALIDATION_HIDDEN_ITEMS_KEY, validationId));
      }

      setSelectedItem((current) =>
        current
          ? {
              ...current,
              status: updatedStatus || current.status,
              human_validation_result: firstPayload?.human_validation_result || current.human_validation_result,
              lines: updatedLines,
            }
          : current,
      );
      setCorrectionOpen(false);
      setCorrectionDraft({
        corrected_account: "",
        corrected_account_label: "",
        comment: "",
      });
      setSuccessMessage("Décision humaine enregistrée pour " + ids.length + " ligne" + (ids.length > 1 ? "s" : "") + ".");
      await loadItems();
      if (action === "validate") {
        setSelectedItem(null);
        setSelectedLineIndex(0);
      }
    } catch (error) {
      setErrorMessage(
        cleanDisplayText(error?.message) ||
          "Impossible d’enregistrer la décision humaine.",
      );
    }
  };

  const openPdf = async (item) => {
    const invoiceId = getPdfInvoiceId(item);
    if (!invoiceId) return;

    setErrorMessage("");
    setPdfLoadingId(item.validation_id || invoiceId);
    try {
      const preview = await fetchInvoicePdfPreview(invoiceId);
      const pageCount = Math.max(0, Number(preview?.page_count || 0));
      if (!pageCount) {
        throw new Error("Document source non disponible pour cette facture.");
      }
      const previewBase = `${API_BASE_URL}/api/analysis/invoice-pdf-preview/${encodeURIComponent(invoiceId)}/pages`;
      setPdfViewerPages(Array.from({ length: pageCount }, (_, index) => `${previewBase}/${index + 1}`));
      setPdfViewerLabel(item.invoice_number || item.supplier || "Document source");
      setShowPdfViewer(true);
    } catch (error) {
      setErrorMessage(
        cleanDisplayText(error?.message) ||
          "Document source non disponible pour cette facture.",
      );
    } finally {
      setPdfLoadingId("");
    }
  };

  const closePdfViewer = () => {
    setShowPdfViewer(false);
    setPdfViewerPages([]);
  };

  const handleDeleteItem = async (item) => {
    const ids = (Array.isArray(item?.lines) && item.lines.length ? item.lines : [item])
      .map(getValidationId)
      .filter(Boolean);
    if (!ids.length) return;
    const confirmed = window.confirm("Voulez-vous supprimer définitivement cette facture de validation ?");
    if (!confirmed) return;
    setErrorMessage("");
    try {
      const results = await Promise.allSettled(
        ids.map((validationId) => deleteHumanValidationItem(validationId)),
      );
      const removableIds = ids.filter((_, index) => isSuccessfulOrMissingDeletion(results[index]));
      const hardFailure = results.find((result) => !isSuccessfulOrMissingDeletion(result));
      removableIds.forEach((validationId) => addPersistentHiddenId(VALIDATION_HIDDEN_ITEMS_KEY, validationId));
      setItems((current) => {
        const hidden = new Set(removableIds);
        const nextItems = current.filter((entry) => !hidden.has(getValidationId(entry)));
        setCounts(countValidationInvoices(nextItems));
        return nextItems;
      });
      if (!hardFailure && selectedItem?.invoice_group_id === item.invoice_group_id) setSelectedItem(null);
      if (hardFailure) {
        setErrorMessage(cleanDisplayText(hardFailure.reason?.message, "Certaines lignes n’ont pas pu être supprimées."));
      }
    } catch (error) {
      setErrorMessage(cleanDisplayText(error?.message, "Impossible de supprimer cette facture de validation."));
    }
  };

  const handlePurgeAll = async () => {
    setConfirmPurge(false);
    const allIds = items.map(getValidationId).filter(Boolean);
    setErrorMessage("");
    const results = await Promise.allSettled(
      allIds.map((validationId) => deleteHumanValidationItem(validationId)),
    );
    const removableIds = allIds.filter((_, index) => isSuccessfulOrMissingDeletion(results[index]));
    const removableSet = new Set(removableIds);
    removableIds.forEach((validationId) => addPersistentHiddenId(VALIDATION_HIDDEN_ITEMS_KEY, validationId));
    setItems((current) => {
      const nextItems = current.filter((entry) => !removableSet.has(getValidationId(entry)));
      setCounts(countValidationInvoices(nextItems));
      return nextItems;
    });
    if (selectedItem && removableSet.has(getValidationId(selectedItem))) setSelectedItem(null);
    const hardFailure = results.find((result) => !isSuccessfulOrMissingDeletion(result));
    if (hardFailure) {
      setErrorMessage(cleanDisplayText(hardFailure.reason?.message, "Certaines lignes n’ont pas pu être supprimées."));
    }
  };

  const openValidationItem = (item) => {
    setSelectedItem(item);
    setSelectedLineIndex(0);
    setCorrectionOpen(false);
    setPcgOpen(false);
    setAccountQuery("");
    setSuccessMessage("");
  };

  return (
    <div className="page-stack validation-page">
      <section className="page-heading-compact" hidden aria-hidden="true">
        <h1 className="section-title">Validation humaine</h1>

        <p className="section-text">
          Contrôlez les lignes incertaines détectées par le moteur avant toute
          automatisation comptable.
        </p>
      </section>

      {showPdfViewer && pdfViewerPages.length ? (
        <section className="validation-pdf-viewer">
          <div className="validation-pdf-viewer-head">
            <div>
              <span className="validation-eyebrow">Document source</span>
              <h2>{textOrFallback(pdfViewerLabel, "Aperçu de la facture")}</h2>
            </div>
            <div className="validation-pdf-viewer-actions">
              <button type="button" className="validation-secondary-action" onClick={closePdfViewer}>
                <X size={15} /> Fermer
              </button>
            </div>
          </div>
          <div className="validation-pdf-viewer-pages">{pdfViewerPages.map((pageUrl, index) => <img key={pageUrl} src={pageUrl} alt={`Page ${index + 1} de la facture`} className="validation-pdf-viewer-page" />)}</div>
        </section>
      ) : null}

      <section className="validation-learning-panel">
        <div className="validation-learning-head">
          <div>
            <span className="validation-eyebrow">Supervision experte</span>
            <h2>Boucle d’apprentissage contrôlée</h2>
          </div>
          <span className="validation-learning-badge">Contrôle humain actif</span>
        </div>
        <div className="validation-status-filters" role="tablist" aria-label="Filtrer les validations">
          {kpis.map((kpi) => (
            <button
              key={kpi.key}
              type="button"
              role="tab"
              aria-selected={activeValidationFilter === kpi.key}
              className={`validation-status-filter validation-status-filter--${kpi.tone}${activeValidationFilter === kpi.key ? " active" : ""}`}
              onClick={() => setActiveValidationFilter(kpi.key)}
            >
              <span className="validation-status-dot" aria-hidden="true" />
              <span className="validation-status-label">{kpi.label}</span>
              <span className="validation-status-count">{kpi.value}</span>
            </button>
          ))}

        </div>
      </section>

      {errorMessage ? <div className="analysis-inline-error">{errorMessage}</div> : null}
      {successMessage ? <div className="analysis-inline-success">{successMessage}</div> : null}

      <section className="validation-queue-panel">
        <div className="validation-queue-toolbar">
          {filteredItems.length ? (
            <div className="validation-queue-title-chip"><h2>Factures à valider</h2></div>
          ) : <span aria-hidden="true" />}
          <div style={{display:"flex",alignItems:"center",gap:8,flexWrap:"wrap"}}>
            <button type="button" className="validation-refresh-btn" onClick={loadItems} disabled={loading}>
              {loading ? <LoaderCircle size={14} className="spin" /> : <RefreshCcw size={14} />}
              Actualiser
            </button>
            {items.length > 0 && (
              confirmPurge ? (
                <>
                  <span style={{fontSize:"12px",fontWeight:700,color:"#dc2626",whiteSpace:"nowrap"}}>Purger toutes les entrées ?</span>
                  <button type="button" className="validation-refresh-btn" style={{background:"rgba(220,38,38,.1)",borderColor:"rgba(220,38,38,.3)",color:"#dc2626"}} onClick={handlePurgeAll}>Confirmer</button>
                  <button type="button" className="validation-refresh-btn" onClick={() => setConfirmPurge(false)}>Annuler</button>
                </>
              ) : (
                <button type="button" className="validation-refresh-btn" style={{color:"#dc2626",borderColor:"rgba(220,38,38,.25)"}} onClick={() => setConfirmPurge(true)}>
                  <Trash2 size={13} /> Tout purger
                </button>
              )
            )}
          </div>
        </div>
        {loading ? (
          <div className="analysis-table-empty"><LoaderCircle size={18} className="spin" /> Chargement de la file...</div>
        ) : filteredItems.length ? (
          <div className="records-stack validation-records-stack">
            {filteredItems.map((item) => {
              const lines = Array.isArray(item.lines) && item.lines.length ? item.lines : [item];
              const primaryLine = lines[0] || item;
              const lineCount = invoiceLineCount(item);
              const invoiceLabel = item.invoice_number || item.invoice_id || "sans référence";
              const invoiceTitle = textOrFallback(item.supplier, "Fournisseur non renseigné");

              return (
                <article key={item.invoice_group_id || item.validation_id} className={`validation-card validation-card--${item.status || "pending_validation"}`}>
                  <div className="record-header">
                    <div className="record-copy">
                      <div className="record-title-row">
                        <h2 className="record-title">{invoiceTitle}</h2>
                        <span className={statusClass(item.status)}>{statusLabel(item.status)}</span>
                      </div>
                      <p className="record-description validation-invoice-summary">
                        Facture {invoiceLabel} · {lineCount} ligne{lineCount > 1 ? "s" : ""} · Client {textOrFallback(item.client)}
                      </p>
                      <p className="record-description">
                        Ligne représentative : {textOrFallback(primaryLine.raw_text || primaryLine.cleaned_text)}
                      </p>
                      <div className="record-metrics validation-invoice-metrics">
                        <div className="metric-pill validation-account-metric">
                          <div className="metric-pill-label">Compte principal</div>
                          <div className="metric-pill-value">
                            {primaryLine.recommended_account ? formatAccount(primaryLine.recommended_account, primaryLine.account_label) : "Aucun"}
                          </div>
                        </div>
                        <div className="metric-pill"><div className="metric-pill-label">Lignes</div><div className="metric-pill-value">{lineCount}</div></div>
                        <div className="metric-pill"><div className="metric-pill-label">Score moyen</div><div className="metric-pill-value success">{formatPercent(item.confidence)}</div></div>
                        <div className="metric-pill"><div className="metric-pill-label">Risque</div><div className="metric-pill-value">{formatRiskStatus(item.risk_level)}</div></div>
                        <div className="metric-pill"><div className="metric-pill-label">Preuve</div><div className="metric-pill-value">{evidenceLabel(item.evidence_status)}</div></div>
                      </div>
                    </div>
                    <div className="button-row validation-card-actions">
                      {getPdfInvoiceId(item) ? (
                        <button type="button" className="validation-card-action" onClick={() => openPdf(item)} disabled={pdfLoadingId === (item.validation_id || item.invoice_id)}>
                          <FileText size={14} />
                          {pdfLoadingId === (item.validation_id || item.invoice_id) ? "Ouverture..." : "Voir PDF"}
                        </button>
                      ) : null}
                      <button type="button" className="validation-card-action" onClick={() => openValidationItem(item)}>
                        <PanelRightOpen size={14} /> Voir détail
                      </button>
                      <button type="button" className="validation-card-action validation-card-delete" onClick={() => handleDeleteItem(item)}>
                        <Trash2 size={14} /> Supprimer
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="validation-empty-state">
            <FileText size={20} />
            <strong>
              {searchQuery
                ? `Aucune facture ni analyse ne correspond à « ${searchQuery} ».`
                : "Aucune facture dans cette catégorie"}
            </strong>
            {searchQuery ? (
              <button type="button" className="validation-empty-reset" onClick={clearSearch}>
                Réinitialiser la recherche
              </button>
            ) : (
              <span>Les factures à contrôler apparaîtront ici après les premières analyses.</span>
            )}
          </div>
        )}
      </section>
      {selectedItem ? (
        <div
          className="ve-modal-backdrop"
          onClick={() => setSelectedItem(null)}
          role="dialog"
          aria-modal="true"
          aria-label="Détail validation"
        >
          <div className="ve-modal-panel" onClick={(event) => event.stopPropagation()}>
            <div className="ve-modal-head">
              <div>
                <h2 className="ve-modal-title">Détail validation</h2>
                <p className="ve-modal-subtitle">Décision moteur, preuves et correction humaine possible.</p>
              </div>
              <button
                type="button"
                className="ve-modal-close"
                onClick={() => setSelectedItem(null)}
                aria-label="Fermer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="ve-modal-body">
              <div className="detail-card validation-invoice-detail-card">
                <div className="detail-label">Facture</div>
                <div className="analysis-detail-grid">
                  <DetailRow label="Fournisseur" value={selectedItem.supplier} />
                  <DetailRow label="Client" value={selectedItem.client} />
                  <DetailRow label="Référence" value={selectedItem.invoice_number || selectedItem.invoice_id} />
                  <DetailRow label="Lignes à contrôler" value={selectedLines.length} />
                </div>
              </div>

              <div className="detail-card validation-lines-card">
                <div className="detail-label">Lignes facture ({selectedLines.length})</div>
                <div className="validation-lines-detail-list">
                  {selectedLines.map((line, index) => (
                    <button
                        type="button"
                        className={`validation-line-detail-row${selectedLineIndex === index ? " is-active" : ""}`}
                        key={getValidationId(line) || `${line.raw_text}-${index}`}
                        onClick={() => {
                          setSelectedLineIndex(index);
                          setAccountQuery(line.recommended_account || "");
                          setCorrectionDraft((current) => ({
                            ...current,
                            corrected_account: line.recommended_account || "",
                            corrected_account_label: line.account_label || "",
                          }));
                        }}
                      >
                      <span className="validation-line-index">{index + 1}</span>
                      <div>
                        <strong>{textOrFallback(line.raw_text || line.cleaned_text)}</strong>
                        <small>{line.recommended_account ? formatAccount(line.recommended_account, line.account_label) : "Compte non renseigné"}</small>
                      </div>
                      <span className={statusClass(line.status)}>{formatPercent(line.confidence)}</span>
                        {selectedLineIndex === index ? (
                          <small className="validation-line-editing">En cours d'édition</small>
                        ) : null}
                      </button>
                  ))}
                </div>
              </div>

              {isManualLineAnalysis ? (
              <div className="detail-card validation-representative-card">
                <div className="detail-label">Ligne représentative</div>
                  <DetailRow label="Texte brut" value={selectedPrimaryLine.raw_text} />
                  <DetailRow label="Texte nettoyé" value={selectedPrimaryLine.cleaned_text} />
                  <DetailRow label="Montant HT" value={formatAmount(selectedPrimaryLine.amount_ht)} />
                  <DetailRow label="Montant TTC" value={formatAmount(selectedPrimaryLine.amount_ttc)} />
                  <DetailRow label="TVA" value={formatPercent(selectedPrimaryLine.tva)} />
                </div>
              ) : null}

              <div className="detail-card validation-decision-card">
                <div className="detail-label">Décision moteur</div>
                <div className="analysis-detail-grid">
                  <DetailRow
                    label="Compte proposé"
                    value={formatAccount(selectedPrimaryLine.recommended_account, selectedPrimaryLine.account_label)}
                    highlight
                  />
                  <DetailRow label="Score" value={formatPercent(selectedPrimaryLine.confidence)} />
                  <DetailRow label="Risque" value={formatRiskStatus(selectedPrimaryLine.risk_level)} />
                  <DetailRow
                    label="Statut référentiel"
                    value={referentialLabel(selectedPrimaryLine.referential_status)}
                  />
                  <DetailRow label="Décision moteur" value={decisionLabel(selectedPrimaryLine.decision)} />
                  <DetailRow label="Preuves" value={evidenceLabel(selectedPrimaryLine.evidence_status)} />
                </div>
                <p className="detail-text">
                  {formatHumanReadableText(selectedPrimaryLine.decision_reason, "Non renseigné")}
                </p>
              </div>

              <div className="detail-card validation-candidates-card">
                <div className="detail-label">Top candidats</div>
                <div className="analysis-candidate-list">
                  {selectedCandidates.length ? (
                    selectedCandidates.map((candidate, index) => (
                      <article key={`${candidate.account}-${index}`} className="analysis-candidate-item">
                        <div className="analysis-candidate-rank">#{index + 1}</div>
                        <div>
                          <div className="analysis-candidate-title">
                            {formatAccount(candidate.account, candidate.account_label)}
                          </div>
                          <div className="analysis-candidate-meta">
                            {textOrFallback(candidate.article_source)} · Base {textOrFallback(candidate.base)} · {formatPercent(candidate.score)}
                          </div>
                          <p className="analysis-candidate-reason">
                            {formatHumanReadableText(candidate.reason, "Non renseigné")}
                          </p>
                        </div>
                      </article>
                    ))
                  ) : (
                    <span className="analysis-token muted">Aucun candidat transmis.</span>
                  )}
                </div>
              </div>

              <div className="detail-card validation-actions-card">
                <div className="detail-label">Actions humaines</div>
                <div className="button-row validation-edit-actions">
                  {selectedValidationGate?.canValidateAccounting ? (
                    <button
                      type="button"
                      className="success-btn validation-action-btn"
                      onClick={() => submitDecision("validate")}
                    >
                      <CheckCircle2 size={15} />
                      Valider l'écriture comptable
                    </button>
                  ) : (
                    <div className="validation-safety-lock">
                      Validation comptable désactivée : score moyen inférieur à 50 %. Corrigez ou complétez les comptes/montants avant validation.
                    </div>
                  )}
                  <button
                    type="button"
                    className="secondary-btn validation-action-btn"
                    onClick={() => { setCorrectionOpen((current) => !current); setPcgOpen(false); }}
                  >
                    Corriger le compte
                  </button>
                  <button
                    type="button"
                    className="secondary-btn validation-action-btn"
                    onClick={() => submitDecision("mark_non_comptable")}
                  >
                    Marquer non comptable
                  </button>
                  <button
                    type="button"
                    className="secondary-btn validation-action-btn"
                    onClick={() => submitDecision("reject")}
                  >
                    Rejeter
                  </button>
                </div>

                {correctionOpen ? (
                  <div className="validation-edit-panel">
                    <div className="validation-edit-grid">
                                            <label className="validation-edit-field">
                        <span className="validation-edit-label">Compte corrigé</span>
                        <div className="validation-combobox">
                          <input
                            className="page-input validation-edit-input"
                            role="combobox"
                            aria-expanded={pcgSuggestions.length > 0}
                            value={correctionDraft.corrected_account}
                            onChange={(event) => {
                              const value = event.target.value;
                              setAccountQuery(value);
                              setCorrectionDraft((current) => ({
                                ...current,
                                corrected_account: value,
                              }));
                            }}
                            placeholder="6011 ou matières premières"
                            autoComplete="off"
                          />
                          {pcgSuggestions.length ? (
                            <div className="validation-combobox-menu" role="listbox">
                              {pcgSuggestions.map((account) => (
                                <button
                                  key={`${account.code}-${account.label}`}
                                  type="button"
                                  className="validation-combobox-option"
                                  role="option"
                                  onMouseDown={(event) => event.preventDefault()}
                                  onClick={() => applyPcgAccount(account)}
                                >
                                  <span className="validation-combobox-option-copy">
                                    <strong>{account.code}</strong>
                                    <small>{account.label}</small>
                                  </span>
                                  <small>{account.category}</small>
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </label>
                      <label className="validation-edit-field">
                        <span className="validation-edit-label">Libellé corrigé</span>
                        <input
                          className="page-input validation-edit-input"
                          value={correctionDraft.corrected_account_label}
                          onChange={(event) =>
                            setCorrectionDraft((current) => ({
                              ...current,
                              corrected_account_label: event.target.value,
                            }))
                          }
                          placeholder="Ex: Matières premières"
                        />
                      </label>
                      <label className="validation-edit-field">
                        <span className="validation-edit-label">Commentaire</span>
                        <textarea
                          className="page-input page-textarea validation-edit-input"
                          rows={3}
                          value={correctionDraft.comment}
                          onChange={(event) =>
                            setCorrectionDraft((current) => ({
                              ...current,
                              comment: event.target.value,
                            }))
                          }
                          placeholder="Explique la correction."
                        />
                      </label>
                    </div>                    <button
                      type="button"
                      className="validation-pcg-toggle"
                      onClick={() => setPcgOpen((current) => !current)}
                      aria-expanded={pcgOpen}
                    >
                      <BookOpen size={15} />
                      <span>Consulter le PCG Classe 6</span>
                      <span className="validation-pcg-toggle-mark">{pcgOpen ? "−" : "+"}</span>
                    </button>
                    {pcgOpen ? (
                      <div className="validation-pcg-guide">
                        {PCG_CLASS_6_GROUPS.map((group) => (
                          <section className="validation-pcg-group" key={group.category}>
                            <h4>{group.category}</h4>
                            <div className="validation-pcg-account-list">
                              {group.accounts.map((account) => (
                                <button
                                  type="button"
                                  className="validation-pcg-account"
                                  key={`${group.category}-${account.code}`}
                                  onClick={() => applyPcgAccount(account)}
                                >
                                  <span className="validation-pcg-code">{account.code}</span>
                                  <span>{account.label}</span>
                                </button>
                              ))}
                            </div>
                          </section>
                        ))}
                      </div>
                    ) : null}
                    <button
                      type="button"
                      className="success-btn"
                      onClick={() => submitDecision("correct_account", correctionDraft)}
                    >
                      Enregistrer la correction
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function DetailRow({ label, value, highlight = false }) {
  return (
    <div className={`detail-row${highlight ? " highlight" : ""}`}>
      <span>{label}</span>
      <strong>{textOrFallback(value)}</strong>
    </div>
  );
}











