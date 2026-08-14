import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  fetchAnalysisBatchJob,
  fetchAnalysisBatchResults,
  fetchInvoicePdfDebug,
  getAnalysisBatchStreamUrl,
  resumeAnalysisBatchJob,
  saveAnalysisBatchJob,
  startAnalysisBatch,
  stopAnalysisBatchJob,
  purgeSavedInvoicesPermanently as purgeSavedInvoicesApi,
} from "../services/api";
import { formatHumanReadableText } from "../utils/uiText";
import { persistValidatedInvoice } from "../utils/validatedEntries";

const AnalysisBatchContext = createContext(null);

function getInvoiceId(invoice) {
  return invoice?.invoice_id || invoice?.id || invoice?._id || invoice?.doc_id || null;
}

function canOpenPdf(invoice) {
  return invoice?.pdf_status === "available";
}

function isPdfOpenableFromDebug(debug) {
  if (!debug || typeof debug !== "object") return false;
  if (debug.exists_on_disk) return true;
  if (String(debug.resolved_kind || "").trim().toLowerCase() === "couch_attachment") return true;
  const related = debug.related_doc_success && typeof debug.related_doc_success === "object"
    ? debug.related_doc_success
    : null;
  return !!(
    related &&
    (related.used_attachment || related.exists_on_disk || related.resolved_kind)
  );
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
      if (canOpenPdf(item)) return item;
      const invoiceId = getInvoiceId(item);
      if (!invoiceId) return item;
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
        // keep current status
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
    if (item.queue_status === "to_control" || item.queue_status === "new_articles") counts.to_control += 1;
    if (item.queue_status === "new_articles") counts.new_articles += 1;
    if (item.queue_status === "low_risk") counts.low_risk += 1;
    if (item.queue_status === "not_analyzed") counts.not_analyzed += 1;
    if (item.queue_status === "no_lines" || item.queue_status === "analysis_failed") counts.high_risk += 1;
  });

  return counts;
}

function formatDurationLabel(ms) {
  const value = Number(ms || 0);
  if (!value || Number.isNaN(value)) return null;
  if (value < 1000) return `${value} ms`;
  return `${Math.round(value / 10) / 100} s`;
}

