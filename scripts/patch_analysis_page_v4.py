#!/usr/bin/env python3
"""
Patch AnalysisPage.jsx v4:
- Add handleLoadDemoSample call via "Charger factures" button in client-dossiers-section
"""
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "frontend/src/pages/AnalysisPage.jsx"
src = TARGET.read_text(encoding="utf-8")

# Find: end of activeDossier badge + closing </div> of client-dossiers-section
# The closing </div> for client-dossiers-section comes right after the null } from activeDossier block
OLD = (
    "              Dossier charg\u00e9\xa0: {activeDossier}\n"
    "            </span>\n"
    "          ) : null}\n"
    "        </div>"
)

NEW = (
    "              Dossier charg\u00e9\xa0: {activeDossier}\n"
    "            </span>\n"
    "          ) : null}\n"
    "          <div className=\"client-dossiers-actions\">\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"secondary-btn compact\"\n"
    "              onClick={handleLoadDemoSample}\n"
    "              disabled={loadingInvoices}\n"
    "              title=\"Charge 3 factures par dossier depuis les 5 dossiers clients r\u00e9els\"\n"
    "            >\n"
    "              {loadingInvoices && !activeDossier ? (\n"
    "                <LoaderCircle size={14} className=\"spin\" />\n"
    "              ) : (\n"
    "                <Database size={14} />\n"
    "              )}\n"
    "              Charger factures\n"
    "            </button>\n"
    "            {!activeDossier && !loadingInvoices ? (\n"
    "              <span className=\"client-dossiers-hint\">\n"
    "                ou cliquez sur un dossier ci-dessus\n"
    "              </span>\n"
    "            ) : null}\n"
    "          </div>\n"
    "        </div>"
)

count = src.count(OLD)
assert count == 1, f"Anchor not found or ambiguous (count={count})"
src = src.replace(OLD, NEW)

TARGET.write_text(src, encoding="utf-8")
print(f"\u2705 Patch v4 applied. File length: {len(src)} chars")
