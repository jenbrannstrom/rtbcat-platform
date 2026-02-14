"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { SELECTED_BUYER_COOKIE, SELECTED_BUYER_STORAGE_KEY } from "@/lib/buyer-routes";

const SELECTED_SERVICE_ACCOUNT_KEY = "rtbcat-selected-service-account-id";
const BUYER_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function writeCookie(name: string, value: string | null) {
  if (value) {
    document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${BUYER_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
    return;
  }
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`;
}

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
    const storedBuyer = localStorage.getItem(SELECTED_BUYER_STORAGE_KEY) || readCookie(SELECTED_BUYER_COOKIE);
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
      localStorage.setItem(SELECTED_BUYER_STORAGE_KEY, buyerId);
    } else {
      localStorage.removeItem(SELECTED_BUYER_STORAGE_KEY);
    }
    writeCookie(SELECTED_BUYER_COOKIE, buyerId);
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
