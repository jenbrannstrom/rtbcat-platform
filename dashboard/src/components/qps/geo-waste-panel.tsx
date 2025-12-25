'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle, Globe, TrendingUp, XCircle, Eye } from 'lucide-react';
import { getGeoWaste } from '@/lib/api';
import { cn } from '@/lib/utils';

interface GeoWastePanelProps {
  days?: number;
}

const recommendationConfig = {
  EXCLUDE: {
    icon: XCircle,
    color: 'text-red-600',
    bg: 'bg-red-100',
    label: 'Exclude',
  },
  MONITOR: {
    icon: Eye,
    color: 'text-yellow-600',
    bg: 'bg-yellow-100',
    label: 'Monitor',
  },
  OK: {
    icon: CheckCircle,
    color: 'text-green-600',
    bg: 'bg-green-100',
    label: 'OK',
  },
  EXPAND: {
    icon: TrendingUp,
    color: 'text-blue-600',
    bg: 'bg-blue-100',
    label: 'Expand',
  },
};

export function GeoWastePanel({ days = 7 }: GeoWastePanelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['geo-waste', days],
    queryFn: () => getGeoWaste(days),
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-12 bg-gray-100 rounded" />
            ))}
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
          <span>Failed to load geo waste analysis</span>
        </div>
      </div>
    );
  }

  const excludeGeos = data.geos.filter(g => g.recommendation === 'EXCLUDE');

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Globe className="h-5 w-5 text-blue-600" />
            Geographic Analysis
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Identify geos with poor performance to exclude from pretargeting
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">{data.total_geos}</div>
          <div className="text-sm text-gray-500">geos analyzed</div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <div className="text-center p-3 bg-green-50 rounded-lg">
          <div className="text-xl font-bold text-green-600">{data.geos_performing_well}</div>
          <div className="text-xs text-gray-500">Performing Well</div>
        </div>
        <div className="text-center p-3 bg-yellow-50 rounded-lg">
          <div className="text-xl font-bold text-yellow-600">{data.geos_to_monitor}</div>
          <div className="text-xs text-gray-500">Monitor</div>
        </div>
        <div className="text-center p-3 bg-red-50 rounded-lg">
          <div className="text-xl font-bold text-red-600">{data.geos_to_exclude}</div>
          <div className="text-xs text-gray-500">Exclude</div>
        </div>
        <div className="text-center p-3 bg-orange-50 rounded-lg">
          <div className="text-xl font-bold text-orange-600">${data.wasted_spend_usd.toFixed(0)}</div>
          <div className="text-xs text-gray-500">Wasted</div>
        </div>
      </div>

      {/* Geos to Exclude */}
      {excludeGeos.length > 0 && (
        <div className="mb-6 p-4 bg-red-50 rounded-lg border border-red-200">
          <h4 className="text-sm font-medium text-red-800 mb-2 flex items-center gap-2">
            <XCircle className="h-4 w-4" />
            Exclude from Pretargeting ({excludeGeos.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {excludeGeos.map(geo => (
              <span
                key={geo.code}
                className="px-3 py-1 bg-red-100 text-red-800 rounded-full text-sm font-medium"
                title={`CTR: ${geo.ctr_pct}%, Spend: $${geo.spend_usd}`}
              >
                {geo.code} - {geo.country}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* All Geos Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 font-medium text-gray-600">Country</th>
              <th className="text-right py-2 font-medium text-gray-600">Impressions</th>
              <th className="text-right py-2 font-medium text-gray-600">Clicks</th>
              <th className="text-right py-2 font-medium text-gray-600">CTR</th>
              <th className="text-right py-2 font-medium text-gray-600">Spend</th>
              <th className="text-right py-2 font-medium text-gray-600">CPM</th>
              <th className="text-right py-2 font-medium text-gray-600">Action</th>
            </tr>
          </thead>
          <tbody>
            {data.geos.map(geo => {
              const config = recommendationConfig[geo.recommendation as keyof typeof recommendationConfig] ||
                             recommendationConfig.OK;
              const Icon = config.icon;

              return (
                <tr key={geo.code} className="border-b border-gray-100 last:border-0">
                  <td className="py-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">{geo.code}</span>
                      <span className="text-gray-500">{geo.country}</span>
                    </div>
                  </td>
                  <td className="py-2 text-right text-gray-900">
                    {geo.impressions.toLocaleString()}
                  </td>
                  <td className="py-2 text-right text-gray-900">
                    {geo.clicks.toLocaleString()}
                  </td>
                  <td className="py-2 text-right">
                    <span className={cn(
                      "font-medium",
                      geo.ctr_pct < 2 ? "text-red-600" : geo.ctr_pct > 5 ? "text-green-600" : "text-gray-900"
                    )}>
                      {geo.ctr_pct}%
                    </span>
                  </td>
                  <td className="py-2 text-right text-gray-900">
                    ${geo.spend_usd.toFixed(2)}
                  </td>
                  <td className="py-2 text-right text-gray-500">
                    ${geo.cpm.toFixed(2)}
                  </td>
                  <td className="py-2 text-right">
                    <span className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
                      config.bg, config.color
                    )}>
                      <Icon className="h-3 w-3" />
                      {config.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
