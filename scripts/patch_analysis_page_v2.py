#!/usr/bin/env python3
"""
Patch AnalysisPage.jsx:
- Remove demo-dossiers-section (large cards)
- Keep manual search accordion
- Add testSource select + unified load button to the test accordion
- Add loadedSourceLabel state + display
"""
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "frontend/src/pages/AnalysisPage.jsx"
src = TARGET.read_text(encoding="utf-8")

# ─── 1. Add testSource and loadedSourceLabel states after activeDossier ───────
OLD_STATE = '  const [activeDossier, setActiveDossier] = useState(null);'
NEW_STATE = (
    '  const [activeDossier, setActiveDossier] = useState(null);\n'
    '  const [testSource, setTestSource] = useState("random");\n'
    '  const [loadedSourceLabel, setLoadedSourceLabel] = useState("");'
)
assert src.count(OLD_STATE) == 1, f"STATE anchor not found or duplicate"
src = src.replace(OLD_STATE, NEW_STATE)

# ─── 2. Remove the demo-dossiers-section block from the queue panel ───────────
DEMO_SECTION_START = '\n        {/* ── Dossiers de démonstration ── */}\n        <div className="demo-dossiers-section">'
DEMO_SECTION_END   = '\n        </div>\n\n        {/* ── Recherche manuelle (accordéon) ── */}'
KEEP_AFTER         = '\n\n        {/* ── Recherche manuelle (accordéon) ── */}'

i_start = src.find(DEMO_SECTION_START)
assert i_start != -1, "Demo section start not found"
i_end = src.find(DEMO_SECTION_END, i_start)
assert i_end != -1, "Demo section end not found"
i_end += len(DEMO_SECTION_END)

src = src[:i_start] + KEEP_AFTER + src[i_end:]

# ─── 3. Replace the test-accordion content ────────────────────────────────────
OLD_ACCORDION = '''        <div className="analysis-queue-test-accordion">
          <button
            type="button"
            className="secondary-btn compact"
            onClick={() => setShowSampleMode((current) => !current)}
          >
            {showSampleMode ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            Mode test / echantillon aleatoire
          </button>

          {showSampleMode ? (
            <div className="analysis-queue-test-mode">
              <p>
                Ce mode sert uniquement a tester le moteur sur un echantillon de
                factures CouchDB.
              </p>
              <button
                type="button"
                className="secondary-btn"
                onClick={loadInvoices}
                disabled={loadingInvoices}
              >
                {loadingInvoices ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Database size={16} />
                )}
                Charger un echantillon test
              </button>
            </div>
          ) : null}
        </div>'''

NEW_ACCORDION = '''        <div className="analysis-queue-test-accordion">
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
                  <option value="BOULANGERIE L\'UNIVERS DU PAIN">BOULANGERIE L\'UNIVERS DU PAIN \u2014 Boulangerie</option>
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
                      "BOULANGERIE L\'UNIVERS DU PAIN": { name: "BOULANGERIE L\'UNIVERS DU PAIN", metier: "Boulangerie"  },
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
        </div>'''

assert src.count(OLD_ACCORDION) == 1, f"ACCORDION anchor not found or duplicate (found {src.count(OLD_ACCORDION)} times)"
src = src.replace(OLD_ACCORDION, NEW_ACCORDION)

TARGET.write_text(src, encoding="utf-8")
print(f"✅ Patch applied. File length: {len(src)} chars")
