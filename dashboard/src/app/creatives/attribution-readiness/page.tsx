"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, CircleDashed, Link2 } from "lucide-react";
import {
  getConversionAttributionSummary,
  getConversionReadiness,
  getCreativeClickMacroCoverage,
  getSeats,
} from "@/lib/api";
import { ErrorPage } from "@/components/error";
import { LoadingPage } from "@/components/loading";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

type AttributionSeatStatus = "no_af" | "af_no_clickid" | "af_exact_ready";

interface SeatAttributionReadinessRow {
  buyer_id: string;
  seat_name: string;
  creative_count: number;
  status: AttributionSeatStatus;
  status_label: string;
  appsflyer_urls: number;
  appsflyer_clickid_urls: number;
  conversion_state: string;
  exact_matched: number;
  exact_total: number;
  notes: string[];
}

function deriveSeatStatus(
  appsflyerUrls: number,
  appsflyerClickidUrls: number,
): Pick<SeatAttributionReadinessRow, "status" | "status_label" | "notes"> {
  if (appsflyerUrls <= 0) {
    return {
      status: "no_af",
      status_label: "No AF",
      notes: ["No AppsFlyer URLs detected in sampled creatives."],
    };
  }
  if (appsflyerClickidUrls <= 0) {
    return {
      status: "af_no_clickid",
      status_label: "AF present / no clickid",
      notes: ["AppsFlyer URLs exist, but no clickid parameter was detected."],
    };
  }
  return {
    status: "af_exact_ready",
    status_label: "AF exact-ready",
    notes: ["AppsFlyer URLs include clickid, enabling exact click-level joins."],
  };
}

