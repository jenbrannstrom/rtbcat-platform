"use client";

import { useState, useCallback, Suspense, useEffect, useRef, useMemo } from "react";
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
  type PretargetingConfigResponse,
  type RTBFunnelResponse,
  type ConfigPerformanceResponse,
  type SpendStatsResponse,
  type EndpointEfficiencyResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import type { BuyerSeat } from "@/types/api";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];
const PRETARGETING_BOOTSTRAP_LIMIT_WARM = 300;
const PRETARGETING_BOOTSTRAP_LIMIT_COLD = 150;
const PRETARGETING_FULL_HYDRATION_IDLE_TIMEOUT_MS_WARM = 2000;
const PRETARGETING_FULL_HYDRATION_IDLE_TIMEOUT_MS_COLD = 5000;
const PRETARGETING_FULL_HYDRATION_FALLBACK_DELAY_MS_WARM = 750;
const PRETARGETING_FULL_HYDRATION_FALLBACK_DELAY_MS_COLD = 2000;
const DEFERRED_QUERY_REFRESH_IDLE_TIMEOUT_MS = 5000;
const DEFERRED_QUERY_REFRESH_DELAY_MS_SEEDED = 1500;
const INITIAL_VISIBLE_CONFIG_ROWS_WARM = 60;
const INITIAL_VISIBLE_CONFIG_ROWS_COLD = 40;
const CONFIG_ROWS_CHUNK_SIZE = 120;
const PRETARGETING_CONFIG_CACHE_PREFIX = "catscan:qps:pretargeting-configs:v1";
const PRETARGETING_CONFIG_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const PRETARGETING_CONFIG_CACHE_MAX_ROWS = 300;
const PRETARGETING_CONFIG_CACHE_FALLBACK_ROWS = 150;
const RTB_FUNNEL_CACHE_PREFIX = "catscan:qps:rtb-funnel:v1";
const RTB_FUNNEL_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const CONFIG_PERFORMANCE_CACHE_PREFIX = "catscan:qps:config-performance:v1";
const CONFIG_PERFORMANCE_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const SPEND_STATS_CACHE_PREFIX = "catscan:qps:spend-stats:v1";
const SPEND_STATS_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const ENDPOINT_EFFICIENCY_CACHE_PREFIX = "catscan:qps:endpoint-efficiency:v1";
const ENDPOINT_EFFICIENCY_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const ACTIVE_SEATS_CACHE_KEY = "catscan:qps:active-seats:v1";
const ACTIVE_SEATS_CACHE_MAX_AGE_MS = 15 * 60 * 1000;

interface PretargetingConfigCachePayload {
  cached_at_iso: string;
  rows: PretargetingConfigResponse[];
}

interface ConfigPerformanceCachePayload {
  cached_at_iso: string;
  data: ConfigPerformanceResponse;
}

interface RTBFunnelCachePayload {
  cached_at_iso: string;
  data: RTBFunnelResponse;
}

interface ActiveSeatsCachePayload {
  cached_at_iso: string;
  rows: BuyerSeat[];
}

interface SpendStatsCachePayload {
  cached_at_iso: string;
  data: SpendStatsResponse;
}

interface EndpointEfficiencyCachePayload {
  cached_at_iso: string;
  data: EndpointEfficiencyResponse;
}

function getRetryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 5000);
}

function shouldRetryAnalyticsQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 5) return false;
  if (!(error instanceof Error)) return true;
  const message = error.message.toLowerCase();
  if (
    message.includes("403")
    || message.includes("forbidden")
    || message.includes("unauthorized")
  ) {
    return false;
  }
  return true;
}

function normalizeDateString(value: string | null | undefined): string | null {
  if (!value) return null;
  return value.slice(0, 10);
}

function getPretargetingConfigCacheKey(buyerId: string): string {
  return `${PRETARGETING_CONFIG_CACHE_PREFIX}:${buyerId}`;
}

function getConfigPerformanceCacheKey(buyerId: string, days: number): string {
  return `${CONFIG_PERFORMANCE_CACHE_PREFIX}:${buyerId}:${days}`;
}

function getRtbFunnelCacheKey(buyerId: string, days: number): string {
  return `${RTB_FUNNEL_CACHE_PREFIX}:${buyerId}:${days}`;
}

function getSpendStatsCacheKey(
  buyerId: string,
  days: number,
  billingId: string | null
): string {
  return `${SPEND_STATS_CACHE_PREFIX}:${buyerId}:${days}:${billingId || "__all__"}`;
}