function mapBatchResultToQueueItem(result) {
  const pdfStatus = normalizePdfStatus(result?.pdf_status);
  const analysisPayload =
    result?.analysis_payload && typeof result.analysis_payload === "object"
      ? result.analysis_payload
      : null;
  const summary = result?.status === "failed"
    ? null
    : {
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
  const badges = [];

  if (failed) {
    badges.push("Analyse échouée");
    if (String(result?.error_message || "").trim()) {
      badges.push(formatHumanReadableText(String(result.error_message).trim(), ""));
    }
  } else {
    badges.push(`${totalLines} ${totalLines > 1 ? "lignes" : "ligne"}`);
    badges.push(`${Number(result?.auto_ok || 0)} auto-validée${Number(result?.auto_ok || 0) > 1 ? "s" : ""}`);
    badges.push(`${Number(result?.validation_humaine || 0)} à valider`);
    badges.push(`${Number(result?.rejeter || 0)} rejetée${Number(result?.rejeter || 0) > 1 ? "s" : ""}`);
  }

  if (analysisDuration) badges.push(analysisDuration);

  const queueStatus = failed
    ? "analysis_failed"
    : totalLines <= 0
      ? "no_lines"
      : Number(result?.validation_humaine || 0) > 0 || Number(result?.rejeter || 0) > 0
        ? "to_control"
        : Number(result?.auto_ok || 0) > 0
          ? "low_risk"
          : "not_analyzed";

  return {
    id: result?.invoice_id,
    supplier: supplier || null,
    client: client || null,
    date: result?.invoice_date || null,
    invoice_number: invoiceNumber || null,
    line_count: totalLines || Number(result?.line_items_count || 0),
    exploitable_lines_count: totalLines || Number(result?.exploitable_lines_count || 0),
    client_ape: result?.client_ape || null,
    supplier_ape: result?.supplier_ape || null,
    queue_status: queueStatus,
    badges: badges.filter(Boolean),
    ready: !failed && totalLines > 0,
    preview: failed
      ? formatHumanReadableText(String(result?.error_message || "Erreur pendant l’analyse.").trim(), "")
      : `Lot ${String(result?.job_id || "").slice(-6)} · ${Number(result?.auto_ok || 0)} auto-validée${Number(result?.auto_ok || 0) > 1 ? "s" : ""} · ${Number(result?.validation_humaine || 0)} à valider`,
    batch_status: result?.status || "completed",
    workflow_status: result?.workflow_status || "",
    batch_job_id: result?.job_id || null,
    batch_duration_ms: Number(result?.duration_ms || 0),
    batch_summary: summary,
    pdf_status: pdfStatus,
    pdf_message: String(result?.pdf_message || "").trim() || null,
    analysis_result: analysisPayload,
  };
}

function mergeQueueItemsByInvoiceId(existing = [], incoming = []) {
  const byId = new Map();
  existing.forEach((item) => {
    const id = getInvoiceId(item);
    if (id) byId.set(id, item);
  });
  incoming.forEach((item) => {
    const id = getInvoiceId(item);
    if (!id) return;
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

export function AnalysisBatchProvider({ children }) {
  const [queueItems, setQueueItems] = useState([]);
  const [queueCounts, setQueueCounts] = useState(buildQueueCounts([]));
  const [invoiceAnalysisCache, setInvoiceAnalysisCache] = useState({});
  const [hasLoadedQueue, setHasLoadedQueue] = useState(false);
  const [queueReturnedEmpty, setQueueReturnedEmpty] = useState(false);
  const [loadingBatch, setLoadingBatch] = useState(false);
  const [batchJob, setBatchJob] = useState(null);
  const [batchJobError, setBatchJobError] = useState("");
  const [persistedBatchCount, setPersistedBatchCount] = useState(0);
  const [showingRecordedInvoices, setShowingRecordedInvoices] = useState(false);
  const [batchControlState, setBatchControlState] = useState("");
  const [batchRequestedLimit, setBatchRequestedLimit] = useState(50);
  const [batchActionMessage, setBatchActionMessage] = useState("");
  const [batchSuccessMessage, setBatchSuccessMessage] = useState("");
  const batchPollTimerRef = useRef(null);
  const batchStreamRef = useRef(null);
  const didAutoLoadBatchRef = useRef(false);

  const closeBatchStream = useCallback(() => {
    if (batchStreamRef.current) {
      batchStreamRef.current.close();
      batchStreamRef.current = null;
    }
  }, []);

  const clearBatchPollTimer = useCallback(() => {
    if (batchPollTimerRef.current) {
      clearTimeout(batchPollTimerRef.current);
      batchPollTimerRef.current = null;
    }
  }, []);

  const mergeQueueSnapshot = useCallback((items = []) => {
    if (!Array.isArray(items) || items.length === 0) return;
    setQueueItems((current) => {
      const nextItems = mergeQueueItemsByInvoiceId(current, items);
      setQueueCounts(buildQueueCounts(nextItems));
      setQueueReturnedEmpty(nextItems.length === 0);
      return nextItems;
    });
    setInvoiceAnalysisCache((current) => {
      const next = { ...current };
      items.forEach((item) => {
        const invoiceId = getInvoiceId(item);
        if (invoiceId && item.analysis_result) next[invoiceId] = item.analysis_result;
      });
      return next;
    });
  }, []);

  const persistLiveAutoValidatedResult = useCallback((result) => {
    const workflowStatus = String(result?.workflow_status || "").trim().toUpperCase();
    const payload = result?.analysis_payload;
    if (!payload || !["VALIDE_AUTO", "COMPTABILISEE", "COMPTABILISÉE"].includes(workflowStatus)) return;
    const invoice = payload.invoice || {};
    const lines = Array.isArray(payload.lines) ? payload.lines : [];
    const invoiceId = result?.invoice_id || invoice.invoice_id;
    if (!invoiceId || !lines.length) return;
    persistValidatedInvoice(
      {
        ...invoice,
        invoice_id: invoiceId,
        invoice_group_id: invoiceId,
        invoice_number: result?.invoice_number || invoice.invoice_number,
        supplier: result?.supplier || invoice.supplier,
        client: result?.client || invoice.client,
        status: "COMPTABILISEE",
        workflow_status: "COMPTABILISEE",
        accounting_status: "COMPTABILISEE",
      },
      lines,
      { human_validation_result: { action: "auto_validate", validated_by: "analysis_batch" } },
    );
  }, []);

  const ingestLiveBatchResult = useCallback((result, type = "INVOICE_PROCESSED") => {
    if (!result || typeof result !== "object") return;
    const mapped = mapBatchResultToQueueItem(result);
    mergeQueueSnapshot([mapped]);
    persistLiveAutoValidatedResult(result);
    window.dispatchEvent(new CustomEvent("keymanage:batch-invoice-processed", {
      detail: { type, result, item: mapped },
    }));
  }, [mergeQueueSnapshot, persistLiveAutoValidatedResult]);

  const openBatchStream = useCallback((jobId) => {
    if (!jobId || typeof window === "undefined" || typeof window.EventSource === "undefined") return;
    closeBatchStream();
    const source = new window.EventSource(getAnalysisBatchStreamUrl(jobId));
    const handlePayload = (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        if (payload.type === "BATCH_SNAPSHOT") {
          if (payload.job) setBatchJob(payload.job);
          (payload.results || []).forEach((result) => ingestLiveBatchResult(result, result.status === "failed" ? "INVOICE_ERROR" : "INVOICE_PROCESSED"));
          return;
        }
        if (payload.type === "INVOICE_PROCESSED" || payload.type === "INVOICE_ERROR") {
          ingestLiveBatchResult(payload.invoice, payload.type);
          setBatchJob((current) => current ? {
            ...current,
            processed: Number(payload.progress?.current ?? current.processed ?? 0),
            sampled_count: Number(payload.progress?.total ?? current.sampled_count ?? 0),
            success: Number(payload.progress?.success ?? current.success ?? 0),
            failed: Number(payload.progress?.failed ?? current.failed ?? 0),
          } : current);
          return;
        }
        if (payload.type === "BATCH_COMPLETED") {
          setBatchJob(payload.job || null);
          closeBatchStream();
        }
      } catch {
        // Ignore malformed keep-alive frames.
      }
    };
    source.addEventListener("BATCH_SNAPSHOT", handlePayload);
    source.addEventListener("INVOICE_PROCESSED", handlePayload);
    source.addEventListener("INVOICE_ERROR", handlePayload);
    source.addEventListener("BATCH_COMPLETED", handlePayload);
    source.onerror = () => {
      // Polling remains the fallback if an intermediary closes the SSE connection.
    };
    batchStreamRef.current = source;
  }, [closeBatchStream, ingestLiveBatchResult]);

  const hydrateBatchResults = useCallback(async (jobId, limit = 500, { merge = false } = {}) => {
    const payload = await fetchAnalysisBatchResults({ job_id: jobId, limit });
    const mappedItems = Array.isArray(payload?.items)
        ? await reconcileBatchPdfStatuses(payload.items.map(mapBatchResultToQueueItem))
        : [];
      const items = dedupeQueueItemsByInvoiceId(mappedItems);

    setQueueItems((current) => {
      const nextItems = merge ? mergeQueueItemsByInvoiceId(current, items) : items;
      setQueueCounts(buildQueueCounts(nextItems));
      setQueueReturnedEmpty(nextItems.length === 0);
      setPersistedBatchCount(nextItems.length);
      return nextItems;
    });

    if (items.length > 0) {
      setInvoiceAnalysisCache((current) => {
        const next = { ...current };
        items.forEach((item) => {
          const invoiceId = getInvoiceId(item);
          if (invoiceId && item.analysis_result) next[invoiceId] = item.analysis_result;
        });
        return next;
      });
    }

    return payload;
  }, []);

  const applyBatchJobPartialResults = useCallback((results = []) => {
    const mappedResults = dedupeQueueItemsByInvoiceId(
      Array.isArray(results) ? results.map(mapBatchResultToQueueItem) : [],
    );
    if (!mappedResults.length) return;
    mergeQueueSnapshot(mappedResults);
    reconcileBatchPdfStatuses(mappedResults)
      .then((reconciledItems) => mergeQueueSnapshot(reconciledItems))
      .catch(() => {});
  }, [mergeQueueSnapshot]);

  const pollBatchJobOnce = useCallback(async (jobId) => {
    if (!jobId) return;
    try {
      const payload = await fetchAnalysisBatchJob(jobId);
      const payloadLimit = Number(payload?.limit || 0);
      if (payloadLimit > 0) setBatchRequestedLimit(payloadLimit);
      setBatchJob(payload);
      if (Array.isArray(payload?.results) && payload.results.length > 0) {
        applyBatchJobPartialResults(payload.results);
      }
      if (["running", "queued", "stopping"].includes(String(payload?.status || ""))) {
        clearBatchPollTimer();
        batchPollTimerRef.current = setTimeout(() => {
          pollBatchJobOnce(jobId);
        }, 2500);
        return;
      }

      clearBatchPollTimer();
      setLoadingBatch(false);
      setBatchControlState("");
      if (payload?.status === "completed") {
        await hydrateBatchResults(jobId, Math.max(20, Number(payload?.limit || batchRequestedLimit || 50)), { merge: false });
        setBatchSuccessMessage(`Lot terminé: ${Number(payload?.processed || 0)} facture(s), ${Number(payload?.success || 0)} succès, ${Number(payload?.failed || 0)} échec(s).`);
        setBatchJobError("");
        setBatchActionMessage("");
      } else if (payload?.status === "stopped") {
        setBatchActionMessage(String(payload?.message || "Lot interrompu. Cliquez sur Continuer l'analyse pour reprendre.").trim());
        setBatchJobError("");
      } else if (payload?.status === "failed") {
        const msg = String(payload?.message || "Le lot d'analyse a échoué.").trim();
        if (/aucune nouvelle facture/i.test(msg)) {
          setBatchActionMessage("Aucune nouvelle facture à analyser. Toutes les factures disponibles ont déjà été traitées.");
        } else {
          setBatchJobError(msg);
        }
      }
    } catch (error) {
      clearBatchPollTimer();
      setLoadingBatch(false);
      setBatchControlState("");
      setBatchJobError(String(error?.message || "Impossible de suivre le lot d'analyse.").trim());
    }
  }, [applyBatchJobPartialResults, batchRequestedLimit, clearBatchPollTimer, hydrateBatchResults]);

  useEffect(() => () => { clearBatchPollTimer(); closeBatchStream(); }, [clearBatchPollTimer, closeBatchStream]);

  useEffect(() => {
    if (didAutoLoadBatchRef.current) return;
    didAutoLoadBatchRef.current = true;
    let cancelled = false;
    (async () => {
      try {
        const payload = await fetchAnalysisBatchResults({ limit: 500 });
        if (cancelled) return;
        const mappedItems = Array.isArray(payload?.items)
        ? await reconcileBatchPdfStatuses(payload.items.map(mapBatchResultToQueueItem))
        : [];
      const items = dedupeQueueItemsByInvoiceId(mappedItems);
        if (items.length > 0) {
          setQueueItems(items);
          setQueueCounts(buildQueueCounts(items));
          setHasLoadedQueue(true);
          setQueueReturnedEmpty(false);
          setPersistedBatchCount(items.length);
          setInvoiceAnalysisCache((current) => {
            const next = { ...current };
            items.forEach((item) => {
              const invoiceId = getInvoiceId(item);
              if (invoiceId && item.analysis_result) next[invoiceId] = item.analysis_result;
            });
            return next;
          });
        }
      } catch {
        // optional
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleLoadBatchAnalysis = useCallback(async (limit = 50) => {
    const requestedLimit = Math.max(1, Math.floor(Number(limit) || 50));
    setBatchRequestedLimit(requestedLimit);
    clearBatchPollTimer();
    setLoadingBatch(true);
    setBatchJobError("");
    setBatchSuccessMessage("");
    setBatchActionMessage(`Lancement du lot de ${requestedLimit} facture(s)...`);
    setHasLoadedQueue(true);
    setQueueReturnedEmpty(false);
    setQueueItems([]);
    setInvoiceAnalysisCache({});
    setQueueCounts(buildQueueCounts([]));

    try {
      const payload = await startAnalysisBatch(requestedLimit);
      setBatchJob(payload);
      openBatchStream(payload?.job_id);
      if (payload?.status === "already_running" || payload?.status === "running") {
        setBatchActionMessage(`Lot déjà lancé (${String(payload?.job_id || "").slice(-6)}). Suivi en cours...`);
        await pollBatchJobOnce(payload?.job_id);
        return;
      }
      setBatchActionMessage(`Lot lancé (${String(payload?.job_id || "").slice(-6)}). Analyse 0/${requestedLimit} en cours...`);
      await pollBatchJobOnce(payload?.job_id);
    } catch (error) {
      setBatchJobError(String(error?.message || "Impossible de lancer le lot d'analyse.").trim());
      setBatchActionMessage("");
      setLoadingBatch(false);
    }
  }, [clearBatchPollTimer, pollBatchJobOnce, openBatchStream]);

  const handleStopBatchAnalysis = useCallback(async () => {
    const jobId = String(batchJob?.job_id || "").trim();
    if (!jobId || !loadingBatch) return;
    try {
      setBatchJobError("");
      setBatchControlState("stopping");
      setBatchActionMessage("Demande d'arrêt envoyée. Le lot va s'arrêter après la facture en cours...");
      const payload = await stopAnalysisBatchJob(jobId);
      setBatchJob(payload);
      await pollBatchJobOnce(jobId);
    } catch (error) {
      setBatchControlState("");
      setBatchJobError(String(error?.message || "Impossible d'arreter le lot d'analyse.").trim());
    }
  }, [batchJob?.job_id, loadingBatch, pollBatchJobOnce]);

  const handleSaveBatchAnalysis = useCallback(async () => {
    const jobId = String(batchJob?.job_id || "").trim();
    if (!jobId || batchJob?.status !== "stopped") return;
    try {
      setBatchJobError("");
      setBatchControlState("saving");
      setBatchSuccessMessage("");
      setBatchActionMessage("Enregistrement des factures d?j? trait?es...");
      const payload = await saveAnalysisBatchJob(jobId);
      setBatchJob(payload);
      await hydrateBatchResults(jobId, Math.max(500, Number(payload?.saved_count || 0), Number(payload?.processed || 0), Number(payload?.limit || batchRequestedLimit || 50)), { merge: false });
      setBatchActionMessage(String(payload?.message || "Analyse partielle enregistr?e.").trim());
      setBatchSuccessMessage(`${Number(payload?.saved_count || 0)} facture(s) d?finitivement enregistr?e(s).`);
    } catch (error) {
      setBatchJobError(String(error?.message || "Impossible d'enregistrer l'analyse partielle.").trim());
    } finally {
      setBatchControlState("");
    }
  }, [batchJob?.job_id, batchJob?.status, batchRequestedLimit, hydrateBatchResults]);

  const handleResumeBatchAnalysis = useCallback(async () => {
    const jobId = String(batchJob?.job_id || "").trim();
    if (!jobId || batchJob?.status !== "stopped") return;
    try {
      setBatchJobError("");
      setBatchControlState("resuming");
      setBatchSuccessMessage("");
      setBatchActionMessage("Reprise du traitement des factures restantes...");
      setLoadingBatch(true);
      const payload = await resumeAnalysisBatchJob(jobId);
      setBatchJob(payload);
      await pollBatchJobOnce(jobId);
    } catch (error) {
      setLoadingBatch(false);
      setBatchControlState("");
      setBatchJobError(String(error?.message || "Impossible de reprendre le lot d'analyse.").trim());
    }
  }, [batchJob?.job_id, batchJob?.status, pollBatchJobOnce]);

  const handleShowAllRecordedInvoices = useCallback(async (options = {}) => {
    setShowingRecordedInvoices(true);
    setBatchJobError("");
    setBatchSuccessMessage("");
    setBatchActionMessage("");
    try {
      const payload = await fetchAnalysisBatchResults({ limit: 500 });
      const mappedItems = Array.isArray(payload?.items)
        ? await reconcileBatchPdfStatuses(payload.items.map(mapBatchResultToQueueItem))
        : [];
      const items = dedupeQueueItemsByInvoiceId(mappedItems);
      setQueueItems(items);
      setQueueCounts(buildQueueCounts(items));
      setHasLoadedQueue(true);
      setQueueReturnedEmpty(items.length === 0);
      setPersistedBatchCount(items.length);
      setInvoiceAnalysisCache((current) => {
        const next = { ...current };
        items.forEach((item) => {
          const invoiceId = getInvoiceId(item);
          if (invoiceId && item.analysis_result) next[invoiceId] = item.analysis_result;
        });
        return next;
      });
      setBatchActionMessage(items.length > 0 ? `${items.length} facture(s) enregistrée(s) affichée(s).` : "Aucune facture enregistrée pour le moment.");
    } catch (error) {
      setBatchJobError(String(error?.message || "Impossible d'afficher les factures enregistrées.").trim());
    } finally {
      setShowingRecordedInvoices(false);
    }
  }, []);

  const patchQueueItem = useCallback((invoiceId, patch) => {
    if (!invoiceId || !patch || typeof patch !== "object") return;
    setQueueItems((current) => {
      const nextItems = current.map((item) =>
        getInvoiceId(item) === invoiceId ? { ...item, ...patch } : item,
      );
      setQueueCounts(buildQueueCounts(nextItems));
      setQueueReturnedEmpty(nextItems.length === 0);
      return nextItems;
    });
  }, []);

  const cacheAnalysisResult = useCallback((invoiceId, payload) => {
    if (!invoiceId || !payload || typeof payload !== "object") return;
    setInvoiceAnalysisCache((current) => ({
      ...current,
      [invoiceId]: payload,
    }));
    setQueueItems((current) => {
      const nextItems = current.map((item) =>
        getInvoiceId(item) === invoiceId ? { ...item, analysis_result: payload } : item,
      );
      setQueueCounts(buildQueueCounts(nextItems));
      return nextItems;
    });
  }, []);

  const handleClearBatchResults = useCallback(() => {
    setBatchActionMessage("Liste locale masquée. Les factures enregistrées restent disponibles via Afficher toutes les factures enregistrées.");
    setBatchSuccessMessage("");
    setQueueItems([]);
    setQueueCounts(buildQueueCounts([]));
    setHasLoadedQueue(false);
    setQueueReturnedEmpty(false);
    setBatchJob(null);
    setBatchJobError("");
  }, []);


  const resetAllBatchState = useCallback((message = "") => {
    clearBatchPollTimer();
    closeBatchStream();
    setQueueItems([]);
    setQueueCounts(buildQueueCounts([]));
    setInvoiceAnalysisCache({});
    setPersistedBatchCount(0);
    setHasLoadedQueue(false);
    setQueueReturnedEmpty(false);
    setBatchJob(null);
    setBatchJobError("");
    setBatchActionMessage(message);
    setBatchSuccessMessage("");
    setShowingRecordedInvoices(false);
    setBatchControlState("");
    window.dispatchEvent(new Event("keymanage:local-analysis-reset"));
    window.dispatchEvent(new Event("keymanage:all-saved-invoices-purged"));
  }, [clearBatchPollTimer, closeBatchStream]);

  const handlePurgeSavedInvoices = useCallback(async () => {
    const payload = await purgeSavedInvoicesApi();
    resetAllBatchState();
    return payload;
  }, [resetAllBatchState]);  const value = useMemo(() => ({
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
    handlePurgeSavedInvoices,
    patchQueueItem,
    cacheAnalysisResult,
  }), [
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
    handlePurgeSavedInvoices,
    patchQueueItem,
    cacheAnalysisResult,
  ]);

  return <AnalysisBatchContext.Provider value={value}>{children}</AnalysisBatchContext.Provider>;
}

export function useAnalysisBatch() {
  const context = useContext(AnalysisBatchContext);
  if (!context) {
    throw new Error("useAnalysisBatch must be used inside AnalysisBatchProvider");
  }
  return context;
}

