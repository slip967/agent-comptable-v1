import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import AppLayout from "./components/layout/AppLayout";
import { AnalysisBatchProvider } from "./context/AnalysisBatchContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SearchProvider } from "./context/SearchContext";

import DashboardPage from "./pages/DashboardPage";
import AnalysisPage from "./pages/AnalysisPage";
import ValidationPage from "./pages/ValidationPage";
import HistoryPage from "./pages/HistoryPage";
import MemoryPage from "./pages/MemoryPage";
import BasesMetiersPage from "./pages/BasesMetiersPage";
import ValidatedEntriesPage from "./pages/ValidatedEntriesPage";
import LoginPage from "./pages/LoginPage";

function ScrollToHash() {
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }

    const targetId = location.hash.replace("#", "");

    const scrollToTarget = () => {
      const target = document.getElementById(targetId);

      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };

    window.requestAnimationFrame(scrollToTarget);
  }, [location.pathname, location.hash]);

  return null;
}

function AuthenticatedApplication() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) return <LoginPage />;

  return (
    <AnalysisBatchProvider>
      <SearchProvider>
        <ScrollToHash />

        <AppLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/analysis" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/validation" element={<ValidationPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/ecritures-validees" element={<ValidatedEntriesPage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/bases-metiers" element={<BasesMetiersPage />} />
          </Routes>
        </AppLayout>
      </SearchProvider>
    </AnalysisBatchProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AuthenticatedApplication />
      </BrowserRouter>
    </AuthProvider>
  );
}


