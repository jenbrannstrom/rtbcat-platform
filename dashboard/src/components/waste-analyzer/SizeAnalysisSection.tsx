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
  buyerId?: string;
}

/**
 * Size Analysis Section.
 * Shows which sizes convert to impressions and identifies coverage gaps.
 */
export function SizeAnalysisSection({ days, buyerId }: SizeAnalysisSectionProps) {
  const [copiedSizes, setCopiedSizes] = useState(false);
  const MIN_VISIBLE_WASTED_QPS = 0.01;

  const { data, isLoading, error } = useQuery({
    queryKey: ['size-coverage', days, buyerId],
    queryFn: () => getQPSSizeCoverage(days, undefined, buyerId),
  });

  const gaps = data?.gaps || [];
  const noCreativeRows = gaps
    .map((g) => {
      const daily = g.daily_estimate || g.queries_received || 0;
      return {
        size: g.size,
        reached: g.queries_received || 0,
        impressions: 0,
        wastedQps: daily / 86400,
      };
    })
    .filter((row) => row.wastedQps >= MIN_VISIBLE_WASTED_QPS)
    .sort((a, b) => b.wastedQps - a.wastedQps);

  const copyBlockSizes = useCallback(() => {
    if (noCreativeRows.length > 0) {
      const sizes = noCreativeRows.map((row) => row.size).join(', ');
      navigator.clipboard.writeText(sizes);
      setCopiedSizes(true);
      setTimeout(() => setCopiedSizes(false), 2000);
    }
  }, [noCreativeRows]);

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
  const sizesWithoutCreativeCount = gaps.length;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            Size Analysis
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Which sizes convert to impressions?
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{data.coverage_rate_pct ?? 0}%</div>
          <div className="text-sm text-gray-500">coverage</div>
        </div>
      </div>

      {allSizes.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
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
            <div className="space-y-1">
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
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-900">No Creatives</h4>
              {noCreativeRows.length > 0 && (
                <button
                  onClick={copyBlockSizes}
                  className="flex items-center gap-1 px-2.5 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded text-xs transition-colors"
                >
                  {copiedSizes ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                  {copiedSizes ? 'Copied!' : 'Copy sizes'}
                </button>
              )}
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Showing material waste only ({`>= ${MIN_VISIBLE_WASTED_QPS.toFixed(2)} QPS`}). Add creatives or remove sizes from pretargeting.
            </p>
            <div className="border rounded-lg overflow-hidden">
              <div className="grid grid-cols-4 gap-2 px-3 py-2 text-xs font-medium text-gray-500 bg-gray-50 border-b">
                <div>Size</div>
                <div className="text-right">Reached</div>
                <div className="text-right">Imp</div>
                <div className="text-right">Wasted QPS</div>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {noCreativeRows.length === 0 && (
                  <div className="px-3 py-3 text-sm text-gray-400">
                    {sizesWithoutCreativeCount > 0
                      ? `No material waste detected (all gaps below ${MIN_VISIBLE_WASTED_QPS.toFixed(2)} QPS).`
                      : 'No gaps detected.'}
                  </div>
                )}
                {noCreativeRows.map((row) => (
                  <div key={row.size} className="grid grid-cols-4 gap-2 px-3 py-2 text-sm border-b last:border-b-0">
                    <div className="font-mono text-gray-800">{row.size}</div>
                    <div className="text-right text-gray-700">{formatNumber(row.reached)}</div>
                    <div className="text-right text-gray-700">{formatNumber(row.impressions)}</div>
                    <div className="text-right text-red-700">{row.wastedQps.toFixed(2)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
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
