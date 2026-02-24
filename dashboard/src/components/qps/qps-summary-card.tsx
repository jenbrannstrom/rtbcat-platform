'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle, Globe, LayoutGrid, DollarSign } from 'lucide-react';
import { getQPSSummary } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useAccount } from '@/contexts/account-context';
import { useTranslation } from '@/contexts/i18n-context';

interface QPSSummaryCardProps {
  days?: number;
}

export function QPSSummaryCard({ days = 7 }: QPSSummaryCardProps) {
  const { t } = useTranslation();
  const { selectedBuyerId } = useAccount();
  const { data, isLoading, error } = useQuery({
    queryKey: ['qps-summary', days, selectedBuyerId],
    queryFn: () => getQPSSummary(days, selectedBuyerId || undefined),
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-28 bg-gray-200 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span>{t.dashboard.failedToLoadQpsSummary}</span>
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
          <span className="text-sm font-medium text-gray-600">{t.dashboard.qpsSummarySizeCoverage}</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            {data.size_coverage.coverage_rate_pct}%
          </span>
          {data.size_coverage.sizes_missing > 0 && (
            <span className="text-sm text-orange-600">
              {t.dashboard.qpsSummaryGaps.replace('{count}', String(data.size_coverage.sizes_missing))}
            </span>
          )}
        </div>
        <div className="mt-1 text-sm text-gray-500">
          {t.dashboard.qpsSummarySizesCovered.replace('{count}', String(data.size_coverage.sizes_covered))}
        </div>
      </div>

      {/* Geo Efficiency */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Globe className="h-5 w-5 text-green-600" />
          <span className="text-sm font-medium text-gray-600">{t.dashboard.qpsSummaryGeoEfficiency}</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            {data.geo_efficiency.geos_analyzed}
          </span>
          <span className="text-sm text-gray-500">{t.dashboard.qpsSummaryGeosUnit}</span>
        </div>
        <div className="mt-1 text-sm">
          {data.geo_efficiency.geos_to_exclude > 0 ? (
            <span className="text-red-600">
              {t.dashboard.qpsSummaryGeosToExclude.replace('{count}', String(data.geo_efficiency.geos_to_exclude))}
            </span>
          ) : (
            <span className="text-green-600 flex items-center gap-1">
              <CheckCircle className="h-3 w-3" /> {t.dashboard.qpsSummaryAllPerformingWell}
            </span>
          )}
        </div>
      </div>

      {/* Wasted Spend */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <DollarSign className="h-5 w-5 text-orange-600" />
          <span className="text-sm font-medium text-gray-600">{t.dashboard.qpsSummaryWastedSpend}</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-gray-900">
            ${data.geo_efficiency.wasted_spend_usd.toFixed(0)}
          </span>
          <span className="text-sm text-gray-500">
            {t.dashboard.qpsSummaryPeriodDays.replace('{days}', String(days))}
          </span>
        </div>
        <div className="mt-1 text-sm text-gray-500">
          {t.dashboard.qpsSummaryWastePctOfTotal.replace('{pct}', String(data.geo_efficiency.waste_pct))}
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
          <span className="text-sm font-medium text-gray-600">{t.dashboard.qpsSummaryActionItems}</span>
        </div>
        {hasIssues ? (
          <div className="space-y-1">
            {data.action_items.geos_to_exclude > 0 && (
              <div className="text-sm text-amber-800">
                {t.dashboard.qpsSummaryExcludeGeos.replace('{count}', String(data.action_items.geos_to_exclude))}
              </div>
            )}
            {data.action_items.sizes_to_block > 0 && (
              <div className="text-sm text-amber-800">
                {t.dashboard.qpsSummaryBlockSizes.replace('{count}', String(data.action_items.sizes_to_block))}
              </div>
            )}
            {data.action_items.sizes_to_consider > 0 && (
              <div className="text-sm text-amber-800">
                {t.dashboard.qpsSummaryConsiderSizes.replace('{count}', String(data.action_items.sizes_to_consider))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-green-800">
            {t.dashboard.qpsSummaryNoImmediateActions}
          </div>
        )}
        {data.estimated_savings.geo_waste_monthly_usd > 0 && (
          <div className="mt-2 text-sm font-medium text-green-700">
            {t.dashboard.qpsSummarySaveMonthly.replace(
              '{amount}',
              data.estimated_savings.geo_waste_monthly_usd.toFixed(0)
            )}
          </div>
        )}
      </div>
    </div>
  );
}
