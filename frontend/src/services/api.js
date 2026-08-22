export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function parseResponse(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? data.detail
        : "Erreur API inattendue.";
    const error = new Error(
      typeof detail === "string" ? detail : "Erreur API inattendue.",
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw error;
    }
    throw new Error(
      `Backend FastAPI inaccessible sur ${API_BASE_URL}. Verifie que le serveur tourne bien et que le port 8000 est ouvert.`,
    );
  }

  return parseResponse(response);
}

async function requestFormData(path, formData, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: formData,
      ...options,
    });
  } catch {
    throw new Error(
      `Impossible d'envoyer le fichier au backend FastAPI sur ${API_BASE_URL}. Lance d'abord l'API locale avant de refaire l'analyse.`,
    );
  }

  return parseResponse(response);
}

export function getHealth() {
  return requestJson("/health", { method: "GET" });
}

export function getMemoryStats() {
  return requestJson("/memory/stats", { method: "GET" });
}

export function getAnalysisHistory(limit = 12) {
  return requestJson(`/analysis/history?limit=${limit}`, { method: "GET" });
}

export function getValidationQueue(limit = 12) {
  return requestJson(`/validation-queue?limit=${limit}`, { method: "GET" });
}

export function recommendLine(payload) {
  return requestJson("/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function analyzeLine(payload) {
  return recommendLine(payload);
}

export function sendFeedback(payload) {
  return requestJson("/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function askAssistant(payload) {
  return requestJson("/assistant", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function uploadInvoice(file) {
  const formData = new FormData();
  formData.append("file", file);
  return requestFormData("/ocr/analyze-invoice", formData);
}

export function analyzeInvoiceFromOCR(file) {
  return uploadInvoice(file);
}

export function analyzeInvoiceDemo(file) {
  return uploadInvoice(file);
}

export function analyzeOCRText(payload) {
  return requestJson("/analyze/ocr-text", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function analyzeStrongLines(payload) {
  return requestJson("/analysis/strong-lines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function analyzeStrongInvoice(invoiceId, timeoutMs = 60000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return requestJson(`/analysis/strong-invoice/${encodeURIComponent(invoiceId)}`, {
    method: "POST",
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
}

export function fetchRandomInvoices(limit = 10) {
  return requestJson(`/analysis/random-invoices?limit=${limit}`, {
    method: "GET",
  });
}

export function startAnalysisBatch(limit = 50, sortStrategy = "DUE_DATE") {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  return requestJson(`/api/analysis/batch-run?limit=${encodeURIComponent(limit)}&sort_strategy=${encodeURIComponent(sortStrategy)}`, {
    method: "POST",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/analysis/batch-run introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le lancement du lot met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function stopAnalysisBatchJob(jobId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  return requestJson(`/api/analysis/batch-jobs/${encodeURIComponent(jobId)}/stop`, {
    method: "POST",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Job d'analyse introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("L'arret du lot met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function saveAnalysisBatchJob(jobId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  return requestJson(`/api/analysis/batch-jobs/${encodeURIComponent(jobId)}/save`, {
    method: "POST",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Job d'analyse introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("L'enregistrement partiel met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function resumeAnalysisBatchJob(jobId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  return requestJson(`/api/analysis/batch-jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Job d'analyse introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("La reprise du lot met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchAnalysisBatchJob(jobId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  return requestJson(`/api/analysis/batch-jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Job d'analyse introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le suivi du lot met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchInvoicePdfPreview(invoiceId) {
  return requestJson(`/api/analysis/invoice-pdf-preview/${encodeURIComponent(invoiceId)}`, {
    method: "GET",
  });
}
export function fetchInvoicePdfDebug(invoiceId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000);
  return requestJson(`/api/analysis/debug-invoice-pdf/${encodeURIComponent(invoiceId)}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.name === "AbortError") {
      throw new Error("Le diagnostic PDF met trop de temps à répondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function clearAnalysisBatchResults() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);
  return requestJson("/api/analysis/batch-results", {
    method: "DELETE",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.name === "AbortError") {
      throw new Error("La suppression met trop de temps à répondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchAnalysisBatchResults(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  return requestJson(`/api/analysis/batch-results${query ? `?${query}` : ""}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/analysis/batch-results introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le chargement des resultats du lot met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchAnalysisControlQueue(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);

  return requestJson(`/api/analysis/control-queue${query ? `?${query}` : ""}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/analysis/control-queue introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("La recherche CouchDB met trop de temps à répondre. Réessayez dans quelques secondes.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchDossierQueue(clientName, limit = 20) {
  const params = new URLSearchParams({ client_name: clientName, limit: String(limit) });
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  return requestJson(`/api/analysis/dossier-queue?${params.toString()}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) throw new Error(`Dossier « ${clientName} » non trouvé.`);
    if (error?.status === 503) throw new Error("CouchDB indisponible");
    if (error?.name === "AbortError") throw new Error("FastAPI indisponible");
    throw error;
  }).finally(() => clearTimeout(timeoutId));
}

export function fetchDemoFolderSample(perFolder = 3) {
  const params = new URLSearchParams({ per_folder: String(perFolder) });
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90000);
  return requestJson(`/api/analysis/demo-folder-sample?${params.toString()}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 503) throw new Error("CouchDB indisponible");
    if (error?.name === "AbortError") throw new Error(
      "Le chargement depuis keymanage_accounting est lent. Réessayez ou réduisez le périmètre.",
    );
    throw error;
  }).finally(() => clearTimeout(timeoutId));
}

export function fetchKnownClients() {
  return requestJson("/api/analysis/known-clients", { method: "GET" });
}

export function createHumanValidationItem(payload) {
  return requestJson("/api/human-validation/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchHumanValidationItems(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  return requestJson(`/api/human-validation/items${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export function submitHumanValidationDecision(validationId, payload) {
  return requestJson(
    `/api/human-validation/items/${encodeURIComponent(validationId)}/decision`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function deleteHumanValidationItem(validationId) {
  return requestJson(`/api/human-validation/items/${encodeURIComponent(validationId)}`, {
    method: "DELETE",
  });
}

export function fetchKnowledgeBasesSummary() {
  return requestJson("/knowledge-bases/summary", { method: "GET" });
}

export function fetchWorkflowHistory(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  return requestJson(`/api/history/events${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export function createWorkflowHistoryEvent(payload) {
  return requestJson("/api/history/events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function clearWorkflowHistory() {
  return requestJson("/api/history/events", {
    method: "DELETE",
  });
}

export function fetchAIMemoryItems(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  return requestJson(`/api/ai-memory/items${query ? `?${query}` : ""}`, {
    method: "GET",
  });
}

export function rebuildAIMemoryFromValidations() {
  return requestJson("/api/ai-memory/rebuild-from-validations", {
    method: "POST",
  });
}

export function fetchMotorSyncStatus() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  return requestJson("/api/motor-sync/status", {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/motor-sync/status introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le statut met trop de temps a repondre. Reessayez dans quelques instants.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchMotorSyncJob(jobId) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  return requestJson(`/api/motor-sync/jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Job de synchronisation introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le suivi du job met trop de temps a repondre. Reessayez dans quelques instants.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchMotorSyncItems(filters = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      searchParams.set(key, String(value).trim());
    }
  });
  const query = searchParams.toString();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);

  return requestJson(`/api/motor-sync/items${query ? `?${query}` : ""}`, {
    method: "GET",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/motor-sync/items introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("Le chargement des factures synchronisees met trop de temps a repondre.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function runMotorSyncBatch(limit = 50) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  const path = `/api/motor-sync/run?limit=${encodeURIComponent(limit)}`;

  return requestJson(path, {
    method: "POST",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/motor-sync/run introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error(
        "Le lancement du job de synchronisation prend trop de temps. Reessayez dans quelques instants.",
      );
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function purgeOldestInvoices(keep = 50) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 180000);
  const query = new URLSearchParams({
    keep: String(Math.max(0, Math.floor(Number(keep) || 50))),
    confirm: "true",
  });

  return requestJson(`/api/invoices/purge-oldest?${query.toString()}`, {
    method: "DELETE",
    signal: controller.signal,
  }).catch((error) => {
    if (error?.status === 404) {
      throw new Error("Route backend /api/invoices/purge-oldest introuvable");
    }
    if (error?.status === 503) {
      throw new Error("CouchDB indisponible");
    }
    if (error?.name === "AbortError") {
      throw new Error("La purge des factures prend plus de temps que pr�vu.");
    }
    if (/backend fastapi inaccessible/i.test(String(error?.message || ""))) {
      throw new Error("FastAPI indisponible");
    }
    throw error;
  }).finally(() => {
    clearTimeout(timeoutId);
  });
}

export function fetchValidatedEntries(limit = 2000) {
  return fetchHumanValidationItems({ status: "validated", limit });
}

export function exportValidatedInvoiceToOdoo(invoiceId) {
  return requestJson(`/api/odoo/export/${encodeURIComponent(invoiceId)}`, {
    method: "POST",
  });
}

export function getAnalysisBatchStreamUrl(jobId) {
  return `${API_BASE_URL}/api/analysis/batch-jobs/${encodeURIComponent(jobId)}/stream`;
}

export function resetAnalysisTestSession() {
  return requestJson("/api/analysis/reset-session?confirm=true", { method: "POST" });
}
