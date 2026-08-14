export function normalizeSearch(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function matchesGlobalSearch(value, query) {
  const needle = normalizeSearch(query);
  if (!needle) return true;

  let haystack = "";
  try {
    haystack = JSON.stringify(value);
  } catch {
    haystack = String(value ?? "");
  }

  return normalizeSearch(haystack).includes(needle);
}
