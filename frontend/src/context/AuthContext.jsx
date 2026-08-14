import { createContext, useContext, useEffect, useMemo, useState } from "react";

const AuthContext = createContext(null);

const AUTH_SESSION_KEY = "keymanage_auth_session";
const AUTH_USER_KEY = "keymanage_auth_user";
const TEST_EMAIL = "expert@keymanage.ai";
const TEST_PASSWORD = "KeyManage2026";
const DEFAULT_USER = {
  name: "Expert Comptable",
  email: TEST_EMAIL,
  role: "Expert-comptable",
};

function readStoredSession() {
  if (typeof window === "undefined") return { isAuthenticated: false, user: null };
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      if (storage.getItem(AUTH_SESSION_KEY) !== "true") continue;
      const storedUser = JSON.parse(storage.getItem(AUTH_USER_KEY) || "null");
      return {
        isAuthenticated: true,
        user: storedUser && typeof storedUser === "object" ? storedUser : DEFAULT_USER,
      };
    } catch {
      // Ignore an invalid or unavailable storage and try the next one.
    }
  }
  return { isAuthenticated: false, user: null };
}

function removeAuthSession(storage) {
  storage.removeItem(AUTH_SESSION_KEY);
  storage.removeItem(AUTH_USER_KEY);
}

export function AuthProvider({ children }) {
  const initialSession = readStoredSession();
  const [isAuthenticated, setIsAuthenticated] = useState(initialSession.isAuthenticated);
  const [user, setUser] = useState(initialSession.user);

  useEffect(() => {
    const restoredSession = readStoredSession();
    setIsAuthenticated(restoredSession.isAuthenticated);
    setUser(restoredSession.user);
  }, []);

  const login = (email, password, rememberMe = false) => {
    const normalizedEmail = String(email || "").trim().toLowerCase();
    if (normalizedEmail !== TEST_EMAIL || String(password || "") !== TEST_PASSWORD) {
      return { success: false, message: "Identifiants invalides." };
    }

    const targetStorage = rememberMe ? window.localStorage : window.sessionStorage;
    const otherStorage = rememberMe ? window.sessionStorage : window.localStorage;
    removeAuthSession(otherStorage);
    targetStorage.setItem(AUTH_SESSION_KEY, "true");
    targetStorage.setItem(AUTH_USER_KEY, JSON.stringify(DEFAULT_USER));
    setIsAuthenticated(true);
    setUser(DEFAULT_USER);
    return { success: true };
  };

  const logout = () => {
    removeAuthSession(window.localStorage);
    removeAuthSession(window.sessionStorage);
    setIsAuthenticated(false);
    setUser(null);
  };

  const value = useMemo(
    () => ({ isAuthenticated, user, login, logout }),
    [isAuthenticated, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
