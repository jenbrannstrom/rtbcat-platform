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

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
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
function summarizeList(items: string[], max: number = 3): string {
  if (items.length === 0) return 'None';
  const shown = items.slice(0, max);
  const remainder = items.length - max;
  return remainder > 0
    ? `${shown.join(', ')} + ${remainder} more`
    : shown.join(', ');
}

function SnapshotCard({
  snapshot,
  onRestore,
}: {
  snapshot: PretargetingSnapshot;
  onRestore: (snapshot: PretargetingSnapshot) => void;
}) {
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
      .catch((err) => setPreviewError(err?.message || 'Failed to preview restore'))
      .finally(() => setPreviewLoading(false));
  };

  return (
    <div className="bg-white border rounded-lg p-3 text-sm">
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-medium text-gray-900">
            {snapshot.snapshot_name || `Snapshot #${snapshot.id}`}
          </div>
          <div className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(snapshot.created_at)}
            {snapshot.snapshot_type === 'before_change' && (
              <span className="ml-1 rounded bg-blue-100 px-1 py-0.5 text-[10px] text-blue-700">auto</span>
            )}
          </div>
        </div>
        <span
          className={cn(
            'px-2 py-0.5 rounded text-xs font-medium',
            snapshot.state === 'ACTIVE' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          )}
        >
          {snapshot.state || 'Unknown'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <div className="text-xs text-gray-500">Impressions</div>
          <div className="font-semibold">{formatNumber(snapshot.total_impressions)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Spend</div>
          <div className="font-semibold">{formatCurrency(snapshot.total_spend_usd)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">CTR</div>
          <div className="font-semibold">{snapshot.ctr_pct?.toFixed(2) || '0'}%</div>
        </div>
      </div>

      {/* Config summary */}
      {(sizes.length > 0 || geos.length > 0 || formats.length > 0) && (
        <div className="mt-2 space-y-0.5 text-xs text-gray-600 border-t pt-2">
          {sizes.length > 0 && (
            <div>Sizes: <span className="font-mono text-gray-700">{summarizeList(sizes)}</span></div>
          )}
          {geos.length > 0 && (
            <div>Geos: <span className="font-mono text-gray-700">{summarizeList(geos)}</span></div>
          )}
          {formats.length > 0 && (
            <div>Formats: <span className="font-mono text-gray-700">{summarizeList(formats, 4)}</span></div>
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
              Previewing restore&hellip;
            </div>
          ) : previewError ? (
            <div className="text-xs text-red-600">{previewError}</div>
          ) : previewResult && previewResult.changes_made.length === 0 ? (
            <div className="flex items-start gap-1.5 text-xs text-blue-700">
              <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
              No differences found. Current config matches this snapshot.
            </div>
          ) : previewResult ? (
            <div className="space-y-1">
              <div className="text-xs font-medium text-orange-800">
                {previewResult.changes_made.length} change{previewResult.changes_made.length !== 1 ? 's' : ''} to restore:
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
          {showPreview ? 'Hide Preview' : 'Preview Restore'}
        </button>
        <button
          onClick={() => onRestore(snapshot)}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100"
        >
          <RotateCcw className="h-3 w-3" />
          Restore
        </button>
      </div>
    </div>
  );
}

function ComparisonCard({ comparison }: { comparison: SnapshotComparison }) {
  const isComplete = comparison.status === 'completed';

  return (
    <div className="bg-white border rounded-lg p-3 text-sm">
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-medium text-gray-900">{comparison.comparison_name}</div>
          <div className="text-xs text-gray-500">
            {formatDate(comparison.before_start_date)} - {formatDate(comparison.before_end_date)}
          </div>
        </div>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
            isComplete ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
          )}
        >
          {isComplete ? <CheckCircle className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
          {isComplete ? 'Completed' : 'In Progress'}
        </span>
      </div>

      {isComplete && (
        <div className="grid grid-cols-3 gap-3 text-center mt-3 pt-3 border-t">
          <div>
            <div className="text-xs text-gray-500">Impressions</div>
            <DeltaIndicator value={comparison.impressions_delta_pct} suffix="%" />
          </div>
          <div>
            <div className="text-xs text-gray-500">Spend</div>
            <DeltaIndicator value={comparison.spend_delta_pct} suffix="%" />
          </div>
          <div>
            <div className="text-xs text-gray-500">CTR</div>
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
      if (!restoreSnapshot) throw new Error('No snapshot selected');
      return rollbackSnapshot({ billing_id, snapshot_id: restoreSnapshot.id, dry_run: false });
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['snapshots', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-snapshots'] });
      queryClient.invalidateQueries({ queryKey: ['config-breakdown'] });
      queryClient.invalidateQueries({ queryKey: ['config-detail'] });
      const name = restoreSnapshot?.snapshot_name || `Snapshot #${restoreSnapshot?.id}`;
      setRestoreSnapshot(null);
      setRestoreSuccess(`Config restored to "${name}". ${result.changes_made.length} change${result.changes_made.length !== 1 ? 's' : ''} applied to Google.`);
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
      .catch((err) => setRestoreDryRunError(err?.message || 'Failed to preview restore'))
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
          History
          {snapshots && snapshots.length > 0 && (
            <span className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-xs">
              {snapshots.length} snapshot{snapshots.length !== 1 && 's'}
            </span>
          )}
        </span>
        <span className="text-xs text-gray-400">Open</span>
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
                History - {configName}
              </h3>
              <button
                onClick={closeDialog}
                className="rounded p-1 text-gray-500 hover:bg-gray-100"
                aria-label="Close history dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          {/* Create Snapshot Section */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium text-blue-900 flex items-center gap-2">
                <Camera className="h-4 w-4" />
                Take Snapshot
              </div>
              <button
                onClick={() => setShowCreateSnapshot(!showCreateSnapshot)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {showCreateSnapshot ? 'Cancel' : 'New Snapshot'}
              </button>
            </div>

            {showCreateSnapshot ? (
              <div className="space-y-2">
                <input
                  type="text"
                  placeholder="Snapshot name (e.g., Before geo expansion)"
                  value={snapshotName}
                  onChange={(e) => setSnapshotName(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  placeholder="Notes about this snapshot..."
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
                  {createSnapshotMutation.isPending ? 'Creating...' : 'Create Snapshot'}
                </button>
              </div>
            ) : (
              <p className="text-xs text-blue-700">
                Take a snapshot before making changes to track the "before" state.
                Compare results after changes to measure impact.
              </p>
            )}
          </div>

          {/* Snapshots List */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <Camera className="h-4 w-4" />
              Snapshots
            </div>
            {snapshotsLoading ? (
              <div className="text-sm text-gray-500">Loading snapshots...</div>
            ) : snapshots && snapshots.length > 0 ? (
              <div className="space-y-2">
                {snapshots.map((snapshot) => (
                  <SnapshotCard key={snapshot.id} snapshot={snapshot} onRestore={handleOpenRestore} />
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 bg-gray-50 rounded p-3">
                No snapshots yet. Create one before making changes to track impact.
              </div>
            )}
          </div>

          {/* Comparisons List */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <GitCompare className="h-4 w-4" />
              Comparisons
            </div>
            {comparisonsLoading ? (
              <div className="text-sm text-gray-500">Loading comparisons...</div>
            ) : comparisons && comparisons.length > 0 ? (
              <div className="space-y-2">
                {comparisons.map((comparison) => (
                  <ComparisonCard key={comparison.id} comparison={comparison} />
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 bg-gray-50 rounded p-3">
                No comparisons yet. After taking snapshots, you can compare before/after results.
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
                Restore Snapshot?
              </h3>
              <button onClick={() => setRestoreSnapshot(null)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>

            {restoreDryRunLoading ? (
              <div className="flex items-center justify-center py-8 gap-2 text-gray-500 text-xs">
                <Loader2 className="h-4 w-4 animate-spin" />
                Previewing restore&hellip;
              </div>
            ) : restoreDryRunError ? (
              <div className="rounded bg-red-50 border border-red-200 p-3 text-xs text-red-700">
                {restoreDryRunError}
              </div>
            ) : restoreDryRunResult && restoreDryRunResult.changes_made.length === 0 ? (
              <div className="rounded bg-blue-50 border border-blue-200 p-3 flex items-start gap-2 text-xs text-blue-700">
                <Info className="h-3.5 w-3.5 text-blue-500 mt-0.5 flex-shrink-0" />
                No differences found between current config and this snapshot. Config already matches.
              </div>
            ) : (
              <>
                <div className="text-xs text-gray-600 mb-2">
                  Config: <span className="font-medium text-gray-900">{billing_id}</span>
                  {' '}&middot;{' '}
                  Restoring to: <span className="font-medium text-gray-900">
                    {restoreSnapshot.snapshot_name || `Snapshot #${restoreSnapshot.id}`}
                  </span>
                  {' '}&middot;{' '}
                  <span className="text-gray-500">{formatDate(restoreSnapshot.created_at)}</span>
                </div>
                {restoreDryRunResult && restoreDryRunResult.changes_made.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs font-medium text-gray-700 mb-1">
                      {restoreDryRunResult.changes_made.length} change{restoreDryRunResult.changes_made.length !== 1 ? 's' : ''} will be applied to Google:
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
                  <span>This pushes to Google immediately. A &ldquo;ROLLBACK&rdquo; entry will be recorded in history.</span>
                </div>
                <div className="mb-3">
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Why are you restoring this snapshot?
                  </label>
                  <input
                    type="text"
                    value={restoreReason}
                    onChange={(e) => setRestoreReason(e.target.value)}
                    placeholder="e.g. Rolling back bad config change"
                    className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-orange-300"
                  />
                  <span className="text-[10px] text-gray-400">(required)</span>
                </div>
              </>
            )}

            {restoreExecuteMutation.isError && (
              <div className="mb-3 rounded bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                {(restoreExecuteMutation.error as Error)?.message || 'Restore failed'}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setRestoreSnapshot(null)}
                disabled={restoreExecuteMutation.isPending}
                className="rounded border px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {(!restoreDryRunResult || restoreDryRunResult.changes_made.length === 0) && !restoreDryRunLoading ? 'Close' : 'Cancel'}
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
                  Restore Snapshot
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
