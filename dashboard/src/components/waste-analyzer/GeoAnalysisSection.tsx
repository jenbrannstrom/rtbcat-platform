"use client";

import { useState } from "react";
import Link from "next/link";
import { Globe, Upload, ArrowRight, ArrowUp, ArrowDown, ChevronsUpDown } from "lucide-react";
import type { GeoPerformance } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";
import { cn } from "@/lib/utils";
import { formatNumber } from "./FunnelCard";

interface GeoAnalysisSectionProps {
  geos: GeoPerformance[];
  seatName?: string;
}

/**
 * Geographic Analysis Section - Using RTB Funnel Geo Data.
 * Shows win rates by country and identifies optimization opportunities.
 */
export function GeoAnalysisSection({ geos, seatName }: GeoAnalysisSectionProps) {
  const { selectedBuyerId } = useAccount();
  const { t } = useTranslation();
  const importHref = toBuyerScopedPath("/import", selectedBuyerId);
  type SortColumn = "country" | "reached" | "bids" | "wins" | "win_rate";
  type SortDirection = "asc" | "desc";
  const [sortColumn, setSortColumn] = useState<SortColumn>("wins");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const hasGeoData = geos && geos.length > 0;

  if (!hasGeoData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Globe className="h-5 w-5 text-green-600" />
              {t.wasteAnalysis.geographicPerformance}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              {t.wasteAnalysis.geographicPerformanceSubtitle}
            </p>
          </div>
        </div>
        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg">
          <div className="flex items-start gap-4">
            <Upload className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-gray-700 mb-2">{t.wasteAnalysis.geographicDataNotAvailable}</h4>
              <p className="text-sm text-gray-600 mb-4">
                {t.wasteAnalysis.importCreativeBiddingGeoReportPrompt}
              </p>
              <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                <p className="font-semibold text-gray-700 mb-2">{t.wasteAnalysis.creativeBidsReportName}</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">{t.wasteAnalysis.dimensions}</p>
                    <ul className="text-gray-600">
                      <li>{t.wasteAnalysis.dimensionDayIndex}</li>
                      <li>{t.wasteAnalysis.dimensionCreativeIdIndex}</li>
                      <li>{t.wasteAnalysis.dimensionCountryIndex}</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">{t.wasteAnalysis.metrics}</p>
                    <ul className="text-gray-600">
                      <li>{t.wasteAnalysis.metricBids}</li>
                      <li>{t.wasteAnalysis.metricBidsInAuction}</li>
                      <li>{t.wasteAnalysis.metricReachedQueries}</li>
                    </ul>
                  </div>
                </div>
                <p className="mt-2 text-gray-500">{t.wasteAnalysis.schedule} <strong>{t.wasteAnalysis.daily}</strong></p>
              </div>
              <Link href={importHref} className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                {t.wasteAnalysis.goToImport} <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDirection("desc");
    }
  };

  const getSortIcon = (column: SortColumn) => {
    if (sortColumn !== column) return <ChevronsUpDown className="h-3 w-3 text-gray-400" />;
    return sortDirection === "asc" ? (
      <ArrowUp className="h-3 w-3 text-gray-600" />
    ) : (
      <ArrowDown className="h-3 w-3 text-gray-600" />
    );
  };

  const sortedGeos = [...geos].sort((a, b) => {
    const aWins = a.auctions_won ?? a.impressions ?? 0;
    const bWins = b.auctions_won ?? b.impressions ?? 0;
    let aVal: number | string;
    let bVal: number | string;

    switch (sortColumn) {
      case "country":
        aVal = a.country || "";
        bVal = b.country || "";
        break;
      case "reached":
        aVal = a.reached_queries;
        bVal = b.reached_queries;
        break;
      case "bids":
        aVal = a.bids ?? 0;
        bVal = b.bids ?? 0;
        break;
      case "win_rate":
        aVal = a.win_rate;
        bVal = b.win_rate;
        break;
      case "wins":
      default:
        aVal = aWins;
        bVal = bWins;
        break;
    }

    if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
    return 0;
  });

  const displayGeos = sortedGeos.slice(0, 15);
  const totalReached = displayGeos.reduce((sum, g) => sum + g.reached_queries, 0);
  const totalWins = displayGeos.reduce((sum, g) => sum + (g.auctions_won ?? g.impressions ?? 0), 0);
  const overallWinRate = totalReached > 0
    ? Math.min(100, totalWins / totalReached * 100)
    : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Globe className="h-5 w-5 text-green-600" />
            {t.wasteAnalysis.geographicPerformanceOverallFor.replace(
              "{seatName}",
              seatName || t.wasteAnalysis.seat
            )}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {t.wasteAnalysis.geographicPerformanceTableSubtitle}
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <div className="px-3 py-1 bg-gray-50 rounded border">
            {t.wasteAnalysis.reached} <span className="ml-1 font-semibold text-gray-900">{formatNumber(totalReached)}</span>
          </div>
          <div className="px-3 py-1 bg-gray-50 rounded border">
            {t.wasteAnalysis.wins} <span className="ml-1 font-semibold text-gray-900">{formatNumber(totalWins)}</span>
          </div>
          <div className="px-3 py-1 bg-gray-50 rounded border">
            {t.wasteAnalysis.winRate} <span className="ml-1 font-semibold text-gray-900">{overallWinRate.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* Geo Table with RTB metrics */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("country")} className="inline-flex items-center gap-1 hover:text-gray-900">
                  {t.wasteAnalysis.country} {getSortIcon("country")}
                </button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("reached")} className="inline-flex items-center gap-1 hover:text-gray-900">
                  {t.wasteAnalysis.reached} {getSortIcon("reached")}
                </button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("bids")} className="inline-flex items-center gap-1 hover:text-gray-900">
                  {t.wasteAnalysis.bids} {getSortIcon("bids")}
                </button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("wins")} className="inline-flex items-center gap-1 hover:text-gray-900">
                  {t.wasteAnalysis.wins} {getSortIcon("wins")}
                </button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("win_rate")} className="inline-flex items-center gap-1 hover:text-gray-900">
                  {t.wasteAnalysis.winRate} {getSortIcon("win_rate")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {displayGeos.map((geo, index) => {
              const wins = geo.auctions_won ?? geo.impressions ?? 0;
              const safeWinRate = Math.min(100, Math.max(0, geo.win_rate));
              const isLow = safeWinRate < 50 && wins > 0;
              const isTop = index === 0;
              return (
              <tr key={geo.country} className="border-b border-gray-100 last:border-0">
                <td className="py-2">
                  <span className="font-medium text-gray-900">
                    {isTop && "🏆 "}
                    {isLow && !isTop && "⚠️ "}
                    {geo.country}
                  </span>
                </td>
                <td className="py-2 text-right text-blue-600">{formatNumber(geo.reached_queries)}</td>
                <td className="py-2 text-right text-gray-900">{formatNumber(geo.bids ?? 0)}</td>
                <td className="py-2 text-right text-green-600">{formatNumber(wins)}</td>
                <td className={cn(
                  "py-2 text-right font-medium",
                  safeWinRate < 30 ? "text-red-600" : safeWinRate >= 60 ? "text-green-600" : "text-gray-900"
                )}>
                  {safeWinRate.toFixed(1)}%
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>
    </div>
  );
}
