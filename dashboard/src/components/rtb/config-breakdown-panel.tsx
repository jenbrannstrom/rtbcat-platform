'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getConfigBreakdown, type ConfigBreakdownType, type ConfigBreakdownItem } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, Check, AlertTriangle, ChevronRight, Info } from 'lucide-react';
import { AppDrilldownModal } from './app-drilldown-modal';
import { useAccount } from '@/contexts/account-context';

interface ConfigBreakdownPanelProps {
  billing_id: string;
  isExpanded: boolean;
}

const TABS: { id: ConfigBreakdownType; label: string }[] = [
  { id: 'size', label: 'By Size' },
  { id: 'geo', label: 'By Geo' },
  { id: 'publisher', label: 'By Publisher' },
  { id: 'creative', label: 'By Creative' },
];

// Format large numbers with K/M suffix
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

// Minimum impressions threshold for showing waste warnings
// Below this, there's insufficient data to make confident assessments
// Inspired by Facebook's 1000 impression learning phase
const MIN_IMPRESSIONS_FOR_WARNING = 1000;

// Get status based on win/waste rates with smart minimum threshold
function getStatus(item: ConfigBreakdownItem): 'great' | 'ok' | 'warning' | 'critical' | 'insufficient_data' {
  // If we don't have enough impressions, don't show warning/critical status
  // This prevents alarming users over small sample sizes
  const hasEnoughData = item.impressions >= MIN_IMPRESSIONS_FOR_WARNING;

  if (!hasEnoughData) {
    // With insufficient data, only show 'great' if win_rate is excellent
    // Otherwise show neutral 'insufficient_data' status
    if (item.win_rate >= 40) return 'great';
    return 'insufficient_data';
  }

  // With sufficient data, apply normal thresholds
  if (item.waste_rate >= 90) return 'critical';
  if (item.waste_rate >= 70) return 'warning';
  if (item.win_rate >= 40) return 'great';
  return 'ok';
}

// Status indicator tooltips
const STATUS_TOOLTIPS: Record<'great' | 'ok' | 'warning' | 'critical' | 'insufficient_data', string> = {
  great: 'Excellent performance: Win rate ≥40%, low waste. Keep this targeting.',
  ok: 'Acceptable performance: Room for optimization but not urgent.',
  warning: 'Needs attention: Waste rate 70-90%. Consider adjusting targeting or excluding.',
  critical: 'Critical waste: ≥90% of bid requests not winning. Strongly recommend excluding or fixing targeting.',
  insufficient_data: `Insufficient data: Need ${MIN_IMPRESSIONS_FOR_WARNING.toLocaleString()}+ impressions to assess performance reliably.`,
};

// Status indicator component with tooltip
function StatusIndicator({ status }: { status: 'great' | 'ok' | 'warning' | 'critical' | 'insufficient_data' }) {
  const [showTooltip, setShowTooltip] = useState(false);

  const icon = (() => {
    switch (status) {
      case 'great':
        return <Check className="h-4 w-4 text-green-500" />;
      case 'ok':
        return <div className="h-4 w-4 rounded-full border-2 border-gray-300" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />;
      case 'critical':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'insufficient_data':
        return <div className="h-4 w-4 rounded-full border-2 border-dashed border-gray-300" title="Insufficient data" />;
    }
  })();

  return (
    <div
      className="relative cursor-help"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {icon}
      {showTooltip && (
        <div className="absolute z-50 left-6 top-1/2 -translate-y-1/2 w-56 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg whitespace-normal">
          {STATUS_TOOLTIPS[status]}
          <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-gray-900" />
        </div>
      )}
    </div>
  );
}

// Info tooltip for table header explanations
function HeaderInfoTooltip({ text }: { text: string }) {
  const [showTooltip, setShowTooltip] = useState(false);
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Info className="h-3 w-3 text-gray-400 hover:text-gray-600 cursor-help" />
      {showTooltip && (
        <div className="absolute z-50 left-0 top-full mt-1 w-56 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg whitespace-normal">
          {text}
          <div className="absolute bottom-full left-2 border-4 border-transparent border-b-gray-900" />
        </div>
      )}
    </span>
  );
}

