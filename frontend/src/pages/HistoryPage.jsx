import { useEffect, useMemo, useState } from "react";
import { useGlobalSearch } from "../context/SearchContext";
import { matchesGlobalSearch } from "../utils/search";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Clock3,
  FileText,
  LoaderCircle,
  RefreshCcw,
  Trash2,
  UserCheck,
  X,
  XCircle,
} from "lucide-react";

import { API_BASE_URL, fetchInvoicePdfDebug, fetchWorkflowHistory, clearWorkflowHistory } from "../services/api";
import { cleanSummaryText, formatHumanReadableText, formatWorkflowSource } from "../utils/uiText";
import { addPersistentHiddenId, readPersistentHiddenIds } from "../utils/persistentHiddenItems";

const HISTORY_HIDDEN_EVENTS_KEY = "keymanage.history.hidden-events.v1";

const HISTORY_V0_STYLES = `
  .history-v0-page {
    width: min(100%, 1120px);
    margin: 0 auto;
    display: grid;
    gap: 22px;
  }

  .history-v0-breadcrumb {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .history-v0-shell,
  .history-v0-viewer,
  .history-v0-empty,
  .history-v0-alert {
    background: var(--surface-bg);
    border: 1px solid var(--card-border);
    box-shadow: var(--shadow-strong);
    backdrop-filter: blur(18px);
  }

  .history-v0-shell {
    display: grid;
    gap: 24px;
    padding: 0;
    border: none;
    box-shadow: none;
    background: transparent;
    backdrop-filter: none;
  }

  .history-v0-toolbar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 0;
  }

  .history-v0-toolbar-copy {
    display: grid;
    gap: 2px;
  }

  .history-v0-toolbar-copy strong {
    color: var(--text);
    font-size: 13px;
    font-weight: 800;
    letter-spacing: -0.01em;
  }

  .history-v0-toolbar-copy span {
    color: var(--muted);
    font-size: 12px;
    line-height: 1.45;
  }

  .history-v0-action-button,
  .history-v0-pdf-button,
  .history-v0-viewer-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: 999px;
    border: 1px solid var(--card-border);
    background: #ffffff;
    color: var(--text);
    transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
  }

  .history-v0-action-button:hover,
  .history-v0-pdf-button:hover,
  .history-v0-viewer-button:hover {
    transform: translateY(-1px);
    border-color: rgba(99, 102, 241, 0.26);
    background: rgba(99, 102, 241, 0.08);
  }

  .history-v0-action-button {
    min-height: 40px;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 700;
  }

  .history-v0-filters {
    margin-top: -6px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .history-v0-filter {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    min-height: 38px;
    padding: 8px 14px;
    border-radius: 999px;
    border: 1px solid var(--card-border);
    background: #ffffff;
    color: var(--text);
    font-size: 12px;
    font-weight: 700;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
    transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
  }

  .history-v0-filter:hover {
    transform: translateY(-1px);
  }

  .history-v0-filter.active {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.26);
    color: #4f46e5;
  }

  .history-v0-filter-dot {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    flex: 0 0 auto;
  }

  .history-v0-filter-dot--all { background: #4f46e5; }
  .history-v0-filter-dot--validations { background: #f59e0b; }
  .history-v0-filter-dot--human-corrections { background: #10b981; }
  .history-v0-filter-dot--ai-events { background: #64748b; }
  .history-v0-filter-dot--errors { background: #ef4444; }

  .history-v0-filter-label {
    white-space: nowrap;
  }

  .history-v0-filter-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 22px;
    padding: 0 7px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.08);
    color: inherit;
    font-size: 11px;
    font-weight: 800;
    line-height: 1;
  }

  .history-v0-alert {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 18px;
    color: #b91c1c;
    background: rgba(248, 113, 113, 0.08);
    border-color: rgba(248, 113, 113, 0.18);
    font-size: 13px;
    line-height: 1.55;
  }

  .history-v0-events {
    display: grid;
    gap: 16px;
    margin-top: 12px;
  }

  .history-v0-event {
    display: grid;
    gap: 9px;
    padding: 14px 18px;
    border-radius: 18px;
    border: 1px solid var(--card-border);
    border-left-width: 4px;
    background: #ffffff;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.06);
    transition: background 0.18s ease, transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  }

  .history-v0-event:hover {
    transform: translateY(-1px);
    border-color: rgba(148, 163, 184, 0.42);
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
  }
  .history-v0-event--analysis { border-left-color: #3b82f6; }
  .history-v0-event--analysis:hover { background: #ffffff; }
  .history-v0-event--review { border-left-color: #f59e0b; }
  .history-v0-event--review:hover { background: #ffffff; }
  .history-v0-event--validated { border-left-color: #10b981; }
  .history-v0-event--validated:hover { background: #ffffff; }
  .history-v0-event--corrected { border-left-color: #10b981; }
  .history-v0-event--corrected:hover { background: #ffffff; }
  .history-v0-event--non-comptable { border-left-color: #94a3b8; }
  .history-v0-event--non-comptable:hover { background: #ffffff; }
  .history-v0-event--rejected, .history-v0-event--error { border-left-color: #ef4444; }
  .history-v0-event--rejected:hover, .history-v0-event--error:hover { background: #ffffff; }
  .history-v0-event--enrichment { border-left-color: #8b5cf6; }
  .history-v0-event--enrichment:hover { background: #ffffff; }
  .history-v0-event--neutral { border-left-color: #cbd5e1; }
  .history-v0-event--neutral:hover { background: #ffffff; }

  .history-v0-event-top,
  .history-v0-event-middle,
  .history-v0-event-bottom {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }

  .history-v0-event-top-left,
  .history-v0-event-middle-left,
  .history-v0-event-bottom-left,
  .history-v0-event-top-right,
  .history-v0-event-bottom-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    min-width: 0;
  }

  .history-v0-event-middle-left {
    align-items: baseline;
  }

  .history-v0-event-top-left {
    flex: 1 1 420px;
  }

  .history-v0-event-top-right {
    flex: 0 0 auto;
    justify-content: flex-end;
    align-items: flex-start;
    margin-left: auto;
  }

  .history-v0-event-bottom-left {
    flex: 1 1 420px;
    min-width: 0;
    display: grid;
    gap: 6px;
  }

  .history-v0-event-bottom-right {
    flex: 0 1 100%;
    justify-content: flex-start;
    margin-top: 2px;
  }

  .history-v0-event-type {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
    padding: 4px 9px;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.18);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .history-v0-event-type--analysis { color: #1d4ed8; background: rgba(59, 130, 246, 0.12); border-color: rgba(59, 130, 246, 0.22); }
  .history-v0-event-type--review { color: #b45309; background: rgba(245, 158, 11, 0.12); border-color: rgba(245, 158, 11, 0.24); }
  .history-v0-event-type--validated,
  .history-v0-event-type--corrected { color: #047857; background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.22); }
  .history-v0-event-type--non-comptable,
  .history-v0-event-type--neutral { color: #475569; background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.2); }
  .history-v0-event-type--rejected,
  .history-v0-event-type--error { color: #b91c1c; background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.2); }
  .history-v0-event-type--enrichment { color: #6d28d9; background: rgba(139, 92, 246, 0.12); border-color: rgba(139, 92, 246, 0.22); }

  .history-v0-event-date {
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }

  .history-v0-tech-badge,
  .history-v0-account-badge {
    display: inline-flex;
    align-items: center;
  }

  .history-v0-tech-badge {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    padding: 5px 11px;
    border-radius: 999px;
    font-family: "Fira Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 600;
    line-height: 1.35;
    color: #64748b;
    background: #f8fafc;
    border: 1px solid rgba(203, 213, 225, 0.72);
    white-space: normal;
    word-break: break-all;
  }

  .history-v0-account-badge {
    padding: 3px 8px;
    border-radius: 999px;
    font-family: "Fira Mono", "Consolas", monospace;
    font-size: 10px;
    font-weight: 700;
    line-height: 1.2;
    border: 1px solid rgba(148, 163, 184, 0.22);
  }

  .history-v0-account-badge--engine { color: #4338ca; background: rgba(99, 102, 241, 0.12); border-color: rgba(99, 102, 241, 0.22); }
  .history-v0-account-badge--human { color: #047857; background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.2); }

  .history-v0-party {
    color: var(--text);
    font-size: 13px;
    line-height: 1.5;
  }

  .history-v0-party--supplier {
    font-weight: 900;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .history-v0-party--client {
    color: var(--muted);
    font-weight: 600;
  }

  .history-v0-invoice-number {
    color: #334155;
    font-size: 12px;
    font-weight: 800;
    padding: 3px 9px;
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 999px;
    background: rgba(248, 250, 252, 0.92);
  }

  .history-v0-arrow {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
  }

  .history-v0-summary,
  .history-v0-secondary {
    margin: 0;
    font-size: 13px;
    line-height: 1.55;
  }

  .history-v0-summary {
    color: var(--text);
    font-weight: 700;
    padding-bottom: 2px;
  }

  .history-v0-secondary {
    color: var(--muted);
    margin-top: 0;
    padding-top: 2px;
  }

  .history-v0-meta-wrap {
    justify-content: flex-end;
  }

  .history-v0-actions {
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    gap: 10px;
    flex-wrap: wrap;
  }

  .history-v0-pdf-button {
    min-height: 40px;
    min-width: 122px;
    padding: 0 18px;
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
    background: #ffffff;
    color: #1e293b;
    border-color: rgba(203, 213, 225, 0.95);
  }

  .history-v0-pdf-button:hover {
    background: #f8fafc;
    color: #4f46e5;
    border-color: rgba(99, 102, 241, 0.22);
  }

  .history-v0-delete-button {
    min-height: 40px;
    min-width: 126px;
    padding: 0 18px;
    border-radius: 999px;
    border: 1px solid rgba(239, 68, 68, 0.2);
    background: #ffffff;
    color: #dc2626;
    font-size: 14px;
    font-weight: 700;
    transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
  }

  .history-v0-delete-button:hover {
    transform: translateY(-1px);
    border-color: rgba(239, 68, 68, 0.28);
    background: rgba(239, 68, 68, 0.1);
  }

  .history-v0-pdf-button[disabled] {
    opacity: 0.72;
    cursor: default;
    transform: none;
  }

  .history-v0-inline-note {
    color: #b45309;
    font-size: 12px;
    line-height: 1.5;
  }

  .history-v0-empty {
    display: grid;
    place-items: center;
    gap: 8px;
    padding: 22px;
    border-radius: 22px;
    color: var(--muted);
    text-align: center;
  }

  .history-v0-empty strong {
    color: var(--text);
    font-size: 14px;
    font-weight: 800;
  }

  .history-v0-viewer {
    display: grid;
    gap: 14px;
    padding: 18px;
    border-radius: 28px;
  }

  .history-v0-viewer-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .history-v0-viewer-title {
    margin: 4px 0 0;
    color: var(--text);
    font-size: 22px;
    font-weight: 900;
    letter-spacing: -0.03em;
  }

  .history-v0-viewer-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .history-v0-viewer-button {
    min-height: 38px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 700;
  }

  .history-v0-viewer-frame {
    width: 100%;
    min-height: 72vh;
    border: 1px solid var(--card-border);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.02);
  }

  :root[data-theme="dark"] .history-v0-action-button {
    background: rgba(15, 23, 42, 0.92);
    color: #e2e8f0;
    border-color: rgba(148, 163, 184, 0.28);
  }

  :root[data-theme="dark"] .history-v0-action-button:hover {
    background: rgba(30, 41, 59, 0.96);
    color: #c7d2fe;
    border-color: rgba(99, 102, 241, 0.34);
  }

  :root[data-theme="dark"] .history-v0-filter {
    background: rgba(15, 23, 42, 0.9);
    border-color: rgba(148, 163, 184, 0.22);
  }

  :root[data-theme="dark"] .history-v0-filter.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
  }

  :root[data-theme="dark"] .history-v0-event {
    background: rgba(15, 23, 42, 0.9);
    box-shadow: 0 6px 18px rgba(2, 6, 23, 0.26);
  }

  :root[data-theme="dark"] .history-v0-event:hover {
    background: rgba(15, 23, 42, 0.96);
    border-color: rgba(148, 163, 184, 0.34);
    box-shadow: 0 14px 28px rgba(2, 6, 23, 0.3);
  }

  :root[data-theme="dark"] .history-v0-pdf-button {
    background: rgba(15, 23, 42, 0.92);
    color: #e2e8f0;
    border-color: rgba(148, 163, 184, 0.26);
  }

  :root[data-theme="dark"] .history-v0-delete-button {
    background: rgba(15, 23, 42, 0.92);
    color: #fca5a5;
    border-color: rgba(248, 113, 113, 0.28);
  }

  :root[data-theme="dark"] .history-v0-pdf-button:hover {
    background: rgba(30, 41, 59, 0.94);
    color: #c7d2fe;
    border-color: rgba(99, 102, 241, 0.3);
  }

  :root[data-theme="dark"] .history-v0-delete-button:hover {
    background: rgba(69, 10, 10, 0.28);
    border-color: rgba(248, 113, 113, 0.4);
  }


  @media (max-width: 760px) {
    .history-v0-page {
      width: 100%;
    }

    .history-v0-shell,
    .history-v0-viewer {
      padding: 16px;
      border-radius: 22px;
    }

    .history-v0-toolbar,
    .history-v0-event-top,
    .history-v0-event-middle,
    .history-v0-event-bottom,
    .history-v0-viewer-header {
      align-items: stretch;
    }

    .history-v0-actions {
      width: 100%;
      justify-content: stretch;
    }

    .history-v0-action-button,
    .history-v0-pdf-button,
    .history-v0-viewer-button,
    .history-v0-delete-button {
      width: 100%;
    }

    .history-v0-meta-wrap,
    .history-v0-event-top-right {
      justify-content: flex-start;
    }

  }
`;

