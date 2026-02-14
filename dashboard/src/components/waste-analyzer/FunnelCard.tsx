"use client";

import Link from "next/link";
import { ArrowRight, Upload } from "lucide-react";

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
  // Only require reached to show funnel (bid_requests is optional)
  const hasFunnelData = reached !== null && reached > 0;

  const winRate = reached && impressions ? (impressions / reached * 100) : null;

  const secondsInPeriod = days * 86400;
  const reachedQps = reached ? reached / secondsInPeriod : null;
  const ips = impressions / secondsInPeriod;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-2">The RTB Funnel</h2>
      <p className="text-sm text-gray-500 mb-6">
        Traffic that reaches your bidder and converts to wins
      </p>

      {hasFunnelData ? (
        <>
          {/* Key Metrics - What Matters */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {/* Reached - Primary focus */}
            <div className="text-center p-5 bg-blue-50 rounded-xl border-2 border-blue-200">
              <div className="text-xs text-blue-600 uppercase tracking-wide mb-1">Reached Your Bidder</div>
              <div className="text-3xl font-bold text-blue-700">{formatNumber(reached!)}</div>
              <div className="text-lg font-semibold text-blue-500 mt-1">{reachedQps?.toLocaleString()} QPS</div>
            </div>

            {/* Win Rate - Key efficiency metric */}
            <div className="text-center p-5 bg-purple-50 rounded-xl border-2 border-purple-200">
              <div className="text-xs text-purple-600 uppercase tracking-wide mb-1">Win Rate</div>
              <div className="text-3xl font-bold text-purple-700">{winRate?.toFixed(1)}%</div>
              <div className="text-sm text-purple-500 mt-1">of reached traffic</div>
            </div>

            {/* Impressions Won */}
            <div className="text-center p-5 bg-green-50 rounded-xl border-2 border-green-200">
              <div className="text-xs text-green-600 uppercase tracking-wide mb-1">Impressions Won</div>
              <div className="text-3xl font-bold text-green-700">{formatNumber(impressions)}</div>
              <div className="text-sm text-green-500 mt-1">{ips.toFixed(0)} IPS</div>
            </div>
          </div>

          {/* Flow visualization */}
          <div className="flex items-center justify-center gap-2 mb-4 text-sm text-gray-500">
            <span className="text-blue-600 font-medium">{formatNumber(reached!)}</span>
            <ArrowRight className="h-4 w-4" />
            <span className="text-purple-600 font-medium">{winRate?.toFixed(1)}% win</span>
            <ArrowRight className="h-4 w-4" />
            <span className="text-green-600 font-medium">{formatNumber(impressions)}</span>
          </div>

          {/* Insight */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="text-sm">
              <strong className="text-blue-800">Your efficiency:</strong>
              <span className="text-blue-700 ml-1">
                {winRate?.toFixed(1)}% of traffic that reaches your bidder converts to impressions.
                {winRate && winRate >= 30 ? " This is healthy!" : " There may be room to improve."}
              </span>
            </div>
          </div>
        </>
      ) : (
        <>
          {/* No data state */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="text-center p-5 bg-gray-100 rounded-xl border-2 border-dashed border-gray-300">
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Reached</div>
              <div className="text-2xl font-bold text-gray-400">?</div>
              <div className="text-xs text-gray-400">Need RTB report</div>
            </div>

            <div className="text-center p-5 bg-gray-100 rounded-xl border-2 border-dashed border-gray-300">
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-gray-400">?</div>
              <div className="text-xs text-gray-400">Need RTB report</div>
            </div>

            <div className="text-center p-5 bg-green-50 rounded-xl border-2 border-green-200">
              <div className="text-xs text-green-600 uppercase tracking-wide mb-1">Impressions</div>
              <div className="text-2xl font-bold text-green-700">{formatNumber(impressions)}</div>
              <div className="text-xs text-green-500">{ips.toFixed(0)} IPS</div>
            </div>
          </div>

          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start gap-3">
              <Upload className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <strong>Import RTB performance data to see the full funnel</strong>
                <p className="mt-2 text-blue-700">
                  Create this report in <strong>Authorized Buyers → Reporting → New Report</strong>:
                </p>
                <div className="mt-3 p-3 bg-white rounded border border-blue-200">
                  <p className="font-medium text-blue-900 mb-2">Report: &quot;catscan-billing-config&quot;</p>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="font-semibold text-gray-600 mb-1">Dimensions (in order):</p>
                      <ol className="list-decimal list-inside text-gray-700">
                        <li>Day</li>
                        <li>Billing ID</li>
                        <li>Creative ID</li>
                        <li>Creative size</li>
                        <li>Creative format</li>
                      </ol>
                    </div>
                    <div>
                      <p className="font-semibold text-gray-600 mb-1">Metrics:</p>
                      <ul className="text-gray-700">
                        <li>✓ Reached queries</li>
                        <li>✓ Impressions</li>
                      </ul>
                      <p className="font-semibold text-gray-600 mt-2 mb-1">Schedule:</p>
                      <p className="text-gray-700">Daily, Yesterday</p>
                    </div>
                  </div>
                </div>
                <Link href="/setup?tab=import" className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                  Go to Import → <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
