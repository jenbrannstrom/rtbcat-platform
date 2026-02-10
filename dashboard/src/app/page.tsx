"use client";

import { useState, useCallback, Suspense, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, AlertTriangle, ArrowUp, ArrowDown, ChevronsUpDown } from "lucide-react";
import { AccountEndpointsHeader } from "@/components/rtb/account-endpoints-header";
import { EndpointEfficiencyPanel } from "@/components/rtb/endpoint-efficiency-panel";
import { PretargetingConfigCard, type PretargetingConfig } from "@/components/rtb/pretargeting-config-card";
import { ConfigBreakdownPanel } from "@/components/rtb/config-breakdown-panel";
import {
  getQPSSummary, getRTBFunnel, getSpendStats, getEndpointEfficiency,
  getPretargetingConfigs, getRTBFunnelConfigs, getSeats,
  type PretargetingConfigResponse
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];

/**
 * Helper to transform API response to component props.
 */
function transformConfigToProps(
  apiConfig: PretargetingConfigResponse,
  performanceData?: { reached: number; impressions: number; win_rate: number; waste_rate: number }
): PretargetingConfig {
  const name = apiConfig.user_name || apiConfig.display_name || `Config ${apiConfig.billing_id}`;
  const hasPerformance = !!performanceData && (performanceData.reached > 0 || performanceData.impressions > 0);
  const reached = performanceData?.reached || 0;
  const impressions = performanceData?.impressions || 0;
  const win_rate = performanceData?.win_rate || 0;
  const waste_rate = performanceData?.waste_rate || 0;

  return {
    billing_id: apiConfig.billing_id || apiConfig.config_id,
    name,
    display_name: apiConfig.display_name,
    user_name: apiConfig.user_name,
    state: (apiConfig.state as 'ACTIVE' | 'SUSPENDED') || 'ACTIVE',
    formats: apiConfig.included_formats || [],
    platforms: apiConfig.included_platforms || [],
    sizes: apiConfig.included_sizes || [],
    included_geos: apiConfig.included_geos || [],
    reached,
    impressions,
    win_rate,
    waste_rate,
    has_performance: hasPerformance,
  };
}

function WasteAnalysisContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();
  const { t } = useTranslation();

  const initialDays = parseInt(searchParams.get("days") || "7", 10);
  const [days, setDays] = useState<number>(initialDays);

  // Fetch seats to auto-select first one if none selected
  const { data: seats } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
  });

  // Auto-select first seat if none selected (removes "All Seats" from Waste Analyzer)
  useEffect(() => {
    if (!selectedBuyerId && seats && seats.length > 0) {
      setSelectedBuyerId(seats[0].buyer_id);
    }
  }, [selectedBuyerId, seats, setSelectedBuyerId]);

  useEffect(() => {
    setExpandedConfigId(null);
  }, [selectedBuyerId]);

  const [expandedConfigId, setExpandedConfigId] = useState<string | null>(null);

  // Sorting state for pretargeting configs
  type SortColumn = 'name' | 'reached' | 'win_rate' | 'waste_rate';
  type SortDirection = 'asc' | 'desc';
  const [sortColumn, setSortColumn] = useState<SortColumn>('waste_rate');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = useCallback((column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  }, [sortColumn]);

  const updateUrl = useCallback(
    (newDays: number) => {
      const params = new URLSearchParams();
      params.set("days", String(newDays));
      router.replace(`/?${params.toString()}`, { scroll: false });
    },
    [router]
  );

  const handleDaysChange = useCallback(
    (newDays: number) => {
      setDays(newDays);
      updateUrl(newDays);
    },
    [updateUrl]
  );

  // Fetch QPS summary
  const {
    data: qpsSummary,
    isLoading: summaryLoading,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["qps-summary", days],
    queryFn: () => getQPSSummary(days, selectedBuyerId || undefined),
  });

  // Fetch RTB funnel data from CSV files
  const {
    data: rtbFunnel,
    isLoading: funnelLoading,
    refetch: refetchFunnel,
  } = useQuery({
    queryKey: ["rtb-funnel", days, selectedBuyerId],
    queryFn: () => getRTBFunnel(days, selectedBuyerId || undefined),
  });

  // Fetch spend stats for CPM display (filtered by expanded config if selected)
  const {
    data: spendStats,
    refetch: refetchSpend,
  } = useQuery({
    queryKey: ["spend-stats", days, expandedConfigId],
    queryFn: () => getSpendStats(days, expandedConfigId || undefined),
  });

  // Fetch pretargeting configs
  const {
    data: pretargetingConfigs,
    isLoading: configsLoading,
    refetch: refetchConfigs,
  } = useQuery({
    queryKey: ["pretargeting-configs", selectedBuyerId],
    queryFn: () => getPretargetingConfigs({ buyer_id: selectedBuyerId || undefined }),
  });

  // Fetch config-level performance data (filtered by selected buyer)
  const {
    data: configPerformance,
    isLoading: configPerformanceLoading,
    refetch: refetchConfigPerf,
    isError: configPerformanceError,
  } = useQuery({
    queryKey: ["rtb-funnel-configs", days, selectedBuyerId],
    queryFn: () => getRTBFunnelConfigs(days, selectedBuyerId || undefined),
    retry: 0,
  });

  const { data: endpointEfficiency, isLoading: endpointEfficiencyLoading } = useQuery({
    queryKey: ["endpoint-efficiency", days, selectedBuyerId],
    queryFn: () => getEndpointEfficiency(days, selectedBuyerId || undefined),
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchFunnel();
    refetchSpend();
    refetchConfigs();
    refetchConfigPerf();
  };

  // Use real funnel data if available (has_data can be at top level or in funnel)
  const hasFunnelData = rtbFunnel?.has_data ?? rtbFunnel?.funnel?.has_data ?? false;
  const reached = hasFunnelData ? (rtbFunnel?.funnel?.total_reached_queries ?? null) : null;
  const impressions = hasFunnelData ? (rtbFunnel?.funnel?.total_impressions ?? 0) : 0;

  // Publishers and Geos from RTB data

  // Build a map of billing_id to performance data from config performance API
  const configPerformanceMap = new Map<string, { reached: number; impressions: number; win_rate: number; waste_rate: number }>();
  if (configPerformance?.configs) {
    for (const cfg of configPerformance.configs) {
      configPerformanceMap.set(cfg.billing_id, {
        reached: cfg.reached || 0,
        impressions: cfg.impressions || 0,
        win_rate: cfg.win_rate_pct || 0,
        waste_rate: cfg.waste_pct || 0,
      });
    }
  }

  // Transform configs for display and sort
  const unsortedConfigs = (pretargetingConfigs || []).map(config =>
    transformConfigToProps(config, configPerformanceMap.get(config.billing_id || config.config_id))
  );

  // Sort configs based on current sort settings
  const displayConfigs = [...unsortedConfigs].sort((a, b) => {
    if (a.has_performance !== b.has_performance) {
      return a.has_performance ? -1 : 1;
    }
    let aVal: number | string;
    let bVal: number | string;

    switch (sortColumn) {
      case 'name':
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case 'reached':
        aVal = a.reached;
        bVal = b.reached;
        break;
      case 'win_rate':
        aVal = a.win_rate;
        bVal = b.win_rate;
        break;
      case 'waste_rate':
      default:
        aVal = a.waste_rate;
        bVal = b.waste_rate;
        break;
    }

    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  const activeConfigsCount = displayConfigs.filter(c => c.state === 'ACTIVE').length;

  // Calculate funnel metrics for compact display
  const winRate = reached && impressions ? (impressions / reached * 100) : null;
  const funnelDataForHeader = {
    reached,
    impressions: impressions || 0,
    winRate,
  };

  return (
    <div className="max-w-7xl mx-auto">
      {/* Compact Top Bar - CPM, Period Selector, Refresh */}
      <div className="sticky top-0 z-30 px-6 py-2 bg-white border-b border-gray-200">
        <div className="flex items-center justify-end gap-2">
          {/* CPM Badge - compact */}
          {spendStats?.has_spend_data && spendStats.avg_cpm_usd && (
            <div className={cn(
              "px-2 py-1 rounded text-xs",
              expandedConfigId
                ? "bg-blue-50 border border-blue-200"
                : "bg-green-50 border border-green-200"
            )}>
              <span className={cn(
                "uppercase tracking-wide",
                expandedConfigId ? "text-blue-600" : "text-green-600"
              )}>
                {expandedConfigId ? 'Config CPM' : 'Avg CPM'}
              </span>
              <span className={cn(
                "ml-1 font-bold",
                expandedConfigId ? "text-blue-700" : "text-green-700"
              )}>
                ${spendStats.avg_cpm_usd.toFixed(2)}
              </span>
            </div>
          )}

          {/* Period Selector - compact buttons */}
          <div className="flex rounded border border-gray-300 overflow-hidden">
            {PERIOD_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => handleDaysChange(option.value)}
                className={cn(
                  "px-2.5 py-1 text-xs font-medium transition-colors",
                  days === option.value
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                )}
              >
                {option.value}d
              </button>
            ))}
          </div>

          {/* Refresh button - icon only */}
          <button
            onClick={handleRefresh}
            disabled={summaryLoading}
            className={cn(
              "p-1.5 rounded border border-gray-300",
              "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
            title={t.common.refresh}
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-gray-600", (summaryLoading || funnelLoading) && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Content area with padding */}
      <div className="p-6 space-y-4">
      {/* Account Endpoints Header with integrated funnel metrics */}
      <AccountEndpointsHeader funnelData={funnelDataForHeader} />

      {endpointEfficiency && !endpointEfficiencyLoading && (
        <EndpointEfficiencyPanel data={endpointEfficiency} />
      )}

      {selectedBuyerId && rtbFunnel?.data_sources?.buyer_filter_message && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
          {rtbFunnel.data_sources.buyer_filter_message}
        </div>
      )}

      {/* Recommended Optimizations Panel (disabled; see ROADMAP) */}

      {/* Pretargeting Configs Section */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {t.pretargeting.configs} ({activeConfigsCount} {t.pretargeting.active})
          </h2>
        </div>

        {configsLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : displayConfigs.length === 0 ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <AlertTriangle className="h-8 w-8 text-yellow-500 mx-auto mb-3" />
            <h3 className="font-medium text-yellow-800 mb-2">{t.pretargeting.noPretargetingConfigs}</h3>
            <p className="text-sm text-yellow-700 mb-4">
              {t.pretargeting.useSyncAllToFetch || "Use \"Sync All\" in the sidebar to fetch pretargeting configs."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {(configPerformanceLoading || configPerformanceError) && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                Config performance metrics are delayed; showing base config list.
              </div>
            )}
            {/* Sortable Column Headers */}
            <div className="flex items-center px-4 py-2 bg-gray-100 rounded-t-lg text-xs font-medium text-gray-600 uppercase tracking-wider">
              <button
                onClick={() => handleSort('name')}
                className="flex items-center gap-1 flex-1 hover:text-gray-900"
              >
                {t.common.name}
                {sortColumn === 'name' ? (
                  sortDirection === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                ) : <ChevronsUpDown className="h-3 w-3 text-gray-400" />}
              </button>
              <button
                onClick={() => handleSort('reached')}
                className="flex items-center gap-1 w-24 justify-end hover:text-gray-900"
              >
                {t.dashboard.reached}
                {sortColumn === 'reached' ? (
                  sortDirection === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                ) : <ChevronsUpDown className="h-3 w-3 text-gray-400" />}
              </button>
              <button
                onClick={() => handleSort('win_rate')}
                className="flex items-center gap-1 w-24 justify-end hover:text-gray-900"
              >
                {t.dashboard.winRate}
                {sortColumn === 'win_rate' ? (
                  sortDirection === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                ) : <ChevronsUpDown className="h-3 w-3 text-gray-400" />}
              </button>
              <button
                onClick={() => handleSort('waste_rate')}
                className="flex items-center gap-1 w-24 justify-end hover:text-gray-900"
              >
                {t.pretargeting.waste}
                {sortColumn === 'waste_rate' ? (
                  sortDirection === 'asc' ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                ) : <ChevronsUpDown className="h-3 w-3 text-gray-400" />}
              </button>
              <div className="w-8" /> {/* Spacer for expand button */}
            </div>
            {displayConfigs.map(config => (
              <div key={config.billing_id}>
                <PretargetingConfigCard
                  config={config}
                  isExpanded={expandedConfigId === config.billing_id}
                  onToggleExpand={() => setExpandedConfigId(
                    prev => prev === config.billing_id ? null : config.billing_id
                  )}
                />
                <ConfigBreakdownPanel
                  billing_id={config.billing_id}
                  days={days}
                  isExpanded={expandedConfigId === config.billing_id}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      </div>
    </div>
  );
}

function WasteAnalysisLoading() {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="mt-2 h-4 w-96 bg-gray-100 rounded animate-pulse" />
      </div>
      <div className="space-y-6">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-64 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<WasteAnalysisLoading />}>
      <WasteAnalysisContent />
    </Suspense>
  );
}
