'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSnapshots,
  createSnapshot,
  getComparisons,
  createComparison,
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
  History,
  X,
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

function SnapshotCard({ snapshot }: { snapshot: PretargetingSnapshot }) {
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

      {snapshot.notes && (
        <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
          {snapshot.notes}
        </div>
      )}
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
                  <SnapshotCard key={snapshot.id} snapshot={snapshot} />
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
        </div>
        </div>
      )}
    </div>
  );
}