function isMeaningful(value) {
  const text = String(value ?? "").trim();
  if (!text) return false;
  const normalized = text.toLowerCase();
  return normalized !== "non renseigne" && normalized !== "non renseigné" && normalized !== "aucun";
}

function cleanText(value) {
  return isMeaningful(value) ? String(value).trim() : "";
}

function normalizeForCompare(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function sameDisplayText(left, right) {
  return normalizeForCompare(left) === normalizeForCompare(right);
}

function repeatsTitle(text, title) {
  if (!text || !title) return false;
  const normalizedText = normalizeForCompare(text).replace(/[.!?…]+$/g, "").trim();
  const normalizedTitle = normalizeForCompare(title).trim();
  return normalizedText === normalizedTitle || normalizedText.startsWith(normalizedTitle);
}

function polishFrenchText(value, fallback = "") {
  let text = String(value ?? fallback ?? "").trim();
  if (!text) return fallback;
  const fixes = [
    ["â€™", "’"],
    ["â€\u009d", ""],
    ["â€œ", ""],
    ["Â·", "·"],
    ["â€¦", "…"],
    ["â†’", "→"],
    ["Ã€", "À"],
    ["Ã©", "é"],
    ["Ã¨", "è"],
    ["Ãª", "ê"],
    ["Ã«", "ë"],
    ["Ã ", "à"],
    ["Ã¢", "â"],
    ["Ã®", "î"],
    ["Ã¯", "ï"],
    ["Ã´", "ô"],
    ["Ã¹", "ù"],
    ["Ã»", "û"],
    ["Ã§", "ç"],
    ["Ã‰", "É"],
  ];
  fixes.forEach(([broken, fixed]) => {
    text = text.replaceAll(broken, fixed);
  });
  return text.replace(/\s*->\s*/g, " → ").replace(/\s+-\s+/g, " · ").replace(/\s+/g, " ").trim();
}

function readNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatSupplierName(value) {
  const text = cleanText(value);
  return text ? polishFrenchText(text).toLocaleUpperCase("fr-FR") : "";
}

function formatEventDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Date inconnue";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return polishFrenchText(raw);
  return new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" }).format(parsed);
}

