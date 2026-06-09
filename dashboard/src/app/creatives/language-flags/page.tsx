"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, HelpCircle, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useParams, usePathname } from "next/navigation";
import { CreativeThumb } from "@/components/creative-thumb";
import { ErrorPage } from "@/components/error";
import { LoadingPage } from "@/components/loading";
import { PreviewModal } from "@/components/preview-modal";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { getCreativeLanguageFlagCoverage, refreshCreativeLanguageFlagCoverage } from "@/lib/api";
import { splitBuyerPath, toBuyerScopedPath } from "@/lib/buyer-routes";
import {
  buildLanguageFlagHeadline,
  getLanguageFlagSeverity,
  type LanguageFlagSeverity,
} from "@/lib/language-flag-headline";
import { cn, getFormatLabel } from "@/lib/utils";
import type { Creative, CreativeLanguageFlagCoverageRow } from "@/types/api";

const PAGE_SIZE = 100;
const EXPORT_PAGE_SIZE = 1000;
const INITIAL_SCAN_LIMIT = 3000;
const BULK_REFRESH_LIMIT = 500;
const AUTO_REFRESH_WINDOW_MS = 60_000;

const SEVERITY_CONFIG: Record<LanguageFlagSeverity, {
  dot: string;
  badge: string;
  Icon: typeof ShieldAlert;
}> = {
  confirmed: {
    dot: "bg-red-500",
    badge: "bg-red-100 text-red-700",
    Icon: ShieldAlert,
  },
  review: {
    dot: "bg-amber-500",
    badge: "bg-amber-100 text-amber-700",
    Icon: HelpCircle,
  },
  ok: {
    dot: "bg-green-500",
    badge: "bg-green-100 text-green-700",
    Icon: CheckCircle2,
  },
};

function formatMoney(micros: number | null | undefined, language: string, compact = false): string {
  if (!micros || micros <= 0) return compact ? "$0" : "-";
  const value = micros / 1_000_000;
  return new Intl.NumberFormat(language, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: compact || value >= 100 ? 0 : 2,
    notation: compact ? "compact" : "standard",
  }).format(value);
}

function rowFootline(row: CreativeLanguageFlagCoverageRow): string {
  const parts = [
    `#${row.creative_id}`,
    row.creative_name ? `"${row.creative_name}"` : null,
    row.format ? getFormatLabel(row.format) : null,
    row.approval_status || null,
  ].filter(Boolean);
  return parts.join(" · ");
}

function isRowRefreshable(row: CreativeLanguageFlagCoverageRow): boolean {
  return row.geo_linguistic_status === "orange" || !row.geo_linguistic_completed_at;
}

