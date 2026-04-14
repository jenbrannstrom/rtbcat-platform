"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, HelpCircle, Search, ShieldAlert } from "lucide-react";
import { usePathname } from "next/navigation";
import { getCreativeLanguageFlagCoverage } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { useAccount } from "@/contexts/account-context";
import { splitBuyerPath, toBuyerScopedPath } from "@/lib/buyer-routes";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 100;

const STATUS_CONFIG = {
  green: {
    label: "Green",
    badge: "bg-green-100 text-green-700",
    icon: CheckCircle2,
  },
  orange: {
    label: "Orange",
    badge: "bg-amber-100 text-amber-700",
    icon: HelpCircle,
  },
  red: {
    label: "Red",
    badge: "bg-red-100 text-red-700",
    icon: ShieldAlert,
  },
} as const;

function StatusBadge({
  status,
  reason,
}: {
  status: "green" | "orange" | "red" | string;
  reason: string;
}) {
  const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.orange;
  const Icon = config.icon;

  return (
    <div className="space-y-1">
      <span className={cn("inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium", config.badge)}>
        <Icon className="h-3.5 w-3.5" />
        {config.label}
      </span>
      <div className="max-w-md text-xs text-gray-600">{reason}</div>
    </div>
  );
}

export default function LanguageFlagCoveragePage() {
  const pathname = usePathname();
  const { selectedBuyerId } = useAccount();
  const { buyerIdInPath } = splitBuyerPath(pathname || "/");
  const effectiveBuyerId = buyerIdInPath ?? selectedBuyerId ?? null;
  const [search, setSearch] = useState("");
  const [languageState, setLanguageState] = useState<"all" | "green" | "orange" | "red">("all");
  const [geoState, setGeoState] = useState<"all" | "green" | "orange" | "red">("all");
  const [pageIndex, setPageIndex] = useState(0);

  useEffect(() => {
    setPageIndex(0);
  }, [effectiveBuyerId]);

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
    queryFn: () =>
      getCreativeLanguageFlagCoverage({
        buyer_id: effectiveBuyerId ?? undefined,
        search: search.trim() || undefined,
        language_state: languageState,
        geo_state: geoState,
        limit: PAGE_SIZE,
        offset,
      }),
    staleTime: 30_000,
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

  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={error instanceof Error ? error.message : "Failed to load language flags"}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Language Flags</h1>
          <p className="text-sm text-gray-600">
            Deterministic language and currency checks plus the latest geo-linguistic result.
          </p>
        </div>
        <Link
          href={toBuyerScopedPath("/creatives", effectiveBuyerId)}
          className="text-sm text-primary-700 hover:text-primary-800"
        >
          Back to Creatives
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Lang Red</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">{summary?.language_red ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Lang Orange</div>
          <div className="mt-1 text-2xl font-semibold text-amber-700">{summary?.language_orange ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Geo Red</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">{summary?.geo_red ?? 0}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Flagged</div>
          <div className="mt-1 text-2xl font-semibold text-gray-900">{flaggedPct.toFixed(1)}%</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(event) => {
              setPageIndex(0);
              setSearch(event.target.value);
            }}
            placeholder="Search by creative ID or name"
            className="input w-full py-1.5 pl-9 pr-3 text-sm"
          />
        </div>

        <select
          value={languageState}
          onChange={(event) => {
            setPageIndex(0);
            setLanguageState(event.target.value as "all" | "green" | "orange" | "red");
          }}
          className="input py-1.5 pr-8 text-sm"
        >
          <option value="all">All Lang States</option>
          <option value="red">Lang Red</option>
          <option value="orange">Lang Orange</option>
          <option value="green">Lang Green</option>
        </select>

        <select
          value={geoState}
          onChange={(event) => {
            setPageIndex(0);
            setGeoState(event.target.value as "all" | "green" | "orange" | "red");
          }}
          className="input py-1.5 pr-8 text-sm"
        >
          <option value="all">All Geo States</option>
          <option value="red">Geo Red</option>
          <option value="orange">Geo Orange</option>
          <option value="green">Geo Green</option>
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Creative ID</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Lang Mismatch</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Geo-Linguistic</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Serving</th>
                <th className="px-3 py-2 text-right font-medium text-gray-600">Spend (30d)</th>
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
                    <StatusBadge status={row.language_flag_status} reason={row.language_flag_reason} />
                    {(row.effective_language_code || row.language_flag_source) && (
                      <div className="mt-1 text-[11px] text-gray-400">
                        {(row.language_flag_source || "unknown").toUpperCase()} · {(row.effective_language_code || "?").toUpperCase()}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 align-top">
                    <StatusBadge status={row.geo_linguistic_status} reason={row.geo_linguistic_reason} />
                    {row.detected_currencies.length > 0 && (
                      <div className="mt-1 text-[11px] text-gray-400">
                        Currency: {row.detected_currencies.join(", ")}
                      </div>
                    )}
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
                    No creatives matched this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>
          Showing {pageStart}-{pageEnd} of {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPageIndex((value) => Math.max(value - 1, 0))}
            disabled={pageIndex === 0}
            className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => setPageIndex((value) => value + 1)}
            disabled={!hasMore}
            className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