// Waste bar component
function WasteBar({ pct }: { pct: number }) {
  return (
    <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
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

export function ConfigBreakdownPanel({ billing_id, isExpanded }: ConfigBreakdownPanelProps) {
  const [activeTab, setActiveTab] = useState<ConfigBreakdownType>('size');
  const contentRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [selectedApp, setSelectedApp] = useState<string | null>(null);
  const { selectedBuyerId } = useAccount();

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab],
    queryFn: () => getConfigBreakdown(billing_id, activeTab, selectedBuyerId || undefined),
    enabled: isExpanded,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Animate height changes
  useEffect(() => {
    if (contentRef.current) {
      setHeight(isExpanded ? contentRef.current.scrollHeight : 0);
    }
  }, [isExpanded, data, activeTab]);

  // Sort breakdown by reached descending
  const sortedBreakdown = data?.breakdown
    ? [...data.breakdown].sort((a, b) => b.reached - a.reached)
    : [];

  return (
    <div
      className="overflow-hidden transition-all duration-300 ease-in-out"
      style={{ height: isExpanded ? height : 0 }}
    >
      <div ref={contentRef} className="border-t bg-gray-50/50 px-4 py-3">
        {/* Tabs */}
        <div className="flex gap-1 mb-3">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                activeTab === tab.id
                  ? 'bg-white text-gray-900 shadow-sm border'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {isLoading && (
          <div className="flex items-center justify-center py-8 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            <span className="text-sm">Loading breakdown...</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
            Failed to load breakdown data
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length === 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-gray-700 mb-1">
                  No {activeTab} data for this config
                </p>
                <p className="text-gray-500 text-xs">
                  {data?.no_data_reason ||
                    `To see ${activeTab} breakdown, import both catscan-quality (has billing_id) and catscan-bidsinauction (has ${activeTab === 'geo' ? 'country' : activeTab}) CSV reports.`}
                </p>
              </div>
            </div>
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length > 0 && (
          <>
            {/* Creative tab info note explaining the metric */}
            {activeTab === 'creative' && (
              <div className="mb-3 flex items-center gap-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <Info className="h-4 w-4 text-blue-500 flex-shrink-0" />
                <span>
                  Win rate shows reached-to-impression conversion for this config.
                  This measures how efficiently bid requests convert to impressions.
                </span>
              </div>
            )}
            <div className="bg-white rounded-lg border overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-14 gap-2 px-3 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500">
              <div className="col-span-1 flex items-center">
                <HeaderInfoTooltip text={`Warning/critical status only shown after ${MIN_IMPRESSIONS_FOR_WARNING.toLocaleString()}+ impressions for reliable assessment.`} />
              </div>
              <div className="col-span-3">Name</div>
              <div className="col-span-2 text-right">Reached</div>
              <div className="col-span-2 text-right">Imp</div>
              <div className="col-span-2 text-right">Win Rate</div>
              <div className="col-span-2 text-right">Waste</div>
              <div className="col-span-2"></div>
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {sortedBreakdown.map((item, index) => {
                const status = getStatus(item);
                const isClickable = activeTab === 'publisher';
                return (
                  <div
                    key={`${item.name}-${index}`}
                    onClick={() => isClickable && setSelectedApp(item.name)}
                    className={cn(
                      'grid grid-cols-14 gap-2 px-3 py-2 text-sm items-center',
                      'hover:bg-gray-50 transition-colors',
                      status === 'critical' && 'bg-red-50/50',
                      status === 'warning' && 'bg-orange-50/30',
                      isClickable && 'cursor-pointer hover:bg-blue-50'
                    )}
                  >
                    <div className="col-span-1">
                      <StatusIndicator status={status} />
                    </div>
                    <div className="col-span-3 font-medium text-gray-900 truncate flex items-center gap-1" title={item.name}>
                      {item.name}
                      {isClickable && (
                        <ChevronRight className="h-3 w-3 text-gray-400 flex-shrink-0" />
                      )}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatNumber(item.reached)}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatNumber(item.impressions || 0)}
                    </div>
                    <div
                      className={cn(
                        'col-span-2 text-right font-medium',
                        item.win_rate >= 40 && 'text-green-600',
                        item.win_rate >= 20 && item.win_rate < 40 && 'text-yellow-600',
                        item.win_rate < 20 && 'text-red-600'
                      )}
                    >
                      {item.win_rate.toFixed(1)}%
                    </div>
                    <div
                      className={cn(
                        'col-span-2 text-right',
                        status === 'insufficient_data' && 'text-gray-400',
                        status !== 'insufficient_data' && item.waste_rate < 50 && 'text-gray-500',
                        status !== 'insufficient_data' && item.waste_rate >= 50 && item.waste_rate < 70 && 'text-yellow-600',
                        status !== 'insufficient_data' && item.waste_rate >= 70 && item.waste_rate < 90 && 'text-orange-600',
                        status !== 'insufficient_data' && item.waste_rate >= 90 && 'text-red-600 font-medium'
                      )}
                    >
                      {item.waste_rate.toFixed(1)}%
                    </div>
                    <div className="col-span-2 flex justify-end">
                      <WasteBar pct={item.waste_rate} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          </>
        )}

        {/* Drill-down modal */}
        {selectedApp && (
          <AppDrilldownModal
            appName={selectedApp}
            billingId={billing_id}
            onClose={() => setSelectedApp(null)}
          />
        )}
      </div>
    </div>
  );
}
