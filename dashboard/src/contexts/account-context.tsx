"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

const SELECTED_BUYER_KEY = "rtbcat-selected-buyer-id";
const SELECTED_SERVICE_ACCOUNT_KEY = "rtbcat-selected-service-account-id";

interface AccountContextValue {
  selectedBuyerId: string | null;
  setSelectedBuyerId: (buyerId: string | null) => void;
  selectedServiceAccountId: string | null;
  setSelectedServiceAccountId: (accountId: string | null) => void;
}

const AccountContext = createContext<AccountContextValue | undefined>(undefined);

export function AccountProvider({ children }: { children: ReactNode }) {
  const [selectedBuyerId, setSelectedBuyerIdState] = useState<string | null>(null);
  const [selectedServiceAccountId, setSelectedServiceAccountIdState] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const storedBuyer = localStorage.getItem(SELECTED_BUYER_KEY);
    if (storedBuyer) {
      setSelectedBuyerIdState(storedBuyer);
    }
    const storedServiceAccount = localStorage.getItem(SELECTED_SERVICE_ACCOUNT_KEY);
    if (storedServiceAccount) {
      setSelectedServiceAccountIdState(storedServiceAccount);
    }
    setInitialized(true);
  }, []);

  // Persist buyer to localStorage when changed
  const setSelectedBuyerId = useCallback((buyerId: string | null) => {
    setSelectedBuyerIdState(buyerId);
    if (buyerId) {
      localStorage.setItem(SELECTED_BUYER_KEY, buyerId);
    } else {
      localStorage.removeItem(SELECTED_BUYER_KEY);
    }
  }, []);

  // Persist service account to localStorage when changed
  const setSelectedServiceAccountId = useCallback((accountId: string | null) => {
    setSelectedServiceAccountIdState(accountId);
    if (accountId) {
      localStorage.setItem(SELECTED_SERVICE_ACCOUNT_KEY, accountId);
    } else {
      localStorage.removeItem(SELECTED_SERVICE_ACCOUNT_KEY);
    }
  }, []);

  // Don't render children until initialized to prevent hydration mismatch
  if (!initialized) {
    return null;
  }

  return (
    <AccountContext.Provider value={{
      selectedBuyerId,
      setSelectedBuyerId,
      selectedServiceAccountId,
      setSelectedServiceAccountId,
    }}>
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
