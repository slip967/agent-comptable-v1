import { startTransition, useEffect, useRef, useState } from "react";

import {
  askAssistant,
  getAnalysisHistory,
  getHealth,
  getMemoryStats,
  getValidationQueue,
  recommendLine,
  sendFeedback,
} from "./api";
import AssistantLogo from "./components/AssistantLogo";
import keyManageIcon from "./assets/keymanage-icon.svg";
import topbarAssistantIcon from "./assets/topbar-assistant-icon.svg";
import topbarThemeMoonIcon from "./assets/topbar-theme-moon-icon.svg";
import topbarThemeSunIcon from "./assets/topbar-theme-sun-icon.svg";
import topbarUiExpertIcon from "./assets/topbar-ui-expert-icon.svg";
import topbarUiSimpleIcon from "./assets/topbar-ui-simple-icon.svg";

const initialForm = {
  article_source: "",
  fournisseur_hint: "",
  metier_hint: "",
  client_ape_hint: "",
  supplier_ape_hint: "",
  tva_hint: "",
  include_charges: true,
};

const UI_MODE_STORAGE_KEY = "agent-comptable-ui-mode";
const THEME_MODE_STORAGE_KEY = "agent-comptable-theme-mode";
const ACTIVE_TAB_STORAGE_KEY = "agent-comptable-active-tab";
const SHOW_INACTIVE_SIGNALS_STORAGE_KEY = "agent-comptable-show-inactive-signals";

const decisionLabels = {
  auto_ok: "Auto OK",
  validation_humaine: "Validation humaine",
  rejeter: "Rejeter",
};

const sourceLabels = {
  engine: "Moteur",
  memory: "Memoire",
  ai: "IA",
};

const signalFamilyLabels = {
  fort: "Signal fort",
  moyen: "Signal moyen",
  faible: "Signal faible",
};

const signalCatalog = {
  human_validation: {
    label: "Validation humaine precedente",
    family: "fort",
  },
  supplier_memory: {
    label: "Fournisseur deja vu",
    family: "fort",
  },
  ape_pair_context: {
    label: "APE client / fournisseur",
    family: "moyen",
  },
  tva_coherence: {
    label: "TVA coherente",
    family: "moyen",
  },
  metier_coherence: {
    label: "Metier coherent",
    family: "moyen",
  },
  text_similarity: {
    label: "Similarite texte",
    family: "faible",
  },
};

const signalDisplayOrder = [
  "human_validation",
  "supplier_memory",
  "ape_pair_context",
  "tva_coherence",
  "metier_coherence",
  "text_similarity",
];

const coherenceLabels = {
  coherente: "Coherente",
  incoherente: "Incoherente",
  a_verifier: "A verifier",
};

const historyFilters = [
  { id: "all", label: "Tout" },
  { id: "auto_ok", label: "Auto OK" },
  { id: "validation_humaine", label: "A valider" },
  { id: "rejeter", label: "Rejetes" },
];

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

const interfaceTabs = [
  { id: "analyse", label: "Analyse" },
  { id: "pilotage", label: "Dashboard" },
  { id: "historique", label: "Historique" },
  { id: "validation", label: "Validation humaine" },
  { id: "memoire", label: "Memoire IA" },
];

function formatScore(score) {
  if (typeof score !== "number") {
    return "-";
  }
  return `${score.toFixed(2)}%`;
}

