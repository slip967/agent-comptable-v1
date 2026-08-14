import { useEffect, useRef, useState } from "react";
import { ClipboardCheck, LoaderCircle, RefreshCcw } from "lucide-react";

import {
  fetchMotorSyncJob,
  fetchMotorSyncItems,
  fetchMotorSyncStatus,
  runMotorSyncBatch,
} from "../../services/api";

const RUNNING_JOB_STATUSES = new Set(["queued", "running"]);

function textOrFallback(value, fallback = "Non renseigne") {
  const text = String(value || "").trim();
  return text || fallback;
}

function formatDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Non renseigne";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function formatDuration(value) {
  const duration = Number(value || 0);
  if (!duration) return "Non renseignée";
  if (duration < 1000) return `${duration} ms`;
  return `${(duration / 1000).toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} s`;
}

function formatCompactDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Non renseigne";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatInvoiceDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Non renseignée";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(parsed);
}

function shortenId(value, maxLen = 14) {
  const text = String(value || "").trim();
  if (!text) return "Non renseigne";
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen)}...`;
}

function pdfStatusLabel(status) {
  return (
    {
      available: "PDF dispo",
      missing_file: "PDF absent",
      no_path: "Sans PDF",
      inaccessible: "Accès KO",
      unknown: "Inconnu",
    }[status] || "Inconnu"
  );
}

function pdfStatusClass(status) {
  if (status === "available") return "status-pill ready compact";
  if (status === "missing_file") return "status-pill review compact";
  if (status === "inaccessible") return "status-pill danger compact";
  if (status === "no_path") return "status-pill slate compact";
  return "status-pill slate compact";
}

function lineStatusClass(lineCount) {
  return Number(lineCount || 0) > 0
    ? "status-pill ready compact"
    : "status-pill slate compact";
}

function lineStatusLabel(lineCount) {
  const count = Number(lineCount || 0);
  if (count <= 0) return "Sans lignes";
  return `${count} ligne${count > 1 ? "s" : ""}`;
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

function syncJobStatusClass(status) {
  if (status === "completed") return "status-pill ready";
  if (status === "failed") return "status-pill danger";
  if (status === "running") return "status-pill review";
  return "status-pill info";
}

function syncJobStatusLabel(status) {
  if (status === "completed") return "Termine";
  if (status === "failed") return "Erreur";
  if (status === "running") return "En cours";
  return "En attente";
}

function isRunningJob(job) {
  return RUNNING_JOB_STATUSES.has(String(job?.status || "").trim());
}

function buildCompletedSyncMessage(job) {
  return `Synchronisation terminée : ${job?.processed || 0} factures traitées, ${job?.with_lines || 0} avec lignes, ${job?.errors || 0} erreur.`;
}

function syncedInvoiceTitle(item) {
  return (
    String(item?.supplier || "").trim()
    || String(item?.client || "").trim()
    || "Facture synchronisée"
  );
}

function syncedInvoiceSubtitle(item) {
  const invoiceLabel = String(item?.invoice_number || "").trim() || shortenId(item?.invoice_id, 12);
  const invoiceDate = formatInvoiceDate(item?.date);
  if (invoiceDate === "Non renseignée") {
    return `Facture : ${invoiceLabel}`;
  }
  return `Facture : ${invoiceLabel} · ${invoiceDate}`;
}

export default function MotorSyncPanel() {
  const [syncStatus, setSyncStatus] = useState({
    database: "keymanage_accounting",
    last_sync_at: "",
    total_batches: 0,
    total_processed: 0,
    total_with_lines: 0,
    total_without_lines: 0,
    total_with_pdf: 0,
    total_errors: 0,
    last_duration_ms: 0,
    has_more: true,
    current_job: null,
  });
  const [syncJob, setSyncJob] = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncStarting, setSyncStarting] = useState(false);
  const [syncErrorMessage, setSyncErrorMessage] = useState("");
  const [syncSuccessMessage, setSyncSuccessMessage] = useState("");
  const [syncInfoMessage, setSyncInfoMessage] = useState("");
  const [syncItems, setSyncItems] = useState([]);
  const [syncItemsLoading, setSyncItemsLoading] = useState(false);
  const [syncItemsError, setSyncItemsError] = useState("");
  const [syncItemsInfo, setSyncItemsInfo] = useState("");
  const pollingRef = useRef(null);

  const hasLaunchedSync = Boolean(
    syncStatus.last_sync_at || syncStatus.total_batches || syncStatus.total_processed,
  );
  const syncIsBusy = syncStarting || isRunningJob(syncJob);

  const stopSyncPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const loadSyncItems = async ({ source = "manual", limit = 50 } = {}) => {
    const startedAt = Date.now();
    console.info("[MotorSyncPanel][items] request start", {
      source,
      method: "GET",
      limit,
      startedAt: new Date(startedAt).toISOString(),
    });
    setSyncItemsLoading(true);
    setSyncItemsError("");
    try {
      const payload = await fetchMotorSyncItems({ limit });
      console.info("[MotorSyncPanel][items] request success", {
        source,
        method: "GET",
        status: 200,
        durationMs: Date.now() - startedAt,
        response: payload,
      });
      const nextItems = Array.isArray(payload?.items) ? payload.items : [];
      setSyncItems(nextItems);
      return payload;
    } catch (error) {
      console.error("[MotorSyncPanel][items] request error", {
        source,
        method: "GET",
        durationMs: Date.now() - startedAt,
        error,
      });
      setSyncItemsError(
        String(error?.message || "").trim() ||
          "Impossible de charger les factures synchronisées récentes.",
      );
      return null;
    } finally {
      setSyncItemsLoading(false);
    }
  };

  const loadSyncStatus = async ({ rethrow = false, source = "manual" } = {}) => {
    const startedAt = Date.now();
    console.info("[MotorSyncPanel][status] request start", {
      source,
      method: "GET",
      startedAt: new Date(startedAt).toISOString(),
    });

    setSyncLoading(true);
    setSyncErrorMessage("");
    try {
      const payload = await fetchMotorSyncStatus();
      console.info("[MotorSyncPanel][status] request success", {
        source,
        method: "GET",
        status: 200,
        durationMs: Date.now() - startedAt,
        response: payload,
      });

      setSyncStatus((current) => ({
        ...current,
        ...(payload || {}),
      }));

      if (payload?.current_job && payload.current_job.status) {
        setSyncJob(payload.current_job);
      }

      return payload;
    } catch (error) {
      const message =
        String(error?.message || "").trim() ||
        "Impossible de charger le statut de synchronisation CouchDB.";
      console.error("[MotorSyncPanel][status] request error", {
        source,
        method: "GET",
        durationMs: Date.now() - startedAt,
        error,
      });
      setSyncErrorMessage(message);
      if (rethrow) {
        throw error;
      }
      return null;
    } finally {
      setSyncLoading(false);
    }
  };

  const pollSyncJobOnce = async (jobId, { silent = false } = {}) => {
    const startedAt = Date.now();
    try {
      const payload = await fetchMotorSyncJob(jobId);
      console.info("[MotorSyncPanel][job] poll success", {
        jobId,
        status: payload?.status,
        durationMs: Date.now() - startedAt,
        response: payload,
      });
      setSyncJob(payload);
      if (isRunningJob(payload)) {
        setSyncStarting(false);
      }

      if (payload?.status === "completed") {
        stopSyncPolling();
        setSyncStarting(false);
        setSyncInfoMessage("");
        setSyncSuccessMessage(buildCompletedSyncMessage(payload));
        await loadSyncStatus({ source: "job-completed-refresh" });
        await loadSyncItems({ source: "job-completed-refresh" });
      } else if (payload?.status === "failed") {
        stopSyncPolling();
        setSyncStarting(false);
        setSyncInfoMessage("");
        setSyncErrorMessage(
          String(payload?.message || "").trim() ||
            "La synchronisation du lot a echoue.",
        );
        await loadSyncStatus({ source: "job-failed-refresh" });
      } else if (!silent) {
        setSyncInfoMessage(
          `Synchronisation en cours : ${payload?.processed || 0}/${payload?.limit || 0} factures traitées.`,
        );
      }

      return payload;
    } catch (error) {
      console.error("[MotorSyncPanel][job] poll error", {
        jobId,
        durationMs: Date.now() - startedAt,
        error,
      });
      setSyncStarting(false);
      if (!silent) {
        setSyncErrorMessage(
          String(error?.message || "").trim() ||
            "Impossible de suivre le job de synchronisation.",
        );
      }
      return null;
    }
  };

  const startSyncPolling = (jobId) => {
    stopSyncPolling();
    void pollSyncJobOnce(jobId, { silent: false });
    pollingRef.current = setInterval(() => {
      void pollSyncJobOnce(jobId, { silent: true });
    }, 2500);
  };

  const handleRunSync = async (limit) => {
    const startedAt = Date.now();

    console.info("[MotorSyncPanel][run] click detected", {
      limit,
      method: "POST",
    });

    setSyncStarting(true);
    setSyncErrorMessage("");
    setSyncSuccessMessage("");
    setSyncInfoMessage("Lancement du job de synchronisation...");

    try {
      const payload = await runMotorSyncBatch(limit);
      console.info("[MotorSyncPanel][run] request success", {
        limit,
        method: "POST",
        status: 202,
        durationMs: Date.now() - startedAt,
        response: payload,
      });

      if (payload?.status === "already_running" && payload?.job_id) {
        setSyncStarting(false);
        setSyncJob(payload);
        setSyncInfoMessage("Une synchronisation est deja en cours.");
        startSyncPolling(payload.job_id);
        return;
      }

      setSyncStarting(false);
      setSyncJob(payload);
      setSyncInfoMessage("Job de synchronisation lance.");

      if (payload?.job_id) {
        startSyncPolling(payload.job_id);
      } else {
        setSyncErrorMessage("Job de synchronisation invalide.");
      }
    } catch (error) {
      console.error("[MotorSyncPanel][run] request error", {
        limit,
        method: "POST",
        durationMs: Date.now() - startedAt,
        error,
      });
      setSyncStarting(false);
      setSyncInfoMessage("");
      setSyncErrorMessage(
        String(error?.message || "").trim() ||
          "Impossible de lancer la synchronisation en lots.",
      );
    }
  };

  useEffect(() => {
    void loadSyncStatus({ source: "page-load" }).then((payload) => {
      if (payload?.current_job?.job_id && isRunningJob(payload.current_job)) {
        startSyncPolling(payload.current_job.job_id);
      }
    });
    void loadSyncItems({ source: "page-load" });

    return () => {
      stopSyncPolling();
    };
  }, []);

  useEffect(() => {
    if (syncItemsInfo) {
      const timer = setTimeout(() => setSyncItemsInfo(""), 2500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [syncItemsInfo]);

  const showSyncItemsWarning =
    !syncItemsLoading &&
    !syncItemsError &&
    syncItems.length === 0 &&
    Number(syncStatus.total_processed || 0) > 0;

  return (
    <section className="card surface-card page-panel-card motor-sync-card">
      <div className="analysis-card-title-row">
        <div className="section-header">
          <h2 className="section-title">Synchronisation CouchDB en lots</h2>
          <p className="section-text">
            Lancez les lots de synchronisation depuis Analyse IA pour alimenter
            la memoire et suivre le job en arrière-plan sans bloquer l&apos;interface.
          </p>
        </div>

        <button
          type="button"
          className="secondary-btn compact"
          onClick={() => void loadSyncStatus({ source: "manual-refresh" })}
          disabled={syncLoading || syncIsBusy}
        >
          {syncLoading ? <LoaderCircle size={15} className="spin" /> : <RefreshCcw size={15} />}
          Rafraîchir le statut
        </button>
      </div>

      {syncInfoMessage ? <div className="analysis-inline-note">{syncInfoMessage}</div> : null}
      {syncErrorMessage ? <div className="analysis-inline-error">{syncErrorMessage}</div> : null}
      {syncSuccessMessage ? <div className="analysis-inline-success">{syncSuccessMessage}</div> : null}
      {syncItemsInfo ? <div className="analysis-inline-success">{syncItemsInfo}</div> : null}

      <div className="motor-sync-summary">
        {!hasLaunchedSync ? (
          <p className="motor-sync-empty">
            Aucune synchronisation lancée pour le moment.
          </p>
        ) : null}

        <div className="mini-stat-grid three-cols motor-sync-grid">
          <div className="mini-stat-card">
            <div className="mini-stat-label">Base utilisée</div>
            <div className="mini-stat-value motor-sync-text">
              {textOrFallback(syncStatus.database)}
            </div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Dernière synchronisation</div>
            <div className="mini-stat-value history-date-value">
              {syncStatus.last_sync_at ? formatDate(syncStatus.last_sync_at) : "Aucune"}
            </div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Lots traités</div>
            <div className="mini-stat-value">{syncStatus.total_batches || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Factures traitées</div>
            <div className="mini-stat-value">{syncStatus.total_processed || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Factures avec lignes</div>
            <div className="mini-stat-value">{syncStatus.total_with_lines || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Documents source disponibles</div>
            <div className="mini-stat-value">{syncStatus.total_with_pdf || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Factures sans lignes</div>
            <div className="mini-stat-value">{syncStatus.total_without_lines || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Erreurs</div>
            <div className="mini-stat-value">{syncStatus.total_errors || 0}</div>
          </div>

          <div className="mini-stat-card">
            <div className="mini-stat-label">Durée du dernier lot</div>
            <div className="mini-stat-value history-date-value">
              {formatDuration(syncStatus.last_duration_ms)}
            </div>
          </div>
        </div>

        {syncJob ? (
          <div className="card surface-card motor-sync-job-panel">
            <div className="motor-sync-job-head">
              <div className="record-title-row">
                <h3 className="section-title">Suivi du job de synchronisation</h3>
                <span className={syncJobStatusClass(syncJob.status)}>
                  {syncJobStatusLabel(syncJob.status)}
                </span>
              </div>
              <p className="section-text">
                {syncJob.message || "Synchronisation en cours"}
              </p>
            </div>

            <div className="record-metrics motor-sync-job-metrics">
              <div className="metric-pill">
                <div className="metric-pill-label">Progression</div>
                <div className="metric-pill-value">
                  {syncJob.processed || 0} / {syncJob.limit || 0}
                </div>
              </div>
              <div className="metric-pill">
                <div className="metric-pill-label">Avec lignes</div>
                <div className="metric-pill-value">{syncJob.with_lines || 0}</div>
              </div>
              <div className="metric-pill">
                <div className="metric-pill-label">Avec PDF</div>
                <div className="metric-pill-value">{syncJob.with_pdf || 0}</div>
              </div>
              <div className="metric-pill">
                <div className="metric-pill-label">Erreurs</div>
                <div className="metric-pill-value">{syncJob.errors || 0}</div>
              </div>
              <div className="metric-pill">
                <div className="metric-pill-label">Durée</div>
                <div className="metric-pill-value">{formatDuration(syncJob.duration_ms)}</div>
              </div>
              <div className="metric-pill">
                <div className="metric-pill-label">Facture en cours</div>
                <div className="metric-pill-value">
                  {textOrFallback(syncJob.current_invoice_id, "Aucune")}
                </div>
              </div>
            </div>

            {Array.isArray(syncJob.warnings) && syncJob.warnings.length ? (
              <div className="motor-sync-job-warnings">
                {syncJob.warnings.map((warning, index) => (
                  <span key={`${syncJob.job_id}-warning-${index}`} className="status-pill review compact">
                    {warning}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="motor-sync-footer">
          <div className="motor-sync-status-line">
            <span className={`status-pill ${syncStatus.has_more ? "review" : "ready"}`}>
              {syncStatus.has_more
                ? "Il reste des factures à synchroniser"
                : "Synchronisation terminée"}
            </span>
            {syncIsBusy ? (
              <span className="motor-sync-inline-note">
                Synchronisation en cours : {syncJob?.processed || 0}/{syncJob?.limit || 0} factures traitées.
              </span>
            ) : null}
          </div>

          <div className="button-row">
            <button
              type="button"
              className="secondary-btn compact"
              disabled={syncIsBusy}
              onClick={() => void handleRunSync(5)}
            >
              {syncIsBusy && Number(syncJob?.limit || 0) === 5 ? <LoaderCircle size={15} className="spin" /> : null}
              Synchroniser 5
            </button>
            <button
              type="button"
              className="secondary-btn compact"
              disabled={syncIsBusy}
              onClick={() => void handleRunSync(50)}
            >
              {syncIsBusy && Number(syncJob?.limit || 0) === 50 ? <LoaderCircle size={15} className="spin" /> : null}
              Synchroniser 50
            </button>
            <button
              type="button"
              className="secondary-btn compact"
              disabled={syncIsBusy}
              onClick={() => void handleRunSync(100)}
            >
              {syncIsBusy && Number(syncJob?.limit || 0) === 100 ? <LoaderCircle size={15} className="spin" /> : null}
              Synchroniser 100
            </button>
          </div>
        </div>
      </div>

      <div className="motor-sync-items-section">
        <div className="analysis-card-title-row">
          <div className="section-header">
            <h3 className="section-title">Factures synchronisées récemment</h3>
            <p className="section-text">
                Suivi compact des dernières factures traitées par les lots de
                synchronisation, sans relancer d&apos;analyse comptable.
            </p>
          </div>

          <button
            type="button"
            className="secondary-btn compact"
            onClick={() => void loadSyncItems({ source: "manual-refresh-list" })}
            disabled={syncItemsLoading}
          >
            {syncItemsLoading ? <LoaderCircle size={15} className="spin" /> : <RefreshCcw size={15} />}
            Rafraîchir la liste
          </button>
        </div>

        {syncItemsError ? <div className="analysis-inline-error">{syncItemsError}</div> : null}
        {showSyncItemsWarning ? (
          <div className="analysis-inline-note">
            Le lot a été traité, mais les résumés des factures ne sont pas encore enregistrés.
          </div>
        ) : null}

        {syncItemsLoading && !syncItems.length ? (
          <div className="motor-sync-items-empty">
            <LoaderCircle size={16} className="spin" />
            Chargement des factures synchronisées...
          </div>
        ) : syncItems.length ? (
          <div className="motor-sync-items-list">
            {syncItems.map((item) => (
              <article key={`${item.invoice_id}-${item.synced_at}`} className="motor-sync-item-row">
                <div className="motor-sync-item-main">
                  <div className="motor-sync-item-headline-row">
                    <h4 className="motor-sync-item-title" title={syncedInvoiceTitle(item)}>
                      {syncedInvoiceTitle(item)}
                    </h4>
                    <button
                      type="button"
                      className="secondary-btn compact motor-sync-copy-btn"
                      onClick={() =>
                        copyToClipboard(item.invoice_id, () =>
                          setSyncItemsInfo("invoice_id copié dans le presse-papiers."),
                        )
                      }
                      title={textOrFallback(item.invoice_id)}
                    >
                      <ClipboardCheck size={12} />
                      Copier ID
                    </button>
                  </div>

                  <p className="motor-sync-item-subtitle" title={syncedInvoiceSubtitle(item)}>
                    {syncedInvoiceSubtitle(item)}
                  </p>

                  <div className="motor-sync-item-inline-meta">
                    <span className="motor-sync-item-inline-text" title={textOrFallback(item.client)}>
                      Client : {textOrFallback(item.client)}
                    </span>
                    <span className="motor-sync-item-inline-dot">·</span>
                    <span className={lineStatusClass(item.line_count)}>
                      {lineStatusLabel(item.line_count)}
                    </span>
                    <span className={pdfStatusClass(item.pdf_status)}>
                      {pdfStatusLabel(item.pdf_status)}
                    </span>
                    <span className="motor-sync-item-inline-text">
                      Sync : {formatCompactDate(item.synced_at)}
                    </span>
                  </div>
                </div>

                <div className="motor-sync-item-side">
                  <div className="motor-sync-item-detail">
                    <span className="motor-sync-item-key">Fournisseur</span>
                    <span className="motor-sync-item-val" title={textOrFallback(item.supplier)}>
                      {textOrFallback(item.supplier)}
                    </span>
                  </div>
                  <div className="motor-sync-item-detail">
                    <span className="motor-sync-item-key">Lignes</span>
                    <span className={lineStatusClass(item.line_count)}>
                      {lineStatusLabel(item.line_count)}
                    </span>
                  </div>
                  <div className="motor-sync-item-detail">
                    <span className="motor-sync-item-key">PDF</span>
                    <span className={pdfStatusClass(item.pdf_status)}>
                      {pdfStatusLabel(item.pdf_status)}
                    </span>
                  </div>
                  <div className="motor-sync-item-detail">
                    <span className="motor-sync-item-key">ID</span>
                    <span className="motor-sync-item-val" title={textOrFallback(item.invoice_id)}>
                      {shortenId(item.invoice_id, 14)}
                    </span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="motor-sync-items-empty">
            Aucune facture synchronisée affichable pour le moment.
          </div>
        )}
      </div>
    </section>
  );
}