function resolveParties(event) {
  const supplierRaw = cleanText(event?.supplier);
  const clientRaw = cleanText(event?.client);

  if (supplierRaw && !clientRaw && /\s*(?:->|→)\s*/.test(supplierRaw)) {
    const [supplierPart, ...clientParts] = polishFrenchText(supplierRaw).split(/\s*(?:->|→)\s*/);
    return { supplier: formatSupplierName(supplierPart), client: polishFrenchText(clientParts.join(" → ")) };
  }

  if (!supplierRaw && clientRaw && /\s*(?:->|→)\s*/.test(clientRaw)) {
    const [supplierPart, ...clientParts] = polishFrenchText(clientRaw).split(/\s*(?:->|→)\s*/);
    return { supplier: formatSupplierName(supplierPart), client: polishFrenchText(clientParts.join(" → ")) };
  }

  return { supplier: formatSupplierName(supplierRaw), client: polishFrenchText(clientRaw) };
}

function extractLineLabel(event, title) {
  const fields = [event?.line_label, event?.line_description, event?.description, event?.raw_text, event?.comment];
  for (const field of fields) {
    const text = cleanText(field);
    if (!text) continue;
    const formatted = polishFrenchText(formatHumanReadableText(text));
    if (!formatted || repeatsTitle(formatted, title)) continue;
    const [firstSegment] = formatted.split(/\s*[·•]\s*/);
    const candidate = polishFrenchText(firstSegment || formatted);
    if (candidate && !repeatsTitle(candidate, title) && candidate.length > 2) return candidate;
  }
  return "";
}

