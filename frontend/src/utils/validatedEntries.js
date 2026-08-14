export const VALIDATED_ENTRIES_STORAGE_KEY = "keymanage.validated-accounting-entries.v1";
export const VALIDATED_INVOICE_IDS_STORAGE_KEY = "keymanage.validated-invoice-ids.v1";
export const ROLLED_BACK_INVOICES_STORAGE_KEY = "keymanage.rolled-back-invoices.v1";

export function getValidatedInvoiceKey(invoice = {}) {
  return String(
    invoice.invoice_id || invoice.invoiceId || invoice.source_invoice_id || invoice.id || invoice._id || invoice.doc_id || invoice.invoice_number || "",
  ).trim();
}


export function readValidatedEntries() {
  return Object.values(readObjectStorage(VALIDATED_ENTRIES_STORAGE_KEY)).filter(Boolean);
}
export function readValidatedInvoiceIds() {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(VALIDATED_INVOICE_IDS_STORAGE_KEY);
    const values = raw ? JSON.parse(raw) : [];
    const ids = Array.isArray(values) ? values : [];

    // Recover ids from entries saved before the dedicated index existed.
    const entriesRaw = window.localStorage.getItem(VALIDATED_ENTRIES_STORAGE_KEY);
    const entries = entriesRaw ? JSON.parse(entriesRaw) : {};
    Object.values(entries || {}).forEach((entry) => {
      const key = getValidatedInvoiceKey(entry);
      if (key) ids.push(key);
    });

    return new Set(ids.map((value) => String(value).trim()).filter(Boolean));
  } catch {
    return new Set();
  }
}

export function markInvoiceAsValidated(invoice = {}) {
  if (typeof window === "undefined") return;
  const invoiceKey = getValidatedInvoiceKey(invoice);
  if (!invoiceKey) return;
  const ids = readValidatedInvoiceIds();
  ids.add(invoiceKey);
  window.localStorage.setItem(VALIDATED_INVOICE_IDS_STORAGE_KEY, JSON.stringify(Array.from(ids)));
}
function readObjectStorage(key) {
  if (typeof window === "undefined") return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function removeValidatedInvoiceId(invoiceOrKey) {
  if (typeof window === "undefined") return;
  const key = typeof invoiceOrKey === "string" ? invoiceOrKey : getValidatedInvoiceKey(invoiceOrKey);
  if (!key) return;
  const ids = readValidatedInvoiceIds();
  ids.delete(key);
  window.localStorage.setItem(VALIDATED_INVOICE_IDS_STORAGE_KEY, JSON.stringify(Array.from(ids)));
}

export function readRolledBackInvoices() {
  return Object.values(readObjectStorage(ROLLED_BACK_INVOICES_STORAGE_KEY)).filter(Boolean);
}

export function removeRolledBackInvoice(invoice = {}) {
  if (typeof window === "undefined") return;
  const key = getValidatedInvoiceKey(invoice);
  if (!key) return;
  const store = readObjectStorage(ROLLED_BACK_INVOICES_STORAGE_KEY);
  delete store[key];
  window.localStorage.setItem(ROLLED_BACK_INVOICES_STORAGE_KEY, JSON.stringify(store));
}

export function saveRolledBackInvoice(invoice = {}) {
  if (typeof window === "undefined") return;
  const key = getValidatedInvoiceKey(invoice);
  if (!key) return;
  const store = readObjectStorage(ROLLED_BACK_INVOICES_STORAGE_KEY);
  store[key] = {
    ...invoice,
    invoice_id: key,
    status: "A_VALIDER",
    workflow_status: "A_VALIDER",
    accounting_status: "A_VALIDER",
    destination: "validation_humaine",
    rolled_back_at: new Date().toISOString(),
  };
  window.localStorage.setItem(ROLLED_BACK_INVOICES_STORAGE_KEY, JSON.stringify(store));
  removeValidatedInvoiceId(key);
  window.dispatchEvent(new Event("keymanage:invoice-rollback-to-human-validation"));
}
export function removeValidatedInvoice(invoice = {}) {
  if (typeof window === "undefined") return;
  const invoiceKey = getValidatedInvoiceKey(invoice);
  if (!invoiceKey) return;
  const store = readObjectStorage(VALIDATED_ENTRIES_STORAGE_KEY);
  const nextStore = Object.fromEntries(
    Object.entries(store).filter(([key, entry]) => {
      const entryKey = getValidatedInvoiceKey(entry);
      return key !== invoiceKey && entryKey !== invoiceKey && entry?.invoice_group_id !== invoiceKey;
    }),
  );
  window.localStorage.setItem(VALIDATED_ENTRIES_STORAGE_KEY, JSON.stringify(nextStore));
  removeValidatedInvoiceId(invoiceKey);
  window.dispatchEvent(new Event("keymanage:validated-accounting-entry"));
}
function getEntryKey(entry, invoiceKey, index) {
  return String(
    entry.validated_entry_id ||
      entry.validation_id ||
      entry.line_id ||
      entry.id ||
      entry._id ||
      invoiceKey + "-" + index,
  );
}

export function persistValidatedInvoice(invoice = {}, lines = [], validationResult = {}) {
  if (typeof window === "undefined") return;

  let store = {};
  try {
    const raw = window.localStorage.getItem(VALIDATED_ENTRIES_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    store = parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    store = {};
  }

  const invoiceKey = getValidatedInvoiceKey(invoice);
  if (!invoiceKey) return;
  removeRolledBackInvoice(invoice);
  markInvoiceAsValidated(invoice);
  const invoiceLines = Array.isArray(lines) && lines.length ? lines : [invoice];
  const validatedAt = new Date().toISOString();

  invoiceLines.forEach((line, index) => {
    const entry = {
      ...invoice,
      ...line,
      invoice_id: line.invoice_id || invoice.invoice_id || invoice.id || invoice._id || invoice.doc_id,
      invoice_number: line.invoice_number || invoice.invoice_number,
      supplier: line.supplier || invoice.supplier,
      client: line.client || invoice.client,
      invoice_group_id: invoice.invoice_group_id || invoiceKey,
      status: "COMPTABILISEE",
      workflow_status: "COMPTABILISEE",
      accounting_status: "COMPTABILISEE",
      destination: "ecritures_validees",
      validated_entries_destination: "ecritures_validees",
      validated_at: validatedAt,
      human_validation_result:
        validationResult.human_validation_result || {
          action: "validate",
          validated_by: "human_user",
          validated_at: validatedAt,
        },
    };

    const key = getEntryKey(entry, invoiceKey, index);
    store[key] = { ...entry, validated_entry_id: key };
  });

  window.localStorage.setItem(VALIDATED_ENTRIES_STORAGE_KEY, JSON.stringify(store));
  window.dispatchEvent(new Event("keymanage:validated-accounting-entry"));
}


