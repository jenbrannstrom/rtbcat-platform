'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPretargetingConfigDetail,
  getPretargetingHistory,
  createPendingChange,
  cancelPendingChange,
  markChangeApplied,
  applyAllPendingChanges,
  discardAllPretargetingChanges,
  suspendPretargeting,
  activatePretargeting,
  syncPretargetingConfigs,
  getSnapshots,
  rollbackSnapshot,
  getPretargetingPublishers,
  addPretargetingPublisher,
  removePretargetingPublisher,
  type PendingChange,
  type PretargetingHistoryItem,
  type PretargetingSnapshot,
  type PretargetingPublisher,
} from '@/lib/api';
import {
  X,
  Plus,
  Minus,
  Clock,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  History,
  Globe,
  LayoutGrid,
  FileType,
  Shield,
  Search,
  Ban,
  Upload,
  Pause,
  Play,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { useTranslation } from '@/contexts/i18n-context';
import type { Translations } from '@/lib/i18n/types';
import { cn } from '@/lib/utils';
import { isValidPublisherId, detectPublisherType } from '@/lib/publisher-validation';

interface PretargetingSettingsEditorProps {
  billing_id: string;
  configName?: string;
  onClose?: () => void;
  initialTab?: 'publishers' | 'settings';
  hideTabs?: boolean;
}

type MajorChangeType = 'targeting' | 'publisher' | 'qps' | 'mixed';

function formatDate(dateStr: string, locale?: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function normalizePublisherId(value: string): string {
  return value.trim();
}

function formatCodeLabel(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatHistoryFieldLabel(field: string, t: Translations): string {
  switch (field) {
    case 'publisher_targeting':
      return t.pretargeting.historyFieldPublisherTargeting;
    case 'publisher_targeting_mode':
      return t.pretargeting.historyFieldPublisherTargetingMode;
    case 'included_sizes':
      return t.pretargeting.historyFieldIncludedSizes;
    case 'included_geos':
      return t.pretargeting.historyFieldIncludedGeos;
    case 'included_formats':
      return t.pretargeting.historyFieldIncludedFormats;
    case 'excluded_geos':
      return t.pretargeting.historyFieldExcludedGeos;
    case 'state':
      return t.pretargeting.historyFieldState;
    default:
      return formatCodeLabel(field);
  }
}

function formatHistorySourceLabel(source: string, t: Translations): string {
  switch (source.toLowerCase()) {
    case 'ui':
      return t.pretargeting.historySourceUi;
    case 'google_sync':
    case 'sync':
      return t.pretargeting.historySourceGoogleSync;
    case 'rollback':
      return t.pretargeting.historySourceRollback;
    case 'system':
      return t.pretargeting.historySourceSystem;
    case 'api':
      return t.pretargeting.historySourceApi;
    default:
      return formatCodeLabel(source);
  }
}

function formatSnapshotTypeLabel(snapshotType: string | null | undefined, t: Translations): string {
  const value = (snapshotType || '').toLowerCase();
  switch (value) {
    case '':
    case 'manual':
      return t.pretargeting.snapshotTypeManual;
    case 'auto':
    case 'automatic':
      return t.pretargeting.snapshotTypeAuto;
    case 'pre_push':
    case 'before_push':
    case 'auto_before_push':
      return t.pretargeting.snapshotTypePrePush;
    case 'rollback':
    case 'pre_rollback':
    case 'before_rollback':
      return t.pretargeting.snapshotTypeRollback;
    case 'sync':
    case 'google_sync':
      return t.pretargeting.snapshotTypeSync;
    default:
      return formatCodeLabel(value);
  }
}

function formatConfigStateLabel(state: string | null | undefined, t: Translations): string {
  const value = (state || '').toUpperCase();
  switch (value) {
    case 'ACTIVE':
      return t.pretargeting.configStateActive;
    case 'SUSPENDED':
      return t.pretargeting.configStateSuspended;
    default:
      return state || '';
  }
}

function formatHistoryChangeTypeLabel(changeType: string, t: Translations): string {
  const keyMap: Record<string, string> = {
    add_size: t.pretargeting.historyChangeTypeAddSize,
    remove_size: t.pretargeting.historyChangeTypeRemoveSize,
    add_geo: t.pretargeting.historyChangeTypeAddGeo,
    remove_geo: t.pretargeting.historyChangeTypeRemoveGeo,
    add_format: t.pretargeting.historyChangeTypeAddFormat,
    remove_format: t.pretargeting.historyChangeTypeRemoveFormat,
    add_publisher: t.pretargeting.historyChangeTypeAddPublisher,
    remove_publisher: t.pretargeting.historyChangeTypeRemovePublisher,
    set_publisher_mode: t.pretargeting.historyChangeTypeSetPublisherMode,
    major_commit: t.pretargeting.pushToGoogle,
  };
  return keyMap[changeType] || formatCodeLabel(changeType);
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
  pendingChanges: PendingChange[],
  hasPendingPublisherRows: boolean
): MajorChangeType | null {
  const majorTypes = new Set<Exclude<MajorChangeType, 'mixed'>>();
  pendingChanges.forEach((change) => {
    majorTypes.add(getMajorChangeType(change.change_type));
  });
  if (hasPendingPublisherRows) {
    majorTypes.add('publisher');
  }
  if (majorTypes.size === 0) {
    return null;
  }
  if (majorTypes.size === 1) {
    return Array.from(majorTypes)[0];
  }
  return 'mixed';
}

// isValidPublisherId and detectPublisherType imported from @/lib/publisher-validation

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
  const { t } = useTranslation();
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
          title={t.pretargeting.remove}
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  );
}

function describePendingChange(
  change: PendingChange,
  publisherMode: string | null | undefined,
  t: Translations
): string {
  const currentModeLabel = publisherMode === 'INCLUSIVE'
    ? t.pretargeting.publisherModeWhitelist
    : t.pretargeting.publisherModeBlacklist;
  const addLabel = publisherMode === 'INCLUSIVE' ? t.pretargeting.allow : t.pretargeting.block;
  const removeLabel = publisherMode === 'INCLUSIVE' ? t.pretargeting.remove : t.pretargeting.unblock;
  const nextModeLabel = change.value === 'INCLUSIVE'
    ? t.pretargeting.publisherModeWhitelist
    : change.value === 'EXCLUSIVE'
      ? t.pretargeting.publisherModeBlacklist
      : (change.value || '');

  switch (change.change_type) {
    case 'add_size':
      return t.pretargeting.pendingChangeAllowSize.replace('{value}', String(change.value || ''));
    case 'remove_size':
      return t.pretargeting.pendingChangeBlockSize.replace('{value}', String(change.value || ''));
    case 'add_geo':
      return t.pretargeting.pendingChangeAddGeo.replace('{value}', String(change.value || ''));
    case 'remove_geo':
      return t.pretargeting.pendingChangeRemoveGeo.replace('{value}', String(change.value || ''));
    case 'add_format':
      return t.pretargeting.pendingChangeEnableFormat.replace('{value}', String(change.value || ''));
    case 'remove_format':
      return t.pretargeting.pendingChangeDisableFormat.replace('{value}', String(change.value || ''));
    case 'add_excluded_geo':
      return t.pretargeting.pendingChangeFallback
        .replace('{changeType}', t.pretargeting.pendingChangeAddExcludedGeo)
        .replace('{value}', String(change.value || ''));
    case 'remove_excluded_geo':
      return t.pretargeting.pendingChangeFallback
        .replace('{changeType}', t.pretargeting.pendingChangeRemoveExcludedGeo)
        .replace('{value}', String(change.value || ''));
    case 'add_publisher':
      return `${addLabel}: ${change.value}`;
    case 'remove_publisher':
      return `${removeLabel}: ${change.value}`;
    case 'set_publisher_mode':
      return t.pretargeting.pendingChangePublisherModeDetailed
        .replace('{current}', currentModeLabel)
        .replace('{next}', nextModeLabel || String(change.value || ''));
    default:
      return t.pretargeting.pendingChangeFallback
        .replace('{changeType}', change.change_type)
        .replace('{value}', String(change.value || ''));
  }
}

// Pending change card
function PendingChangeCard({
  change,
  onCancel,
  onMarkApplied,
  publisherMode,
}: {
  change: PendingChange;
  onCancel: () => void;
  onMarkApplied: () => void;
  publisherMode?: string | null;
}) {
  const { t } = useTranslation();
  const isRemove = change.change_type.startsWith('remove_');
  const Icon = isRemove ? Minus : Plus;
  const label = describePendingChange(change, publisherMode, t);

  return (
    <div className="flex items-center justify-between p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-4 w-4', isRemove ? 'text-red-500' : 'text-green-500')} />
        <span className="font-medium">{label}</span>
        {change.reason && (
          <span className="text-xs text-gray-400 italic">- {change.reason}</span>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={onMarkApplied}
          className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200"
          title={t.pretargeting.markAsAppliedInGoogle}
        >
          {t.pretargeting.applied}
        </button>
        <button
          onClick={onCancel}
          className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
          title={t.pretargeting.cancelChange}
        >
          {t.common.cancel}
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
  const { t } = useTranslation();
  const [newValue, setNewValue] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);

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
          <span className="text-sm text-gray-500">
            ({t.pretargeting.valuesCount.replace('{count}', String(effectiveValues.length))})
          </span>
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
              placeholder={
                fieldName === 'included_sizes'
                  ? t.pretargeting.addSizePlaceholder
                  : fieldName === 'included_geos'
                    ? t.pretargeting.addGeoPlaceholder
                    : t.pretargeting.addFormatPlaceholder
              }
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
              <span className="text-xs text-gray-500">{t.pretargeting.bulkLabel}</span>
              {onSelectAll && (
                <button
                  onClick={onSelectAll}
                  className="px-2 py-1 text-xs bg-red-50 text-red-600 rounded hover:bg-red-100 transition-colors"
                >
                  {t.pretargeting.removeAll}
                </button>
              )}
              {onInvertAll && (
                <button
                  onClick={onInvertAll}
                  className="px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
                >
                  {t.pretargeting.invertSelection}
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
            <p className="text-sm text-gray-500 italic">{t.pretargeting.noValuesConfigured}</p>
          )}
        </div>
      )}
    </div>
  );
}

