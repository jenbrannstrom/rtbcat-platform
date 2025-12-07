'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getConfigBreakdown, type ConfigBreakdownType, type ConfigBreakdownItem } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, Check, AlertTriangle } from 'lucide-react';

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

// Get status based on win/waste rates
function getStatus(item: ConfigBreakdownItem): 'great' | 'ok' | 'warning' | 'critical' {
  if (item.waste_rate >= 90) return 'critical';
  if (item.waste_rate >= 70) return 'warning';
  if (item.win_rate >= 40) return 'great';
  return 'ok';
}

// Status indicator component
function StatusIndicator({ status }: { status: 'great' | 'ok' | 'warning' | 'critical' }) {
  switch (status) {
    case 'great':
      return <Check className="h-4 w-4 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-orange-500" />;
    case 'critical':
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    default:
      return <div className="w-4" />;
  }
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

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab],
    queryFn: () => getConfigBreakdown(billing_id, activeTab),
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
          <div className="text-center py-6 text-gray-400 text-sm">
            No data available for this breakdown
          </div>
        )}

        {!isLoading && !error && sortedBreakdown.length > 0 && (
          <div className="bg-white rounded-lg border overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-12 gap-2 px-3 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500">
              <div className="col-span-1"></div>
              <div className="col-span-4">Name</div>
              <div className="col-span-2 text-right">Reached</div>
              <div className="col-span-2 text-right">Win Rate</div>
              <div className="col-span-2 text-right">Waste</div>
              <div className="col-span-1"></div>
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {sortedBreakdown.map((item, index) => {
                const status = getStatus(item);
                return (
                  <div
                    key={`${item.name}-${index}`}
                    className={cn(
                      'grid grid-cols-12 gap-2 px-3 py-2 text-sm items-center',
                      'hover:bg-gray-50 transition-colors',
                      status === 'critical' && 'bg-red-50/50',
                      status === 'warning' && 'bg-orange-50/30'
                    )}
                  >
                    <div className="col-span-1">
                      <StatusIndicator status={status} />
                    </div>
                    <div className="col-span-4 font-medium text-gray-900 truncate" title={item.name}>
                      {item.name}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatNumber(item.reached)}
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
                        item.waste_rate < 50 && 'text-gray-500',
                        item.waste_rate >= 50 && item.waste_rate < 70 && 'text-yellow-600',
                        item.waste_rate >= 70 && item.waste_rate < 90 && 'text-orange-600',
                        item.waste_rate >= 90 && 'text-red-600 font-medium'
                      )}
                    >
                      {item.waste_rate.toFixed(1)}%
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <WasteBar pct={item.waste_rate} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
