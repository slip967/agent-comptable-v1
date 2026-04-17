import { startTransition, useEffect, useRef, useState } from "react";

import {
  askAssistant,
  getAnalysisHistory,
  getHealth,
  getValidationQueue,
  recommendLine,
  sendFeedback,
} from "./api";
import AssistantLogo from "./components/AssistantLogo";

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

const assistantActionLabels = {
  analyser: "Action suggeree : lancer l'analyse",
  valider: "Action suggeree : valider",
  modifier: "Action suggeree : modifier",
  rejeter: "Action suggeree : rejeter",
  neutre: "Action suggeree : aucune",
};

const assistantExecutionLabels = {
  analyser: "Executer l'analyse",
  valider: "Valider la ligne",
  modifier: "Modifier la ligne",
  rejeter: "Rejeter la ligne",
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

function buildContextMessage(decision) {
  if (!decision) {
    return null;
  }

  return {
    role: "assistant",
    content:
      `Contexte charge pour "${decision.article_source}". ` +
      `Decision: ${decisionLabels[decision.decision]}. ` +
      `Compte: ${decision.compte_comptable || "-"}. ` +
      `Score: ${formatScore(decision.score_confiance)}.`,
    suggestedAction:
      decision.decision === "auto_ok"
        ? "valider"
        : decision.decision === "rejeter"
          ? "modifier"
          : "modifier",
  };
}

function buildEditDraft(decision) {
  return {
    compte_comptable: decision?.compte_comptable || "",
    categorie: decision?.categorie || "",
    sous_categorie: decision?.sous_categorie || "",
    commentaire: "",
  };
}

function buildDecisionFromRecord(record) {
  return {
    article_source: record.article_source,
    categorie: record.categorie,
    sous_categorie: record.sous_categorie,
    compte_comptable: record.compte_comptable,
    score_confiance: record.score_confiance,
    decision: record.decision,
    explication: record.explication,
    candidats: [],
  };
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }

  try {
    return new Intl.DateTimeFormat("fr-FR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function getAssistantQuickPrompts(result, editMode) {
  if (editMode) {
    return [
      "Que dois-je corriger ici ?",
      "Comment justifier la modification ?",
      "Quel champ verifier en priorite ?",
    ];
  }

  if (!result) {
    return [
      "Mode d'emploi",
      "Que remplir ?",
      "Premier test",
    ];
  }

  return [
    "Explique la decision",
    "Etape suivante",
    result.decision === "validation_humaine" ? "Que modifier ?" : "Pourquoi ce score ?",
  ];
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [validationQueue, setValidationQueue] = useState([]);
  const [insightsError, setInsightsError] = useState("");
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editDraft, setEditDraft] = useState(() => buildEditDraft(null));
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantMessages, setAssistantMessages] = useState([]);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [assistantStatus, setAssistantStatus] = useState("Pas d'analyse");
  const assistantWidgetRef = useRef(null);

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

  useEffect(() => {
    setEditDraft(buildEditDraft(result));
    setEditMode(false);
  }, [result]);

  useEffect(() => {
    if (!assistantOpen || !assistantWidgetRef.current) {
      return;
    }

    const widgetElement = assistantWidgetRef.current;
    widgetElement.scrollTop = widgetElement.scrollHeight;
  }, [assistantMessages, assistantOpen]);

  useEffect(() => {
    void refreshInsights();
  }, []);

  function buildRecommendPayload() {
    return {
      article_source: form.article_source.trim(),
      metier_hint: cleanOptional(form.metier_hint.trim()),
      tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
      include_charges: form.include_charges,
    };
  }

  async function refreshInsights() {
    setInsightsLoading(true);

    try {
      const [historyPayload, queuePayload] = await Promise.all([
        getAnalysisHistory(),
        getValidationQueue(),
      ]);

      startTransition(() => {
        setAnalysisHistory(historyPayload.items || []);
        setValidationQueue(queuePayload.items || []);
        setInsightsError("");
      });
    } catch (apiError) {
      setInsightsError(apiError.message);
    } finally {
      setInsightsLoading(false);
    }
  }

  function buildAssistantPayload(userMessage) {
    return {
      user_message: userMessage,
      article_source: cleanOptional(form.article_source.trim()),
      metier_hint: cleanOptional(form.metier_hint.trim()),
      tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
      current_decision: result,
    };
  }

  function loadRecordIntoWorkspace(record, sourceLabel) {
    const nextResult = buildDecisionFromRecord(record);
    const contextMessage = buildContextMessage(nextResult);

    startTransition(() => {
      setForm({
        article_source: record.article_source,
        metier_hint: record.metier_hint || "",
        tva_hint: record.tva_hint == null ? "" : String(record.tva_hint),
        include_charges: record.include_charges ?? true,
      });
      setResult(nextResult);
      setFeedbackStatus(
        sourceLabel === "queue"
          ? "La ligne de la file est prechargee. Tu peux maintenant valider, modifier ou rejeter."
          : "Analyse rechargee depuis l'historique.",
      );
      setAssistantMessages(contextMessage ? [contextMessage] : []);
      setAssistantOpen(true);
      setAssistantStatus(
        sourceLabel === "queue" ? "Element de la file charge" : "Historique charge",
      );
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setFeedbackStatus("");
    setEditMode(false);

    try {
      const apiResult = await recommendLine(buildRecommendPayload());
      const contextMessage = buildContextMessage(apiResult);

      startTransition(() => {
        setResult(apiResult);
        setAssistantMessages(contextMessage ? [contextMessage] : []);
        setAssistantOpen(true);
        setAssistantStatus("Decision disponible");
      });
      await refreshInsights();
    } catch (apiError) {
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function openEditMode() {
    if (!result) {
      return;
    }

    setEditDraft(buildEditDraft(result));
    setEditMode(true);
    setFeedbackStatus("Mode modification ouvert. Ajuste les champs puis enregistre.");
    setAssistantStatus("Edition en cours");
    setAssistantOpen(true);
  }

  async function submitFeedback(decisionType) {
    if (!result) {
      return;
    }

    setFeedbackStatus("Enregistrement en cours...");
    setEditMode(false);

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
        commentaire: null,
        recommandation_ia: result,
      };

      await sendFeedback(payload);

      let updatedResult = null;
      if (decisionType === "rejeter") {
        updatedResult = {
          ...result,
          decision: "rejeter",
          explication:
            "Cette recommandation a ete rejetee par validation humaine. Une correction manuelle ou une nouvelle analyse est necessaire.",
        };
      } else {
        updatedResult = await recommendLine(buildRecommendPayload());
      }

      const followupMessage =
        decisionType === "valider"
          ? {
              role: "assistant",
              content:
                "La validation humaine est enregistree. L'assistant s'est resynchronise avec la nouvelle decision backend.",
              suggestedAction: "neutre",
            }
          : decisionType === "modifier"
            ? {
                role: "assistant",
                content:
                  "La ligne est marquee comme modifiee. Tu peux maintenant verifier le compte final et reposer une question a l'assistant si besoin.",
                suggestedAction: "neutre",
              }
            : {
                role: "assistant",
                content:
                  "La recommandation a ete rejetee. Le plus prudent est de corriger la ligne manuellement ou de relancer l'analyse avec plus de contexte.",
                suggestedAction: "modifier",
              };

      startTransition(() => {
        setResult(updatedResult);
        setAssistantMessages(() => {
          const contextMessage = buildContextMessage(updatedResult);
          return contextMessage ? [followupMessage, contextMessage] : [followupMessage];
        });
        setAssistantStatus(
          decisionType === "valider"
            ? "Validation enregistree"
            : decisionType === "rejeter"
              ? "Recommendation rejetee"
              : "Modification a verifier",
        );
      });

      setFeedbackStatus("Validation humaine enregistree.");
      await refreshInsights();
    } catch (apiError) {
      setFeedbackStatus(apiError.message);
    }
  }

  async function submitEditedFeedback() {
    if (!result) {
      return;
    }

    setFeedbackStatus("Enregistrement de la modification...");

    try {
      const payload = {
        article_source: result.article_source,
        metier_hint: cleanOptional(form.metier_hint.trim()),
        tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
        decision_humaine: "modifier",
        compte_comptable_final: cleanOptional(editDraft.compte_comptable.trim()),
        categorie_finale: cleanOptional(editDraft.categorie.trim()),
        sous_categorie_finale: cleanOptional(editDraft.sous_categorie.trim()),
        commentaire: cleanOptional(editDraft.commentaire.trim()),
        recommandation_ia: result,
      };

      await sendFeedback(payload);
      const updatedResult = await recommendLine(buildRecommendPayload());
      const contextMessage = buildContextMessage(updatedResult);

      startTransition(() => {
        setResult(updatedResult);
        setAssistantMessages([
          {
            role: "assistant",
            content:
              "La modification humaine est enregistree. Je me base maintenant sur la nouvelle version pour la suite.",
            suggestedAction: "neutre",
          },
          ...(contextMessage ? [contextMessage] : []),
        ]);
        setAssistantStatus("Modification enregistree");
      });

      setFeedbackStatus("Modification humaine enregistree.");
      await refreshInsights();
    } catch (apiError) {
      setFeedbackStatus(apiError.message);
    }
  }

  async function submitAssistantMessage(messageOverride) {
    const message = (messageOverride ?? assistantInput).trim();
    if (!message) {
      return;
    }

    const userEntry = { role: "user", content: message };
    startTransition(() => {
      setAssistantMessages((current) => [...current, userEntry]);
      setAssistantOpen(true);
    });
    setAssistantInput("");
    setAssistantLoading(true);

    try {
      const reply = await askAssistant(buildAssistantPayload(message));
      const assistantEntry = {
        role: "assistant",
        content: reply.answer,
        suggestedAction: reply.suggested_action,
      };
      startTransition(() => {
        setAssistantMessages((current) => [...current, assistantEntry]);
      });
    } catch (apiError) {
      startTransition(() => {
        setAssistantMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: apiError.message,
            suggestedAction: "neutre",
          },
        ]);
      });
    } finally {
      setAssistantLoading(false);
    }
  }

  async function executeSuggestedAction(action) {
    if (assistantLoading || action === "neutre") {
      return;
    }

    if (action === "analyser") {
      const syntheticEvent = {
        preventDefault() {},
      };
      await handleSubmit(syntheticEvent);
      return;
    }

    if (action === "modifier") {
      openEditMode();
      return;
    }

    if (action === "valider" || action === "rejeter") {
      await submitFeedback(action);
    }
  }

  const quickPrompts = getAssistantQuickPrompts(result, editMode);
  const hasDraftArticle = form.article_source.trim().length > 0;
  const assistantContextTitle = result?.article_source || "Aucune ligne analysee";
  const assistantContextSummary = result
    ? `Decision: ${decisionLabels[result.decision]} / Compte: ${result.compte_comptable || "-"}`
    : hasDraftArticle
      ? "Une ligne est en cours de preparation dans le formulaire. Lance l'analyse pour la charger ici."
      : "Decision: Pas encore d'analyse / Compte: -";
  const canSaveModification =
    editDraft.compte_comptable.trim().length > 0 ||
    editDraft.categorie.trim().length > 0 ||
    editDraft.sous_categorie.trim().length > 0;

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
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => submitFeedback("valider")}
                >
                  Valider
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={openEditMode}
                >
                  Modifier
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => submitFeedback("rejeter")}
                >
                  Rejeter
                </button>
              </div>

              {feedbackStatus ? <p className="panel-info">{feedbackStatus}</p> : null}

              {editMode ? (
                <div className="edit-panel">
                  <div className="panel-heading compact">
                    <p className="eyebrow">Modifier</p>
                    <h3>Ajuster la decision humaine</h3>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Compte final</span>
                      <input
                        type="text"
                        value={editDraft.compte_comptable}
                        onChange={(event) =>
                          setEditDraft((current) => ({
                            ...current,
                            compte_comptable: event.target.value,
                          }))
                        }
                        placeholder="Ex: 6281"
                      />
                    </label>

                    <label className="field">
                      <span>Categorie finale</span>
                      <input
                        type="text"
                        value={editDraft.categorie}
                        onChange={(event) =>
                          setEditDraft((current) => ({
                            ...current,
                            categorie: event.target.value,
                          }))
                        }
                        placeholder="Ex: charges_externes"
                      />
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Sous-categorie finale</span>
                      <input
                        type="text"
                        value={editDraft.sous_categorie}
                        onChange={(event) =>
                          setEditDraft((current) => ({
                            ...current,
                            sous_categorie: event.target.value,
                          }))
                        }
                        placeholder="Ex: charges_generales"
                      />
                    </label>

                    <label className="field">
                      <span>Commentaire</span>
                      <input
                        type="text"
                        value={editDraft.commentaire}
                        onChange={(event) =>
                          setEditDraft((current) => ({
                            ...current,
                            commentaire: event.target.value,
                          }))
                        }
                        placeholder="Pourquoi tu modifies cette ligne ?"
                      />
                    </label>
                  </div>

                  <div className="feedback-row">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={submitEditedFeedback}
                      disabled={!canSaveModification}
                    >
                      Enregistrer la modification
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setEditDraft(buildEditDraft(result));
                        setEditMode(false);
                        setFeedbackStatus("Modification annulee.");
                        setAssistantStatus("Decision disponible");
                      }}
                    >
                      Annuler
                    </button>
                    <div />
                  </div>
                </div>
              ) : null}

              <div className="candidate-list">
                <div className="panel-heading compact">
                  <p className="eyebrow">Top 3</p>
                  <h3>Candidats retournes par le moteur</h3>
                </div>

                {result.candidats.length > 0 ? (
                  result.candidats.map((candidate, index) => (
                    <article
                      className="candidate-card"
                      key={`${candidate.article_source_match}-${index}`}
                    >
                      <div className="candidate-topline">
                        <strong>{candidate.compte_comptable}</strong>
                        <span>{formatScore(candidate.score_confiance)}</span>
                      </div>
                      <p className="candidate-title">{candidate.article_source_match}</p>
                      <p className="candidate-meta">
                        {candidate.categorie} / {candidate.sous_categorie} / {candidate.metier}
                      </p>
                      <p className="candidate-reason">{candidate.raison_match}</p>
                    </article>
                  ))
                ) : (
                  <div className="candidate-empty-state">
                    La reponse actuelle provient de la memoire des validations humaines. Aucun
                    candidat moteur n'est affiche pour ce cas.
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <p>On n'a pas encore lance d'analyse.</p>
              <span>
                Envoie une ligne depuis le formulaire pour voir la recommandation du backend.
              </span>
            </div>
          )}
        </section>
      </section>

      <section className="insights-grid">
        <section className="panel insight-panel">
          <div className="panel-heading compact">
            <p className="eyebrow">Historique</p>
            <h3>Dernieres analyses</h3>
          </div>

          {insightsError ? <p className="panel-error">{insightsError}</p> : null}

          <div className="insight-list">
            {analysisHistory.length > 0 ? (
              analysisHistory.map((item, index) => (
                <button
                  className="insight-card"
                  type="button"
                  key={`${item.lookup_key}-${item.created_at}-${index}`}
                  onClick={() => loadRecordIntoWorkspace(item, "history")}
                >
                  <div className="insight-card-topline">
                    <strong>{item.article_source}</strong>
                    <span>{formatScore(item.score_confiance)}</span>
                  </div>
                  <p className="insight-card-meta">
                    {decisionLabels[item.decision]} / {item.compte_comptable || "-"} /{" "}
                    {formatTimestamp(item.created_at)}
                  </p>
                  <p className="insight-card-description">{item.explication}</p>
                </button>
              ))
            ) : (
              <div className="candidate-empty-state">
                {insightsLoading
                  ? "Chargement de l'historique..."
                  : "Aucune analyse enregistree pour le moment."}
              </div>
            )}
          </div>
        </section>

        <section className="panel insight-panel">
          <div className="panel-heading compact">
            <p className="eyebrow">File humaine</p>
            <h3>Validations a traiter</h3>
          </div>

          <div className="insight-list">
            {validationQueue.length > 0 ? (
              validationQueue.map((item, index) => (
                <button
                  className="insight-card insight-card-queue"
                  type="button"
                  key={`${item.lookup_key}-${item.created_at}-${index}`}
                  onClick={() => loadRecordIntoWorkspace(item, "queue")}
                >
                  <div className="insight-card-topline">
                    <strong>{item.article_source}</strong>
                    <span>{item.compte_comptable || "-"}</span>
                  </div>
                  <p className="insight-card-meta">
                    Score {formatScore(item.score_confiance)} / {formatTimestamp(item.created_at)}
                  </p>
                  <p className="insight-card-description">{item.explication}</p>
                </button>
              ))
            ) : (
              <div className="candidate-empty-state">
                {insightsLoading
                  ? "Chargement de la file..."
                  : "La file de validation humaine est vide pour l'instant."}
              </div>
            )}
          </div>
        </section>
      </section>

      <button
        className={`assistant-launcher ${assistantOpen ? "assistant-launcher-hidden" : ""}`}
        type="button"
        onClick={() => setAssistantOpen(true)}
      >
        <AssistantLogo compact />
        <span>Assistant IA</span>
      </button>

      <aside
        className={`assistant-widget ${assistantOpen ? "assistant-widget-open" : ""}`}
        ref={assistantWidgetRef}
      >
        <div className="assistant-widget-header">
          <div className="assistant-widget-brand">
            <AssistantLogo />
            <div>
              <strong>Assistant IA</strong>
              <span>Assistant contextuel toujours disponible</span>
            </div>
          </div>

          <div className="assistant-widget-actions">
            <button
              className="assistant-control-button"
              type="button"
              onClick={() => setAssistantMessages([])}
              disabled={assistantLoading || assistantMessages.length === 0}
            >
              Effacer
            </button>
            <button
              className="assistant-control-button"
              type="button"
              onClick={() => setAssistantOpen(false)}
            >
              Reduire
            </button>
          </div>
        </div>

        <div className="assistant-context-card">
          <p className="assistant-context-label">Contexte courant</p>
          <strong>{assistantContextTitle}</strong>
          <span>{assistantContextSummary}</span>
          <span className="assistant-status-badge">{assistantStatus}</span>
        </div>

        <div className="assistant-quick-actions">
          {quickPrompts.map((prompt) => (
            <button
              key={prompt}
              className="quick-prompt-button"
              type="button"
              onClick={() => submitAssistantMessage(prompt)}
              disabled={assistantLoading}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="assistant-thread">
          {assistantMessages.length > 0 ? (
            assistantMessages.map((message, index) => (
              <article
                className={`assistant-bubble assistant-${message.role}`}
                key={`${message.role}-${index}`}
              >
                <strong>{message.role === "user" ? "Toi" : "Assistant IA"}</strong>
                <p>{message.content}</p>
                {message.role === "assistant" ? (
                  <div className="assistant-action-block">
                    <span className="assistant-action-label">
                      {assistantActionLabels[message.suggestedAction || "neutre"]}
                    </span>
                    {message.suggestedAction && message.suggestedAction !== "neutre" ? (
                      <button
                        className="assistant-inline-action"
                        type="button"
                        onClick={() => executeSuggestedAction(message.suggestedAction)}
                        disabled={assistantLoading}
                      >
                        {assistantExecutionLabels[message.suggestedAction]}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ))
          ) : (
            <div className="assistant-empty-state">
              Pose une question sur la ligne en cours, la decision comptable ou la prochaine
              action a prendre.
            </div>
          )}
        </div>

        <div className="assistant-composer">
          <textarea
            rows="3"
            value={assistantInput}
            onChange={(event) => setAssistantInput(event.target.value)}
            placeholder="Ex: explique-moi pourquoi cette ligne est en validation humaine"
          />
          <button
            className="primary-button"
            type="button"
            onClick={() => submitAssistantMessage()}
            disabled={assistantLoading || assistantInput.trim().length === 0}
          >
            {assistantLoading ? "Assistant en cours..." : "Demander a l'assistant"}
          </button>
        </div>
      </aside>
    </main>
  );
}
