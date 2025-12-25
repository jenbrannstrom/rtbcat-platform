"use client";

import { useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw, AlertTriangle, TrendingUp, BarChart3, Globe,
  Copy, CheckCircle, ArrowRight, Trophy, AlertCircle, Ban, Upload
} from "lucide-react";
import { AccountEndpointsHeader } from "@/components/rtb/account-endpoints-header";
import { PretargetingConfigCard, type PretargetingConfig } from "@/components/rtb/pretargeting-config-card";
import { ConfigBreakdownPanel } from "@/components/rtb/config-breakdown-panel";
import { RecommendedOptimizationsPanel } from "@/components/rtb/recommended-optimizations-panel";
import {
  getQPSSummary, getQPSSizeCoverage, getRTBFunnel, getSpendStats,
  getPretargetingConfigs, syncPretargetingConfigs,
  type PublisherPerformance, type GeoPerformance, type PretargetingConfigResponse
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/account-context";

const PERIOD_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
];

// Utility to format large numbers
function formatNumber(num: number): string {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}B`;
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}

// The RTB Funnel Visualization - Focus on what hits the bidder
function FunnelCard({
  bidRequests,
  reached,
  impressions,
  days,
}: {
  bidRequests: number | null;
  reached: number | null;
  impressions: number;
  days: number;
}) {
  const hasFunnelData = bidRequests !== null && reached !== null;

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
                <a href="/setup?tab=import" className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                  Go to Import → <ArrowRight className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// Publisher Performance Section
function PublisherPerformanceSection({ publishers }: { publishers: PublisherPerformance[] }) {
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
              <a href="/setup?tab=import" className="inline-flex items-center gap-1 mt-3 text-blue-600 hover:text-blue-800 font-medium text-sm">
                Go to Import → <ArrowRight className="h-3 w-3" />
              </a>
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
  const blocked = publishers.filter(p => p.reached_queries === 0 && p.bid_requests > 100000);

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
              Blocked by Pretargeting (0 Reached) - {blocked.length} publishers
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <div className="flex flex-wrap gap-2">
                {blocked.slice(0, 10).map(pub => (
                  <span
                    key={pub.publisher_id}
                    className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs"
                    title={`${formatNumber(pub.bid_requests)} bid requests`}
                  >
                    {pub.publisher_name.length > 25 ? pub.publisher_name.slice(0, 25) + '...' : pub.publisher_name}
                  </span>
                ))}
              </div>
              <p className="text-xs text-red-600 mt-2">
                These publishers have traffic but pretargeting blocks all of it. Review if intentional.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Size Bar visualization component
function SizeBar({
  size,
  requests,
  impressions,
  hasCreative,
  creativeCount,
  maxRequests
}: {
  size: string;
  requests: number;
  impressions: number;
  hasCreative: boolean;
  creativeCount: number;
  maxRequests: number;
}) {
  const requestsWidth = maxRequests > 0 ? (requests / maxRequests * 100) : 0;
  const impressionsWidth = requests > 0 ? (impressions / requests * requestsWidth) : 0;
  const utilization = requests > 0 ? (impressions / requests * 100) : 0;

  return (
    <div className="flex items-center gap-4 py-2">
      <div className="w-24 font-mono text-sm text-gray-700 truncate" title={size}>{size}</div>
      <div className="flex-1 relative h-6 bg-gray-100 rounded overflow-hidden">
        <div
          className="absolute h-full bg-gray-300 rounded-l transition-all"
          style={{ width: `${requestsWidth}%` }}
        />
        <div
          className="absolute h-full bg-green-500 rounded-l transition-all"
          style={{ width: `${impressionsWidth}%` }}
        />
      </div>
      <div className="w-20 text-right text-sm">
        {formatNumber(requests)}
      </div>
      <div className="w-24 text-right text-sm">
        {hasCreative ? (
          <span className="text-green-600">{utilization.toFixed(1)}% util</span>
        ) : (
          <span className="text-red-600 flex items-center justify-end gap-1">
            <AlertTriangle className="h-3 w-3" />
            No creative
          </span>
        )}
      </div>
      <div className="w-16 text-right text-xs text-gray-500">
        {hasCreative ? `${creativeCount} ads` : '-'}
      </div>
    </div>
  );
}

// Size Analysis Section
function SizeAnalysisSection({ days, billingId }: { days: number; billingId?: string }) {
  const [copiedSizes, setCopiedSizes] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['size-coverage', days, billingId],
    queryFn: () => getQPSSizeCoverage(days, billingId),
  });

  const copyBlockSizes = useCallback(() => {
    if (data?.gaps) {
      const sizes = data.gaps.map(g => g.size).join(', ');
      navigator.clipboard.writeText(sizes);
      setCopiedSizes(true);
      setTimeout(() => setCopiedSizes(false), 2000);
    }
  }, [data]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="space-y-2">
            {[1,2,3,4,5].map(i => <div key={i} className="h-8 bg-gray-100 rounded" />)}
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load size analysis</span>
        </div>
      </div>
    );
  }

  const coveredSizes = data.covered_sizes || [];
  const gaps = data.gaps || [];

  const allSizes = [
    ...coveredSizes.map(s => ({ ...s, hasCreative: true, requests: s.impressions * 2 })),
    ...gaps.map(g => ({
      size: g.size,
      format: g.format,
      impressions: 0,
      spend_usd: 0,
      creative_count: 0,
      ctr_pct: 0,
      hasCreative: false,
      requests: g.queries_received
    }))
  ].sort((a, b) => b.requests - a.requests);

  const maxRequests = Math.max(...allSizes.map(s => s.requests), 1);
  const sizesWithoutCreative = gaps;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            Size Analysis
            {billingId && (
              <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                Filtered: {billingId}
              </span>
            )}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Which sizes convert to impressions?
            {billingId && <span className="ml-1 text-blue-600">(for selected config)</span>}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{data.coverage_rate_pct ?? 0}%</div>
          <div className="text-sm text-gray-500">coverage</div>
        </div>
      </div>

      {allSizes.length > 0 ? (
        <>
          {/* Legend */}
          <div className="flex items-center gap-6 mb-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gray-300 rounded" />
              <span className="text-gray-600">Requests</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded" />
              <span className="text-gray-600">Impressions</span>
            </div>
          </div>

          {/* Size bars */}
          <div className="space-y-1 mb-6">
            <div className="flex items-center gap-4 py-1 text-xs font-medium text-gray-500 border-b">
              <div className="w-24">Size</div>
              <div className="flex-1">Traffic Distribution</div>
              <div className="w-20 text-right">Requests</div>
              <div className="w-24 text-right">Win Rate</div>
              <div className="w-16 text-right">Creatives</div>
            </div>
            {allSizes.slice(0, 15).map((s) => (
              <SizeBar
                key={s.size}
                size={s.size}
                requests={s.requests}
                impressions={s.impressions}
                hasCreative={s.hasCreative}
                creativeCount={s.creative_count}
                maxRequests={maxRequests}
              />
            ))}
          </div>

          {/* Sizes without creatives alert */}
          {sizesWithoutCreative.length > 0 && (
            <div className="p-4 bg-red-50 rounded-lg border border-red-200">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-sm font-medium text-red-800 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    No creatives for {sizesWithoutCreative.length} sizes
                  </h4>
                  <p className="text-sm text-red-700 mt-1">
                    You're receiving traffic for sizes you can't bid on.
                    Either add creatives or remove these sizes from pretargeting.
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {sizesWithoutCreative.slice(0, 10).map(g => (
                      <span key={g.size} className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">
                        {g.size}
                      </span>
                    ))}
                    {sizesWithoutCreative.length > 10 && (
                      <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
                        +{sizesWithoutCreative.length - 10} more
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={copyBlockSizes}
                  className="flex items-center gap-1 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 rounded text-sm transition-colors"
                >
                  {copiedSizes ? <CheckCircle className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copiedSizes ? 'Copied!' : 'Copy sizes'}
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="p-6 border-2 border-dashed border-gray-200 rounded-lg">
          <div className="flex items-start gap-4">
            <Upload className="h-8 w-8 text-gray-400 flex-shrink-0" />
            <div>
              <h4 className="font-medium text-gray-700 mb-2">No Size Data Available</h4>
              <p className="text-sm text-gray-600 mb-4">
                Import a CSV with <strong>Creative size</strong> as the first dimension to see size breakdown.
              </p>
              <div className="p-3 bg-gray-50 rounded border border-gray-200 text-xs">
                <p className="font-semibold text-gray-700 mb-2">Required CSV format:</p>
                <p className="text-gray-600 mb-2">
                  In Google Authorized Buyers → Reporting → New Report:
                </p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Dimensions:</p>
                    <ul className="text-gray-600">
                      <li>1. Creative size</li>
                      <li>2. Day</li>
                      <li>3. Creative ID</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-semibold text-gray-500 mb-1">Metrics:</p>
                    <ul className="text-gray-600">
                      <li>✓ Reached queries</li>
                      <li>✓ Impressions</li>
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
      )}
    </div>
  );
}

// Zone mapping for geographic analysis
const ZONE_MAPPING: Record<string, string> = {
  'US': 'North America', 'CA': 'North America', 'MX': 'North America',
  'GB': 'Europe', 'DE': 'Europe', 'FR': 'Europe', 'IT': 'Europe', 'ES': 'Europe', 'NL': 'Europe', 'BE': 'Europe', 'PL': 'Europe', 'SE': 'Europe', 'NO': 'Europe', 'DK': 'Europe', 'FI': 'Europe', 'AT': 'Europe', 'CH': 'Europe', 'IE': 'Europe', 'PT': 'Europe',
  'BR': 'LATAM', 'AR': 'LATAM', 'CO': 'LATAM', 'CL': 'LATAM', 'PE': 'LATAM',
  'JP': 'Asia', 'CN': 'Asia', 'KR': 'Asia', 'IN': 'Asia', 'ID': 'Asia', 'TH': 'Asia', 'VN': 'Asia', 'PH': 'Asia', 'MY': 'Asia', 'SG': 'Asia', 'TW': 'Asia', 'HK': 'Asia',
  'AU': 'Oceania', 'NZ': 'Oceania',
  'ZA': 'Africa', 'NG': 'Africa', 'EG': 'Africa', 'KE': 'Africa',
  'SA': 'Middle East', 'AE': 'Middle East', 'IL': 'Middle East', 'TR': 'Middle East',
};

function getZone(countryCode: string): string {
  return ZONE_MAPPING[countryCode] || 'Other';
}

// Geographic Analysis Section - Using RTB Funnel Geo Data
function GeoAnalysisSection({ geos }: { geos: GeoPerformance[] }) {
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

  // Sort by auctions won (wins)
  const sortedGeos = [...geos].sort((a, b) => b.auctions_won - a.auctions_won);

  // Categorize by win rate
  const highWinRate = sortedGeos.filter(g => g.win_rate >= 80);
  const goodWinRate = sortedGeos.filter(g => g.win_rate >= 50 && g.win_rate < 80);
  const lowWinRate = sortedGeos.filter(g => g.win_rate < 50 && g.auctions_won > 0);

  // Calculate totals
  const totalBids = geos.reduce((sum, g) => sum + g.bids, 0);
  const totalReached = geos.reduce((sum, g) => sum + g.reached_queries, 0);
  const totalWins = geos.reduce((sum, g) => sum + g.auctions_won, 0);
  const overallWinRate = totalReached > 0 ? (totalWins / totalReached * 100) : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Globe className="h-5 w-5 text-green-600" />
            Geographic Performance
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Win rates by country
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
                  title={`Reached: ${formatNumber(geo.reached_queries)}, Wins: ${formatNumber(geo.auctions_won)}`}
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
                  title={`Reached: ${formatNumber(geo.reached_queries)}, Wins: ${formatNumber(geo.auctions_won)}`}
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
                <td className="py-2 text-right text-gray-900">{formatNumber(geo.bids)}</td>
                <td className="py-2 text-right text-blue-600">{formatNumber(geo.reached_queries)}</td>
                <td className="py-2 text-right text-green-600">{formatNumber(geo.auctions_won)}</td>
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

// Helper to transform API response to component props
function transformConfigToProps(
  apiConfig: PretargetingConfigResponse,
  performanceData?: { reached: number; impressions: number; win_rate: number; waste_rate: number }
): PretargetingConfig {
  const name = apiConfig.user_name || apiConfig.display_name || `Config ${apiConfig.billing_id}`;
  const reached = performanceData?.reached || 0;
  const impressions = performanceData?.impressions || 0;
  const win_rate = performanceData?.win_rate || 0;
  const waste_rate = performanceData?.waste_rate || 100;

  return {
    billing_id: apiConfig.billing_id || apiConfig.config_id,
    name,
    display_name: apiConfig.display_name,
    user_name: apiConfig.user_name,
    state: (apiConfig.state as 'ACTIVE' | 'SUSPENDED') || 'ACTIVE',
    formats: apiConfig.included_formats || [],
    platforms: apiConfig.included_platforms || [],
    sizes: apiConfig.included_sizes || [],
    included_geos: apiConfig.included_geos || [],
    reached,
    impressions,
    win_rate,
    waste_rate,
  };
}

function WasteAnalysisContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { selectedServiceAccountId } = useAccount();

  const initialDays = parseInt(searchParams.get("days") || "7", 10);
  const [days, setDays] = useState<number>(initialDays);
  const [expandedConfigId, setExpandedConfigId] = useState<string | null>(null);

  const updateUrl = useCallback(
    (newDays: number) => {
      const params = new URLSearchParams();
      params.set("days", String(newDays));
      router.replace(`/?${params.toString()}`, { scroll: false });
    },
    [router]
  );

  const handleDaysChange = useCallback(
    (newDays: number) => {
      setDays(newDays);
      updateUrl(newDays);
    },
    [updateUrl]
  );

  // Fetch QPS summary
  const {
    data: qpsSummary,
    isLoading: summaryLoading,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["qps-summary", days],
    queryFn: () => getQPSSummary(days),
  });

  // Fetch RTB funnel data from CSV files
  const {
    data: rtbFunnel,
    isLoading: funnelLoading,
    refetch: refetchFunnel,
  } = useQuery({
    queryKey: ["rtb-funnel"],
    queryFn: () => getRTBFunnel(),
  });

  // Fetch spend stats for CPM display (filtered by expanded config if selected)
  const {
    data: spendStats,
    refetch: refetchSpend,
  } = useQuery({
    queryKey: ["spend-stats", days, expandedConfigId],
    queryFn: () => getSpendStats(days, expandedConfigId || undefined),
  });

  // Fetch pretargeting configs
  const {
    data: pretargetingConfigs,
    isLoading: configsLoading,
    refetch: refetchConfigs,
  } = useQuery({
    queryKey: ["pretargeting-configs", selectedServiceAccountId],
    queryFn: () => getPretargetingConfigs({ service_account_id: selectedServiceAccountId || undefined }),
  });

  // Sync pretargeting mutation
  const syncConfigsMutation = useMutation({
    mutationFn: () => syncPretargetingConfigs({ service_account_id: selectedServiceAccountId || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pretargeting-configs", selectedServiceAccountId] });
    },
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchFunnel();
    refetchSpend();
    refetchConfigs();
  };

  // Use real funnel data if available
  const hasFunnelData = rtbFunnel?.funnel?.has_data ?? false;
  const bidRequests = hasFunnelData ? rtbFunnel!.funnel.total_bid_requests : null;
  const reached = hasFunnelData ? rtbFunnel!.funnel.total_reached_queries : null;
  const impressions = hasFunnelData ? rtbFunnel!.funnel.total_impressions : 0;

  // Publishers and Geos from RTB data
  const publishers = rtbFunnel?.publishers || [];
  const geos = rtbFunnel?.geos || [];

  // Build a map of billing_id to performance data from qpsSummary or rtbFunnel
  const configPerformanceMap = new Map<string, { reached: number; impressions: number; win_rate: number; waste_rate: number }>();
  // If we have config-level data from the funnel, use it (placeholder for now)

  // Transform configs for display
  const displayConfigs = (pretargetingConfigs || []).map(config =>
    transformConfigToProps(config, configPerformanceMap.get(config.billing_id || config.config_id))
  );
  const activeConfigsCount = displayConfigs.filter(c => c.state === 'ACTIVE').length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Waste Optimizer</h1>
          <p className="mt-1 text-sm text-gray-500">
            Understand your RTB funnel and optimize QPS waste
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* CPM Badge - show when spend data available */}
          {spendStats?.has_spend_data && spendStats.avg_cpm_usd && (
            <div className={cn(
              "px-3 py-1.5 rounded-lg",
              expandedConfigId
                ? "bg-blue-50 border border-blue-200"
                : "bg-green-50 border border-green-200"
            )}>
              <span className={cn(
                "text-xs uppercase tracking-wide",
                expandedConfigId ? "text-blue-600" : "text-green-600"
              )}>
                {expandedConfigId ? "Config CPM" : "Avg CPM"}
              </span>
              <span className={cn(
                "ml-2 text-sm font-bold",
                expandedConfigId ? "text-blue-700" : "text-green-700"
              )}>
                ${spendStats.avg_cpm_usd.toFixed(2)}
              </span>
            </div>
          )}

          {/* Period Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Period:</span>
            <div className="flex rounded-lg border border-gray-300 overflow-hidden">
              {PERIOD_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleDaysChange(option.value)}
                  className={cn(
                    "px-3 py-1.5 text-sm font-medium transition-colors",
                    days === option.value
                      ? "bg-blue-600 text-white"
                      : "bg-white text-gray-700 hover:bg-gray-50"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleRefresh}
            disabled={summaryLoading}
            className={cn(
              "flex items-center gap-2 px-4 py-2",
              "bg-white border border-gray-300 rounded-lg shadow-sm",
              "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "text-sm font-medium text-gray-700"
            )}
          >
            <RefreshCw className={cn("h-4 w-4", (summaryLoading || funnelLoading) && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Account Endpoints Header */}
      <AccountEndpointsHeader />

      {/* The Funnel */}
      <section>
        {(summaryLoading || funnelLoading) ? (
          <div className="bg-white rounded-xl border p-6 animate-pulse">
            <div className="h-6 bg-gray-200 rounded w-1/4 mb-4" />
            <div className="flex gap-4">
              {[1,2,3].map(i => <div key={i} className="flex-1 h-24 bg-gray-100 rounded" />)}
            </div>
          </div>
        ) : (
          <FunnelCard
            bidRequests={bidRequests}
            reached={reached}
            impressions={impressions || 0}
            days={days}
          />
        )}
      </section>

      {/* Recommended Optimizations Panel */}
      <section>
        <RecommendedOptimizationsPanel
          days={days}
          onConfigSelect={(billingId) => setExpandedConfigId(billingId)}
        />
      </section>

      {/* Pretargeting Configs Section */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Pretargeting Configs ({activeConfigsCount} active)
          </h2>
          <button
            onClick={() => syncConfigsMutation.mutate()}
            disabled={syncConfigsMutation.isPending}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-md",
              "bg-gray-100 text-gray-700 hover:bg-gray-200",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            <RefreshCw className={cn("h-4 w-4", syncConfigsMutation.isPending && "animate-spin")} />
            {syncConfigsMutation.isPending ? "Syncing..." : "Sync from Google"}
          </button>
        </div>

        {configsLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : displayConfigs.length === 0 ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
            <AlertTriangle className="h-8 w-8 text-yellow-500 mx-auto mb-3" />
            <h3 className="font-medium text-yellow-800 mb-2">No Pretargeting Configs</h3>
            <p className="text-sm text-yellow-700 mb-4">
              Click "Sync from Google" to fetch your pretargeting configurations from the Authorized Buyers API.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayConfigs.map(config => (
              <div key={config.billing_id}>
                <PretargetingConfigCard
                  config={config}
                  isExpanded={expandedConfigId === config.billing_id}
                  onToggleExpand={() => setExpandedConfigId(
                    prev => prev === config.billing_id ? null : config.billing_id
                  )}
                />
                <ConfigBreakdownPanel
                  billing_id={config.billing_id}
                  isExpanded={expandedConfigId === config.billing_id}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Publisher Performance */}
      <section>
        <PublisherPerformanceSection publishers={publishers} />
      </section>

      {/* Size Analysis */}
      <section>
        <SizeAnalysisSection days={days} billingId={expandedConfigId || undefined} />
      </section>

      {/* Geographic Analysis */}
      <section>
        <GeoAnalysisSection geos={geos} />
      </section>
    </div>
  );
}

function WasteAnalysisLoading() {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="mt-2 h-4 w-96 bg-gray-100 rounded animate-pulse" />
      </div>
      <div className="space-y-6">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-64 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<WasteAnalysisLoading />}>
      <WasteAnalysisContent />
    </Suspense>
  );
}