function formatTechnicalText(value) {
  const text = cleanText(value);
  if (!text) return "";
  return polishFrenchText(text);
}

function getEventPresentation(eventType) {
  const normalized = normalizeForCompare(eventType);
  if (normalized === "invoice analyzed" || normalized === "facture analysee") return { title: "Facture analysée", kind: "analysis", category: "ai-events" };
  if (normalized === "auto validated" || normalized === "facture auto validee") return { title: "Événement IA", kind: "neutral", category: "ai-events" };
  if (normalized === "sent to human validation" || normalized === "ligne envoyee validation" || normalized === "line sent validation") return { title: "Ligne envoyée en validation", kind: "review", category: "validations" };
  if (normalized === "human validated" || normalized === "line validated") return { title: "Ligne validée", kind: "validated", category: "validations" };
  if (normalized === "human corrected" || normalized === "correction humaine" || normalized === "human correction" || normalized === "line corrected") return { title: "Correction humaine appliquée", kind: "corrected", category: "human-corrections" };
  if (normalized === "marked non comptable" || normalized === "line marked non accounting") return { title: "Ligne marquée non comptable", kind: "non-comptable", category: "human-corrections" };
  if (normalized === "rejected") return { title: "Erreur de traitement", kind: "rejected", category: "errors" };
  if (normalized === "enrichment proposed" || normalized === "candidat memoire" || normalized === "memory candidate created") return { title: "Enrichissement IA", kind: "enrichment", category: "ai-events" };
  if (normalized.includes("error") || normalized === "erreur analyse" || normalized === "analysis error") return { title: "Erreur de traitement", kind: "error", category: "errors" };
  return { title: "Événement IA", kind: "neutral", category: "ai-events" };
}

