'use client';

import { useQuery } from '@tanstack/react-query';
import { getRTBEndpoints } from '@/lib/api';
import { Server, AlertTriangle, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAccount } from '@/contexts/account-context';

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

// Helper to format QPS
function formatQPS(qps: number | null): string {
  if (qps === null) return 'Unlimited';
  if (qps >= 1000000) return `${(qps / 1000000).toFixed(1)}M`;
  if (qps >= 1000) return `${(qps / 1000).toFixed(0)}K`;
  return qps.toString();
}

export function AccountEndpointsHeader() {
  const { selectedServiceAccountId } = useAccount();

  const { data, isLoading, error } = useQuery({
    queryKey: ['rtb-endpoints', selectedServiceAccountId],
    queryFn: () => getRTBEndpoints({ service_account_id: selectedServiceAccountId || undefined }),
  });

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

  // No endpoints warning
  if (!data?.endpoints?.length) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-medium text-yellow-800">No RTB Endpoints Configured</h3>
            <p className="text-sm text-yellow-700 mt-1">
              RTB endpoints will be synced automatically when you configure your service account credentials.
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
          <div className="text-sm text-gray-500 mb-1">Total QPS Allocated</div>
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
