#!/usr/bin/env python3
"""Patch AnalysisPage.jsx: replace old queue-top block with demo-dossier cards."""
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "frontend/src/pages/AnalysisPage.jsx"

src = TARGET.read_text(encoding="utf-8")

# ── locate the section to replace ─────────────────────────────────────────────
ANCHOR_START = 'id="contexte-facture">'
ANCHOR_END = '<div className="analysis-queue-bottom-bar">'

i_start = src.find(ANCHOR_START)
if i_start == -1:
    raise ValueError("ANCHOR_START not found")

# The <section …> opening tag starts a few chars before the anchor — find its line start
line_start = src.rfind("\n", 0, i_start) + 1  # beginning of the <section line

i_end = src.find(ANCHOR_END, i_start)
if i_end == -1:
    raise ValueError("ANCHOR_END not found")

old_block = src[line_start:i_end]
print("OLD block length:", len(old_block), "chars")
print("First 80 chars:", repr(old_block[:80]))

NEW_BLOCK = """\
      {/* ── FILE DE CONTROLE PLEINE LARGEUR ── */}
      <section className="card surface-card analysis-queue-panel" id="contexte-facture">

        {/* ── En-tête ── */}
        <div className="analysis-queue-header">
          <div>
            <h2 className="section-title">File de contrôle comptable</h2>
            <p className="section-text">
              Le moteur pré-analyse les factures et l'utilisateur intervient
              uniquement sur les lignes douteuses ou absentes du référentiel.
            </p>
          </div>
        </div>

        {/* ── Dossiers de démonstration ── */}
        <div className="demo-dossiers-section">
          <div className="demo-dossiers-header">
            <div>
              <h3 className="demo-dossiers-title">Dossiers de démonstration</h3>
              <p className="demo-dossiers-subtitle">
                Charge rapidement un lot de factures réelles par dossier, sans scanner toute CouchDB.
              </p>
            </div>
            {activeDossier ? (
              <span className="demo-dossier-active-badge">
                <Database size={13} />
                Dossier chargé\u00a0: {activeDossier}
              </span>
            ) : null}
          </div>

          <div className="demo-dossiers-grid">
            {[
              { name: "BOUCHERIE IFRI",               metier: "Boucherie",    invoices: 1316, color: "red"    },
              { name: "ASSAINIS",                      metier: "BTP",          invoices: 4919, color: "amber"  },
              { name: "BOULANGERIE L'UNIVERS DU PAIN", metier: "Boulangerie",  invoices: 3113, color: "yellow" },
              { name: "PROSERVICES AMBULANCES",        metier: "Transport",    invoices: 2562, color: "blue"   },
              { name: "PRIM DEMENAGEMENT",             metier: "Déménagement", invoices: 750,  color: "violet" },
            ].map((d) => {
              const isActive = activeDossier === d.name;
              const isLoading = loadingInvoices && isActive;
              return (
                <button
                  key={d.name}
                  type="button"
                  className={`demo-dossier-card demo-dossier-card--${d.color}${isActive ? " demo-dossier-card--active" : ""}`}
                  onClick={() => handleLoadDossier(d)}
                  disabled={loadingInvoices}
                >
                  <span className={`demo-dossier-badge demo-dossier-badge--${d.color}`}>{d.metier}</span>
                  <span className="demo-dossier-name">{d.name}</span>
                  <span className="demo-dossier-meta">~{d.invoices.toLocaleString("fr-FR")} factures réelles</span>
                  <span className="demo-dossier-action">
                    {isLoading ? (
                      <><LoaderCircle size={12} className="spin" /> Chargement...</>
                    ) : isActive ? (
                      <><Database size={12} /> Chargé</>
                    ) : (
                      "Charger le dossier →"
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Recherche manuelle (accordéon) ── */}
        <details className="manual-search-section">
          <summary className="manual-search-summary">
            <SearchCheck size={14} />
            Recherche manuelle dans CouchDB
          </summary>
          <div className="manual-search-body">
            <div className="analysis-field-grid analysis-queue-search-grid">
              <label className="analysis-field">
                <span>Fournisseur</span>
                <input
                  value={queueFilters.supplier}
                  onChange={(event) => handleQueueFilterInput("supplier", event.target.value)}
                  placeholder="Ex : Bouygues Telecom"
                />
              </label>
              <label className="analysis-field">
                <span>Client</span>
                <input
                  value={queueFilters.client}
                  onChange={(event) => handleQueueFilterInput("client", event.target.value)}
                  placeholder="Ex : Boucherie Mouad"
                />
              </label>
              <label className="analysis-field">
                <span>Code APE</span>
                <input
                  value={queueFilters.ape}
                  onChange={(event) => handleQueueFilterInput("ape", event.target.value)}
                  placeholder="Ex : 4722Z"
                />
              </label>
            </div>
            <div className="analysis-engine-actions analysis-queue-search-action">
              <button
                type="button"
                className="primary-btn"
                onClick={handleQueueSearch}
                disabled={loadingInvoices}
              >
                {loadingInvoices ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <SearchCheck size={16} />
                )}
                Rechercher dans CouchDB
              </button>
            </div>
          </div>
        </details>

        """

new_src = src[:line_start] + NEW_BLOCK + src[i_end:]
TARGET.write_text(new_src, encoding="utf-8")
print("✅ Patch applied. New file length:", len(new_src))