function EventIcon({ kind }) {
  const iconProps = { size: 14, strokeWidth: 2.1 };
  if (kind === "analysis") return <Brain {...iconProps} />;
  if (kind === "review") return <Clock3 {...iconProps} />;
  if (kind === "validated") return <CheckCircle2 {...iconProps} />;
  if (kind === "corrected") return <UserCheck {...iconProps} />;
  if (kind === "non-comptable") return <FileText {...iconProps} />;
  if (kind === "enrichment") return <AlertTriangle {...iconProps} />;
  if (kind === "rejected" || kind === "error") return <XCircle {...iconProps} />;
  return <FileText {...iconProps} />;
}

function buildInvoiceAnalysisSummary(event) {
  const totalLines = readNumber(event?.total_lines) ?? readNumber(event?.line_count) ?? readNumber(event?.lines_count) ?? readNumber(event?.summary?.total_lines) ?? readNumber(event?.summary?.line_count);
  const autoOk = readNumber(event?.auto_ok) ?? readNumber(event?.summary?.auto_ok);
  const toValidate = readNumber(event?.validation_humaine) ?? readNumber(event?.to_validate) ?? readNumber(event?.pending_validation) ?? readNumber(event?.summary?.validation_humaine) ?? readNumber(event?.summary?.to_validate);
  const rejected = readNumber(event?.rejected) ?? readNumber(event?.rejeter) ?? readNumber(event?.rejected_count) ?? readNumber(event?.summary?.rejected) ?? readNumber(event?.summary?.rejected_count);
  const nonComptable = readNumber(event?.non_comptable) ?? readNumber(event?.summary?.non_comptable);
  const parts = [];
  if (totalLines) parts.push(`${totalLines} lignes traitées`);
  if (autoOk) parts.push(`${autoOk} auto-validée${autoOk > 1 ? "s" : ""}`);
  if (toValidate) parts.push(`${toValidate} à valider`);
  if (rejected) parts.push(`${rejected} rejetée${rejected > 1 ? "s" : ""}`);
  if (nonComptable) parts.push(`${nonComptable} non comptable${nonComptable > 1 ? "s" : ""}`);
  return parts.join(" · ");
}

function buildSummary(event, presentation) {
  const lineLabel = extractLineLabel(event, presentation.title);
  const engineAccount = cleanText(event?.engine_account);
  const humanAccount = cleanText(event?.human_account);

  if (presentation.kind === "analysis") {
    const summary = buildInvoiceAnalysisSummary(event);
    if (summary) return summary;
  }
  if (presentation.kind === "review") return [lineLabel, engineAccount ? `Compte moteur ${engineAccount}` : "", "À valider"].filter(Boolean).join(" · ");
  if (presentation.kind === "validated") return [lineLabel, humanAccount || engineAccount ? `Compte ${humanAccount || engineAccount} confirmé` : "", "Validation humaine"].filter(Boolean).join(" · ");
  if (presentation.kind === "corrected") {
    if (engineAccount && humanAccount && !sameDisplayText(engineAccount, humanAccount)) return `Compte ${engineAccount} → ${humanAccount} · Correction humaine`;
    return [lineLabel, humanAccount ? `Nouveau compte ${humanAccount}` : "", "Correction humaine"].filter(Boolean).join(" · ");
  }
  if (presentation.kind === "non-comptable") return lineLabel ? `${lineLabel} · Hors périmètre comptable` : "Hors périmètre comptable";
  if (presentation.kind === "rejected") return lineLabel ? `${lineLabel} · Rejet de sécurité` : "Rejet de sécurité";
  if (presentation.kind === "enrichment") return lineLabel ? `${lineLabel} · Candidat à enrichir` : "Proposition d’enrichissement préparée";
  if (presentation.kind === "error") {
    const message = cleanText(event?.message) || cleanText(event?.comment);
    const formatted = polishFrenchText(formatHumanReadableText(message));
    if (formatted && !repeatsTitle(formatted, presentation.title)) return formatted;
    return "Erreur pendant le traitement";
  }
  const fallbackCandidates = [cleanText(event?.message), cleanText(event?.raw_text), cleanText(event?.comment)].map((value) => polishFrenchText(formatHumanReadableText(value))).filter(Boolean);
  return fallbackCandidates.find((text) => !repeatsTitle(text, presentation.title)) || "";
}

function buildSecondaryText(event, summaryText, titleText) {
  const candidates = [cleanText(event?.comment), cleanText(event?.message), cleanText(event?.raw_text)]
    .map((value) => polishFrenchText(cleanSummaryText(value, event) || formatHumanReadableText(value)))
    .filter(Boolean);
  return candidates.find((value) => !repeatsTitle(value, titleText) && !sameDisplayText(value, summaryText) && !summaryText.includes(value)) || "";
}

