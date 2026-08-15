export function isMissingValidationLineError(error) {
  const status = Number(error?.status ?? error?.response?.status ?? 0);
  if (status === 400 || status === 404) return true;

  const message = String(
    error?.message ?? error?.detail ?? error?.response?.data?.detail ?? "",
  )
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

  return (
    message.includes("ligne de validation introuvable") ||
    message.includes("validation line not found") ||
    message.includes("validation introuvable")
  );
}

export function isSuccessfulOrMissingDeletion(result) {
  return result?.status === "fulfilled" || (
    result?.status === "rejected" && isMissingValidationLineError(result.reason)
  );
}
