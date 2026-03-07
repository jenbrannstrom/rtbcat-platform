'use client';

import { useQuery } from '@tanstack/react-query';
import { X, Loader2, AlertTriangle, Globe, Layers, ImageIcon, Info, HelpCircle, Filter, Ban } from 'lucide-react';
import { getAppDrilldown } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { useTranslation } from '@/contexts/i18n-context';

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

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <Info
        className="h-3.5 w-3.5 text-gray-400 hover:text-gray-600 cursor-help inline ml-1"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      />
      {show && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg">
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </span>
  );
}

function formatCurrency(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

export function AppDrilldownModal({ appName, billingId, onClose }: AppDrilldownModalProps) {
  const { t } = useTranslation();
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
            <p className="text-sm text-gray-500">{t.creatives.drilldownAnalysis}</p>
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
              <span className="ml-3 text-gray-500">{t.creatives.loadingAnalysis}</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {t.creatives.failedToLoadDrilldownData}
            </div>
          )}

          {data && !data.has_data && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
              <div className="flex flex-col items-center gap-4">
                <AlertTriangle className="h-10 w-10 text-amber-500" />
                <div>
                  <h3 className="font-semibold text-amber-800 mb-2">
                    {t.creatives.noDrilldownDataFor.replace('{appName}', appName)}
                  </h3>
                  <p className="text-sm text-amber-700 max-w-md mx-auto">
                    {data.message || t.creatives.noDrilldownDataDefaultMessage}
                  </p>
                </div>
                <div className="bg-white/60 rounded-lg p-4 max-w-lg text-left">
                  <h4 className="text-xs font-semibold text-amber-800 mb-2">{t.creatives.whyMightThisHappen}</h4>
                  <ul className="text-xs text-amber-700 space-y-1">
                    <li className="flex items-start gap-2">
                      <span className="text-amber-500">•</span>
                      <span>{t.creatives.noCsvDataImportedForPeriod}</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-amber-500">•</span>
                      <span>{t.creatives.appNameMismatchBetweenReportTypes}</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-amber-500">•</span>
                      <span>{t.creatives.timeRangeIssueTryAdjustingDateFilter}</span>
                    </li>
                  </ul>
                  <p className="text-xs text-amber-600 mt-3 italic">
                    {t.creatives.importPerformanceDetailCsvTip}
                  </p>
                </div>
              </div>
            </div>
          )}

          {data && data.has_data && data.summary && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-5 gap-3">
                <div className="bg-blue-50 rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-blue-700">{formatNumber(data.summary.total_reached)}</div>
                  <div className="text-xs text-blue-600">
                    {t.dashboard.reached}
                    <InfoTooltip text={t.creatives.reachedTooltip} />
                  </div>
                </div>
                <div className="bg-green-50 rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-green-700">{formatNumber(data.summary.total_impressions)}</div>
                  <div className="text-xs text-green-600">{t.dashboard.impressions}</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-purple-700">{data.summary.win_rate}%</div>
                  <div className="text-xs text-purple-600">{t.dashboard.winRate}</div>
                </div>
                <div className="bg-cyan-50 rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-cyan-700">{formatNumber(data.summary.total_clicks)}</div>
                  <div className="text-xs text-cyan-600">{t.campaigns.clicks}</div>
                </div>
                <div className="bg-amber-50 rounded-lg p-3 text-center">
                  <div className="text-xl font-bold text-amber-700">{formatCurrency(data.summary.total_spend_usd)}</div>
                  <div className="text-xs text-amber-600">{t.campaigns.spend}</div>
                </div>
              </div>

              {/* Waste Insight Alert */}
              {data.waste_insight && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="font-medium text-red-800">{t.creatives.wasteSourceIdentified}</h4>
                      <p className="text-sm text-red-700 mt-1">{data.waste_insight.message}</p>
                      <p className="text-xs text-red-500 mt-1">
                        ~{t.creatives.bidRequestsWithoutWins.replace('{count}', formatNumber(data.waste_insight.wasted_queries))}
                      </p>

                      {/* Show actual bid filtering reasons if available, otherwise show generic hints */}
                      {data.bid_filtering && data.bid_filtering.length > 0 ? (
                        <div className="mt-3 pt-3 border-t border-red-200">
                          <h5 className="text-xs font-semibold text-red-800 flex items-center gap-1">
                            <Filter className="h-3 w-3" />
                            {t.creatives.bidFilteringReasonsFromGoogle}
                          </h5>
                          <div className="mt-2 space-y-1">
                            {data.bid_filtering.slice(0, 5).map((item, idx) => (
                              <div key={idx} className="flex items-center justify-between text-xs">
                                <span className="text-red-700 flex items-center gap-1">
                                  <Ban className="h-3 w-3 text-red-400" />
                                  {item.reason}
                                </span>
                                <span className="font-mono text-red-600">
                                  {formatNumber(item.bids_filtered)} ({item.pct_of_filtered}%)
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="mt-3 pt-3 border-t border-red-200">
                          <h5 className="text-xs font-semibold text-red-800 flex items-center gap-1">
                            <HelpCircle className="h-3 w-3" />
                            {t.creatives.whyAreWeLosingAuctions}
                          </h5>
                          <ul className="mt-2 text-xs text-red-700 space-y-1">
                            <li className="flex items-start gap-2">
                              <span className="text-red-400">•</span>
                              <span>{t.creatives.bidFloorHint}</span>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="text-red-400">•</span>
                              <span>{t.creatives.competitionHint.replace('{value}', data.waste_insight.value)}</span>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="text-red-400">•</span>
                              <span>{t.creatives.creativeFitHint}</span>
                            </li>
                          </ul>
                          <p className="mt-2 text-xs text-red-500 italic">
                            {t.creatives.uploadBidFilteringCsvTip}
                          </p>
                        </div>
                      )}

                      <div className="mt-3 p-2 bg-white/50 rounded border border-red-200">
                        <p className="text-xs text-red-800 font-medium">
                          💡 {data.waste_insight.recommendation}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Bid Filtering Full Breakdown */}
              {data.bid_filtering && data.bid_filtering.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
                    <Filter className="h-4 w-4" />
                    {t.creatives.whyBidsAreFiltered}
                    <InfoTooltip text={t.creatives.bidFilteringReportTooltip} />
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">{t.creatives.filteringReason}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.bidsFiltered}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.percentOfTotal}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.lostSpend}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.bid_filtering.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-2">
                              <span className="flex items-center gap-2">
                                <Ban className="h-3.5 w-3.5 text-red-400" />
                                <span className="font-medium text-gray-800">{item.reason}</span>
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                              {formatNumber(item.bids_filtered)}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-red-400"
                                    style={{ width: `${Math.min(item.pct_of_filtered, 100)}%` }}
                                  />
                                </div>
                                <span className="font-mono text-xs text-gray-600 w-12 text-right">
                                  {item.pct_of_filtered}%
                                </span>
                              </div>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-red-600">
                              {item.opportunity_cost_usd > 0 ? formatCurrency(item.opportunity_cost_usd) : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* By Size Breakdown */}
              {data.by_size && data.by_size.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-3">
                    <Layers className="h-4 w-4" />
                    {t.creatives.bySizeFormat}
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">{t.creatives.size}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.reached}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.impsShort}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.winRate}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.clicks}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.spend}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.cpm}</th>
                          <th className="px-3 py-2 font-medium text-gray-600 w-20">{t.pretargeting.waste}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_size.map((item, idx) => {
                          const cpm = item.impressions > 0 ? (item.spend_usd / item.impressions) * 1000 : 0;
                          return (
                            <tr
                              key={idx}
                              className={cn(
                                'hover:bg-gray-50',
                                item.is_wasteful && 'bg-red-50'
                              )}
                            >
                              <td className="px-3 py-2">
                                <span className={cn(
                                  'font-medium',
                                  item.is_wasteful && 'text-red-700'
                                )}>
                                  {item.size}
                                </span>
                                {item.is_wasteful && (
                                  <span className="ml-1 text-xs bg-red-100 text-red-700 px-1 py-0.5 rounded">
                                    !
                                  </span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.reached)}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.impressions)}
                              </td>
                              <td className={cn(
                                'px-3 py-2 text-right font-medium',
                                item.win_rate >= 40 && 'text-green-600',
                                item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                                item.win_rate < 20 && 'text-red-600'
                              )}>
                                {item.win_rate}%
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.clicks)}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {item.spend_usd > 0 ? formatCurrency(item.spend_usd) : '-'}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-500">
                                {cpm > 0 ? `$${cpm.toFixed(2)}` : '-'}
                              </td>
                              <td className="px-3 py-2">
                                <WasteBar pct={item.waste_pct} />
                              </td>
                            </tr>
                          );
                        })}
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
                    {t.creatives.byCountry}
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">{t.geo.country}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.reached}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.impsShort}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.winRate}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.clicks}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.spend}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.percentTraffic}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_country.map((item, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-2 font-medium">{item.country}</td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                              {formatNumber(item.reached)}
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                              {formatNumber(item.impressions)}
                            </td>
                            <td className={cn(
                              'px-3 py-2 text-right font-medium',
                              item.win_rate >= 40 && 'text-green-600',
                              item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                              item.win_rate < 20 && 'text-red-600'
                            )}>
                              {item.win_rate}%
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                              {formatNumber(item.clicks)}
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                              {item.spend_usd > 0 ? formatCurrency(item.spend_usd) : '-'}
                            </td>
                            <td className="px-3 py-2 text-right text-xs text-gray-500">
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
                    <ImageIcon className="h-4 w-4" />
                    {t.creatives.byCreativeTop10}
                  </h3>
                  <div className="bg-white border rounded-lg overflow-hidden overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">{t.creatives.creativeId}</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">{t.creatives.size}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.reached}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.impsShort}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.dashboard.winRate}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.clicks}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.creatives.ctr}</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">{t.campaigns.spend}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {data.by_creative.map((item, idx) => {
                          const ctr = item.impressions > 0 ? (item.clicks / item.impressions) * 100 : 0;
                          return (
                            <tr key={idx} className="hover:bg-gray-50">
                              <td className="px-3 py-2">
                                <span className="font-mono text-xs text-gray-600 truncate block max-w-[180px]" title={item.creative_id}>
                                  {item.creative_id.length > 25 ? item.creative_id.slice(0, 25) + '...' : item.creative_id}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-xs text-gray-600">{item.size}</td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.reached)}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.impressions)}
                              </td>
                              <td className={cn(
                                'px-3 py-2 text-right font-medium',
                                item.win_rate >= 40 && 'text-green-600',
                                item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                                item.win_rate < 20 && 'text-red-600'
                              )}>
                                {item.win_rate}%
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {formatNumber(item.clicks)}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-500">
                                {ctr > 0 ? `${ctr.toFixed(2)}%` : '-'}
                              </td>
                              <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">
                                {item.spend_usd > 0 ? formatCurrency(item.spend_usd) : '-'}
                              </td>
                            </tr>
                          );
                        })}
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
            {t.common.close}
          </button>
        </div>
      </div>
    </div>
  );
}
