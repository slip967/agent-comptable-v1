const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data ? data.detail : "Erreur API inattendue.";
    throw new Error(typeof detail === "string" ? detail : "Erreur API inattendue.");
  }

  return data;
}

export function getHealth() {
  return requestJson("/health", { method: "GET" });
}

export function getAnalysisHistory(limit = 12) {
  return requestJson(`/analysis/history?limit=${limit}`, { method: "GET" });
}

export function getValidationQueue(limit = 12) {
  return requestJson(`/validation-queue?limit=${limit}`, { method: "GET" });
}

export function recommendLine(payload) {
  return requestJson("/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sendFeedback(payload) {
  return requestJson("/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function askAssistant(payload) {
  return requestJson("/assistant", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
