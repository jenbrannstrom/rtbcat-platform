'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPretargetingConfigDetail,
  getPretargetingHistory,
  createPendingChange,
  cancelPendingChange,
  markChangeApplied,
  type ConfigDetail,
  type PendingChange,
  type PretargetingHistoryItem,
} from '@/lib/api';
import {
  Settings,
  X,
  Plus,
  Minus,
  Clock,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  History,
  Globe,
  LayoutGrid,
  FileType,
  Ban,
  ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface PretargetingSettingsEditorProps {
  billing_id: string;
  configName: string;
  onClose?: () => void;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Pill component for displaying values with remove action
function ValuePill({
  value,
  isPending,
  isRemoved,
  onRemove,
}: {
  value: string;
  isPending?: boolean;
  isRemoved?: boolean;
  onRemove?: () => void;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-all',
        isRemoved && 'bg-red-100 text-red-700 line-through opacity-60',
        isPending && !isRemoved && 'bg-yellow-100 text-yellow-800 border border-yellow-300',
        !isPending && !isRemoved && 'bg-gray-100 text-gray-700 hover:bg-gray-200'
      )}
    >
      {value}
      {onRemove && !isRemoved && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 text-gray-400 hover:text-red-600 transition-colors"
          title="Remove"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  );
}

// Pending change card
function PendingChangeCard({
  change,
  onCancel,
  onMarkApplied,
}: {
  change: PendingChange;
  onCancel: () => void;
  onMarkApplied: () => void;
}) {
  const isRemove = change.change_type.startsWith('remove_');
  const Icon = isRemove ? Minus : Plus;

  return (
    <div className="flex items-center justify-between p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-4 w-4', isRemove ? 'text-red-500' : 'text-green-500')} />
        <span className="font-medium">{change.value}</span>
        <span className="text-gray-500">({change.field_name})</span>
        {change.reason && (
          <span className="text-xs text-gray-400 italic">- {change.reason}</span>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={onMarkApplied}
          className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
          title="Mark as applied in Google"
        >
          Applied
        </button>
        <button
          onClick={onCancel}
          className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
          title="Cancel change"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// Section for a targeting type (sizes, geos, formats)
function TargetingSection({
  title,
  icon: Icon,
  values,
  pendingAdds,
  pendingRemoves,
  onAddValue,
  onRemoveValue,
  onSelectAll,
  onInvertAll,
  fieldName,
  showBulkActions = false,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  values: string[];
  pendingAdds: string[];
  pendingRemoves: string[];
  onAddValue: (value: string) => void;
  onRemoveValue: (value: string) => void;
  onSelectAll?: () => void;
  onInvertAll?: () => void;
  fieldName: string;
  showBulkActions?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [newValue, setNewValue] = useState('');

  const handleAdd = () => {
    if (newValue.trim()) {
      onAddValue(newValue.trim());
      setNewValue('');
    }
  };

  const effectiveValues = [
    ...values.filter(v => !pendingRemoves.includes(v)),
    ...pendingAdds,
  ];

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-gray-500" />
          <span className="font-medium text-gray-900">{title}</span>
          <span className="text-sm text-gray-500">({effectiveValues.length} values)</span>
          {pendingAdds.length > 0 && (
            <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">
              +{pendingAdds.length}
            </span>
          )}
          {pendingRemoves.length > 0 && (
            <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs rounded">
              -{pendingRemoves.length}
            </span>
          )}
        </div>
        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {isExpanded && (
        <div className="p-4 space-y-3">
          {/* Add new value */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder={`Add ${fieldName === 'included_sizes' ? 'size (e.g., 300x250)' : fieldName === 'included_geos' ? 'geo (e.g., US)' : 'format'}`}
              className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleAdd}
              disabled={!newValue.trim()}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          {/* Bulk actions */}
          {showBulkActions && values.length > 0 && (
            <div className="flex items-center gap-2 pb-2 border-b">
              <span className="text-xs text-gray-500">Bulk:</span>
              {onSelectAll && (
                <button
                  onClick={onSelectAll}
                  className="px-2 py-1 text-xs bg-red-50 text-red-600 rounded hover:bg-red-100 transition-colors"
                >
                  Remove All
                </button>
              )}
              {onInvertAll && (
                <button
                  onClick={onInvertAll}
                  className="px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
                >
                  Invert
                </button>
              )}
            </div>
          )}

          {/* Current values */}
          <div className="flex flex-wrap gap-2">
            {values.map((value) => (
              <ValuePill
                key={value}
                value={value}
                isRemoved={pendingRemoves.includes(value)}
                onRemove={() => onRemoveValue(value)}
              />
            ))}
            {pendingAdds.map((value) => (
              <ValuePill
                key={`pending-${value}`}
                value={value}
                isPending
              />
            ))}
          </div>

          {values.length === 0 && pendingAdds.length === 0 && (
            <p className="text-sm text-gray-500 italic">No values configured</p>
          )}
        </div>
      )}
    </div>
  );
}

// History entry component
function HistoryEntry({ entry }: { entry: PretargetingHistoryItem }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b last:border-0">
      <Clock className="h-4 w-4 text-gray-400 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-gray-900">{entry.change_type}</span>
          {entry.field_changed && (
            <span className="text-gray-500">on {entry.field_changed}</span>
          )}
        </div>
        {entry.new_value && (
          <p className="text-xs text-gray-600 mt-0.5 truncate">{entry.new_value}</p>
        )}
        <p className="text-xs text-gray-400 mt-1">
          {formatDate(entry.changed_at)} - {entry.change_source}
        </p>
      </div>
    </div>
  );
}

export function PretargetingSettingsEditor({
  billing_id,
  configName,
  onClose,
}: PretargetingSettingsEditorProps) {
  const [showHistory, setShowHistory] = useState(false);
  const queryClient = useQueryClient();

  // Fetch config detail
  const { data: configDetail, isLoading: configLoading } = useQuery({
    queryKey: ['pretargeting-detail', billing_id],
    queryFn: () => getPretargetingConfigDetail(billing_id),
  });

  // Fetch history
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['pretargeting-history', billing_id],
    queryFn: () => getPretargetingHistory({ billing_id, days: 90 }),
    enabled: showHistory,
  });

  // Mutations
  const createChangeMutation = useMutation({
    mutationFn: createPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
    },
  });

  const cancelChangeMutation = useMutation({
    mutationFn: cancelPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
    },
  });

  const markAppliedMutation = useMutation({
    mutationFn: markChangeApplied,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history', billing_id] });
    },
  });

  // Get pending changes by type
  const getPendingByType = (changeType: string): string[] => {
    if (!configDetail) return [];
    return configDetail.pending_changes
      .filter(c => c.change_type === changeType)
      .map(c => c.value);
  };

  const handleAddSize = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'add_size',
      field_name: 'included_sizes',
      value,
    });
  };

  const handleRemoveSize = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_size',
      field_name: 'included_sizes',
      value,
      reason: 'Blocking size to reduce QPS waste',
    });
  };

  const handleAddGeo = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'add_geo',
      field_name: 'included_geos',
      value,
    });
  };

  const handleRemoveGeo = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_geo',
      field_name: 'included_geos',
      value,
    });
  };

  const handleAddFormat = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'add_format',
      field_name: 'included_formats',
      value,
    });
  };

  const handleRemoveFormat = (value: string) => {
    createChangeMutation.mutate({
      billing_id,
      change_type: 'remove_format',
      field_name: 'included_formats',
      value,
    });
  };

  // Bulk action handlers for sizes
  const handleSelectAllSizes = () => {
    if (!configDetail) return;
    const pendingRemoves = getPendingByType('remove_size');
    // Remove all sizes that aren't already pending removal
    configDetail.included_sizes
      .filter(size => !pendingRemoves.includes(size))
      .forEach(size => {
        createChangeMutation.mutate({
          billing_id,
          change_type: 'remove_size',
          field_name: 'included_sizes',
          value: size,
          reason: 'Bulk removal to reduce QPS waste',
        });
      });
  };

  const handleInvertSizesSelection = () => {
    if (!configDetail) return;
    const pendingRemoves = getPendingByType('remove_size');

    configDetail.included_sizes.forEach(size => {
      if (pendingRemoves.includes(size)) {
        // Cancel the pending removal
        const pendingChange = configDetail.pending_changes.find(
          c => c.change_type === 'remove_size' && c.value === size
        );
        if (pendingChange) {
          cancelChangeMutation.mutate(pendingChange.id);
        }
      } else {
        // Add a pending removal
        createChangeMutation.mutate({
          billing_id,
          change_type: 'remove_size',
          field_name: 'included_sizes',
          value: size,
          reason: 'Bulk removal to reduce QPS waste',
        });
      }
    });
  };

  if (configLoading) {
    return (
      <div className="p-4 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
        <div className="space-y-3">
          <div className="h-12 bg-gray-100 rounded" />
          <div className="h-12 bg-gray-100 rounded" />
          <div className="h-12 bg-gray-100 rounded" />
        </div>
      </div>
    );
  }

  if (!configDetail) {
    return (
      <div className="p-4 text-center text-gray-500">
        <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-yellow-500" />
        <p>Failed to load config details</p>
      </div>
    );
  }

  const pendingChanges = configDetail.pending_changes || [];
  const hasPendingChanges = pendingChanges.length > 0;

  return (
    <div className="border-t bg-white">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-gray-500" />
          <span className="font-medium text-gray-900">Pretargeting Settings</span>
          {hasPendingChanges && (
            <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs rounded-full">
              {pendingChanges.length} pending
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={cn(
              'flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors',
              showHistory ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <History className="h-3 w-3" />
            History
          </button>
          {onClose && (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Warning banner */}
      <div className="px-4 py-2 bg-amber-50 border-b border-amber-200">
        <div className="flex items-start gap-2 text-xs text-amber-800">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Changes are staged locally only</p>
            <p className="mt-0.5">
              After making changes here, apply them manually in{' '}
              <a
                href="https://admanager.google.com/authorizedbuyers"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-700 underline hover:text-amber-900 inline-flex items-center gap-0.5"
              >
                Google Authorized Buyers
                <ExternalLink className="h-3 w-3" />
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Pending changes section */}
        {hasPendingChanges && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-yellow-800 flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Pending Changes ({pendingChanges.length})
              </h4>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    // Mark all as applied
                    pendingChanges.forEach(c => markAppliedMutation.mutate(c.id));
                  }}
                  className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors"
                >
                  Apply All
                </button>
                <button
                  onClick={() => {
                    // Cancel all pending changes
                    pendingChanges.forEach(c => cancelChangeMutation.mutate(c.id));
                  }}
                  className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
                >
                  Clear All
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {pendingChanges.map((change) => (
                <PendingChangeCard
                  key={change.id}
                  change={change}
                  onCancel={() => cancelChangeMutation.mutate(change.id)}
                  onMarkApplied={() => markAppliedMutation.mutate(change.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Targeting sections */}
        <TargetingSection
          title="Ad Sizes"
          icon={LayoutGrid}
          values={configDetail.included_sizes}
          pendingAdds={getPendingByType('add_size')}
          pendingRemoves={getPendingByType('remove_size')}
          onAddValue={handleAddSize}
          onRemoveValue={handleRemoveSize}
          onSelectAll={handleSelectAllSizes}
          onInvertAll={handleInvertSizesSelection}
          fieldName="included_sizes"
          showBulkActions={true}
        />

        <TargetingSection
          title="Geographic Targeting"
          icon={Globe}
          values={configDetail.included_geos}
          pendingAdds={getPendingByType('add_geo')}
          pendingRemoves={getPendingByType('remove_geo')}
          onAddValue={handleAddGeo}
          onRemoveValue={handleRemoveGeo}
          fieldName="included_geos"
        />

        <TargetingSection
          title="Formats"
          icon={FileType}
          values={configDetail.included_formats}
          pendingAdds={getPendingByType('add_format')}
          pendingRemoves={getPendingByType('remove_format')}
          onAddValue={handleAddFormat}
          onRemoveValue={handleRemoveFormat}
          fieldName="included_formats"
        />

        {/* Excluded geos (read-only for now) */}
        {configDetail.excluded_geos.length > 0 && (
          <div className="border rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Ban className="h-4 w-4 text-red-500" />
              <span className="font-medium text-gray-900">Excluded Geos</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {configDetail.excluded_geos.map((geo) => (
                <span
                  key={geo}
                  className="px-2 py-0.5 bg-red-50 text-red-700 rounded text-xs"
                >
                  {geo}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Last sync info */}
        {configDetail.synced_at && (
          <p className="text-xs text-gray-400 text-center">
            Last synced from Google: {formatDate(configDetail.synced_at)}
          </p>
        )}
      </div>

      {/* History panel */}
      {showHistory && (
        <div className="border-t bg-gray-50 p-4">
          <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
            <History className="h-4 w-4" />
            Change History
          </h4>
          {historyLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : history && history.length > 0 ? (
            <div className="max-h-64 overflow-y-auto">
              {history.map((entry) => (
                <HistoryEntry key={entry.id} entry={entry} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">No history available</p>
          )}
        </div>
      )}
    </div>
  );
}
