'use client';

import { useState, useRef, useEffect, type MouseEvent } from 'react';
import Link from 'next/link';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { setPretargetingName, lookupGeoNames, suspendPretargeting, activatePretargeting, syncPretargetingConfigs, getPretargetingConfigDetail, createPendingChange, cancelPendingChange, applyAllPendingChanges, discardAllPretargetingChanges } from '@/lib/api';
import { ChevronRight, Pencil, Check, X, AlertTriangle, AlertCircle, Pause, Play, Loader2, History, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SnapshotComparisonPanel } from './snapshot-comparison-panel';
import { useAccount } from '@/contexts/account-context';
import { toBuyerScopedPath } from '@/lib/buyer-routes';
import { useTranslation } from '@/contexts/i18n-context';
import { asNumber } from '@/lib/utils';

export interface PretargetingConfig {
  billing_id: string;
  name: string;              // resolved: user_name || display_name || 'Config {id}'
  display_name: string | null;
  user_name: string | null;
  state: 'ACTIVE' | 'SUSPENDED';
  maximum_qps: number | null;
  formats: string[];         // ['HTML', 'VAST']
  platforms: string[];       // ['PHONE', 'TABLET']
  sizes: string[];           // ['300x250', '320x50']
  included_geos: string[];   // country codes
  reached: number;
  impressions: number;
  win_rate: number;
  waste_rate: number;
  has_performance: boolean;
  metrics_delayed?: boolean;
  pending_changes_count?: number;
}

interface PretargetingConfigCardProps {
  config: PretargetingConfig;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

type MajorChangeType = 'targeting' | 'publisher' | 'qps' | 'mixed';

// Format large numbers
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

// Geo display component that fetches names from the database
function GeoSettingPill({
  geoIds,
  max = 5,
  resolveNames = false,
}: {
  geoIds: string[];
  max?: number;
  resolveNames?: boolean;
}) {
  const { t } = useTranslation();
  const { data: geoNames } = useQuery({
    queryKey: ['geo-names', geoIds.join(',')],
    queryFn: () => lookupGeoNames(geoIds),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    enabled: resolveNames && geoIds.length > 0,
  });

  if (!geoIds?.length) return null;

  const displayIds = geoIds.slice(0, max);
  const remaining = geoIds.length - max;

  // Format display names - use looked up name or fall back to ID
  const displayNames = displayIds.map(id => {
    if (resolveNames && geoNames?.[id]) return geoNames[id];
    // If it's already a 2 or 3 letter code, return as-is
    if (/^[A-Z]{2,3}$/i.test(id)) return id.toUpperCase();
    return id;
  });

  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">
      <span className="text-gray-400">{t.pretargeting.cardGeosLabel}:</span>
      <span>{displayNames.join(', ')}</span>
      {remaining > 0 && <span className="text-gray-400">+{remaining}</span>}
    </div>
  );
}

// Pill component for settings
function SettingPill({ label, values, max = 3, formatValue }: {
  label: string;
  values: string[];
  max?: number;
  formatValue?: (v: string) => string;
}) {
  if (!values?.length) return null;

  const displayValues = values.slice(0, max);
  const remaining = values.length - max;
  const formatter = formatValue || ((v: string) => v);

  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">
      <span className="text-gray-400">{label}:</span>
      <span>{displayValues.map(formatter).join(', ')}</span>
      {remaining > 0 && <span className="text-gray-400">+{remaining}</span>}
    </div>
  );
}