function getEndpointEfficiencyCacheKey(buyerId: string, days: number): string {
  return `${ENDPOINT_EFFICIENCY_CACHE_PREFIX}:${buyerId}:${days}`;
}

function readPretargetingConfigCache(buyerId: string | null): PretargetingConfigResponse[] | undefined {
  if (!buyerId || typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(getPretargetingConfigCacheKey(buyerId));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as PretargetingConfigCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > PRETARGETING_CONFIG_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(getPretargetingConfigCacheKey(buyerId));
      return undefined;
    }
    if (!Array.isArray(parsed.rows)) return undefined;
    return parsed.rows.slice(0, PRETARGETING_CONFIG_CACHE_MAX_ROWS);
  } catch {
    return undefined;
  }
}

function writePretargetingConfigCache(buyerId: string | null, rows: PretargetingConfigResponse[] | undefined): void {
  if (!buyerId || typeof window === "undefined" || !rows) return;
  const writeRows = (candidateRows: PretargetingConfigResponse[]): void => {
    const payload: PretargetingConfigCachePayload = {
      cached_at_iso: new Date().toISOString(),
      rows: candidateRows,
    };
    window.localStorage.setItem(getPretargetingConfigCacheKey(buyerId), JSON.stringify(payload));
  };

  const boundedRows = rows.slice(0, PRETARGETING_CONFIG_CACHE_MAX_ROWS);
  try {
    writeRows(boundedRows);
  } catch {
    try {
      writeRows(boundedRows.slice(0, PRETARGETING_CONFIG_CACHE_FALLBACK_ROWS));
    } catch {
      // Ignore localStorage failures (quota/private browsing).
    }
  }
}

function readConfigPerformanceCache(
  buyerId: string | null,
  days: number
): ConfigPerformanceResponse | undefined {
  if (!buyerId || typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(getConfigPerformanceCacheKey(buyerId, days));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as ConfigPerformanceCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > CONFIG_PERFORMANCE_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(getConfigPerformanceCacheKey(buyerId, days));
      return undefined;
    }
    if (!parsed.data || typeof parsed.data !== "object") return undefined;
    return parsed.data;
  } catch {
    return undefined;
  }
}

function writeConfigPerformanceCache(
  buyerId: string | null,
  days: number,
  data: ConfigPerformanceResponse | undefined
): void {
  if (!buyerId || typeof window === "undefined" || !data) return;
  try {
    const payload: ConfigPerformanceCachePayload = {
      cached_at_iso: new Date().toISOString(),
      data,
    };
    window.localStorage.setItem(getConfigPerformanceCacheKey(buyerId, days), JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures (quota/private browsing).
  }
}

function readRtbFunnelCache(
  buyerId: string | null,
  days: number,
): RTBFunnelResponse | undefined {
  if (!buyerId || typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(getRtbFunnelCacheKey(buyerId, days));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as RTBFunnelCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > RTB_FUNNEL_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(getRtbFunnelCacheKey(buyerId, days));
      return undefined;
    }
    if (!parsed.data || typeof parsed.data !== "object") return undefined;
    return parsed.data;
  } catch {
    return undefined;
  }
}

function writeRtbFunnelCache(
  buyerId: string | null,
  days: number,
  data: RTBFunnelResponse | undefined,
): void {
  if (!buyerId || typeof window === "undefined" || !data) return;
  try {
    const payload: RTBFunnelCachePayload = {
      cached_at_iso: new Date().toISOString(),
      data,
    };
    window.localStorage.setItem(getRtbFunnelCacheKey(buyerId, days), JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures (quota/private browsing).
  }
}

function readSpendStatsCache(
  buyerId: string | null,
  days: number,
  billingId: string | null
): SpendStatsResponse | undefined {
  if (!buyerId || typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(getSpendStatsCacheKey(buyerId, days, billingId));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as SpendStatsCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > SPEND_STATS_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(getSpendStatsCacheKey(buyerId, days, billingId));
      return undefined;
    }
    if (!parsed.data || typeof parsed.data !== "object") return undefined;
    return parsed.data;
  } catch {
    return undefined;
  }
}