function PublisherTargetingSection({
  baseMode,
  publishers,
  pendingModeChange,
  onAddPublisher,
  onRemovePublisher,
  onUndoPublisher,
  onSetMode,
  onShowHistory,
  onApplyPending,
  onDiscardPending,
  onBulkAdd,
  onExportCsv,
  disabled = false,
}: {
  baseMode: string | null | undefined;
  publishers: PretargetingPublisher[];
  pendingModeChange: PendingChange | null;
  onAddPublisher: (value: string) => void;
  onRemovePublisher: (publisherId: string) => void;
  onUndoPublisher: (publisherId: string) => void;
  onSetMode: (mode: string) => void;
  onShowHistory: () => void;
  onApplyPending: () => void;
  onDiscardPending: () => void;
  onBulkAdd: (values: string[]) => void;
  onExportCsv: (values: string[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('');
  const [newPublisher, setNewPublisher] = useState('');
  const [inputError, setInputError] = useState<string | null>(null);
  const [showModeConfirm, setShowModeConfirm] = useState(false);
  const [nextMode, setNextMode] = useState<string>('EXCLUSIVE');
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkInput, setBulkInput] = useState('');
  const [bulkPreview, setBulkPreview] = useState<{
    valid: string[];
    duplicates: string[];
    invalid: string[];
  } | null>(null);

  const pendingMode = pendingModeChange?.value || null;
  const effectiveMode = pendingMode || baseMode || 'EXCLUSIVE';

  // Count publishers by status
  const activeCount = publishers.filter(p => p.status === 'active').length;
  const pendingAddCount = publishers.filter(p => p.status === 'pending_add').length;
  const pendingRemoveCount = publishers.filter(p => p.status === 'pending_remove').length;
  const totalPendingCount = pendingAddCount + pendingRemoveCount;

  // Filter publishers
  const filteredPublishers = publishers.filter((p) =>
    p.publisher_id.toLowerCase().includes(filter.trim().toLowerCase())
  );

  const isWhitelist = effectiveMode === 'INCLUSIVE';
  const modeLabel = effectiveMode === 'INCLUSIVE'
    ? t.pretargeting.publisherModeWhitelist
    : effectiveMode === 'EXCLUSIVE'
      ? t.pretargeting.publisherModeBlacklist
      : t.pretargeting.noPublisherTargeting;
  const statusLabel = isWhitelist ? t.pretargeting.statusAllowed : t.pretargeting.statusBlocked;
  const actionLabel = isWhitelist ? t.pretargeting.allow : t.pretargeting.block;

  const handleAdd = () => {
    const normalized = normalizePublisherId(newPublisher);
    if (!normalized) return;
    if (!isValidPublisherId(normalized)) {
      setInputError(t.pretargeting.invalidPublisherIdFormatLong);
      return;
    }
    // Check if already exists
    const existingPublisher = publishers.find(p => p.publisher_id === normalized);
    if (existingPublisher && existingPublisher.status !== 'pending_remove') {
      setInputError(t.pretargeting.publisherAlreadyInList);
      return;
    }
    setInputError(null);
    onAddPublisher(normalized);
    setNewPublisher('');
  };

  const handleModeRequest = (mode: string) => {
    if (mode === effectiveMode) return;
    setNextMode(mode);
    setShowModeConfirm(true);
  };

  const confirmModeChange = () => {
    setShowModeConfirm(false);
    onSetMode(nextMode);
  };

  const parseBulkInput = () => {
    const tokens = bulkInput
      .split(/[\n,]/)
      .map((item) => normalizePublisherId(item))
      .filter(Boolean);
    const valid: string[] = [];
    const duplicates: string[] = [];
    const invalid: string[] = [];
    const existingIds = new Set(publishers.filter(p => p.status !== 'pending_remove').map(p => p.publisher_id));

    tokens.forEach((value) => {
      if (!isValidPublisherId(value)) {
        invalid.push(value);
        return;
      }
      if (existingIds.has(value)) {
        duplicates.push(value);
        return;
      }
      if (!valid.includes(value)) {
        valid.push(value);
      }
    });

    setBulkPreview({ valid, duplicates, invalid });
  };

  const handleBulkImport = () => {
    if (!bulkPreview) return;
    if (bulkPreview.valid.length === 0) return;
    onBulkAdd(bulkPreview.valid);
    setBulkInput('');
    setBulkPreview(null);
    setShowBulkImport(false);
  };

  const handleExport = () => {
    onExportCsv(publishers.filter(p => p.status !== 'pending_remove').map(p => p.publisher_id));
  };

  const summaryLabel = publishers.length === 0 && !pendingMode
    ? t.pretargeting.noPublisherTargeting
    : `${modeLabel}: ${activeCount} ${isWhitelist ? t.pretargeting.allowedLower : t.pretargeting.blockedLower}`;
  const nextModeLabel = nextMode === 'INCLUSIVE'
    ? t.pretargeting.publisherModeWhitelist
    : nextMode === 'EXCLUSIVE'
      ? t.pretargeting.publisherModeBlacklist
      : nextMode;

  const renderStatusLabel = (status: string) => {
    if (status === 'pending_add' || status === 'pending_remove') {
      return `⏳ ${t.pretargeting.statusPending}`;
    }
    return statusLabel;
  };

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-gray-500" />
          <span className="font-medium text-gray-900">{t.pretargeting.publishersSectionTitle}</span>
          <span className="text-sm text-gray-500">{summaryLabel}</span>
        </div>
        <div className="flex items-center gap-3 text-sm font-medium text-gray-700">
          <span>{t.pretargeting.modeLabel}:</span>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="publisher-mode"
              checked={effectiveMode === 'EXCLUSIVE'}
              onChange={() => handleModeRequest('EXCLUSIVE')}
              disabled={disabled}
              className="sr-only"
            />
            <span
              className={cn(
                "h-2 w-2 rounded-full border",
                effectiveMode === 'EXCLUSIVE' ? "bg-gray-900 border-gray-900" : "bg-white border-gray-300"
              )}
            />
            {t.pretargeting.publisherModeBlacklist}
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="publisher-mode"
              checked={effectiveMode === 'INCLUSIVE'}
              onChange={() => handleModeRequest('INCLUSIVE')}
              disabled={disabled}
              className="sr-only"
            />
            <span
              className={cn(
                "h-2 w-2 rounded-full border",
                effectiveMode === 'INCLUSIVE' ? "bg-gray-900 border-gray-900" : "bg-white border-gray-300"
              )}
            />
            {t.pretargeting.publisherModeWhitelist}
          </label>
        </div>
      </div>

      <div className="p-4 space-y-4">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-gray-400" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t.pretargeting.filterPublishersPlaceholder}
            className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="overflow-hidden rounded border">
          <div className="grid grid-cols-[1fr_80px_100px_100px] gap-2 px-3 py-2 bg-gray-50 text-xs font-medium text-gray-500">
            <span>{t.pretargeting.publisherIdHeader}</span>
            <span>{t.pretargeting.typeHeader}</span>
            <span>{t.pretargeting.columnStatus}</span>
            <span className="text-right">{t.pretargeting.columnAction}</span>
          </div>
          {filteredPublishers.length === 0 ? (
            <div className="px-3 py-6 text-sm text-gray-500 text-center">
              {publishers.length === 0
                ? (isWhitelist ? t.pretargeting.noPublishersAllowedYet : t.pretargeting.noPublishersBlockedYet)
                : t.pretargeting.noPublishersMatchCurrentFilter}
            </div>
          ) : (
            <div className="divide-y max-h-80 overflow-y-auto">
              {filteredPublishers.map((pub) => {
                const isPendingAdd = pub.status === 'pending_add';
                const isPendingRemove = pub.status === 'pending_remove';
                return (
                  <div
                    key={pub.publisher_id}
                    className={cn(
                      'grid grid-cols-[1fr_80px_100px_100px] gap-2 px-3 py-2 text-sm items-center',
                      isPendingRemove && 'bg-red-50 text-gray-400 line-through'
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-xs text-gray-500" title={pub.publisher_id}>
                        {pub.publisher_id}
                      </div>
                    </div>
                    <span className="text-gray-500">{detectPublisherType(pub.publisher_id)}</span>
                    <span className="text-gray-600">{renderStatusLabel(pub.status)}</span>
                    <div className="text-right">
                      {isPendingAdd || isPendingRemove ? (
                        <button
                          onClick={() => onUndoPublisher(pub.publisher_id)}
                          className="px-2 py-1 text-xs rounded bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                          disabled={disabled}
                        >
                          {t.pretargeting.undo}
                        </button>
                      ) : (
                        <button
                          onClick={() => onRemovePublisher(pub.publisher_id)}
                          className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
                          disabled={disabled}
                        >
                          {t.pretargeting.remove}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-xs text-gray-500">
            {isWhitelist ? t.pretargeting.addPublisherToAllow : t.pretargeting.addPublisherToBlock}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newPublisher}
              onChange={(e) => {
                setNewPublisher(e.target.value);
                setInputError(null);
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder={t.pretargeting.publisherInputPlaceholder}
              className="flex-1 px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleAdd}
              disabled={!newPublisher.trim() || disabled}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {actionLabel}
            </button>
          </div>
          {inputError && (
            <p className="text-xs text-red-600">{inputError}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBulkImport(true)}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
          >
            <Upload className="h-3 w-3" />
            {t.pretargeting.bulkImport}
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
          >
            <Download className="h-3 w-3" />
            {t.pretargeting.exportCsv}
          </button>
          <button
            onClick={onShowHistory}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
          >
            <History className="h-3 w-3" />
            {t.pretargeting.viewHistory}
          </button>
        </div>

        {/* Pending Changes Bar (sticky) */}
        {totalPendingCount > 0 && (
          <div className="sticky bottom-4 z-10">
            <div className="border rounded-lg p-3 bg-yellow-50 border-yellow-200 shadow-sm">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <span className="text-sm font-medium text-yellow-800">
                  {t.pretargeting.pendingPublisherChangesSummary.replace('{count}', String(totalPendingCount))}
                </span>
              </div>
              <div className="mt-2 text-xs text-yellow-700 space-y-1">
                {pendingAddCount > 0 && (
                  <div>
                    • {(isWhitelist ? t.pretargeting.pendingPublishersToAdd : t.pretargeting.pendingPublishersToBlock)
                      .replace('{count}', String(pendingAddCount))}
                  </div>
                )}
                {pendingRemoveCount > 0 && (
                  <div>
                    • {(isWhitelist ? t.pretargeting.pendingPublishersToRemove : t.pretargeting.pendingPublishersToUnblock)
                      .replace('{count}', String(pendingRemoveCount))}
                  </div>
                )}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  onClick={onDiscardPending}
                  disabled={disabled}
                  className="px-3 py-1.5 text-xs bg-white text-gray-700 rounded border hover:bg-gray-50 disabled:opacity-50"
                >
                  {t.pretargeting.discardAll}
                </button>
                <button
                  onClick={onApplyPending}
                  disabled={disabled}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {t.pretargeting.pushToGoogle}
                </button>
                <span className="text-xs text-yellow-600">
                  {t.pretargeting.changesApplyImmediatelyOnGoogle}
                </span>
              </div>
            </div>
          </div>
        )}

        {showModeConfirm && (
          <div className="border rounded-lg bg-yellow-50 border-yellow-200 p-3 text-sm">
            <p className="font-medium text-yellow-900 mb-2">
              {t.pretargeting.switchToModePrompt.replace('{mode}', nextModeLabel)}
            </p>
            <p className="text-yellow-700 text-xs mb-3">
              {t.pretargeting.switchModeClearsPublisherListWarning}
            </p>
            <div className="flex gap-2">
              <button
                onClick={confirmModeChange}
                className="px-3 py-1.5 bg-yellow-600 text-white text-xs rounded hover:bg-yellow-700"
              >
                {t.pretargeting.switchToModeAction.replace('{mode}', nextModeLabel)}
              </button>
              <button
                onClick={() => setShowModeConfirm(false)}
                className="px-3 py-1.5 bg-white text-gray-700 text-xs rounded border hover:bg-gray-50"
              >
                {t.common.cancel}
              </button>
            </div>
          </div>
        )}

        {showBulkImport && (
          <div className="border rounded-lg p-3 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-900">{t.pretargeting.bulkImportPublishersTitle}</h4>
              <button
                onClick={() => {
                  setShowBulkImport(false);
                  setBulkPreview(null);
                  setBulkInput('');
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {!bulkPreview ? (
              <>
                <textarea
                  value={bulkInput}
                  onChange={(e) => setBulkInput(e.target.value)}
                  rows={5}
                  className="w-full px-3 py-2 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t.pretargeting.bulkImportTextareaPlaceholder}
                />
                <div className="flex justify-end gap-2 mt-3">
                  <button
                    onClick={() => {
                      setShowBulkImport(false);
                      setBulkInput('');
                    }}
                    className="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
                  >
                    {t.common.cancel}
                  </button>
                  <button
                    onClick={parseBulkInput}
                    disabled={!bulkInput.trim()}
                    className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {t.pretargeting.previewImport}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="text-xs text-gray-600 space-y-2">
                  <div>
                    <span className="font-medium text-green-700">{t.pretargeting.bulkValidLabel}:</span>{' '}
                    {bulkPreview.valid.length}
                  </div>
                  {bulkPreview.valid.length > 0 && (
                    <div className="text-gray-500">
                      {bulkPreview.valid.join(', ')}
                    </div>
                  )}
                  {bulkPreview.duplicates.length > 0 && (
                    <div>
                      <span className="font-medium text-yellow-700">{t.pretargeting.bulkDuplicatesLabel}:</span>{' '}
                      {bulkPreview.duplicates.join(', ')}
                    </div>
                  )}
                  {bulkPreview.invalid.length > 0 && (
                    <div>
                      <span className="font-medium text-red-700">{t.pretargeting.bulkInvalidLabel}:</span>{' '}
                      {bulkPreview.invalid.join(', ')}
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-2 mt-3">
                  <button
                    onClick={() => setBulkPreview(null)}
                    className="px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
                  >
                    {t.common.back}
                  </button>
                  <button
                    onClick={handleBulkImport}
                    disabled={bulkPreview.valid.length === 0}
                    className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {t.pretargeting.importPublishersCount.replace('{count}', String(bulkPreview.valid.length))}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// History entry component
function HistoryEntry({ entry }: { entry: PretargetingHistoryItem }) {
  const { t, language } = useTranslation();
  const commitChanges = entry.commit_context?.changes || [];
  return (
    <div className="flex items-start gap-3 py-2 border-b last:border-0">
      <Clock className="h-4 w-4 text-gray-400 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-gray-900">{formatHistoryChangeTypeLabel(entry.change_type, t)}</span>
          {entry.field_changed && (
            <span className="text-gray-500">
              {t.pretargeting.historyOnField.replace('{field}', formatHistoryFieldLabel(entry.field_changed, t))}
            </span>
          )}
        </div>
        {entry.new_value && (
          <p className="text-xs text-gray-600 mt-0.5 truncate">{entry.new_value}</p>
        )}
        {commitChanges.length > 0 && (
          <div className="mt-1 max-h-24 overflow-y-auto rounded bg-gray-50 p-2">
            {commitChanges.map((change, index) => (
              <div key={`${entry.id}-${change.change_id || index}`} className="text-xs text-gray-600">
                • {formatCodeLabel(String(change.change_type || 'change'))}: {String(change.value || '')}
              </div>
            ))}
          </div>
        )}
        <p className="text-xs text-gray-400 mt-1">
          {formatDate(entry.changed_at, language)} {t.pretargeting.historyMetaSeparator} {formatHistorySourceLabel(entry.change_source, t)}
        </p>
      </div>
    </div>
  );
}

export function PretargetingSettingsEditor({
  billing_id,
  configName,
  onClose,
  initialTab = 'settings',
  hideTabs = false,
}: PretargetingSettingsEditorProps) {
  const { t, language } = useTranslation();
  const [showHistory, setShowHistory] = useState(false);
  const [historyView, setHistoryView] = useState<'audit' | 'snapshots'>('audit');
  const [activeTab, setActiveTab] = useState<'publishers' | 'settings'>(initialTab);
  const [rollbackPreview, setRollbackPreview] = useState<{
    snapshot: PretargetingSnapshot;
    changes: string[];
  } | null>(null);
  const [showCommitToast, setShowCommitToast] = useState(false);
  const [showConfirmSuspend, setShowConfirmSuspend] = useState(false);
  const [pushResult, setPushResult] = useState<{ success: boolean; message: string } | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  // Fetch config detail
  const { data: configDetail, isLoading: configLoading, refetch: refetchDetail } = useQuery({
    queryKey: ['pretargeting-detail', billing_id],
    queryFn: () => getPretargetingConfigDetail(billing_id),
    staleTime: 30_000,
  });

  // Fetch publishers from dedicated endpoint
  const { data: publishersData, refetch: refetchPublishers } = useQuery({
    queryKey: ['pretargeting-publishers', billing_id],
    queryFn: () => getPretargetingPublishers(billing_id),
    staleTime: 30_000,
  });

  // Fetch history
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['pretargeting-history', billing_id],
    queryFn: () => getPretargetingHistory({ billing_id, days: 90 }),
    enabled: showHistory && historyView === 'audit',
    staleTime: 30_000,
  });

  const { data: snapshots, isLoading: snapshotsLoading } = useQuery({
    queryKey: ['pretargeting-snapshots', billing_id],
    queryFn: () => getSnapshots({ billing_id, limit: 50 }),
    enabled: showHistory && historyView === 'snapshots',
    staleTime: 30_000,
  });

  // Mutations
  const createChangeMutation = useMutation({
    mutationFn: createPendingChange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
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

  // Publisher mutations
  const addPublisherMutation = useMutation({
    mutationFn: ({ publisherId, mode }: { publisherId: string; mode: "BLACKLIST" | "WHITELIST" }) =>
      addPretargetingPublisher(billing_id, publisherId, mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const removePublisherMutation = useMutation({
    mutationFn: (publisherId: string) => removePretargetingPublisher(billing_id, publisherId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  // Push to Google mutations
  const applyAllMutation = useMutation({
    mutationFn: () => applyAllPendingChanges(billing_id, false),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      // Sync to get updated state from Google
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
      setShowCommitToast(false);
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const discardAllMutation = useMutation({
    mutationFn: () => discardAllPretargetingChanges(billing_id),
    onSuccess: (data) => {
      setPushResult({ success: true, message: data.message });
      setShowCommitToast(false);
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-publishers', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: (snapshotId: number) =>
      rollbackSnapshot({ billing_id, snapshot_id: snapshotId, dry_run: false }),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      setRollbackPreview(null);
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-history', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-snapshots', billing_id] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const suspendMutation = useMutation({
    mutationFn: () => suspendPretargeting(billing_id),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      setShowConfirmSuspend(false);
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const activateMutation = useMutation({
    mutationFn: () => activatePretargeting(billing_id),
    onSuccess: async (data) => {
      setPushResult({ success: true, message: data.message });
      await syncPretargetingConfigs();
      queryClient.invalidateQueries({ queryKey: ['pretargeting-detail', billing_id] });
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
    },
    onError: (error: Error) => {
      setPushResult({ success: false, message: error.message });
    },
  });

  const isPushing =
    applyAllMutation.isPending ||
    discardAllMutation.isPending ||
    suspendMutation.isPending ||
    activateMutation.isPending;

  // Get pending changes by type
  const getPendingByType = (changeType: string): string[] => {
    if (!configDetail) return [];
    return configDetail.pending_changes
      .filter(c => c.change_type === changeType)
      .map(c => c.value);
  };

  const findPendingChange = (changeType: string, value: string) => {
    if (!configDetail) return undefined;
    return configDetail.pending_changes.find(
      c => c.change_type === changeType && c.value === value
    );
  };

  const pendingPublisherRowsCount = (publishersData?.publishers || []).filter(
    (publisher) => publisher.status === 'pending_add' || publisher.status === 'pending_remove'
  ).length;
  const activeMajorChangeType = resolveActiveMajorChangeType(
    configDetail?.pending_changes || [],
    pendingPublisherRowsCount > 0
  );

  const canStageChange = (nextChangeType: string): boolean => {
    const nextMajorType = getMajorChangeType(nextChangeType);
    if (activeMajorChangeType === null || activeMajorChangeType === nextMajorType) {
      return true;
    }
    if (activeMajorChangeType === 'mixed') {
      setPushResult({
        success: false,
        message:
          'Pending changes already mix major types. Commit or clear them before staging more changes.',
      });
      return false;
    }
    setPushResult({
      success: false,
      message: `Only one major change per commit is allowed (active=${activeMajorChangeType}, requested=${nextMajorType}).`,
    });
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

  const openCommitToast = () => {
    if (!hasPendingChanges) {
      return;
    }
    setShowCommitToast(true);
  };

  const handleAddSize = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'add_size',
      field_name: 'included_sizes',
      value,
    });
  };

  const handleRemoveSize = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'remove_size',
      field_name: 'included_sizes',
      value,
      reason: t.pretargeting.reasonBlockSizeReduceQpsWaste,
    });
  };

  const handleAddGeo = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'add_geo',
      field_name: 'included_geos',
      value,
    });
  };

  const handleRemoveGeo = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'remove_geo',
      field_name: 'included_geos',
      value,
    });
  };

  const handleAddFormat = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'add_format',
      field_name: 'included_formats',
      value,
    });
  };

  const handleRemoveFormat = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'remove_format',
      field_name: 'included_formats',
      value,
    });
  };

  const handleAddPublisher = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'add_publisher',
      field_name: 'publisher_targeting',
      value,
    });
  };

  const handleRemovePublisher = (value: string) => {
    stageChange({
      billing_id,
      change_type: 'remove_publisher',
      field_name: 'publisher_targeting',
      value,
    });
  };

  const handleSetPublisherMode = (mode: string) => {
    stageChange({
      billing_id,
      change_type: 'set_publisher_mode',
      field_name: 'publisher_targeting_mode',
      value: mode,
    });
  };

  const queuePublisherAdd = (publisherId: string) => {
    if (!canStageChange('add_publisher')) {
      return;
    }
    const mode = (configDetail?.publisher_targeting_mode || 'EXCLUSIVE') === 'INCLUSIVE'
      ? 'WHITELIST'
      : 'BLACKLIST';
    addPublisherMutation.mutate(
      { publisherId, mode: mode as "BLACKLIST" | "WHITELIST" },
      {
        onSuccess: () => {
          handleAddPublisher(publisherId);
        },
      }
    );
  };

  const queuePublisherRemove = (publisherId: string) => {
    if (!canStageChange('remove_publisher')) {
      return;
    }
    removePublisherMutation.mutate(publisherId, {
      onSuccess: () => {
        handleRemovePublisher(publisherId);
      },
    });
  };

  const undoPublisherPending = (publisherId: string) => {
    removePublisherMutation.mutate(publisherId, {
      onSuccess: () => {
        const pendingAdd = findPendingChange('add_publisher', publisherId);
        if (pendingAdd) {
          cancelChangeMutation.mutate(pendingAdd.id);
        }
        const pendingRemove = findPendingChange('remove_publisher', publisherId);
        if (pendingRemove) {
          cancelChangeMutation.mutate(pendingRemove.id);
        }
      },
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
        stageChange({
          billing_id,
          change_type: 'remove_size',
          field_name: 'included_sizes',
          value: size,
          reason: t.pretargeting.reasonBulkRemovalReduceQpsWaste,
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
        stageChange({
          billing_id,
          change_type: 'remove_size',
          field_name: 'included_sizes',
          value: size,
          reason: t.pretargeting.reasonBulkRemovalReduceQpsWaste,
        });
      }
    });
  };

  const handleExportPublishers = (values: string[]) => {
    const content = ['publisher_id', ...values].join('\n');
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `publisher-targeting-${billing_id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleRollbackPreview = async (snapshot: PretargetingSnapshot) => {
    try {
      const preview = await rollbackSnapshot({
        billing_id,
        snapshot_id: snapshot.id,
        dry_run: true,
      });
      setRollbackPreview({ snapshot, changes: preview.changes_made });
    } catch (error) {
      const message = error instanceof Error ? error.message : t.pretargeting.failedToPreviewRollback;
      setPushResult({ success: false, message });
    }
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
        <p>{t.pretargeting.failedToLoadConfigDetails}</p>
      </div>
    );
  }

  const pendingChanges = configDetail.pending_changes || [];
  const hasPendingChanges = pendingChanges.length > 0;
  const pendingModeChange = [...pendingChanges]
    .reverse()
    .find((change) => change.change_type === 'set_publisher_mode') || null;
  const publisherMode = configDetail.publisher_targeting_mode || null;

  const resolvedConfigName = configName
    || configDetail?.user_name
    || configDetail?.display_name
    || billing_id;
  const headerTitle = activeTab === 'publishers'
    ? t.pretargeting.publisherListHeader.replace('{name}', resolvedConfigName)
    : t.pretargeting.pretargetingSettingsTitle;

  return (
    <div className="border-t bg-white">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900">{headerTitle}</span>
          {hasPendingChanges && (
            <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs rounded-full">
              {t.pretargeting.changesPending}
              {pendingChanges.length ? ` (${pendingChanges.length})` : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeTab === 'publishers' && (
            <button
              onClick={async () => {
                await syncPretargetingConfigs();
                refetchDetail();
                refetchPublishers();
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
            >
              <RefreshCw className="h-3 w-3" />
              {t.pretargeting.syncFromGoogle}
            </button>
          )}
          <button
            onClick={() => {
              setHistoryView('audit');
              setShowHistory(!showHistory);
            }}
            className={cn(
              'flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors',
              showHistory ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            <History className="h-3 w-3" />
            {t.pretargeting.historyShort}
          </button>
          {onClose && (
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Tab selector */}
      {!hideTabs && (
        <div className="px-4 py-2 border-b bg-white flex items-center gap-2">
          <button
            onClick={() => setActiveTab('publishers')}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === 'publishers'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {t.pretargeting.publisherListTab}
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded transition-colors',
              activeTab === 'settings'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {t.pretargeting.configSettingsTab}
          </button>
        </div>
      )}

      {/* Result notification */}
      {pushResult && (
        <div className={cn(
          "px-4 py-2 border-b flex items-center justify-between",
          pushResult.success ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
        )}>
          <div className="flex items-center gap-2 text-sm">
            {pushResult.success ? (
              <Check className="h-4 w-4 text-green-600" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-600" />
            )}
            <span className={pushResult.success ? "text-green-800" : "text-red-800"}>
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

      {/* Status & Actions bar */}
      {activeTab === 'settings' && (
        <div className="px-4 py-2 bg-gray-50 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={cn(
              "px-2 py-0.5 text-xs font-medium rounded",
              configDetail.state === 'ACTIVE' ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"
            )}>
              {formatConfigStateLabel(configDetail.state, t)}
            </span>
            <span className="text-xs text-gray-500">
              {t.pretargeting.configLabel}: {configDetail.config_id}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {configDetail.state === 'ACTIVE' ? (
              <button
                onClick={() => setShowConfirmSuspend(true)}
                disabled={isPushing}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 disabled:opacity-50"
              >
                <Pause className="h-3 w-3" />
                {t.pretargeting.suspendAction}
              </button>
            ) : (
              <button
                onClick={() => activateMutation.mutate()}
                disabled={isPushing}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50"
              >
                {activateMutation.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                {t.pretargeting.activateAction}
              </button>
            )}
            <button
              onClick={() => refetchDetail()}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
              title={t.pretargeting.refreshFromGoogle}
            >
              <RefreshCw className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      {/* Confirmation dialogs */}

      {showConfirmSuspend && (
        <div className="px-4 py-3 bg-yellow-50 border-b border-yellow-200">
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

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Pending changes section (settings tab only) */}
        {activeTab === 'settings' && hasPendingChanges && (
          <div className="space-y-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium text-yellow-800 flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  {t.pretargeting.pendingChangesTitle.replace('{count}', String(pendingChanges.length))}
                </h4>
              <div className="flex items-center gap-2">
                <button
                  onClick={openCommitToast}
                  disabled={isPushing}
                  className="flex items-center gap-1 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 font-medium"
                >
                  <Upload className="h-3 w-3" />
                  {t.pretargeting.pushToGoogle}
                </button>
                <button
                  onClick={() => discardAllMutation.mutate()}
                  disabled={isPushing}
                  className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  {t.pretargeting.discardAll}
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
                  publisherMode={publisherMode}
                />
              ))}
            </div>
            <p className="text-xs text-yellow-700 mt-2">
              {t.pretargeting.clickPushToGoogleHint}
            </p>
          </div>
        )}

        {activeTab === 'publishers' ? (
          <PublisherTargetingSection
            baseMode={publisherMode}
            publishers={publishersData?.publishers || []}
            pendingModeChange={pendingModeChange}
            onAddPublisher={queuePublisherAdd}
            onRemovePublisher={queuePublisherRemove}
            onUndoPublisher={(publisherId) => {
              // For undo, we just re-fetch after removing from pending
              // The API DELETE endpoint handles both pending_add (removes row) and pending_remove (resets to active)
              undoPublisherPending(publisherId);
            }}
            onSetMode={handleSetPublisherMode}
            onShowHistory={() => {
              setHistoryView('snapshots');
              setShowHistory(true);
            }}
            onApplyPending={openCommitToast}
            onDiscardPending={() => discardAllMutation.mutate()}
            onBulkAdd={(values) => values.forEach((publisherId) => queuePublisherAdd(publisherId))}
            onExportCsv={handleExportPublishers}
            disabled={isPushing || addPublisherMutation.isPending || removePublisherMutation.isPending}
          />
        ) : (
          <>
            <TargetingSection
              title={t.pretargeting.adSizes}
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
              title={t.pretargeting.geographicTargeting}
              icon={Globe}
              values={configDetail.included_geos}
              pendingAdds={getPendingByType('add_geo')}
              pendingRemoves={getPendingByType('remove_geo')}
              onAddValue={handleAddGeo}
              onRemoveValue={handleRemoveGeo}
              fieldName="included_geos"
            />

            <TargetingSection
              title={t.pretargeting.formats}
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
                  <span className="font-medium text-gray-900">{t.pretargeting.excludedGeos}</span>
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
                {t.pretargeting.lastSyncedFromGoogle}: {formatDate(configDetail.synced_at, language)}
              </p>
            )}
          </>
        )}
      </div>

      {showCommitToast && hasPendingChanges && (
        <div className="fixed bottom-4 right-4 z-50 w-full max-w-md rounded-lg border border-blue-200 bg-white shadow-xl">
          <div className="border-b border-blue-100 bg-blue-50 px-3 py-2">
            <p className="text-sm font-medium text-blue-900">
              {t.pretargeting.pushPendingChangesToGoogleConfirm.replace('{count}', String(pendingChanges.length))}
            </p>
            <p className="mt-1 text-xs text-blue-700">{t.pretargeting.pushConfirmLiveChangeWarning}</p>
          </div>
          <div className="max-h-40 overflow-y-auto px-3 py-2">
            {pendingChanges.map((change) => (
              <div key={`toast-${change.id}`} className="text-xs text-gray-700">
                • {describePendingChange(change, publisherMode, t)}
              </div>
            ))}
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

      {/* History panel */}
      {showHistory && (
        <div className="border-t bg-gray-50 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <History className="h-4 w-4" />
              {t.pretargeting.historyShort}
            </h4>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setHistoryView('audit')}
                className={cn(
                  'px-2 py-1 text-xs rounded',
                  historyView === 'audit'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {t.admin.auditLog}
              </button>
              <button
                onClick={() => setHistoryView('snapshots')}
                className={cn(
                  'px-2 py-1 text-xs rounded',
                  historyView === 'snapshots'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {t.pretargeting.rollback}
              </button>
            </div>
          </div>

          {historyView === 'audit' && (
            <>
              {historyLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="h-12 bg-gray-200 rounded animate-pulse" />
                  ))}
                </div>
              ) : history && history.length > 0 ? (
                <div className="max-h-64 overflow-y-auto">
                  {history.map((entry) => (
                    <HistoryEntry key={entry.id} entry={entry} />
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 italic">{t.pretargeting.noHistoryAvailable}</p>
              )}
            </>
          )}

          {historyView === 'snapshots' && (
            <>
              {snapshotsLoading ? (
                <div className="space-y-2">
                  {[1, 2].map(i => (
                    <div key={i} className="h-16 bg-gray-200 rounded animate-pulse" />
                  ))}
                </div>
              ) : snapshots && snapshots.length > 0 ? (
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {snapshots.map((snapshot) => (
                    <div key={snapshot.id} className="border rounded-lg p-3 bg-white">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {snapshot.snapshot_name || t.pretargeting.snapshotLabel}
                          </p>
                          <p className="text-xs text-gray-500">
                            {formatSnapshotTypeLabel(snapshot.snapshot_type, t)} • {formatDate(snapshot.created_at, language)}
                          </p>
                        </div>
                        <button
                          onClick={() => handleRollbackPreview(snapshot)}
                          className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                        >
                          {t.pretargeting.rollback}
                        </button>
                      </div>
                      {snapshot.notes && (
                        <p className="text-xs text-gray-500 mt-2">{snapshot.notes}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 italic">{t.pretargeting.noSnapshotsAvailable}</p>
              )}
            </>
          )}

          {rollbackPreview && (
            <div className="mt-4 border rounded-lg p-3 bg-yellow-50 border-yellow-200">
              <p className="text-sm font-medium text-yellow-900">
                {t.pretargeting.rollbackToSnapshotPrompt.replace('{snapshot}', rollbackPreview.snapshot.snapshot_name || t.pretargeting.snapshotLabel.toLowerCase())}
              </p>
              <ul className="text-xs text-yellow-800 mt-2 space-y-1">
                {rollbackPreview.changes.map((change) => (
                  <li key={change}>• {change}</li>
                ))}
              </ul>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => rollbackMutation.mutate(rollbackPreview.snapshot.id)}
                  disabled={rollbackMutation.isPending}
                  className="px-3 py-1.5 bg-yellow-600 text-white text-xs rounded hover:bg-yellow-700 disabled:opacity-50"
                >
                  {rollbackMutation.isPending ? t.pretargeting.rollingBack : t.pretargeting.rollbackNow}
                </button>
                <button
                  onClick={() => setRollbackPreview(null)}
                  className="px-3 py-1.5 bg-white text-gray-700 text-xs rounded border hover:bg-gray-50"
                >
                  {t.common.cancel}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
