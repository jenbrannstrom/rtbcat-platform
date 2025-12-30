"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AccountProvider } from "@/contexts/account-context";
import { AuthProvider } from "@/contexts/auth-context";
import { I18nProvider } from "@/contexts/i18n-context";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <AuthProvider>
          <AccountProvider>{children}</AccountProvider>
        </AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
