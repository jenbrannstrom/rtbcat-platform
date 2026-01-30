'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { setPretargetingName, lookupGeoNames } from '@/lib/api';
import { ChevronRight, Pencil, Check, X, AlertTriangle, AlertCircle, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SnapshotComparisonPanel } from './snapshot-comparison-panel';
import { PretargetingSettingsEditor } from './pretargeting-settings-editor';

export interface PretargetingConfig {
  billing_id: string;
  name: string;              // resolved: user_name || display_name || 'Config {id}'
  display_name: string | null;
  user_name: string | null;
  state: 'ACTIVE' | 'SUSPENDED';
  formats: string[];         // ['HTML', 'VAST']
  platforms: string[];       // ['PHONE', 'TABLET']
  sizes: string[];           // ['300x250', '320x50']
  included_geos: string[];   // country codes
  reached: number;
  impressions: number;
  win_rate: number;
  waste_rate: number;
  has_performance: boolean;
}

interface PretargetingConfigCardProps {
  config: PretargetingConfig;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

// Format large numbers
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

// Geo display component that fetches names from the database
function GeoSettingPill({ geoIds, max = 5 }: { geoIds: string[]; max?: number }) {
  const { data: geoNames } = useQuery({
    queryKey: ['geo-names', geoIds.join(',')],
    queryFn: () => lookupGeoNames(geoIds),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    enabled: geoIds.length > 0,
  });

  if (!geoIds?.length) return null;

  const displayIds = geoIds.slice(0, max);
  const remaining = geoIds.length - max;

  // Format display names - use looked up name or fall back to ID
  const displayNames = displayIds.map(id => {
    if (geoNames?.[id]) return geoNames[id];
    // If it's already a 2 or 3 letter code, return as-is
    if (/^[A-Z]{2,3}$/i.test(id)) return id.toUpperCase();
    return id;
  });

  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-xs text-gray-600">
      <span className="text-gray-400">Geos:</span>
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

export function PretargetingConfigCard({ config, isExpanded, onToggleExpand }: PretargetingConfigCardProps) {
  // Support both controlled and uncontrolled expansion
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = isExpanded !== undefined ? isExpanded : internalExpanded;
  const handleToggle = onToggleExpand || (() => setInternalExpanded(!internalExpanded));
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(config.name);
  const [showSettingsEditor, setShowSettingsEditor] = useState(false);
  const [editorTab, setEditorTab] = useState<'publishers' | 'settings'>('settings');
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const nameMutation = useMutation({
    mutationFn: ({ billingId, userName }: { billingId: string; userName: string }) =>
      setPretargetingName(billingId, userName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pretargeting-configs'] });
      setIsEditing(false);
    },
  });

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

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

  // Determine status indicator
  const isHighWaste = config.has_performance && config.waste_rate >= 70;
  const isCriticalWaste = config.has_performance && config.waste_rate >= 90;
  const isGoodWinRate = config.has_performance && config.win_rate >= 50;

  // Check if using display_name from Google (not user-defined)
  const isGoogleName = !config.user_name && config.display_name;

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
            'h-4 w-4 text-gray-400 transition-transform shrink-0',
            expanded && 'rotate-90'
          )}
        />

        {/* Status indicator */}
        <div className="shrink-0">
          {isCriticalWaste && <AlertCircle className="h-4 w-4 text-red-500" />}
          {isHighWaste && !isCriticalWaste && <AlertTriangle className="h-4 w-4 text-orange-500" />}
          {!isGoodWinRate && !isHighWaste && <div className="w-4" />}
        </div>

