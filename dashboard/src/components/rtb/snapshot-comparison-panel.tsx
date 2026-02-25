'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSnapshots,
  createSnapshot,
  getComparisons,
  createComparison,
  rollbackSnapshot,
  type PretargetingSnapshot,
  type SnapshotComparison,
} from '@/lib/api';
import {
  Camera,
  GitCompare,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  History,
  X,
  RotateCcw,
  Loader2,
  Eye,
  Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/contexts/i18n-context';

interface SnapshotComparisonPanelProps {
  billing_id: string;
  configName: string;
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function formatCurrency(n: number): string {
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
}

function formatDate(dateStr: string, locale?: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  });
}

function DeltaIndicator({ value, suffix = '' }: { value: number | null; suffix?: string }) {
  if (value === null) return <span className="text-gray-400">-</span>;

  const isPositive = value > 0;
  const isNegative = value < 0;
  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-sm font-medium',
        isPositive && 'text-green-600',
        isNegative && 'text-red-600',
        !isPositive && !isNegative && 'text-gray-500'
      )}
    >
      <Icon className="h-3 w-3" />
      {isPositive && '+'}
      {value.toFixed(1)}
      {suffix}
    </span>
  );
}

/** Parse a JSON string field from the snapshot (sizes, geos, formats are stored as JSON strings). */
function parseSnapshotList(value: string | null): string[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** Summarize a list with "item1, item2 + N more" format. */
function summarizeList(items: string[], t: ReturnType<typeof useTranslation>['t'], max: number = 3): string {
  if (items.length === 0) return t.common.none;
  const shown = items.slice(0, max);
  const remainder = items.length - max;
  return remainder > 0
    ? t.pretargeting.snapshotPanelListPlusMore
      .replace('{items}', shown.join(', '))
      .replace('{count}', String(remainder))
    : shown.join(', ');
}

function SnapshotCard({
  snapshot,
  onRestore,
}: {
  snapshot: PretargetingSnapshot;
  onRestore: (snapshot: PretargetingSnapshot) => void;
}) {
  const { t, language } = useTranslation();
  const [showPreview, setShowPreview] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<{ changes_made: string[]; message: string } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const sizes = parseSnapshotList(snapshot.included_sizes);
  const geos = parseSnapshotList(snapshot.included_geos);
  const formats = parseSnapshotList(snapshot.included_formats);

  const handlePreview = () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }
    setShowPreview(true);
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewResult(null);
    rollbackSnapshot({ billing_id: snapshot.billing_id, snapshot_id: snapshot.id, dry_run: true })
      .then((result) => setPreviewResult(result))
      .catch((err) => setPreviewError(err?.message || t.pretargeting.failedToPreviewRollback))
      .finally(() => setPreviewLoading(false));
  };

  return (
    <div className="bg-white border rounded-lg p-3 text-sm">
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-medium text-gray-900">
            {snapshot.snapshot_name || t.pretargeting.snapshotNumber.replace('{id}', String(snapshot.id))}
          </div>
          <div className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(snapshot.created_at, language)}
            {snapshot.snapshot_type === 'before_change' && (
              <span className="ml-1 rounded bg-blue-100 px-1 py-0.5 text-[10px] text-blue-700">{t.pretargeting.snapshotPanelAutoTag}</span>
            )}
          </div>
        </div>
        <span
          className={cn(
            'px-2 py-0.5 rounded text-xs font-medium',
            snapshot.state === 'ACTIVE' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          )}
        >
          {snapshot.state || t.pretargeting.snapshotPanelStateUnknown}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelImpressions}</div>
          <div className="font-semibold">{formatNumber(snapshot.total_impressions)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelSpend}</div>
          <div className="font-semibold">{formatCurrency(snapshot.total_spend_usd)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelCtr}</div>
          <div className="font-semibold">{snapshot.ctr_pct?.toFixed(2) || '0'}%</div>
        </div>
      </div>

      {/* Config summary */}
      {(sizes.length > 0 || geos.length > 0 || formats.length > 0) && (
        <div className="mt-2 space-y-0.5 text-xs text-gray-600 border-t pt-2">
          {sizes.length > 0 && (
            <div>{t.pretargeting.snapshotPanelSizesLabel}: <span className="font-mono text-gray-700">{summarizeList(sizes, t)}</span></div>
          )}
          {geos.length > 0 && (
            <div>{t.pretargeting.snapshotPanelGeosLabel}: <span className="font-mono text-gray-700">{summarizeList(geos, t)}</span></div>
          )}
          {formats.length > 0 && (
            <div>{t.pretargeting.snapshotPanelFormatsLabel}: <span className="font-mono text-gray-700">{summarizeList(formats, t, 4)}</span></div>
          )}
        </div>
      )}

      {snapshot.notes && (
        <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
          {snapshot.notes}
        </div>
      )}

      {/* Preview restore diff (inline) */}
      {showPreview && (
        <div className="mt-2 rounded border border-orange-200 bg-orange-50/50 p-2">
          {previewLoading ? (
            <div className="flex items-center gap-1.5 py-2 text-xs text-gray-500 justify-center">
              <Loader2 className="h-3 w-3 animate-spin" />
              {t.pretargeting.previewingRollback}
            </div>
          ) : previewError ? (
            <div className="text-xs text-red-600">{previewError}</div>
          ) : previewResult && previewResult.changes_made.length === 0 ? (
            <div className="flex items-start gap-1.5 text-xs text-blue-700">
              <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
              {t.pretargeting.snapshotPanelNoDifferencesCurrentMatches}
            </div>
          ) : previewResult ? (
            <div className="space-y-1">
              <div className="text-xs font-medium text-orange-800">
                {t.pretargeting.snapshotPanelRestoreChangesCount.replace('{count}', String(previewResult.changes_made.length))}
              </div>
              <div className="max-h-28 overflow-y-auto space-y-0.5">
                {previewResult.changes_made.map((desc, i) => (
                  <div key={i} className="text-[11px] font-mono text-gray-700">{desc}</div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* Restore actions */}
      <div className="mt-2 flex items-center justify-end gap-2 pt-1 border-t">
        <button
          onClick={handlePreview}
          className={cn(
            'inline-flex items-center gap-1 px-2 py-1 text-xs rounded border transition-colors',
            showPreview
              ? 'border-orange-300 bg-orange-100 text-orange-800'
              : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
          )}
        >
          <Eye className="h-3 w-3" />
          {showPreview ? t.pretargeting.snapshotPanelHidePreview : t.pretargeting.snapshotPanelPreviewRestore}
        </button>
        <button
          onClick={() => onRestore(snapshot)}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100"
        >
          <RotateCcw className="h-3 w-3" />
          {t.pretargeting.snapshotPanelRestoreAction}
        </button>
      </div>
    </div>
  );
}

function ComparisonCard({ comparison }: { comparison: SnapshotComparison }) {
  const { t, language } = useTranslation();
  const isComplete = comparison.status === 'completed';

  return (
    <div className="bg-white border rounded-lg p-3 text-sm">
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-medium text-gray-900">{comparison.comparison_name}</div>
          <div className="text-xs text-gray-500">
            {formatDate(comparison.before_start_date, language)} - {formatDate(comparison.before_end_date, language)}
          </div>
        </div>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
            isComplete ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
          )}
        >
          {isComplete ? <CheckCircle className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
          {isComplete ? t.pretargeting.snapshotPanelComparisonCompleted : t.pretargeting.snapshotPanelComparisonInProgress}
        </span>
      </div>

      {isComplete && (
        <div className="grid grid-cols-3 gap-3 text-center mt-3 pt-3 border-t">
          <div>
            <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelImpressions}</div>
            <DeltaIndicator value={comparison.impressions_delta_pct} suffix="%" />
          </div>
          <div>
            <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelSpend}</div>
            <DeltaIndicator value={comparison.spend_delta_pct} suffix="%" />
          </div>
          <div>
            <div className="text-xs text-gray-500">{t.pretargeting.snapshotPanelCtr}</div>
            <DeltaIndicator value={comparison.ctr_delta_pct} suffix="%" />
          </div>
        </div>
      )}

      {comparison.conclusion && (
        <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
          {comparison.conclusion}
        </div>
      )}
    </div>
  );
}

export function SnapshotComparisonPanel({ billing_id, configName }: SnapshotComparisonPanelProps) {
  const { t, language } = useTranslation();
  const [showDialog, setShowDialog] = useState(false);
  const [showCreateSnapshot, setShowCreateSnapshot] = useState(false);
  const [snapshotName, setSnapshotName] = useState('');
  const [snapshotNotes, setSnapshotNotes] = useState('');
  const [restoreSnapshot, setRestoreSnapshot] = useState<PretargetingSnapshot | null>(null);
  const [restoreDryRunResult, setRestoreDryRunResult] = useState<{ changes_made: string[]; message: string } | null>(null);
  const [restoreDryRunLoading, setRestoreDryRunLoading] = useState(false);
  const [restoreDryRunError, setRestoreDryRunError] = useState<string | null>(null);
  const [restoreReason, setRestoreReason] = useState('');
  const [restoreSuccess, setRestoreSuccess] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: snapshots, isLoading: snapshotsLoading } = useQuery({
    queryKey: ['snapshots', billing_id],
    queryFn: () => getSnapshots({ billing_id, limit: 10 }),
    enabled: showDialog,
  });

  const { data: comparisons, isLoading: comparisonsLoading } = useQuery({
    queryKey: ['comparisons', billing_id],
    queryFn: () => getComparisons({ billing_id, limit: 10 }),
    enabled: showDialog,
  });

  const createSnapshotMutation = useMutation({
    mutationFn: createSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snapshots', billing_id] });
      setShowCreateSnapshot(false);
      setSnapshotName('');
      setSnapshotNotes('');
    },
  });

  const restoreExecuteMutation = useMutation({
    mutationFn: async () => {
      if (!restoreSnapshot) throw new Error(t.pretargeting.snapshotPanelNoSnapshotSelected);
      return rollbackSnapshot({ billing_id, snapshot_id: restoreSnapshot.id, dry_run: false });
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['snapshots', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-snapshots'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown'] });
      queryClient.invalidateQueries({ queryKey: ['config-detail'] });
      const name = restoreSnapshot?.snapshot_name || t.pretargeting.snapshotNumber.replace('{id}', String(restoreSnapshot?.id));
      setRestoreSnapshot(null);
      setRestoreSuccess(
        t.pretargeting.snapshotPanelRestoreSuccess
          .replace('{name}', name)
          .replace('{count}', String(result.changes_made.length))
      );
    },
  });

  const handleOpenRestore = (snapshot: PretargetingSnapshot) => {
    setRestoreSnapshot(snapshot);
    setRestoreReason('');
    setRestoreDryRunResult(null);
    setRestoreDryRunError(null);
    setRestoreDryRunLoading(true);
    rollbackSnapshot({ billing_id, snapshot_id: snapshot.id, dry_run: true })
      .then((result) => setRestoreDryRunResult(result))
      .catch((err) => setRestoreDryRunError(err?.message || t.pretargeting.failedToPreviewRollback))
      .finally(() => setRestoreDryRunLoading(false));
  };

  const handleCreateSnapshot = () => {
    createSnapshotMutation.mutate({
      billing_id,
      snapshot_name: snapshotName || undefined,
      notes: snapshotNotes || undefined,
    });
  };

  const closeDialog = () => {
    setShowDialog(false);
    setShowCreateSnapshot(false);
    setSnapshotName('');
    setSnapshotNotes('');
    setRestoreSuccess(null);
  };

  return (
    <div className="border-t pt-2">
      <button
        onClick={() => setShowDialog(true)}
        className="w-full px-4 py-2 flex items-center justify-between text-sm text-gray-600 hover:bg-gray-50 rounded"
      >
        <span className="flex items-center gap-2">
          <History className="h-4 w-4" />
          {t.pretargeting.historyShort}
          {snapshots && snapshots.length > 0 && (
            <span className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">
              {t.pretargeting.snapshotPanelSnapshotsCount.replace('{count}', String(snapshots.length))}
            </span>
          )}
        </span>
        <span className="text-xs text-gray-400">{t.pretargeting.snapshotPanelOpen}</span>
      </button>

      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={closeDialog}
          />
          <div className="relative mx-4 max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border bg-white p-4 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="text-sm font-semibold text-gray-900">
                {t.pretargeting.snapshotPanelHistoryDialogTitle.replace('{name}', configName)}
              </h3>
              <button
                onClick={closeDialog}
                className="rounded p-1 text-gray-500 hover:bg-gray-100"
                aria-label={t.pretargeting.snapshotPanelCloseHistoryDialogAria}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          {/* Create Snapshot Section */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium text-blue-900 flex items-center gap-2">
                <Camera className="h-4 w-4" />
                {t.pretargeting.snapshotPanelTakeSnapshot}
              </div>
              <button
                onClick={() => setShowCreateSnapshot(!showCreateSnapshot)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {showCreateSnapshot ? t.common.cancel : t.pretargeting.snapshotPanelNewSnapshot}
              </button>
            </div>

            {showCreateSnapshot ? (
              <div className="space-y-2">
                <input
                  type="text"
                  placeholder={t.pretargeting.snapshotPanelSnapshotNamePlaceholder}
                  value={snapshotName}
                  onChange={(e) => setSnapshotName(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  placeholder={t.pretargeting.snapshotPanelSnapshotNotesPlaceholder}
                  value={snapshotNotes}
                  onChange={(e) => setSnapshotNotes(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={handleCreateSnapshot}
                  disabled={createSnapshotMutation.isPending}
                  className="w-full py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {createSnapshotMutation.isPending ? t.pretargeting.snapshotPanelCreatingSnapshot : t.pretargeting.snapshotPanelCreateSnapshot}
                </button>
              </div>
            ) : (
              <p className="text-xs text-blue-700">
                {t.pretargeting.snapshotPanelTakeSnapshotHint}
              </p>
            )}
          </div>

          {/* Snapshots List */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <Camera className="h-4 w-4" />
              {t.pretargeting.snapshotPanelSnapshotsTitle}
            </div>
            {snapshotsLoading ? (
              <div className="text-sm text-gray-500">{t.pretargeting.snapshotPanelLoadingSnapshots}</div>
            ) : snapshots && snapshots.length > 0 ? (
              <div className="space-y-2">
                {snapshots.map((snapshot) => (
                  <SnapshotCard key={snapshot.id} snapshot={snapshot} onRestore={handleOpenRestore} />
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 bg-gray-50 rounded p-3">
                {t.pretargeting.snapshotPanelNoSnapshots}
              </div>
            )}
          </div>

          {/* Comparisons List */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <GitCompare className="h-4 w-4" />
              {t.pretargeting.snapshotPanelComparisonsTitle}
            </div>
            {comparisonsLoading ? (
              <div className="text-sm text-gray-500">{t.pretargeting.snapshotPanelLoadingComparisons}</div>
            ) : comparisons && comparisons.length > 0 ? (
              <div className="space-y-2">
                {comparisons.map((comparison) => (
                  <ComparisonCard key={comparison.id} comparison={comparison} />
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 bg-gray-50 rounded p-3">
                {t.pretargeting.snapshotPanelNoComparisons}
              </div>
            )}
          </div>

          {/* Restore success banner */}
          {restoreSuccess && (
            <div className="flex items-center justify-between rounded-lg bg-green-50 border border-green-200 p-3">
              <div className="flex items-start gap-2 text-sm text-green-800">
                <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                {restoreSuccess}
              </div>
              <button onClick={() => setRestoreSuccess(null)} className="text-green-600 hover:text-green-800">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {restoreSnapshot && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setRestoreSnapshot(null)} />
          <div className="relative mx-4 w-full max-w-lg rounded-lg border bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="flex items-center gap-1.5 text-sm font-semibold text-gray-900">
                <RotateCcw className="h-4 w-4 text-orange-600" />
                {t.pretargeting.snapshotPanelRestoreSnapshotTitle}
              </h3>
              <button onClick={() => setRestoreSnapshot(null)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>

            {restoreDryRunLoading ? (
              <div className="flex items-center justify-center py-8 gap-2 text-gray-500 text-xs">
                <Loader2 className="h-4 w-4 animate-spin" />
                {t.pretargeting.previewingRollback}
              </div>
            ) : restoreDryRunError ? (
              <div className="rounded bg-red-50 border border-red-200 p-3 text-xs text-red-700">
                {restoreDryRunError}
              </div>
            ) : restoreDryRunResult && restoreDryRunResult.changes_made.length === 0 ? (
              <div className="rounded bg-blue-50 border border-blue-200 p-3 flex items-start gap-2 text-xs text-blue-700">
                <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                {t.pretargeting.noDifferencesFromSnapshot}
              </div>
            ) : (
              <>
                <div className="text-xs text-gray-600 mb-2">
                  {t.pretargeting.configLabel}: <span className="font-medium text-gray-900">{billing_id}</span>
                  {' '}&middot;{' '}
                  {t.pretargeting.restoringToLabel}: <span className="font-medium text-gray-900">
                    {restoreSnapshot.snapshot_name || t.pretargeting.snapshotNumber.replace('{id}', String(restoreSnapshot.id))}
                  </span>
                  {' '}&middot;{' '}
                  <span className="text-gray-500">{formatDate(restoreSnapshot.created_at, language)}</span>
                </div>
                {restoreDryRunResult && restoreDryRunResult.changes_made.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-medium text-gray-700 mb-1">
                      {t.pretargeting.snapshotPanelRestoreChangesWillBeApplied.replace('{count}', String(restoreDryRunResult.changes_made.length))}
                    </p>
                    <div className="max-h-32 overflow-y-auto rounded border bg-gray-50 p-2 space-y-0.5">
                      {restoreDryRunResult.changes_made.map((desc, i) => (
                        <div key={i} className="text-[11px] font-mono text-gray-700">{desc}</div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mb-3 rounded bg-amber-50 border border-amber-200 p-2 flex items-start gap-2 text-xs text-amber-800">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500 mt-0.5 flex-shrink-0" />
                  <span>{t.pretargeting.rollbackImmediateWarning}</span>
                </div>
                <div className="mb-3">
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t.pretargeting.snapshotPanelRestoreReasonLabel}
                  </label>
                  <input
                    type="text"
                    value={restoreReason}
                    onChange={(e) => setRestoreReason(e.target.value)}
                    placeholder={t.pretargeting.snapshotPanelRestoreReasonPlaceholder}
                    className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-orange-300"
                  />
                  <span className="text-[10px] text-gray-400">{t.pretargeting.requiredLabel}</span>
                </div>
              </>
            )}

            {restoreExecuteMutation.isError && (
              <div className="mb-3 rounded bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                {(restoreExecuteMutation.error as Error)?.message || t.pretargeting.rollbackFailed}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setRestoreSnapshot(null)}
                disabled={restoreExecuteMutation.isPending}
                className="rounded border px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {(!restoreDryRunResult || restoreDryRunResult.changes_made.length === 0) && !restoreDryRunLoading ? t.common.close : t.common.cancel}
              </button>
              {restoreDryRunResult && restoreDryRunResult.changes_made.length > 0 && (
                <button
                  onClick={() => restoreExecuteMutation.mutate()}
                  disabled={restoreExecuteMutation.isPending || !restoreReason.trim()}
                  className="inline-flex items-center gap-1 rounded bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-50"
                >
                  {restoreExecuteMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3 w-3" />
                  )}
                  {t.pretargeting.snapshotPanelRestoreAction}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
