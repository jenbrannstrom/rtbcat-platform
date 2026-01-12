"use client";

import { Globe, Upload, ArrowRight, Trophy, AlertCircle } from "lucide-react";
import type { GeoPerformance } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatNumber } from "./FunnelCard";

interface GeoAnalysisSectionProps {
  geos: GeoPerformance[];
}

/**
 * Geographic Analysis Section - Using RTB Funnel Geo Data.
 * Shows win rates by country and identifies optimization opportunities.
 */
export function GeoAnalysisSection({ geos }: GeoAnalysisSectionProps) {
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

  // Sort by wins (auctions_won or impressions)
  const sortedGeos = [...geos].sort((a, b) =>
    (b.auctions_won ?? b.impressions ?? 0) - (a.auctions_won ?? a.impressions ?? 0)
  );

  // Categorize by win rate
  const highWinRate = sortedGeos.filter(g => g.win_rate >= 80);
  const lowWinRate = sortedGeos.filter(g => g.win_rate < 50 && (g.auctions_won ?? g.impressions ?? 0) > 0);

  // Calculate totals
  const totalBids = geos.reduce((sum, g) => sum + (g.bids ?? 0), 0);
  const totalReached = geos.reduce((sum, g) => sum + g.reached_queries, 0);
  const totalWins = geos.reduce((sum, g) => sum + (g.auctions_won ?? g.impressions ?? 0), 0);
  const overallWinRate = totalReached > 0 ? (totalWins / totalReached * 100) : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Globe className="h-5 w-5 text-green-600" />
            Geographic Performance
            <span className="text-xs font-normal bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              Account-wide
            </span>
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Win rates by country (all pretargeting configs combined)
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{overallWinRate.toFixed(1)}%</div>
          <div className="text-sm text-gray-500">avg win rate</div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="p-3 bg-gray-50 rounded-lg text-center">
          <div className="text-lg font-bold text-gray-900">{geos.length}</div>
          <div className="text-xs text-gray-500">Countries</div>
        </div>
        <div className="p-3 bg-blue-50 rounded-lg text-center">
          <div className="text-lg font-bold text-blue-700">{formatNumber(totalReached)}</div>
          <div className="text-xs text-blue-600">Reached</div>
        </div>
        <div className="p-3 bg-purple-50 rounded-lg text-center">
          <div className="text-lg font-bold text-purple-700">{formatNumber(totalBids)}</div>
          <div className="text-xs text-purple-600">Bids</div>
        </div>
        <div className="p-3 bg-green-50 rounded-lg text-center">
          <div className="text-lg font-bold text-green-700">{formatNumber(totalWins)}</div>
          <div className="text-xs text-green-600">Wins</div>
        </div>
      </div>

      {/* Win Rate Categories */}
      <div className="space-y-4 mb-6">
        {highWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-green-700 mb-2">
              <Trophy className="h-4 w-4" />
              High Win Rate (&gt;80%) - {highWinRate.length} countries
            </div>
            <div className="flex flex-wrap gap-2">
              {highWinRate.map(geo => (
                <span
                  key={geo.country}
                  className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium"
                  title={`Reached: ${formatNumber(geo.reached_queries)}, Wins: ${formatNumber(geo.auctions_won ?? geo.impressions ?? 0)}`}
                >
                  {geo.country} ({geo.win_rate.toFixed(0)}%)
                </span>
              ))}
            </div>
          </div>
        )}

        {lowWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-orange-700 mb-2">
              <AlertCircle className="h-4 w-4" />
              Lower Win Rate (&lt;50%) - Optimize these
            </div>
            <div className="flex flex-wrap gap-2">
              {lowWinRate.slice(0, 10).map(geo => (
                <span
                  key={geo.country}
                  className="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs font-medium"
                  title={`Reached: ${formatNumber(geo.reached_queries)}, Wins: ${formatNumber(geo.auctions_won ?? geo.impressions ?? 0)}`}
                >
                  {geo.country} ({geo.win_rate.toFixed(0)}%)
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Geo Table with RTB metrics */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 font-medium text-gray-600">Country</th>
              <th className="text-right py-2 font-medium text-gray-600">Bids</th>
              <th className="text-right py-2 font-medium text-gray-600">Reached</th>
              <th className="text-right py-2 font-medium text-gray-600">Wins</th>
              <th className="text-right py-2 font-medium text-gray-600">Win Rate</th>
            </tr>
          </thead>
          <tbody>
            {sortedGeos.slice(0, 15).map(geo => (
              <tr key={geo.country} className="border-b border-gray-100 last:border-0">
                <td className="py-2">
                  <span className="font-medium text-gray-900">{geo.country}</span>
                </td>
                <td className="py-2 text-right text-gray-900">{formatNumber(geo.bids ?? 0)}</td>
                <td className="py-2 text-right text-blue-600">{formatNumber(geo.reached_queries)}</td>
                <td className="py-2 text-right text-green-600">{formatNumber(geo.auctions_won ?? geo.impressions ?? 0)}</td>
                <td className={cn(
                  "py-2 text-right font-medium",
                  geo.win_rate < 30 ? "text-red-600" : geo.win_rate >= 60 ? "text-green-600" : "text-gray-900"
                )}>
                  {geo.win_rate.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
