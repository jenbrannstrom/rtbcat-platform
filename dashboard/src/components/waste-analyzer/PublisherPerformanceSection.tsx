"use client";

import Link from "next/link";
import { BarChart3, Upload, ArrowRight, Trophy, AlertCircle, TrendingUp, Ban } from "lucide-react";
import type { PublisherPerformance } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";
import { formatNumber } from "./FunnelCard";

interface PublisherPerformanceSectionProps {
  publishers: PublisherPerformance[];
  seatName?: string;
}

/**
 * Publisher Performance Section.
 * Shows publisher win rates categorized by performance tier.
 */
export function PublisherPerformanceSection({ publishers, seatName }: PublisherPerformanceSectionProps) {
  const { selectedBuyerId } = useAccount();
  const importHref = toBuyerScopedPath("/import", selectedBuyerId);
  const hasPublisherData = publishers && publishers.length > 0;

  if (!hasPublisherData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              Publisher Performance
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Where are you winning vs losing?
            </p>
          </div>
        </div>

        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg">
          <div className="flex items-start gap-4">
            <Upload className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Publisher Data Not Available</h4>
              <p className="text-sm text-gray-600 mb-4">
                Import a publisher performance report to see which publishers you're winning on.
              </p>
              <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                <p className="font-semibold text-gray-700 mb-2">Report: &quot;catscan-publisher-perf&quot;</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Dimensions:</p>
                    <ul className="text-gray-600">
                      <li>1. Publisher ID</li>
                      <li>2. Publisher name</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Metrics:</p>
                    <ul className="text-gray-600">
                      <li>✓ Bid requests</li>
                      <li>✓ Reached queries</li>
                      <li>✓ Impressions</li>
                    </ul>
                  </div>
                </div>
                <p className="mt-2 text-gray-500">Schedule: <strong>Daily</strong></p>
              </div>
              <Link href={importHref} className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                Go to Import → <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Categorize publishers by win rate
  const highWinRate = publishers.filter(p => p.win_rate >= 40 && p.impressions > 0);
  const moderateWinRate = publishers.filter(p => p.win_rate >= 20 && p.win_rate < 40 && p.impressions > 0);
  const lowWinRate = publishers.filter(p => p.win_rate < 20 && p.impressions > 0);
  const blockedTrafficThreshold = 100000;
  const blocked = publishers.filter(
    (p) => p.reached_queries === 0 && (p.bid_requests ?? 0) > blockedTrafficThreshold
  );

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            Publisher Performance
            <span className="text-xs font-normal bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              {seatName ? `Overall for ${seatName}` : "Seat overall"}
            </span>
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Win/loss analysis across all pretargeting configs for this seat
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{publishers.length}</div>
          <div className="text-sm text-gray-500">publishers</div>
        </div>
      </div>

      <div className="space-y-6">
        {/* High Win Rate */}
        {highWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-green-700 mb-2">
              <Trophy className="h-4 w-4" />
              High Win Rate (&gt;40%) - {highWinRate.length} publishers
            </div>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="space-y-2">
                {highWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-green-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-green-600">{formatNumber(pub.impressions)} impr</span>
                      <span className="font-medium text-green-700">{pub.win_rate.toFixed(1)}% win</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Moderate Win Rate */}
        {moderateWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-yellow-700 mb-2">
              <AlertCircle className="h-4 w-4" />
              Moderate Win Rate (20-40%) - {moderateWinRate.length} publishers
            </div>
            <div className="bg-yellow-50 rounded-lg p-3">
              <div className="space-y-2">
                {moderateWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-yellow-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-yellow-600">{formatNumber(pub.impressions)} impr</span>
                      <span className="font-medium text-yellow-700">{pub.win_rate.toFixed(1)}% win</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Low Win Rate */}
        {lowWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-orange-700 mb-2">
              <TrendingUp className="h-4 w-4" />
              Low Win Rate (&lt;20%) - {lowWinRate.length} publishers
            </div>
            <div className="bg-orange-50 rounded-lg p-3">
              <div className="space-y-2">
                {lowWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-orange-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-orange-600">{formatNumber(pub.impressions)} impr</span>
                      <span className="font-medium text-orange-700">{pub.win_rate.toFixed(1)}% win</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Blocked Publishers */}
        {blocked.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-red-700 mb-2">
              <Ban className="h-4 w-4" />
              Potentially blocked by pretargeting (0 reached, &gt;{formatNumber(blockedTrafficThreshold)} bids) - {blocked.length} publishers
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <div className="flex flex-wrap gap-2">
                {blocked.slice(0, 10).map(pub => (
                  <span
                    key={pub.publisher_id}
                    className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs"
                    title={`${formatNumber(pub.bid_requests ?? 0)} bid requests`}
                  >
                    {pub.publisher_name.length > 25 ? pub.publisher_name.slice(0, 25) + '...' : pub.publisher_name}
                  </span>
                ))}
              </div>
              <p className="text-xs text-red-600 mt-2">
                These publishers have bid requests but zero reached queries. This may be intentional; review against current pretargeting goals.
              </p>
            </div>
          </div>
        )}
        {blocked.length === 0 && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
            No high-volume blocked publishers detected in this seat snapshot.
          </div>
        )}
      </div>
    </div>
  );
}