function writeSpendStatsCache(
  buyerId: string | null,
  days: number,
  billingId: string | null,
  data: SpendStatsResponse | undefined
): void {
  if (!buyerId || typeof window === "undefined" || !data) return;
  try {
    const payload: SpendStatsCachePayload = {
      cached_at_iso: new Date().toISOString(),
      data,
    };
    window.localStorage.setItem(
      getSpendStatsCacheKey(buyerId, days, billingId),
      JSON.stringify(payload),
    );
  } catch {
    // Ignore localStorage failures (quota/private browsing).
  }
}

function readEndpointEfficiencyCache(
  buyerId: string | null,
  days: number
): EndpointEfficiencyResponse | undefined {
  if (!buyerId || typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(getEndpointEfficiencyCacheKey(buyerId, days));
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as EndpointEfficiencyCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > ENDPOINT_EFFICIENCY_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(getEndpointEfficiencyCacheKey(buyerId, days));
      return undefined;
    }
    if (!parsed.data || typeof parsed.data !== "object") return undefined;
    return parsed.data;
  } catch {
    return undefined;
  }
}

function writeEndpointEfficiencyCache(
  buyerId: string | null,
  days: number,
  data: EndpointEfficiencyResponse | undefined
): void {
  if (!buyerId || typeof window === "undefined" || !data) return;
  try {
    const payload: EndpointEfficiencyCachePayload = {
      cached_at_iso: new Date().toISOString(),
      data,
    };
    window.localStorage.setItem(getEndpointEfficiencyCacheKey(buyerId, days), JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures (quota/private browsing).
  }
}

function readActiveSeatsCache(): BuyerSeat[] | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const raw = window.localStorage.getItem(ACTIVE_SEATS_CACHE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as ActiveSeatsCachePayload;
    const cachedAtMs = Date.parse(parsed.cached_at_iso);
    if (!Number.isFinite(cachedAtMs)) return undefined;
    if ((Date.now() - cachedAtMs) > ACTIVE_SEATS_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(ACTIVE_SEATS_CACHE_KEY);
      return undefined;
    }
    if (!Array.isArray(parsed.rows)) return undefined;
    return parsed.rows;
  } catch {
    return undefined;
  }
}

