"use client";

import { useState } from "react";
import { Globe, Upload, ArrowRight } from "lucide-react";
import type { GeoPerformance } from "@/lib/api";
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
  const hasGeoData = geos && geos.length > 0;

  if (!hasGeoData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Globe className="h-5 w-5 text-green-600" />
              Geographic Performance
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Which geos have highest win rates?
            </p>
          </div>
        </div>
        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg">
          <div className="flex items-start gap-4">
            <Upload className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Geographic Data Not Available</h4>
              <p className="text-sm text-gray-600 mb-4">
                Import a creative bidding activity report to see geographic win rates.
              </p>
              <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                <p className="font-semibold text-gray-700 mb-2">Report: &quot;catscan-creative-bids&quot;</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Dimensions:</p>
                    <ul className="text-gray-600">
                      <li>1. Day</li>
                      <li>2. Creative ID</li>
                      <li>3. Country</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Metrics:</p>
                    <ul className="text-gray-600">
                      <li>✓ Bids</li>
                      <li>✓ Bids in auction</li>
                      <li>✓ Reached queries</li>
                    </ul>
                  </div>
                </div>
                <p className="mt-2 text-gray-500">Schedule: <strong>Daily</strong></p>
              </div>
              <a href="/setup?tab=import" className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                Go to Import → <ArrowRight className="h-3 w-3" />
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  type SortColumn = "country" | "reached" | "bids" | "wins" | "win_rate";
  type SortDirection = "asc" | "desc";
  const [sortColumn, setSortColumn] = useState<SortColumn>("wins");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(column);
      setSortDirection("desc");
    }
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
  const totalBids = displayGeos.reduce((sum, g) => sum + (g.bids ?? 0), 0);
  const totalReached = displayGeos.reduce((sum, g) => sum + g.reached_queries, 0);
  const totalWins = displayGeos.reduce((sum, g) => sum + (g.auctions_won ?? g.impressions ?? 0), 0);
  const overallWinRate = totalReached > 0 ? (totalWins / totalReached * 100) : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Globe className="h-5 w-5 text-green-600" />
            Geographic Performance — overall for {seatName || "seat"}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Win rates by country (all pretargeting configs combined)
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <div className="px-3 py-1 bg-gray-50 rounded border">
            Reached <span className="ml-1 font-semibold text-gray-900">{formatNumber(totalReached)}</span>
          </div>
          <div className="px-3 py-1 bg-gray-50 rounded border">
            Wins <span className="ml-1 font-semibold text-gray-900">{formatNumber(totalWins)}</span>
          </div>
          <div className="px-3 py-1 bg-gray-50 rounded border">
            Win Rate <span className="ml-1 font-semibold text-gray-900">{overallWinRate.toFixed(1)}%</span>
          </div>
        </div>
      </div>

      {/* Geo Table with RTB metrics */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("country")} className="hover:text-gray-900">Country</button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("reached")} className="hover:text-gray-900">Reached</button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("bids")} className="hover:text-gray-900">Bids</button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("wins")} className="hover:text-gray-900">Wins</button>
              </th>
              <th className="text-right py-2 font-medium text-gray-600">
                <button onClick={() => handleSort("win_rate")} className="hover:text-gray-900">Win Rate</button>
              </th>
            </tr>
          </thead>
          <tbody>
            {displayGeos.map((geo, index) => {
              const wins = geo.auctions_won ?? geo.impressions ?? 0;
              const isLow = geo.win_rate < 50 && wins > 0;
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
                  geo.win_rate < 30 ? "text-red-600" : geo.win_rate >= 60 ? "text-green-600" : "text-gray-900"
                )}>
                  {geo.win_rate.toFixed(1)}%
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>
    </div>
  );
}