function formatModelName(modelName) {
  if (!modelName) {
    return "Non charge";
  }

  const normalized = String(modelName).trim();
  if (normalized === "deepseek/deepseek-chat-v3.1") {
    return "DeepSeek Chat v3.1";
  }

  const withoutVendor = normalized.includes("/") ? normalized.split("/")[1] : normalized;
  return withoutVendor
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function cleanOptional(value) {
  return value ? value : null;
}

function buildUnavailableSignal(key, context = {}) {
  const spec = signalCatalog[key];
  if (!spec) {
    return null;
  }

  let explanation = "Ce signal n'a pas renforce ce candidat pour cette analyse.";

  if (key === "tva_coherence") {
    explanation =
      context.tvaHint == null
        ? "La TVA n'a pas ete renseignee dans l'interface pour cette analyse."
        : "La TVA fournie n'a pas renforce ce candidat.";
  } else if (key === "metier_coherence") {
    explanation =
      !context.metierHint
        ? "Le metier n'a pas ete renseigne dans l'interface pour cette analyse."
        : "Le contexte metier fourni n'a pas renforce ce candidat.";
  } else if (key === "ape_pair_context") {
    explanation =
      !context.clientApeHint && !context.supplierApeHint
        ? "Les APE client et fournisseur n'ont pas ete renseignes dans l'interface."
        : !context.clientApeHint || !context.supplierApeHint
          ? "Le couple APE est incomplet, donc ce signal reste limite."
          : "Le couple APE fourni n'a pas renforce ce candidat.";
  } else if (key === "supplier_memory") {
    explanation =
      !context.fournisseurHint
        ? "Le fournisseur n'a pas ete renseigne dans l'interface pour activer ce signal."
        : "Aucun historique fournisseur exploitable n'a renforce ce cas pour cette analyse.";
  } else if (key === "human_validation") {
    explanation = "Aucune validation humaine precedente n'a renforce ce cas pour cette analyse.";
  } else if (key === "text_similarity") {
    explanation = "Aucun score textuel detaille n'a ete conserve pour cette lecture.";
  }

  return {
    key,
    label: spec.label,
    family: spec.family,
    value: null,
    contribution: null,
    explanation,
    inactive: true,
  };
}

function buildSignalList(signals, context = {}, includeInactive = false) {
  const normalizedSignals = Array.isArray(signals) ? signals : [];
  if (!includeInactive) {
    return normalizedSignals;
  }

  const signalsByKey = new Map(
    normalizedSignals.map((signal) => [String(signal.key || "").trim(), signal]),
  );

  return signalDisplayOrder
    .map((key) => signalsByKey.get(key) || buildUnavailableSignal(key, context))
    .filter(Boolean);
}

function buildContextMessage(decision, context = {}) {
  if (!decision) {
    return null;
  }

  const fournisseurSegment = context.fournisseurHint
    ? ` Fournisseur: ${context.fournisseurHint}.`
    : "";

  return {
    role: "assistant",
    content:
      `Contexte charge pour "${decision.article_source}". ` +
      `Decision: ${decisionLabels[decision.decision]}. ` +
      `Compte: ${decision.compte_comptable || "-"}. ` +
      `Score: ${formatScore(decision.score_confiance)}.` +
      fournisseurSegment,
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

function buildEditDraftFromCandidate(candidate) {
  return {
    compte_comptable: candidate?.compte_comptable || "",
    categorie: candidate?.categorie || "",
    sous_categorie: candidate?.sous_categorie || "",
    commentaire: "",
  };
}

function buildDecisionFromRecord(record) {
  return {
    article_source: record.article_source,
    fournisseur_hint: record.fournisseur_hint,
    categorie: record.categorie,
    sous_categorie: record.sous_categorie,
    compte_comptable: record.compte_comptable,
    score_confiance: record.score_confiance,
    decision: record.decision,
    explication: record.explication,
    source: record.source || "engine",
    signals: record.signals || [],
    candidats: record.candidats || [],
  };
}

function formatSignalValue(value) {
  if (typeof value !== "number") {
    return "-";
  }
  return `${Math.round(value * 100)}%`;
}

function clampPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function buildDisplaySignals(decision, context = {}, includeInactive = false) {
  if (!decision) {
    return [];
  }

  if (decision.signals?.length) {
    return buildSignalList(decision.signals, context, includeInactive);
  }

  const matchingCandidate =
    (decision.compte_comptable &&
      decision.candidats?.find(
        (candidate) => candidate.compte_comptable === decision.compte_comptable,
      )) ||
    decision.candidats?.[0] ||
    null;

  return buildSignalList(matchingCandidate?.signals || [], context, includeInactive);
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

function matchesInsightQuery(item, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  const haystack = [
    item.article_source,
    item.fournisseur_hint,
    item.metier_hint,
    item.client_ape_hint,
    item.supplier_ape_hint,
    item.compte_comptable,
    item.categorie,
    item.sous_categorie,
    item.explication,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return haystack.includes(normalizedQuery);
}

function buildCandidateKey(candidate, index) {
  return `${candidate.article_source_match}-${candidate.compte_comptable}-${index}`;
}

function buildHistoryKey(record, index) {
  return `${record.lookup_key}-${record.created_at}-${index}`;
}

function buildRecordActionKey(record) {
  return `${record.lookup_key}-${record.created_at}`;
}

function getAssistantQuickPrompts(result, editMode, hasSelectedCandidate) {
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

  if (hasSelectedCandidate) {
    return [
      "Explique la decision",
      "Etape suivante",
      "Que penser du candidat selectionne ?",
    ];
  }

  return [
    "Explique la decision",
    "Etape suivante",
    result.decision === "validation_humaine" ? "Que modifier ?" : "Pourquoi ce score ?",
  ];
}

function getInitialUiMode() {
  if (typeof window === "undefined") {
    return "expert";
  }

  const storedValue = window.localStorage.getItem(UI_MODE_STORAGE_KEY);
  return storedValue === "simple" ? "simple" : "expert";
}

function getInitialThemeMode() {
  if (typeof window === "undefined") {
    return "light";
  }

  const storedValue = window.localStorage.getItem(THEME_MODE_STORAGE_KEY);
  return storedValue === "dark" ? "dark" : "light";
}

function getInitialActiveTab() {
  if (typeof window === "undefined") {
    return "analyse";
  }

  const storedValue = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
  return interfaceTabs.some((tab) => tab.id === storedValue) ? storedValue : "analyse";
}

function getInitialShowInactiveSignals() {
  if (typeof window === "undefined") {
    return false;
  }

  return window.localStorage.getItem(SHOW_INACTIVE_SIGNALS_STORAGE_KEY) === "true";
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [memoryStats, setMemoryStats] = useState(null);
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
  const [uiMode, setUiMode] = useState(getInitialUiMode);
  const [themeMode, setThemeMode] = useState(getInitialThemeMode);
  const [activeTab, setActiveTab] = useState(getInitialActiveTab);
  const [showInactiveSignals, setShowInactiveSignals] = useState(getInitialShowInactiveSignals);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null);
  const [selectedHistoryKey, setSelectedHistoryKey] = useState(null);
  const [insightQuery, setInsightQuery] = useState("");
  const [historyFilter, setHistoryFilter] = useState("all");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantMessages, setAssistantMessages] = useState([]);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [assistantStatus, setAssistantStatus] = useState("Pas d'analyse");
  const [listActionStatus, setListActionStatus] = useState("");
  const [listActionLoadingKey, setListActionLoadingKey] = useState("");
  const assistantWidgetRef = useRef(null);
  const nextResultModeRef = useRef("view");

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
    setEditMode(nextResultModeRef.current === "edit");
    setSelectedCandidateKey(
      result?.candidats?.length ? buildCandidateKey(result.candidats[0], 0) : null,
    );
    nextResultModeRef.current = "view";
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

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(UI_MODE_STORAGE_KEY, uiMode);
  }, [uiMode]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, themeMode);
    window.document.documentElement.dataset.theme = themeMode;
  }, [themeMode]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      SHOW_INACTIVE_SIGNALS_STORAGE_KEY,
      showInactiveSignals ? "true" : "false",
    );
  }, [showInactiveSignals]);

  function buildRecommendPayload() {
    return {
      article_source: form.article_source.trim(),
      fournisseur_hint: cleanOptional(form.fournisseur_hint.trim()),
      metier_hint: cleanOptional(form.metier_hint.trim()),
      client_ape_hint: cleanOptional(form.client_ape_hint.trim()),
      supplier_ape_hint: cleanOptional(form.supplier_ape_hint.trim()),
      tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
      include_charges: form.include_charges,
    };
  }

  async function refreshInsights() {
    setInsightsLoading(true);

    try {
      const [historyPayload, queuePayload, statsPayload] = await Promise.all([
        getAnalysisHistory(),
        getValidationQueue(),
        getMemoryStats(),
      ]);

      startTransition(() => {
        setAnalysisHistory(historyPayload.items || []);
        setValidationQueue(queuePayload.items || []);
        setMemoryStats(statsPayload);
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
      fournisseur_hint: cleanOptional(form.fournisseur_hint.trim()),
      metier_hint: cleanOptional(form.metier_hint.trim()),
      client_ape_hint: cleanOptional(form.client_ape_hint.trim()),
      supplier_ape_hint: cleanOptional(form.supplier_ape_hint.trim()),
      tva_hint: form.tva_hint === "" ? null : Number(form.tva_hint),
      current_decision: result,
      selected_candidate: selectedCandidate,
    };
  }

  function loadRecordIntoWorkspace(record, sourceLabel, options = {}) {
    const startInEdit = options.startInEdit || false;
    const nextResult = buildDecisionFromRecord(record);
    const contextMessage = buildContextMessage(nextResult, {
      fournisseurHint: cleanOptional(record.fournisseur_hint || ""),
    });
    nextResultModeRef.current = startInEdit ? "edit" : "view";
    setListActionStatus("");

    startTransition(() => {
      setForm({
        article_source: record.article_source,
        fournisseur_hint: record.fournisseur_hint || "",
        metier_hint: record.metier_hint || "",
        client_ape_hint: record.client_ape_hint || "",
        supplier_ape_hint: record.supplier_ape_hint || "",
        tva_hint: record.tva_hint == null ? "" : String(record.tva_hint),
        include_charges: record.include_charges ?? true,
      });
      setResult(nextResult);
      setFeedbackStatus(
        startInEdit
          ? "Mode modification ouvert. Ajuste les champs puis enregistre."
          : sourceLabel === "queue"
            ? "La ligne de la file est prechargee. Tu peux maintenant valider, modifier ou rejeter."
            : "Analyse rechargee depuis l'historique.",
      );
      setActiveTab("analyse");
      setAssistantMessages(contextMessage ? [contextMessage] : []);
      setAssistantOpen(true);
      setAssistantStatus(
        startInEdit
          ? "Edition en cours"
          : sourceLabel === "queue"
            ? "Element de la file charge"
            : "Historique charge",
      );
    });
  }

  function openRecordInEdit(record, sourceLabel) {
    loadRecordIntoWorkspace(record, sourceLabel, { startInEdit: true });
  }

  function buildFeedbackPayloadFromRecord(record, decisionType) {
    return {
      article_source: record.article_source,
      fournisseur_hint: cleanOptional(record.fournisseur_hint || ""),
      metier_hint: cleanOptional(record.metier_hint || ""),
      client_ape_hint: cleanOptional(record.client_ape_hint || ""),
      supplier_ape_hint: cleanOptional(record.supplier_ape_hint || ""),
      tva_hint: record.tva_hint == null ? null : Number(record.tva_hint),
      decision_humaine: decisionType,
      compte_comptable_final:
        decisionType === "rejeter" ? null : cleanOptional(record.compte_comptable || ""),
      categorie_finale: decisionType === "rejeter" ? null : cleanOptional(record.categorie || ""),
      sous_categorie_finale:
        decisionType === "rejeter" ? null : cleanOptional(record.sous_categorie || ""),
      commentaire: null,
      recommandation_ia: buildDecisionFromRecord(record),
    };
  }

  async function submitRecordFeedback(record, sourceLabel, decisionType) {
    if (decisionType !== "rejeter" && !record.compte_comptable) {
      setListActionStatus(
        "Impossible de valider directement cette ligne sans compte propose. Ouvre Corriger.",
      );
      return;
    }

    const actionKey = buildRecordActionKey(record);
    setListActionLoadingKey(actionKey);
    setListActionStatus(
      decisionType === "valider" ? "Validation en cours..." : "Enregistrement en cours...",
    );

    try {
      await sendFeedback(buildFeedbackPayloadFromRecord(record, decisionType));
      setListActionStatus(
        sourceLabel === "queue"
          ? "Validation enregistree depuis la file."
          : "Validation enregistree depuis l'historique.",
      );
      await refreshInsights();
    } catch (apiError) {
      setListActionStatus(apiError.message);
    } finally {
      setListActionLoadingKey("");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setFeedbackStatus("");
    setEditMode(false);

    try {
      const apiResult = await recommendLine(buildRecommendPayload());
      const contextMessage = buildContextMessage(apiResult, {
        fournisseurHint: cleanOptional(form.fournisseur_hint.trim()),
      });

      startTransition(() => {
        setResult(apiResult);
        setActiveTab("analyse");
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

  function useSelectedCandidateInEdit() {
    if (!selectedCandidate) {
      return;
    }

    setEditDraft(buildEditDraftFromCandidate(selectedCandidate));
    setEditMode(true);
    setFeedbackStatus(
      "Le candidat selectionne a ete copie dans le mode Modifier. Tu peux maintenant ajuster avant d'enregistrer.",
    );
    setAssistantStatus("Edition pre-remplie");
    setAssistantOpen(true);
  }

  function askAboutSelectedCandidate() {
    if (!selectedCandidate || assistantLoading) {
      return;
    }
    void submitAssistantMessage("Que penser du candidat selectionne ?");
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
        fournisseur_hint: cleanOptional(form.fournisseur_hint.trim()),
        metier_hint: cleanOptional(form.metier_hint.trim()),
        client_ape_hint: cleanOptional(form.client_ape_hint.trim()),
        supplier_ape_hint: cleanOptional(form.supplier_ape_hint.trim()),
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
          const contextMessage = buildContextMessage(updatedResult, {
            fournisseurHint: cleanOptional(form.fournisseur_hint.trim()),
          });
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
        fournisseur_hint: cleanOptional(form.fournisseur_hint.trim()),
        metier_hint: cleanOptional(form.metier_hint.trim()),
        client_ape_hint: cleanOptional(form.client_ape_hint.trim()),
        supplier_ape_hint: cleanOptional(form.supplier_ape_hint.trim()),
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
      const contextMessage = buildContextMessage(updatedResult, {
        fournisseurHint: cleanOptional(form.fournisseur_hint.trim()),
      });

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

  const selectedCandidate =
    result?.candidats?.find(
      (candidate, index) => buildCandidateKey(candidate, index) === selectedCandidateKey,
    ) || null;
  const isExpertMode = uiMode === "expert";
  const hasDraftArticle = form.article_source.trim().length > 0;
  const currentFournisseurHint = cleanOptional(form.fournisseur_hint.trim());
  const currentMetierHint = cleanOptional(form.metier_hint.trim());
  const currentClientApeHint = cleanOptional(form.client_ape_hint.trim());
  const currentSupplierApeHint = cleanOptional(form.supplier_ape_hint.trim());
  const currentTvaHint = form.tva_hint === "" ? null : Number(form.tva_hint);
  const quickPrompts = getAssistantQuickPrompts(result, editMode, Boolean(selectedCandidate));
  const resultSignalContext = {
    fournisseurHint: currentFournisseurHint,
    metierHint: currentMetierHint,
    clientApeHint: currentClientApeHint,
    supplierApeHint: currentSupplierApeHint,
    tvaHint: currentTvaHint,
  };
  const resultSignalPreview = buildDisplaySignals(result, resultSignalContext, true);
  const resultSignals = buildDisplaySignals(result, resultSignalContext, showInactiveSignals);
  const selectedCandidateSignals = buildSignalList(
    selectedCandidate?.signals || [],
    resultSignalContext,
    showInactiveSignals,
  );
  const selectedCandidateSignalPreview = buildSignalList(
    selectedCandidate?.signals || [],
    resultSignalContext,
    true,
  );
  const selectedCandidateActiveSignalCount = selectedCandidateSignalPreview.filter(
    (signal) => !signal.inactive,
  ).length;
  const topCandidate = result?.candidats?.[0] || null;
  const selectedCandidateOverviewCards =
    result?.candidats?.length > 0
      ? [
          {
            id: "top",
            label: "Top recommande",
            value: topCandidate?.compte_comptable || "-",
            helper: topCandidate
              ? `Score ${formatScore(
                  topCandidate.final_score ?? topCandidate.score_confiance,
                )} sur ${result.candidats.length} candidat${result.candidats.length > 1 ? "s" : ""}.`
              : "Aucun candidat moteur disponible.",
            tone: "summary-tone-purple",
          },
          {
            id: "active",
            label: "Candidat actif",
            value: selectedCandidate?.compte_comptable || "Aucun",
            helper: selectedCandidate
              ? "Le panneau de droite detaille ce candidat ligne par ligne."
              : "Selectionne un candidat pour ouvrir sa lecture detaillee.",
            tone: selectedCandidate ? "summary-tone-blue" : "summary-tone-muted",
          },
          {
            id: "signals",
            label: "Signaux actifs",
            value: selectedCandidate ? `${selectedCandidateActiveSignalCount}` : "-",
            helper: selectedCandidate
              ? `${selectedCandidateActiveSignalCount} signal${
                  selectedCandidateActiveSignalCount > 1 ? "s sont" : " a"
                } visible${selectedCandidateActiveSignalCount > 1 ? "s" : ""} sur ce candidat.`
              : "Les signaux apparaissent une fois le candidat ouvert.",
            tone: "summary-tone-violet",
          },
          {
            id: "text",
            label: "Score texte",
            value: selectedCandidate ? formatScore(selectedCandidate.score_texte ?? 0) : "-",
            helper: selectedCandidate
              ? "Indique la proximite brute entre le libelle saisi et la reference."
              : "Selectionne un candidat pour lire sa similarite texte.",
            tone: "summary-tone-green",
          },
        ]
      : [];
  const optionalContextCount = [
    currentFournisseurHint,
    currentMetierHint,
    currentClientApeHint,
    currentSupplierApeHint,
    currentTvaHint != null ? String(currentTvaHint) : null,
  ].filter(Boolean).length;
  const analysisContextCards = [
    {
      id: "line",
      label: "Ligne facture",
      value: hasDraftArticle ? "Prete" : "Requise",
      helper: hasDraftArticle
        ? "Le moteur peut deja lancer une recommandation."
        : "Ajoute le libelle pour declencher l'analyse.",
      tone: hasDraftArticle ? "context-ready" : "context-pending",
    },
    {
      id: "supplier",
      label: "Memoire fournisseur",
      value: currentFournisseurHint || "Optionnel",
      helper: currentFournisseurHint
        ? "L'historique du fournisseur pourra renforcer le ranking."
        : "Ajoute le fournisseur pour reutiliser la memoire existante.",
      tone: currentFournisseurHint ? "context-active" : "context-muted",
    },
    {
      id: "business",
      label: "Metier et TVA",
      value:
        currentMetierHint || currentTvaHint != null
          ? [currentMetierHint, currentTvaHint != null ? `TVA ${currentTvaHint}%` : null]
              .filter(Boolean)
              .join(" / ")
          : "Optionnels",
      helper:
        currentMetierHint || currentTvaHint != null
          ? "Le moteur peut verifier la coherence metier et fiscale."
          : "Ces indices renforcent les signaux metier et TVA.",
      tone:
        currentMetierHint || currentTvaHint != null ? "context-active" : "context-muted",
    },
    {
      id: "ape",
      label: "APE client et fournisseur",
      value:
        currentClientApeHint || currentSupplierApeHint
          ? [
              currentClientApeHint ? `Client ${currentClientApeHint}` : null,
              currentSupplierApeHint ? `Fourn. ${currentSupplierApeHint}` : null,
            ]
              .filter(Boolean)
              .join(" / ")
          : "Optionnels",
      helper:
        currentClientApeHint || currentSupplierApeHint
          ? "Le contexte APE est pret a alimenter le ranker."
          : "Ajoute les codes APE pour affiner la compatibilite metier.",
      tone:
        currentClientApeHint || currentSupplierApeHint ? "context-active" : "context-muted",
    },
  ];
  const assistantContextTitle = result?.article_source || "Aucune ligne analysee";
  const assistantContextSummary = result
    ? `Decision: ${decisionLabels[result.decision]} / Compte: ${result.compte_comptable || "-"}${
        currentFournisseurHint ? ` / Fournisseur: ${currentFournisseurHint}` : ""
      }`
    : hasDraftArticle
      ? `Une ligne est en cours de preparation dans le formulaire.${
          currentFournisseurHint ? ` Fournisseur: ${currentFournisseurHint}.` : ""
        } Lance l'analyse pour la charger ici.`
      : "Decision: Pas encore d'analyse / Compte: -";
  const assistantContextFocus = selectedCandidate
    ? `Candidat actif: ${selectedCandidate.compte_comptable} / ${selectedCandidate.article_source_match}`
    : currentFournisseurHint
      ? `Fournisseur en contexte: ${currentFournisseurHint}`
    : result?.candidats?.length
      ? "Aucun candidat actif choisi dans le panneau."
      : null;
  const canSaveModification =
    editDraft.compte_comptable.trim().length > 0 ||
    editDraft.categorie.trim().length > 0 ||
    editDraft.sous_categorie.trim().length > 0;
  const filteredHistory = analysisHistory.filter(
    (item) =>
      (historyFilter === "all" || item.decision === historyFilter) &&
      matchesInsightQuery(item, insightQuery),
  );
  const filteredQueue = validationQueue.filter((item) => matchesInsightQuery(item, insightQuery));
  const filteredHistoryKeyDigest = filteredHistory
    .map((item, index) => buildHistoryKey(item, index))
    .join("|");
  const selectedHistoryRecord =
    filteredHistory.find((item, index) => buildHistoryKey(item, index) === selectedHistoryKey) ||
    null;
  const historySignalContext = {
    fournisseurHint: selectedHistoryRecord?.fournisseur_hint || null,
    metierHint: selectedHistoryRecord?.metier_hint || null,
    clientApeHint: selectedHistoryRecord?.client_ape_hint || null,
    supplierApeHint: selectedHistoryRecord?.supplier_ape_hint || null,
    tvaHint: selectedHistoryRecord?.tva_hint ?? null,
  };
  const historySignals = buildDisplaySignals(
    selectedHistoryRecord,
    historySignalContext,
    showInactiveSignals,
  );
  const historySignalPreview = buildDisplaySignals(selectedHistoryRecord, historySignalContext, true);
  const historyActiveSignalCount = historySignalPreview.filter((signal) => !signal.inactive).length;
  const historyContextCount = [
    selectedHistoryRecord?.fournisseur_hint || null,
    selectedHistoryRecord?.metier_hint || null,
    selectedHistoryRecord?.client_ape_hint || null,
    selectedHistoryRecord?.supplier_ape_hint || null,
    selectedHistoryRecord?.tva_hint != null ? String(selectedHistoryRecord.tva_hint) : null,
  ].filter(Boolean).length;
  const activeHistoryFilter = historyFilters.find((filter) => filter.id === historyFilter);
  const historyFilterLabel = activeHistoryFilter?.label || "Tout";
  const historyOverviewCards = selectedHistoryRecord
    ? [
        {
          id: "source",
          label: "Source de decision",
          value: sourceLabels[selectedHistoryRecord.source || "engine"] || "Moteur",
          helper:
            selectedHistoryRecord.source === "memory"
              ? "Cette ligne a ete resservie depuis une validation deja connue."
              : selectedHistoryRecord.source === "ai"
                ? "La decision conserve une intervention IA au moment de l'analyse."
                : "La ligne a ete resolue par le moteur et ses signaux.",
          tone: "summary-tone-blue",
        },
        {
          id: "signals",
          label: "Signaux actifs",
          value: `${historyActiveSignalCount}`,
          helper: historySignalPreview.length
            ? `${historyActiveSignalCount} signal${
                historyActiveSignalCount > 1 ? "s ont" : " a"
              } contribue a la trace conservee.`
            : "Aucun signal detaille n'a ete conserve sur cette ligne.",
          tone: "summary-tone-violet",
        },
        {
          id: "context",
          label: "Contexte saisi",
          value: `${historyContextCount}`,
          helper:
            historyContextCount > 0
              ? "Nombre d'indices utilisateur conserves avec cette analyse."
              : "La ligne a ete analysee sans contexte metier supplementaire.",
          tone: "summary-tone-purple",
        },
        {
          id: "candidates",
          label: "Top 3 conserve",
          value: `${selectedHistoryRecord.candidats?.length || 0}`,
          helper: selectedHistoryRecord.candidats?.length
            ? "Le classement du moteur a ete archive avec cette analyse."
            : "Aucun candidat moteur n'a ete conserve pour cette ligne.",
          tone: "summary-tone-green",
        },
      ]
    : [];
  const dashboardAutoOkCount = analysisHistory.filter((item) => item.decision === "auto_ok").length;
  const dashboardValidationCount = analysisHistory.filter(
    (item) => item.decision === "validation_humaine",
  ).length;
  const dashboardRejectedCount = analysisHistory.filter((item) => item.decision === "rejeter").length;
  const dashboardMemoryCount = analysisHistory.filter((item) => item.source === "memory").length;
  const dashboardAutoOkRateValue = analysisHistory.length
    ? Math.round((dashboardAutoOkCount / analysisHistory.length) * 100)
    : null;
  const dashboardAutoOkRateLabel =
    dashboardAutoOkRateValue == null ? "-" : `${dashboardAutoOkRateValue}%`;
  const dashboardSummaryTone =
    !analysisHistory.length
      ? "dashboard-tone-blue"
      : validationQueue.length > 0
        ? "dashboard-tone-amber"
        : dashboardAutoOkRateValue != null && dashboardAutoOkRateValue >= 65
          ? "dashboard-tone-green"
          : "dashboard-tone-blue";
  const dashboardSummaryStatus = !analysisHistory.length
    ? "Pret"
    : validationQueue.length > 0
      ? "Action requise"
      : dashboardAutoOkRateValue != null && dashboardAutoOkRateValue >= 65
        ? "Stable"
        : "A suivre";
  const dashboardHeadline = !analysisHistory.length
    ? "Aucun flux recent a piloter"
    : validationQueue.length > 0
      ? validationQueue.length === 1
        ? "1 validation humaine reste ouverte"
        : `${validationQueue.length} validations humaines restent ouvertes`
      : dashboardAutoOkRateValue != null && dashboardAutoOkRateValue >= 65
        ? "Le flux recent reste bien calibre"
        : "Le flux recent doit encore etre consolide";
  const dashboardSummaryText = !analysisHistory.length
    ? "Lance quelques analyses pour remplir le pilotage, suivre l'automatisation et identifier les cas a arbitrer."
    : validationQueue.length > 0
      ? "La priorite est de vider la file humaine pour fiabiliser la memoire et garder un historique propre."
      : "La file est vide. Le pilotage consiste surtout a surveiller la memoire, les rejets et le niveau d'automatisation.";
  const dashboardOverviewMetrics = [
    {
      id: "rate",
      label: "Taux auto OK",
      value: dashboardAutoOkRateLabel,
      tone:
        dashboardAutoOkRateValue != null && dashboardAutoOkRateValue >= 65
          ? "dashboard-tone-green"
          : "dashboard-tone-blue",
    },
    {
      id: "queue",
      label: "A traiter",
      value: validationQueue.length,
      tone: validationQueue.length > 0 ? "dashboard-tone-orange" : "dashboard-tone-blue",
    },
    {
      id: "memory",
      label: "Memoire",
      value: memoryStats?.reusable_records ?? "-",
      tone: "dashboard-tone-amber",
    },
    {
      id: "rejected",
      label: "Rejets",
      value: dashboardRejectedCount,
      tone: dashboardRejectedCount > 0 ? "dashboard-tone-amber" : "dashboard-tone-green",
    },
  ];
  const dashboardCards = [
    {
      id: "history",
      label: "Historique charge",
      helper: "Base recente",
      value: analysisHistory.length,
      footnote: "Analyses conservees dans le suivi local",
      tone: "dashboard-tone-blue",
    },
    {
      id: "auto",
      label: "Auto OK recents",
      helper: "Decisions fiables",
      value: dashboardAutoOkCount,
      footnote: "Recommandations passees sans correction manuelle",
      tone: "dashboard-tone-green",
    },
    {
      id: "human",
      label: "Validation humaine",
      helper: "Arbitrages",
      value: dashboardValidationCount,
      footnote: "Cas recents ou le moteur est reste prudent",
      tone: "dashboard-tone-orange",
    },
    {
      id: "memory-analyses",
      label: "Analyses memoire",
      helper: "Reutilisations",
      value: dashboardMemoryCount,
      footnote: "Recommandations servies a partir d'une validation precedente",
      tone: "dashboard-tone-blue",
    },
    {
      id: "rejected",
      label: "Rejets recents",
      helper: "Exceptions",
      value: dashboardRejectedCount,
      footnote: "Cas a requalifier ou a corriger avec plus de contexte",
      tone: "dashboard-tone-amber",
    },
  ];
  const queueOverviewCards = [
    {
      id: "filtered",
      label: "A arbitrer",
      value: filteredQueue.length,
      helper: filteredQueue.length
        ? "Lignes visibles dans la file selon la recherche courante."
        : "Aucune ligne ne correspond au filtre courant.",
      tone: "summary-tone-amber",
    },
    {
      id: "total",
      label: "File totale",
      value: validationQueue.length,
      helper: "Volume global des validations humaines encore ouvertes.",
      tone: "summary-tone-purple",
    },
    {
      id: "memory-ready",
      label: "Memoire reutilisable",
      value: memoryStats?.reusable_records ?? "-",
      helper: "Validations reexploitables automatiquement par le moteur.",
      tone: "summary-tone-blue",
    },
    {
      id: "auto-rate",
      label: "Taux auto OK",
      value: dashboardAutoOkRateLabel,
      helper: "Indicateur rapide de stabilite du flux recent.",
      tone: "summary-tone-green",
    },
  ];
  const nextThemeMode = themeMode === "dark" ? "light" : "dark";
  const nextUiMode = isExpertMode ? "simple" : "expert";
  const resultSourceLabel = result ? sourceLabels[result.source || "engine"] || "Moteur" : null;
  const resultActiveSignalCount = resultSignalPreview.filter((signal) => !signal.inactive).length;
  const resultActiveSignals = resultSignalPreview
    .filter((signal) => !signal.inactive)
    .sort((left, right) => (right.contribution ?? 0) - (left.contribution ?? 0));
  const resultPrimaryMetier =
    currentMetierHint ||
    selectedCandidate?.metier ||
    topCandidate?.metier ||
    result?.categorie ||
    "-";
  const resultPrimarySource =
    result?.source === "memory"
      ? "Memoire fournisseur et validation humaine precedente"
      : resultActiveSignals.some((signal) => signal.key === "human_validation")
        ? "Memoire de validation et matching exact"
        : resultActiveSignals.some((signal) => signal.key === "supplier_memory")
          ? "Memoire fournisseur et ranking moteur"
          : resultActiveSignals.some((signal) => signal.key === "text_similarity")
            ? "Matching article et ranking moteur"
            : "Ranking moteur hybride";
  const resultNarrativeTitle =
    result?.decision === "auto_ok"
      ? "Decision comptable IA prete a valider"
      : result?.decision === "validation_humaine"
        ? "Niveau de confiance insuffisant"
        : "Decision comptable a requalifier";
  const resultNarrativeCopy =
    result?.decision === "auto_ok"
      ? "Le moteur estime que la recommandation est assez solide pour un traitement rapide."
      : result?.decision === "validation_humaine"
        ? "Le moteur prefere escalader ce cas plutot que de forcer une ecriture peu fiable."
        : "Le moteur detecte un risque de mauvaise imputation et prefere l'abstention.";
  const resultReasonBullets = [
    ...(result?.source === "memory"
      ? [
          {
            title: "Memoire reutilisee",
            copy: "Une validation humaine precedente sur un contexte proche a ete rejouee.",
          },
        ]
      : []),
    ...resultActiveSignals.slice(0, 4).map((signal) => ({
      title: signal.label,
      copy: signal.explanation,
    })),
  ];
  const rankedCandidates = (result?.candidats || []).slice(0, 3).map((candidate, index) => ({
    ...candidate,
    rank: index + 1,
    width: `${Math.max(14, clampPercent(candidate.final_score ?? candidate.score_confiance))}%`,
    sourceLabel:
      candidate.signals?.find((signal) => signal.key === "human_validation")?.label ||
      candidate.signals?.find((signal) => signal.key === "supplier_memory")?.label ||
      candidate.signals?.find((signal) => signal.key === "text_similarity")?.label ||
      candidate.raison_match ||
      "Ranking moteur",
  }));
  const explicabilityRows = resultActiveSignals.slice(0, 6).map((signal) => ({
    key: signal.key,
    label: signal.label,
    family: signalFamilyLabels[signal.family] || signal.family,
    contributionLabel: formatScore(signal.contribution),
    width: `${Math.max(8, clampPercent(signal.contribution ?? 0))}%`,
  }));
  const memoryReuseRate =
    memoryStats?.total_records && memoryStats.total_records > 0
      ? Math.round((memoryStats.reusable_records / memoryStats.total_records) * 100)
      : null;
  const memoryReplayItems = analysisHistory.filter((item) => item.source === "memory").slice(0, 8);
  const latestValidationReadyItems = analysisHistory
    .filter((item) => item.decision === "auto_ok" || item.source === "memory")
    .slice(0, 8);
  const memoryCards = [
    {
      id: "records",
      label: "Enregistrements memoire",
      value: memoryStats?.total_records ?? "-",
      helper: "Volume total des validations humaines memorisees.",
      tone: "summary-tone-purple",
    },
    {
      id: "reusable",
      label: "Reutilisables",
      value: memoryStats?.reusable_records ?? "-",
      helper: "Validations directement rejouables par le moteur.",
      tone: "summary-tone-green",
    },
    {
      id: "replay-rate",
      label: "Taux de reemploi",
      value: memoryReuseRate == null ? "-" : `${memoryReuseRate}%`,
      helper: "Part de la memoire actuellement exploitable sans correction.",
      tone: "summary-tone-blue",
    },
    {
      id: "served",
      label: "Analyses servies par memoire",
      value: dashboardMemoryCount,
      helper: "Nombre de recommandations recentes servies depuis l'historique humain.",
      tone: "summary-tone-amber",
    },
  ];
  const dashboardKpis = [
    {
      id: "auto",
      label: "Auto OK",
      value: dashboardAutoOkCount,
      helper: "Decisions sorties sans validation supplementaire.",
      tone: "dashboard-tone-green",
    },
    {
      id: "validation",
      label: "Validation humaine",
      value: dashboardValidationCount,
      helper: "Cas ou le moteur choisit l'escalade.",
      tone: "dashboard-tone-orange",
    },
    {
      id: "confidence",
      label: "Taux confiance",
      value: dashboardAutoOkRateLabel,
      helper: "Part des analyses recentes qui finissent en Auto OK.",
      tone: "dashboard-tone-blue",
    },
    {
      id: "reuse",
      label: "Memoire reutilisee",
      value: dashboardMemoryCount,
      helper: "Recommandations resservies depuis des validations existantes.",
      tone: "dashboard-tone-amber",
    },
  ];
  const resultOverviewCards = result
    ? [
        {
          id: "confidence",
          label: "Confiance finale",
          value: formatScore(result.score_confiance),
          helper: "Score retenu pour la recommandation affichee.",
          tone: "result-tone-purple",
        },
        {
          id: "source",
          label: "Source",
          value: resultSourceLabel || "Moteur",
          helper:
            result.source === "memory"
              ? "La memoire utilisateur a servi une validation precedente."
              : result.source === "ai"
                ? "La recommandation a ete consolidee par l'IA."
                : "La decision vient du moteur de matching et des signaux.",
          tone: "result-tone-blue",
        },
        {
          id: "workflow",
          label: "Parcours recommande",
          value: decisionLabels[result.decision],
          helper:
            result.decision === "auto_ok"
              ? "La ligne est suffisamment solide pour un traitement rapide."
              : result.decision === "validation_humaine"
                ? "Une verification humaine reste conseillee avant validation."
                : "Le moteur prefere rejeter ou requalifier cette ligne.",
          tone:
            result.decision === "auto_ok"
              ? "result-tone-green"
              : result.decision === "validation_humaine"
                ? "result-tone-amber"
                : "result-tone-rose",
        },
        {
          id: "signals",
          label: "Signaux actifs",
          value: `${resultActiveSignalCount}`,
          helper: resultSignalPreview.length
            ? `${resultActiveSignalCount} signal${
                resultActiveSignalCount > 1 ? "s ont" : " a"
              } contribue a la decision.`
            : "Aucun signal detaille n'est visible pour cette ligne.",
          tone: "result-tone-violet",
        },
      ]
    : [];
  const selectedHistoryActionKey = selectedHistoryRecord
    ? buildRecordActionKey(selectedHistoryRecord)
    : "";

  useEffect(() => {
    if (!filteredHistory.length) {
      if (selectedHistoryKey !== null) {
        setSelectedHistoryKey(null);
      }
      return;
    }

    const hasSelectedHistory = filteredHistory.some(
      (item, index) => buildHistoryKey(item, index) === selectedHistoryKey,
    );

    if (!hasSelectedHistory) {
      setSelectedHistoryKey(buildHistoryKey(filteredHistory[0], 0));
    }
  }, [filteredHistoryKeyDigest, selectedHistoryKey]);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className={`hero-topbar ${health ? "hero-topbar-online" : "hero-topbar-offline"}`}>
          <div className="hero-brand">
            <div className="hero-brand-copy">
              <div className="hero-title-row">
                <div className="hero-brand-mark" aria-hidden="true">
                  <img className="hero-brand-logo" src={keyManageIcon} alt="" />
                </div>
                <p className="hero-brand-title">KeyManage</p>
                <span
                  className={`hero-status-dot ${
                    health ? "hero-status-dot-online" : "hero-status-dot-offline"
                  }`}
                  aria-hidden="true"
                />
              </div>
              <p className="hero-brand-subtitle">
                Assistant intelligent de recommandation comptable fournisseur
              </p>
            </div>
          </div>

          <div className="hero-actions">
            <div className="topbar-pill topbar-pill-status">
              <span className={`status-dot ${health ? "status-dot-online" : "status-dot-offline"}`} />
              <span>{health ? "Systeme en ligne" : "Systeme hors ligne"}</span>
            </div>

            <button
              className="topbar-pill topbar-pill-button topbar-pill-button-theme"
              type="button"
              onClick={() => setThemeMode(nextThemeMode)}
            >
              <img
                className="topbar-pill-logo topbar-pill-logo-theme"
                src={themeMode === "dark" ? topbarThemeMoonIcon : topbarThemeSunIcon}
                alt=""
              />
              <span>{themeMode === "dark" ? "Theme sombre" : "Theme clair"}</span>
            </button>

            <button
              className="topbar-pill topbar-pill-button"
              type="button"
              onClick={() => setUiMode(nextUiMode)}
            >
              <img
                className="topbar-pill-logo topbar-pill-logo-ui"
                src={isExpertMode ? topbarUiExpertIcon : topbarUiSimpleIcon}
                alt=""
              />
              <span>{isExpertMode ? "Mode expert" : "Mode simple"}</span>
            </button>

            <button
              className="topbar-primary"
              type="button"
              onClick={() => setAssistantOpen(true)}
            >
              <img className="topbar-primary-logo" src={topbarAssistantIcon} alt="" />
              Ouvrir assistant
            </button>
          </div>
        </div>

        <div className="hero-controls hero-controls-top">
          <div className="tab-row tab-row-topbar">
            {interfaceTabs.map((tab) => (
              <button
                key={tab.id}
                className={`tab-button ${activeTab === tab.id ? "tab-button-active" : ""}`}
                type="button"
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {healthError ? <p className="panel-error">{healthError}</p> : null}
      </section>

      {activeTab === "analyse" ? (
        <section className="workspace-grid">
        <form className="panel form-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <p className="eyebrow">Analyse</p>
            <h2>Quelle ecriture comptable proposer ?</h2>
          </div>

          <p className="panel-info">
            Saisis la ligne facture, ajoute le contexte utile, puis laisse le moteur hybride
            arbitrer entre memoire, matching article, compatibilite metier et validation humaine.
          </p>

          <section className="analysis-context-band" aria-label="Contexte de saisie">
            <div className="analysis-context-band-copy">
              <span className="analysis-context-kicker">Contexte capture</span>
              <strong>
                {hasDraftArticle
                  ? optionalContextCount > 0
                    ? `${optionalContextCount} indice${optionalContextCount > 1 ? "s" : ""} actif${
                        optionalContextCount > 1 ? "s" : ""
                      }`
                    : "Analyse minimale prete"
                  : "Complete d'abord le libelle"}
              </strong>
              <p>
                Plus tu renseignes le contexte fournisseur, metier, TVA ou APE, plus les signaux
                visibles dans l'Entry Ranker deviennent explicites et stables.
              </p>
            </div>

            <div className="analysis-context-grid">
              {analysisContextCards.map((card) => (
                <article className={`analysis-context-card ${card.tone}`} key={card.id}>
                  <span className="analysis-context-label">{card.label}</span>
                  <strong className="analysis-context-value">{card.value}</strong>
                  <p className="analysis-context-helper">{card.helper}</p>
                </article>
              ))}
            </div>
          </section>

          <label className="field">
            <span>Libelle de ligne facture</span>
            <textarea
              rows="4"
              value={form.article_source}
              onChange={(event) =>
                setForm((current) => ({ ...current, article_source: event.target.value }))
              }
              placeholder="Ex: AUBERGINE CI ou Electricite mars 2025"
              required
            />
          </label>

          <label className="field">
            <span>Fournisseur (optionnel)</span>
            <input
              type="text"
              value={form.fournisseur_hint}
              onChange={(event) =>
                setForm((current) => ({ ...current, fournisseur_hint: event.target.value }))
              }
              placeholder="Ex: Metro, EDF, Uber, Orange"
            />
          </label>

          <div className="field-row">
            <label className="field">
              <span>Metier (optionnel)</span>
              <input
                type="text"
                value={form.metier_hint}
                onChange={(event) =>
                  setForm((current) => ({ ...current, metier_hint: event.target.value }))
                }
                placeholder="Ex: epicerie, vtc, coiffure"
              />
            </label>

            <label className="field">
              <span>TVA (optionnelle)</span>
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

          <div className="field-row">
            <label className="field">
              <span>APE client (optionnel)</span>
              <input
                type="text"
                value={form.client_ape_hint}
                onChange={(event) =>
                  setForm((current) => ({ ...current, client_ape_hint: event.target.value }))
                }
                placeholder="Ex: 4711D"
                autoCapitalize="characters"
                spellCheck="false"
              />
            </label>

            <label className="field">
              <span>APE fournisseur (optionnel)</span>
              <input
                type="text"
                value={form.supplier_ape_hint}
                onChange={(event) =>
                  setForm((current) => ({ ...current, supplier_ape_hint: event.target.value }))
                }
                placeholder="Ex: 4322A"
                autoCapitalize="characters"
                spellCheck="false"
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
            <p className="eyebrow">Resultat IA</p>
            <h2>Decision comptable IA</h2>
          </div>

          {result ? (
            <>
              <div className="result-header">
                <div>
                  <p className="result-title">{result.article_source}</p>
                  <p className="result-subtitle">{result.explication}</p>
                </div>
                <div className="result-badge-stack">
                  {resultSourceLabel ? (
                    <span className={`source-chip source-${result.source || "engine"}`}>
                      {resultSourceLabel}
                    </span>
                  ) : null}
                  <span className={`decision-chip decision-${result.decision}`}>
                    {decisionLabels[result.decision]}
                  </span>
                </div>
              </div>

              <section className="ai-decision-hero">
                <div className="ai-decision-copy">
                  <span className="ai-decision-kicker">Compte recommande</span>
                  <strong className="ai-decision-account">{result.compte_comptable || "-"}</strong>
                  <p className="ai-decision-caption">
                    {result.categorie || "categorie a preciser"}
                    {result.sous_categorie ? ` / ${result.sous_categorie}` : ""}
                  </p>
                </div>

                <div className="ai-decision-side">
                  <article className="ai-decision-stat">
                    <span>Confiance</span>
                    <strong>{formatScore(result.score_confiance)}</strong>
                  </article>
                  <article className="ai-decision-stat">
                    <span>Mode</span>
                    <strong>{decisionLabels[result.decision]}</strong>
                  </article>
                  <article className="ai-decision-stat">
                    <span>Metier detecte</span>
                    <strong>{resultPrimaryMetier}</strong>
                  </article>
                  <article className="ai-decision-stat">
                    <span>Source principale</span>
                    <strong>{resultPrimarySource}</strong>
                  </article>
                </div>
              </section>

              <div
                className={`decision-alert decision-alert-${
                  result.decision === "auto_ok" ? "success" : "warning"
                }`}
              >
                <strong>{resultNarrativeTitle}</strong>
                <span>{resultNarrativeCopy}</span>
              </div>

              {result.source === "memory" ? (
                <div className="memory-banner">
                  <strong>Suggestion issue de la memoire utilisateur</strong>
                  <span>
                    Le backend a reutilise une validation humaine precedente pour ce meme libelle.
                  </span>
                </div>
              ) : null}

              <div className="result-overview-grid">
                {resultOverviewCards.map((card) => (
                  <article className={`result-overview-card ${card.tone}`} key={card.id}>
                    <span className="result-overview-label">{card.label}</span>
                    <strong>{card.value}</strong>
                    <p className="result-overview-helper">{card.helper}</p>
                  </article>
                ))}
              </div>

              <div className="decision-explainer-grid">
                <section className="decision-explainer-card">
                  <div className="panel-heading compact">
                    <p className="eyebrow">Pourquoi cette recommandation ?</p>
                    <h3>Lecture humaine de la decision</h3>
                  </div>

                  <div className="reason-bullet-list">
                    {resultReasonBullets.length > 0 ? (
                      resultReasonBullets.map((reason, index) => (
                        <article className="reason-bullet" key={`${reason.title}-${index}`}>
                          <strong>{reason.title}</strong>
                          <p>{reason.copy}</p>
                        </article>
                      ))
                    ) : (
                      <div className="candidate-empty-state">
                        Aucun signal detaille n'est disponible pour expliquer cette ligne.
                      </div>
                    )}
                  </div>
                </section>

                <section className="decision-explainer-card">
                  <div className="panel-heading compact">
                    <p className="eyebrow">Explicabilite</p>
                    <h3>Poids des signaux</h3>
                  </div>

                  {explicabilityRows.length > 0 ? (
                    <div className="score-stack">
                      {explicabilityRows.map((row) => (
                        <article className="score-stack-row" key={row.key}>
                          <div className="score-stack-copy">
                            <strong>{row.label}</strong>
                            <span>{row.family}</span>
                          </div>
                          <div className="score-stack-bar-shell">
                            <div className="score-stack-bar" style={{ width: row.width }} />
                          </div>
                          <span className="score-stack-value">{row.contributionLabel}</span>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="candidate-empty-state">
                      Aucun poids de signal n'est visible pour cette ligne.
                    </div>
                  )}
                </section>
              </div>

              <section className="ranking-showcase">
                <div className="panel-heading compact">
                  <p className="eyebrow">Top candidats</p>
                  <h3>Ranking comptable top-k</h3>
                </div>

                {rankedCandidates.length > 0 ? (
                  <div className="ranking-bars">
                    {rankedCandidates.map((candidate) => (
                      <article className="ranking-row" key={`${candidate.rank}-${candidate.compte_comptable}`}>
                        <div className="ranking-main">
                          <span className="ranking-rank">#{candidate.rank}</span>
                          <div className="ranking-copy">
                            <strong>{candidate.compte_comptable}</strong>
                            <span>{candidate.sourceLabel}</span>
                          </div>
                        </div>
                        <div className="ranking-bar-shell">
                          <div className="ranking-bar" style={{ width: candidate.width }} />
                        </div>
                        <strong className="ranking-score">
                          {formatScore(candidate.final_score ?? candidate.score_confiance)}
                        </strong>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="candidate-empty-state">
                    Aucun top-k moteur n'est disponible pour cette recommandation.
                  </div>
                )}
              </section>

              {resultSignals.length > 0 ? (
                <div className="signal-summary-panel">
                  <div className="signal-summary-toolbar">
                    <div className="panel-heading compact">
                      <p className="eyebrow">Signaux detectes</p>
                      <h3>Moteur hybride et signaux utilises</h3>
                    </div>
                    <label className="checkbox-row signal-toggle-row">
                      <input
                        type="checkbox"
                        checked={showInactiveSignals}
                        onChange={(event) => setShowInactiveSignals(event.target.checked)}
                      />
                      <span>Afficher aussi les signaux non actives</span>
                    </label>
                  </div>
                  <div className="signal-card-grid">
                    {resultSignals.map((signal) => (
                      <article
                        className={`signal-card signal-card-${signal.family} ${
                          signal.inactive ? "signal-card-inactive" : ""
                        }`}
                        key={`${signal.key}-${signal.family}`}
                      >
                        <div className="signal-card-topline">
                          <span className="signal-family-label">
                            {signalFamilyLabels[signal.family] || signal.family}
                          </span>
                          <strong>{signal.label}</strong>
                        </div>
                        <div className="signal-card-metrics">
                          <span>Valeur {formatSignalValue(signal.value)}</span>
                          <span>Contribution {formatScore(signal.contribution)}</span>
                        </div>
                        <p className="signal-card-copy">{signal.explanation}</p>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

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

              {isExpertMode ? (
                <div className="candidate-list">
                <div className="candidate-toolbar">
                  <div className="panel-heading compact">
                    <p className="eyebrow">Top 3</p>
                    <h3>Candidats retournes par le moteur</h3>
                  </div>
                  <p className="candidate-toolbar-note">
                    Compare les candidats, les alertes et les raisons de match.
                  </p>
                </div>

                {result.candidats.length > 0 ? (
                  <>
                    <div className="workspace-summary-grid candidate-overview-grid">
                      {selectedCandidateOverviewCards.map((card) => (
                        <article className={`workspace-summary-card ${card.tone}`} key={card.id}>
                          <span className="workspace-summary-label">{card.label}</span>
                          <strong>{card.value}</strong>
                          <p className="workspace-summary-helper">{card.helper}</p>
                        </article>
                      ))}
                    </div>

                    <div className="candidate-layout">
                    <div className="candidate-cards">
                      {result.candidats.map((candidate, index) => {
                        const candidateKey = buildCandidateKey(candidate, index);
                        const isSelected = candidateKey === selectedCandidateKey;

                        return (
                          <article
                            className={`candidate-card ${
                              result.compte_comptable &&
                              candidate.compte_comptable === result.compte_comptable
                                ? "candidate-card-selected"
                                : ""
                            } ${isSelected ? "candidate-card-focused" : ""}`}
                            key={candidateKey}
                          >
                            <div className="candidate-topline">
                              <div className="candidate-topline-left">
                                <span className="candidate-rank">#{index + 1}</span>
                                <strong>{candidate.compte_comptable}</strong>
                              </div>
                              <span>{formatScore(candidate.score_confiance)}</span>
                            </div>
                            <p className="candidate-title">{candidate.article_source_match}</p>
                            <p className="candidate-meta">
                              {candidate.categorie} / {candidate.sous_categorie} / {candidate.metier}
                            </p>
                            <div className="candidate-pill-row">
                              <span
                                className={`decision-chip decision-${candidate.decision || "validation_humaine"}`}
                              >
                                {decisionLabels[candidate.decision] || candidate.decision}
                              </span>
                              <span className="candidate-mini-pill">
                                TVA{" "}
                                {coherenceLabels[candidate.tva_coherence] || candidate.tva_coherence}
                              </span>
                              <span className="candidate-mini-pill">
                                Metier{" "}
                                {coherenceLabels[candidate.metier_coherence] ||
                                  candidate.metier_coherence}
                              </span>
                            </div>

                            <button
                              className="candidate-toggle"
                              type="button"
                              onClick={() => setSelectedCandidateKey(candidateKey)}
                            >
                              {isSelected ? "Panneau ouvert" : "Voir dans le panneau"}
                            </button>
                          </article>
                        );
                      })}
                    </div>

                    {selectedCandidate ? (
                      <aside className="candidate-side-panel">
                        <div className="candidate-side-header">
                          <div>
                            <p className="eyebrow">Candidat actif</p>
                            <h4>{selectedCandidate.article_source_match}</h4>
                          </div>
                          <span
                            className={`decision-chip decision-${
                              selectedCandidate.decision || "validation_humaine"
                            }`}
                          >
                            {decisionLabels[selectedCandidate.decision] ||
                              selectedCandidate.decision}
                          </span>
                        </div>

                        <div className="candidate-detail-grid">
                          <article className="candidate-detail-card">
                            <span>Compte</span>
                            <strong>{selectedCandidate.compte_comptable}</strong>
                          </article>
                          <article className="candidate-detail-card">
                            <span>Score</span>
                            <strong>
                              {formatScore(
                                selectedCandidate.final_score ?? selectedCandidate.score_confiance,
                              )}
                            </strong>
                          </article>
                          <article className="candidate-detail-card">
                            <span>Texte</span>
                            <strong>{formatScore(selectedCandidate.score_texte ?? 0)}</strong>
                          </article>
                          <article className="candidate-detail-card">
                            <span>TVA</span>
                            <strong>
                              {coherenceLabels[selectedCandidate.tva_coherence] ||
                                selectedCandidate.tva_coherence}
                            </strong>
                          </article>
                          <article className="candidate-detail-card">
                            <span>Metier</span>
                            <strong>
                              {coherenceLabels[selectedCandidate.metier_coherence] ||
                                selectedCandidate.metier_coherence}
                            </strong>
                          </article>
                        </div>

                        <div className="candidate-side-section">
                          <span className="candidate-alerts-label">Classement</span>
                          <p className="candidate-side-copy">
                            {selectedCandidate.categorie} / {selectedCandidate.sous_categorie} /{" "}
                            {selectedCandidate.metier}
                          </p>
                        </div>

                        <div className="candidate-side-section">
                          <span className="candidate-alerts-label">Raison de match</span>
                          <p className="candidate-side-copy">{selectedCandidate.raison_match}</p>
                        </div>

                        {selectedCandidateSignals.length ? (
                          <div className="candidate-side-section">
                            <span className="candidate-alerts-label">Signaux du score</span>
                            <div className="signal-card-grid compact">
                              {selectedCandidateSignals.map((signal) => (
                                <article
                                  className={`signal-card signal-card-${signal.family} ${
                                    signal.inactive ? "signal-card-inactive" : ""
                                  }`}
                                  key={`${selectedCandidate.compte_comptable}-${signal.key}`}
                                >
                                  <div className="signal-card-topline">
                                    <span className="signal-family-label">
                                      {signalFamilyLabels[signal.family] || signal.family}
                                    </span>
                                    <strong>{signal.label}</strong>
                                  </div>
                                  <div className="signal-card-metrics">
                                    <span>Valeur {formatSignalValue(signal.value)}</span>
                                    <span>Contribution {formatScore(signal.contribution)}</span>
                                  </div>
                                  <p className="signal-card-copy">{signal.explanation}</p>
                                </article>
                              ))}
                            </div>
                          </div>
                        ) : null}

                        <div className="candidate-side-actions">
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={useSelectedCandidateInEdit}
                          >
                            Utiliser ce candidat dans Modifier
                          </button>
                          <button
                            className="candidate-link-button"
                            type="button"
                            onClick={askAboutSelectedCandidate}
                            disabled={assistantLoading}
                          >
                            Demander l'avis de l'assistant
                          </button>
                        </div>

                        <div className="candidate-side-section">
                          <span className="candidate-alerts-label">Alertes</span>
                          {selectedCandidate.alertes?.length ? (
                            <div className="candidate-alert-list">
                              {selectedCandidate.alertes.map((alert, alertIndex) => (
                                <span className="candidate-alert-pill" key={`${alert}-${alertIndex}`}>
                                  {alert}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <div className="candidate-alert-empty">
                              Aucune alerte sur ce candidat.
                            </div>
                            )}
                          </div>

                        {isExpertMode ? (
                          <div className="candidate-side-section">
                            <span className="candidate-alerts-label">Pieces sources</span>
                            {selectedCandidate.source_invoice_ids?.length ? (
                              <div className="candidate-source-list">
                                {selectedCandidate.source_invoice_ids.map((sourceId) => (
                                  <code key={sourceId} className="candidate-source-pill">
                                    {sourceId}
                                  </code>
                                ))}
                              </div>
                            ) : (
                              <div className="candidate-alert-empty">
                                Aucune piece source rattachee.
                              </div>
                            )}
                          </div>
                        ) : null}
                      </aside>
                    ) : null}
                    </div>
                  </>
                ) : (
                  <div className="candidate-empty-state">
                    La reponse actuelle provient de la memoire des validations humaines. Aucun
                    candidat moteur n'est affiche pour ce cas.
                  </div>
                )}
                </div>
              ) : (
                <div className="candidate-empty-state simple-mode-note">
                  Le mode simple masque le Top 3 et les details moteurs. Passe en mode expert pour
                  comparer les candidats et lire les alertes.
                </div>
              )}
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
      ) : null}

      {activeTab === "historique" || activeTab === "validation" ? (
        <section className="panel command-panel">
            <div className="command-bar">
              <label className="field search-field">
                <span>Recherche rapide</span>
                <input
                  type="text"
                  value={insightQuery}
                  onChange={(event) => setInsightQuery(event.target.value)}
                  placeholder="Ex: uber, 6281, electricite, frais fixes..."
                />
              </label>

              {activeTab === "historique" ? (
                <div className="filter-group">
                  <span className="filter-label">Historique</span>
                  <div className="filter-chip-row">
                    {historyFilters.map((filter) => (
                      <button
                        key={filter.id}
                        className={`filter-chip ${historyFilter === filter.id ? "filter-chip-active" : ""}`}
                        type="button"
                        onClick={() => setHistoryFilter(filter.id)}
                      >
                        {filter.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <button
                className="secondary-button refresh-button"
                type="button"
                onClick={() => void refreshInsights()}
                disabled={insightsLoading}
              >
                {insightsLoading ? "Rafraichissement..." : "Rafraichir"}
              </button>
            </div>
          </section>
      ) : null}

      {activeTab === "pilotage" ? (
        <section className="dashboard-grid">
          <section className="panel dashboard-panel">
            <div className="dashboard-panel-head">
              <div className="panel-heading compact">
                <p className="eyebrow">Dashboard</p>
                <h3>Pilotage du moteur comptable</h3>
              </div>

              <span className={`dashboard-summary-status ${dashboardSummaryTone}`}>
                {dashboardSummaryStatus}
              </span>
            </div>

            <div className="dashboard-overview-band">
              <div className="dashboard-overview-copy">
                <p className="dashboard-overview-kicker">Pilotage recent</p>
                <h4>{dashboardHeadline}</h4>
                <p>{dashboardSummaryText}</p>
              </div>

              <div className="dashboard-overview-metrics">
                {dashboardOverviewMetrics.map((metric) => (
                  <article className={`dashboard-overview-metric ${metric.tone}`} key={metric.id}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                  </article>
                ))}
              </div>
            </div>

            <div className="dashboard-card-grid">
              {dashboardKpis.map((card) => (
                <article className={`dashboard-stat-card ${card.tone}`} key={card.id}>
                  <div className="dashboard-stat-topline">
                    <span className="dashboard-stat-helper">{card.helper}</span>
                  </div>
                  <p className="dashboard-stat-label">{card.label}</p>
                  <strong className="dashboard-stat-value">{card.value}</strong>
                  <span className="dashboard-stat-footnote">{card.helper}</span>
                </article>
              ))}
            </div>
          </section>

          <section className="panel dashboard-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Analytics</p>
              <h3>Repartition du flux de decision</h3>
            </div>

            <div className="dashboard-card-grid">
              {dashboardCards.map((card) => (
                <article className={`dashboard-stat-card ${card.tone}`} key={card.id}>
                  <div className="dashboard-stat-topline">
                    <span className="dashboard-stat-helper">{card.helper}</span>
                  </div>
                  <p className="dashboard-stat-label">{card.label}</p>
                  <strong className="dashboard-stat-value">{card.value}</strong>
                  <span className="dashboard-stat-footnote">{card.footnote}</span>
                </article>
              ))}
            </div>
          </section>
        </section>
      ) : null}

      {activeTab === "validation" ? (
        <section className="dashboard-grid">
          <section className="panel insight-panel dashboard-queue-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Validation humaine</p>
              <h3>File d'escalade metier</h3>
            </div>

            {insightsError ? <p className="panel-error">{insightsError}</p> : null}

            <div className="workspace-summary-grid queue-overview-grid">
              {queueOverviewCards.map((card) => (
                <article className={`workspace-summary-card ${card.tone}`} key={card.id}>
                  <span className="workspace-summary-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="workspace-summary-helper">{card.helper}</p>
                </article>
              ))}
            </div>

            <div className="insight-list">
              {filteredQueue.length > 0 ? (
                filteredQueue.map((item, index) => {
                  const recordActionKey = buildRecordActionKey(item);
                  const isActionLoading = listActionLoadingKey === recordActionKey;

                  return (
                    <article
                      className="insight-card insight-card-queue insight-card-shell"
                      key={`${item.lookup_key}-${item.created_at}-${index}`}
                    >
                      <button
                        className="insight-card-body"
                        type="button"
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

                      <div className="insight-card-actions">
                        <button
                          className="secondary-button insight-inline-button"
                          type="button"
                          onClick={() => void submitRecordFeedback(item, "queue", "valider")}
                          disabled={isActionLoading || !item.compte_comptable}
                        >
                          {isActionLoading ? "Validation..." : "Valider"}
                        </button>
                        <button
                          className="candidate-link-button insight-inline-button"
                          type="button"
                          onClick={() => openRecordInEdit(item, "queue")}
                        >
                          Corriger
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <div className="candidate-empty-state">
                  {insightsLoading
                    ? "Chargement de la file..."
                    : "Aucune ligne de validation ne correspond a la recherche actuelle."}
                </div>
              )}
            </div>

            {listActionStatus ? <p className="panel-info panel-info-inline">{listActionStatus}</p> : null}
          </section>

          <section className="panel dashboard-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Workflow</p>
              <h3>Pourquoi le moteur escalade</h3>
            </div>

            <div className="reason-bullet-list">
              <article className="reason-bullet">
                <strong>Abstention intelligente</strong>
                <p>
                  Le moteur n'impose pas une ecriture quand le score, la trace ou la coherence
                  metier restent insuffisants.
                </p>
              </article>
              <article className="reason-bullet">
                <strong>Validation humaine</strong>
                <p>
                  Les corrections humaines enrichissent la memoire et reduisent la friction sur les
                  cas similaires suivants.
                </p>
              </article>
              <article className="reason-bullet">
                <strong>Trajectoire produit</strong>
                <p>
                  Cette file doit rester visible et traitee separement pour distinguer le moteur,
                  l'audit et les arbitrages metier.
                </p>
              </article>
            </div>
          </section>
        </section>
      ) : null}

      {activeTab === "historique" ? (
        <section className="history-grid">
          <section className="panel insight-panel history-list-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Historique</p>
              <h3>Analyses ligne par ligne</h3>
            </div>

            {insightsError ? <p className="panel-error">{insightsError}</p> : null}

            <div className="history-list-summary">
              <span className="history-list-summary-label">Lecture rapide</span>
              <strong>
                {filteredHistory.length} ligne{filteredHistory.length > 1 ? "s" : ""} visible
                {filteredHistory.length > 1 ? "s" : ""}
              </strong>
              <p>
                Filtre {historyFilterLabel}
                {insightQuery ? ` / recherche "${insightQuery}"` : " / sans recherche libre"}.
              </p>
            </div>

            <div className="insight-list">
              {filteredHistory.length > 0 ? (
                filteredHistory.map((item, index) => {
                  const historyKey = buildHistoryKey(item, index);
                  const isActive = historyKey === selectedHistoryKey;

                  return (
                    <button
                      className={`insight-card ${isActive ? "insight-card-active" : ""}`}
                      type="button"
                      key={historyKey}
                      onClick={() => setSelectedHistoryKey(historyKey)}
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
                  );
                })
              ) : (
                <div className="candidate-empty-state">
                  {insightsLoading
                    ? "Chargement de l'historique..."
                    : "Aucune analyse ne correspond au filtre actuel."}
                </div>
              )}
            </div>
          </section>

          <section className="panel history-detail-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Detail</p>
              <h3>Lecture complete d'une ligne</h3>
            </div>

            {selectedHistoryRecord ? (
              <div className="history-detail-stack">
                <div className="result-header history-detail-header">
                  <div>
                    <p className="result-title">{selectedHistoryRecord.article_source}</p>
                    <p className="result-subtitle">{selectedHistoryRecord.explication}</p>
                  </div>
                  <span className={`decision-chip decision-${selectedHistoryRecord.decision}`}>
                    {decisionLabels[selectedHistoryRecord.decision]}
                  </span>
                </div>

                <div className="workspace-summary-grid history-overview-grid">
                  {historyOverviewCards.map((card) => (
                    <article className={`workspace-summary-card ${card.tone}`} key={card.id}>
                      <span className="workspace-summary-label">{card.label}</span>
                      <strong>{card.value}</strong>
                      <p className="workspace-summary-helper">{card.helper}</p>
                    </article>
                  ))}
                </div>

                <div className="metric-grid history-metric-grid">
                  <article className="metric-card accent-orange">
                    <span>Compte</span>
                    <strong>{selectedHistoryRecord.compte_comptable || "-"}</strong>
                  </article>
                  <article className="metric-card accent-green">
                    <span>Score</span>
                    <strong>{formatScore(selectedHistoryRecord.score_confiance)}</strong>
                  </article>
                  <article className="metric-card accent-blue">
                    <span>Metier</span>
                    <strong>{selectedHistoryRecord.metier_hint || "-"}</strong>
                  </article>
                  <article className="metric-card accent-amber">
                    <span>Fournisseur</span>
                    <strong>{selectedHistoryRecord.fournisseur_hint || "-"}</strong>
                  </article>
                  <article className="metric-card accent-amber">
                    <span>Source</span>
                    <strong>{sourceLabels[selectedHistoryRecord.source || "engine"] || "Moteur"}</strong>
                  </article>
                </div>

                {historySignals.length > 0 ? (
                  <div className="signal-summary-panel history-signal-summary">
                    <div className="signal-summary-toolbar">
                      <div className="panel-heading compact">
                        <p className="eyebrow">Entry Ranker</p>
                        <h3>Signaux conserves avec l'analyse</h3>
                      </div>
                      <label className="checkbox-row signal-toggle-row">
                        <input
                          type="checkbox"
                          checked={showInactiveSignals}
                          onChange={(event) => setShowInactiveSignals(event.target.checked)}
                        />
                        <span>Afficher aussi les signaux non actives</span>
                      </label>
                    </div>
                    <div className="signal-card-grid compact">
                      {historySignals.map((signal) => (
                        <article
                          className={`signal-card signal-card-${signal.family} ${
                            signal.inactive ? "signal-card-inactive" : ""
                          }`}
                          key={`${selectedHistoryRecord.lookup_key}-${signal.key}`}
                        >
                          <div className="signal-card-topline">
                            <span className="signal-family-label">
                              {signalFamilyLabels[signal.family] || signal.family}
                            </span>
                            <strong>{signal.label}</strong>
                          </div>
                          <div className="signal-card-metrics">
                            <span>Valeur {formatSignalValue(signal.value)}</span>
                            <span>Contribution {formatScore(signal.contribution)}</span>
                          </div>
                          <p className="signal-card-copy">{signal.explanation}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="history-detail-grid">
                  <article className="history-detail-card">
                    <span>Fournisseur</span>
                    <strong>{selectedHistoryRecord.fournisseur_hint || "-"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>APE client</span>
                    <strong>{selectedHistoryRecord.client_ape_hint || "-"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>APE fournisseur</span>
                    <strong>{selectedHistoryRecord.supplier_ape_hint || "-"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>TVA</span>
                    <strong>
                      {selectedHistoryRecord.tva_hint == null ? "-" : `${selectedHistoryRecord.tva_hint}%`}
                    </strong>
                  </article>
                  <article className="history-detail-card">
                    <span>Categorie</span>
                    <strong>{selectedHistoryRecord.categorie || "-"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>Sous-categorie</span>
                    <strong>{selectedHistoryRecord.sous_categorie || "-"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>Inclure charges</span>
                    <strong>{selectedHistoryRecord.include_charges ? "Oui" : "Non"}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>Horodatage</span>
                    <strong>{formatTimestamp(selectedHistoryRecord.created_at)}</strong>
                  </article>
                  <article className="history-detail-card">
                    <span>Cle de recherche</span>
                    <strong>{selectedHistoryRecord.lookup_key}</strong>
                  </article>
                </div>

                {selectedHistoryRecord.candidats?.length ? (
                  <div className="history-candidates-section">
                    <div className="panel-heading compact">
                      <p className="eyebrow">Top 3 conserve</p>
                      <h3>Candidats au moment de l'analyse</h3>
                    </div>

                    <div className="history-candidate-list">
                      {selectedHistoryRecord.candidats.map((candidate, index) => (
                        <article
                          className="history-candidate-card"
                          key={`${selectedHistoryRecord.lookup_key}-${candidate.compte_comptable}-${index}`}
                        >
                          <div className="history-candidate-header">
                            <span className="candidate-rank">#{index + 1}</span>
                            <strong>{candidate.compte_comptable}</strong>
                            <span>{formatScore(candidate.score_confiance)}</span>
                          </div>
                          <p className="candidate-title">{candidate.article_source_match}</p>
                          <p className="candidate-meta">
                            {candidate.categorie} / {candidate.sous_categorie} / {candidate.metier}
                          </p>
                          <p className="history-candidate-reason">{candidate.raison_match}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="candidate-empty-state">
                    {selectedHistoryRecord.source === "memory"
                      ? "Pas de top 3 a conserver pour cette ligne: elle provient de la memoire."
                      : "Aucun top 3 n'a ete conserve pour cette analyse plus ancienne."}
                  </div>
                )}

                <div className="history-detail-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => loadRecordIntoWorkspace(selectedHistoryRecord, "history")}
                  >
                    Charger dans l'analyse
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => void submitRecordFeedback(selectedHistoryRecord, "history", "valider")}
                    disabled={
                      listActionLoadingKey === selectedHistoryActionKey ||
                      !selectedHistoryRecord.compte_comptable
                    }
                  >
                    {listActionLoadingKey === selectedHistoryActionKey ? "Validation..." : "Valider"}
                  </button>
                  <button
                    className="candidate-link-button"
                    type="button"
                    onClick={() => openRecordInEdit(selectedHistoryRecord, "history")}
                  >
                    Corriger
                  </button>
                </div>

                {listActionStatus ? <p className="panel-info panel-info-inline">{listActionStatus}</p> : null}
              </div>
            ) : (
              <div className="candidate-empty-state">
                Choisis une ligne de l'historique pour ouvrir sa lecture detaillee.
              </div>
            )}
          </section>
        </section>
      ) : null}

      {activeTab === "memoire" ? (
        <section className="history-grid">
          <section className="panel dashboard-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Memoire IA</p>
              <h3>Base reutilisable du moteur</h3>
            </div>

            <div className="workspace-summary-grid history-overview-grid">
              {memoryCards.map((card) => (
                <article className={`workspace-summary-card ${card.tone}`} key={card.id}>
                  <span className="workspace-summary-label">{card.label}</span>
                  <strong>{card.value}</strong>
                  <p className="workspace-summary-helper">{card.helper}</p>
                </article>
              ))}
            </div>

            <div className="history-detail-grid memory-detail-grid">
              <article className="history-detail-card">
                <span>Fichier memoire</span>
                <strong>{memoryStats?.memory_file || "-"}</strong>
              </article>
              <article className="history-detail-card">
                <span>Analyses source memoire</span>
                <strong>{dashboardMemoryCount}</strong>
              </article>
              <article className="history-detail-card">
                <span>Auto OK recents</span>
                <strong>{dashboardAutoOkCount}</strong>
              </article>
              <article className="history-detail-card">
                <span>File humaine ouverte</span>
                <strong>{validationQueue.length}</strong>
              </article>
            </div>
          </section>

          <section className="panel history-detail-panel">
            <div className="panel-heading compact">
              <p className="eyebrow">Reutilisation recente</p>
              <h3>Lignes servies ou pretes pour la memoire</h3>
            </div>

            <div className="memory-columns">
              <div className="memory-column">
                <span className="memory-column-title">Analyses servies par la memoire</span>
                <div className="insight-list">
                  {memoryReplayItems.length > 0 ? (
                    memoryReplayItems.map((item, index) => (
                      <button
                        className="insight-card"
                        type="button"
                        key={`${item.lookup_key}-${item.created_at}-${index}`}
                        onClick={() => loadRecordIntoWorkspace(item, "history")}
                      >
                        <div className="insight-card-topline">
                          <strong>{item.article_source}</strong>
                          <span>{item.compte_comptable || "-"}</span>
                        </div>
                        <p className="insight-card-meta">
                          {formatTimestamp(item.created_at)} / {decisionLabels[item.decision]}
                        </p>
                        <p className="insight-card-description">{item.explication}</p>
                      </button>
                    ))
                  ) : (
                    <div className="candidate-empty-state">
                      Aucune analyse recente n'a encore ete servie depuis la memoire.
                    </div>
                  )}
                </div>
              </div>

              <div className="memory-column">
                <span className="memory-column-title">Lignes fortes a reutiliser</span>
                <div className="insight-list">
                  {latestValidationReadyItems.length > 0 ? (
                    latestValidationReadyItems.map((item, index) => (
                      <button
                        className="insight-card"
                        type="button"
                        key={`${item.lookup_key}-${item.created_at}-${index}-ready`}
                        onClick={() => loadRecordIntoWorkspace(item, "history")}
                      >
                        <div className="insight-card-topline">
                          <strong>{item.article_source}</strong>
                          <span>{item.compte_comptable || "-"}</span>
                        </div>
                        <p className="insight-card-meta">
                          {sourceLabels[item.source || "engine"] || "Moteur"} /{" "}
                          {formatScore(item.score_confiance)}
                        </p>
                        <p className="insight-card-description">{item.explication}</p>
                      </button>
                    ))
                  ) : (
                    <div className="candidate-empty-state">
                      Aucune ligne recente n'est encore marquee comme forte pour la memoire.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        </section>
      ) : null}

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
          {assistantContextFocus ? (
            <span className="assistant-context-focus">{assistantContextFocus}</span>
          ) : null}
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
