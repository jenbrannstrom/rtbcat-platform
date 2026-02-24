'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRTBEndpoints, syncRTBEndpoints } from '@/lib/api';
import { Server, AlertTriangle, Globe, Info, Loader2 } from 'lucide-react';
import { useAccount } from '@/contexts/account-context';
import { useState, useEffect, useRef } from 'react';
import { useTranslation } from '@/contexts/i18n-context';
import type { Translations } from '@/lib/i18n/types';

function formatLocation(location: string | null, t: Translations): string {
  if (!location) return t.pretargeting.endpointsHeaderLocationUnknown;
  const map: Record<string, string> = {
    'US_WEST': t.pretargeting.endpointsHeaderLocationUsWest,
    'US_EAST': t.pretargeting.endpointsHeaderLocationUsEast,
    'EUROPE': t.pretargeting.endpointsHeaderLocationEurope,
    'ASIA': t.pretargeting.endpointsHeaderLocationAsia,
    'TRADING_LOCATION_UNSPECIFIED': t.pretargeting.endpointsHeaderLocationUnspecified,
  };
  return map[location] || location;
}

function formatQPS(qps: number | null, t: Translations): string {
  if (qps === null) return t.pretargeting.endpointsHeaderUnlimited;
  return qps.toLocaleString();
}

interface AccountEndpointsHeaderProps {
  observedQpsByEndpointId?: Record<string, number | null>;
}

export function AccountEndpointsHeader({ observedQpsByEndpointId }: AccountEndpointsHeaderProps) {
  const { t, language } = useTranslation();
  const { selectedBuyerId, selectedServiceAccountId } = useAccount();
  const [showQpsInfo, setShowQpsInfo] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rtb-endpoints', selectedBuyerId],
    queryFn: () => getRTBEndpoints({ buyer_id: selectedBuyerId || undefined }),
    enabled: !!selectedBuyerId,
  });

  const syncMutation = useMutation({
    mutationFn: () => syncRTBEndpoints({ service_account_id: selectedServiceAccountId || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rtb-endpoints'] });
      refetch();
    },
  });

  const hasSynced = useRef(false);
  useEffect(() => {
    if (!isLoading && !hasSynced.current && data && !data.endpoints?.length && selectedServiceAccountId) {
      hasSynced.current = true;
      syncMutation.mutate();
    }
  }, [isLoading, data, selectedServiceAccountId]);

  if (!selectedBuyerId) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
        {t.pretargeting.endpointsHeaderSelectSeat}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border p-3">
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-300 rounded w-40" />
          <div className="h-8 bg-gray-200 rounded" />
          <div className="h-8 bg-gray-200 rounded" />
        </div>
      </div>
    );
  }

  if (error) {
    const isConnectionError = error instanceof Error &&
      (error.message.includes('fetch') || error.message.includes('network') || error.message.includes('500'));
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-600">
            {isConnectionError ? t.pretargeting.endpointsHeaderCannotConnectApi : t.pretargeting.endpointsHeaderFailedToLoad}
          </span>
        </div>
      </div>
    );
  }

  if (!data?.endpoints?.length) {
    if (syncMutation.isPending) {
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-2">
          <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
          <span className="text-sm text-blue-800">{t.pretargeting.endpointsHeaderSyncing}</span>
        </div>
      );
    }
    if (syncMutation.isError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <span className="text-sm text-red-800">
            {syncMutation.error instanceof Error ? syncMutation.error.message : t.pretargeting.endpointsHeaderFailedToSync}
          </span>
        </div>
      );
    }
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 flex items-center gap-2">
        <Server className="h-4 w-4 text-gray-400" />
        <span className="text-sm text-gray-600">{t.pretargeting.endpointsHeaderNoEndpoints}</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border p-3">
      <div className="flex items-center gap-2 mb-2">
        <Server className="h-3.5 w-3.5 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-900">{t.pretargeting.endpointsHeaderTitle}</h3>
        {data.bidder_id && (
          <span className="text-xs text-gray-400">· {data.account_name || data.bidder_id}</span>
        )}
        {selectedBuyerId && (
          <span className="text-xs text-gray-400">· {selectedBuyerId}</span>
        )}
      </div>

      <div className="space-y-0.5">
        <div className="flex items-center justify-end gap-4 px-2 text-[10px] uppercase tracking-wide text-gray-400">
          <span className="w-20 text-right">{t.pretargeting.endpointsHeaderAllocated}</span>
          <span className="w-20 text-right">{t.pretargeting.endpointsHeaderObserved}</span>
        </div>
        {data.endpoints.map((endpoint) => (
          <div
            key={endpoint.endpoint_id}
            className="flex items-center justify-between px-2 py-1 bg-gray-50 rounded text-xs"
          >
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <Globe className="h-3 w-3 text-gray-400 flex-shrink-0" />
              <span className="font-medium text-gray-700 w-14 flex-shrink-0">
                {formatLocation(endpoint.trading_location, t)}
              </span>
              <span className="text-[11px] text-gray-400 font-mono truncate" title={endpoint.url}>
                {endpoint.url.replace(/^https?:\/\//, '')}
              </span>
              <span className="text-[11px] text-gray-400 flex-shrink-0">
                {endpoint.bid_protocol?.replace('OPENRTB_', 'OpenRTB ').replace('_', '.') || ''}
              </span>
            </div>
            <div className="flex items-center gap-4 flex-shrink-0">
              <span className="font-medium text-gray-800 w-20 text-right">
                {formatQPS(endpoint.maximum_qps, t)}
              </span>
              <span className="font-medium text-slate-600 w-20 text-right">
                {observedQpsByEndpointId?.[endpoint.endpoint_id] != null
                  ? Number(observedQpsByEndpointId[endpoint.endpoint_id]).toLocaleString(undefined, { maximumFractionDigits: 1 })
                  : '—'}
              </span>
            </div>
          </div>
        ))}

        {/* Total row */}
        <div className="flex items-center justify-between px-2 py-1.5 mt-1 bg-blue-50 border border-blue-200 rounded">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-blue-800">{t.pretargeting.endpointsHeaderTotalQpsCap}</span>
            <div className="relative">
              <button
                onMouseEnter={() => setShowQpsInfo(true)}
                onMouseLeave={() => setShowQpsInfo(false)}
                className="p-0.5 hover:bg-blue-100 rounded-full"
                aria-label={t.pretargeting.endpointsHeaderQpsInfoAria}
              >
                <Info className="h-3 w-3 text-blue-400" />
              </button>
              {showQpsInfo && (
                <div className="absolute left-0 top-5 w-64 p-2 bg-white border border-gray-200 rounded shadow-lg z-10 text-[11px] text-gray-600">
                  {t.pretargeting.endpointsHeaderQpsInfoTooltip}
                </div>
              )}
            </div>
            {data.synced_at && (
              <span className="text-[10px] text-blue-400">
                · {new Date(data.synced_at).toLocaleString(language)}
              </span>
            )}
          </div>
          <span className="text-sm font-bold text-blue-900">
            {formatQPS(data.total_qps_allocated, t)}
          </span>
        </div>
      </div>
    </div>
  );
}
