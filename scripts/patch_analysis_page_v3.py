#!/usr/bin/env python3
"""
Patch AnalysisPage.jsx v3:
- Remove showSampleMode / testSource / loadedSourceLabel states
- Insert compact client-dossiers-section (pills) before the manual-search accordion
- Update manual-search summary label
- Remove analysis-queue-test-accordion block entirely
"""
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "frontend/src/pages/AnalysisPage.jsx"
src = TARGET.read_text(encoding="utf-8")

# ─── 1. Remove obsolete states ────────────────────────────────────────────────
OLD_STATES = (
    "  const [showSampleMode, setShowSampleMode] = useState(false);\n"
    "  const [activeDossier, setActiveDossier] = useState(null);\n"
    "  const [testSource, setTestSource] = useState(\"random\");\n"
    "  const [loadedSourceLabel, setLoadedSourceLabel] = useState(\"\");"
)
NEW_STATES = (
    "  const [activeDossier, setActiveDossier] = useState(null);"
)
assert src.count(OLD_STATES) == 1, f"STATE block not found (count={src.count(OLD_STATES)})"
src = src.replace(OLD_STATES, NEW_STATES)

# ─── 2. Insert client-dossiers-section before the manual-search accordion ─────
ANCHOR = "\n\n        {/* \u2500\u2500 Recherche manuelle (accord\u00e9on) \u2500\u2500 */}\n        <details className=\"manual-search-section\">"

NEW_DOSSIERS = """

        {/* \u2500\u2500 Dossiers clients \u2500\u2500 */}
        <div className="client-dossiers-section">
          <div className="client-dossiers-header">
            <span className="client-dossiers-title">Dossiers clients</span>
            <span className="client-dossiers-subtitle">
              Charge les factures d\u2019un dossier r\u00e9el sans scanner toute CouchDB.
            </span>
          </div>
          <div className="client-dossiers-pills">
            {[
              { name: "BOUCHERIE IFRI",               label: "BOUCHERIE IFRI",    metier: "Boucherie"    },
              { name: "ASSAINIS",                      label: "ASSAINIS",          metier: "BTP"          },
              { name: "BOULANGERIE L'UNIVERS DU PAIN", label: "UNIVERS DU PAIN",   metier: "Boulangerie"  },
              { name: "PROSERVICES AMBULANCES",        label: "PROSERVICES",       metier: "Transport"    },
              { name: "PRIM DEMENAGEMENT",             label: "PRIM D\u00c9M\u00c9NAGEMENT",    metier: "D\u00e9m\u00e9nagement" },
            ].map((d) => (
              <button
                key={d.name}
                type="button"
                className={`client-dossier-pill${activeDossier === d.name ? " active" : ""}`}
                onClick={() => handleLoadDossier(d)}
                disabled={loadingInvoices}
              >
                <span className="client-dossier-pill-badge">{d.metier}</span>
                {loadingInvoices && activeDossier === d.name ? (
                  <LoaderCircle size={11} className="spin" />
                ) : null}
                {d.label}
              </button>
            ))}
          </div>
          {activeDossier ? (
            <span className="analysis-loaded-source-label">
              <Database size={11} />
              Dossier charg\u00e9\u00a0: {activeDossier}
            </span>
          ) : null}
        </div>

        {/* \u2500\u2500 Recherche manuelle (accord\u00e9on) \u2500\u2500 */}
        <details className="manual-search-section">"""

assert src.count(ANCHOR) == 1, f"ACCORDION anchor not found (count={src.count(ANCHOR)})"
src = src.replace(ANCHOR, NEW_DOSSIERS)

# ─── 3. Update manual-search summary text ─────────────────────────────────────
OLD_SUMMARY = "            Recherche manuelle dans CouchDB"
NEW_SUMMARY = "            Recherche manuelle"
assert src.count(OLD_SUMMARY) == 1, f"SUMMARY text not found"
src = src.replace(OLD_SUMMARY, NEW_SUMMARY)

# ─── 4. Remove the analysis-queue-test-accordion block ───────────────────────
OLD_ACCORDION = """
        <div className="analysis-queue-test-accordion">
          <button
            type="button"
            className="secondary-btn compact"
            onClick={() => setShowSampleMode((current) => !current)}
          >
            {showSampleMode ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            Mode test / source de test
          </button>

          {showSampleMode ? (
            <div className="analysis-queue-test-mode">
              <label className="analysis-field analysis-test-source-field">
                <span>Source de test</span>
                <select
                  value={testSource}
                  onChange={(e) => setTestSource(e.target.value)}
                  disabled={loadingInvoices}
                >
                  <option value="random">\u00c9chantillon al\u00e9atoire</option>
                  <option value="BOUCHERIE IFRI">BOUCHERIE IFRI \u2014 Boucherie</option>
                  <option value="ASSAINIS">ASSAINIS \u2014 BTP</option>
                  <option value="BOULANGERIE L'UNIVERS DU PAIN">BOULANGERIE L'UNIVERS DU PAIN \u2014 Boulangerie</option>
                  <option value="PROSERVICES AMBULANCES">PROSERVICES AMBULANCES \u2014 Transport</option>
                  <option value="PRIM DEMENAGEMENT">PRIM DEMENAGEMENT \u2014 D\u00e9m\u00e9nagement</option>
                </select>
              </label>
              <button
                type="button"
                className="secondary-btn"
                onClick={async () => {
                  if (testSource === "random") {
                    setLoadedSourceLabel("");
                    await loadInvoices();
                    setLoadedSourceLabel("\u00c9chantillon al\u00e9atoire");
                  } else {
                    const DOSSIERS = {
                      "BOUCHERIE IFRI":               { name: "BOUCHERIE IFRI",               metier: "Boucherie"    },
                      "ASSAINIS":                      { name: "ASSAINIS",                      metier: "BTP"          },
                      "BOULANGERIE L'UNIVERS DU PAIN": { name: "BOULANGERIE L'UNIVERS DU PAIN", metier: "Boulangerie"  },
                      "PROSERVICES AMBULANCES":        { name: "PROSERVICES AMBULANCES",        metier: "Transport"    },
                      "PRIM DEMENAGEMENT":             { name: "PRIM DEMENAGEMENT",             metier: "D\u00e9m\u00e9nagement" },
                    };
                    setLoadedSourceLabel("");
                    await handleLoadDossier(DOSSIERS[testSource]);
                    setLoadedSourceLabel(testSource);
                  }
                }}
                disabled={loadingInvoices}
              >
                {loadingInvoices ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Database size={16} />
                )}
                Charger les factures
              </button>
              {loadedSourceLabel ? (
                <span className="analysis-loaded-source-label">
                  Source charg\u00e9e\u00a0: {loadedSourceLabel}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>"""

assert src.count(OLD_ACCORDION) == 1, f"ACCORDION block not found (count={src.count(OLD_ACCORDION)})"
src = src.replace(OLD_ACCORDION, "")

TARGET.write_text(src, encoding="utf-8")
print(f"\u2705 Patch v3 applied. File length: {len(src)} chars")
