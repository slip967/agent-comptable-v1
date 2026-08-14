import {
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  Gauge,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { formatAccount } from "../utils/accountLabels";

const kpis = [
  { label: "Auto OK", value: "82%", desc: "Decisions automatiques valides", tone: "blue" },
  { label: "Validation humaine", value: "14", desc: "Cas a arbitrer", tone: "purple" },
  { label: "Confiance moyenne", value: "92%", desc: "Score global des recommandations", tone: "green" },
  { label: "Memoire IA", value: "248", desc: "Lignes reutilisables", tone: "orange" },
];

const alerts = [
  {
    title: "Charges externes a surveiller",
    detail: "10 lignes demandent une validation humaine avant reutilisation.",
    level: "warning",
  },
  {
    title: "BTP encore sensible",
    detail: "Le metier BTP concentre les recommandations les plus fragiles.",
    level: "warning",
  },
  {
    title: "Memoire fournisseur active",
    detail: "Les derniers cas valides sont bien reinjectes dans le moteur local.",
    level: "ok",
  },
];

const recentActivity = [
  { article: "UBER TRIP", compte: "6251", metier: "Transport", status: "Auto OK" },
  { article: "BASSE COTE BOEUF", compte: "6011", metier: "Boucherie", status: "Validation" },
  { article: "EDF AVRIL 2026", compte: "6061", metier: "Charges externes", status: "Auto OK" },
  { article: "FRAIS FIXES", compte: "6281", metier: "Charges externes", status: "A revoir" },
];

const riskyMetiers = [
  { metier: "BTP", risk: "Eleve", note: "Libelles techniques et cas produits encore heterogenes." },
  { metier: "Charges externes", risk: "Moyen", note: "Certaines lignes generiques demandent une supervision." },
  { metier: "VTC", risk: "Moyen", note: "Melange entre exploitation vehicule et frais de service." },
];

function statusClass(status) {
  if (status === "Auto OK") return "status-pill ready";
  if (status === "Validation") return "status-pill review";
  return "status-pill danger";
}

function alertClass(level) {
  return level === "ok" ? "dashboard-alert ok" : "dashboard-alert warning";
}

function riskClass(risk) {
  return risk === "Eleve" ? "status-pill danger" : "status-pill review";
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [activePanel, setActivePanel] = useState("summary");
  const primaryRisk = riskyMetiers[0];
  const panels = [
    { key: "summary", label: "Synthese" },
    { key: "metrics", label: "Pilotage IA" },
  ];

  useEffect(() => {
    const hash = location.hash;
    if (
      hash === "#kpi-globaux" ||
      hash === "#alertes-ia" ||
      hash === "#activite-recente" ||
      !hash
    ) {
      setActivePanel("summary");
    } else if (
      hash === "#niveau-confiance" ||
      hash === "#repartition-auto-validation" ||
      hash === "#metiers-a-risque"
    ) {
      setActivePanel("metrics");
    }
  }, [location.hash]);

  return (
    <div className="page-stack dashboard-page">
      <section className="card hero-card dashboard-hero">
        <div className="hero-eyebrow">
          <Sparkles size={16} />
          <span>Dashboard IA</span>
        </div>

        <div className="dashboard-hero-row">
          <div className="dashboard-hero-copy">
            <h1 className="page-title">Pilotage du moteur comptable</h1>
            <p className="hero-text">
              Vue synthese du moteur IA, des validations humaines, de la qualite
              de la memoire et des metiers a risque.
            </p>
          </div>
        </div>
      </section>

      <div className="page-panel-tabs" role="tablist" aria-label="Panneaux Dashboard">
        {panels.map((panel) => (
          <button
            key={panel.key}
            type="button"
            role="tab"
            aria-selected={activePanel === panel.key}
            className={`page-panel-tab${activePanel === panel.key ? " active" : ""}`}
            onClick={() => setActivePanel(panel.key)}
          >
            {panel.label}
          </button>
        ))}
      </div>

      {activePanel === "summary" ? (
        <div className="page-stack dashboard-panel-stack">
          <section className="card surface-card dashboard-panel-card" id="kpi-globaux">
            <div className="dashboard-section-head">
              <h2 className="section-title">KPI globaux</h2>
            </div>

            <div className="dashboard-grid dashboard-kpi-grid">
              {kpis.map((item) => (
                <div key={item.label} className={`card kpi-card dashboard-kpi-card ${item.tone}`}>
                  <div className="kpi-label">{item.label}</div>
                  <div className="kpi-value">{item.value}</div>
                  <div className="kpi-desc">{item.desc}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="card surface-card dashboard-panel-card" id="alertes-ia">
            <div className="dashboard-section-head">
              <h2 className="section-title">Alertes IA</h2>
            </div>

            <div className="dashboard-alert-list">
              {alerts.map((item) => (
                <article key={item.title} className={alertClass(item.level)}>
                  <div className="dashboard-alert-icon">
                    {item.level === "ok" ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
                  </div>

                  <div className="dashboard-alert-copy">
                    <h3>{item.title}</h3>
                    <p>{item.detail}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="card surface-card dashboard-panel-card" id="activite-recente">
            <div className="dashboard-section-head">
              <h2 className="section-title">Activite recente</h2>
            </div>

            <div className="dashboard-activity-list">
              {recentActivity.map((item) => (
                <article key={`${item.article}-${item.compte}`} className="dashboard-activity-item">
                  <div className="dashboard-activity-copy">
                    <h3 className="dashboard-activity-title">{item.article}</h3>
                    <p className="dashboard-activity-meta">
                      Compte {formatAccount(item.compte)} · {item.metier}
                    </p>
                  </div>

                  <span className={statusClass(item.status)}>{item.status}</span>
                </article>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      {activePanel === "metrics" ? (
        <div className="dashboard-secondary-grid dashboard-panel-card">
          <section className="card surface-card dashboard-metric-card" id="niveau-confiance">
            <div className="dashboard-metric-head">
              <div className="dashboard-metric-icon">
                <Gauge size={18} />
              </div>
              <h2 className="section-title">Niveau de confiance</h2>
            </div>

            <div className="dashboard-ring">
              <div className="dashboard-ring-core">
                <div className="dashboard-ring-value">92%</div>
                <div className="dashboard-ring-label">Confiance</div>
              </div>
            </div>

            <p className="dashboard-metric-note">
              Confiance elevee : le moteur peut automatiser la majorite des cas simples.
            </p>

            <button type="button" className="dashboard-metric-cta" onClick={() => navigate("/analysis")}>
              Analyser une ligne
            </button>
          </section>

          <section className="card surface-card dashboard-metric-card" id="repartition-auto-validation">
            <div className="dashboard-metric-head">
              <div className="dashboard-metric-icon">
                <BarChart3 size={18} />
              </div>
              <h2 className="section-title">Repartition Auto OK / Validation</h2>
            </div>

            <div className="dashboard-split-bar">
              <div className="dashboard-split-fill auto">82%</div>
              <div className="dashboard-split-fill validation">18%</div>
            </div>

            <div className="dashboard-split-legend">
              <div className="dashboard-split-legend-item">
                <span className="legend-dot auto" />
                <span>Auto OK</span>
              </div>

              <div className="dashboard-split-legend-item">
                <span className="legend-dot validation" />
                <span>Validation</span>
              </div>
            </div>

            <p className="dashboard-metric-note">
              18% des cas demandent encore une validation humaine avant reutilisation.
            </p>

            <button type="button" className="dashboard-metric-cta" onClick={() => navigate("/validation")}>
              Ouvrir Validation humaine
            </button>
          </section>

          <section className="card surface-card dashboard-metric-card" id="metiers-a-risque">
            <div className="dashboard-metric-head">
              <div className="dashboard-metric-icon">
                <BriefcaseBusiness size={18} />
              </div>
              <h2 className="section-title">Metiers a risque</h2>
            </div>

            <div className="dashboard-risk-focus">
              <div className="dashboard-risk-focus-top">
                <div>
                  <div className="dashboard-risk-focus-label">Priorite actuelle</div>
                  <h3 className="dashboard-risk-focus-title">{primaryRisk.metier}</h3>
                </div>

                <span className={riskClass(primaryRisk.risk)}>{primaryRisk.risk}</span>
              </div>

              <p className="dashboard-risk-focus-text">{primaryRisk.note}</p>
            </div>

            <p className="dashboard-metric-note">
              {riskyMetiers.length} metiers sont actuellement sous surveillance renforcee.
            </p>

            <button type="button" className="dashboard-metric-cta" onClick={() => navigate("/history")}>
              Voir l'historique
            </button>
          </section>
        </div>
      ) : null}
    </div>
  );
}
