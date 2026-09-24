import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  LogOut,
  Moon,
  Search,
  Sun,
  X,
  UserRound,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useGlobalSearch } from "../../context/SearchContext";
import { useAuth } from "../../context/AuthContext";
import { useAnalysisBatch } from "../../context/AnalysisBatchContext";
import {
  getValidatedInvoiceKey,
  readRolledBackInvoices,
  readValidatedEntries,
} from "../../utils/validatedEntries";
import { normalizeSearch } from "../../utils/search";
import {
  fetchAnalysisBatchResults,
  fetchHumanValidationItems,
  fetchValidatedEntries,
} from "../../services/api";

const ANALYSIS_SEARCH_SELECTION_KEY = "keymanage.analysis.search-selection.v1";

function invoiceIdOf(invoice = {}) {
  return String(
    invoice.invoice_id || invoice.id || invoice._id || invoice.doc_id ||
      invoice.invoice_group_id || getValidatedInvoiceKey(invoice) || "",
  ).trim();
}

function invoiceApeOf(invoice = {}) {
  return String(
    invoice.client_ape || invoice.supplier_ape || invoice.code_ape ||
      invoice.ape_code || invoice.ape || "",
  ).trim();
}

function invoiceStatusOf(invoice = {}) {
  const status = String(
    invoice.workflow_status || invoice.accounting_status || invoice.queue_status ||
      invoice.status || "Non analysée",
  ).trim();
  return status.replaceAll("_", " ");
}

function invoiceAmountOf(invoice = {}) {
  const raw = invoice.total_ttc ?? invoice.amount_ttc ?? invoice.ttc ?? invoice.total;
  const amount = Number(raw);
  return Number.isFinite(amount)
    ? new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(amount)
    : "";
}

function invoiceLocationOf(invoice = {}) {
  if (invoice.searchLocation === "validated" || invoice.searchDestination === "/ecritures-validees") {
    return { key: "validated", label: "🟢 Comptabilisée" };
  }
  if (invoice.searchLocation === "validation" || invoice.searchDestination === "/validation") {
    return { key: "validation", label: "⏳ Validation humaine" };
  }
  return { key: "analysis", label: "⚡ Analyse IA" };
}

function dedupeInvoices(items = []) {
  const invoices = new Map();
  items.forEach((invoice) => {
    const id = invoiceIdOf(invoice);
    if (!id) return;
    invoices.set(id, { ...invoices.get(id), ...invoice });
  });
  return [...invoices.values()];
}

