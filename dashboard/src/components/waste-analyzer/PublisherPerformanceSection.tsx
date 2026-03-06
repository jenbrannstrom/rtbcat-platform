"use client";

import Link from "next/link";
import { BarChart3, Upload, ArrowRight, Trophy, AlertCircle, TrendingUp, Ban } from "lucide-react";
import type { PublisherPerformance } from "@/lib/api";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";
import { asNumber } from "@/lib/utils";
import { formatNumber } from "./FunnelCard";

interface PublisherPerformanceSectionProps {
  publishers: PublisherPerformance[];
  seatName?: string;
}

function formatSpendUsd(value: number | null | undefined): string {
  const amount = asNumber(value);
  if (amount <= 0) return "$0";
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  if (amount >= 100) return `$${amount.toFixed(0)}`;
  return `$${amount.toFixed(2)}`;
}

/**
 * Publisher Performance Section.
 * Shows publisher win rates categorized by performance tier.
 */
export function PublisherPerformanceSection({ publishers, seatName }: PublisherPerformanceSectionProps) {
  const { selectedBuyerId } = useAccount();
  const { t } = useTranslation();
  const importHref = toBuyerScopedPath("/import", selectedBuyerId);
  const hasPublisherData = publishers && publishers.length > 0;

  if (!hasPublisherData) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              {t.wasteAnalysis.publisherPerformance}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              {t.wasteAnalysis.publisherPerformanceSubtitle}
            </p>
          </div>
        </div>

        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg">
          <div className="flex items-start gap-4">
            <Upload className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-gray-700 mb-2">{t.wasteAnalysis.publisherDataNotAvailable}</h4>
              <p className="text-sm text-gray-600 mb-4">
                {t.wasteAnalysis.importPublisherPerformanceReportPrompt}
              </p>
              <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                <p className="font-semibold text-gray-700 mb-2">{t.wasteAnalysis.publisherPerfReportName}</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">{t.wasteAnalysis.dimensions}</p>
                    <ul className="text-gray-600">
                      <li>{t.wasteAnalysis.publisherPerfDimensionPublisherId}</li>
                      <li>{t.wasteAnalysis.publisherPerfDimensionPublisherName}</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">{t.wasteAnalysis.metrics}</p>
                    <ul className="text-gray-600">
                      <li>{t.wasteAnalysis.metricBidRequests}</li>
                      <li>{t.wasteAnalysis.metricReachedQueries}</li>
                      <li>{t.wasteAnalysis.metricImpressions}</li>
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

  // Categorize publishers by win rate
  const highWinRate = publishers.filter((p) => asNumber(p.win_rate) >= 40 && asNumber(p.impressions) > 0);
  const moderateWinRate = publishers.filter(
    (p) => asNumber(p.win_rate) >= 20 && asNumber(p.win_rate) < 40 && asNumber(p.impressions) > 0
  );
  const lowWinRate = publishers.filter((p) => asNumber(p.win_rate) < 20 && asNumber(p.impressions) > 0);
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
            {t.wasteAnalysis.publisherPerformance}
            <span className="text-xs font-normal bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              {seatName
                ? t.wasteAnalysis.overallForSeat.replace("{seatName}", seatName)
                : t.wasteAnalysis.seatOverall}
            </span>
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {t.wasteAnalysis.publisherPerformanceSeatSummary}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{publishers.length}</div>
          <div className="text-sm text-gray-500">{t.wasteAnalysis.publishers}</div>
        </div>
      </div>

      <div className="space-y-6">
        {/* High Win Rate */}
        {highWinRate.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-green-700 mb-2">
              <Trophy className="h-4 w-4" />
              {t.wasteAnalysis.highWinRateBucket.replace("{count}", String(highWinRate.length))}
            </div>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="space-y-2">
                {highWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-green-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-green-600">{formatSpendUsd(pub.spend_usd)} {t.campaigns.spend}</span>
                      <span className="text-green-600">{formatNumber(asNumber(pub.impressions))} {t.wasteAnalysis.imprShort}</span>
                      <span className="font-medium text-green-700">{asNumber(pub.win_rate).toFixed(1)}% {t.wasteAnalysis.winShort}</span>
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
              {t.wasteAnalysis.moderateWinRateBucket.replace("{count}", String(moderateWinRate.length))}
            </div>
            <div className="bg-yellow-50 rounded-lg p-3">
              <div className="space-y-2">
                {moderateWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-yellow-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-yellow-600">{formatSpendUsd(pub.spend_usd)} {t.campaigns.spend}</span>
                      <span className="text-yellow-600">{formatNumber(asNumber(pub.impressions))} {t.wasteAnalysis.imprShort}</span>
                      <span className="font-medium text-yellow-700">{asNumber(pub.win_rate).toFixed(1)}% {t.wasteAnalysis.winShort}</span>
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
              {t.wasteAnalysis.lowWinRateBucket.replace("{count}", String(lowWinRate.length))}
            </div>
            <div className="bg-orange-50 rounded-lg p-3">
              <div className="space-y-2">
                {lowWinRate.slice(0, 5).map(pub => (
                  <div key={pub.publisher_id} className="flex items-center justify-between text-sm">
                    <span className="text-orange-800 truncate max-w-[300px]" title={pub.publisher_name}>
                      {pub.publisher_name}
                    </span>
                    <div className="flex items-center gap-4">
                      <span className="text-orange-600">{formatSpendUsd(pub.spend_usd)} {t.campaigns.spend}</span>
                      <span className="text-orange-600">{formatNumber(asNumber(pub.impressions))} {t.wasteAnalysis.imprShort}</span>
                      <span className="font-medium text-orange-700">{asNumber(pub.win_rate).toFixed(1)}% {t.wasteAnalysis.winShort}</span>
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
              {t.wasteAnalysis.potentiallyBlockedBucket
                .replace("{threshold}", formatNumber(blockedTrafficThreshold))
                .replace("{count}", String(blocked.length))}
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <div className="flex flex-wrap gap-2">
                {blocked.slice(0, 10).map(pub => (
                  <span
                    key={pub.publisher_id}
                    className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs"
                    title={t.wasteAnalysis.bidRequestsTitle.replace("{count}", formatNumber(pub.bid_requests ?? 0))}
                  >
                    {pub.publisher_name.length > 25 ? pub.publisher_name.slice(0, 25) + '...' : pub.publisher_name}
                  </span>
                ))}
              </div>
              <p className="text-xs text-red-600 mt-2">
                {t.wasteAnalysis.blockedPublishersHint}
              </p>
            </div>
          </div>
        )}
        {blocked.length === 0 && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700">
            {t.wasteAnalysis.noHighVolumeBlockedPublishers}
          </div>
        )}
      </div>
    </div>
  );
}
