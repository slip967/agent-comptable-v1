import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Copy,
  Eye,
  FileText,
  FolderOpen,
  Layers3,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { formatAccount, getAccountLabel } from "../utils/accountLabels";
import "./BasesMetiersPage.css";

/* ─── Configuration des fichiers source ─── */
const SOURCE_FILES = [
  { file: "/data/base_charges_externes_v1.json",    label: "Charges externes" },
  { file: "/data/base_produits_boucherie_v1.json",  label: "Boucherie" },
  { file: "/data/base_produits_boulangerie_v1.json",label: "Boulangerie" },
  { file: "/data/base_produits_btp_v1.json",        label: "BTP" },
  { file: "/data/base_produits_epicerie_v1.json",   label: "Épicerie" },
  { file: "/data/base_produits_restaurant_v1.json", label: "Restaurant" },
  { file: "/data/base_produits_transport_v1.json",  label: "Transport" },
  { file: "/data/base_produits_vtc_v1.json",        label: "VTC" },
];

/* ─── Données expert mockées ─── */
const EXPERT_DATA = {
  "Boucherie":         { version: "v1.1", statut: "Validé",      date: "06/05/2026", expert: "Expert comptable" },
  "Boulangerie":       { version: "v1.0", statut: "Validé",      date: "06/05/2026", expert: "Expert comptable" },
  "VTC":               { version: "v1.2", statut: "Validé",      date: "06/05/2026", expert: "Expert comptable" },
  "Restaurant":        { version: "v1.1", statut: "Validé",      date: "06/05/2026", expert: "Expert comptable" },
  "Transport":         { version: "v1.0", statut: "Validé",      date: "06/05/2026", expert: "Expert comptable" },
  "Charges externes":  { version: "v1.0", statut: "À contrôler", date: null,         expert: "En attente" },
  "BTP":               { version: "v0.9", statut: "À contrôler", date: null,         expert: "En attente" },
  "Épicerie":          { version: "v1.0", statut: "À auditer",   date: null,         expert: "En attente" },
};

/* ─── Articles sensibles mockés ─── */
const SENSITIVE_ARTICLES = [
  { article: "FRAIS FIXES",             base: "Charges externes", probleme: "Libellé trop générique",                  compte: "6281 — Divers",  risque: "Moyen",  action: "Revoir" },
  { article: "PRESTATION",              base: "BTP",              probleme: "Peut correspondre à plusieurs comptes",   compte: "604 / 611",      risque: "Élevé",  action: "Arbitrer" },
  { article: "SERVICE",                 base: "Transport",        probleme: "Article ambigu",                          compte: "626 / 628",      risque: "Moyen",  action: "Contrôler" },
  { article: "CONDITION DE LIVRAISON",  base: "Transport",        probleme: "Compte métier discutable",                compte: "607",            risque: "Moyen",  action: "Vérifier" },
];

/* ─── Métier icons & colors ─── */
const METIER_ICONS = {
  "VTC":              "🚗",
  "Transport":        "🚛",
  "Restaurant":       "🍽️",
  "Épicerie":         "🛒",
  "BTP":              "🏗️",
  "Boulangerie":      "🥖",
  "Boucherie":        "🥩",
  "Charges externes": "📊",
};
const METIER_COLORS = {
  "VTC":              "#0ea5e9",
  "Transport":        "#f97316",
  "Restaurant":       "#10b981",
  "Épicerie":         "#8b5cf6",
  "BTP":              "#f59e0b",
  "Boulangerie":      "#d97706",
  "Boucherie":        "#ef4444",
  "Charges externes": "#6366f1",
};

const EMPTY_VALUE = "Non renseign\u00E9";

