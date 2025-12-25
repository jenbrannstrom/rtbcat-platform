'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle, Globe, LayoutGrid, DollarSign } from 'lucide-react';
import { getQPSSummary } from '@/lib/api';
import { cn } from '@/lib/utils';

interface QPSSummaryCardProps {
  days?: number;
}

export function QPSSummaryCard({ days = 7 }: QPSSummaryCardProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['qps-summary', days],
    queryFn: () => getQPSSummary(days),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-28 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span>Failed to load QPS summary</span>
        </div>
      </div>
    );
  }

  const hasIssues = data.action_items.geos_to_exclude > 0 ||
                    data.action_items.sizes_to_block > 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Size Coverage */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <LayoutGrid className="h-5 w-5 text-blue-600" />
          <span className="text-sm font-medium text-gray-600">Size Coverage</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            {data.size_coverage.coverage_rate_pct}%
          </span>
          {data.size_coverage.sizes_missing > 0 && (
            <span className="text-sm text-orange-600">
              {data.size_coverage.sizes_missing} gaps
            </span>
          )}
        </div>
        <div className="mt-1 text-sm text-gray-500">
          {data.size_coverage.sizes_covered} sizes covered
        </div>
      </div>

      {/* Geo Efficiency */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Globe className="h-5 w-5 text-green-600" />
          <span className="text-sm font-medium text-gray-600">Geo Efficiency</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            {data.geo_efficiency.geos_analyzed}
          </span>
          <span className="text-sm text-gray-500">geos</span>
        </div>
        <div className="mt-1 text-sm">
          {data.geo_efficiency.geos_to_exclude > 0 ? (
            <span className="text-red-600">
              {data.geo_efficiency.geos_to_exclude} to exclude
            </span>
          ) : (
            <span className="text-green-600 flex items-center gap-1">
              <CheckCircle className="h-3 w-3" /> All performing well
            </span>
          )}
        </div>
      </div>

      {/* Wasted Spend */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <DollarSign className="h-5 w-5 text-orange-600" />
          <span className="text-sm font-medium text-gray-600">Wasted Spend</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            ${data.geo_efficiency.wasted_spend_usd.toFixed(0)}
          </span>
          <span className="text-sm text-gray-500">/ {days} days</span>
        </div>
        <div className="mt-1 text-sm text-gray-500">
          {data.geo_efficiency.waste_pct}% of total
        </div>
      </div>

      {/* Action Items */}
      <div className={cn(
        "rounded-lg border p-4",
        hasIssues ? "bg-amber-50 border-amber-200" : "bg-green-50 border-green-200"
      )}>
        <div className="flex items-center gap-2 mb-2">
          {hasIssues ? (
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          ) : (
            <CheckCircle className="h-5 w-5 text-green-600" />
          )}
          <span className="text-sm font-medium text-gray-600">Action Items</span>
        </div>
        {hasIssues ? (
          <div className="space-y-1">
            {data.action_items.geos_to_exclude > 0 && (
              <div className="text-sm text-amber-800">
                Exclude {data.action_items.geos_to_exclude} geos
              </div>
            )}
            {data.action_items.sizes_to_block > 0 && (
              <div className="text-sm text-amber-800">
                Block {data.action_items.sizes_to_block} sizes
              </div>
            )}
            {data.action_items.sizes_to_consider > 0 && (
              <div className="text-sm text-amber-800">
                Consider {data.action_items.sizes_to_consider} sizes
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-green-800">
            No immediate actions needed
          </div>
        )}
        {data.estimated_savings.geo_waste_monthly_usd > 0 && (
          <div className="mt-2 text-sm font-medium text-green-700">
            Save ~${data.estimated_savings.geo_waste_monthly_usd.toFixed(0)}/mo
          </div>
        )}
      </div>
    </div>
  );
}
