'use client';

import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getConfigBreakdown,
  getConfigCreatives,
  getCreative,
  type ConfigBreakdownType,
  type ConfigBreakdownItem,
  type ConfigCreativesItem,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { Loader2, AlertCircle, AlertTriangle, ArrowUpDown, ChevronRight, Info, Image } from 'lucide-react';
import { AppDrilldownModal } from './app-drilldown-modal';
import { useAccount } from '@/contexts/account-context';
import { PreviewModal } from '@/components/preview-modal';

interface ConfigBreakdownPanelProps {
  billing_id: string;
  isExpanded: boolean;
}

const TABS: { id: ConfigBreakdownType; label: string }[] = [
  { id: 'creative', label: 'By Creative' },
  { id: 'size', label: 'By Size' },
  { id: 'geo', label: 'By Geo' },
  { id: 'publisher', label: 'By Publisher' },
];

// Format large numbers with K/M suffix
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

function formatMoney(amount: number): string {
  if (!amount || amount <= 0) return "$0";
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  if (amount >= 100) return `$${amount.toFixed(0)}`;
  return `$${amount.toFixed(2)}`;
}

export function ConfigBreakdownPanel({ billing_id, isExpanded }: ConfigBreakdownPanelProps) {
  const [activeTab, setActiveTab] = useState<ConfigBreakdownType>('creative');
  const [sortKey, setSortKey] = useState<'name' | 'spend' | 'reached' | 'impressions' | 'win_rate'>('reached');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const contentRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [selectedApp, setSelectedApp] = useState<string | null>(null);
  const { selectedBuyerId } = useAccount();
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [sizeCreatives, setSizeCreatives] = useState<ConfigCreativesItem[]>([]);
  const [sizeCreativesMessage, setSizeCreativesMessage] = useState<string | null>(null);
  const [selectedCreative, setSelectedCreative] = useState<null | { id: string }>(null);
  const [isLoadingCreative, setIsLoadingCreative] = useState(false);
  const [fullCreative, setFullCreative] = useState<any | null>(null);

  // Query for breakdown data
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-breakdown', billing_id, activeTab, selectedBuyerId],
    queryFn: () => getConfigBreakdown(billing_id, activeTab, selectedBuyerId || undefined),
    enabled: isExpanded,
    staleTime: 30000, // Cache for 30 seconds
  });

  const { data: sizeCreativeData, isLoading: sizeCreativesLoading } = useQuery({
    queryKey: ['config-creatives', billing_id, selectedSize, selectedBuyerId],
    queryFn: () => getConfigCreatives(billing_id, selectedSize || undefined, selectedBuyerId || undefined),
    enabled: isExpanded && activeTab === 'size' && !!selectedSize,
    staleTime: 30000,
  });

  // Animate height changes
  useEffect(() => {
    if (contentRef.current) {
      setHeight(isExpanded ? contentRef.current.scrollHeight : 0);
    }
  }, [isExpanded, data, activeTab, selectedSize, sizeCreatives, sizeCreativesLoading, sizeCreativesMessage]);

  useEffect(() => {
    setSelectedSize(null);
    setSizeCreatives([]);
    setSortKey('reached');
    setSortDir('desc');
  }, [activeTab, billing_id]);

  useEffect(() => {
    if (sizeCreativeData?.creatives) {
      setSizeCreatives(sizeCreativeData.creatives);
    }
    setSizeCreativesMessage(sizeCreativeData?.message || null);
  }, [sizeCreativeData]);

  useEffect(() => {
    if (!selectedCreative) {
      setFullCreative(null);
      return;
    }
    setIsLoadingCreative(true);
    getCreative(selectedCreative.id)
      .then((creative) => setFullCreative(creative))
      .catch(() => setFullCreative(null))
      .finally(() => setIsLoadingCreative(false));
  }, [selectedCreative]);

  // Sort breakdown by reached descending
  const sortedBreakdown = data?.breakdown
    ? [...data.breakdown].sort((a, b) => {
        const dir = sortDir === 'asc' ? 1 : -1;
        const getValue = (item: ConfigBreakdownItem) => {
          switch (sortKey) {
            case 'name':
              return item.name?.toLowerCase() || '';
            case 'spend':
              return item.spend_usd ?? 0;
            case 'impressions':
              return item.impressions ?? 0;
            case 'win_rate':
              return item.win_rate ?? 0;
            case 'reached':
            default:
              return item.reached ?? 0;
          }
        };
        const aVal = getValue(a);
        const bVal = getValue(b);
        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return aVal.localeCompare(bVal) * dir;
        }
        return ((aVal as number) - (bVal as number)) * dir;
      })
    : [];

  const handleSort = (key: typeof sortKey) => {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDir('desc');
  };

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
            <div className={cn(
              "grid gap-2 px-3 py-2 border-b bg-gray-50 text-xs font-medium text-gray-500",
              activeTab === "creative" ? "grid-cols-14" : "grid-cols-12"
            )}>
              <button
                type="button"
                onClick={() => handleSort("name")}
                className={cn(
                  activeTab === "creative" ? "col-span-3" : "col-span-4",
                  "flex items-center gap-1 text-left",
                  sortKey === "name" && "text-gray-700"
                )}
              >
                Name
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("spend")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "spend" && "text-gray-700"
                )}
              >
                Spend
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("reached")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "reached" && "text-gray-700"
                )}
              >
                Reached
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("impressions")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "impressions" && "text-gray-700"
                )}
              >
                Imp
                <ArrowUpDown className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleSort("win_rate")}
                className={cn(
                  "col-span-2 flex items-center gap-1 justify-end",
                  sortKey === "win_rate" && "text-gray-700"
                )}
              >
                Win Rate
                <ArrowUpDown className="h-3 w-3" />
              </button>
              {activeTab === "creative" && (
                <>
                  <div className="col-span-2">Country Targeted</div>
                  <div className="col-span-1">Creative Lang</div>
                </>
              )}
            </div>

            {/* Table body */}
            <div className="divide-y divide-gray-100">
              {sortedBreakdown.map((item, index) => {
                const isClickable = activeTab === 'publisher';
                const winRate = item.win_rate ?? 0;
                const winRateClass =
                  winRate < 51 ? 'text-red-600' : winRate < 75 ? 'text-orange-600' : 'text-green-600';
                const nameColSpan = activeTab === 'creative' ? 'col-span-3' : 'col-span-4';
                return (
                  <div
                    key={`${item.name}-${index}`}
                    onClick={() => isClickable && setSelectedApp(item.name)}
                    className={cn(
                      'grid gap-2 px-3 py-2 text-sm items-center',
                      activeTab === 'creative' ? 'grid-cols-14' : 'grid-cols-12',
                      'hover:bg-gray-50 transition-colors',
                      isClickable && 'cursor-pointer hover:bg-blue-50'
                    )}
                  >
                    <div className={cn(nameColSpan, "font-medium text-gray-900 truncate flex items-center gap-1")} title={item.name}>
                      {item.name}
                      {activeTab === 'size' && (
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedSize((prev) => (prev === item.name ? null : item.name));
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600"
                          title="View creatives for this size"
                        >
                          <ChevronRight className="h-3 w-3" />
                        </button>
                      )}
                      {activeTab === 'creative' && (
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedCreative({ id: item.name });
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600"
                          title="View creative"
                        >
                          <Image className="h-3 w-3" />
                        </button>
                      )}
                      {isClickable && (
                        <ChevronRight className="h-3 w-3 text-gray-400 flex-shrink-0" />
                      )}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatMoney(item.spend_usd ?? 0)}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatNumber(item.reached)}
                    </div>
                    <div className="col-span-2 text-right text-gray-600 font-mono text-xs">
                      {formatNumber(item.impressions || 0)}
                    </div>
                    <div className={cn('col-span-2 text-right font-medium', winRateClass)}>
                      {winRate.toFixed(1)}%
                    </div>
                    {activeTab === 'creative' && (
                      <>
                        <div className="col-span-2 text-xs text-gray-600 truncate">
                          {(item.target_countries || []).join(", ") || "—"}
                        </div>
                        <div className="col-span-1 text-xs text-gray-600 flex items-center gap-1">
                          <span className="truncate">{item.creative_language || "—"}</span>
                          {item.language_mismatch && (
                            <AlertTriangle
                              className="h-3 w-3 text-orange-500"
                              title={`Language mismatch: ${item.mismatched_countries?.join(", ") || "check geo targets"}`}
                            />
                          )}
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
            {activeTab === 'size' && selectedSize && (
              <div className="mt-4 border rounded-lg bg-white">
                <div className="flex items-center justify-between px-3 py-2 border-b">
                  <div className="text-sm font-medium text-gray-900">
                    Creatives for {selectedSize}
                  </div>
                  <button
                    onClick={() => setSelectedSize(null)}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    Close
                  </button>
                </div>
                {sizeCreativesLoading && (
                  <div className="px-3 py-3 text-sm text-gray-500">Loading creatives...</div>
                )}
                {!sizeCreativesLoading && sizeCreatives.length === 0 && (
                  <div className="px-3 py-3 text-sm text-gray-400">
                    {sizeCreativesMessage || "No creatives found for this size."}
                  </div>
                )}
                {!sizeCreativesLoading && sizeCreatives.length > 0 && (
                  <div className="divide-y">
                    {sizeCreatives.map((creative) => (
                      <div key={creative.id} className="flex items-center justify-between px-3 py-2 text-sm">
                        <span className="font-mono text-gray-800 truncate">{creative.name}</span>
                        <button
                          onClick={() => setSelectedCreative({ id: creative.id })}
                          className="p-1 text-gray-400 hover:text-gray-600"
                          title="View creative"
                        >
                          <Image className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
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
        {fullCreative && selectedCreative && (
          <PreviewModal
            creative={fullCreative}
            onClose={() => setSelectedCreative(null)}
          />
        )}
      </div>
    </div>
  );
}
