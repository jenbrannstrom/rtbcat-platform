'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Pencil, Trash2, ArrowDown, ArrowUp, X, ChevronDown, Check } from 'lucide-react';
import { ListItem } from './list-item';
import { cn } from '@/lib/utils';

type SortField = 'spend' | 'impressions' | 'clicks' | 'country' | 'id' | 'date_added';

interface Creative {
  id: string;
  format: string;
  country?: string;
  created_at?: string;
  final_url?: string;
  video?: { thumbnail_url?: string };
  native?: { logo?: { url?: string }; image?: { url?: string } };
  html?: { thumbnail_url?: string };
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
    total_clicks?: number;
  };
}

interface ListClusterProps {
  id: string;
  name: string;
  creatives: Creative[];
  isUnclustered?: boolean;
  selectedIds?: Set<string>;
  onCreativeSelect?: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
  onRename?: (id: string, name: string) => void;
  onDelete?: (id: string) => void;
  onOpenPreview?: (id: string) => void;
  pageSortField?: 'spend' | 'impressions' | 'clicks' | 'creatives' | 'name';
}

function formatSpend(micros?: number): string {
  if (!micros) return '$0';
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

export function ListCluster({
  id,
  name,
  creatives,
  isUnclustered = false,
  selectedIds = new Set(),
  onCreativeSelect,
  onRename,
  onDelete,
  onOpenPreview,
  pageSortField,
}: ListClusterProps) {
  const { setNodeRef, isOver } = useDroppable({ id });
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(name);
  const [sortField, setSortField] = useState<SortField>('spend');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [excludedCountries, setExcludedCountries] = useState<Set<string>>(new Set());
  const [showSortDropdown, setShowSortDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const sortDropdownRef = useRef<HTMLDivElement>(null);

  // Update local name when prop changes
  useEffect(() => {
    setEditName(name);
  }, [name]);

  // Focus input when editing
  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(event.target as Node)) {
        setShowSortDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Extract unique countries with counts
  const countryBreakdown = useMemo(() => {
    const breakdown: Record<string, { count: number }> = {};
    creatives.forEach(c => {
      const country = c.country || 'Unknown';
      if (!breakdown[country]) {
        breakdown[country] = { count: 0 };
      }
      breakdown[country].count++;
    });
    return breakdown;
  }, [creatives]);

  const uniqueCountries = useMemo(() => {
    return Object.keys(countryBreakdown).sort();
  }, [countryBreakdown]);

  const toggleCountry = (country: string) => {
    setExcludedCountries(prev => {
      const next = new Set(prev);
      if (next.has(country)) {
        next.delete(country);
      } else {
        next.add(country);
      }
      return next;
    });
  };

  // Filter and sort creatives
  const sortedCreatives = useMemo(() => {
    // Apply country exclusion filter first
    let filtered = excludedCountries.size === 0
      ? creatives
      : creatives.filter(c => !excludedCountries.has(c.country || 'Unknown'));

    // Then sort
    const sorted = [...filtered].sort((a, b) => {
      if (sortField === 'country') {
        const aCountry = a.country || '';
        const bCountry = b.country || '';
        return sortDirection === 'desc'
          ? bCountry.localeCompare(aCountry)
          : aCountry.localeCompare(bCountry);
      }

      let aVal: number, bVal: number;

      switch (sortField) {
        case 'spend':
          aVal = a.performance?.total_spend_micros || 0;
          bVal = b.performance?.total_spend_micros || 0;
          break;
        case 'impressions':
          aVal = a.performance?.total_impressions || 0;
          bVal = b.performance?.total_impressions || 0;
          break;
        case 'clicks':
          aVal = a.performance?.total_clicks || 0;
          bVal = b.performance?.total_clicks || 0;
          break;
        case 'id':
          aVal = parseInt(String(a.id)) || 0;
          bVal = parseInt(String(b.id)) || 0;
          break;
        case 'date_added':
          aVal = a.created_at ? new Date(a.created_at).getTime() : 0;
          bVal = b.created_at ? new Date(b.created_at).getTime() : 0;
          break;
        default:
          return 0;
      }

      return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
    });
    return sorted;
  }, [creatives, sortField, sortDirection, excludedCountries]);

  // Calculate total spend
  const totalSpend = creatives.reduce(
    (sum, c) => sum + (c.performance?.total_spend_micros || 0),
    0
  );

  const handleSave = () => {
    if (editName.trim() && editName !== name && onRename) {
      onRename(id, editName.trim());
    } else {
      setEditName(name);
    }
    setIsEditing(false);
  };

  const sortOptions: { field: SortField; label: string }[] = [
    { field: 'spend', label: 'Spend' },
    { field: 'impressions', label: 'Impressions' },
    { field: 'clicks', label: 'Clicks' },
    { field: 'country', label: 'Country' },
    { field: 'date_added', label: 'Added' },
    { field: 'id', label: 'ID' },
  ];

  // Map page sort field to local sort field for ListItem
  const itemSortField = pageSortField === 'creatives' || pageSortField === 'name'
    ? sortField
    : (pageSortField as SortField | undefined) || sortField;

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "w-80 flex-shrink-0 rounded-lg border bg-white flex flex-col",
        isOver && "border-blue-500 bg-blue-50",
        isUnclustered && "bg-gray-50"
      )}
      style={{ maxHeight: '70vh' }}
    >
      {/* Header - sticky with proper z-index */}
      <div className="p-3 border-b bg-gray-50 rounded-t-lg flex-shrink-0 sticky top-0 z-10">
        {/* Title row */}
        <div className="flex items-center justify-between mb-1">
          {isEditing && !isUnclustered ? (
            <input
              ref={inputRef}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={handleSave}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSave();
                if (e.key === 'Escape') {
                  setEditName(name);
                  setIsEditing(false);
                }
              }}
              className="flex-1 font-medium border-b-2 border-blue-500 outline-none bg-transparent text-sm"
            />
          ) : (
            <div
              className={cn(
                "font-medium truncate flex-1",
                !isUnclustered && "cursor-pointer hover:text-blue-600 group flex items-center gap-1"
              )}
              onDoubleClick={() => !isUnclustered && setIsEditing(true)}
            >
              {name}
              {!isUnclustered && (
                <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-50 transition-opacity" />
              )}
            </div>
          )}

          {/* Delete button */}
          {!isUnclustered && onDelete && (
            <button
              onClick={() => onDelete(id)}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors"
              title="Delete campaign"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Stats row */}
        <div className="text-xs text-gray-500 flex items-center gap-2 mb-2">
          <span>
            {excludedCountries.size > 0
              ? `${sortedCreatives.length}/${creatives.length}`
              : creatives.length
            } creative{creatives.length !== 1 ? 's' : ''}
          </span>
          {totalSpend > 0 && (
            <>
              <span>·</span>
              <span className="text-green-600 font-medium">{formatSpend(totalSpend)}</span>
            </>
          )}
        </div>

        {/* Controls row */}
        <div className="flex items-center gap-2">
          {/* Sort dropdown */}
          <div className="relative" ref={sortDropdownRef}>
            <button
              onClick={() => setShowSortDropdown(!showSortDropdown)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-white border rounded hover:bg-gray-50 transition-colors"
            >
              {sortDirection === 'desc' ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />}
              <span>{sortOptions.find(o => o.field === sortField)?.label}</span>
              <ChevronDown className="h-3 w-3" />
            </button>

            {showSortDropdown && (
              <div className="absolute z-50 mt-1 left-0 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]">
                {sortOptions.map(option => (
                  <button
                    key={option.field}
                    onClick={() => {
                      if (sortField === option.field) {
                        setSortDirection(d => d === 'desc' ? 'asc' : 'desc');
                      } else {
                        setSortField(option.field);
                        setSortDirection('desc');
                      }
                      setShowSortDropdown(false);
                    }}
                    className={cn(
                      "w-full px-3 py-1.5 text-left text-xs hover:bg-gray-100 flex items-center justify-between",
                      sortField === option.field && "bg-blue-50 text-blue-700"
                    )}
                  >
                    <span>{option.label}</span>
                    {sortField === option.field && (
                      sortDirection === 'desc' ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Country tags */}
        {uniqueCountries.length > 1 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {uniqueCountries.map(country => {
              const isIncluded = !excludedCountries.has(country);
              const data = countryBreakdown[country];

              return (
                <button
                  key={country}
                  onClick={() => toggleCountry(country)}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full transition-colors",
                    isIncluded
                      ? "bg-blue-100 text-blue-700 hover:bg-blue-200"
                      : "bg-gray-100 text-gray-400 line-through hover:bg-gray-200"
                  )}
                >
                  {isIncluded && <Check className="h-3 w-3" />}
                  <span>{country}</span>
                  <span className="text-[10px] opacity-70">({data?.count || 0})</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Scrollable list */}
      <div className="overflow-y-auto flex-1 p-2" style={{ maxHeight: 'calc(70vh - 100px)' }}>
        <SortableContext
          items={sortedCreatives.map(c => String(c.id))}
          strategy={verticalListSortingStrategy}
        >
          {sortedCreatives.map(creative => (
            <ListItem
              key={creative.id}
              creative={creative}
              clusterId={id}
              isSelected={selectedIds.has(String(creative.id))}
              onSelect={onCreativeSelect}
              onOpenPreview={onOpenPreview}
              sortField={itemSortField}
            />
          ))}
        </SortableContext>

        {sortedCreatives.length === 0 && (
          <div className="text-gray-400 text-sm py-8 text-center">
            {excludedCountries.size > 0
              ? 'No creatives match filter'
              : isUnclustered
                ? 'All creatives are clustered'
                : 'Drag creatives here'
            }
          </div>
        )}
      </div>
    </div>
  );
}