        {/* Billing ID */}
        <span className="font-mono text-xs text-gray-400 w-24 shrink-0">
          {config.billing_id}
        </span>

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
              {isGoogleName && (
                <span className="text-xs text-gray-400">(from Google)</span>
              )}
              <button
                onClick={handleStartEdit}
                className="p-1 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-600 transition-opacity"
              >
                <Pencil className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* State badge */}
        {config.state === 'SUSPENDED' && (
          <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
            Paused
          </span>
        )}

        {/* Metrics summary */}
        <div className="flex items-center gap-4 text-xs shrink-0">
          <span className="text-gray-600 w-16 text-right">
            {formatNumber(config.reached)}
          </span>
          {config.has_performance ? (
            <>
              <span
                className={cn(
                  'w-14 text-right font-medium',
                  config.win_rate >= 50 && 'text-green-600',
                  config.win_rate >= 30 && config.win_rate < 50 && 'text-yellow-600',
                  config.win_rate < 30 && 'text-red-600'
                )}
              >
                {config.win_rate.toFixed(1)}% win
              </span>
              <span
                className={cn(
                  'w-14 text-right',
                  config.waste_rate < 50 && 'text-gray-500',
                  config.waste_rate >= 50 && config.waste_rate < 70 && 'text-yellow-600',
                  config.waste_rate >= 70 && config.waste_rate < 90 && 'text-orange-600',
                  config.waste_rate >= 90 && 'text-red-600 font-medium'
                )}
              >
                {config.waste_rate.toFixed(1)}%
              </span>
              <WasteMiniBar pct={config.waste_rate} />
            </>
          ) : (
            <>
              <span className="w-14 text-right text-gray-400">--</span>
              <span className="w-14 text-right text-gray-400">No data</span>
              <div className="w-16 h-1.5 bg-gray-200 rounded-full" />
            </>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t bg-gray-50/50">
          {/* Settings pills with entry buttons */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex flex-wrap gap-2">
              <GeoSettingPill geoIds={config.included_geos} max={5} />
              <SettingPill label="Formats" values={config.formats} />
              <SettingPill label="Platforms" values={config.platforms} />
              <SettingPill label="Sizes" values={config.sizes} max={4} />
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditorTab('publishers');
                  setShowSettingsEditor(true);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors bg-blue-600 text-white hover:bg-blue-700"
              >
                Publisher List
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditorTab('settings');
                  setShowSettingsEditor(!showSettingsEditor);
                }}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors',
                  showSettingsEditor && editorTab === 'settings'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                <Settings className="h-3 w-3" />
                {showSettingsEditor && editorTab === 'settings' ? 'Hide Settings' : 'Config Settings'}
              </button>
            </div>
          </div>

          {/* Settings Editor */}
          {showSettingsEditor && (
            <div className="mb-4 -mx-4 border-y">
              <PretargetingSettingsEditor
                billing_id={config.billing_id}
                configName={config.name}
                initialTab={editorTab}
                onClose={() => setShowSettingsEditor(false)}
              />
            </div>
          )}

          {!showSettingsEditor && (
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-3 border">
                <div className="text-xs text-gray-500 mb-1">Reached</div>
                <div className="text-xl font-bold text-gray-900">
                  {formatNumber(config.reached)}
                </div>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="text-xs text-gray-500 mb-1">Impressions</div>
                <div className="text-xl font-bold text-gray-900">
                  {formatNumber(config.impressions)}
                </div>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="text-xs text-gray-500 mb-1">Win Rate</div>
                <div
                  className={cn(
                    'text-xl font-bold',
                    config.has_performance && config.win_rate >= 50 && 'text-green-600',
                    config.has_performance && config.win_rate >= 30 && config.win_rate < 50 && 'text-yellow-600',
                    config.has_performance && config.win_rate < 30 && 'text-red-600',
                    !config.has_performance && 'text-gray-400'
                  )}
                >
                  {config.has_performance ? `${config.win_rate.toFixed(1)}%` : '--'}
                </div>
              </div>
              <div className="bg-white rounded-lg p-3 border">
                <div className="text-xs text-gray-500 mb-1">Waste Rate</div>
                <div
                  className={cn(
                    'text-xl font-bold',
                    config.has_performance && config.waste_rate < 50 && 'text-gray-700',
                    config.has_performance && config.waste_rate >= 50 && config.waste_rate < 70 && 'text-yellow-600',
                    config.has_performance && config.waste_rate >= 70 && config.waste_rate < 90 && 'text-orange-600',
                    config.has_performance && config.waste_rate >= 90 && 'text-red-600',
                    !config.has_performance && 'text-gray-400'
                  )}
                >
                  {config.has_performance ? `${config.waste_rate.toFixed(1)}%` : '--'}
                </div>
              </div>
            </div>
          )}

          {/* A/B Comparison Panel */}
          <div className="mt-4">
            <SnapshotComparisonPanel
              billing_id={config.billing_id}
              configName={config.name}
            />
          </div>
        </div>
      )}
    </div>
  );
}