function writeActiveSeatsCache(rows: BuyerSeat[] | undefined): void {
  if (typeof window === "undefined" || !rows) return;
  try {
    const payload: ActiveSeatsCachePayload = {
      cached_at_iso: new Date().toISOString(),
      rows,
    };
    window.localStorage.setItem(ACTIVE_SEATS_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures (quota/private browsing).
  }
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
  const loadCycleStartedAtRef = useRef<number>(Date.now());
  const perfMarkPrefixRef = useRef<string>(`catscan:qps:${loadCycleStartedAtRef.current}`);
  const firstTableRowMsRef = useRef<number | null>(null);
  const tableHydratedMsRef = useRef<number | null>(null);
  const startupApiLatencyMsRef = useRef<Record<string, number>>({});
  const qpsLoadMetricsPostedRef = useRef<boolean>(false);
  const pendingApiLatencyBufferRef = useRef<Record<string, number>>({});
  const pendingApiLatencyFlushTimerRef = useRef<number | null>(null);

  const setStartupApiLatency = useCallback((name: string, startedAtMs: number) => {
    const endedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    startupApiLatencyMsRef.current[name] = Math.round(Math.max(0, endedAtMs - startedAtMs));
  }, []);

  const writeQpsLoadMetricsSnapshot = useCallback((): QpsPageLoadMetricsSnapshot | null => {
    if (typeof window === "undefined") return null;
    const snapshot: QpsPageLoadMetricsSnapshot = {
      started_at_iso: new Date(loadCycleStartedAtRef.current).toISOString(),
      buyer_id: selectedBuyerId || null,
      days,
      time_to_first_table_row_ms: firstTableRowMsRef.current,
      time_to_table_hydrated_ms: tableHydratedMsRef.current,
      api_latency_ms: { ...startupApiLatencyMsRef.current },
    };
    window.__CATSCAN_QPS_LOAD_METRICS = snapshot;
    return snapshot;
  }, [days, selectedBuyerId]);

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
    pendingApiLatencyBufferRef.current[apiPath] = latencyMs;
    if (pendingApiLatencyFlushTimerRef.current !== null) return;
    pendingApiLatencyFlushTimerRef.current = window.setTimeout(() => {
      const buffered = { ...pendingApiLatencyBufferRef.current };
      pendingApiLatencyBufferRef.current = {};
      pendingApiLatencyFlushTimerRef.current = null;
      if (Object.keys(buffered).length === 0) return;
      postQpsLoadMetricPayload({
        page: "qps_home",
        buyer_id: selectedBuyerId || null,
        selected_days: days,
        api_latency_ms: buffered,
        sampled_at: new Date().toISOString(),
      });
    }, 1500);
  }, [days, postQpsLoadMetricPayload, selectedBuyerId]);

  useEffect(() => {
    return () => {
      if (pendingApiLatencyFlushTimerRef.current !== null) {
        window.clearTimeout(pendingApiLatencyFlushTimerRef.current);
        pendingApiLatencyFlushTimerRef.current = null;
      }
      const buffered = { ...pendingApiLatencyBufferRef.current };
      pendingApiLatencyBufferRef.current = {};
      if (Object.keys(buffered).length === 0) return;
      postQpsLoadMetricPayload({
        page: "qps_home",
        buyer_id: selectedBuyerId || null,
        selected_days: days,
        api_latency_ms: buffered,
        sampled_at: new Date().toISOString(),
      });
    };
  }, [days, postQpsLoadMetricPayload, selectedBuyerId]);

  // Fetch seats to auto-select first one if none selected
  const {
    data: seats,
    isLoading: seatsLoading,
    isError: seatsError,
    refetch: refetchSeats,
    isFetchedAfterMount: seatsFetchedAfterMount,
  } = useQuery({
    queryKey: ["seats"],
    queryFn: () => getSeats({ active_only: true }),
    initialData: () => readActiveSeatsCache(),
    initialDataUpdatedAt: () => 0,
    retry: 5,
    retryDelay: getRetryDelay,
    staleTime: 60_000,
    refetchOnMount: true,
  });

  useEffect(() => {
    if (!seatsFetchedAfterMount) return;
    writeActiveSeatsCache(seats);
  }, [seats, seatsFetchedAfterMount]);

  // Keep selected seat valid and deterministic once seats resolve.
  useEffect(() => {
    if (!seats || seats.length === 0) return;

    const hasSelectedSeat = !!selectedBuyerId && seats.some((seat) => seat.buyer_id === selectedBuyerId);
    if (!hasSelectedSeat) {
      setSelectedBuyerId(seats[0].buyer_id);
    }
  }, [selectedBuyerId, seats, setSelectedBuyerId]);

  const [expandedConfigId, setExpandedConfigId] = useState<string | null>(null);
  const [pretargetingBootstrapLimit, setPretargetingBootstrapLimit] = useState<number | null>(
    PRETARGETING_BOOTSTRAP_LIMIT_WARM
  );
  const loadMoreSentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setExpandedConfigId(null);
  }, [selectedBuyerId]);

  useEffect(() => {
    setPretargetingBootstrapLimit(PRETARGETING_BOOTSTRAP_LIMIT_WARM);
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
  const selectedBuyerKnownValid = !!selectedBuyerId && !!seats && seats.some((s) => s.buyer_id === selectedBuyerId);
  const seatReady = !!selectedBuyerId && (seatsLoading || selectedBuyerKnownValid);
  const pretargetingCacheSeed = useMemo(
    () => readPretargetingConfigCache(selectedBuyerId),
    [selectedBuyerId]
  );
  const hasPretargetingCacheSeed = Array.isArray(pretargetingCacheSeed)
    && pretargetingCacheSeed.length > 0;
  const pretargetingSeedSummaryOnly = hasPretargetingCacheSeed && pretargetingCacheSeed.every(
    (row) =>
      row.included_formats === null
      && row.included_platforms === null
      && row.included_sizes === null
  );
  const useSummaryBootstrap = pretargetingBootstrapLimit !== null
    && (!hasPretargetingCacheSeed || pretargetingSeedSummaryOnly);
  const pretargetingRequestLimit = pretargetingBootstrapLimit === null
    ? null
    : (useSummaryBootstrap
      ? PRETARGETING_BOOTSTRAP_LIMIT_COLD
      : pretargetingBootstrapLimit);

  const fetchMeasuredPretargetingConfigs = useCallback(async () => {
    const shouldMeasureStartup = pretargetingRequestLimit !== null;
    const startedAtMs = typeof window !== "undefined" && window.performance
      ? window.performance.now()
      : Date.now();
    try {
      return await getPretargetingConfigs({
        buyer_id: selectedBuyerId || undefined,
        limit: pretargetingRequestLimit ?? undefined,
        summary_only: useSummaryBootstrap,
      });
    } finally {
      if (shouldMeasureStartup) {
        setStartupApiLatency("/settings/pretargeting", startedAtMs);
        writeQpsLoadMetricsSnapshot();
      }
    }
  }, [
    pretargetingRequestLimit,
    selectedBuyerId,
    setStartupApiLatency,
    useSummaryBootstrap,
    writeQpsLoadMetricsSnapshot,
  ]);

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

  const rtbFunnelCacheSeed = useMemo(
    () => readRtbFunnelCache(selectedBuyerId, days),
    [days, selectedBuyerId]
  );

  // Fetch RTB funnel data from CSV files
  const {
    data: rtbFunnel,
    isLoading: funnelLoading,
    refetch: refetchFunnel,
    isFetchedAfterMount: rtbFunnelFetchedAfterMount,
  } = useQuery({
    queryKey: ["rtb-funnel", days, selectedBuyerId],
    queryFn: () => getRTBFunnel(days, selectedBuyerId || undefined),
    initialData: () => rtbFunnelCacheSeed,
    enabled: false,
  });

  useEffect(() => {
    if (!rtbFunnelFetchedAfterMount) return;
    writeRtbFunnelCache(selectedBuyerId, days, rtbFunnel);
  }, [days, rtbFunnel, rtbFunnelFetchedAfterMount, selectedBuyerId]);

  // Fetch spend stats for CPM display (filtered by expanded config if selected)
  const {
    data: spendStats,
    refetch: refetchSpend,
    isFetchedAfterMount: spendStatsFetchedAfterMount,
  } = useQuery({
    queryKey: ["spend-stats", days, selectedBuyerId, expandedConfigId],
    queryFn: () => getSpendStats(days, expandedConfigId || undefined),
    initialData: () => readSpendStatsCache(selectedBuyerId, days, expandedConfigId),
    enabled: false,
  });

  useEffect(() => {
    if (!spendStatsFetchedAfterMount) return;
    writeSpendStatsCache(selectedBuyerId, days, expandedConfigId, spendStats);
  }, [days, expandedConfigId, selectedBuyerId, spendStats, spendStatsFetchedAfterMount]);

  // Fetch pretargeting configs
  const {
    data: pretargetingConfigs,
    isLoading: configsLoading,
    refetch: refetchConfigs,
    isFetchedAfterMount: configsFetchedAfterMount,
  } = useQuery({
    queryKey: [
      "pretargeting-configs",
      selectedBuyerId,
      pretargetingRequestLimit ?? "all",
      useSummaryBootstrap ? "summary" : "full",
    ],
    queryFn: fetchMeasuredPretargetingConfigs,
    enabled: seatReady,
    initialData: () => pretargetingCacheSeed,
    placeholderData: (previousData) => previousData,
    retry: shouldRetryAnalyticsQuery,
    retryDelay: getRetryDelay,
    retryOnMount: true,
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
    refetchInterval: (query) => {
      if (!seatReady) return false;
      if (Date.now() - loadCycleStartedAtRef.current > 120_000) return false;
      if (query.state.status === "error") return 5000;
      const rows = query.state.data as PretargetingConfigResponse[] | undefined;
      if (Array.isArray(rows) && rows.length === 0) return 8000;
      return false;
    },
  });

  useEffect(() => {
    if (!seatReady) return;
    if (pretargetingBootstrapLimit === null) return;
    if (!Array.isArray(pretargetingConfigs)) return;
    if (!useSummaryBootstrap && pretargetingConfigs.length < (pretargetingRequestLimit ?? 0)) return;
    const hydrationIdleTimeoutMs = useSummaryBootstrap
      ? PRETARGETING_FULL_HYDRATION_IDLE_TIMEOUT_MS_COLD
      : PRETARGETING_FULL_HYDRATION_IDLE_TIMEOUT_MS_WARM;
    const hydrationFallbackDelayMs = useSummaryBootstrap
      ? PRETARGETING_FULL_HYDRATION_FALLBACK_DELAY_MS_COLD
      : PRETARGETING_FULL_HYDRATION_FALLBACK_DELAY_MS_WARM;
    const browserWindow = window as Window & {
      requestIdleCallback?: (callback: IdleRequestCallback, opts?: IdleRequestOptions) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (
      typeof browserWindow.requestIdleCallback === "function"
      && typeof browserWindow.cancelIdleCallback === "function"
    ) {
      const idleId = browserWindow.requestIdleCallback(
        () => setPretargetingBootstrapLimit(null),
        { timeout: hydrationIdleTimeoutMs }
      );
      return () => browserWindow.cancelIdleCallback?.(idleId);
    }
    const timer = setTimeout(() => {
      setPretargetingBootstrapLimit(null);
    }, hydrationFallbackDelayMs);
    return () => clearTimeout(timer);
  }, [
    pretargetingBootstrapLimit,
    pretargetingConfigs,
    pretargetingRequestLimit,
    seatReady,
    useSummaryBootstrap,
  ]);

  useEffect(() => {
    if (!configsFetchedAfterMount) return;
    writePretargetingConfigCache(selectedBuyerId, pretargetingConfigs);
  }, [configsFetchedAfterMount, pretargetingConfigs, selectedBuyerId]);

  const hasPretargetingRows = Array.isArray(pretargetingConfigs);
  const configPerformanceEnabled = seatReady && (!useSummaryBootstrap || hasPretargetingRows);
  const configPerformanceCacheSeed = useMemo(
    () => readConfigPerformanceCache(selectedBuyerId, days),
    [days, selectedBuyerId]
  );

  // Fetch config-level performance data (filtered by selected buyer)
  const {
    data: configPerformance,
    isLoading: configPerformanceLoading,
    refetch: refetchConfigPerf,
    isError: configPerformanceError,
    isFetching: configPerformanceFetching,
    isFetchedAfterMount: configPerformanceFetchedAfterMount,
  } = useQuery({
    queryKey: ["rtb-funnel-configs", days, selectedBuyerId],
    queryFn: fetchMeasuredConfigPerformance,
    enabled: configPerformanceEnabled,
    initialData: () => configPerformanceCacheSeed,
    retry: shouldRetryAnalyticsQuery,
    retryDelay: getRetryDelay,
    retryOnMount: !configPerformanceCacheSeed,
    refetchOnMount: !configPerformanceCacheSeed,
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
    refetchInterval: (query) => {
      if (!configPerformanceEnabled) return false;
      if (Date.now() - loadCycleStartedAtRef.current > 120_000) return false;
      if (query.state.status === "error") return 5000;
      return false;
    },
  });

  useEffect(() => {
    if (!configPerformanceEnabled) return;
    const hasSeed = Array.isArray(configPerformanceCacheSeed?.configs)
      && configPerformanceCacheSeed.configs.length > 0;
    if (!hasSeed) return;

    const browserWindow = window as Window & {
      requestIdleCallback?: (callback: IdleRequestCallback, opts?: IdleRequestOptions) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (
      typeof browserWindow.requestIdleCallback === "function"
      && typeof browserWindow.cancelIdleCallback === "function"
    ) {
      const idleId = browserWindow.requestIdleCallback(
        () => void refetchConfigPerf(),
        { timeout: DEFERRED_QUERY_REFRESH_IDLE_TIMEOUT_MS }
      );
      return () => browserWindow.cancelIdleCallback?.(idleId);
    }
    const timer = setTimeout(() => {
      void refetchConfigPerf();
    }, DEFERRED_QUERY_REFRESH_DELAY_MS_SEEDED);
    return () => clearTimeout(timer);
  }, [
    configPerformanceCacheSeed,
    configPerformanceEnabled,
    days,
    refetchConfigPerf,
    selectedBuyerId,
  ]);

  useEffect(() => {
    if (!configPerformanceFetchedAfterMount) return;
    writeConfigPerformanceCache(selectedBuyerId, days, configPerformance);
  }, [configPerformance, configPerformanceFetchedAfterMount, days, selectedBuyerId]);

  const endpointEfficiencyCacheSeed = useMemo(
    () => readEndpointEfficiencyCache(selectedBuyerId, days),
    [days, selectedBuyerId]
  );

  const {
    data: endpointEfficiency,
    isLoading: endpointEfficiencyLoading,
    refetch: refetchEndpointEfficiency,
    isFetchedAfterMount: endpointEfficiencyFetchedAfterMount,
  } = useQuery({
    queryKey: ["endpoint-efficiency", days, selectedBuyerId],
    queryFn: fetchMeasuredEndpointEfficiency,
    initialData: () => endpointEfficiencyCacheSeed,
    enabled: false,
  });

  useEffect(() => {
    if (!endpointEfficiencyFetchedAfterMount) return;
    writeEndpointEfficiencyCache(selectedBuyerId, days, endpointEfficiency);
  }, [days, endpointEfficiency, endpointEfficiencyFetchedAfterMount, selectedBuyerId]);

  const handleRefresh = () => {
    refetchFunnel();
    refetchSpend();
    refetchConfigs();
    refetchConfigPerf();
    refetchEndpointEfficiency();
  };

  // Build a map of billing_id to performance data from config performance API
  const hasConfigPerformanceSeed = Array.isArray(configPerformance?.configs) && configPerformance.configs.length > 0;
  const configMetricsDelayed = Boolean(
    configPerformanceError
    || ((!hasConfigPerformanceSeed) && (configPerformanceLoading || configPerformanceFetching))
  );
  const configFallbackApplied = configPerformance?.fallback_applied === true;
  const configRequestedDays = configPerformance?.requested_days ?? days;
  const configEffectiveDays = configPerformance?.effective_days ?? days;
  const configPerformanceMap = useMemo(() => {
    const nextMap = new Map<string, { reached: number; impressions: number; win_rate: number; waste_rate: number }>();
    if (configPerformance?.configs) {
      for (const cfg of configPerformance.configs) {
        nextMap.set(cfg.billing_id, {
          reached: cfg.reached || 0,
          impressions: cfg.impressions || 0,
          win_rate: cfg.win_rate_pct || 0,
          waste_rate: cfg.waste_pct || 0,
        });
      }
    }
    return nextMap;
  }, [configPerformance]);

  const unsortedConfigs = useMemo(
    () =>
      (pretargetingConfigs || []).map((config) =>
        transformConfigToProps(
          config,
          configPerformanceMap.get(config.billing_id || config.config_id),
          configMetricsDelayed
        )
      ),
    [configMetricsDelayed, configPerformanceMap, pretargetingConfigs]
  );

  const displayConfigs = useMemo(() => {
    return [...unsortedConfigs].sort((a, b) => {
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
  }, [sortColumn, sortDirection, unsortedConfigs]);
  const initialVisibleConfigRows = useSummaryBootstrap
    ? INITIAL_VISIBLE_CONFIG_ROWS_COLD
    : INITIAL_VISIBLE_CONFIG_ROWS_WARM;
  const [visibleConfigCount, setVisibleConfigCount] = useState<number>(initialVisibleConfigRows);
  const visibleConfigs = displayConfigs.slice(0, Math.min(visibleConfigCount, displayConfigs.length));

  const activeConfigsCount = displayConfigs.filter(c => c.state === 'ACTIVE').length;
  const hasTableRows = !configsLoading && displayConfigs.length > 0;
  const tableDataSettled = !configsLoading
    && !configPerformanceLoading
    && (!configPerformanceFetching || hasConfigPerformanceSeed);
  const tableHydrated = hasTableRows && tableDataSettled;
  const deferredStartupQueriesReady = seatReady && tableDataSettled;

  useEffect(() => {
    const totalRows = displayConfigs.length;
    if (totalRows <= initialVisibleConfigRows) {
      setVisibleConfigCount(totalRows);
      return;
    }
    setVisibleConfigCount(initialVisibleConfigRows);
  }, [displayConfigs.length, days, initialVisibleConfigRows, selectedBuyerId, sortColumn, sortDirection]);

  useEffect(() => {
    if (!expandedConfigId) return;
    const expandedIndex = displayConfigs.findIndex((row) => row.billing_id === expandedConfigId);
    if (expandedIndex < 0 || expandedIndex < visibleConfigCount) return;
    const nextVisible = Math.min(displayConfigs.length, expandedIndex + CONFIG_ROWS_CHUNK_SIZE);
    setVisibleConfigCount(nextVisible);
  }, [displayConfigs, expandedConfigId, visibleConfigCount]);

  useEffect(() => {
    const sentinel = loadMoreSentinelRef.current;
    if (!sentinel) return;
    if (visibleConfigCount >= displayConfigs.length) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        setVisibleConfigCount((prev) =>
          Math.min(displayConfigs.length, prev + CONFIG_ROWS_CHUNK_SIZE)
        );
      },
      { root: null, rootMargin: "400px 0px", threshold: 0 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [displayConfigs.length, visibleConfigCount]);

  useEffect(() => {
    if (!deferredStartupQueriesReady) return;
    refetchSpend();
  }, [deferredStartupQueriesReady, refetchSpend, selectedBuyerId, days, expandedConfigId]);

  useEffect(() => {
    if (!deferredStartupQueriesReady) return;
    if (!rtbFunnelCacheSeed) {
      refetchFunnel();
      return;
    }
    const browserWindow = window as Window & {
      requestIdleCallback?: (callback: IdleRequestCallback, opts?: IdleRequestOptions) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (
      typeof browserWindow.requestIdleCallback === "function"
      && typeof browserWindow.cancelIdleCallback === "function"
    ) {
      const idleId = browserWindow.requestIdleCallback(
        () => void refetchFunnel(),
        { timeout: DEFERRED_QUERY_REFRESH_IDLE_TIMEOUT_MS }
      );
      return () => browserWindow.cancelIdleCallback?.(idleId);
    }
    const timer = setTimeout(() => {
      void refetchFunnel();
    }, DEFERRED_QUERY_REFRESH_DELAY_MS_SEEDED);
    return () => clearTimeout(timer);
  }, [days, deferredStartupQueriesReady, refetchFunnel, rtbFunnelCacheSeed, selectedBuyerId]);

  useEffect(() => {
    if (!deferredStartupQueriesReady) return;
    if (!endpointEfficiencyCacheSeed) {
      refetchEndpointEfficiency();
      return;
    }
    const browserWindow = window as Window & {
      requestIdleCallback?: (callback: IdleRequestCallback, opts?: IdleRequestOptions) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (
      typeof browserWindow.requestIdleCallback === "function"
      && typeof browserWindow.cancelIdleCallback === "function"
    ) {
      const idleId = browserWindow.requestIdleCallback(
        () => void refetchEndpointEfficiency(),
        { timeout: DEFERRED_QUERY_REFRESH_IDLE_TIMEOUT_MS }
      );
      return () => browserWindow.cancelIdleCallback?.(idleId);
    }
    const timer = setTimeout(() => {
      void refetchEndpointEfficiency();
    }, DEFERRED_QUERY_REFRESH_DELAY_MS_SEEDED);
    return () => clearTimeout(timer);
  }, [
    days,
    deferredStartupQueriesReady,
    endpointEfficiencyCacheSeed,
    refetchEndpointEfficiency,
    selectedBuyerId,
  ]);

  useEffect(() => {
    const startedAtMs = Date.now();
    loadCycleStartedAtRef.current = startedAtMs;
    perfMarkPrefixRef.current = `catscan:qps:${startedAtMs}`;
    firstTableRowMsRef.current = null;
    tableHydratedMsRef.current = null;
    startupApiLatencyMsRef.current = {};
    qpsLoadMetricsPostedRef.current = false;
    pendingApiLatencyBufferRef.current = {};
    if (pendingApiLatencyFlushTimerRef.current !== null) {
      window.clearTimeout(pendingApiLatencyFlushTimerRef.current);
      pendingApiLatencyFlushTimerRef.current = null;
    }
    if (typeof window !== "undefined" && window.performance?.mark) {
      const startMark = `${perfMarkPrefixRef.current}:navigation-start`;
      window.performance.mark(startMark);
    }
    writeQpsLoadMetricsSnapshot();
  }, [days, selectedBuyerId, writeQpsLoadMetricsSnapshot]);

  useEffect(() => {
    if (!hasTableRows || firstTableRowMsRef.current !== null) return;
    const elapsedMs = Math.max(0, Date.now() - loadCycleStartedAtRef.current);
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
  }, [hasTableRows, writeQpsLoadMetricsSnapshot]);

  useEffect(() => {
    if (!tableHydrated || tableHydratedMsRef.current !== null) return;
    const elapsedMs = Math.max(0, Date.now() - loadCycleStartedAtRef.current);
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
  }, [submitQpsLoadMetrics, tableHydrated, writeQpsLoadMetricsSnapshot]);

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
        enabled={deferredStartupQueriesReady}
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
            {visibleConfigs.map(config => (
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
            {visibleConfigCount < displayConfigs.length && (
              <div
                ref={loadMoreSentinelRef}
                className="rounded border border-dashed border-gray-200 bg-gray-50 px-3 py-2 text-center text-xs text-gray-500"
              >
                Showing {visibleConfigCount.toLocaleString()} of {displayConfigs.length.toLocaleString()} configs
              </div>
            )}
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
