export function readPersistentHiddenIds(storageKey) {
  if (typeof window === "undefined") return [];

  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) || "[]");
    return Array.isArray(parsed)
      ? parsed.map((value) => String(value || "").trim()).filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

export function addPersistentHiddenId(storageKey, itemId) {
  const normalizedId = String(itemId || "").trim();
  if (!normalizedId || typeof window === "undefined") return;

  const nextIds = new Set(readPersistentHiddenIds(storageKey));
  nextIds.add(normalizedId);
  window.localStorage.setItem(storageKey, JSON.stringify([...nextIds]));
}