// Mini progress bar for waste
function WasteMiniBar({ pct }: { pct: number }) {
  return (
    <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
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

function getMajorChangeType(changeType: string): Exclude<MajorChangeType, 'mixed'> {
  if (changeType === 'set_maximum_qps') {
    return 'qps';
  }
  if (changeType === 'add_publisher' || changeType === 'remove_publisher' || changeType === 'set_publisher_mode') {
    return 'publisher';
  }
  return 'targeting';
}

function resolveActiveMajorChangeType(
  pendingChanges: Array<{ change_type: string }>
): MajorChangeType | null {
  const majorTypes = new Set<Exclude<MajorChangeType, 'mixed'>>();
  pendingChanges.forEach((change) => {
    majorTypes.add(getMajorChangeType(change.change_type));
  });
  if (majorTypes.size === 0) {
    return null;
  }
  if (majorTypes.size === 1) {
    return Array.from(majorTypes)[0];
  }
  return 'mixed';
}

export function PretargetingConfigCard({ config, isExpanded, onToggleExpand }: PretargetingConfigCardProps) {
  const { t } = useTranslation();
  const { selectedBuyerId } = useAccount();
  // Support both controlled and uncontrolled expansion
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = isExpanded !== undefined ? isExpanded : internalExpanded;
  const handleToggle = onToggleExpand || (() => setInternalExpanded(!internalExpanded));
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(config.name);
  const [showHistory, setShowHistory] = useState(false);
  const [showConfirmSuspend, setShowConfirmSuspend] = useState(false);
  const [showCommitToast, setShowCommitToast] = useState(false);
  const [pushResult, setPushResult] = useState<{ success: boolean; message: string } | null>(null);
  const [changeError, setChangeError] = useState<string | null>(null);
  const [qpsInput, setQpsInput] = useState(
    config.maximum_qps === null || config.maximum_qps === undefined ? '' : String(config.maximum_qps)
  );
  const [isEditingQps, setIsEditingQps] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const qpsInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const winRate = asNumber(config.win_rate);
  const wasteRate = asNumber(config.waste_rate);

  const { data: configDetail, isFetching: configDetailFetching } = useQuery({
    queryKey: ['pretargeting-detail', config.billing_id],
    queryFn: () => getPretargetingConfigDetail(config.billing_id),
    enabled: expanded || isEditingQps || (config.pending_changes_count ?? 0) > 0,
    staleTime: 30_000,
  });

  const nameMutation = useMutation({
    mutationFn: ({ billingId, userName }: { billingId: string; userName: string }) =>
      setPretargetingName(billingId, userName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      setIsEditing(false);
    },
  });

  const suspendMutation = useMutation({
    mutationFn: () => suspendPretargeting(config.billing_id),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      setShowConfirmSuspend(false);
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const activateMutation = useMutation({
    mutationFn: () => activatePretargeting(config.billing_id),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const createChangeMutation = useMutation({
    mutationFn: createPendingChange,
    onSuccess: () => {
      setChangeError(null);
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
    },
    onError: (error: Error) => {
      setChangeError(error.message);
    },
  });

  const cancelChangeMutation = useMutation({
    mutationFn: cancelPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
    },
  });

  const applyAllMutation = useMutation({
    mutationFn: () => applyAllPendingChanges(config.billing_id, false),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      setShowCommitToast(false);
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', config.billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const discardAllMutation = useMutation({
    mutationFn: () => discardAllPretargetingChanges(config.billing_id),
    onSuccess: (data) => {
      setPushResult({ success: true, message: data.message });
      setShowCommitToast(false);
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', config.billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', config.billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Focus QPS input when editing starts
  useEffect(() => {
    if (isEditingQps && qpsInputRef.current) {
      qpsInputRef.current.focus();
      qpsInputRef.current.select();
    }
  }, [isEditingQps]);

  // Sync QPS input with config detail
  useEffect(() => {
    if (isEditingQps) return;
    const qpsValue =
      configDetail?.effective_maximum_qps ??
      configDetail?.maximum_qps ??
      config.maximum_qps;
    setQpsInput(qpsValue === null || qpsValue === undefined ? '' : String(qpsValue));
  }, [
    configDetail?.effective_maximum_qps,
    configDetail?.maximum_qps,
    config.maximum_qps,
    isEditingQps,
  ]);

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(config.user_name || config.display_name || '');
    setIsEditing(true);
  };

  const handleSave = () => {
    if (editValue.trim() && editValue !== config.user_name) {
      nameMutation.mutate({ billingId: config.billing_id, userName: editValue.trim() });
    } else {
      setIsEditing(false);
    }
  };

  const handleCancel = () => {
    setEditValue(config.name);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const pendingQpsChanges = (configDetail?.pending_changes || []).filter(
    (c) => c.change_type === 'set_maximum_qps'
  );
  const latestPendingQpsChange = pendingQpsChanges.length > 0
    ? pendingQpsChanges[pendingQpsChanges.length - 1]
    : null;
  const persistedQpsLimit = configDetail?.maximum_qps ?? config.maximum_qps ?? null;
  const pendingChanges = configDetail?.pending_changes || [];
  const pendingChangesCount = configDetail?.pending_changes_count ?? config.pending_changes_count ?? 0;
  const hasPendingChanges = pendingChangesCount > 0;
  const activeMajorChangeType = resolveActiveMajorChangeType(pendingChanges);

  const canStageChange = (nextChangeType: string): boolean => {
    const nextMajorType = getMajorChangeType(nextChangeType);
    if (activeMajorChangeType === null || activeMajorChangeType === nextMajorType) {
      return true;
    }
    if (activeMajorChangeType === 'mixed') {
      setChangeError('Pending changes already mix major types. Commit or clear them before staging more changes.');
      return false;
    }
    setChangeError(
      `Only one major change per commit is allowed (active=${activeMajorChangeType}, requested=${nextMajorType}).`
    );
    return false;
  };

  const stageChange = (payload: {
    billing_id: string;
    change_type: string;
    field_name: string;
    value: string;
    reason?: string;
    estimated_qps_impact?: number;
  }) => {
    if (!canStageChange(payload.change_type)) {
      return;
    }
    createChangeMutation.mutate(payload);
  };

  const applyQpsChange = () => {
    if (!configDetail) return;
    const normalized = qpsInput.trim();
    if (!normalized) {
      pendingQpsChanges.forEach((c) => cancelChangeMutation.mutate(c.id));
      return;
    }
    const parsed = Number.parseInt(normalized, 10);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    const desired = String(parsed);
    pendingQpsChanges
      .filter((c) => c.value !== desired)
      .forEach((c) => cancelChangeMutation.mutate(c.id));
    if (persistedQpsLimit === parsed) {
      pendingQpsChanges
        .filter((c) => c.value === desired)
        .forEach((c) => cancelChangeMutation.mutate(c.id));
      setChangeError(null);
      return;
    }
    if (latestPendingQpsChange?.value === desired) return;
    stageChange({
      billing_id: config.billing_id,
      change_type: 'set_maximum_qps',
      field_name: 'maximum_qps',
      value: desired,
      reason: 'Updated from config card QPS control',
    });
  };

  // Format controls
  const effectiveFormats = new Set(
    configDetail?.effective_formats || configDetail?.included_formats || config.formats || []
  );
  const isFormatEnabled = (format: string): boolean => effectiveFormats.has(format);
  const findPendingChange = (changeType: string, value: string) =>
    pendingChanges.find((c: { change_type: string; value: string }) => c.change_type === changeType && c.value === value);

  const setFormatEnabledState = (format: string, shouldEnable: boolean) => {
    const pendingAdd = findPendingChange('add_format', format);
    const pendingRemove = findPendingChange('remove_format', format);
    const currentlyEnabled = isFormatEnabled(format);

    if (shouldEnable) {
      if (pendingRemove) {
        cancelChangeMutation.mutate(pendingRemove.id);
        return;
      }
      if (pendingAdd || currentlyEnabled) return;
      stageChange({
        billing_id: config.billing_id,
        change_type: 'add_format',
        field_name: 'included_formats',
        value: format,
        reason: 'Enabled from config card',
      });
      return;
    }

    if (pendingAdd) {
      cancelChangeMutation.mutate(pendingAdd.id);
      return;
    }
    if (pendingRemove || !currentlyEnabled) return;
    stageChange({
      billing_id: config.billing_id,
      change_type: 'remove_format',
      field_name: 'included_formats',
      value: format,
      reason: 'Disabled from config card',
    });
  };

  const formatMutationPending =
    createChangeMutation.isPending ||
    cancelChangeMutation.isPending ||
    discardAllMutation.isPending;
  useEffect(() => {
    if (hasPendingChanges) {
      setShowCommitToast(true);
    }
  }, [hasPendingChanges, config.billing_id]);

  // Determine status indicator
  const isHighWaste = config.has_performance && config.waste_rate >= 70;
  const isCriticalWaste = config.has_performance && config.waste_rate >= 90;
  const isGoodWinRate = config.has_performance && config.win_rate >= 50;

  // Check if using display_name from Google (not user-defined)
  const stateMutationPending = suspendMutation.isPending || activateMutation.isPending;
  const isPushing = applyAllMutation.isPending || discardAllMutation.isPending || stateMutationPending;
  const qpsMutationPending =
    createChangeMutation.isPending ||
    cancelChangeMutation.isPending ||
    discardAllMutation.isPending;
  const configDetailHref = toBuyerScopedPath(
    `/bill_id/${encodeURIComponent(config.billing_id)}`,
    selectedBuyerId
  );

  return (
    <div
      className={cn(
        'border rounded-lg transition-all',
        config.state === 'SUSPENDED' && 'opacity-60 bg-gray-50 border-gray-300',
        config.state === 'ACTIVE' && 'bg-green-50/50 border-green-300',
        config.state === 'ACTIVE' && isCriticalWaste && 'border-l-4 border-l-red-400',
        config.state === 'ACTIVE' && isHighWaste && !isCriticalWaste && 'border-l-4 border-l-orange-400'
      )}
    >
      {/* Main row - clickable to expand */}
      <div
        role="button"
        tabIndex={0}
        onClick={handleToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleToggle(); }}
        className="w-full px-4 py-3 flex items-center gap-3 text-left cursor-pointer hover:bg-gray-50/50"
      >
        <ChevronRight
          className={cn(
            'h-4 w-4 text-gray-600 transition-transform shrink-0',
            expanded && 'rotate-90'
          )}
        />

        {/* Status indicator */}
        <div className="shrink-0">
          {isCriticalWaste && <AlertCircle className="h-4 w-4 text-red-500" />}
          {isHighWaste && !isCriticalWaste && <AlertTriangle className="h-4 w-4 text-orange-500" />}
          {!isGoodWinRate && !isHighWaste && <div className="w-4" />}
        </div>

        {/* Pretargeting config ID (billing_id) */}
        <Link
          href={configDetailHref}
          onClick={(e: MouseEvent<HTMLAnchorElement>) => e.stopPropagation()}
          className="font-mono text-xs text-gray-500 hover:text-primary-600 hover:underline w-24 shrink-0"
          title={t.pretargeting.cardPretargetingConfigIdTitle}
          aria-label={t.pretargeting.cardPretargetingConfigIdAria.replace('{id}', config.billing_id)}
        >
          {config.billing_id}
        </Link>

        {/* Name - editable */}
        <div className="flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
          {isEditing ? (
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={handleKeyDown}
                onBlur={handleSave}
                className="flex-1 px-2 py-0.5 text-sm font-medium border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={nameMutation.isPending}
              />
              <button
                onClick={handleSave}
                disabled={nameMutation.isPending}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={handleCancel}
                disabled={nameMutation.isPending}
                className="p-1 text-gray-400 hover:bg-gray-100 rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <span className="font-medium text-gray-900 truncate">
                {config.name}
              </span>
              {hasPendingChanges && (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
                  {pendingChangesCount} pending
                </span>
              )}
              <button
                onClick={handleStartEdit}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <Pencil className="h-3 w-3" />
              </button>
              <span className="text-gray-300 mx-0.5">|</span>
              {/* QPS inline display/edit */}
              <div className="flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                <span className="text-[10px] text-gray-500">{t.pretargeting.cardQpsLabel}</span>
                {isEditingQps ? (
                  <div className="flex items-center gap-1">
                    <input
                      ref={qpsInputRef}
                      type="number"
                      min={0}
                      step={1}
                      value={qpsInput}
                      onChange={(e) => setQpsInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && configDetail) { applyQpsChange(); setIsEditingQps(false); }
                        if (e.key === 'Escape') {
                          setIsEditingQps(false);
                          const qpsValue =
                            configDetail?.effective_maximum_qps ??
                            configDetail?.maximum_qps ??
                            config.maximum_qps;
                          setQpsInput(qpsValue === null || qpsValue === undefined ? '' : String(qpsValue));
                        }
                      }}
                      className="w-20 rounded border border-gray-300 bg-white px-1.5 py-0.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
                      placeholder={t.pretargeting.cardQpsUnsetPlaceholder}
                      disabled={!configDetail}
                    />
                    {configDetailFetching && !configDetail && (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-400" />
                    )}
                    <button
                      onClick={() => { applyQpsChange(); setIsEditingQps(false); }}
                      disabled={qpsMutationPending || !configDetail}
                      className="p-0.5 text-green-600 hover:bg-green-50 rounded"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setIsEditingQps(false);
                        const qpsValue =
                          configDetail?.effective_maximum_qps ??
                          configDetail?.maximum_qps ??
                          config.maximum_qps;
                        setQpsInput(qpsValue === null || qpsValue === undefined ? '' : String(qpsValue));
                      }}
                      className="p-0.5 text-gray-400 hover:bg-gray-100 rounded"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <span className="text-xs font-medium text-gray-700">{qpsInput || '—'}</span>
                    {latestPendingQpsChange && (
                      <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-800">
                        {t.pretargeting.cardPendingLabel}: {latestPendingQpsChange.value}
                      </span>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); setIsEditingQps(true); }}
                      className="p-0.5 text-gray-400 hover:text-gray-600"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* State badge */}
        {config.state === 'SUSPENDED' && (
          <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
            {t.pretargeting.cardPausedBadge}
          </span>
        )}

        {/* Metrics summary */}
        <div className="flex items-center gap-4 text-xs shrink-0">
          <span className="text-gray-600 w-16 text-right">
            {config.has_performance ? formatNumber(config.reached) : '--'}
          </span>
          {config.has_performance ? (
            <>
              <span
                className={cn(
                  'w-14 text-right font-medium',
                  winRate >= 50 && 'text-green-600',
                  winRate >= 30 && winRate < 50 && 'text-yellow-600',
                  winRate < 30 && 'text-red-600'
                )}
              >
                {winRate.toFixed(1)}% {t.pretargeting.cardWinSuffix}
              </span>
              <span
                className={cn(
                  'w-14 text-right',
                  wasteRate < 50 && 'text-gray-500',
                  wasteRate >= 50 && wasteRate < 70 && 'text-yellow-600',
                  wasteRate >= 70 && wasteRate < 90 && 'text-orange-600',
                  wasteRate >= 90 && 'text-red-600 font-medium'
                )}
              >
                {wasteRate.toFixed(1)}%
              </span>
              <WasteMiniBar pct={wasteRate} />
            </>
          ) : (
            <>
              <span className="w-14 text-right text-gray-400">--</span>
              <span className="w-14 text-right text-gray-400">{t.pretargeting.cardNoData}</span>
              <div className="w-16 h-1.5 bg-gray-200 rounded-full" />
            </>
          )}
        </div>

      </div>

      {pushResult && (
        <div className={cn(
          'px-4 py-2 border-t flex items-center justify-between',
          pushResult.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        )}>
          <div className="flex items-center gap-2 text-sm">
            {pushResult.success ? (
              <Check className="h-4 w-4 text-green-600" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-600" />
            )}
            <span className={pushResult.success ? 'text-green-800' : 'text-red-800'}>
              {pushResult.message}
            </span>
          </div>
          <button
            onClick={() => setPushResult(null)}
            className="text-gray-400 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {changeError && (
        <div className="px-4 pb-2 text-xs text-red-600">{changeError}</div>
      )}

      {showConfirmSuspend && (
        <div className="px-4 py-3 bg-yellow-50 border-t border-yellow-200">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-900">
                {t.pretargeting.suspendConfigConfirmTitle}
              </p>
              <p className="text-xs text-yellow-700 mt-1">
                {t.pretargeting.suspendConfigConfirmDesc}
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => suspendMutation.mutate()}
                  disabled={suspendMutation.isPending}
                  className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 disabled:opacity-50"
                >
                  {suspendMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Pause className="h-4 w-4" />
                  )}
                  {t.pretargeting.yesSuspend}
                </button>
                <button
                  onClick={() => setShowConfirmSuspend(false)}
                  disabled={suspendMutation.isPending}
                  className="px-3 py-1.5 bg-white text-gray-700 text-sm rounded border hover:bg-gray-50 disabled:opacity-50"
                >
                  {t.common.cancel}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {hasPendingChanges && (
        <div className="px-4 py-3 border-t bg-blue-50/60" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-blue-900">
                {t.pretargeting.pendingChangesTitle.replace('{count}', String(pendingChanges.length))}
              </p>
              <p className="text-xs text-blue-700">
                {t.pretargeting.clickPushToGoogleHint}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => discardAllMutation.mutate()}
                disabled={isPushing}
                className="px-2 py-1 text-xs bg-white text-gray-600 rounded border hover:bg-gray-50 disabled:opacity-50"
              >
                {t.pretargeting.discardAll}
              </button>
              <button
                onClick={() => setShowCommitToast(true)}
                disabled={isPushing}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <Upload className="h-3 w-3" />
                {t.pretargeting.pushToGoogle}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Expanded content */}
      {expanded && (
        <div className="border-t bg-gray-50/50">
          {/* Sticky action header with Pause/Activate and History */}
          <div className="sticky top-0 z-10 bg-gray-50 border-b px-4 py-2 flex items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              <GeoSettingPill geoIds={config.included_geos} max={5} resolveNames={expanded} />
              <SettingPill label={t.pretargeting.cardPlatformsLabel} values={config.platforms} />
              <SettingPill label={t.pretargeting.cardSizesLabel} values={config.sizes} max={4} />
            </div>
            <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
              {/* Format checkboxes inline */}
              <div className="flex items-center gap-2 text-xs text-slate-700">
                <span className="text-[11px] text-gray-500 font-medium">{t.pretargeting.formats}</span>
                {[
                  { label: t.pretargeting.cardFormatBanner, value: 'HTML' },
                  { label: t.pretargeting.cardFormatAudioVideo, value: 'VIDEO' },
                  { label: t.pretargeting.cardFormatNative, value: 'NATIVE' },
                ].map((formatOption) => (
                  <label key={formatOption.value} className="inline-flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={isFormatEnabled(formatOption.value)}
                      disabled={formatMutationPending}
                      onChange={(event) => setFormatEnabledState(formatOption.value, event.target.checked)}
                      className="h-3.5 w-3.5 rounded border-gray-300"
                    />
                    <span className="text-[11px]">{formatOption.label}</span>
                  </label>
                ))}
              </div>
              <div className="w-px h-5 bg-gray-300" />
              {/* Pause/Activate */}
              {config.state === 'ACTIVE' ? (
                <button
                  onClick={() => setShowConfirmSuspend(true)}
                  disabled={stateMutationPending}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-yellow-100 text-yellow-700 hover:bg-yellow-200 disabled:opacity-50"
                >
                  {suspendMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Pause className="h-3 w-3" />}
                  {t.pretargeting.suspendAction}
                </button>
              ) : (
                <button
                  onClick={() => activateMutation.mutate()}
                  disabled={stateMutationPending}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-green-100 text-green-700 hover:bg-green-200 disabled:opacity-50"
                >
                  {activateMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                  {t.pretargeting.activateAction}
                </button>
              )}
              {/* History toggle */}
              <button
                onClick={() => setShowHistory(!showHistory)}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors',
                  showHistory
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                <History className="h-3 w-3" />
                {t.pretargeting.historyShort}
              </button>
            </div>
          </div>

          {/* History Panel - toggled via button */}
          {showHistory && (
            <div className="px-4 pb-3 pt-2">
              <SnapshotComparisonPanel
                billing_id={config.billing_id}
                configName={config.name}
              />
            </div>
          )}
        </div>
      )}

      {!showCommitToast && hasPendingChanges && (
        <div className="fixed bottom-4 right-4 z-40 w-full max-w-sm rounded-lg border border-amber-200 bg-white shadow-lg">
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <div>
              <p className="text-sm font-medium text-amber-900">
                {pendingChangesCount} pending change{pendingChangesCount === 1 ? '' : 's'}
              </p>
              <p className="text-xs text-amber-700">{t.pretargeting.clickPushToGoogleHint}</p>
            </div>
            <button
              onClick={() => setShowCommitToast(true)}
              disabled={isPushing}
              className="inline-flex items-center gap-1 rounded bg-amber-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-600"
            >
              <Upload className="h-3 w-3" />
              Review
            </button>
          </div>
        </div>
      )}

      {showCommitToast && hasPendingChanges && (
        <div className="fixed bottom-4 right-4 z-50 w-full max-w-md rounded-lg border border-blue-200 bg-white shadow-xl">
          <div className="border-b border-blue-100 bg-blue-50 px-3 py-2">
            <p className="text-sm font-medium text-blue-900">
              {t.pretargeting.pushPendingChangesToGoogleConfirm.replace('{count}', String(pendingChanges.length))}
            </p>
            <p className="mt-1 text-xs text-blue-700">{t.pretargeting.pushConfirmLiveChangeWarning}</p>
          </div>
          <div className="max-h-40 overflow-y-auto px-3 py-2">
            {pendingChanges.length > 0 ? pendingChanges.map((change) => (
              <div key={`toast-${change.id}`} className="text-xs text-gray-700">
                • {change.change_type === 'set_maximum_qps'
                  ? t.pretargeting.pendingChangeSetQpsLimit.replace('{value}', change.value)
                  : change.change_type === 'add_format'
                    ? t.pretargeting.pendingChangeEnableFormat.replace('{value}', change.value)
                    : change.change_type === 'remove_format'
                      ? t.pretargeting.pendingChangeDisableFormat.replace('{value}', change.value)
                      : `${change.change_type}: ${change.value}`}
              </div>
            )) : (
              <div className="flex items-center gap-2 text-xs text-gray-700">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-400" />
                <span>{pendingChangesCount} pending change{pendingChangesCount === 1 ? '' : 's'} ready to push.</span>
              </div>
            )}
          </div>
          <div className="border-t border-gray-100 px-3 py-2 text-xs text-blue-700">
            {t.pretargeting.pushConfirmSnapshotCreated}
          </div>
          <div className="flex items-center justify-end gap-2 px-3 py-2">
            <button
              onClick={() => setShowCommitToast(false)}
              disabled={applyAllMutation.isPending || discardAllMutation.isPending}
              className="rounded border px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {t.common.back}
            </button>
            <button
              onClick={() => discardAllMutation.mutate()}
              disabled={applyAllMutation.isPending || discardAllMutation.isPending}
              className="inline-flex items-center gap-1 rounded border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              {discardAllMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {t.pretargeting.discardAll}
            </button>
            <button
              onClick={() => applyAllMutation.mutate()}
              disabled={applyAllMutation.isPending || discardAllMutation.isPending}
              className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {applyAllMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {t.pretargeting.yesPushToGoogle}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
