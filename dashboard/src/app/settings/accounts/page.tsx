"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Settings, Link2, Mail } from "lucide-react";
import { getHealth, getGmailStatus } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { SensitiveRouteGuard } from "@/components/sensitive-route-guard";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/contexts/i18n-context";

// Import extracted components
import { ApiConnectionTab, GmailReportsTab, SystemTab } from "./components";

type SetupTab = "api" | "gmail" | "system";

export default function ConnectedAccountsPage() {
  const { t } = useTranslation();

  const TABS: { id: SetupTab; label: string; icon: React.ElementType; description: string }[] = [
    { id: "api", label: t.setup?.connectApi || "Connect API", icon: Link2, description: t.setup?.googleAuthorizedBuyers || "Google Authorized Buyers" },
    { id: "gmail", label: t.setup?.gmailReports || "Gmail Reports", icon: Mail, description: t.setup?.autoFetchReports || "Auto-fetch reports" },
    { id: "system", label: t.setup?.system || "System", icon: Settings, description: t.setup?.statusAndSettings || "Status & settings" },
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

  const { data: gmailStatus } = useQuery({
    queryKey: ["gmailStatus"],
    queryFn: getGmailStatus,
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
            : "Failed to check API status"
        }
        onRetry={() => refetchHealth()}
      />
    );
  }

  const isConfigured = health?.configured === true;
  const isGmailAuthorized = gmailStatus?.authorized === true;
  const isGmailConfigured = gmailStatus?.configured === true;

  return (
    <SensitiveRouteGuard featureName="API credentials and account settings">
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t.setup?.title || "Connected Accounts"}</h1>
        <p className="text-gray-600 mt-1">
          {t.setup?.configureDataSources || "Configure your data sources and integrations"}
        </p>
      </div>

      {/* Quick Status Bar */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-2 h-2 rounded-full",
                isConfigured ? "bg-green-500" : "bg-yellow-500"
              )} />
              <span className="text-sm text-gray-600">
                API: {isConfigured ? (t.setup?.connected || "Connected") : (t.setup?.notConnected || "Not connected")}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn(
                "w-2 h-2 rounded-full",
                isGmailAuthorized ? "bg-green-500" : isGmailConfigured ? "bg-yellow-500" : "bg-gray-400"
              )} />
              <span className="text-sm text-gray-600">
                Gmail: {isGmailAuthorized ? (t.setup?.connected || "Connected") : isGmailConfigured ? (t.setup?.notAuthorized || "Not authorized") : (t.setup?.notConfigured || "Not configured")}
              </span>
            </div>
          </div>
          <Link
            href="/"
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            {t.setup?.goToWasteOptimizer || "Go to Waste Optimizer"} →
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-1" aria-label="Setup tabs">
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
        {activeTab === "gmail" && <GmailReportsTab />}
        {activeTab === "system" && <SystemTab />}
      </div>
    </div>
    </SensitiveRouteGuard>
  );
}