export default function AttributionReadinessPage() {
  const seatsQuery = useQuery({
    queryKey: ["seats", "active-only", "attribution-readiness"],
    queryFn: () => getSeats({ active_only: true }),
    staleTime: 30_000,
  });

  const readinessQuery = useQuery({
    queryKey: ["attribution-readiness-table", seatsQuery.data?.map((s) => s.buyer_id).join(",")],
    enabled: Boolean(seatsQuery.data && seatsQuery.data.length > 0),
    staleTime: 30_000,
    queryFn: async (): Promise<SeatAttributionReadinessRow[]> => {
      const seats = seatsQuery.data ?? [];
      const rows = await Promise.all(
        seats.map(async (seat) => {
          const [macroResult, readinessResult, attributionResult] = await Promise.allSettled([
            getCreativeClickMacroCoverage({
              buyer_id: seat.buyer_id,
              limit: 1,
              offset: 0,
              scan_limit: 3000,
            }),
            getConversionReadiness({
              buyer_id: seat.buyer_id,
              days: 14,
              freshness_hours: 72,
            }),
            getConversionAttributionSummary({
              buyer_id: seat.buyer_id,
              source_type: "appsflyer",
              days: 14,
            }),
          ]);

          const macroSummary =
            macroResult.status === "fulfilled" ? macroResult.value.summary : undefined;
          const conversionState =
            readinessResult.status === "fulfilled" ? readinessResult.value.state : "unavailable";
          const attributionModes =
            attributionResult.status === "fulfilled" ? attributionResult.value.modes : [];
          const exactMode = attributionModes.find((mode) => mode.mode === "exact_clickid");

          const appsflyerUrls = macroSummary?.creatives_with_appsflyer_url ?? 0;
          const appsflyerClickidUrls = macroSummary?.creatives_with_appsflyer_clickid ?? 0;

          const derived = deriveSeatStatus(appsflyerUrls, appsflyerClickidUrls);
          const notes = [...derived.notes];
          if (readinessResult.status === "rejected") {
            notes.push("Conversion readiness endpoint unavailable for this seat.");
          } else if (conversionState !== "ready") {
            notes.push(`Conversion state is '${conversionState}'.`);
          }
          if (attributionResult.status === "rejected") {
            notes.push("Attribution summary endpoint unavailable for this seat.");
          }

          return {
            buyer_id: seat.buyer_id,
            seat_name: seat.display_name || seat.buyer_id,
            creative_count: seat.creative_count,
            status: derived.status,
            status_label: derived.status_label,
            appsflyer_urls: appsflyerUrls,
            appsflyer_clickid_urls: appsflyerClickidUrls,
            conversion_state: conversionState,
            exact_matched: exactMode?.matched ?? 0,
            exact_total: exactMode?.total ?? 0,
            notes,
          };
        }),
      );
      return rows.sort((a, b) => a.seat_name.localeCompare(b.seat_name));
    },
  });

  const rows = readinessQuery.data ?? [];

  const summary = useMemo(() => {
    return {
      no_af: rows.filter((row) => row.status === "no_af").length,
      af_no_clickid: rows.filter((row) => row.status === "af_no_clickid").length,
      af_exact_ready: rows.filter((row) => row.status === "af_exact_ready").length,
    };
  }, [rows]);

  if (seatsQuery.isLoading || readinessQuery.isLoading) {
    return <LoadingPage />;
  }

  if (seatsQuery.error) {
    return (
      <ErrorPage
        message={seatsQuery.error instanceof Error ? seatsQuery.error.message : "Failed to load seats"}
        onRetry={() => seatsQuery.refetch()}
      />
    );
  }

  if (readinessQuery.error) {
    return (
      <ErrorPage
        message={readinessQuery.error instanceof Error ? readinessQuery.error.message : "Failed to build readiness table"}
        onRetry={() => readinessQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Attribution Readiness</h1>
          <p className="text-sm text-gray-600">
            Seat-level AppsFlyer readiness for exact attribution joins (`No AF`, `AF no clickid`, `AF exact-ready`).
          </p>
        </div>
        <Link
          href="/creatives/click-macros"
          className="inline-flex items-center gap-2 text-sm text-primary-700 hover:text-primary-800"
        >
          <Link2 className="h-4 w-4" />
          Open Click Macro Audit
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">No AF</div>
          <div className="mt-1 text-2xl font-semibold text-gray-900">{summary.no_af}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">AF no clickid</div>
          <div className="mt-1 text-2xl font-semibold text-amber-700">{summary.af_no_clickid}</div>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs uppercase tracking-wide text-gray-500">AF exact-ready</div>
          <div className="mt-1 text-2xl font-semibold text-green-700">{summary.af_exact_ready}</div>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Seat</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">AF URLs</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">AF + clickid</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Conversion State</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Exact Matches (14d)</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => {
                const statusClass =
                  row.status === "af_exact_ready"
                    ? "bg-green-100 text-green-700"
                    : row.status === "af_no_clickid"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-gray-100 text-gray-700";
                const statusIcon =
                  row.status === "af_exact_ready" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : row.status === "af_no_clickid" ? (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  ) : (
                    <CircleDashed className="h-3.5 w-3.5" />
                  );
                return (
                  <tr key={row.buyer_id}>
                    <td className="px-3 py-2 align-top">
                      <div className="font-medium text-gray-900">{row.seat_name}</div>
                      <div className="font-mono text-xs text-gray-500">{row.buyer_id}</div>
                      <div className="text-xs text-gray-500">{row.creative_count} creatives</div>
                    </td>
                    <td className="px-3 py-2 align-top">
                      <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ${statusClass}`}>
                        {statusIcon}
                        {row.status_label}
                      </span>
                      {row.notes.length > 0 && (
                        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-gray-600">
                          {row.notes.slice(0, 2).map((note) => (
                            <li key={`${row.buyer_id}-${note}`}>{note}</li>
                          ))}
                        </ul>
                      )}
                    </td>
                    <td className="px-3 py-2 align-top text-xs text-gray-800">{row.appsflyer_urls}</td>
                    <td className="px-3 py-2 align-top text-xs text-gray-800">{row.appsflyer_clickid_urls}</td>
                    <td className="px-3 py-2 align-top text-xs text-gray-800">{row.conversion_state}</td>
                    <td className="px-3 py-2 align-top text-xs text-gray-800">
                      {row.exact_matched}/{row.exact_total}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <div className="flex flex-col gap-1 text-xs">
                        <Link
                          href={toBuyerScopedPath("/creatives/click-macros", row.buyer_id)}
                          className="text-primary-700 hover:text-primary-800"
                        >
                          Click macros
                        </Link>
                        <Link
                          href={toBuyerScopedPath("/settings/system", row.buyer_id)}
                          className="text-primary-700 hover:text-primary-800"
                        >
                          System status
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-500">
                    No active seats found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