/* ─── Helpers ─── */
function getInvoiceIds(item) {
  return item.source_invoice_ids || item.ids_factures_sources || [];
}
function getPdfPaths(item) {
  return item.invoice_paths_sources || [];
}
function getApe(item) {
  const a = item.ape_context || [];
  return Array.isArray(a) ? a : [a];
}
function getPartitions(item) {
  return item.partitions_sources || item.source_partition_ids || [];
}
function getTva(item) {
  const v = item.taux_tva ?? item.tva_rate ?? null;
  if (v === null || v === "") return null;
  return typeof v === "number" ? `${v}%` : String(v);
}
function getLabel(item) {
  return (
    item.compte_comptable_libelle ||
    item.account_label ||
    item.recommended_account_label ||
    getAccountLabel(item.compte_comptable) ||
    ""
  );
}
function displayValue(value) {
  const text = String(value ?? "").trim();
  return text || EMPTY_VALUE;
}
function displayList(items) {
  return items.length > 0 ? items.join(", ") : EMPTY_VALUE;
}
function extractFileName(path) {
  const text = String(path || "").trim();
  if (!text) return EMPTY_VALUE;
  const parts = text.split(/[\\/]/);
  return parts[parts.length - 1] || text;
}
function computeStatut(item) {
  const badges = [];
  const hasCompte  = !!item.compte_comptable;
  const hasFacture = getInvoiceIds(item).length > 0;
  const hasPdf     = getPdfPaths(item).length > 0;
  const hasApe     = getApe(item).filter(Boolean).length > 0;
  if (hasCompte && hasFacture && hasPdf) badges.push("fiable");
  else badges.push("a-controler");
  if (!hasApe) badges.push("sans-ape");
  return badges;
}
function getPrimaryStatus(badges = []) {
  if (badges.includes("fiable")) {
    return { label: "Fiable", tone: "green" };
  }
  return { label: "\u00C0 contr\u00F4ler", tone: "orange" };
}

