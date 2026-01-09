'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRTBEndpoints, getPretargetingConfigs, syncRTBEndpoints } from '@/lib/api';
import { Server, AlertTriangle, Globe, Info, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
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

export function AccountEndpointsHeader() {
  const { selectedBuyerId, selectedServiceAccountId } = useAccount();
  const [showQpsInfo, setShowQpsInfo] = useState(false);
  const queryClient = useQueryClient();

  // Use buyer_id for filtering - RTB endpoints are looked up via buyer -> bidder mapping
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rtb-endpoints', selectedBuyerId],
    queryFn: () => getRTBEndpoints({ buyer_id: selectedBuyerId || undefined }),
  });

  // Also fetch pretargeting configs to count active ones
  const { data: configsData } = useQuery({
    queryKey: ['pretargeting-configs', selectedBuyerId],
    queryFn: () => getPretargetingConfigs({ buyer_id: selectedBuyerId || undefined }),
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

  // Calculate usage percentage
  const usagePercent = data.qps_current && data.total_qps_allocated > 0
    ? Math.round((data.qps_current / data.total_qps_allocated) * 100)
    : null;

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Server className="h-4 w-4 text-gray-500" />
            RTB Endpoints
          </h3>
          {data.bidder_id && (
            <p className="text-xs text-gray-500 mt-0.5">
              Bidder: {data.account_name || data.bidder_id}
            </p>
          )}
        </div>
      </div>

      <div className="flex gap-6">
        {/* Left: Endpoints list */}
        <div className="flex-1">
          <div className="grid gap-2">
            {data.endpoints.map((endpoint) => (
              <div
                key={endpoint.endpoint_id}
                className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg text-sm"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <Globe className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="font-medium text-gray-700 flex-shrink-0 w-16">
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
                  <span className="font-medium text-gray-900 min-w-[60px] text-right">
                    {formatQPS(endpoint.maximum_qps)} QPS
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: QPS Summary */}
        <div className="w-64 bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500 mb-1">Total QPS Allocated</div>
            <div className="relative">
              <button
                onClick={() => setShowQpsInfo(!showQpsInfo)}
                onMouseEnter={() => setShowQpsInfo(true)}
                onMouseLeave={() => setShowQpsInfo(false)}
                className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                aria-label="QPS allocation info"
              >
                <Info className="h-4 w-4 text-gray-400" />
              </button>
              {showQpsInfo && (
                <div className="absolute right-0 top-6 w-72 p-3 bg-white border border-gray-200 rounded-lg shadow-lg z-10 text-xs text-gray-600">
                  <p className="font-medium text-gray-900 mb-1">QPS Allocation</p>
                  <p className="mb-2">
                    This is the total QPS your endpoints can handle.
                    {activeConfigsCount > 0 && (
                      <> You have <strong>{activeConfigsCount}</strong> active pretargeting config{activeConfigsCount !== 1 ? 's' : ''} competing for this QPS.</>
                    )}
                  </p>
                  <p className="text-yellow-700 bg-yellow-50 p-2 rounded">
                    <strong>Tip:</strong> If your pretargeting QPS budget exceeds your endpoint allocation,
                    you may be losing traffic. Check your pretargeting configs.
                  </p>
                </div>
              )}
            </div>
          </div>
          <div className="text-2xl font-bold text-gray-900 mb-3">
            {formatQPS(data.total_qps_allocated)}
          </div>

          {data.qps_current !== null && (
            <>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500">Current Usage</span>
                <span className="font-medium text-gray-700">
                  {formatQPS(data.qps_current)} ({usagePercent}%)
                </span>
              </div>
              <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all',
                    usagePercent !== null && usagePercent < 50 && 'bg-green-500',
                    usagePercent !== null && usagePercent >= 50 && usagePercent < 80 && 'bg-yellow-500',
                    usagePercent !== null && usagePercent >= 80 && 'bg-red-500'
                  )}
                  style={{ width: `${Math.min(usagePercent || 0, 100)}%` }}
                />
              </div>
            </>
          )}

          {data.synced_at && (
            <div className="text-xs text-gray-400 mt-3">
              Last synced: {new Date(data.synced_at).toLocaleString()}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