function csvCell(value: string | number | boolean | null | undefined): string {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function csvLine(values: Array<string | number | boolean | null | undefined>): string {
  return values.map(csvCell).join(",");
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
  const [severity, setSeverity] = useState<"all" | LanguageFlagSeverity>("all");
  const [pageIndex, setPageIndex] = useState(0);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [isAutoRefreshing, setIsAutoRefreshing] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<{
    creativeId: string;
    creative?: Creative | null;
  } | null>(null);
  const [refreshingCreativeId, setRefreshingCreativeId] = useState<string | null>(null);
  const [isExportingCsv, setIsExportingCsv] = useState(false);

  useEffect(() => {
    setPageIndex(0);
  }, [effectiveBuyerId]);

  useEffect(() => {
    if (!isAutoRefreshing) return;
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
      severity,
      offset,
    ],
    enabled: Boolean(effectiveBuyerId),
    retry: false,
    refetchInterval: isAutoRefreshing ? 5_000 : false,
    queryFn: () =>
      getCreativeLanguageFlagCoverage({
        buyer_id: effectiveBuyerId ?? undefined,
        search: search.trim() || undefined,
        severity,
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

  const refreshRowMutation = useMutation({
    mutationFn: (creativeId: string) => {
      setRefreshingCreativeId(creativeId);
      return refreshCreativeLanguageFlagCoverage({
        buyer_id: effectiveBuyerId ?? undefined,
        search: creativeId,
        refresh_limit: 1,
        force: true,
      });
    },
    onSuccess: async () => {
      setIsAutoRefreshing(true);
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
    onSettled: () => setRefreshingCreativeId(null),
  });

  const rows = data?.rows ?? [];
  const summary = data?.summary;
  const total = data?.total ?? 0;
  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = offset + rows.length;
  const hasMore = offset + rows.length < total;

  const riskCount = (summary?.count_confirmed ?? 0) + (summary?.count_review ?? 0);
  const riskFigure = t.creatives.languageFlagsRiskFigure
    .replace("{amount}", formatMoney(summary?.spend_at_risk_micros ?? 0, language))
    .replace("{count}", riskCount.toLocaleString(language));

  const segments = useMemo(() => [
    {
      key: "confirmed" as const,
      label: t.creatives.languageFlagsSeverityConfirmed,
      count: summary?.count_confirmed ?? 0,
      spend: summary?.spend_confirmed_micros ?? 0,
    },
    {
      key: "review" as const,
      label: t.creatives.languageFlagsSeverityReview,
      count: summary?.count_review ?? 0,
      spend: summary?.spend_review_micros ?? 0,
    },
    {
      key: "ok" as const,
      label: t.creatives.languageFlagsSeverityOk,
      count: summary?.count_ok ?? 0,
      spend: 0,
    },
  ], [summary, t.creatives]);

  const downloadCsv = async () => {
    if (!effectiveBuyerId || isExportingCsv) return;
    setIsExportingCsv(true);
    try {
      const exportedRows: CreativeLanguageFlagCoverageRow[] = [];
      let nextOffset = 0;
      let expectedTotal: number | null = null;

      while (expectedTotal === null || exportedRows.length < expectedTotal) {
        const response = await getCreativeLanguageFlagCoverage({
          buyer_id: effectiveBuyerId,
          search: search.trim() || undefined,
          severity,
          limit: EXPORT_PAGE_SIZE,
          offset: nextOffset,
          scan_limit: INITIAL_SCAN_LIMIT,
        });

        expectedTotal = response.total;
        exportedRows.push(...response.rows);
        if (response.rows.length === 0) break;
        nextOffset += response.rows.length;
      }

      const header = csvLine([
        "creative_id",
        "creative_name",
        "severity",
        "headline",
        "flag_reason",
        "language_flag_status",
        "language_flag_reason",
        "geo_linguistic_status",
        "geo_linguistic_reason",
        "currency_flag_status",
        "currency_flag_reason",
        "serving_countries",
        "detected_currencies",
        "effective_language_code",
        "detected_language",
        "format",
        "approval_status",
        "spend_30d_micros",
        "impressions_30d",
        "last_active_date",
      ]);
      const body = exportedRows.map((row) => {
        const headline = buildLanguageFlagHeadline(row, t.creatives, language);
        return csvLine([
          row.creative_id,
          row.creative_name,
          getLanguageFlagSeverity(row),
          headline.title,
          headline.subtitle,
          row.language_flag_status,
          row.language_flag_reason,
          row.geo_linguistic_status,
          row.geo_linguistic_reason,
          row.currency_flag_status,
          row.currency_flag_reason,
          row.serving_countries.join("|"),
          row.detected_currencies.join("|"),
          row.effective_language_code,
          row.detected_language,
          row.format,
          row.approval_status,
          row.spend_30d_micros,
          row.impressions_30d,
          row.last_active_date,
        ]);
      });

      const csv = [header, ...body].join("\r\n");
      const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `language-flags-${effectiveBuyerId}-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (exportError) {
      setNotice({
        tone: "error",
        message:
          exportError instanceof Error
            ? exportError.message
            : t.creatives.languageFlagsExportFailed,
      });
    } finally {
      setIsExportingCsv(false);
    }
  };

  if (!effectiveBuyerId) {
    return <ErrorPage message={t.creatives.languageFlagsSelectBuyer} />;
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

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t.creatives.languageFlagsTitle}</h1>
          <div className="mt-1 text-2xl font-semibold text-gray-950">{riskFigure}</div>
          <p className="mt-1 text-sm text-gray-600">{t.creatives.languageFlagsDescription}</p>
        </div>
        <Link
          href={toBuyerScopedPath("/creatives", effectiveBuyerId)}
          className="text-sm text-primary-700 hover:text-primary-800"
        >
          {t.creatives.backToCreatives}
        </Link>
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
        <div className="inline-flex overflow-hidden rounded-lg border border-gray-200 bg-white">
          {segments.map((segment) => {
            const active = severity === segment.key;
            const config = SEVERITY_CONFIG[segment.key];
            return (
              <button
                key={segment.key}
                type="button"
                onClick={() => {
                  setPageIndex(0);
                  setSeverity(segment.key);
                }}
                className={cn(
                  "min-w-[148px] border-r border-gray-200 px-3 py-2 text-left text-sm last:border-r-0 hover:bg-gray-50",
                  active && "bg-gray-900 text-white hover:bg-gray-900"
                )}
              >
                <span className="flex items-center gap-2 font-medium">
                  <span className={cn("h-2 w-2 rounded-full", config.dot)} />
                  {segment.label}
                </span>
                <span className={cn("mt-0.5 block text-xs", active ? "text-gray-200" : "text-gray-500")}>
                  {segment.count.toLocaleString(language)} · {formatMoney(segment.spend, language, true)}
                </span>
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => {
              setPageIndex(0);
              setSeverity("all");
            }}
            className={cn(
              "min-w-[92px] px-3 py-2 text-left text-sm hover:bg-gray-50",
              severity === "all" && "bg-gray-900 text-white hover:bg-gray-900"
            )}
          >
            <span className="font-medium">{t.common.all}</span>
            <span className={cn("mt-0.5 block text-xs", severity === "all" ? "text-gray-200" : "text-gray-500")}>
              {total.toLocaleString(language)}
            </span>
          </button>
        </div>

        <label className="block w-full max-w-sm">
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

        <button
          type="button"
          onClick={() => refreshAllMutation.mutate()}
          disabled={refreshAllMutation.isPending}
          className="inline-flex items-center gap-2 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", refreshAllMutation.isPending && "animate-spin")} />
          {t.creatives.languageFlagsRefreshAll}
        </button>

        <button
          type="button"
          onClick={downloadCsv}
          disabled={isExportingCsv || total === 0}
          className="inline-flex items-center gap-2 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isExportingCsv ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {isExportingCsv ? t.creatives.languageFlagsDownloadingCsv : t.creatives.languageFlagsDownloadCsv}
        </button>
      </div>

      {data?.scan_limit_reached && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {t.creatives.languageFlagsCoverageNote.replace(
            "{count}",
            data.scan_limit.toLocaleString(language)
          )}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        {rows.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-gray-500">
            {t.creatives.languageFlagsNoResults}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {rows.map((row) => {
              const severityKey = getLanguageFlagSeverity(row);
              const config = SEVERITY_CONFIG[severityKey];
              const Icon = config.Icon;
              const headline = buildLanguageFlagHeadline(row, t.creatives, language);
              const previewCreative = row.preview_creative ?? null;
              const thumbCreative = previewCreative ?? {
                format: row.format,
                video: null,
                native: null,
                html: null,
                display_url: null,
                final_url: null,
                data_source: null,
              };
              const openPreview = () => {
                setPreviewTarget({
                  creativeId: row.creative_id,
                  creative: previewCreative,
                });
              };
              const rowRefreshing = refreshingCreativeId === row.creative_id;

              return (
                <div
                  key={row.creative_id}
                  role="button"
                  tabIndex={0}
                  onClick={openPreview}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openPreview();
                    }
                  }}
                  className={cn(
                    "grid cursor-pointer grid-cols-[72px_minmax(0,1fr)] gap-3 px-3 py-3 hover:bg-gray-50 md:grid-cols-[72px_minmax(0,1fr)_160px]",
                    !row.is_active && "opacity-75"
                  )}
                >
                  <div className="overflow-hidden rounded border border-gray-200">
                    <CreativeThumb creative={thumbCreative} size="sm" showSourceBadge={false} />
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium", config.badge)}>
                        <Icon className="h-3.5 w-3.5" />
                        {severityKey === "confirmed"
                          ? t.creatives.languageFlagsConfirmedWrong
                          : severityKey === "review"
                          ? t.creatives.languageFlagsNeedsReview
                          : t.creatives.languageFlagsOk}
                      </span>
                      {row.geo_linguistic_completed_at ? (
                        <span className="text-[11px] text-gray-400">
                          {t.creatives.languageFlagsUpdated.replace(
                            "{date}",
                            new Date(row.geo_linguistic_completed_at).toLocaleDateString(language)
                          )}
                        </span>
                      ) : (
                        <span className="text-[11px] text-gray-400">
                          {t.creatives.languageFlagsNoAiRefreshYet}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 truncate text-base font-medium text-gray-950" title={headline.title}>
                      {headline.title}
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-sm text-gray-600" title={headline.subtitle}>
                      {headline.subtitle}
                    </div>
                    <div className="mt-1 truncate text-xs text-gray-400" title={rowFootline(row)}>
                      {rowFootline(row)}
                    </div>
                  </div>

                  <div className="col-span-2 flex items-center justify-between gap-2 md:col-span-1 md:flex-col md:items-end md:justify-center">
                    <div className={cn("text-sm font-semibold", row.spend_30d_micros > 0 ? "text-gray-950" : "text-gray-400")}>
                      {formatMoney(row.spend_30d_micros, language)} <span className="font-normal text-gray-400">/ 30d</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isRowRefreshable(row) && (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            refreshRowMutation.mutate(row.creative_id);
                          }}
                          disabled={rowRefreshing}
                          className="inline-flex items-center gap-1 rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50 disabled:opacity-50"
                        >
                          <RefreshCw className={cn("h-3.5 w-3.5", rowRefreshing && "animate-spin")} />
                          {t.creatives.languageFlagsRefreshRow}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          openPreview();
                        }}
                        className="rounded border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-primary-700 hover:bg-primary-50"
                      >
                        {t.creatives.languageFlagsView}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
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

      {previewTarget && (
        <PreviewModal
          creative={previewTarget.creative ?? undefined}
          creativeId={previewTarget.creativeId}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </div>
  );
}
