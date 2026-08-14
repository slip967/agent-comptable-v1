import { useEffect, useMemo, useState } from "react";
import {
  BrainCircuit,
  Gauge,
  LoaderCircle,
  RefreshCcw,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  fetchAnalysisBatchResults,
  fetchAIMemoryItems,
  fetchHumanValidationItems,
  fetchWorkflowHistory,
} from "../services/api";
import { useAnalysisBatch } from "../context/AnalysisBatchContext";
import { readPersistentHiddenIds } from "../utils/persistentHiddenItems";

const VALIDATION_HIDDEN_ITEMS_KEY = "keymanage.validation.hidden-items.v1";
const HISTORY_HIDDEN_EVENTS_KEY = "keymanage.history.hidden-events.v1";
const DONUT_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#7c3aed"];
const PERFORMANCE_RESET_STORAGE_KEY = "keymanage.performance-reset.v1";

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function finiteNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function firstNumber(source, keys) {
  for (const key of keys) {
    const value = finiteNumber(source?.[key]);
    if (value !== null) return value;
  }
  return null;
}

function firstDate(source) {
  const raw =
    source?.analyzed_at ||
    source?.finished_at ||
    source?.created_at ||
    source?.updated_at ||
    source?.date ||
    source?.timestamp;
  if (!raw) return null;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getResultLines(result) {
  const payload = result?.analysis_payload;
  if (asArray(payload?.lines).length) return payload.lines;
  if (asArray(payload?.analysis).length) return payload.analysis;
  return asArray(result?.lines);
}

function countDecision(lines, decision) {
  return lines.filter((line) => String(line?.decision || "").toLowerCase() === decision).length;
}

function getBatchMetrics(result) {
  const lines = getResultLines(result);
  const total = firstNumber(result, ["total_lines", "line_items_count", "exploitable_lines_count"]);
  const auto = firstNumber(result, ["auto_ok", "auto_ok_lines", "auto_validated"]);
  const human = firstNumber(result, ["validation_humaine", "human_validation_lines"]);
  let confidence = firstNumber(result, [
    "average_confidence",
    "confidence",
    "confidence_score",
    "recommended_score",
    "top_score",
  ]);

  if (confidence === null && lines.length) {
    const scores = lines
      .map((line) => firstNumber(line, ["confidence", "score", "confidence_score", "top_score"]))
      .filter((value) => value !== null);
    confidence = scores.length
      ? scores.reduce((sum, value) => sum + value, 0) / scores.length
      : null;
  }

  return {
    total: total ?? lines.length,
    auto: auto ?? countDecision(lines, "auto_ok"),
    human: human ?? countDecision(lines, "validation_humaine"),
    confidence,
  };
}

function uniqueBatchResults(items) {
  const sorted = [...asArray(items)].sort((left, right) => {
    const leftTime = firstDate(left)?.getTime() || 0;
    const rightTime = firstDate(right)?.getTime() || 0;
    return leftTime - rightTime;
  });
  const unique = new Map();
  sorted.forEach((item, index) => {
    const key = String(item?.invoice_id || item?.id || item?._id || `result-${index}`);
    unique.set(key, item);
  });
  return [...unique.values()];
}

function startOfWeek(date) {
  const value = new Date(date);
  const day = value.getDay() || 7;
  value.setDate(value.getDate() - day + 1);
  value.setHours(0, 0, 0, 0);
  return value;
}

function formatWeekLabel(date) {
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(date);
}

function formatMonthLabel(date) {
  const label = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "2-digit" }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function validationCategory(item) {
  const result = item?.human_validation_result || {};
  const value = String(result?.action || item?.action || item?.status || "").toLowerCase();
  if (value.includes("correct")) return "Comptes corrigés";
  if (value.includes("non_comptable") || value.includes("non comptable")) return "Non comptables";
  if (value.includes("enrich")) return "Nouveaux articles";
  if (value.includes("reject") || value.includes("rejet")) return "Rejets";
  if (value === "validate" || value.includes("validated") || value.includes("validé")) {
    return "Validations simples";
  }
  return null;
}

function EmptyChart({ children }) {
  return (
    <div className="memory-performance-empty">
      <BrainCircuit size={24} aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

function ChartTooltip({ active, payload, label, suffix = "" }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="memory-performance-tooltip">
      <strong>{label}</strong>
      {payload.map((entry) => (
        <span key={entry.dataKey}>
          <i style={{ background: entry.color }} />
          {entry.name} : {entry.value}{suffix}
        </span>
      ))}
    </div>
  );
}

function getEntityInvoiceId(item) {
  return String(
    item?.invoice_id ||
      item?.invoiceId ||
      item?.id ||
      item?._id ||
      item?.doc_id ||
      item?.event_invoice_id ||
      item?.source_invoice_id ||
      ""
  ).trim();
}

function hasRelatedInvoiceId(item, invoiceIds) {
  if (!invoiceIds.size) return false;
  const directId = getEntityInvoiceId(item);
  if (directId && invoiceIds.has(directId)) return true;

  const arraysToCheck = [
    item?.source_invoice_ids,
    item?.ids_factures_sources,
    item?.invoice_ids,
    item?.related_invoice_ids,
  ];

  return arraysToCheck.some((value) =>
    Array.isArray(value) && value.some((entry) => invoiceIds.has(String(entry || "").trim())),
  );
}

export default function MemoryPage() {
  const [batchItems, setBatchItems] = useState([]);
  const [validationItems, setValidationItems] = useState([]);
  const [historyEvents, setHistoryEvents] = useState([]);
  const [memoryItems, setMemoryItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sourceErrors, setSourceErrors] = useState([]);
  // eslint-disable-next-line no-unused-vars
  const { queueItems: _liveBatchQueueItems = [] } = useAnalysisBatch();

  const resetPerformanceState = () => {
    setBatchItems([]);
    setValidationItems([]);
    setHistoryEvents([]);
    setMemoryItems([]);
    setSourceErrors([]);
    setLoading(false);
  };

  const loadDashboard = async () => {
    try {
      if (window.sessionStorage?.getItem(PERFORMANCE_RESET_STORAGE_KEY) === "1") {
        resetPerformanceState();
        return;
      }
    } catch {
      // Ignore storage restrictions and continue loading real data.
    }
    setLoading(true);
    setSourceErrors([]);
    try {
      const results = await Promise.allSettled([
        fetchAnalysisBatchResults({ limit: 500 }),
        fetchHumanValidationItems({ limit: 200 }),
        fetchWorkflowHistory({ limit: 500 }),
        fetchAIMemoryItems({ limit: 1000 }),
      ]);

      const labels = ["analyses", "validations humaines", "historique", "mémoire IA"];
      const errors = [];
      results.forEach((result, index) => {
        if (result.status === "rejected") {
          errors.push(`${labels[index]} : ${result.reason?.message || "source indisponible"}`);
        }
      });

      const hiddenValidationIds = new Set(readPersistentHiddenIds(VALIDATION_HIDDEN_ITEMS_KEY));
      const hiddenHistoryIds = new Set(readPersistentHiddenIds(HISTORY_HIDDEN_EVENTS_KEY));
      const batchPayload = results[0].status === "fulfilled" ? results[0].value : {};
      const validationPayload = results[1].status === "fulfilled" ? results[1].value : {};
      const historyPayload = results[2].status === "fulfilled" ? results[2].value : {};
      const memoryPayload = results[3].status === "fulfilled" ? results[3].value : {};

      setBatchItems(asArray(batchPayload?.items));
      setValidationItems(
        asArray(validationPayload?.items).filter(
          (item) => !hiddenValidationIds.has(String(item?.validation_id || item?.id || "")),
        ),
      );
      setHistoryEvents(
        asArray(historyPayload?.events).filter(
          (event) => !hiddenHistoryIds.has(String(event?.event_id || event?.id || "")),
        ),
      );
      setMemoryItems(asArray(memoryPayload?.items));
      setSourceErrors(errors);
    } catch (error) {
      setSourceErrors([error?.message || "Impossible de charger les indicateurs de performance"]);
      setBatchItems([]);
      setValidationItems([]);
      setHistoryEvents([]);
      setMemoryItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleReset = () => resetPerformanceState();

    const handlePerformanceRefresh = () => {
      try {
        window.sessionStorage?.removeItem(PERFORMANCE_RESET_STORAGE_KEY);
      } catch {
        // Ignore storage restrictions.
      }
      void loadDashboard();
    };
    const handleBatchStarted = () => {
      try {
        window.sessionStorage?.removeItem(PERFORMANCE_RESET_STORAGE_KEY);
      } catch {
        // Ignore storage restrictions.
      }
      void loadDashboard();
    };
    window.addEventListener("keymanage:local-analysis-reset", handleReset);
    window.addEventListener("keymanage:performance-refresh", handlePerformanceRefresh);
    window.addEventListener("keymanage:batch-analysis-started", handleBatchStarted);
    return () => {
      window.removeEventListener("keymanage:local-analysis-reset", handleReset);
      window.removeEventListener("keymanage:performance-refresh", handlePerformanceRefresh);
      window.removeEventListener("keymanage:batch-analysis-started", handleBatchStarted);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Données effectives : historique complet des batches persistés ── */
  const effectiveBatchItems = useMemo(() => {
    if (!asArray(batchItems).length) return [];
    return uniqueBatchResults(batchItems);
  }, [batchItems]);

  const currentBatchInvoiceIds = useMemo(() => {
    return new Set(
      effectiveBatchItems
        .map((item) => String(item?.id || item?.invoice_id || item?._id || "").trim())
        .filter(Boolean),
    );
  }, [effectiveBatchItems]);

  const filteredValidationItems = useMemo(() => {
    if (!currentBatchInvoiceIds.size) return validationItems;
    return validationItems.filter((item) => hasRelatedInvoiceId(item, currentBatchInvoiceIds));
  }, [validationItems, currentBatchInvoiceIds]);

  const filteredHistoryEvents = useMemo(() => {
    if (!currentBatchInvoiceIds.size) return historyEvents;
    return historyEvents.filter((item) => hasRelatedInvoiceId(item, currentBatchInvoiceIds));
  }, [historyEvents, currentBatchInvoiceIds]);

  const filteredMemoryItems = useMemo(() => {
    if (!currentBatchInvoiceIds.size) return memoryItems;
    return memoryItems.filter((item) => hasRelatedInvoiceId(item, currentBatchInvoiceIds));
  }, [memoryItems, currentBatchInvoiceIds]);

  /* ── Métriques au niveau FACTURE (pas ligne individuelle) ── */
  const metrics = useMemo(() => {
    return effectiveBatchItems.reduce(
      (totals, item) => {
        const current = getBatchMetrics(item);
        totals.totalInvoices += 1;
        if (current.human === 0) {
          totals.autoInvoices += 1;
        } else {
          totals.humanInvoices += 1;
        }
        totals.total += current.total;
        totals.auto += current.auto;
        totals.human += current.human;
        if (current.confidence !== null && current.total > 0) {
          totals.confidenceTotal += current.confidence * current.total;
          totals.confidenceWeight += current.total;
        }
        return totals;
      },
      { total: 0, auto: 0, human: 0, confidenceTotal: 0, confidenceWeight: 0, totalInvoices: 0, autoInvoices: 0, humanInvoices: 0 },
    );
  }, [effectiveBatchItems]);

  /* Taux au niveau facture — renvoient 0 si aucune donnée (non bloquant) */
  const automationRate = metrics.totalInvoices > 0 ? (metrics.autoInvoices / metrics.totalInvoices) * 100 : 0;
  const humanValidationRate = metrics.totalInvoices > 0 ? (metrics.humanInvoices / metrics.totalInvoices) * 100 : 0;
  const humanValidationInvoices = metrics.humanInvoices;

  /* ── Graphique hebdomadaire (niveau facture) ── */
  const weeklyData = useMemo(() => {
    const groups = new Map();
    effectiveBatchItems.forEach((item) => {
      const date = firstDate(item);
      if (!date) return;
      const week = startOfWeek(date);
      const key = week.toISOString().slice(0, 10);
      const current = groups.get(key) || {
        key,
        date: week,
        totalInvoices: 0,
        autoInvoices: 0,
        confidenceTotal: 0,
        confidenceWeight: 0,
      };
      const values = getBatchMetrics(item);
      current.totalInvoices += 1;
      if (values.human === 0) current.autoInvoices += 1;
      if (values.confidence !== null && values.total > 0) {
        current.confidenceTotal += values.confidence * values.total;
        current.confidenceWeight += values.total;
      }
      groups.set(key, current);
    });
    return [...groups.values()]
      .sort((left, right) => left.date - right.date)
      .map((group) => ({
        periode: formatWeekLabel(group.date),
        automatisation: group.totalInvoices ? Number(((group.autoInvoices / group.totalInvoices) * 100).toFixed(1)) : 0,
        confiance: group.confidenceWeight
          ? Number((group.confidenceTotal / group.confidenceWeight).toFixed(1))
          : null,
      }));
  }, [effectiveBatchItems]);

  /* ── Graphique donut corrections humaines ── */
  const correctionData = useMemo(() => {
    const groups = new Map();
    filteredValidationItems.forEach((item) => {
      const category = validationCategory(item);
      if (category) groups.set(category, (groups.get(category) || 0) + 1);
    });
    return [...groups.entries()].map(([name, value]) => ({ name, value }));
  }, [filteredValidationItems]);

  /* ── Graphique mensuel (niveau facture) ── */
  const monthlyData = useMemo(() => {
    const groups = new Map();
    effectiveBatchItems.forEach((item) => {
      const date = firstDate(item);
      if (!date) return;
      const month = new Date(date.getFullYear(), date.getMonth(), 1);
      const key = month.toISOString().slice(0, 7);
      const current = groups.get(key) || { key, date: month, auto: 0, humain: 0 };
      const values = getBatchMetrics(item);
      if (values.human === 0) {
        current.auto += 1;
      } else {
        current.humain += 1;
      }
      groups.set(key, current);
    });
    return [...groups.values()]
      .sort((left, right) => left.date - right.date)
      .map((group) => ({
        mois: formatMonthLabel(group.date),
        autoValidees: group.auto,
        validationsHumaines: group.humain,
      }));
  }, [effectiveBatchItems]);

  return (
    <div className="memory-performance-page">
      <div className="memory-performance-toolbar">
        <div className="memory-performance-actions">
          <button type="button" onClick={loadDashboard} disabled={loading}>
            {loading ? <LoaderCircle size={17} className="spin" /> : <RefreshCcw size={17} />}
            Actualiser
          </button>
        </div>
      </div>

      {sourceErrors.length ? (
        <div className="memory-performance-alert" role="status">
          Certaines sources réelles sont indisponibles : {sourceErrors.join(" · ")}
        </div>
      ) : null}

      <section className="memory-performance-kpis" aria-label="Indicateurs de performance IA">
        <article className="memory-performance-kpi tone-blue">
          <span className="memory-performance-kpi-icon"><Gauge size={21} /></span>
          <div>
            <small>{"Taux d\u2019automatisation"}</small>
            <strong>{loading ? "\u2014" : `${automationRate.toFixed(1)} %`}</strong>
          </div>
          <p>
            {loading
              ? "Chargement\u2026"
              : metrics.totalInvoices
                ? `${metrics.autoInvoices} facture(s) entièrement auto-validée(s) sur ${metrics.totalInvoices}`
                : "Aucune analyse réelle exploitable."}
          </p>
        </article>
        <article className="memory-performance-kpi tone-amber">
          <span className="memory-performance-kpi-icon"><BrainCircuit size={21} /></span>
          <div>
            <small>Taux de validation humaine</small>
            <strong>{loading ? "\u2014" : `${humanValidationRate.toFixed(1)} %`}</strong>
          </div>
          <p>
            {loading
              ? "Chargement\u2026"
              : metrics.totalInvoices
                ? `${humanValidationInvoices} facture(s) nécessitent un contrôle humain sur ${metrics.totalInvoices}`
                : "Aucune analyse réelle exploitable."}
          </p>
        </article>
      </section>

      <section className="memory-performance-grid">
        <article className="memory-performance-chart memory-performance-chart-wide">
          <div className="memory-performance-chart-head">
            <div>
              <span>Évolution hebdomadaire</span>
              <h2>{"Courbe d\u2019apprentissage de l\u2019IA"}</h2>
            </div>
            <BrainCircuit size={21} />
          </div>
          {loading ? (
            <EmptyChart>{"Chargement des analyses réelles\u2026"}</EmptyChart>
          ) : weeklyData.length >= 2 ? (
            <div className="memory-performance-chart-body">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weeklyData} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="memoryAutomationFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.38} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="4 6" vertical={false} stroke="rgba(100,116,139,.18)" />
                  <XAxis dataKey="periode" axisLine={false} tickLine={false} tick={{ fill: "#7b8798", fontSize: 12 }} />
                  <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fill: "#7b8798", fontSize: 12 }} />
                  <Tooltip content={<ChartTooltip suffix=" %" />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="automatisation" name="Automatisation" stroke="#2563eb" strokeWidth={3} fill="url(#memoryAutomationFill)" />
                  <Area type="monotone" dataKey="confiance" name="Confiance IA" stroke="#7c3aed" strokeWidth={2.5} fill="transparent" connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart>{"Pas encore assez de données réelles pour tracer la courbe d\u2019apprentissage."}</EmptyChart>
          )}
        </article>

        <article className="memory-performance-chart">
          <div className="memory-performance-chart-head">
            <div>
              <span>Décisions réelles</span>
              <h2>Nature des corrections expert-comptable</h2>
            </div>
            <UserRoundCheck size={21} />
          </div>
          {loading ? (
            <EmptyChart>{"Chargement des validations réelles\u2026"}</EmptyChart>
          ) : correctionData.length ? (
            <div className="memory-performance-chart-body donut">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={correctionData} dataKey="value" nameKey="name" cx="50%" cy="44%" innerRadius={54} outerRadius={82} paddingAngle={3}>
                    {correctionData.map((entry, index) => (
                      <Cell key={entry.name} fill={DONUT_COLORS[index % DONUT_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart>Aucune correction humaine réelle disponible pour le moment.</EmptyChart>
          )}
        </article>

        <article className="memory-performance-chart memory-performance-chart-full">
          <div className="memory-performance-chart-head">
            <div>
              <span>Répartition mensuelle</span>
              <h2>{"IA vs humain \u2014 volumes mensuels"}</h2>
            </div>
            <ShieldCheck size={21} />
          </div>
          {loading ? (
            <EmptyChart>{"Chargement des volumes réels\u2026"}</EmptyChart>
          ) : monthlyData.length && monthlyData.some((item) => item.autoValidees || item.validationsHumaines) ? (
            <div className="memory-performance-chart-body bar">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyData} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="4 6" vertical={false} stroke="rgba(100,116,139,.18)" />
                  <XAxis dataKey="mois" axisLine={false} tickLine={false} tick={{ fill: "#7b8798", fontSize: 12 }} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: "#7b8798", fontSize: 12 }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="autoValidees" name="Auto-validées" fill="#2563eb" radius={[7, 7, 0, 0]} maxBarSize={42} />
                  <Bar dataKey="validationsHumaines" name="Validations humaines" fill="#f59e0b" radius={[7, 7, 0, 0]} maxBarSize={42} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyChart>Les volumes mensuels seront disponibles après les premières analyses et validations réelles.</EmptyChart>
          )}
        </article>
      </section>

      <section className="memory-performance-sources" aria-label="État des sources réelles">
        <span>{batchItems.length} analyse(s) enregistrée(s)</span>
        <span>{validationItems.length} validation(s) visible(s)</span>
        <span>
          {filteredHistoryEvents.length
            ? `${filteredHistoryEvents.length} événement(s) réel(s)`
            : "Aucun événement réel disponible pour calculer cette métrique."}
        </span>
        <span>
          {filteredMemoryItems.length
            ? `${filteredMemoryItems.length} candidat(s) mémoire`
            : "Aucun candidat mémoire réel n'a encore été généré."}
        </span>
      </section>
    </div>
  );
}




