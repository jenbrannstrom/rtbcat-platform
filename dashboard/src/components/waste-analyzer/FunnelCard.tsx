"use client";

import Link from "next/link";
import { ArrowRight, Upload } from "lucide-react";
import { useAccount } from "@/contexts/account-context";
import { useTranslation } from "@/contexts/i18n-context";
import { toBuyerScopedPath } from "@/lib/buyer-routes";

/**
 * Utility to format large numbers with K/M/B suffixes.
 */
export function formatNumber(num: number): string {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}B`;
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}

interface FunnelCardProps {
  bidRequests: number | null;
  reached: number | null;
  impressions: number;
  days: number;
}

/**
 * The RTB Funnel Visualization - Focus on what hits the bidder.
 * Shows traffic reaching the bidder and conversion to impressions.
 */
export function FunnelCard({
  bidRequests,
  reached,
  impressions,
  days,
}: FunnelCardProps) {
  const { selectedBuyerId } = useAccount();
  const { t } = useTranslation();
  const importHref = toBuyerScopedPath("/import", selectedBuyerId);
  // Only require reached to show funnel (bid_requests is optional)
  const hasFunnelData = reached !== null && reached > 0;

  const winRate = reached && impressions ? (impressions / reached * 100) : null;

  const secondsInPeriod = days * 86400;
  const reachedQps = reached ? reached / secondsInPeriod : null;
  const ips = impressions / secondsInPeriod;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-2">{t.wasteAnalysis.funnelTitle}</h2>
      <p className="text-sm text-gray-500 mb-6">
        {t.wasteAnalysis.funnelSubtitle}
      </p>

      {hasFunnelData ? (
        <>
          {/* Key Metrics - What Matters */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {/* Reached - Primary focus */}
            <div className="text-center p-5 bg-blue-50 rounded-xl border-2 border-blue-200">
              <div className="text-xs text-blue-600 uppercase tracking-wide mb-1">{t.wasteAnalysis.reachedYourBidder}</div>
              <div className="text-3xl font-bold text-blue-700">{formatNumber(reached!)}</div>
              <div className="text-lg font-semibold text-blue-500 mt-1">{reachedQps?.toLocaleString()} {t.wasteAnalysis.qps}</div>
            </div>

            {/* Win Rate - Key efficiency metric */}
            <div className="text-center p-5 bg-purple-50 rounded-xl border-2 border-purple-200">
              <div className="text-xs text-purple-600 uppercase tracking-wide mb-1">{t.wasteAnalysis.winRate}</div>
              <div className="text-3xl font-bold text-purple-700">{winRate?.toFixed(1)}%</div>
              <div className="text-sm text-purple-500 mt-1">{t.wasteAnalysis.ofReachedTraffic}</div>
            </div>

            {/* Impressions Won */}
            <div className="text-center p-5 bg-green-50 rounded-xl border-2 border-green-200">
              <div className="text-xs text-green-600 uppercase tracking-wide mb-1">{t.wasteAnalysis.impressionsWon}</div>
              <div className="text-3xl font-bold text-green-700">{formatNumber(impressions)}</div>
              <div className="text-sm text-green-500 mt-1">{ips.toFixed(0)} {t.wasteAnalysis.ips}</div>
            </div>
          </div>

          {/* Flow visualization */}
          <div className="flex items-center justify-center gap-2 mb-4 text-sm text-gray-500">
            <span className="text-blue-600 font-medium">{formatNumber(reached!)}</span>
            <ArrowRight className="h-4 w-4" />
            <span className="text-purple-600 font-medium">{winRate?.toFixed(1)}% {t.wasteAnalysis.winShort}</span>
            <ArrowRight className="h-4 w-4" />
            <span className="text-green-600 font-medium">{formatNumber(impressions)}</span>
          </div>

          {/* Insight */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="text-sm">
              <strong className="text-blue-800">{t.wasteAnalysis.yourEfficiency}</strong>
              <span className="text-blue-700 ml-1">
                {t.wasteAnalysis.efficiencySentence.replace("{rate}", String(winRate?.toFixed(1) ?? "0"))}
                {winRate && winRate >= 30 ? ` ${t.wasteAnalysis.efficiencyHealthy}` : ` ${t.wasteAnalysis.efficiencyNeedsImprovement}`}
              </span>
            </div>
          </div>
        </>
      ) : (
        <>
          {/* No data state */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center p-5 bg-gray-100 rounded-xl border-2 border-dashed border-gray-300">
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">{t.wasteAnalysis.reached}</div>
              <div className="text-2xl font-bold text-gray-400">?</div>
              <div className="text-xs text-gray-400">{t.wasteAnalysis.needRtbReport}</div>
            </div>

            <div className="text-center p-5 bg-gray-100 rounded-xl border-2 border-dashed border-gray-300">
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">{t.wasteAnalysis.winRate}</div>
              <div className="text-2xl font-bold text-gray-400">?</div>
              <div className="text-xs text-gray-400">{t.wasteAnalysis.needRtbReport}</div>
            </div>

            <div className="text-center p-5 bg-green-50 rounded-xl border-2 border-green-200">
              <div className="text-xs text-green-600 uppercase tracking-wide mb-1">{t.wasteAnalysis.impressions}</div>
              <div className="text-2xl font-bold text-green-700">{formatNumber(impressions)}</div>
              <div className="text-xs text-green-500">{ips.toFixed(0)} {t.wasteAnalysis.ips}</div>
            </div>
          </div>

          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start gap-3">
              <Upload className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <strong>{t.wasteAnalysis.importRtbPerformanceToSeeFunnel}</strong>
                <p className="mt-2 text-blue-700">
                  {t.wasteAnalysis.createThisReportIn} <strong>{t.wasteAnalysis.authorizedBuyersReportingNewReport}</strong>:
                </p>
                <div className="mt-3 p-3 bg-white rounded border border-blue-200">
                  <p className="font-medium text-blue-900 mb-2">{t.wasteAnalysis.funnelReportName}</p>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="font-semibold text-gray-600 mb-1">{t.wasteAnalysis.dimensionsInOrder}</p>
                      <ol className="list-decimal list-inside text-gray-700">
                        <li>{t.wasteAnalysis.dimensionDay}</li>
                        <li>{t.wasteAnalysis.dimensionPretargetingConfigBillingId}</li>
                        <li>{t.wasteAnalysis.dimensionCreativeId}</li>
                        <li>{t.wasteAnalysis.dimensionCreativeSize}</li>
                        <li>{t.wasteAnalysis.dimensionCreativeFormat}</li>
                      </ol>
                    </div>
                    <div>
                      <p className="font-semibold text-gray-600 mb-1">{t.wasteAnalysis.metrics}</p>
                      <ul className="text-gray-700">
                        <li>{t.wasteAnalysis.metricReachedQueries}</li>
                        <li>{t.wasteAnalysis.metricImpressions}</li>
                      </ul>
                      <p className="font-semibold text-gray-600 mt-2 mb-1">{t.wasteAnalysis.schedule}</p>
                      <p className="text-gray-700">{t.wasteAnalysis.dailyYesterday}</p>
                    </div>
                  </div>
                </div>
                <Link href={importHref} className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                  {t.wasteAnalysis.goToImport} <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
