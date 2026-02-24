"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Settings, Link2 } from "lucide-react";
import { getHealth } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

// Import extracted components
import { ApiConnectionTab, SystemTab } from "./components";

type SetupTab = "api" | "system";

export default function ConnectedAccountsPage() {
  const { t } = useTranslation();

  const TABS: { id: SetupTab; label: string; icon: React.ElementType; description: string }[] = [
    { id: "api", label: t.setup.connectApi, icon: Link2, description: t.setup.googleAuthorizedBuyers },
    { id: "system", label: t.setup.system, icon: Settings, description: t.setup.statusAndSettings },
  ];
  const [activeTab, setActiveTab] = useState<SetupTab>("api");

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  if (healthLoading) {
    return <LoadingPage />;
  }

  if (healthError) {
    return (
      <ErrorPage
        message={
          healthError instanceof Error
            ? healthError.message
            : t.settings.failedToCheckApiStatus
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  const isConfigured = health?.configured === true;
  const apiConnected = !healthError;
  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t.settingsNav.connectedAccounts}</h1>
        <p className="text-gray-600 mt-1">
          {t.setup.configureDataSources}
        </p>
      </div>

      {/* Quick Status Bar */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-2 h-2 rounded-full",
                apiConnected ? "bg-green-500" : "bg-red-500"
              )} />
              <span className="text-sm text-gray-600">
                {t.setup.apiStatusLabel}: {apiConnected ? t.setup.connected : t.setup.notConnected}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-2 h-2 rounded-full",
                isConfigured ? "bg-green-500" : "bg-yellow-500"
              )} />
              <span className="text-sm text-gray-600">
                {t.setup.accountsStatusLabel}: {isConfigured ? t.settings.configured : t.setup.notConfigured}
              </span>
            </div>
          </div>
          <div />
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-1" aria-label={t.setup.tabsNavLabel}>
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                  isActive
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[500px]">
        {activeTab === "api" && <ApiConnectionTab />}
        {activeTab === "system" && <SystemTab />}
      </div>
    </div>
  );
}
