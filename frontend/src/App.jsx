import { startTransition, useEffect, useState } from "react";

import { getHealth, recommendLine, sendFeedback } from "./api";

const initialForm = {
  article_source: "",
  metier_hint: "",
  tva_hint: "",
  include_charges: true,
};

const decisionLabels = {
  auto_ok: "Auto OK",
  validation_humaine: "Validation humaine",
  rejeter: "Rejeter",
};

function formatScore(score) {
  if (typeof score !== "number") {
    return "-";
  }
  return `${score.toFixed(2)}%`;
}

function cleanOptional(value) {
  return value ? value : null;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState("");

  useEffect(() => {
    let isMounted = true;

    getHealth()
      .then((payload) => {
        if (!isMounted) {
          return;
        }
        startTransition(() => {
          setHealth(payload);
          setHealthError("");
        });
      })
      .catch((apiError) => {
        if (!isMounted) {
          return;
        }
        setHealthError(apiError.message);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setFeedbackStatus("");

    try {
      const payload = {
        article_source: form.article_source.trim(),
        metier_hint: cleanOptional(form.metier_hint.trim()),
        tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
        include_charges: form.include_charges,
      };

      const apiResult = await recommendLine(payload);
      startTransition(() => {
        setResult(apiResult);
      });
    } catch (apiError) {
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitFeedback(decisionType) {
    if (!result) {
      return;
    }

    setFeedbackStatus("Enregistrement en cours...");

    try {
      const payload = {
        article_source: result.article_source,
        metier_hint: cleanOptional(form.metier_hint.trim()),
        tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
        decision_humaine: decisionType,
        compte_comptable_final:
          decisionType === "rejeter" ? null : cleanOptional(result.compte_comptable),
        categorie_finale: decisionType === "rejeter" ? null : cleanOptional(result.categorie),
        sous_categorie_finale:
          decisionType === "rejeter" ? null : cleanOptional(result.sous_categorie),
        commentaire:
          decisionType === "modifier"
            ? "Validation manuelle a ajuster dans une V2 avec edition de compte."
            : null,
        recommandation_ia: result,
      };

      await sendFeedback(payload);
      setFeedbackStatus("Validation humaine enregistree.");
    } catch (apiError) {
      setFeedbackStatus(apiError.message);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Agent Comptable</p>
        <h1>React + FastAPI, avec la cle OpenRouter gardee cote backend.</h1>
        <p className="hero-copy">
          On analyse une ligne de facture, on affiche la recommandation comptable, puis on peut
          enregistrer une validation humaine sans jamais exposer la cle API dans le navigateur.
        </p>

        <div className="status-row">
          <div className="status-pill">
            <span className="status-label">API</span>
            <strong>{health ? "Connectee" : "En attente"}</strong>
          </div>
          <div className="status-pill">
            <span className="status-label">Modele</span>
            <strong>{health?.openrouter_model || "Non charge"}</strong>
          </div>
          <div className="status-pill">
            <span className="status-label">References</span>
            <strong>{health?.references_loaded ?? "-"}</strong>
          </div>
        </div>

        {healthError ? <p className="panel-error">{healthError}</p> : null}
      </section>

      <section className="workspace-grid">
        <form className="panel form-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <p className="eyebrow">Analyse</p>
            <h2>Envoyer une ligne au backend</h2>
          </div>

          <label className="field">
            <span>Libelle de ligne facture</span>
            <textarea
              rows="4"
              value={form.article_source}
              onChange={(event) =>
                setForm((current) => ({ ...current, article_source: event.target.value }))
              }
              placeholder="Ex: Electricite mars 2025"
              required
            />
          </label>

          <div className="field-row">
            <label className="field">
              <span>Metier</span>
              <input
                type="text"
                value={form.metier_hint}
                onChange={(event) =>
                  setForm((current) => ({ ...current, metier_hint: event.target.value }))
                }
                placeholder="Ex: vtc"
              />
            </label>

            <label className="field">
              <span>TVA</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={form.tva_hint}
                onChange={(event) =>
                  setForm((current) => ({ ...current, tva_hint: event.target.value }))
                }
                placeholder="20"
              />
            </label>
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.include_charges}
              onChange={(event) =>
                setForm((current) => ({ ...current, include_charges: event.target.checked }))
              }
            />
            <span>Inclure les charges externes dans la recherche</span>
          </label>

          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Analyse en cours..." : "Analyser"}
          </button>

          {error ? <p className="panel-error">{error}</p> : null}
        </form>

        <section className="panel result-panel">
          <div className="panel-heading">
            <p className="eyebrow">Resultat</p>
            <h2>Decision comptable</h2>
          </div>

          {result ? (
            <>
              <div className="result-header">
                <div>
                  <p className="result-title">{result.article_source}</p>
                  <p className="result-subtitle">{result.explication}</p>
                </div>
                <span className={`decision-chip decision-${result.decision}`}>
                  {decisionLabels[result.decision]}
                </span>
              </div>

              <div className="metric-grid">
                <article className="metric-card accent-orange">
                  <span>Compte</span>
                  <strong>{result.compte_comptable || "-"}</strong>
                </article>
                <article className="metric-card accent-green">
                  <span>Categorie</span>
                  <strong>{result.categorie || "-"}</strong>
                </article>
                <article className="metric-card accent-blue">
                  <span>Sous-categorie</span>
                  <strong>{result.sous_categorie || "-"}</strong>
                </article>
                <article className="metric-card accent-amber">
                  <span>Score</span>
                  <strong>{formatScore(result.score_confiance)}</strong>
                </article>
              </div>

              <div className="feedback-row">
                <button className="secondary-button" type="button" onClick={() => submitFeedback("valider")}>
                  Valider
                </button>
                <button className="secondary-button" type="button" onClick={() => submitFeedback("modifier")}>
                  Modifier
                </button>
                <button className="ghost-button" type="button" onClick={() => submitFeedback("rejeter")}>
                  Rejeter
                </button>
              </div>

              {feedbackStatus ? <p className="panel-info">{feedbackStatus}</p> : null}

              <div className="candidate-list">
                <div className="panel-heading compact">
                  <p className="eyebrow">Top 3</p>
                  <h3>Candidats retournes par le moteur</h3>
                </div>

                {result.candidats.map((candidate, index) => (
                  <article className="candidate-card" key={`${candidate.article_source_match}-${index}`}>
                    <div className="candidate-topline">
                      <strong>{candidate.compte_comptable}</strong>
                      <span>{formatScore(candidate.score_confiance)}</span>
                    </div>
                    <p className="candidate-title">{candidate.article_source_match}</p>
                    <p className="candidate-meta">
                      {candidate.categorie} · {candidate.sous_categorie} · {candidate.metier}
                    </p>
                    <p className="candidate-reason">{candidate.raison_match}</p>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>On n’a pas encore lance d’analyse.</p>
              <span>
                Envoie une ligne depuis le formulaire pour voir la recommandation du backend.
              </span>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
