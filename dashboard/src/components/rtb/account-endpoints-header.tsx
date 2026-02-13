'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRTBEndpoints, getPretargetingConfigs, syncRTBEndpoints } from '@/lib/api';
import { Server, AlertTriangle, Globe, Info, Loader2 } from 'lucide-react';
import { useAccount } from '@/contexts/account-context';
import { useState, useEffect, useRef } from 'react';

// Helper to format trading location for display
function formatLocation(location: string | null): string {
  if (!location) return 'Unknown';
  const map: Record<string, string> = {
    'US_WEST': 'US West',
    'US_EAST': 'US East',
    'EUROPE': 'Europe',
    'ASIA': 'Asia',
    'TRADING_LOCATION_UNSPECIFIED': 'Unspecified',
  };
  return map[location] || location;
}

// Helper to format QPS - show exact amounts with commas
function formatQPS(qps: number | null): string {
  if (qps === null) return 'Unlimited';
  return qps.toLocaleString();
}

// Helper to format large numbers
function formatNumber(num: number): string {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}B`;
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toLocaleString();
}

function formatIsoDate(value: string | null | undefined): string {
  if (!value) return "N/A";
  return value;
}

interface AccountEndpointsHeaderProps {
  funnelData?: {
    reached: number | null;
    impressions: number;
    deliveryWinRate: number | null;
    auctionWinRate: number | null;
    auctionsWon: number | null;
    filteredBids: number | null;
    filteredBidRate: number | null;
    requestedEndDate?: string | null;
    homeSeatDataThrough?: string | null;
    bidstreamDataThrough?: string | null;
  };
}

export function AccountEndpointsHeader({ funnelData }: AccountEndpointsHeaderProps) {
  const { selectedBuyerId, selectedServiceAccountId } = useAccount();
  const [showQpsInfo, setShowQpsInfo] = useState(false);
  const [showDataQualityInfo, setShowDataQualityInfo] = useState(false);
  const queryClient = useQueryClient();

  // Use buyer_id for filtering - RTB endpoints are looked up via buyer -> bidder mapping
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rtb-endpoints', selectedBuyerId],
    queryFn: () => getRTBEndpoints({ buyer_id: selectedBuyerId || undefined }),
    enabled: !!selectedBuyerId,
  });

  // Also fetch pretargeting configs to count active ones
  const { data: configsData } = useQuery({
    queryKey: ['pretargeting-configs', selectedBuyerId],
    queryFn: () => getPretargetingConfigs({ buyer_id: selectedBuyerId || undefined }),
    enabled: !!selectedBuyerId,
    retry: 0,
  });

  // Mutation to sync endpoints from Google API
  const syncMutation = useMutation({
    mutationFn: () => syncRTBEndpoints({ service_account_id: selectedServiceAccountId || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rtb-endpoints'] });
      refetch();
    },
  });

  // Auto-sync endpoints on mount if none exist
  const hasSynced = useRef(false);
  useEffect(() => {
    if (!isLoading && !hasSynced.current && data && !data.endpoints?.length && selectedServiceAccountId) {
      hasSynced.current = true;
      syncMutation.mutate();
    }
  }, [isLoading, data, selectedServiceAccountId]);

  if (!selectedBuyerId) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
        Select a seat to load RTB endpoints and pretargeting metrics.
      </div>
    );
  }

  const activeConfigsCount = configsData?.filter(c => c.state === 'ACTIVE').length || 0;

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border p-4">
        <div className="animate-pulse flex justify-between items-start">
          <div className="space-y-3 flex-1">
            <div className="h-5 bg-gray-200 rounded w-48" />
            <div className="flex gap-4">
              <div className="h-16 bg-gray-100 rounded w-40" />
              <div className="h-16 bg-gray-100 rounded w-40" />
              <div className="h-16 bg-gray-100 rounded w-40" />
            </div>
          </div>
          <div className="h-8 bg-gray-200 rounded w-20" />
        </div>
      </div>
    );
  }

  // Error state - could be API not running or actual error
  if (error) {
    const isConnectionError = error instanceof Error &&
      (error.message.includes('fetch') || error.message.includes('network') || error.message.includes('500'));

    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Server className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-medium text-gray-700">RTB Endpoints</h3>
            <p className="text-sm text-gray-500 mt-1">
              {isConnectionError
                ? "Unable to connect to API server. Make sure the backend is running."
                : "Failed to load endpoint data. Try refreshing the page."}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // No endpoints - show syncing state or error
  if (!data?.endpoints?.length) {
    // If syncing, show loading indicator
    if (syncMutation.isPending) {
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
            <div>
              <h3 className="font-medium text-blue-800">Syncing RTB Endpoints</h3>
              <p className="text-sm text-blue-700 mt-1">
                Fetching endpoint configuration from Google Authorized Buyers API...
              </p>
            </div>
          </div>
        </div>
      );
    }

    // If sync failed, show error
    if (syncMutation.isError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-800">Failed to Sync Endpoints</h3>
              <p className="text-sm text-red-700 mt-1">
                {syncMutation.error instanceof Error ? syncMutation.error.message : 'Could not fetch endpoint configuration. Check your service account credentials.'}
              </p>
            </div>
          </div>
        </div>
      );
    }

    // No endpoints and not syncing - probably no service account configured
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Server className="h-5 w-5 text-gray-400 mt-0.5" />
          <div>
            <h3 className="font-medium text-gray-700">No RTB Endpoints</h3>
            <p className="text-sm text-gray-500 mt-1">
              Endpoints will sync automatically when a service account is configured.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Calculate funnel metrics
  const hasFunnelData = funnelData && funnelData.reached !== null && funnelData.reached > 0;

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex gap-6">
        {/* Left: Endpoints with Total QPS as sum row */}
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-3">
            <Server className="h-4 w-4 text-gray-500" />
            <h3 className="font-semibold text-gray-900">RTB Endpoints</h3>
            {data.bidder_id && (
              <span className="text-xs text-gray-500">
                · {data.account_name || data.bidder_id}
              </span>
            )}
            {selectedBuyerId && (
              <span className="text-xs text-gray-500">
                · {selectedBuyerId}
              </span>
            )}
          </div>

          <div className="space-y-1">
            {data.endpoints.map((endpoint) => (
              <div
                key={endpoint.endpoint_id}
                className="flex items-center justify-between px-3 py-1.5 bg-gray-50 rounded text-sm"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <Globe className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                  <span className="font-medium text-gray-700 flex-shrink-0 w-16 text-sm">
                    {formatLocation(endpoint.trading_location)}
                  </span>
                  <span className="text-xs text-gray-400 font-mono truncate" title={endpoint.url}>
                    {endpoint.url.replace(/^https?:\/\//, '')}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-gray-500">
                    {endpoint.bid_protocol?.replace('OPENRTB_', 'OpenRTB ').replace('_', '.') || 'Unknown'}
                  </span>
                  <span className="font-medium text-gray-900 min-w-[80px] text-right text-sm">
                    {formatQPS(endpoint.maximum_qps)} QPS
                  </span>
                </div>
              </div>
            ))}

            {/* Total QPS Row - styled as a sum */}
            <div className="flex items-center justify-between px-3 py-2 mt-2 bg-blue-50 border-2 border-blue-200 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-blue-800">Allocated QPS Cap</span>
                <div className="relative">
                  <button
                    onClick={() => setShowQpsInfo(!showQpsInfo)}
                    onMouseEnter={() => setShowQpsInfo(true)}
                    onMouseLeave={() => setShowQpsInfo(false)}
                    className="p-0.5 hover:bg-blue-100 rounded-full transition-colors"
                    aria-label="QPS allocation info"
                  >
                    <Info className="h-3.5 w-3.5 text-blue-400" />
                  </button>
                  {showQpsInfo && (
                    <div className="absolute left-0 top-6 w-72 p-3 bg-white border border-gray-200 rounded-lg shadow-lg z-10 text-xs text-gray-600">
                      <p className="font-medium text-gray-900 mb-1">QPS Allocation</p>
                      <p>
                        This is your configured QPS cap (invited capacity), not guaranteed incoming traffic.
                        Actual delivery is spend-constrained and controlled by Google throttling. Use observed delivery
                        metrics as directional, especially when CSV imports are missing on some dates.
                      </p>
                    </div>
                  )}
                </div>
                {data.synced_at && (
                  <span className="text-xs text-blue-400 ml-2">
                    · {new Date(data.synced_at).toLocaleString()}
                  </span>
                )}
              </div>
              <span className="text-lg font-bold text-blue-900 min-w-[80px] text-right">
                {formatQPS(data.total_qps_allocated)}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Compact Funnel Metrics */}
        <div className="w-72 flex flex-col justify-center">
          {hasFunnelData ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between px-2">
                <span className="text-[10px] uppercase tracking-wide text-gray-500">Observed Delivery</span>
                <div className="relative">
                  <button
                    onClick={() => setShowDataQualityInfo(!showDataQualityInfo)}
                    onMouseEnter={() => setShowDataQualityInfo(true)}
                    onMouseLeave={() => setShowDataQualityInfo(false)}
                    className="p-0.5 hover:bg-gray-100 rounded-full transition-colors"
                    aria-label="Observed delivery data quality"
                  >
                    <Info className="h-3.5 w-3.5 text-gray-400" />
                  </button>
                  {showDataQualityInfo && (
                    <div className="absolute right-0 top-6 w-80 p-3 bg-white border border-gray-200 rounded-lg shadow-lg z-10 text-xs text-gray-600">
                      <p className="font-medium text-gray-900 mb-1">Configured vs Observed</p>
                      <p>
                        Endpoint rows above come from Google endpoint configuration (`/settings/endpoints`).
                        Delivery metrics here come from imported CSV/precompute data. Missing or delayed CSV days can
                        skew observed region comparisons, so treat these comparisons as directional and verify over
                        longer windows before making hard decisions.
                      </p>
                    </div>
                  )}
                </div>
              </div>
              {funnelData?.requestedEndDate && (
                <div className="px-2 text-[10px] text-gray-500">
                  Requested through {formatIsoDate(funnelData.requestedEndDate)}
                </div>
              )}
              {funnelData?.homeSeatDataThrough && (
                <div className="px-2 text-[10px] text-amber-700">
                  Delivery data through {formatIsoDate(funnelData.homeSeatDataThrough)}
                </div>
              )}
              {funnelData?.bidstreamDataThrough && (
                <div className="px-2 text-[10px] text-indigo-700">
                  Auction-funnel data through {formatIsoDate(funnelData.bidstreamDataThrough)}
                </div>
              )}
              {/* Reached */}
              <div className="flex items-center justify-between px-3 py-1.5 bg-blue-50 rounded border border-blue-100">
                <span className="text-xs text-blue-600 uppercase tracking-wide">Reached Queries</span>
                <span className="text-sm font-bold text-blue-700">{formatNumber(funnelData!.reached!)}</span>
              </div>
              {/* Impressions */}
              <div className="flex items-center justify-between px-3 py-1.5 bg-green-50 rounded border border-green-100">
                <span className="text-xs text-green-600 uppercase tracking-wide">Impressions</span>
                <span className="text-sm font-bold text-green-700">{formatNumber(funnelData!.impressions)}</span>
              </div>
              {/* Delivery Win Rate */}
              <div className="flex items-center justify-between px-3 py-1.5 bg-purple-50 rounded border border-purple-100">
                <span className="text-xs text-purple-600 uppercase tracking-wide">Delivery Win (Impr/Reached)</span>
                <span className="text-sm font-bold text-purple-700">
                  {funnelData!.deliveryWinRate !== null ? `${funnelData!.deliveryWinRate.toFixed(1)}%` : "N/A"}
                </span>
              </div>
              {/* AB-style parity metrics */}
              <div className="flex items-center justify-between px-3 py-1.5 bg-indigo-50 rounded border border-indigo-100">
                <span className="text-xs text-indigo-600 uppercase tracking-wide">Auctions Won</span>
                <span className="text-sm font-bold text-indigo-700">
                  {funnelData!.auctionsWon !== null ? formatNumber(funnelData!.auctionsWon) : "N/A"}
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-1.5 bg-orange-50 rounded border border-orange-100">
                <span className="text-xs text-orange-600 uppercase tracking-wide">Filtered Bids</span>
                <span className="text-sm font-bold text-orange-700">
                  {funnelData!.filteredBids !== null ? formatNumber(funnelData!.filteredBids) : "N/A"}
                  {funnelData!.filteredBidRate !== null ? ` (${funnelData!.filteredBidRate.toFixed(1)}%)` : ""}
                </span>
              </div>
              <div className="flex items-center justify-between px-3 py-1.5 bg-cyan-50 rounded border border-cyan-100">
                <span className="text-xs text-cyan-700 uppercase tracking-wide">Auction Win (Won/Bids)</span>
                <span className="text-sm font-bold text-cyan-700">
                  {funnelData!.auctionWinRate !== null ? `${funnelData!.auctionWinRate.toFixed(1)}%` : "N/A"}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-center p-4 bg-gray-50 rounded-lg border border-dashed border-gray-200">
              <p className="text-xs text-gray-400">Import RTB data to see funnel metrics</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
