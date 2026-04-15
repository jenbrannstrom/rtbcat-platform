"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, HelpCircle, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { getCreativeLanguageFlagCoverage, refreshCreativeLanguageFlagCoverage } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { splitBuyerPath, toBuyerScopedPath } from "@/lib/buyer-routes";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 100;
const INITIAL_SCAN_LIMIT = 200;
const BULK_REFRESH_LIMIT = 500;
const AUTO_REFRESH_WINDOW_MS = 60_000;

const STATUS_CONFIG = {
  green: {
    badge: "bg-green-100 text-green-700",
    icon: CheckCircle2,
  },
  orange: {
    badge: "bg-amber-100 text-amber-700",
    icon: HelpCircle,
  },
  red: {
    badge: "bg-red-100 text-red-700",
    icon: ShieldAlert,
  },
} as const;

function StatusBadge({
  status,
  reason,
  label,
}: {
  status: "green" | "orange" | "red" | string;
  reason: string;
  label: string;
}) {
  const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.orange;
  const Icon = config.icon;

  return (
    <div className="space-y-1">
      <span className={cn("inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium", config.badge)}>
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <div className="max-w-md text-xs text-gray-600">{reason}</div>
    </div>
  );
}

export default function LanguageFlagCoveragePage() {
  const params = useParams<{ buyerId?: string }>();
  const pathname = usePathname();
  const { selectedBuyerId } = useAccount();
  const { t, language } = useTranslation();
  const { buyerIdInPath } = splitBuyerPath(pathname || "/");
  const buyerIdFromParams = typeof params?.buyerId === "string" ? params.buyerId : null;
  const effectiveBuyerId = buyerIdFromParams ?? buyerIdInPath ?? selectedBuyerId ?? null;
  const [search, setSearch] = useState("");
  const [languageState, setLanguageState] = useState<"all" | "green" | "orange" | "red">("all");
  const [geoState, setGeoState] = useState<"all" | "green" | "orange" | "red">("all");
  const [pageIndex, setPageIndex] = useState(0);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [isAutoRefreshing, setIsAutoRefreshing] = useState(false);

  useEffect(() => {
    setPageIndex(0);
  }, [effectiveBuyerId]);

  useEffect(() => {
    if (!isAutoRefreshing) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setIsAutoRefreshing(false);
    }, AUTO_REFRESH_WINDOW_MS);

    return () => window.clearTimeout(timeoutId);
  }, [isAutoRefreshing]);

  const offset = pageIndex * PAGE_SIZE;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [
      "creative-language-flag-coverage",
      effectiveBuyerId,
      search,
      languageState,
      geoState,
      offset,
    ],
    enabled: Boolean(effectiveBuyerId),
    retry: false,
    refetchInterval: isAutoRefreshing ? 5_000 : false,
    queryFn: () =>
      getCreativeLanguageFlagCoverage({
        buyer_id: effectiveBuyerId ?? undefined,
        search: search.trim() || undefined,
        language_state: languageState,
        geo_state: geoState,
        limit: PAGE_SIZE,
        offset,
        scan_limit: INITIAL_SCAN_LIMIT,
      }),
    staleTime: 30_000,
  });

  const refreshAllMutation = useMutation({
    mutationFn: () =>
      refreshCreativeLanguageFlagCoverage({
        buyer_id: effectiveBuyerId ?? undefined,
        search: search.trim() || undefined,
        refresh_limit: BULK_REFRESH_LIMIT,
        force: true,
      }),
    onSuccess: async (result) => {
      const countLabel = String(result.queued_creatives.toLocaleString(language));
      const baseMessage = result.queued_creatives > 0
        ? t.creatives.languageFlagsRefreshQueuedMessage.replace("{count}", countLabel)
        : t.creatives.languageFlagsRefreshNoMatchMessage;
      setNotice({
        tone: "success",
        message:
          result.queued_creatives > 0
            ? `${baseMessage} ${t.creatives.languageFlagsRefreshQueuedSuffix}`
            : baseMessage,
      });
      setIsAutoRefreshing(result.queued_creatives > 0);
      await refetch();
    },
    onError: (mutationError) => {
      setNotice({
        tone: "error",
        message:
          mutationError instanceof Error
            ? mutationError.message
            : t.creatives.languageFlagsRefreshFailed,
      });
    },
  });

  const rows = data?.rows ?? [];
  const summary = data?.summary;
  const total = data?.total ?? 0;
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = offset + rows.length;
  const hasMore = offset + rows.length < total;

  const flaggedPct = useMemo(() => {
    if (!summary) return 0;
    const denominator = summary.geo_green + summary.geo_orange + summary.geo_red;
    if (denominator === 0) return 0;
    return ((summary.geo_orange + summary.geo_red) / denominator) * 100;
  }, [summary]);

  if (!effectiveBuyerId) {
    return (
      <ErrorPage
        message={t.creatives.languageFlagsSelectBuyer}
      />
    );
  }

  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={error instanceof Error ? error.message : t.creatives.languageFlagsFailedToLoad}
        onRetry={() => refetch()}
      />
    );
  }

  const statusLabels = {
    green: t.creatives.statusGreen,
    orange: t.creatives.statusOrange,
    red: t.creatives.statusRed,
  } as const;

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t.creatives.languageFlagsTitle}</h1>
          <p className="text-sm text-gray-600">
            {t.creatives.languageFlagsDescription}
          </p>
        </div>
        <Link
          href={toBuyerScopedPath("/creatives", effectiveBuyerId)}
          className="text-sm text-primary-700 hover:text-primary-800"
        >
          {t.creatives.backToCreatives}
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">{t.creatives.languageFlagsLangRed}</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">{summary?.language_red ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">{t.creatives.languageFlagsLangOrange}</div>
          <div className="mt-1 text-2xl font-semibold text-amber-700">{summary?.language_orange ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">{t.creatives.languageFlagsGeoRed}</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">{summary?.geo_red ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">{t.creatives.languageFlagsFlagged}</div>
          <div className="mt-1 text-2xl font-semibold text-gray-900">{flaggedPct.toFixed(1)}%</div>
        </div>
      </div>

      {notice && (
        <div
          className={cn(
            "rounded-lg border px-3 py-2 text-sm",
            notice.tone === "success"
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800"
          )}
        >
          {notice.message}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="block w-full max-w-md">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500">
            {t.creatives.languageFlagsSearchLabel}
          </span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(event) => {
                setPageIndex(0);
                setSearch(event.target.value);
              }}
              placeholder={t.creatives.languageFlagsSearchPlaceholder}
              className="input w-full py-1.5 pl-9 pr-3 text-sm"
            />
          </div>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500">
            {t.creatives.languageFlagsLanguageStatus}
          </span>
          <select
            value={languageState}
            onChange={(event) => {
              setPageIndex(0);
              setLanguageState(event.target.value as "all" | "green" | "orange" | "red");
            }}
            className="input py-1.5 pr-8 text-sm"
          >
            <option value="all">{t.creatives.languageFlagsAllLanguageResults}</option>
            <option value="red">{t.creatives.languageFlagsLanguageRed}</option>
            <option value="orange">{t.creatives.languageFlagsLanguageOrange}</option>
            <option value="green">{t.creatives.languageFlagsLanguageGreen}</option>
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500">
            {t.creatives.languageFlagsGeoStatus}
          </span>
          <select
            value={geoState}
            onChange={(event) => {
              setPageIndex(0);
              setGeoState(event.target.value as "all" | "green" | "orange" | "red");
            }}
            className="input py-1.5 pr-8 text-sm"
          >
            <option value="all">{t.creatives.languageFlagsAllGeoResults}</option>
            <option value="red">{t.creatives.languageFlagsGeoRedOption}</option>
            <option value="orange">{t.creatives.languageFlagsGeoOrangeOption}</option>
            <option value="green">{t.creatives.languageFlagsGeoGreenOption}</option>
          </select>
        </label>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
            {t.common.refresh}
          </span>
          <button
            type="button"
            onClick={() => refreshAllMutation.mutate()}
            disabled={refreshAllMutation.isPending}
            className="inline-flex items-center gap-2 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className={cn("h-4 w-4", refreshAllMutation.isPending && "animate-spin")} />
            {t.creatives.languageFlagsRefreshAll}
          </button>
        </div>
      </div>

      <div className="text-xs text-gray-500">
        {t.creatives.languageFlagsRefreshHint.replace(
          "{count}",
          BULK_REFRESH_LIMIT.toLocaleString(language)
        )}
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">{t.creatives.creativeId}</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">{t.creatives.languageFlagsTableLangMismatch}</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">{t.creatives.languageFlagsTableGeoLinguistic}</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">{t.creatives.languageFlagsTableServing}</th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">{t.creatives.languageFlagsTableSpend30d}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr key={row.creative_id}>
                  <td className="px-3 py-2 align-top">
                    <div className="font-mono text-xs text-gray-900">{row.creative_id}</div>
                    <div className="max-w-sm truncate text-xs text-gray-600" title={row.creative_name}>
                      {row.creative_name}
                    </div>
                    <div className="mt-1 text-[11px] text-gray-400">
                      {row.format || "-"} · {row.approval_status || "-"}
                    </div>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <StatusBadge
                      status={row.language_flag_status}
                      reason={row.language_flag_reason}
                      label={statusLabels[row.language_flag_status as keyof typeof statusLabels] || statusLabels.orange}
                    />
                    {(row.effective_language_code || row.language_flag_source) && (
                      <div className="mt-1 text-[11px] text-gray-400">
                        {(row.language_flag_source || t.creatives.languageFlagsSourceUnknown).toUpperCase()} · {(row.effective_language_code || "?").toUpperCase()}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 align-top">
                    <StatusBadge
                      status={row.geo_linguistic_status}
                      reason={row.geo_linguistic_reason}
                      label={statusLabels[row.geo_linguistic_status as keyof typeof statusLabels] || statusLabels.orange}
                    />
                    {row.detected_currencies.length > 0 && (
                      <div className="mt-1 text-[11px] text-gray-400">
                        {t.creatives.languageFlagsCurrencyLabel}: {row.detected_currencies.join(", ")}
                      </div>
                    )}
                    <div className="mt-1 text-[11px] text-gray-400">
                      {row.geo_linguistic_completed_at
                        ? t.creatives.languageFlagsUpdated.replace(
                            "{date}",
                            new Date(row.geo_linguistic_completed_at).toLocaleDateString(language)
                          )
                        : t.creatives.languageFlagsNoAiRefreshYet}
                    </div>
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-gray-700">
                    {row.serving_countries.length > 0 ? row.serving_countries.join(", ") : "-"}
                  </td>
                  <td className="px-3 py-2 align-top text-right text-xs">
                    {row.spend_30d_micros > 0 ? (
                      <span className="font-medium text-gray-900">
                        ${(row.spend_30d_micros / 1_000_000).toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-sm text-gray-500">
                    {t.creatives.languageFlagsNoResults}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>
          {t.creatives.languageFlagsShowingOf
            .replace("{start}", String(pageStart))
            .replace("{end}", String(pageEnd))
            .replace("{total}", String(total))}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPageIndex((value) => Math.max(value - 1, 0))}
            disabled={pageIndex === 0}
            className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t.common.previous}
          </button>
          <button
            type="button"
            onClick={() => setPageIndex((value) => value + 1)}
            disabled={!hasMore}
            className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t.common.next}
          </button>
        </div>
      </div>
    </div>
  );
}
