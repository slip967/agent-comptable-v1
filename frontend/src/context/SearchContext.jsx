import { createContext, useContext, useMemo, useState } from "react";

const SearchContext = createContext(null);

export function SearchProvider({ children }) {
  const [searchQuery, setSearchQuery] = useState("");

  const value = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      clearSearch: () => setSearchQuery(""),
    }),
    [searchQuery],
  );

  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useGlobalSearch() {
  const context = useContext(SearchContext);
  if (!context) {
    throw new Error("useGlobalSearch must be used inside SearchProvider");
  }
  return context;
}
