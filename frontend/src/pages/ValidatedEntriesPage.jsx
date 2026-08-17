import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, CheckCircle2, Download, Eye, FileText, Pencil, Trash2, X, AlertTriangle, RotateCcw } from "lucide-react";
import { useGlobalSearch } from "../context/SearchContext";
import { matchesGlobalSearch } from "../utils/search";
import { API_BASE_URL, fetchInvoicePdfPreview, fetchValidatedEntries, deleteHumanValidationItem, createHumanValidationItem } from "../services/api";
import { isSuccessfulOrMissingDeletion } from "../utils/apiErrors";
import { clearValidatedSessionStorage, getValidatedInvoiceKey, readValidatedEntries, removeValidatedInvoice } from "../utils/validatedEntries";

const value = (input, fallback = "Non renseigné") => String(input ?? "").trim() || fallback;
const keyOf = (entry) => String(entry?.invoice_group_id || entry?.invoice_id || getValidatedInvoiceKey(entry) || "").trim();
const accountOf = (line) => String(line?.corrected_account || line?.recommended_account || line?.accounting_account || line?.account || "").trim();
const accountLabelOf = (line) => value(line?.corrected_account_label || line?.account_label || line?.recommended_account_label, "Compte comptable validé");
const dateOf = (entry) => { const raw = entry?.invoice_date || entry?.date || entry?.validated_at; if (!raw) return "Date inconnue"; const date = new Date(raw); return Number.isNaN(date.getTime()) ? value(raw) : new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" }).format(date); };
function groupEntries(entries) { const groups = new Map(); entries.forEach((entry) => { const key = keyOf(entry); if (!key) return; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(entry); }); return [...groups].map(([key, lines]) => ({ ...lines[0], invoice_group_id: key, lines })); }
function mergeEntries(localEntries, remoteEntries) { const byLine = new Map(); [...localEntries, ...remoteEntries].forEach((entry) => { const id = String(entry?.validated_entry_id || entry?.validation_id || entry?.line_id || entry?.id || (keyOf(entry) + "-" + (entry?.raw_text || entry?.description || "line"))); byLine.set(id, { ...byLine.get(id), ...entry }); }); return [...byLine.values()]; }
function amount(line, names, fallback = 0) { const raw = names.map((name) => line?.[name]).find((candidate) => candidate !== undefined && candidate !== null && candidate !== ""); const parsed = Number(raw); return Number.isFinite(parsed) ? parsed : fallback; }

function pdfInvoiceIdOf(entry) {
  const lines = Array.isArray(entry?.lines) ? entry.lines : [];
  const candidates = [
    entry?.invoice_id,
    entry?.source_invoice_id,
    entry?.doc_id,
    entry?.invoice_group_id,
    ...lines.flatMap((line) => [line?.invoice_id, line?.source_invoice_id, line?.doc_id]),
  ];
  return String(candidates.find((candidate) => String(candidate || "").trim()) || "").trim();
}
function isPdfOpenableFromDebug(debug) {
  if (!debug || typeof debug !== "object") return false;
  if (debug.exists_on_disk) return true;
  if (String(debug.resolved_kind || "").trim().toLowerCase() === "couch_attachment") return true;
  const related = debug.related_doc_success && typeof debug.related_doc_success === "object" ? debug.related_doc_success : null;
  return Boolean(related && (related.used_attachment || related.exists_on_disk || related.resolved_kind));
}
const euro = (number) => Number(number || 0).toFixed(2).replace(".", ",") + " €";
const csvCell = (input) => "\"" + String(input ?? "").replaceAll("\"", "\"\"") + "\"";
function exportCsv(invoices) { const rows = [["Fournisseur", "N° facture", "Client / dossier", "Date", "Ligne", "Compte", "Libellé compte", "HT", "TVA", "TTC"]]; invoices.forEach((invoice) => invoice.lines.forEach((line) => rows.push([invoice.supplier, invoice.invoice_number || invoice.invoice_id, invoice.client, dateOf(invoice), line.raw_text || line.description || line.article_source, accountOf(line), accountLabelOf(line), amount(line, ["ht", "amount_ht", "total_ht"]), amount(line, ["vat", "tva", "amount_tva"]), amount(line, ["ttc", "amount_ttc", "total_ttc"])]))); const blob = new Blob(["\ufeff" + rows.map((row) => row.map(csvCell).join(";")).join("\n")], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "ecritures-comptabilisees.csv"; anchor.click(); URL.revokeObjectURL(url); }

function LinePopover({ line }) { const ht = amount(line, ["ht", "amount_ht", "total_ht"], 29.99); const vat = amount(line, ["vat", "tva", "amount_tva"], ht * 0.2); const ttc = amount(line, ["ttc", "amount_ttc", "total_ttc"], ht + vat); return <div className="ve-line-popover"><div className="ve-ocr-text">Texte OCR original : {value(line.raw_text || line.description || line.article_source, "Ligne sans libellé")}</div><p className="ve-account-description"><strong>Description du compte {value(accountOf(line), "—")} :</strong> {accountLabelOf(line)}.</p><dl className="ve-amounts"><div><dt>HT</dt><dd>{euro(ht)}</dd></div><div><dt>TVA (20%)</dt><dd>{euro(vat)}</dd></div><div className="ve-amount-total"><dt>TTC</dt><dd>{euro(ttc)}</dd></div></dl><button type="button" className="ve-btn ve-btn-ghost ve-edit-button"><Pencil size={14} /> Edit</button></div>; }

function AuditModal({ invoice, onClose }) {
  const [openLine, setOpenLine] = useState(0);
  const isAutoValidated = invoice.lines.every(
    (line) => line?.auto_validated === true && line?.human_intervention !== true,
  );
  return <div className="ve-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="ve-modal-panel ve-audit-panel" role="dialog" aria-modal="true"><header className="ve-modal-head"><div><h2 className="ve-modal-title">Audit de la facture</h2><p className="ve-modal-subtitle">{value(invoice.supplier)} · {invoice.lines.length} ligne(s)</p></div><button className="ve-modal-close" type="button" onClick={onClose} aria-label="Fermer"><X size={19} /></button></header><div className="ve-modal-body"><div className="ve-confirmation"><CheckCircle2 size={19} /><strong>{isAutoValidated ? "Facture auto-validée par l’IA" : "Facture validée par humain"}</strong><span>Statut COMPTABILISEE · confiance finale 100%</span></div><h3 className="ve-audit-heading">Piste d’audit · lignes facture</h3><div className="ve-audit-lines">{invoice.lines.map((line, index) => <div className="ve-audit-line-wrap" key={line.validation_id || line.validated_entry_id || index}><button type="button" className={"ve-audit-line " + (openLine === index ? "is-open" : "")} onClick={() => setOpenLine(openLine === index ? -1 : index)}><span className="ve-audit-line-copy"><strong>{index + 1}. {value(line.raw_text || line.description || line.article_source)}</strong><small>Compte {value(accountOf(line), "—")}</small></span><span className="ve-human-badge"><CheckCircle2 size={14} /> {line?.auto_validated === true && line?.human_intervention !== true ? "AUTO-VALIDÉE PAR L’IA" : "VALIDÉ PAR HUMAIN"} <ChevronDown size={16} /></span></button>{openLine === index && <LinePopover line={line} />}</div>)}</div></div></section></div>;
}


function PdfPreviewModal({ pages, label, onClose }) {
  return <div className="ve-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="ve-modal-panel ve-pdf-modal-panel" role="dialog" aria-modal="true"><header className="ve-modal-head"><div><h2 className="ve-modal-title">Aperçu de la facture</h2><p className="ve-modal-subtitle">{value(label, "Document source")}</p></div><button className="ve-modal-close" type="button" onClick={onClose} aria-label="Fermer"><X size={19} /></button></header><div className="ve-pdf-preview-pages">{pages.map((pageUrl, index) => <img key={pageUrl} src={pageUrl} alt={`Page ${index + 1} de la facture`} className="ve-pdf-preview-page" />)}</div></section></div>;
}
export default function ValidatedEntriesPage() {
  const { searchQuery } = useGlobalSearch(); const [entries, setEntries] = useState(() => readValidatedEntries()); const [selectedInvoice, setSelectedInvoice] = useState(null); const [pendingPurge, setPendingPurge] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [pdfViewerPages, setPdfViewerPages] = useState([]); const [pdfViewerLabel, setPdfViewerLabel] = useState(""); const [pdfLoadingId, setPdfLoadingId] = useState(""); const [notice, setNotice] = useState("");
  const resetVersionRef = useRef(0);
  const reload = async () => { const resetVersion = resetVersionRef.current; const local = readValidatedEntries(); if (resetVersion !== resetVersionRef.current) return; setEntries(local); try { const remote = await fetchValidatedEntries(); if (resetVersion !== resetVersionRef.current) return; setEntries(mergeEntries(local, remote?.items || [])); } catch (remoteError) { if (resetVersion !== resetVersionRef.current) return; if (!local.length) setError(remoteError.message || "Impossible de charger les écritures."); } };
  useEffect(() => { void reload(); const refresh = () => void reload(); window.addEventListener("keymanage:validated-accounting-entry", refresh); return () => window.removeEventListener("keymanage:validated-accounting-entry", refresh); }, []);
  useEffect(() => {
    const resetAfterSessionClear = () => {
      resetVersionRef.current += 1;
      setEntries([]);
      setSelectedInvoice(null);
      setPendingPurge(false);
      setPdfViewerPages([]);
      setError("");
      setNotice("");
      clearValidatedSessionStorage();
    };
    window.addEventListener("keymanage:all-saved-invoices-purged", resetAfterSessionClear);
    window.addEventListener("keymanage:test-session-reset", resetAfterSessionClear);
    return () => {
      window.removeEventListener("keymanage:all-saved-invoices-purged", resetAfterSessionClear);
      window.removeEventListener("keymanage:test-session-reset", resetAfterSessionClear);
    };
  }, []);
  const invoices = useMemo(() => groupEntries(entries).filter((invoice) => matchesGlobalSearch(invoice, searchQuery)), [entries, searchQuery]); const lineCount = invoices.reduce((total, invoice) => total + invoice.lines.length, 0); const notifyMemory = () => window.dispatchEvent(new Event("keymanage:performance-refresh"));
  const handleSendBackToValidation = async (invoice) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await Promise.all(invoice.lines.map((line) => {
        const { validation_id: _oldValidationId, validated_entry_id: _oldEntryId, ...lineData } = line;
        return createHumanValidationItem({
          ...invoice,
          ...lineData,
          invoice_group_id: invoice.invoice_group_id,
          workflow_status: "A_CONTROLER",
          status: "pending_validation",
          human_validation_result: null,
        });
      }));
      const oldIds = invoice.lines.map((line) => line.validation_id).filter(Boolean);
      const deletions = await Promise.allSettled(oldIds.map((id) => deleteHumanValidationItem(id)));
      const failedDeletion = deletions.find((result) => !isSuccessfulOrMissingDeletion(result));
      if (failedDeletion) throw failedDeletion.reason || new Error("Le transfert de la facture a échoué.");
      removeValidatedInvoice(invoice);
      setEntries((current) => current.filter((entry) => keyOf(entry) !== invoice.invoice_group_id));
      setSelectedInvoice(null);
      setNotice("Facture renvoyée dans la file de validation humaine.");
      window.dispatchEvent(new Event("keymanage:human-validation-updated"));
      notifyMemory();
    } catch (transferError) {
      setError(transferError?.message || "Impossible de renvoyer la facture vers la validation humaine.");
    } finally {
      setBusy(false);
    }
  };  const removeInvoice = async (invoice) => { setBusy(true); setError(""); const ids = invoice.lines.map((line) => line.validation_id).filter(Boolean); const results = await Promise.allSettled(ids.map((id) => deleteHumanValidationItem(id))); const failed = results.find((result) => !isSuccessfulOrMissingDeletion(result)); if (failed) { setError(failed.reason?.message || "La suppression backend a échoué."); setBusy(false); return; } removeValidatedInvoice(invoice); setEntries((current) => current.filter((entry) => keyOf(entry) !== invoice.invoice_group_id)); setSelectedInvoice((current) => current?.invoice_group_id === invoice.invoice_group_id ? null : current); notifyMemory(); setBusy(false); };
  const purgeAll = async () => { setBusy(true); setError(""); const ids = entries.map((line) => line.validation_id).filter(Boolean); const results = await Promise.allSettled(ids.map((id) => deleteHumanValidationItem(id))); const deletionById = new Map(ids.map((id, index) => [id, results[index]])); const removableInvoices = invoices.filter((invoice) => invoice.lines.every((line) => !line.validation_id || isSuccessfulOrMissingDeletion(deletionById.get(line.validation_id)))); const removableKeys = new Set(removableInvoices.map((invoice) => invoice.invoice_group_id)); removableInvoices.forEach(removeValidatedInvoice); setEntries((current) => current.filter((entry) => !removableKeys.has(keyOf(entry)))); setPendingPurge(false); const failed = results.find((result) => !isSuccessfulOrMissingDeletion(result)); if (failed) setError(failed.reason?.message || "Certaines lignes n’ont pas pu être supprimées."); notifyMemory(); setBusy(false); };
  const openPdf = async (invoice) => {
    const invoiceId = pdfInvoiceIdOf(invoice);
    if (!invoiceId) { setError("Identifiant de facture manquant."); return; }
    setError("");
    setPdfLoadingId(invoiceId);
    try {
      const preview = await fetchInvoicePdfPreview(invoiceId);
      const pageCount = Math.max(0, Number(preview?.page_count || 0));
      if (!pageCount) throw new Error("Document source non disponible pour cette facture.");
      const previewBase = `${API_BASE_URL}/api/analysis/invoice-pdf-preview/${encodeURIComponent(invoiceId)}/pages`;
      setPdfViewerLabel(invoice.invoice_number || invoice.supplier || "Document source");
      setPdfViewerPages(Array.from({ length: pageCount }, (_, index) => `${previewBase}/${index + 1}`));
    } catch (pdfError) {
      setError(String(pdfError?.message || "Document source non disponible pour cette facture.").trim());
    } finally {
      setPdfLoadingId("");
    }
  };
  return <div className="validated-entries-page"><div className="validated-entries-badges-row"><span className="ve-badge ve-badge-blue">{invoices.length} facture{invoices.length > 1 ? "s" : ""} comptabilisée{invoices.length > 1 ? "s" : ""}</span><span className="ve-badge ve-badge-indigo">{lineCount} ligne{lineCount > 1 ? "s" : ""} comptable{lineCount > 1 ? "s" : ""}</span><div className="ve-purge-zone"><button type="button" className="ve-btn ve-btn-primary" onClick={() => exportCsv(invoices)} disabled={!invoices.length}><Download size={15} /> Exporter FEC / CSV</button><button type="button" className="ve-btn ve-btn-ghost" onClick={() => setPendingPurge(true)} disabled={!invoices.length || busy}><Trash2 size={15} /> Tout purger</button></div></div>{error && <div className="ve-error"><AlertTriangle size={17} /> {error}</div>}{notice && <div className="ve-success" style={{ margin: "12px 0", padding: "10px 14px", borderRadius: "12px", background: "#dcfce7", color: "#166534", fontWeight: 700 }}>{notice}</div>}{!invoices.length ? <div className="validated-empty-state"><FileText size={30} /><strong>Aucune écriture comptabilisée</strong><span>Les factures validées par un humain apparaîtront ici.</span></div> : <div className="validated-entry-list">{invoices.map((invoice) => <article className="validated-entry-card" key={invoice.invoice_group_id}><div className="validated-entry-card-head"><div className="ve-card-left"><span className="validated-entry-eyebrow">🟢 COMPTABILISÉE</span><h2>{value(invoice.supplier)}</h2><p>{value(invoice.invoice_number || invoice.invoice_id)} · {invoice.lines.length} ligne{invoice.lines.length > 1 ? "s" : ""} · {value(invoice.client, "Dossier non renseigné")} · {dateOf(invoice)}</p></div><div className="ve-card-meta"><span className="ve-account-label">Compte principal</span><strong className="ve-account-number">{value(accountOf(invoice.lines[0]), "—")}</strong><span className="ve-account-sublabel">{accountLabelOf(invoice.lines[0])}</span></div></div><div className="validated-entry-card-actions"><button className="ve-btn ve-btn-primary" type="button" onClick={() => setSelectedInvoice(invoice)}><Eye size={15} /> Voir détail</button><button className="ve-btn ve-btn-ghost" type="button" onClick={() => void openPdf(invoice)} disabled={!pdfInvoiceIdOf(invoice) || pdfLoadingId === pdfInvoiceIdOf(invoice)} title={pdfInvoiceIdOf(invoice) ? "Afficher le PDF dans l’application" : "PDF non disponible pour cette facture"}><FileText size={15} /> {pdfLoadingId === pdfInvoiceIdOf(invoice) ? "Ouverture..." : "Voir PDF"}</button><button type="button" className="ve-btn warning-btn" onClick={() => void handleSendBackToValidation(invoice)} disabled={busy}><RotateCcw size={15} aria-hidden="true" /> Renvoyer vers validation humaine</button><button className="ve-btn ve-btn-danger-ghost" type="button" onClick={() => void removeInvoice(invoice)} disabled={busy}><Trash2 size={15} /> Supprimer</button></div></article>)}</div>}{selectedInvoice && <AuditModal invoice={selectedInvoice} onClose={() => setSelectedInvoice(null)} />}{pdfViewerPages.length > 0 && <PdfPreviewModal pages={pdfViewerPages} label={pdfViewerLabel} onClose={() => setPdfViewerPages([])} />}{pendingPurge && <div className="ve-modal-backdrop"><section className="ve-modal-panel ve-confirm-modal" role="dialog" aria-modal="true"><header className="ve-modal-head"><div><h2 className="ve-modal-title">Purger les écritures validées ?</h2><p className="ve-modal-subtitle">Cette action supprimera {lineCount} ligne(s) de l’API et de l’interface.</p></div><button className="ve-modal-close" type="button" onClick={() => setPendingPurge(false)} aria-label="Fermer"><X size={19} /></button></header><div className="ve-modal-body"><div className="ve-confirm-actions"><button type="button" className="ve-btn ve-btn-ghost" onClick={() => setPendingPurge(false)}>Annuler</button><button type="button" className="ve-btn ve-btn-danger" onClick={() => void purgeAll()} disabled={busy}><Trash2 size={15} /> Confirmer la purge</button></div></div></section></div>}</div>;
}
