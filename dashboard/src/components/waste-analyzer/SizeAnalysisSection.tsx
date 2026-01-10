"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, AlertTriangle, Copy, CheckCircle, Upload, ArrowRight } from "lucide-react";
import { getQPSSizeCoverage } from "@/lib/api";
import { formatNumber } from "./FunnelCard";

interface SizeBarProps {
  size: string;
  requests: number;
  impressions: number;
  hasCreative: boolean;
  creativeCount: number;
  maxRequests: number;
}

/**
 * Size Bar visualization component.
 */
function SizeBar({
  size,
  requests,
  impressions,
  hasCreative,
  creativeCount,
  maxRequests
}: SizeBarProps) {
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

interface SizeAnalysisSectionProps {
  days: number;
  billingId?: string;
}

/**
 * Size Analysis Section.
 * Shows which sizes convert to impressions and identifies coverage gaps.
 */
export function SizeAnalysisSection({ days, billingId }: SizeAnalysisSectionProps) {
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
    ...coveredSizes.map(s => ({ ...s, hasCreative: true, requests: s.reached_queries || s.impressions })),
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