export default function Topbar() {
  const { searchQuery, setSearchQuery, clearSearch } = useGlobalSearch();
  const { user, logout } = useAuth();
  const { queueItems } = useAnalysisBatch();
  const navigate = useNavigate();
  const searchRef = useRef(null);
  const profileRef = useRef(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [storedInvoices, setStoredInvoices] = useState(() => [
    ...readValidatedEntries().map((invoice) => ({ ...invoice, searchDestination: "/ecritures-validees", searchLocation: "validated" })),
    ...readRolledBackInvoices().map((invoice) => ({ ...invoice, searchDestination: "/validation", searchLocation: "validation" })),
  ]);
  const [remoteInvoices, setRemoteInvoices] = useState([]);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") {
      return "dark";
    }

    return window.localStorage.getItem("km-theme") || "dark";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("km-theme", theme);
  }, [theme]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setIsSearchOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setIsProfileOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setIsSearchOpen(false);
        setIsProfileOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => {
    const refreshStoredInvoices = () => {
      setStoredInvoices([
        ...readValidatedEntries().map((invoice) => ({ ...invoice, searchDestination: "/ecritures-validees", searchLocation: "validated" })),
        ...readRolledBackInvoices().map((invoice) => ({ ...invoice, searchDestination: "/validation", searchLocation: "validation" })),
      ]);
    };
    window.addEventListener("keymanage:validated-accounting-entry", refreshStoredInvoices);
    window.addEventListener("keymanage:invoice-rollback-to-human-validation", refreshStoredInvoices);
    window.addEventListener("storage", refreshStoredInvoices);
    return () => {
      window.removeEventListener("keymanage:validated-accounting-entry", refreshStoredInvoices);
      window.removeEventListener("keymanage:invoice-rollback-to-human-validation", refreshStoredInvoices);
      window.removeEventListener("storage", refreshStoredInvoices);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadAllSearchSources = async () => {
      const results = await Promise.allSettled([
        fetchAnalysisBatchResults({ limit: 500 }),
        fetchHumanValidationItems({ limit: 1000 }),
        fetchValidatedEntries(2000),
      ]);
      if (cancelled) return;
      const analysisItems = results[0].status === "fulfilled" && Array.isArray(results[0].value?.items)
        ? results[0].value.items
        : [];
      const validationItems = results[1].status === "fulfilled" && Array.isArray(results[1].value?.items)
        ? results[1].value.items
        : [];
      const validatedItems = results[2].status === "fulfilled" && Array.isArray(results[2].value?.items)
        ? results[2].value.items
        : [];
      setRemoteInvoices([
        ...analysisItems.map((invoice) => ({ ...invoice, searchDestination: "/analysis", searchLocation: "analysis" })),
        ...validationItems.map((invoice) => ({ ...invoice, searchDestination: "/validation", searchLocation: "validation" })),
        ...validatedItems.map((invoice) => ({ ...invoice, searchDestination: "/ecritures-validees", searchLocation: "validated" })),
      ]);
    };
    const refresh = () => void loadAllSearchSources();
    void loadAllSearchSources();
    const refreshInterval = window.setInterval(refresh, 15000);
    window.addEventListener("keymanage:validated-accounting-entry", refresh);
    window.addEventListener("keymanage:human-validation-updated", refresh);
    window.addEventListener("keymanage:analysis-history-updated", refresh);
    return () => {
      cancelled = true;
      window.clearInterval(refreshInterval);
      window.removeEventListener("keymanage:validated-accounting-entry", refresh);
      window.removeEventListener("keymanage:human-validation-updated", refresh);
      window.removeEventListener("keymanage:analysis-history-updated", refresh);
    };
  }, []);

  const searchableInvoices = dedupeInvoices([
    ...queueItems.map((invoice) => ({ ...invoice, searchDestination: "/analysis", searchLocation: "analysis" })),
    ...remoteInvoices,
    ...storedInvoices,
  ]);
  const needle = normalizeSearch(searchQuery);
  const searchResults = needle
    ? searchableInvoices.filter((invoice) => [
        invoice.supplier,
        invoice.supplier_name,
        invoice.client,
        invoice.customer,
        invoice.dossier,
        invoiceApeOf(invoice),
        invoice.invoice_number,
        invoice.ref,
        invoice.total_ht,
        invoice.amount_ht,
        invoice.ht,
        invoice.total_ttc,
        invoice.amount_ttc,
        invoice.ttc,
        invoiceIdOf(invoice),
      ].some((field) => normalizeSearch(field).includes(needle))).slice(0, 12)
    : [];

  const handleSearchSelection = (invoice) => {
    const invoiceId = invoiceIdOf(invoice);
    const destination = invoice.searchDestination || "/analysis";
    setIsSearchOpen(false);
    setSearchQuery(String(invoice.supplier || invoice.supplier_name || invoice.invoice_number || searchQuery));
    if (destination === "/analysis" && invoiceId) {
      const selectedInvoice = {
        ...invoice,
        invoice_id: invoiceId,
        line_count: invoice.line_count || invoice.total_lines || invoice.line_items_count || 0,
      };
      delete selectedInvoice.analysis_payload;
      window.sessionStorage.setItem(
        ANALYSIS_SEARCH_SELECTION_KEY,
        JSON.stringify({ invoiceId, invoice: selectedInvoice }),
      );
    }
    navigate(destination);
    window.requestAnimationFrame(() => {
      window.dispatchEvent(new CustomEvent("keymanage:analysis-search-select", {
        detail: { invoiceId, invoice },
      }));
    });
  };

  const handleClearSearch = () => {
    clearSearch();
    setIsSearchOpen(false);
  };

  const handleProfile = () => {
    setIsProfileOpen(false);
    window.alert("Profil utilisateur : Expert-comptable");
  };

  const handleLogout = () => {
    setIsProfileOpen(false);
    logout();
  };

  const isDark = theme === "dark";

  return (
    <header className="topbar">
      <div className="topbar-search-shell" ref={searchRef}>
      <div className="topbar-search">
        <Search size={18} />
        <input
          type="text"
          placeholder="Rechercher une analyse..."
          value={searchQuery}
          onChange={(event) => {
            setSearchQuery(event.target.value);
            setIsSearchOpen(Boolean(event.target.value.trim()));
          }}
          onFocus={() => setIsSearchOpen(Boolean(searchQuery.trim()))}
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={isSearchOpen}
        />
        {searchQuery ? (
          <button
            type="button"
            className="topbar-search-clear"
            aria-label="Réinitialiser la recherche"
            onClick={handleClearSearch}
          >
            <X size={16} />
          </button>
        ) : null}
      </div>

      {isSearchOpen && searchQuery.trim() ? (
        <div className="topbar-search-dropdown absolute z-50 w-full bg-white rounded-xl shadow-2xl border border-gray-100 max-h-80 overflow-y-auto" role="listbox">
          {searchResults.length ? searchResults.map((invoice) => {
            const supplier = String(invoice.supplier || invoice.supplier_name || "Fournisseur inconnu").trim();
            const client = String(invoice.client || invoice.customer || invoice.dossier || "Non renseigné").trim();
            const ape = invoiceApeOf(invoice) || "Non renseigné";
            const amount = invoiceAmountOf(invoice);
            const location = invoiceLocationOf(invoice);
            return (
              <button
                type="button"
                role="option"
                className="topbar-search-result"
                key={`${invoice.searchDestination || "/analysis"}-${invoiceIdOf(invoice)}`}
                onClick={() => handleSearchSelection(invoice)}
              >
                <span className="topbar-search-result-copy">
                  <strong>{supplier}</strong>
                  <small>Client : {client} <span aria-hidden="true">|</span> Code APE : {ape}</small>
                </span>
                <span className="topbar-search-result-side">
                  <span className={`topbar-search-location topbar-search-location--${location.key}`}>
                    {location.label}
                  </span>
                  <b title={invoiceStatusOf(invoice)}>{invoiceStatusOf(invoice)}</b>
                  {amount ? <small>{amount}</small> : null}
                </span>
              </button>
            );
          }) : (
            <div className="topbar-search-empty">
              Aucune analyse ou facture trouvée pour « {searchQuery.trim()} »
            </div>
          )}
        </div>
      ) : null}
      </div>

      <div className="topbar-actions">
        <button
          type="button"
          className="theme-toggle-btn"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          title={isDark ? "Thème clair" : "Thème sombre"}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <div className="profile-menu-shell" ref={profileRef}>
          <button
            type="button"
            className="profile-trigger"
            aria-expanded={isProfileOpen}
            aria-haspopup="menu"
            onClick={() => setIsProfileOpen((open) => !open)}
          >
            <span className="profile-avatar" aria-hidden="true">EC</span>
            <span className="profile-trigger-copy">
              <strong>{user?.name || "Expert-comptable"}</strong>
              <small>{user?.role || "Expert-comptable"}</small>
            </span>
            <ChevronDown
              className={`profile-chevron ${isProfileOpen ? "open" : ""}`}
              size={17}
              aria-hidden="true"
            />
          </button>

          {isProfileOpen && (
            <div className="profile-dropdown" role="menu">
              <div className="profile-dropdown-head">
                <span className="profile-avatar profile-avatar-large" aria-hidden="true">EC</span>
                <div>
                  <strong>{user?.name || "Expert-comptable"}</strong>
                  <span>{user?.role || "Expert-comptable"}</span>
                  <a href={`mailto:${user?.email || "expert@keymanage.ai"}`}>{user?.email || "expert@keymanage.ai"}</a>
                </div>
              </div>

              <div className="profile-dropdown-divider" />

              <button type="button" role="menuitem" onClick={handleProfile}>
                <UserRound size={17} aria-hidden="true" />
                Profil
              </button>
              <button
                type="button"
                role="menuitem"
                className="profile-logout"
                onClick={handleLogout}
              >
                <LogOut size={17} aria-hidden="true" />
                Déconnexion
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
