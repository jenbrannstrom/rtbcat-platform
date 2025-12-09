"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

const SELECTED_BUYER_KEY = "rtbcat-selected-buyer-id";

interface AccountContextValue {
  selectedBuyerId: string | null;
  setSelectedBuyerId: (buyerId: string | null) => void;
}

const AccountContext = createContext<AccountContextValue | undefined>(undefined);

export function AccountProvider({ children }: { children: ReactNode }) {
  const [selectedBuyerId, setSelectedBuyerIdState] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(SELECTED_BUYER_KEY);
    if (stored) {
      setSelectedBuyerIdState(stored);
    }
    setInitialized(true);
  }, []);

  // Persist to localStorage when changed
  const setSelectedBuyerId = useCallback((buyerId: string | null) => {
    setSelectedBuyerIdState(buyerId);
    if (buyerId) {
      localStorage.setItem(SELECTED_BUYER_KEY, buyerId);
    } else {
      localStorage.removeItem(SELECTED_BUYER_KEY);
    }
  }, []);

  // Don't render children until initialized to prevent hydration mismatch
  if (!initialized) {
    return null;
  }

  return (
    <AccountContext.Provider value={{ selectedBuyerId, setSelectedBuyerId }}>
      {children}
    </AccountContext.Provider>
  );
}

export function useAccount() {
  const context = useContext(AccountContext);
  if (context === undefined) {
    throw new Error("useAccount must be used within an AccountProvider");
  }
  return context;
}
