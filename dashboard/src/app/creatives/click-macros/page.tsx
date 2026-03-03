"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Search } from "lucide-react";
import { getCreativeClickMacroCoverage } from "@/lib/api";
import { LoadingPage } from "@/components/loading";
import { ErrorPage } from "@/components/error";
import { useAccount } from "@/contexts/account-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 100;

export default function ClickMacroCoveragePage() {
  const { selectedBuyerId } = useAccount();
  const [search, setSearch] = useState("");
  const [macroState, setMacroState] = useState<"all" | "has_click_macro" | "missing_click_macro">("all");
  const [pageIndex, setPageIndex] = useState(0);

  useEffect(() => {
    setPageIndex(0);
  }, [selectedBuyerId]);

  const offset = pageIndex * PAGE_SIZE;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["creative-click-macro-coverage", selectedBuyerId, search, macroState, offset],
    queryFn: () =>
      getCreativeClickMacroCoverage({
        buyer_id: selectedBuyerId ?? undefined,
        search: search.trim() || undefined,
        macro_state: macroState,
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

  const compliancePct = useMemo(() => {
    if (!summary) return 0;
    const denominator = summary.creatives_with_click_macro + summary.creatives_without_click_macro;
    if (denominator === 0) return 0;
    return (summary.creatives_with_click_macro / denominator) * 100;
  }, [summary]);

  if (isLoading) {
    return <LoadingPage />;
  }

  if (error) {
    return (
      <ErrorPage
        message={error instanceof Error ? error.message : "Failed to load click macro coverage"}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Click Macro Coverage</h1>
          <p className="text-sm text-gray-600">
            Google requires click macro support. This table shows which creatives include or miss it.
          </p>
        </div>
        <Link
          href={toBuyerScopedPath("/creatives", selectedBuyerId)}
          className="text-sm text-primary-700 hover:text-primary-800"
        >
          Back to Creatives
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">With Click Macro</div>
          <div className="mt-1 text-2xl font-semibold text-green-700">
            {summary?.creatives_with_click_macro ?? 0}
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Missing Click Macro</div>
          <div className="mt-1 text-2xl font-semibold text-red-700">
            {summary?.creatives_without_click_macro ?? 0}
          </div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">Coverage</div>
          <div className="mt-1 text-2xl font-semibold text-gray-900">{compliancePct.toFixed(1)}%</div>
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
          value={macroState}
          onChange={(event) => {
            setPageIndex(0);
            setMacroState(event.target.value as "all" | "has_click_macro" | "missing_click_macro");
          }}
          className="input py-1.5 pr-8 text-sm"
        >
          <option value="all">All</option>
          <option value="has_click_macro">Has click macro</option>
          <option value="missing_click_macro">Missing click macro</option>
        </select>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Creative</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Format</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Approval</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Click Macro Tokens</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Sources</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Sample URL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => (
                <tr key={row.creative_id}>
                  <td className="px-3 py-2 align-top">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium",
                        row.has_click_macro ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                      )}
                    >
                      {row.has_click_macro ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                      {row.has_click_macro ? "Present" : "Missing"}
                    </span>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <div className="font-mono text-xs text-gray-900">{row.creative_id}</div>
                    <div className="max-w-sm truncate text-xs text-gray-600" title={row.creative_name}>
                      {row.creative_name}
                    </div>
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-gray-700">{row.format || "-"}</td>
                  <td className="px-3 py-2 align-top text-xs text-gray-700">{row.approval_status || "-"}</td>
                  <td className="px-3 py-2 align-top text-xs text-gray-700">
                    {row.click_macro_tokens.length > 0 ? row.click_macro_tokens.join(", ") : "-"}
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-gray-700">
                    {row.url_sources.length > 0 ? row.url_sources.join(", ") : "-"}
                  </td>
                  <td className="px-3 py-2 align-top">
                    {row.sample_url ? (
                      <a
                        href={row.sample_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block max-w-[26rem] truncate font-mono text-xs text-primary-700 hover:text-primary-800"
                        title={row.sample_url}
                      >
                        {row.sample_url}
                      </a>
                    ) : (
                      <span className="text-xs text-gray-500">-</span>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-500">
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
            onClick={() => setPageIndex((prev) => Math.max(prev - 1, 0))}
            disabled={pageIndex === 0}
            className="rounded border border-gray-300 px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPageIndex((prev) => prev + 1)}
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
