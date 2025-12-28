'use client';

import { useQuery } from '@tanstack/react-query';
import { X, Loader2, AlertTriangle, TrendingDown, Globe, Layers, Image } from 'lucide-react';
import { getAppDrilldown, type AppDrilldownResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

interface AppDrilldownModalProps {
  appName: string;
  billingId?: string;
  onClose: () => void;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString();
}

function WasteBar({ pct, height = 'h-2' }: { pct: number; height?: string }) {
  return (
    <div className={cn('w-full bg-gray-200 rounded-full overflow-hidden', height)}>
      <div
        className={cn(
          'h-full transition-all',
          pct < 50 && 'bg-green-400',
          pct >= 50 && pct < 70 && 'bg-yellow-400',
          pct >= 70 && pct < 90 && 'bg-orange-400',
          pct >= 90 && 'bg-red-500'
        )}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

export function AppDrilldownModal({ appName, billingId, onClose }: AppDrilldownModalProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['app-drilldown', appName, billingId],
    queryFn: () => getAppDrilldown(appName, billingId),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{appName}</h2>
            <p className="text-sm text-gray-500">Performance drill-down analysis</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
              <span className="ml-3 text-gray-500">Loading analysis...</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              Failed to load drill-down data
            </div>
          )}

          {data && !data.has_data && (
            <div className="text-center py-12 text-gray-500">
              No data available for this app
            </div>
          )}

          {data && data.has_data && data.summary && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-blue-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-blue-700">{formatNumber(data.summary.total_reached)}</div>
                  <div className="text-xs text-blue-600">Reached</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-green-700">{formatNumber(data.summary.total_impressions)}</div>
                  <div className="text-xs text-green-600">Impressions</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-purple-700">{data.summary.win_rate}%</div>
                  <div className="text-xs text-purple-600">Win Rate</div>
                </div>
                <div className={cn(
                  'rounded-lg p-4 text-center',
                  data.summary.waste_rate >= 70 ? 'bg-red-50' : 'bg-orange-50'
                )}>
                  <div className={cn(
                    'text-2xl font-bold',
                    data.summary.waste_rate >= 70 ? 'text-red-700' : 'text-orange-700'
                  )}>
                    {data.summary.waste_rate}%
                  </div>
                  <div className={cn(
                    'text-xs',
                    data.summary.waste_rate >= 70 ? 'text-red-600' : 'text-orange-600'
                  )}>Waste</div>
                </div>
              </div>

              {/* Waste Insight Alert */}
              {data.waste_insight && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-red-800">Waste Source Identified</h4>
                      <p className="text-sm text-red-700 mt-1">{data.waste_insight.message}</p>
                      <p className="text-sm text-red-600 mt-2 font-medium">
                        {data.waste_insight.recommendation}
                      </p>
                      <p className="text-xs text-red-500 mt-1">
                        ~{formatNumber(data.waste_insight.wasted_queries)} wasted queries
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* By Size Breakdown */}
              {data.by_size && data.by_size.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
                    <Layers className="h-4 w-4" />
                    By Size/Format
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-4 py-2 font-medium text-gray-600">Size</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Reached</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Win Rate</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">% Traffic</th>
                          <th className="px-4 py-2 font-medium text-gray-600 w-24">Waste</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_size.map((item, idx) => (
                          <tr
                            key={idx}
                            className={cn(
                              'hover:bg-gray-50',
                              item.is_wasteful && 'bg-red-50'
                            )}
                          >
                            <td className="px-4 py-2">
                              <span className={cn(
                                'font-medium',
                                item.is_wasteful && 'text-red-700'
                              )}>
                                {item.size}
                              </span>
                              {item.is_wasteful && (
                                <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                                  WASTEFUL
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-gray-600">
                              {formatNumber(item.reached)}
                            </td>
                            <td className={cn(
                              'px-4 py-2 text-right font-medium',
                              item.win_rate >= 40 && 'text-green-600',
                              item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                              item.win_rate < 20 && 'text-red-600'
                            )}>
                              {item.win_rate}%
                            </td>
                            <td className="px-4 py-2 text-right text-gray-500">
                              {item.pct_of_traffic}%
                            </td>
                            <td className="px-4 py-2">
                              <WasteBar pct={item.waste_pct} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* By Country Breakdown */}
              {data.by_country && data.by_country.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
                    <Globe className="h-4 w-4" />
                    By Country
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-4 py-2 font-medium text-gray-600">Country</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Reached</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Impressions</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Win Rate</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">% Traffic</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_country.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-2 font-medium">{item.country}</td>
                            <td className="px-4 py-2 text-right font-mono text-gray-600">
                              {formatNumber(item.reached)}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-gray-600">
                              {formatNumber(item.impressions)}
                            </td>
                            <td className={cn(
                              'px-4 py-2 text-right font-medium',
                              item.win_rate >= 40 && 'text-green-600',
                              item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                              item.win_rate < 20 && 'text-red-600'
                            )}>
                              {item.win_rate}%
                            </td>
                            <td className="px-4 py-2 text-right text-gray-500">
                              {item.pct_of_traffic}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* By Creative Breakdown */}
              {data.by_creative && data.by_creative.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
                    <Image className="h-4 w-4" />
                    By Creative (Top 10)
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-4 py-2 font-medium text-gray-600">Creative ID</th>
                          <th className="text-left px-4 py-2 font-medium text-gray-600">Size</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Reached</th>
                          <th className="text-right px-4 py-2 font-medium text-gray-600">Win Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_creative.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-4 py-2">
                              <span className="font-mono text-xs text-gray-600 truncate block max-w-[200px]" title={item.creative_id}>
                                {item.creative_id.length > 30 ? item.creative_id.slice(0, 30) + '...' : item.creative_id}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-gray-600">{item.size}</td>
                            <td className="px-4 py-2 text-right font-mono text-gray-600">
                              {formatNumber(item.reached)}
                            </td>
                            <td className={cn(
                              'px-4 py-2 text-right font-medium',
                              item.win_rate >= 40 && 'text-green-600',
                              item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                              item.win_rate < 20 && 'text-red-600'
                            )}>
                              {item.win_rate}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