function getEventInvoiceId(event) {
  return event?.invoice_id || event?.id || event?._id || event?.doc_id || null;
}


function isPdfOpenableFromDebug(debug) {
  if (!debug || typeof debug !== "object") return false;
  if (debug.exists_on_disk) return true;
  if (String(debug.resolved_kind || "").trim().toLowerCase() === "couch_attachment") return true;
  const relatedDocSuccess = debug.related_doc_success && typeof debug.related_doc_success === "object" ? debug.related_doc_success : null;
  return Boolean(relatedDocSuccess && (relatedDocSuccess.used_attachment || relatedDocSuccess.exists_on_disk || relatedDocSuccess.resolved_kind));
}

const FILTERS = [
  { key: "all", label: "Tous" },
  { key: "validations", label: "Validations humaines" },
  { key: "human-corrections", label: "Corrections humaines" },
  { key: "ai-events", label: "Événements IA" },
  { key: "errors", label: "Erreurs" },
];

function getLastActivityInfo(events) {
  const latest = Array.isArray(events) && events.length ? events[0] : null;
  if (!latest) return { value: "Aucune", detail: "Aucune activité enregistrée" };
  const parsed = new Date(latest.created_at || latest.date || latest.timestamp || "");
  if (Number.isNaN(parsed.getTime())) {
    return { value: "Récente", detail: formatWorkflowSource(latest.source || "") };
  }
  return {
    value: new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(parsed),
    detail: `${new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(parsed)} · ${formatWorkflowSource(latest.source || "")}`,
  };
}
export default function HistoryPage() {
  const { searchQuery, clearSearch } = useGlobalSearch();
  const [activeFilter, setActiveFilter] = useState("all");
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [pdfViewerUrl, setPdfViewerUrl] = useState("");
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [pdfViewerLabel, setPdfViewerLabel] = useState("");
  const [pdfStatusByEvent, setPdfStatusByEvent] = useState({});
  const [hiddenEventIds, setHiddenEventIds] = useState(() =>
    readPersistentHiddenIds(HISTORY_HIDDEN_EVENTS_KEY),
  );

  const loadHistory = async (options = {}) => {
    const silent = options?.silent === true;
    if (!silent) setLoading(true);
    setErrorMessage("");
    try {
      const payload = await fetchWorkflowHistory({ limit: 200 });
      const nextEvents = Array.isArray(payload?.events)
        ? payload.events
        : Array.isArray(payload)
          ? payload
          : [];
      const sortedEvents = [...nextEvents].sort((left, right) => {
        const leftTime = Date.parse(left?.created_at || left?.date || left?.timestamp || 0);
        const rightTime = Date.parse(right?.created_at || right?.date || right?.timestamp || 0);
        return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
      });
      setEvents(sortedEvents);

    } catch (error) {
      setErrorMessage(polishFrenchText(error?.message || "Impossible de charger l’historique."));
      if (!silent) setEvents([]);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    void loadHistory();
    const refreshHistory = () => {
      void loadHistory({ silent: true });
    };
    const resetHistory = () => {
      setEvents([]);
      setActiveFilter("all");
      setErrorMessage("");
      setConfirmPurge(false);
      setHiddenEventIds([]);
      try {
        window.localStorage.removeItem(HISTORY_HIDDEN_EVENTS_KEY);
      } catch {
        // Keep the UI reset available in restricted browser contexts.
      }
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void loadHistory({ silent: true });
    };
    const refreshInterval = window.setInterval(
      () => void loadHistory({ silent: true }),
      5000,
    );
    window.addEventListener("keymanage:validated-accounting-entry", refreshHistory);
    window.addEventListener("keymanage:human-validation-updated", refreshHistory);
    window.addEventListener("keymanage:analysis-history-updated", refreshHistory);
    window.addEventListener("keymanage:test-session-reset", resetHistory);
    window.addEventListener("storage", refreshHistory);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(refreshInterval);
      window.removeEventListener("keymanage:validated-accounting-entry", refreshHistory);
      window.removeEventListener("keymanage:human-validation-updated", refreshHistory);
      window.removeEventListener("keymanage:analysis-history-updated", refreshHistory);
      window.removeEventListener("keymanage:test-session-reset", resetHistory);
      window.removeEventListener("storage", refreshHistory);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, []);

  const preparedEvents = useMemo(() => {
    return events.map((event, index) => {
      const presentation = getEventPresentation(event?.event_type || event?.type || event?.status || "");
      const summary = polishFrenchText(buildSummary(event, presentation));
      const secondary = polishFrenchText(buildSecondaryText(event, summary, presentation.title));
      const { supplier, client } = resolveParties(event);
      const invoiceId = getEventInvoiceId(event);
      const invoiceNumber = cleanText(event?.invoice_number || event?.invoiceNumber || event?.number);
      const technicalValue = cleanText(event?.line_id) || cleanText(event?.event_id);
      const technicalBadge = technicalValue ? formatTechnicalText(technicalValue) : "";
      const technicalTitle = technicalValue ? polishFrenchText(technicalValue) : "";
      const engineAccount = cleanText(event?.engine_account);
      const humanAccount = cleanText(event?.human_account);
      return {
        id: String(event?.event_id || event?.id || `${invoiceId || "event"}-${index}`),
        raw: event,
        title: presentation.title,
        kind: presentation.kind,
        category: presentation.category,
        summary,
        secondary,
        supplier,
        client,
        invoiceId,
        invoiceNumber,
        dateLabel: formatEventDate(event?.created_at || event?.date || event?.timestamp),
        technicalBadge,
        technicalTitle,
        engineAccount,
        humanAccount,
      };
    }).filter((event) => !hiddenEventIds.includes(event.id));
  }, [events, hiddenEventIds]);

  const counters = useMemo(() => {
    const base = { all: preparedEvents.length, validations: 0, "human-corrections": 0, "ai-events": 0, errors: 0 };
    preparedEvents.forEach((event) => {
      if (event.category in base) {
        base[event.category] += 1;
      }
    });
    return base;
  }, [preparedEvents]);

  const filteredEvents = useMemo(() => {
    const byFilter =
      activeFilter === "all"
        ? preparedEvents
        : preparedEvents.filter((event) => event.category === activeFilter);
    return byFilter.filter((event) => matchesGlobalSearch(event, searchQuery));
  }, [activeFilter, preparedEvents, searchQuery]);

  const openPdfForEvent = async (eventItem) => {
    if (!eventItem?.invoiceId) return;

    setErrorMessage("");
    setPdfStatusByEvent((current) => ({
      ...current,
      [eventItem.id]: { state: "loading", message: "" },
    }));

    try {
      const debug = await fetchInvoicePdfDebug(eventItem.invoiceId);
      if (!isPdfOpenableFromDebug(debug)) {
        throw new Error("PDF indisponible pour cette facture.");
      }
      const nextUrl = `${API_BASE_URL}/api/analysis/invoice-pdf/${encodeURIComponent(eventItem.invoiceId)}`;
      setPdfViewerUrl(nextUrl);
      setPdfViewerLabel(eventItem.invoiceId || "Document source");
      setShowPdfViewer(true);
      setPdfStatusByEvent((current) => ({
        ...current,
        [eventItem.id]: { state: "ready", message: "" },
      }));
    } catch (error) {
      const message = polishFrenchText(error?.message || "PDF indisponible pour cette facture.");
      setPdfStatusByEvent((current) => ({
        ...current,
        [eventItem.id]: { state: "error", message },
      }));
      setErrorMessage(message);
    }
  };

  const closeViewer = () => {
    setShowPdfViewer(false);
  };

  const handleHideEvent = (eventId) => {
    if (!eventId) return;
    const confirmed = window.confirm("Voulez-vous masquer cet événement de l’historique affiché ?");
    if (!confirmed) return;
    addPersistentHiddenId(HISTORY_HIDDEN_EVENTS_KEY, eventId);
    setHiddenEventIds((current) => (current.includes(eventId) ? current : [...current, eventId]));
  };

  const handlePurgeAll = async () => {
    setConfirmPurge(false);
    setLoading(true);
    try {
      await clearWorkflowHistory();
      setEvents([]);
      setHiddenEventIds([]);
      try { window.localStorage.removeItem(HISTORY_HIDDEN_EVENTS_KEY); } catch { /* ignore */ }
    } catch (error) {
      setErrorMessage(error?.message || "Impossible de vider l'historique.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-stack history-page">
      <style>{HISTORY_V0_STYLES}</style>

      {showPdfViewer && pdfViewerUrl ? (
        <section className="history-v0-viewer">
          <div className="history-v0-viewer-header">
            <div>
              <div className="history-v0-breadcrumb">Document source</div>
              <h2 className="history-v0-viewer-title">{pdfViewerLabel || "Aperçu du document source"}</h2>
            </div>

            <div className="history-v0-viewer-actions">
              <button
                type="button"
                className="history-v0-viewer-button"
                onClick={() => window.open(pdfViewerUrl, "_blank", "noopener,noreferrer")}
              >
                Ouvrir dans un nouvel onglet
              </button>
              <button type="button" className="history-v0-viewer-button" onClick={closeViewer}>
                <X size={14} />
                Fermer
              </button>
            </div>
          </div>

          <iframe title="Document source" src={pdfViewerUrl} className="history-v0-viewer-frame" />
        </section>
      ) : null}

      <div className="history-v0-page">
        <section className="history-v0-shell">
          <div className="history-v0-filters">
            {FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                className={`history-v0-filter ${activeFilter === filter.key ? "active" : ""}`}
                onClick={() => setActiveFilter(filter.key)}
              >
                <span className={`history-v0-filter-dot history-v0-filter-dot--${filter.key}`} />
                <span className="history-v0-filter-label">{filter.label}</span>
                <span className="history-v0-filter-count">{counters[filter.key] ?? 0}</span>
              </button>
            ))}
          </div>

          <div className="history-v0-toolbar">
            <button type="button" className="history-v0-action-button" onClick={loadHistory} disabled={loading}>
              <RefreshCcw size={14} className={loading ? "animate-spin" : ""} />
              {loading ? "Actualisation..." : "Actualiser"}
            </button>
            {confirmPurge ? (
              <>
                <span style={{fontSize:"12px",fontWeight:700,color:"#dc2626",whiteSpace:"nowrap"}}>Purger tout l'historique ?</span>
                <button type="button" className="history-v0-delete-button" style={{minWidth:"auto",padding:"0 14px",fontSize:12}} onClick={handlePurgeAll}>Confirmer</button>
                <button type="button" className="history-v0-action-button" style={{minWidth:"auto",padding:"0 12px",fontSize:12}} onClick={() => setConfirmPurge(false)}>Annuler</button>
              </>
            ) : (
              <button type="button" className="history-v0-delete-button" style={{minWidth:"auto",padding:"0 14px",fontSize:12,display:"inline-flex",alignItems:"center",gap:6}} onClick={() => setConfirmPurge(true)}>
                <Trash2 size={13} /> Tout purger
              </button>
            )}
          </div>

          {errorMessage ? (
            <div className="history-v0-alert">
              <AlertTriangle size={15} />
              <span>{errorMessage}</span>
            </div>
          ) : null}

          {loading ? (
            <div className="history-v0-empty">
              <LoaderCircle size={18} className="animate-spin" />
              <strong>Chargement de l’historique...</strong>
              <span>Les événements réels du workflow IA arrivent ici.</span>
            </div>
          ) : filteredEvents.length ? (
            <div className="history-v0-events">
              {filteredEvents.map((event) => {
                const pdfState = pdfStatusByEvent[event.id] || { state: "idle", message: "" };
                const pdfButtonLabel = pdfState.state === "loading" ? "Ouverture..." : "Voir PDF";

                return (
                  <article key={event.id} className={`history-v0-event history-v0-event--${event.kind}`}>
                    <div className="history-v0-event-top">
                      <div className="history-v0-event-top-left">
                        <span className={`history-v0-event-type history-v0-event-type--${event.kind}`}>
                          <EventIcon kind={event.kind} />
                          {event.title}
                        </span>
                      </div>

                      <div className="history-v0-event-top-right">
                        <div className="history-v0-actions">
                          {event.invoiceId ? (
                            <button
                              type="button"
                              className="history-v0-pdf-button"
                              onClick={() => openPdfForEvent(event)}
                              disabled={pdfState.state === "loading"}
                            >
                              {pdfButtonLabel}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            className="history-v0-delete-button"
                            onClick={() => handleHideEvent(event.id)}
                          >
                            Supprimer
                          </button>
                        </div>
                      </div>
                    </div>

                    {(event.supplier || event.client || event.invoiceNumber) ? (
                      <div className="history-v0-event-middle">
                        <div className="history-v0-event-middle-left">
                          {event.supplier ? <span className="history-v0-party history-v0-party--supplier">{event.supplier}</span> : null}
                          {event.client ? <span className="history-v0-arrow">→</span> : null}
                          {event.client ? <span className="history-v0-party history-v0-party--client">{event.client}</span> : null}
                          {event.invoiceNumber ? <span className="history-v0-invoice-number">Facture n° {event.invoiceNumber}</span> : null}
                        </div>
                      </div>
                    ) : null}

                    <div className="history-v0-event-bottom">
                      <div className="history-v0-event-bottom-left">
                        {event.summary ? <p className="history-v0-summary">{event.summary}</p> : null}
                        {event.secondary ? <p className="history-v0-secondary">{event.secondary}</p> : null}
                      </div>
                    </div>

                    {pdfState.state === "error" && pdfState.message ? (
                      <div className="history-v0-inline-note">{pdfState.message}</div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="history-v0-empty">
              <FileText size={18} />
              <strong>
                {searchQuery
                  ? `Aucune facture ni analyse ne correspond à « ${searchQuery} ».`
                  : preparedEvents.length
                    ? "Aucun événement pour ce filtre"
                    : "Aucun événement enregistré"}
              </strong>
              {searchQuery ? (
                <button type="button" className="history-v0-reset-search" onClick={clearSearch}>
                  Réinitialiser la recherche
                </button>
              ) : (
                <span>
                  {preparedEvents.length
                    ? "Essayez un autre filtre pour retrouver les événements recherchés."
                    : "Les événements IA, validations humaines et corrections humaines apparaîtront ici au fil du workflow."}
                </span>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}





