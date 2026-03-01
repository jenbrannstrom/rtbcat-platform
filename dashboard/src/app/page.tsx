"use client";

import { useState, useCallback, Suspense, useEffect, useRef } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, AlertTriangle, ArrowUp, ArrowDown, ChevronsUpDown, Loader2 } from "lucide-react";
import { AccountEndpointsHeader } from "@/components/rtb/account-endpoints-header";
import { EndpointEfficiencyPanel } from "@/components/rtb/endpoint-efficiency-panel";
import { PretargetingConfigCard, type PretargetingConfig } from "@/components/rtb/pretargeting-config-card";
import { ConfigBreakdownPanel } from "@/components/rtb/config-breakdown-panel";
import {
  getRTBFunnel, getSpendStats, getEndpointEfficiency,
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

function getRetryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 5000);
}

function normalizeDateString(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.slice(0, 10);
}

interface QpsPageLoadMetricsSnapshot {
  started_at_iso: string;
  buyer_id: string | null;
  days: number;
  time_to_first_table_row_ms: number | null;
  time_to_table_hydrated_ms: number | null;
  api_latency_ms: Record<string, number>;
}

interface QpsPageLoadMetricPostPayload {
  page: "qps_home";
  buyer_id?: string | null;
  selected_days?: number;
  time_to_first_table_row_ms?: number | null;
  time_to_table_hydrated_ms?: number | null;
  api_latency_ms?: Record<string, number>;
  sampled_at?: string;
}

declare global {
  interface Window {
    __CATSCAN_QPS_LOAD_METRICS?: QpsPageLoadMetricsSnapshot;
  }
}

/**
 * Helper to transform API response to component props.
 */
function transformConfigToProps(
  apiConfig: PretargetingConfigResponse,
  performanceData?: { reached: number; impressions: number; win_rate: number; waste_rate: number },
  metricsDelayed = false
): PretargetingConfig {
  const name = apiConfig.user_name || apiConfig.display_name || `Config ${apiConfig.billing_id}`;
  const hasPerformance = performanceData !== undefined;
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
    maximum_qps: apiConfig.maximum_qps ?? null,
    formats: apiConfig.included_formats || [],
    platforms: apiConfig.included_platforms || [],
    sizes: apiConfig.included_sizes || [],
    included_geos: apiConfig.included_geos || [],
    reached,
    impressions,
    win_rate,
    waste_rate,
    has_performance: hasPerformance,
    metrics_delayed: metricsDelayed && !hasPerformance,
  };
}

function WasteAnalysisContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { selectedBuyerId, setSelectedBuyerId } = useAccount();
  const { t } = useTranslation();

  const initialDays = parseInt(searchParams.get("days") || "7", 10);
  const [days, setDays] = useState<number>(initialDays);
  const [dashboardLoadStartedAt] = useState<number>(() => Date.now());
  const perfMarkPrefixRef = useRef<string>(`catscan:qps:${dashboardLoadStartedAt}`);
  const firstTableRowMsRef = useRef<number | null>(null);
  const tableHydratedMsRef = useRef<number | null>(null);
  const startupApiLatencyMsRef = useRef<Record<string, number>>({});
  const qpsLoadMetricsPostedRef = useRef<boolean>(false);

  const setStartupApiLatency = useCallback((name: string, startedAtMs: number) => {
    const endedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    startupApiLatencyMsRef.current[name] = Math.round(Math.max(0, endedAtMs - startedAtMs));
  }, []);

  const writeQpsLoadMetricsSnapshot = useCallback((): QpsPageLoadMetricsSnapshot | null => {
    if (typeof window === "undefined") return null;
    const snapshot: QpsPageLoadMetricsSnapshot = {
      started_at_iso: new Date(dashboardLoadStartedAt).toISOString(),
      buyer_id: selectedBuyerId || null,
      days,
      time_to_first_table_row_ms: firstTableRowMsRef.current,
      time_to_table_hydrated_ms: tableHydratedMsRef.current,
      api_latency_ms: { ...startupApiLatencyMsRef.current },
    };
    window.__CATSCAN_QPS_LOAD_METRICS = snapshot;
    return snapshot;
  }, [dashboardLoadStartedAt, days, selectedBuyerId]);

  const postQpsLoadMetricPayload = useCallback((payload: QpsPageLoadMetricPostPayload) => {
    const body = JSON.stringify(payload);
    let queued = false;
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      try {
        queued = navigator.sendBeacon(
          "/api/system/ui-metrics/page-load",
          new Blob([body], { type: "application/json" })
        );
      } catch {
        queued = false;
      }
    }
    if (!queued) {
      fetch("/api/system/ui-metrics/page-load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body,
        keepalive: true,
      }).catch(() => undefined);
    }
  }, []);

  const submitQpsLoadMetrics = useCallback((snapshot: QpsPageLoadMetricsSnapshot | null) => {
    if (!snapshot || qpsLoadMetricsPostedRef.current) return;
    if (snapshot.time_to_table_hydrated_ms === null) return;

    postQpsLoadMetricPayload({
      page: "qps_home",
      buyer_id: snapshot.buyer_id,
      selected_days: snapshot.days,
      time_to_first_table_row_ms: snapshot.time_to_first_table_row_ms,
      time_to_table_hydrated_ms: snapshot.time_to_table_hydrated_ms,
      api_latency_ms: snapshot.api_latency_ms,
      sampled_at: snapshot.started_at_iso,
    });
    qpsLoadMetricsPostedRef.current = true;
  }, [postQpsLoadMetricPayload]);

  const submitQpsApiLatencySample = useCallback((apiPath: string, latencyMs: number) => {
    postQpsLoadMetricPayload({
      page: "qps_home",
      buyer_id: selectedBuyerId || null,
      selected_days: days,
      api_latency_ms: { [apiPath]: latencyMs },
      sampled_at: new Date().toISOString(),
    });
  }, [days, postQpsLoadMetricPayload, selectedBuyerId]);

  // Fetch seats to auto-select first one if none selected
  const {
    data: seats,
    isLoading: seatsLoading,
    isError: seatsError,
    refetch: refetchSeats,
  } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
    retry: 5,
    retryDelay: getRetryDelay,
    staleTime: 60_000,
  });

  // Keep selected seat valid and deterministic once seats resolve.
  useEffect(() => {
    if (!seats || seats.length === 0) return;

    const hasSelectedSeat = !!selectedBuyerId && seats.some((seat) => seat.buyer_id === selectedBuyerId);
    if (!hasSelectedSeat) {
      setSelectedBuyerId(seats[0].buyer_id);
    }
  }, [selectedBuyerId, seats, setSelectedBuyerId]);

  const [expandedConfigId, setExpandedConfigId] = useState<string | null>(null);

  useEffect(() => {
    setExpandedConfigId(null);
  }, [selectedBuyerId]);

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
      const targetPath = pathname || "/";
      router.replace(`${targetPath}?${params.toString()}`, { scroll: false });
    },
    [pathname, router]
  );

  const handleDaysChange = useCallback(
    (newDays: number) => {
      setDays(newDays);
      updateUrl(newDays);
    },
    [updateUrl]
  );

  // Only fire analytics queries once seats have loaded AND selectedBuyerId is
  // confirmed valid.  This prevents 403 storms when the user's RBAC changed
  // but localStorage still holds the old buyer_id.
  const seatReady = !!selectedBuyerId && !!seats && seats.some((s) => s.buyer_id === selectedBuyerId);

  const fetchMeasuredPretargetingConfigs = useCallback(async () => {
    const startedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    try {
      return await getPretargetingConfigs({ buyer_id: selectedBuyerId || undefined });
    } finally {
      setStartupApiLatency("/settings/pretargeting", startedAtMs);
      writeQpsLoadMetricsSnapshot();
    }
  }, [selectedBuyerId, setStartupApiLatency, writeQpsLoadMetricsSnapshot]);

  const fetchMeasuredConfigPerformance = useCallback(async () => {
    const startedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    try {
      return await getRTBFunnelConfigs(days, selectedBuyerId || undefined);
    } finally {
      setStartupApiLatency("/analytics/home/configs", startedAtMs);
      writeQpsLoadMetricsSnapshot();
    }
  }, [days, selectedBuyerId, setStartupApiLatency, writeQpsLoadMetricsSnapshot]);

  const fetchMeasuredEndpointEfficiency = useCallback(async () => {
    const startedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    try {
      return await getEndpointEfficiency(days, selectedBuyerId || undefined);
    } finally {
      setStartupApiLatency("/analytics/home/endpoint-efficiency", startedAtMs);
      writeQpsLoadMetricsSnapshot();
    }
  }, [days, selectedBuyerId, setStartupApiLatency, writeQpsLoadMetricsSnapshot]);

  const handleApiLatencyMeasured = useCallback((apiPath: string, latencyMs: number) => {
    const normalizedLatency = Math.round(Math.max(0, latencyMs));
    startupApiLatencyMsRef.current[apiPath] = normalizedLatency;
    writeQpsLoadMetricsSnapshot();
    if (qpsLoadMetricsPostedRef.current) {
      submitQpsApiLatencySample(apiPath, normalizedLatency);
    }
  }, [submitQpsApiLatencySample, writeQpsLoadMetricsSnapshot]);

  // Fetch RTB funnel data from CSV files
  const {
    data: rtbFunnel,
    isLoading: funnelLoading,
    refetch: refetchFunnel,
  } = useQuery({
    queryKey: ["rtb-funnel", days, selectedBuyerId],
    queryFn: () => getRTBFunnel(days, selectedBuyerId || undefined),
    enabled: false,
  });

  // Fetch spend stats for CPM display (filtered by expanded config if selected)
  const {
    data: spendStats,
    refetch: refetchSpend,
  } = useQuery({
    queryKey: ["spend-stats", days, selectedBuyerId, expandedConfigId],
    queryFn: () => getSpendStats(days, expandedConfigId || undefined),
    enabled: seatReady,
  });

  // Fetch pretargeting configs
  const {
    data: pretargetingConfigs,
    isLoading: configsLoading,
    refetch: refetchConfigs,
  } = useQuery({
    queryKey: ["pretargeting-configs", selectedBuyerId],
    queryFn: fetchMeasuredPretargetingConfigs,
    enabled: seatReady,
    retry: 5,
    retryDelay: getRetryDelay,
    retryOnMount: true,
    refetchOnReconnect: true,
    refetchInterval: (query) => {
      if (!seatReady) return false;
      if (Date.now() - dashboardLoadStartedAt > 120_000) return false;
      if (query.state.status === "error") return 5000;
      const rows = query.state.data as PretargetingConfigResponse[] | undefined;
      if (Array.isArray(rows) && rows.length === 0) return 8000;
      return false;
    },
  });

  // Fetch config-level performance data (filtered by selected buyer)
  const {
    data: configPerformance,
    isLoading: configPerformanceLoading,
    refetch: refetchConfigPerf,
    isError: configPerformanceError,
    isFetching: configPerformanceFetching,
  } = useQuery({
    queryKey: ["rtb-funnel-configs", days, selectedBuyerId],
    queryFn: fetchMeasuredConfigPerformance,
    enabled: seatReady,
    retry: 5,
    retryDelay: getRetryDelay,
    retryOnMount: true,
    refetchOnReconnect: true,
    refetchInterval: (query) => {
      if (!seatReady) return false;
      if (Date.now() - dashboardLoadStartedAt > 120_000) return false;
      if (query.state.status === "error") return 5000;
      return false;
    },
  });

  const { data: endpointEfficiency, isLoading: endpointEfficiencyLoading } = useQuery({
    queryKey: ["endpoint-efficiency", days, selectedBuyerId],
    queryFn: fetchMeasuredEndpointEfficiency,
    enabled: seatReady,
  });

  const handleRefresh = () => {
    refetchFunnel();
    refetchSpend();
    refetchConfigs();
    refetchConfigPerf();
  };

  // Build a map of billing_id to performance data from config performance API
  const configMetricsDelayed = configPerformanceLoading || configPerformanceFetching || configPerformanceError;
  const configFallbackApplied = configPerformance?.fallback_applied === true;
  const configRequestedDays = configPerformance?.requested_days ?? days;
  const configEffectiveDays = configPerformance?.effective_days ?? days;
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
    transformConfigToProps(
      config,
      configPerformanceMap.get(config.billing_id || config.config_id),
      configMetricsDelayed
    )
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
  const hasTableRows = !configsLoading && displayConfigs.length > 0;
  const tableHydrated = hasTableRows && !configPerformanceLoading && !configPerformanceFetching;

  useEffect(() => {
    if (!seatReady || !tableHydrated) return;
    refetchFunnel();
  }, [refetchFunnel, seatReady, tableHydrated, selectedBuyerId, days]);

  useEffect(() => {
    writeQpsLoadMetricsSnapshot();
  }, [writeQpsLoadMetricsSnapshot]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.performance?.mark) return;
    const startMark = `${perfMarkPrefixRef.current}:navigation-start`;
    window.performance.mark(startMark);
  }, []);

  useEffect(() => {
    if (!hasTableRows || firstTableRowMsRef.current !== null) return;
    const elapsedMs = Math.max(0, Date.now() - dashboardLoadStartedAt);
    firstTableRowMsRef.current = elapsedMs;
    if (typeof window !== "undefined" && window.performance?.mark && window.performance?.measure) {
      try {
        const startMark = `${perfMarkPrefixRef.current}:navigation-start`;
        const endMark = `${perfMarkPrefixRef.current}:first-table-row`;
        const measureName = `${perfMarkPrefixRef.current}:time_to_first_table_row`;
        window.performance.mark(endMark);
        window.performance.measure(measureName, startMark, endMark);
      } catch {
        // Best-effort mark/measure for operator diagnostics.
      }
    }
    writeQpsLoadMetricsSnapshot();
  }, [dashboardLoadStartedAt, hasTableRows, writeQpsLoadMetricsSnapshot]);

  useEffect(() => {
    if (!tableHydrated || tableHydratedMsRef.current !== null) return;
    const elapsedMs = Math.max(0, Date.now() - dashboardLoadStartedAt);
    tableHydratedMsRef.current = elapsedMs;
    if (typeof window !== "undefined" && window.performance?.mark && window.performance?.measure) {
      try {
        const startMark = `${perfMarkPrefixRef.current}:navigation-start`;
        const endMark = `${perfMarkPrefixRef.current}:table-hydrated`;
        const measureName = `${perfMarkPrefixRef.current}:time_to_table_hydrated`;
        window.performance.mark(endMark);
        window.performance.measure(measureName, startMark, endMark);
      } catch {
        // Best-effort mark/measure for operator diagnostics.
      }
    }
    const snapshot = writeQpsLoadMetricsSnapshot();
    submitQpsLoadMetrics(snapshot);
  }, [dashboardLoadStartedAt, submitQpsLoadMetrics, tableHydrated, writeQpsLoadMetricsSnapshot]);

  // Observed QPS by endpoint for endpoints header
  const coverage = endpointEfficiency?.data_coverage;
  const observedQpsByEndpointId = endpointEfficiency?.endpoint_reconciliation?.rows?.reduce<Record<string, number | null>>(
    (acc, row) => {
      if (row.catscan_endpoint_id) {
        acc[row.catscan_endpoint_id] = row.google_current_qps;
      }
      return acc;
    },
    {}
  ) ?? {};

  const homeSeatDataAsOf = normalizeDateString(coverage?.home_seat_daily?.end_date ?? null);
  const bidstreamDataAsOf = normalizeDateString(coverage?.rtb_bidstream?.end_date ?? null);
  const availableDataDates = [homeSeatDataAsOf, bidstreamDataAsOf].filter((value): value is string => !!value);
  const dataAsOf = availableDataDates.length > 0 ? [...availableDataDates].sort()[0] : null;
  const hasDataDateDrift = !!homeSeatDataAsOf && !!bidstreamDataAsOf && homeSeatDataAsOf !== bidstreamDataAsOf;

  return (
    <div className="max-w-7xl mx-auto">
      {/* Compact Top Bar - CPM, Period Selector, Refresh */}
      <div className="sticky top-0 z-30 px-6 py-2 bg-white border-b border-gray-200">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-gray-600">
            {seatReady && dataAsOf && (
              <span>
                {t.dashboard.dataAsOf} <strong>{dataAsOf}</strong>
                {hasDataDateDrift && (
                  <span className="ml-2 text-amber-700">
                    ({t.dashboard.homeLabel}: {homeSeatDataAsOf}, {t.dashboard.bidstreamLabel}: {bidstreamDataAsOf})
                  </span>
                )}
              </span>
            )}
            {seatReady && !dataAsOf && (
              <span className="text-gray-500">{t.dashboard.dataFreshnessPending}</span>
            )}
          </div>
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
                {expandedConfigId ? t.dashboard.configCpm : t.dashboard.avgCpm}
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
            disabled={funnelLoading || configsLoading || configPerformanceLoading}
            className={cn(
              "p-1.5 rounded border border-gray-300",
              "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
            title={t.common.refresh}
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-gray-600", (funnelLoading || configsLoading || configPerformanceLoading) && "animate-spin")} />
          </button>
          </div>
        </div>
      </div>

      {/* Content area with padding */}
      <div className="p-6 space-y-4">
      {seatsError && (
        <div className="flex items-center justify-between gap-3 text-red-800 bg-red-50 border border-red-200 rounded px-3 py-2">
          <span>{t.dashboard.unableToLoadBuyerSeatsRetry}</span>
          <button
            onClick={() => refetchSeats()}
            className="px-2 py-1 text-xs font-medium rounded bg-red-100 hover:bg-red-200"
          >
            {t.common.retry}
          </button>
        </div>
      )}
      {!seatReady && !seatsError && (
        <div className="rounded-lg p-4 text-sm border">
          {seatsLoading && (
            <div className="flex items-center gap-2 text-blue-800 bg-blue-50 border border-blue-200 rounded px-3 py-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{t.dashboard.loadingSeatAccess}</span>
            </div>
          )}
          {!seatsLoading && seats && seats.length === 0 && (
            <div className="text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {t.dashboard.noActiveBuyerSeatsSyncSettings}
            </div>
          )}
          {!seatsLoading && seats && seats.length > 0 && (
            <div className="text-blue-800 bg-blue-50 border border-blue-200 rounded px-3 py-2">
              {t.dashboard.selectSeatToLoadHomeAnalytics}
            </div>
          )}
        </div>
      )}
      {/* Account Endpoints Header - config only, no delivery duplication */}
      <AccountEndpointsHeader
        observedQpsByEndpointId={observedQpsByEndpointId}
        onApiLatencyMeasured={handleApiLatencyMeasured}
      />

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
              <div key={i} className="h-16 bg-gray-200 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : displayConfigs.length === 0 ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <AlertTriangle className="h-8 w-8 text-yellow-500 mx-auto mb-3" />
            <h3 className="font-medium text-yellow-800 mb-2">{t.pretargeting.noPretargetingConfigs}</h3>
            <p className="text-sm text-yellow-700 mb-4">
              {t.pretargeting.useSyncAllToFetch}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {configMetricsDelayed && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 flex items-center gap-2">
                {(configPerformanceLoading || configPerformanceFetching) && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" />
                )}
                <span>
                  {configPerformanceError
                    ? t.pretargeting.configPerformanceFailedNoValues
                    : t.pretargeting.configPerformanceDelayedNoValues}
                  </span>
              </div>
            )}
            {configFallbackApplied && (
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
                <span>
                  {t.pretargeting.showingLast} <span className="font-semibold">{configEffectiveDays} {t.dashboard.days}</span>
                  {" "}{t.pretargeting.becauseNoRowsFoundInRequested}
                  {" "}<span className="font-semibold">{configRequestedDays} {t.pretargeting.dayWindow}</span>
                </span>
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
                {expandedConfigId === config.billing_id && (
                  <ConfigBreakdownPanel
                    billing_id={config.billing_id}
                    days={days}
                    isExpanded={true}
                    onApiLatencyMeasured={handleApiLatencyMeasured}
                  />
                )}
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
        <div className="h-8 w-48 bg-gray-300 rounded animate-pulse" />
        <div className="mt-2 h-4 w-96 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="space-y-6">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-64 bg-gray-200 rounded-xl animate-pulse" />
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
