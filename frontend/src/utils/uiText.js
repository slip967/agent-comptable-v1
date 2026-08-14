function normalizeKey(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function capitalize(text) {
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function readNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function extractCount(text, pattern) {
  const match = String(text || "").match(pattern);
  return match ? Number(match[1]) : null;
}

export function formatHumanReadableText(value, fallback = "") {
  const raw = String(value ?? "").trim();
  if (!raw) return fallback;

  return raw
    .replace(/\bFacture analysee\b/gi, "Facture analysée")
    .replace(/\bfacture_analysee\b/gi, "Facture analysée")
    .replace(/\binvoice_analyzed\b/gi, "Facture analysée")
    .replace(/\bLigne envoyee validation\b/gi, "Ligne envoyée en validation")
    .replace(/\bsent_to_human_validation\b/gi, "Ligne envoyée en validation")
    .replace(/\bline_sent_validation\b/gi, "Ligne envoyée en validation")
    .replace(/\bCorrection humaine\b/gi, "Correction humaine appliquée")
    .replace(/\bhuman_correction\b/gi, "Correction humaine appliquée")
    .replace(/\bhuman_corrected\b/gi, "Correction humaine appliquée")
    .replace(/\bline_corrected\b/gi, "Correction humaine appliquée")
    .replace(/\bLigne validee\b/gi, "Ligne validée")
    .replace(/\bline_validated\b/gi, "Ligne validée")
    .replace(/\bhuman_validated\b/gi, "Ligne validée")
    .replace(/\bNon comptable\b/gi, "Ligne marquée non comptable")
    .replace(/\bline_marked_non_accounting\b/gi, "Ligne marquée non comptable")
    .replace(/\bmarked_non_comptable\b/gi, "Ligne marquée non comptable")
    .replace(/\bErreur analyse\b/gi, "Erreur d’analyse")
    .replace(/\banalysis_error\b/gi, "Erreur d’analyse")
    .replace(/\bCandidat memoire\b/gi, "Candidat mémoire créé")
    .replace(/\bmemory_candidate_created\b/gi, "Candidat mémoire créé")
    .replace(/\bAnalyse echouee\b/gi, "Analyse échouée")
    .replace(/\bA controler\b/gi, "À contrôler")
    .replace(/\ba controler\b/gi, "à contrôler")
    .replace(/\bA analyser\b/gi, "À analyser")
    .replace(/\ba analyser\b/gi, "à analyser")
    .replace(/\bNon renseigne\b/gi, "Non renseigné")
    .replace(/\bNon detecte\b/gi, "Non détecté")
    .replace(/\bMemoire\b/gi, "Mémoire")
    .replace(/\bReferentiel\b/gi, "Référentiel")
    .replace(/\brejetees\b/gi, "rejetées")
    .replace(/\brejetee\b/gi, "rejetée")
    .replace(/\bvalidee\b/gi, "validée")
    .replace(/\bcorrigee\b/gi, "corrigée")
    .replace(/\banalysee\b/gi, "analysée")
    .replace(/\ba valider\b/gi, "à valider");
}

export function formatMetierText(value, fallback = "Non détecté") {
  const text = String(value ?? "").replaceAll("_", " ").trim();
  if (!text) return fallback;
  return capitalize(text);
}

export function formatReferentialStatus(value) {
  switch (normalizeKey(value)) {
    case "found exact":
      return "Exact";
    case "found fuzzy":
    case "found close":
      return "Proche";
    case "missing":
    case "missing candidate":
      return "Absent";
    case "unknown":
      return "Inconnu";
    case "non comptable":
      return "Non comptable";
    default:
      return "Inconnu";
  }
}

export function formatEvidenceStatus(value) {
  switch (normalizeKey(value)) {
    case "complete":
      return "Complètes";
    case "partial":
      return "Partielles";
    case "missing":
      return "Sans preuve";
    default:
      return "Sans preuve";
  }
}

export function formatDecisionStatus(value) {
  switch (normalizeKey(value)) {
    case "auto ok":
      return "Auto-validée";
    case "validation humaine":
    case "validation required":
      return "À valider";
    case "rejected":
    case "rejetee":
    case "rejeter":
      return "Rejetée";
    case "non comptable":
      return "Non comptable";
    case "partial":
      return "Partielle";
    default:
      return "À vérifier";
  }
}

export function formatRiskStatus(value) {
  switch (normalizeKey(value)) {
    case "faible":
      return "Faible";
    case "moyen":
      return "Moyen";
    case "eleve":
      return "Élevé";
    default:
      return "Moyen";
  }
}

export function formatQualityStatus(value) {
  return normalizeKey(value) === "fiable" ? "Fiable" : "À contrôler";
}

export function formatQueueStatus(value) {
  switch (normalizeKey(value)) {
    case "to control":
    case "a controler":
      return "À contrôler";
    case "new articles":
      return "Nouveaux articles";
    case "low risk":
      return "Faible risque";
    case "not analyzed":
    case "non analysee":
      return "Non analysée";
    case "analyse":
    case "analysee":
      return "Analysée";
    case "accounted":
    case "comptabilisee":
      return "Comptabilisée";
    case "en attente":
      return "En attente";
    case "no lines":
      return "Sans lignes";
    case "analysis failed":
    case "erreur":
      return "Erreur";
    default:
      return "Non analysée";
  }
}

export function formatHumanValidationStatus(value) {
  switch (normalizeKey(value)) {
    case "pending validation":
      return "À valider";
    case "validated":
      return "Validée";
    case "corrected":
      return "Corrigée";
    case "rejected":
      return "Rejetée";
    case "non comptable":
      return "Non comptable";
    case "enrichment proposed":
      return "Enrichissement";
    default:
      return "À valider";
  }
}

export function formatEventTitle(eventType) {
  switch (normalizeKey(eventType)) {
    case "invoice analyzed":
    case "facture analysee":
      return "Facture analysée";
    case "sent to human validation":
    case "ligne envoyee validation":
    case "line sent validation":
      return "Ligne envoyée en validation";
    case "human validated":
    case "line validated":
      return "Ligne validée";
    case "human corrected":
    case "correction humaine":
    case "human correction":
    case "line corrected":
      return "Correction humaine appliquée";
    case "marked non comptable":
    case "line marked non accounting":
      return "Ligne marquée non comptable";
    case "rejected":
    case "erreur analyse":
    case "analysis error":
      return "Erreur d’analyse";
    case "enrichment proposed":
    case "candidat memoire":
    case "memory candidate created":
      return "Candidat mémoire créé";
    default:
      return "Événement IA";
  }
}

export function formatWorkflowSource(value) {
  switch (normalizeKey(value)) {
    case "analyse ia":
      return "Analyse IA";
    case "validation humaine":
      return "Validation humaine";
    case "memoire ia":
      return "Mémoire IA";
    default:
      return "Workflow IA";
  }
}

export function formatReferentialPanelTitle(value) {
  switch (normalizeKey(value)) {
    case "found exact":
      return "Référentiel trouvé";
    case "found fuzzy":
    case "found close":
      return "Référentiel proche";
    case "missing candidate":
    case "missing":
      return "Hypothèse référentielle";
    case "unknown":
      return "Aucun référentiel fiable";
    case "non comptable":
      return "Ligne non comptable";
    default:
      return "Référentiel";
  }
}

export function cleanSummaryText(value, event = {}) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";

  const source = formatHumanReadableText(raw, "")
    .replace(/^Facture analysée\s*:\s*/i, "")
    .replace(/^Analyse facture\s*:\s*/i, "")
    .replace(/^Facture analysee\s*:\s*/i, "");

  const totalLines =
    readNumber(event?.total_lines) ??
    readNumber(event?.line_count) ??
    extractCount(source, /(\d+)\s*ligne/i);
  const autoValidated =
    readNumber(event?.auto_ok) ??
    readNumber(event?.auto_validated) ??
    extractCount(source, /(\d+)\s*(?:auto[\s-]*ok|auto[\s-]*valid)/i);
  const toValidate =
    readNumber(event?.validation_humaine) ??
    readNumber(event?.to_validate) ??
    readNumber(event?.pending_validation) ??
    extractCount(source, /(\d+)\s*à\s*valider/i);
  const nonComptable =
    readNumber(event?.non_comptable) ??
    readNumber(event?.non_accounting) ??
    extractCount(source, /(\d+)\s*non\s*comptable/i);
  const rejected =
    readNumber(event?.rejected) ??
    readNumber(event?.rejeter) ??
    extractCount(source, /(\d+)\s*rejet/i);

  if (
    totalLines !== null ||
    autoValidated !== null ||
    toValidate !== null ||
    nonComptable !== null ||
    rejected !== null
  ) {
    const parts = [];

    if (totalLines !== null) {
      parts.push(`${totalLines} ${totalLines > 1 ? "lignes traitées" : "ligne traitée"}`);
    }

    const showAutoMetric =
      autoValidated !== null &&
      (autoValidated > 0 ||
        totalLines !== null ||
        (toValidate !== null && toValidate > 0) ||
        (nonComptable !== null && nonComptable > 0) ||
        (rejected !== null && rejected > 0));

    if (showAutoMetric) {
      parts.push(`${autoValidated} auto-validée${autoValidated > 1 ? "s" : ""}`);
    }

    if (toValidate !== null && toValidate > 0) {
      parts.push(`${toValidate} à valider`);
    }

    if (nonComptable !== null && nonComptable > 0) {
      parts.push(`${nonComptable} non comptable${nonComptable > 1 ? "s" : ""}`);
    }

    if (rejected !== null && rejected > 0) {
      parts.push(`${rejected} rejetée${rejected > 1 ? "s" : ""}`);
    }

    if (parts.length) {
      return parts.join(" · ");
    }
  }

  return source;
}