function filterBaseItems(items, { searchTerm = "", compteFilter = "all", apeFilter = "all" }) {
  const q = searchTerm.trim().toLowerCase();

  return items.filter((item) => {
    const compte = item.compte_comptable ? String(item.compte_comptable) : "";
    const ape = getApe(item).filter(Boolean);

    if (compteFilter !== "all" && compte !== compteFilter) return false;
    if (apeFilter !== "all" && !ape.includes(apeFilter)) return false;

    if (!q) return true;

    const haystack = [
      item.article_source,
      item.article_canonique,
      item.compte_comptable,
      getLabel(item),
      ...(item.mots_cles || []),
      ...getPartitions(item),
      ...getInvoiceIds(item),
      ...ape,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(q);
  });
}

/* ─── Explorer par métier ─── */
function MetierExplorer({ bases, selectedMetier, searchTerm, filterCompte, filterApe, onOpenDetail }) {
  const tableRef = useRef(null);
  const base  = bases.find((item) => item.label === selectedMetier) || bases[0];
  if (!base) return null;
  const items = base.items || [];
  const visibleItems = useMemo(
    () => filterBaseItems(items, { searchTerm, compteFilter: filterCompte, apeFilter: filterApe }),
    [items, searchTerm, filterCompte, filterApe],
  );

  const uniqueAccounts = useMemo(() =>
    new Set(visibleItems.map(it => it.compte_comptable).filter(Boolean)).size
  , [visibleItems]);

  const uniqueApe = useMemo(() => {
    const s = new Set();
    visibleItems.forEach(it => getApe(it).filter(Boolean).forEach(a => s.add(a)));
    return s.size;
  }, [visibleItems]);

  const topAccounts = useMemo(() => {
    const counts = {};
    visibleItems.forEach(it => {
      const acc = it.compte_comptable;
      if (acc) counts[String(acc)] = (counts[String(acc)] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 10);
  }, [visibleItems]);

  const color = METIER_COLORS[base.label] || "#6366f1";
  const icon  = METIER_ICONS[base.label]  || "📁";

  return (
    <section id="explorer-par-metier" className="bm-explorer-section">
      <div className="section-header bm-explorer-title-row">
        <div className="bm-explorer-title-chip">
          <h2 className="section-title">Explorer par métier</h2>
        </div>

      </div>
      <div className="bm-explorer">

        {/* ── Main ── */}
        <AnimatePresence mode="wait">
          <motion.div
            key={base.label}
            className="bm-explorer-main"
            initial={{ opacity: 0, x: 14 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Header */}
            <div className="bm-explorer-header" style={{ borderLeftColor: color }}>
              <div className="bm-explorer-hicon" style={{ background: `${color}20`, color }}>{icon}</div>
              <div className="bm-explorer-htitle">
                <div className="bm-explorer-hlabel" style={{ color }}>
                  {base.meta?.doc_type?.toUpperCase() || base.label.toUpperCase()}
                </div>
                <h3 className="bm-explorer-hname">{base.meta?.nom || `Base produits ${base.label}`}</h3>
                <p className="bm-explorer-hsub">
                  {visibleItems.length.toLocaleString("fr-FR")} articles affichés
                  {" · "}{items.length.toLocaleString("fr-FR")} au total
                  {" · "}{uniqueAccounts} comptes comptables
                  {" · "}{uniqueApe} codes APE
                </p>
              </div>
              <div className="bm-explorer-hmeta">
                {base.meta?.source_file && (
                  <div className="bm-explorer-hmeta-row">
                    <span>Source JSON :</span>
                    <strong>{base.meta.source_file}</strong>
                  </div>
                )}
                {base.meta?.updated_at && (
                  <div className="bm-explorer-hmeta-row">
                    <span>MAJ :</span>
                    <strong>{base.meta.updated_at}</strong>
                  </div>
                )}
              </div>
            </div>

            {/* Comptes fréquents */}
            <div className="card surface-card bm-explorer-content-card">
            {topAccounts.length > 0 && (
              <div className="bm-explorer-accounts">
                <div className="bm-explorer-section-label">Comptes les plus fréquents</div>
                <div className="bm-accounts-grid">
                  {topAccounts.map(([acc, count]) => (
                    <div key={acc} className="bm-account-pill">
                      <span className="bm-account-pill-code">{acc}</span>
                      <span className="bm-account-pill-sep">·</span>
                      <span className="bm-account-pill-count">{count} lignes</span>
                    </div>
                  ))}
                </div>
              </div>
            )}



            {/* Articles table */}
            <div className="bm-explorer-table-shell">
              <div ref={tableRef} className="data-table-shell bm-explorer-table-wrap">
                <table className="data-table bm-table bm-explorer-table">
                  <colgroup>
                    <col style={{ width: "260px" }} />
                    <col style={{ width: "100px" }} />
                    <col style={{ width: "250px" }} />
                    <col style={{ width: "90px" }} />
                    <col style={{ width: "80px" }} />
                    <col style={{ width: "120px" }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th className="bm-col-article">Article source</th>
                      <th>Compte</th>
                      <th>Libelle compte</th>
                      <th>APE</th>
                      <th>TVA</th>
                      <th className="bm-col-action">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleItems.map((item, i) => {
                      const acc   = item.compte_comptable;
                      const lbl   = getLabel(item);
                      const src   = item.article_source || item.label_source || item.designation || item.libelle || EMPTY_VALUE;
                      const ape   = getApe(item).filter(Boolean);
                      const tva   = getTva(item);
                      return (
                        <tr key={i} className="bm-row" onClick={() => onOpenDetail({ item, metier: base.label })}>
                          <td className="bm-article-cell" title={src}>
                            <div className="bm-article-inline">
                              <span className="bm-article-rank">{i + 1}</span>
                              <span className="bm-text-clamp bm-text-clamp--two">{src}</span>
                            </div>
                          </td>
                          <td>{acc ? <code className="bm-compte-pill">{acc}</code> : <span className="bm-missing">{EMPTY_VALUE}</span>}</td>
                          <td className="bm-label-cell" title={displayValue(lbl)}>
                            <span className="bm-text-clamp bm-text-clamp--two">{displayValue(lbl)}</span>
                          </td>
                          <td className="bm-ape-cell">
                            {ape.length > 0
                              ? (
                                <div className="bm-inline-cell">
                                  <code className="bm-ape-tag">{ape[0]}</code>
                                  {ape.length > 1 ? <span className="bm-inline-note">+{ape.length - 1}</span> : null}
                                </div>
                              )
                              : <span className="bm-missing">{EMPTY_VALUE}</span>}
                          </td>
                          <td>{tva ? <span className="bm-tva-badge">{tva}</span> : <span className="bm-missing">{EMPTY_VALUE}</span>}</td>
                          <td className="bm-col-action" onClick={e => e.stopPropagation()}>
                            <div className="bm-action-row">
                              <button
                                className="bm-action-btn"
                                title="Voir détails"
                                onClick={() => onOpenDetail({ item, metier: base.label })}
                              >
                                <Eye size={12}/> Détails
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {visibleItems.length === 0 && (
                  <div className="bm-empty">Aucun article ne correspond aux filtres actuels.</div>
                )}
              </div>
            </div>
            </div>
          </motion.div>
        </AnimatePresence>

      </div>
    </section>
  );
}

/* ─── Badge composant ─── */
function StatusBadge({ badges }) {
  return (
    <span className="bm-badge-group">
      {badges.includes("fiable") && (
        <span className="bm-badge bm-badge--green">Fiable</span>
      )}
      {badges.includes("a-controler") && (
        <span className="bm-badge bm-badge--orange">\u00C0 contr\u00F4ler</span>
      )}
      {badges.includes("sans-ape") && (
        <span className="bm-badge bm-badge--gray">Sans APE</span>
      )}
    </span>
  );
}
function PrimaryStatusBadge({ badges }) {
  const status = getPrimaryStatus(badges);
  return <span className={`bm-badge bm-badge--${status.tone}`}>{status.label}</span>;
}

/* ─── Panneau détail ─── */
function DetailPanel({ item, metier, onClose }) {
  const [showDocuments, setShowDocuments] = useState(false);
  const [copyMessage, setCopyMessage] = useState("");

  if (!item) return null;

  const ids = getInvoiceIds(item);
  const pdfs = getPdfPaths(item);
  const ape = getApe(item).filter(Boolean);
  const parts = getPartitions(item);
  const tva = getTva(item);
  const lbl = getLabel(item);
  const statut = computeStatut(item);
  const articleSource = displayValue(item.article_source);
  const canonicalArticle = displayValue(item.article_canonique);
  const accountDisplay = item.compte_comptable
    ? formatAccount(item.compte_comptable, lbl)
    : EMPTY_VALUE;
  const visiblePdfs = showDocuments ? pdfs : pdfs.slice(0, 3);

  const copyProofs = async () => {
    const payload = [
      `Article source: ${articleSource}`,
      `Article canonique: ${canonicalArticle}`,
      `Compte: ${accountDisplay}`,
      `Metier: ${displayValue(metier)}`,
      `TVA: ${displayValue(tva)}`,
      `APE: ${displayList(ape)}`,
      `Partitions: ${displayList(parts)}`,
      `Factures sources: ${ids.length ? ids.join(", ") : EMPTY_VALUE}`,
      `Documents PDF: ${pdfs.length ? pdfs.join(", ") : EMPTY_VALUE}`,
    ].join("\n");

    try {
      await navigator.clipboard.writeText(payload);
      setCopyMessage("Preuves copiees");
    } catch {
      setCopyMessage("Copie impossible");
    }
  };

  const copyPath = async (path) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopyMessage("Chemin copie");
    } catch {
      setCopyMessage("Copie impossible");
    }
  };

  return (
    <motion.div
      className="bm-overlay"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <motion.div
        className="bm-panel"
        onClick={(e) => e.stopPropagation()}
        initial={{ x: 48, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 48, opacity: 0 }}
        transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="bm-panel-header">
          <div>
            <div className="bm-panel-eyebrow">{metier}</div>
            <h3 className="bm-panel-title">{articleSource}</h3>
            <p className="bm-panel-subtitle">{accountDisplay}</p>
          </div>
          <button className="bm-close-btn" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="bm-panel-body">
          <div className="bm-audit-summary-grid">
            <div className="bm-audit-summary-card">
              <span className="bm-audit-summary-label">Factures sources</span>
              <strong className="bm-audit-summary-value">{ids.length}</strong>
            </div>
            <div className="bm-audit-summary-card">
              <span className="bm-audit-summary-label">Documents PDF</span>
              <strong className="bm-audit-summary-value">{pdfs.length}</strong>
            </div>
            <div className="bm-audit-summary-card">
              <span className="bm-audit-summary-label">Partitions</span>
              <strong className="bm-audit-summary-value">{parts.length}</strong>
            </div>
            <div className="bm-audit-summary-card">
              <span className="bm-audit-summary-label">APE</span>
              <strong className="bm-audit-summary-value">{displayValue(ape[0])}</strong>
            </div>
            <div className="bm-audit-summary-card">
              <span className="bm-audit-summary-label">Statut qualite</span>
              <div className="bm-audit-summary-status">
                <PrimaryStatusBadge badges={statut} />
              </div>
            </div>
          </div>

          <div className="bm-panel-actions">
            <button type="button" className="bm-audit-btn" onClick={copyProofs}>
              <Copy size={14} />
              Copier preuves
            </button>
            <button
              type="button"
              className="bm-audit-btn bm-audit-btn--ghost"
              onClick={() => setShowDocuments((current) => !current)}
            >
              <FolderOpen size={14} />
              {showDocuments ? "Masquer documents sources" : "Voir documents sources"}
            </button>
          </div>

          {copyMessage ? <div className="bm-copy-feedback">{copyMessage}</div> : null}

          <section className="bm-audit-section">
            <div className="bm-panel-section-title">
              <FileText size={14} /> Referentiel trouve
            </div>
            <div className="bm-audit-grid">
              <AuditField label="Article source" value={articleSource} />
              <AuditField label="Article canonique" value={canonicalArticle} />
              <AuditField label="Compte + libelle" value={accountDisplay} />
              <AuditField label="TVA" value={displayValue(tva)} />
              <AuditField label="Categorie" value={displayValue(item.categorie)} />
              <AuditField label="Sous-categorie" value={displayValue(item.sous_categorie)} />
              <AuditField label="Type fournisseur" value={displayValue(item.type_fournisseur || item.fournisseur_type)} />
            </div>
          </section>

          <section className="bm-audit-section">
            <div className="bm-panel-section-title">
              <ShieldCheck size={14} /> Contexte metier
            </div>
            <div className="bm-audit-grid">
              <AuditField label="Metier" value={displayValue(metier)} />
              <AuditField label="APE" value={displayList(ape)} />
              <AuditField label="Partitions" value={displayList(parts)} />
              <div className="bm-audit-field">
                <span className="bm-audit-key">Statut qualite</span>
                <div className="bm-audit-value">
                  <PrimaryStatusBadge badges={statut} />
                </div>
              </div>
            </div>
          </section>

          <section className="bm-audit-section">
            <div className="bm-panel-section-title">
              <FileText size={14} /> Factures sources
            </div>
            {ids.length === 0 ? (
              <span className="bm-missing">{EMPTY_VALUE}</span>
            ) : (
              <div className="bm-document-list">
                {ids.slice(0, 3).map((id, index) => (
                  <div key={id + index} className="bm-source-line">
                    <code className="bm-id">{id}</code>
                  </div>
                ))}
                {ids.length > 3 ? <span className="bm-more">+{ids.length - 3} autres</span> : null}
              </div>
            )}
          </section>

          <section className="bm-audit-section">
            <div className="bm-panel-section-title">
              <FolderOpen size={14} /> Documents PDF
            </div>
            {pdfs.length === 0 ? (
              <span className="bm-missing">{EMPTY_VALUE}</span>
            ) : (
              <div className="bm-document-list">
                {visiblePdfs.map((path, index) => (
                  <div key={path + index} className="bm-document-item" title={path}>
                    <div className="bm-document-copy">
                      <span className="bm-document-name">{extractFileName(path)}</span>
                      <span className="bm-document-meta">Document source disponible</span>
                    </div>
                    <button
                      type="button"
                      className="bm-inline-copy-btn"
                      onClick={() => copyPath(path)}
                    >
                      Copier chemin
                    </button>
                  </div>
                ))}
                {!showDocuments && pdfs.length > 3 ? (
                  <span className="bm-more">+{pdfs.length - 3} autres</span>
                ) : null}
              </div>
            )}
          </section>

          <section className="bm-audit-section">
            <div className="bm-panel-section-title">
              <ShieldCheck size={14} /> Statut qualite
            </div>
            <div className="bm-audit-grid bm-audit-grid--single">
              <div className="bm-audit-field">
                <span className="bm-audit-key">Evaluation</span>
                <div className="bm-audit-value">
                  <PrimaryStatusBadge badges={statut} />
                </div>
              </div>
              <AuditField
                label="Resume"
                value={ids.length > 0 || pdfs.length > 0 ? "Preuves documentaires rattachees au referentiel." : "Aucune preuve documentaire rattachee."}
              />
            </div>
          </section>
        </div>
      </motion.div>
    </motion.div>
  );
}

function AuditField({ label, value }) {
  return (
    <div className="bm-audit-field">
      <span className="bm-audit-key">{label}</span>
      <span className="bm-audit-value">{value || EMPTY_VALUE}</span>
    </div>
  );
}

/* ─── Page principale ─── */
export default function BasesMetiersPage() {
  const metierRailRef = useRef(null);
  const [bases, setBases]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState("");
  const [filterMetier, setMetier] = useState("");
  const [filterCompte, setCompte] = useState("all");
  const [filterApe, setApe]       = useState("all");
  const [detailItem, setDetailItem] = useState(null);

  /* Chargement des JSON */
  useEffect(() => {
    let cancelled = false;
    async function loadAll() {
      const results = await Promise.all(
        SOURCE_FILES.map(async ({ file, label }) => {
          try {
            const res  = await fetch(file);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            return { label, file, meta: json.meta || {}, items: json.items || [], error: null };
          } catch (err) {
            return { label, file, meta: {}, items: [], error: err.message };
          }
        })
      );
      if (!cancelled) {
        setBases(results);
        setLoading(false);
      }
    }
    loadAll();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!filterMetier && bases.length > 0) {
      setMetier(bases[0].label);
    }
  }, [bases, filterMetier]);

  useEffect(() => {
    setCompte("all");
    setApe("all");
  }, [filterMetier]);

  /* Tous les articles aplatis */
  const allRows = useMemo(() => {
    const rows = [];
    for (const base of bases) {
      for (const item of base.items) {
        rows.push({ ...item, _metier: base.label });
      }
    }
    return rows;
  }, [bases]);

  /* KPI */
  const kpis = useMemo(() => {
    if (!allRows.length) return null;
    const uniqueAccounts = new Set(
      allRows.map((row) => row.compte_comptable).filter(Boolean).map(String),
    ).size;
    return [
      { label: "Bases actives", value: bases.filter((base) => !base.error).length, desc: "Referentiels charges", tone: "blue", icon: Layers3 },
      { label: "Articles indexes", value: allRows.length.toLocaleString("fr-FR"), desc: "Articles sources structures", tone: "purple", icon: BookOpen },
      { label: "Comptes couverts", value: uniqueAccounts.toLocaleString("fr-FR"), desc: "Comptes distincts detectes", tone: "green", icon: FileText },
    ];
  }, [allRows, bases]);

  /* Résumé par métier */
  const summaryByMetier = useMemo(() => {
    return bases.map(base => {
      const items = base.items;
      const fiable    = items.filter(i => computeStatut(i).includes("fiable")).length;
      const withApe   = items.filter(i => getApe(i).filter(Boolean).length > 0).length;
      const invoices  = items.reduce((s, i) => s + getInvoiceIds(i).length, 0);
      const pdfs      = items.reduce((s, i) => s + getPdfPaths(i).length, 0);
      const toControl = items.filter(i => !computeStatut(i).includes("fiable")).length;
      const apePct    = items.length ? Math.round(withApe / items.length * 100) : 0;
      const fiablePct = items.length ? Math.round(fiable / items.length * 100) : 0;
      const exp = EXPERT_DATA[base.label] || {};
      let refStatut = "Brouillon";
      if (exp.statut === "Validé") refStatut = "Validé";
      else if (exp.statut === "À contrôler") refStatut = "À contrôler";
      else if (exp.statut === "À auditer") refStatut = "À auditer";
      return { ...base, fiable, fiablePct, withApe, apePct, invoices, pdfs, toControl, refStatut };
    });
  }, [bases]);

  const selectedBase = useMemo(
    () => bases.find((base) => base.label === filterMetier) || bases[0] || null,
    [bases, filterMetier],
  );

  const compteOptions = useMemo(() => {
    return [...new Set(allRows.map((item) => item.compte_comptable).filter(Boolean).map(String))].sort();
  }, [allRows]);

  const apeOptions = useMemo(() => {
    const apeSet = new Set();
    allRows.forEach((item) => {
      getApe(item).filter(Boolean).forEach((ape) => apeSet.add(ape));
    });
    return [...apeSet].sort();
  }, [allRows]);

  const scrollMetierRail = (direction) => {
    metierRailRef.current?.scrollBy({
      left: direction * 280,
      behavior: "smooth",
    });
  };

  if (loading) {
    return (
      <div className="page-stack">
        <div className="bm-skeleton-kpis">
          {[...Array(4)].map((_, i) => <div key={i} className="bm-skeleton-kpi"/>)}
        </div>
        <div className="bm-skeleton-table"/>
      </div>
    );
  }

  const errors = bases.filter(b => b.error);

  return (
    <div className="page-stack bm-dark-root">

      {/* ── Erreurs de chargement ── */}
      {errors.length > 0 && (
        <div className="bm-error-list">
          {errors.map(b => (
            <div key={b.file} className="bm-error-item">
              <AlertTriangle size={14}/> Impossible de charger {b.file.split("/").pop()} : {b.error}
            </div>
          ))}
        </div>
      )}

      {/* ── KPI ── */}
      {kpis && (
        <div className="bm-kpi-buttons" aria-label="Résumé des référentiels métier">
          {kpis.map((k, kIdx) => {
            const Icon = k.icon;
            return (
              <motion.button
                key={k.label}
                type="button"
                className={`bm-kpi-button bm-kpi-button--${k.tone}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: kIdx * 0.06 }}
                whileHover={{ y: -2 }}
                onClick={() => document.querySelector(".bm-toolbar-card")?.scrollIntoView({ behavior: "smooth", block: "start" })}
              >
                <span className="bm-kpi-button-icon"><Icon size={15} /></span>
                <span className="bm-kpi-button-label">{k.label}</span>
                <strong className="bm-kpi-button-value">{k.value}</strong>
              </motion.button>
            );
          })}
        </div>
      )}

      {bases.length > 0 && (
        <section className="card surface-card bm-toolbar-card">
          <div className="bm-toolbar-grid">
            <div className="bm-toolbar-field bm-toolbar-field--search">
              <label className="bm-toolbar-label">Recherche globale</label>
              <div className="bm-filter-search">
                <Search size={16} className="bm-search-icon"/>
                <input
                  className="bm-input"
                  placeholder="Rechercher article, compte, APE, partition, facture…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>

            <div className="bm-toolbar-field">
              <label className="bm-toolbar-label">Métier</label>
              <select className="bm-select" value={filterMetier} onChange={(e) => setMetier(e.target.value)}>
                {bases.map((base) => (
                  <option key={base.label} value={base.label}>{base.label}</option>
                ))}
              </select>
            </div>

            <div className="bm-toolbar-field">
              <label className="bm-toolbar-label">Compte</label>
              <select className="bm-select" value={filterCompte} onChange={(e) => setCompte(e.target.value)}>
                <option value="all">Tous les comptes</option>
                {compteOptions.map((compte) => (
                  <option key={compte} value={compte}>{compte}</option>
                ))}
              </select>
            </div>

            <div className="bm-toolbar-field">
              <label className="bm-toolbar-label">APE</label>
              <select className="bm-select" value={filterApe} onChange={(e) => setApe(e.target.value)}>
                <option value="all">Tous les APE</option>
                {apeOptions.map((ape) => (
                  <option key={ape} value={ape}>{ape}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="bm-scroll-shell">
            <button
              type="button"
              className="bm-scroll-arrow bm-scroll-arrow--left"
              aria-label="Faire défiler les métiers vers la gauche"
              onClick={() => scrollMetierRail(-1)}
            >
              <ChevronLeft size={16} />
            </button>

            <div ref={metierRailRef} className="bm-metier-rail">
              {bases.map((base) => {
                const accountsCount = new Set(base.items.map((item) => item.compte_comptable).filter(Boolean)).size;
                const apeCount = new Set(
                  base.items.flatMap((item) => getApe(item).filter(Boolean))
                ).size;
                const active = filterMetier === base.label;
                const color = METIER_COLORS[base.label] || "#6366f1";

                return (
                  <button
                    key={base.label}
                    className={`bm-metier-card bm-metier-rail-card ${active ? "bm-metier-card--active" : ""}`}
                    onClick={() => setMetier(base.label)}
                    style={active ? { borderColor: `${color}55`, background: `${color}14` } : {}}
                  >
                    <div className="bm-metier-icon" style={{ background: `${color}20`, color }}>
                      {METIER_ICONS[base.label] || "📁"}
                    </div>
                    <div className="bm-metier-info">
                      <div className="bm-metier-name" style={active ? { color } : {}}>{base.label}</div>
                      <div className="bm-metier-stats">
                        {base.items.length} articles · {accountsCount} comptes · {apeCount} APE
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              className="bm-scroll-arrow bm-scroll-arrow--right"
              aria-label="Faire défiler les métiers vers la droite"
              onClick={() => scrollMetierRail(1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
      )}

      {/* ── Explorer par métier ── */}
      {bases.length > 0 && (
        <MetierExplorer
          bases={bases}
          selectedMetier={filterMetier}
          searchTerm={search}
          filterCompte={filterCompte}
          filterApe={filterApe}
          onOpenDetail={setDetailItem}
        />
      )}

      {/* ── Résumé par métier ── */}
      {false && (
      <section id="resume-referentiels-metier" className="card surface-card">
        <button className="bm-section-toggle" onClick={() => setSummaryOpen(o => !o)}>
          <div className="section-header" style={{marginBottom:0}}>
            <h2 className="section-title">Résumé des référentiels métier</h2>
          </div>
          {summaryOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </button>
        {summaryOpen && (
          <div className="data-table-shell" style={{marginTop:"1rem"}}>
            <table className="data-table bm-table">
              <thead>
                <tr>
                  <th>Métier</th><th>Articles</th><th>Factures</th><th>PDF</th>
                  <th>APE %</th><th>Preuves %</th><th>À contrôler</th><th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {summaryByMetier.map(row => (
                  <tr key={row.label}>
                    <td className="bm-metier-cell">{row.label}</td>
                    <td>{row.items.length.toLocaleString("fr-FR")}</td>
                    <td>{row.invoices.toLocaleString("fr-FR")}</td>
                    <td>{row.pdfs.toLocaleString("fr-FR")}</td>
                    <td>
                      <div className="bm-bar-wrap">
                        <div className="bm-bar" style={{width:`${row.apePct}%`}}/>
                        <span>{row.apePct}%</span>
                      </div>
                    </td>
                    <td>
                      <div className="bm-bar-wrap">
                        <div className={`bm-bar ${row.fiablePct >= 80 ? "bm-bar--green" : "bm-bar--orange"}`} style={{width:`${row.fiablePct}%`}}/>
                        <span>{row.fiablePct}%</span>
                      </div>
                    </td>
                    <td>{row.toControl}</td>
                    <td><RefStatutBadge statut={row.refStatut}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}

      {/* ── Validation expert ── */}
      {false && (
      <section id="validation-expert-versionning" className="card surface-card">
        <button className="bm-section-toggle" onClick={() => setExpertOpen(o => !o)}>
          <div className="section-header" style={{marginBottom:0}}>
            <h2 className="section-title">Validation expert &amp; versionning</h2>
          </div>
          {expertOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </button>
        {expertOpen && (
          <div className="data-table-shell" style={{marginTop:"1rem"}}>
            <table className="data-table bm-table">
              <thead>
                <tr><th>Métier</th><th>Version</th><th>Statut expert</th><th>Dernière validation</th><th>Expert signataire</th><th>Action</th></tr>
              </thead>
              <tbody>
                {SOURCE_FILES.map(({ label }) => {
                  const e = EXPERT_DATA[label] || {};
                  return (
                    <tr key={label}>
                      <td className="bm-metier-cell">{label}</td>
                      <td><code className="bm-version">{e.version || "—"}</code></td>
                      <td><RefStatutBadge statut={e.statut || "Brouillon"}/></td>
                      <td>{e.date || <span className="bm-missing">Non validé</span>}</td>
                      <td>{e.expert || "—"}</td>
                      <td>
                        <button className="bm-action-btn bm-action-btn--ghost">
                          {e.statut === "Validé" ? "Voir rapport" : "Demander validation"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}

      {/* ── Articles sensibles ── */}
      {false && (
      <section id="articles-sensibles-detectes" className="card surface-card">
        <button className="bm-section-toggle" onClick={() => setSensOpen(o => !o)}>
          <div className="section-header" style={{marginBottom:0}}>
            <h2 className="section-title">
              <AlertTriangle size={16} style={{color:"var(--orange)",marginRight:6}}/>
              Articles sensibles détectés
            </h2>
          </div>
          {sensOpen ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </button>
        {sensOpen && (
          <div className="data-table-shell" style={{marginTop:"1rem"}}>
            <table className="data-table bm-table">
              <thead>
                <tr><th>Article</th><th>Base</th><th>Problème détecté</th><th>Compte proposé</th><th>Risque</th><th>Action</th></tr>
              </thead>
              <tbody>
                {SENSITIVE_ARTICLES.map((row, i) => (
                  <tr key={i}>
                    <td className="bm-article-cell">{row.article}</td>
                    <td><span className="bm-metier-tag">{row.base}</span></td>
                    <td>{row.probleme}</td>
                    <td><code className="bm-compte-code">{row.compte}</code></td>
                    <td><RiskBadge risque={row.risque}/></td>
                    <td><button className="bm-action-btn bm-action-btn--ghost">{row.action}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}

      {/* Panneaux */}
      <AnimatePresence>
        {detailItem && (
          <DetailPanel
            key="detail-panel"
            item={detailItem.item}
            metier={detailItem.metier}
            onClose={() => setDetailItem(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── Mini-composants ─── */
function RefStatutBadge({ statut }) {
  const cls =
    statut === "Validé"      ? "bm-badge bm-badge--green"  :
    statut === "À contrôler" ? "bm-badge bm-badge--orange" :
    statut === "À auditer"   ? "bm-badge bm-badge--blue"   :
                               "bm-badge bm-badge--gray";
  return <span className={cls}>{statut}</span>;
}

function RiskBadge({ risque }) {
  const cls =
    risque === "Élevé" ? "bm-badge bm-badge--red"    :
    risque === "Moyen" ? "bm-badge bm-badge--orange"  :
                         "bm-badge bm-badge--green";
  return <span className={cls}>{risque}</span>;
}







