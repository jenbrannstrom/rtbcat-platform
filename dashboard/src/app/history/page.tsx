'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  History,
  Clock,
  RotateCcw,
  Filter,
  Download,
  Check,
  X,
  AlertTriangle,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Bot,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getPretargetingHistory, type PretargetingHistoryItem } from '@/lib/api';

// Rollback modal component
function RollbackModal({
  change,
  onConfirm,
  onCancel,
  isLoading,
}: {
  change: PretargetingHistoryItem;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  isLoading: boolean;
}) {
  const [reason, setReason] = useState('');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5 text-orange-600" />
            <h2 className="text-lg font-semibold text-gray-900">Rollback Change</h2>
          </div>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-gray-600">You are about to rollback:</p>

          <div className="bg-gray-50 rounded-lg p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Config:</span>
              <span className="font-medium text-gray-900">{change.config_id}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Field:</span>
              <span className="font-medium text-gray-900">{change.field_changed}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Current:</span>
              <span className="font-mono text-sm text-gray-900 truncate max-w-[200px]">
                {change.new_value || '(empty)'}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Restore to:</span>
              <span className="font-mono text-sm text-blue-600 truncate max-w-[200px]">
                {change.old_value || '(empty)'}
              </span>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-800">
              This will restore the previous setting. You'll need to apply the change manually in
              Google Authorized Buyers.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Reason for rollback
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why are you rolling back this change?"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={isLoading || !reason.trim()}
            className={cn(
              'flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg transition-colors',
              'hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {isLoading ? (
              <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Rollback Now
          </button>
        </div>
      </div>
    </div>
  );
}

// Format date nicely
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Time ago helper
function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor(diff / (1000 * 60));

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (minutes > 0) return `${minutes}m ago`;
  return 'just now';
}

// Single history entry
function HistoryCard({
  entry,
  onRollback,
}: {
  entry: PretargetingHistoryItem;
  onRollback: () => void;
}) {
  const isAI = entry.change_source?.includes('ai') || entry.changed_by?.includes('ai');
  const isRollback = entry.change_type === 'rollback';
  const isAdd = entry.change_type.includes('add');
  const isRemove = entry.change_type.includes('remove');

  return (
    <div
      className={cn(
        'border rounded-lg p-4 transition-all hover:shadow-md',
        isRollback && 'bg-orange-50 border-orange-200',
        !isRollback && 'bg-white'
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div
            className={cn(
              'p-2 rounded-lg',
              isRollback && 'bg-orange-100',
              isAdd && !isRollback && 'bg-green-100',
              isRemove && !isRollback && 'bg-red-100',
              !isAdd && !isRemove && !isRollback && 'bg-gray-100'
            )}
          >
            {isRollback ? (
              <RotateCcw className="h-4 w-4 text-orange-600" />
            ) : isAdd ? (
              <TrendingUp className="h-4 w-4 text-green-600" />
            ) : isRemove ? (
              <TrendingDown className="h-4 w-4 text-red-600" />
            ) : (
              <Clock className="h-4 w-4 text-gray-500" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-gray-900">{entry.change_type}</span>
              <span className="text-gray-400">on</span>
              <span className="font-mono text-sm text-gray-600">{entry.field_changed}</span>
            </div>

            <div className="mt-1 text-sm text-gray-600">
              <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                {entry.config_id}
              </span>
            </div>

            {entry.new_value && (
              <div className="mt-2 text-sm">
                <span className="text-gray-500">Value: </span>
                <span className="font-mono text-gray-900 truncate">{entry.new_value}</span>
              </div>
            )}

            <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
              <span title={formatDate(entry.changed_at)}>
                <Clock className="h-3 w-3 inline mr-1" />
                {timeAgo(entry.changed_at)}
              </span>
              <span className="flex items-center gap-1">
                {isAI ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
                {entry.change_source || 'manual'}
              </span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {!isRollback && (
            <button
              onClick={onRollback}
              className="flex items-center gap-1 px-2 py-1 text-xs text-orange-600 hover:bg-orange-50 rounded transition-colors"
            >
              <RotateCcw className="h-3 w-3" />
              Rollback
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const [days, setDays] = useState(30);
  const [billingIdFilter, setBillingIdFilter] = useState<string>('');
  const [changeTypeFilter, setChangeTypeFilter] = useState<string>('');
  const [selectedChange, setSelectedChange] = useState<PretargetingHistoryItem | null>(null);
  const queryClient = useQueryClient();

  // Fetch history
  const { data: history, isLoading } = useQuery({
    queryKey: ['pretargeting-history', days, billingIdFilter],
    queryFn: () =>
      getPretargetingHistory({
        days,
        billing_id: billingIdFilter || undefined,
      }),
  });

  // Rollback mutation (placeholder - needs backend endpoint)
  const rollbackMutation = useMutation({
    mutationFn: async ({ changeId, reason }: { changeId: number; reason: string }) => {
      // TODO: Implement rollback endpoint
      console.log('Rolling back change', changeId, 'with reason:', reason);
      return { success: true };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history'] });
      setSelectedChange(null);
    },
  });

  // Filter history by change type
  const filteredHistory = (history || []).filter((entry) => {
    if (changeTypeFilter && !entry.change_type.includes(changeTypeFilter)) {
      return false;
    }
    return true;
  });

  // Get unique billing IDs for filter
  const uniqueBillingIds = [...new Set((history || []).map((h) => h.config_id))];

  // Get unique change types for filter
  const uniqueChangeTypes = [...new Set((history || []).map((h) => h.change_type.split('_')[0]))];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <History className="h-6 w-6 text-blue-600" />
            Change History
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Track and rollback pretargeting configuration changes
          </p>
        </div>
        <button className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
          <Download className="h-4 w-4" />
          Export
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Filters:</span>
          </div>

          {/* Days filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Period:</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>

          {/* Billing ID filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Config:</span>
            <select
              value={billingIdFilter}
              onChange={(e) => setBillingIdFilter(e.target.value)}
              className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All configs</option>
              {uniqueBillingIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>

          {/* Change type filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Type:</span>
            <select
              value={changeTypeFilter}
              onChange={(e) => setChangeTypeFilter(e.target.value)}
              className="px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All types</option>
              {uniqueChangeTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {(billingIdFilter || changeTypeFilter) && (
            <button
              onClick={() => {
                setBillingIdFilter('');
                setChangeTypeFilter('');
              }}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* History List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filteredHistory.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
            <History className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <h3 className="font-medium text-gray-900 mb-2">No changes found</h3>
            <p className="text-sm text-gray-500">
              {billingIdFilter || changeTypeFilter
                ? 'Try adjusting your filters.'
                : 'Configuration changes will appear here.'}
            </p>
          </div>
        ) : (
          <>
            <div className="text-sm text-gray-500 mb-2">
              Showing {filteredHistory.length} change{filteredHistory.length !== 1 ? 's' : ''}{' '}
              from the last {days} days
            </div>
            {filteredHistory.map((entry) => (
              <HistoryCard
                key={entry.id}
                entry={entry}
                onRollback={() => setSelectedChange(entry)}
              />
            ))}
          </>
        )}
      </div>

      {/* Rollback Modal */}
      {selectedChange && (
        <RollbackModal
          change={selectedChange}
          onConfirm={(reason) =>
            rollbackMutation.mutate({ changeId: selectedChange.id, reason })
          }
          onCancel={() => setSelectedChange(null)}
          isLoading={rollbackMutation.isPending}
        />
      )}
    </div>
  );
}
