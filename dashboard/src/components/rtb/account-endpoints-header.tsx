'use client';

import { useQuery } from '@tanstack/react-query';
import { getRTBEndpoints, updateEndpointQps } from '@/lib/api';
import { Server, Globe, Info, Loader2, RefreshCw, X, Pencil, Undo2 } from 'lucide-react';
import { useAccount } from '@/contexts/account-context';
import { useState, useRef, useCallback } from 'react';
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

function formatQPS(qps: number | null, t: Translations, locale: string): string {
  if (qps === null) return t.pretargeting.endpointsHeaderUnlimited;
  return qps.toLocaleString(locale);
}

interface AccountEndpointsHeaderProps {
  observedQpsByEndpointId?: Record<string, number | null>;
}

export function AccountEndpointsHeader({ observedQpsByEndpointId }: AccountEndpointsHeaderProps) {
  const { t, language } = useTranslation();
  const { selectedBuyerId, selectedServiceAccountId } = useAccount();
  const [showQpsInfo, setShowQpsInfo] = useState(false);

  // Pending QPS edits (endpoint_id -> new value)
  const [pendingQpsEdits, setPendingQpsEdits] = useState<Record<string, number>>({});
  const [editingEndpointId, setEditingEndpointId] = useState<string | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  // Confirmation modal
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState<{ type: 'success' | 'partial' | 'error'; message: string } | null>(null);

  // Refresh state
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['rtb-endpoints', selectedBuyerId],
    queryFn: () => getRTBEndpoints({ buyer_id: selectedBuyerId || undefined, live: true }),
    enabled: !!selectedBuyerId,
  });

  const hasPendingEdits = Object.keys(pendingQpsEdits).length > 0;
  const pendingCount = Object.keys(pendingQpsEdits).length;

  // Compute effective total QPS
  const effectiveTotal = data?.endpoints?.reduce((sum, ep) => {
    const qps = pendingQpsEdits[ep.endpoint_id] ?? ep.maximum_qps;
    return sum + (qps ?? 0);
  }, 0) ?? 0;

  const observedTotal = data?.endpoints?.reduce((sum, ep) => {
    const observed = observedQpsByEndpointId?.[ep.endpoint_id];
    return typeof observed === 'number' ? sum + observed : sum;
  }, 0) ?? 0;

  const observedTotalCount = data?.endpoints?.reduce((count, ep) => {
    const observed = observedQpsByEndpointId?.[ep.endpoint_id];
    return typeof observed === 'number' ? count + 1 : count;
  }, 0) ?? 0;

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setPendingQpsEdits({});
    setEditingEndpointId(null);
    setShowCommitConfirm(false);
    setCommitResult(null);
    try {
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  }, [refetch]);

  const handleStartEdit = useCallback((endpointId: string, currentQps: number | null) => {
    if (currentQps === null) return; // Don't edit unlimited
    setEditingEndpointId(endpointId);
    setCommitResult(null);
    // Focus will be handled via autoFocus on the input
  }, []);

  const handleEditSubmit = useCallback((endpointId: string, originalQps: number | null) => {
    const input = editInputRef.current;
    if (!input) return;
    const newValue = parseInt(input.value, 10);
    if (isNaN(newValue) || newValue < 0) {
      setEditingEndpointId(null);
      return;
    }
    if (newValue === originalQps) {
      // No change — remove from pending if it was there
      setPendingQpsEdits(prev => {
        const next = { ...prev };
        delete next[endpointId];
        return next;
      });
    } else {
      setPendingQpsEdits(prev => ({ ...prev, [endpointId]: newValue }));
    }
    setEditingEndpointId(null);
  }, []);

  const handleUndoEdit = useCallback((endpointId: string) => {
    setPendingQpsEdits(prev => {
      const next = { ...prev };
      delete next[endpointId];
      return next;
    });
  }, []);

  const handleDiscardAll = useCallback(() => {
    setPendingQpsEdits({});
    setEditingEndpointId(null);
    setShowCommitConfirm(false);
    setCommitResult(null);
  }, []);

  const handleCommit = useCallback(async () => {
    if (!data?.endpoints || Object.keys(pendingQpsEdits).length === 0) {
      setShowCommitConfirm(false);
      return;
    }
    setIsCommitting(true);
    setCommitResult(null);

    // Build ordered edits: decreases first, then increases
    const edits = Object.entries(pendingQpsEdits).map(([endpointId, newQps]) => {
      const endpoint = data.endpoints.find(ep => ep.endpoint_id === endpointId);
      const originalQps = endpoint?.maximum_qps ?? 0;
      return { endpointId, newQps, originalQps, isDecrease: newQps < originalQps };
    });
    edits.sort((a, b) => {
      if (a.isDecrease && !b.isDecrease) return -1;
      if (!a.isDecrease && b.isDecrease) return 1;
      return 0;
    });

    let applied = 0;
    let failed = false;
    let failedErrorMessage: string | null = null;

    for (const edit of edits) {
      try {
        await updateEndpointQps(edit.endpointId, edit.newQps, {
          buyer_id: selectedBuyerId || undefined,
          service_account_id: selectedServiceAccountId || undefined,
        });
        applied++;
      } catch (err) {
        failedErrorMessage = err instanceof Error ? err.message : null;
        failed = true;
        break;
      }
    }

    try {
      // Live-refetch to get server truth
      await refetch();

      if (failed) {
        // Reconcile: remove successfully applied edits from pending
        const appliedIds = new Set(edits.slice(0, applied).map(e => e.endpointId));
        setPendingQpsEdits(prev => {
          const next: Record<string, number> = {};
          for (const [id, val] of Object.entries(prev)) {
            if (!appliedIds.has(id)) {
              next[id] = val;
            }
          }
          return next;
        });
        const partialMessage = t.pretargeting.endpointsPartialFailure
          .replace('{applied}', String(applied))
          .replace('{total}', String(edits.length));
        setCommitResult({
          type: applied > 0 ? 'partial' : 'error',
          message: failedErrorMessage
            ? (applied > 0 ? `${partialMessage} ${failedErrorMessage}` : failedErrorMessage)
            : partialMessage,
        });
      } else {
        setPendingQpsEdits({});
        setCommitResult({ type: 'success', message: t.pretargeting.endpointsSuccess });
      }

      setShowCommitConfirm(false);
    } finally {
      setIsCommitting(false);
    }
  }, [data, pendingQpsEdits, selectedBuyerId, selectedServiceAccountId, refetch, t]);

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
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 flex items-center gap-2">
        <Server className="h-4 w-4 text-gray-400" />
        <span className="text-sm text-gray-600">{t.pretargeting.endpointsHeaderNoEndpoints}</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border p-3">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2">
        <Server className="h-3.5 w-3.5 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-900">{t.pretargeting.endpointsHeaderTitle}</h3>
        {data.bidder_id && (
          <span className="text-xs text-gray-400">· {data.account_name || data.bidder_id}</span>
        )}
        {selectedBuyerId && (
          <span className="text-xs text-gray-400">· {selectedBuyerId}</span>
        )}
        <div className="flex-1" />
        <button
          onClick={handleRefresh}
          disabled={isRefreshing || isCommitting}
          className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 disabled:opacity-50"
          title={t.pretargeting.endpointsRefresh}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Commit result banner */}
      {commitResult && (
        <div className={`mb-2 px-2 py-1.5 rounded text-xs flex items-center justify-between ${
          commitResult.type === 'success'
            ? 'bg-green-50 border border-green-200 text-green-800'
            : 'bg-amber-50 border border-amber-200 text-amber-800'
        }`}>
          <span>{commitResult.message}</span>
          <button onClick={() => setCommitResult(null)} className="ml-2 p-0.5 hover:bg-black/5 rounded">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      <div className="space-y-0.5">
        {/* Column headers */}
        <div className="flex items-center justify-end gap-4 px-2 text-[10px] uppercase tracking-wide text-gray-400">
          <span className="w-24 text-right">{t.pretargeting.endpointsHeaderAllocated}</span>
          <span className="w-24 text-right">{t.pretargeting.endpointsHeaderObserved}</span>
        </div>

        {/* Endpoint rows */}
        {data.endpoints.map((endpoint) => {
          const isPending = endpoint.endpoint_id in pendingQpsEdits;
          const isEditing = editingEndpointId === endpoint.endpoint_id;
          const isEditable = endpoint.maximum_qps !== null;
          const pendingValue = isPending ? pendingQpsEdits[endpoint.endpoint_id] : null;

          return (
            <div
              key={endpoint.endpoint_id}
              className={`group flex items-center justify-between px-2 py-1 rounded text-xs ${
                isPending ? 'bg-yellow-50 border border-yellow-200' : 'bg-gray-50'
              }`}
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
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Allocated QPS — editable */}
                <div className="w-24 text-right flex items-center justify-end gap-1">
                  {isEditing ? (
                    <input
                      ref={editInputRef}
                      type="number"
                      min={0}
                      defaultValue={pendingValue ?? endpoint.maximum_qps ?? 0}
                      autoFocus
                      className="w-20 px-1 py-0.5 text-xs text-right border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleEditSubmit(endpoint.endpoint_id, endpoint.maximum_qps);
                        if (e.key === 'Escape') setEditingEndpointId(null);
                      }}
                      onBlur={() => handleEditSubmit(endpoint.endpoint_id, endpoint.maximum_qps)}
                    />
                  ) : (
                    <>
                      {isPending && (
                        <>
                          <span className="text-gray-400 line-through text-[10px]">
                            {formatQPS(endpoint.maximum_qps, t, language)}
                          </span>
                          <span className="font-semibold text-amber-700">
                            {formatQPS(pendingValue!, t, language)}
                          </span>
                          <button
                            onClick={() => handleUndoEdit(endpoint.endpoint_id)}
                            className="p-0.5 rounded hover:bg-yellow-200 text-yellow-600"
                            title={t.pretargeting.endpointsUndo}
                          >
                            <Undo2 className="h-2.5 w-2.5" />
                          </button>
                        </>
                      )}
                      {!isPending && (
                        <span
                          className={`font-medium text-gray-800 ${isEditable ? 'cursor-pointer hover:text-blue-600' : ''}`}
                          onClick={() => isEditable && handleStartEdit(endpoint.endpoint_id, endpoint.maximum_qps)}
                          title={isEditable ? t.pretargeting.endpointsEditQps : undefined}
                        >
                          {formatQPS(endpoint.maximum_qps, t, language)}
                        </span>
                      )}
                      {!isPending && isEditable && (
                        <button
                          onClick={() => handleStartEdit(endpoint.endpoint_id, endpoint.maximum_qps)}
                          className="p-0.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
                        >
                          <Pencil className="h-2.5 w-2.5" />
                        </button>
                      )}
                    </>
                  )}
                </div>

                {/* Observed QPS — read-only */}
                <span className="font-medium text-slate-600 w-24 text-right">
                  {observedQpsByEndpointId?.[endpoint.endpoint_id] != null
                    ? Number(observedQpsByEndpointId[endpoint.endpoint_id]).toLocaleString(language, { maximumFractionDigits: 1 })
                    : '\u2014'}
                </span>
              </div>
            </div>
          );
        })}

        {/* Pending changes banner */}
        {hasPendingEdits && !showCommitConfirm && (
          <div className="flex items-center justify-between px-2 py-1.5 mt-1 bg-yellow-50 border border-yellow-200 rounded text-xs">
            <span className="font-medium text-yellow-800">
              {t.pretargeting.endpointsChangesPending.replace('{count}', String(pendingCount))}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDiscardAll}
                className="px-2 py-0.5 text-yellow-700 hover:bg-yellow-100 rounded"
              >
                {t.pretargeting.endpointsDiscardAll}
              </button>
              <button
                onClick={() => setShowCommitConfirm(true)}
                className="px-2 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                {t.pretargeting.endpointsPushToGoogle}
              </button>
            </div>
          </div>
        )}

        {/* Confirmation panel (inline) */}
        {showCommitConfirm && (
          <div className="mt-1 p-3 bg-blue-50 border border-blue-200 rounded space-y-2">
            <h4 className="text-xs font-semibold text-blue-900">{t.pretargeting.endpointsConfirmTitle}</h4>
            <p className="text-[11px] text-blue-700">{t.pretargeting.endpointsConfirmBody}</p>
            <div className="space-y-1">
              {Object.entries(pendingQpsEdits).map(([endpointId, newQps]) => {
                const ep = data.endpoints.find(e => e.endpoint_id === endpointId);
                const url = ep?.url?.replace(/^https?:\/\//, '') ?? endpointId;
                const oldQps = ep?.maximum_qps;
                return (
                  <div key={endpointId} className="text-[11px] text-blue-800 font-mono px-2 py-0.5 bg-white/50 rounded">
                    {url}: {oldQps?.toLocaleString(language) ?? '?'} &rarr; {newQps.toLocaleString(language)}
                  </div>
                );
              })}
            </div>
            <div className="text-[11px] text-blue-700">
              {t.pretargeting.endpointsHeaderTotalQpsCap}: {t.pretargeting.endpointsCurrentTotal}{' '}
              {data.total_qps_allocated.toLocaleString(language)} &rarr; {t.pretargeting.endpointsAfterTotal}{' '}
              {effectiveTotal.toLocaleString(language)}
            </div>
            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={() => setShowCommitConfirm(false)}
                disabled={isCommitting}
                className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded disabled:opacity-50"
              >
                {t.pretargeting.endpointsCancel}
              </button>
              <button
                onClick={handleCommit}
                disabled={isCommitting}
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {isCommitting ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {t.pretargeting.endpointsCommitting}
                  </>
                ) : (
                  t.pretargeting.endpointsConfirm
                )}
              </button>
            </div>
          </div>
        )}

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
          <div className="flex items-center gap-2">
            <div className="w-24 text-right leading-tight">
              {hasPendingEdits ? (
                <div className="flex flex-col items-end">
                  <span className="text-[10px] text-blue-500 line-through">
                    {formatQPS(data.total_qps_allocated, t, language)}
                  </span>
                  <span className="text-sm font-bold text-amber-700">
                    {effectiveTotal.toLocaleString(language)}
                  </span>
                </div>
              ) : (
                <span className="text-sm font-bold text-blue-900">
                  {formatQPS(data.total_qps_allocated, t, language)}
                </span>
              )}
            </div>

            <div className="w-24 text-right">
              <span className="text-sm font-bold text-slate-700">
                {observedTotalCount > 0
                  ? observedTotal.toLocaleString(language, { maximumFractionDigits: 1 })
                  : '\u2014'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
