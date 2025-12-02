'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { Pencil, Trash2, ArrowDown, ArrowUp, ZoomIn, ZoomOut } from 'lucide-react';
import { DraggableCreative } from './draggable-creative';
import { cn } from '@/lib/utils';

type SortField = 'spend' | 'impressions' | 'id';
type SortDirection = 'asc' | 'desc';

// Zoom levels for thumbnails
const ZOOM_LEVELS = [
  { size: 40, cols: 5 },
  { size: 56, cols: 4 },
  { size: 72, cols: 3 },
  { size: 96, cols: 3 },
];

interface Campaign {
  id: string;
  name: string;
  creative_ids: string[];
}

interface Creative {
  id: string;
  format: string;
  performance?: {
    total_spend_micros?: number;
    total_impressions?: number;
  };
  waste_flags?: {
    broken_video?: boolean;
    zero_engagement?: boolean;
  };
}

interface ClusterCardProps {
  campaign: Campaign;
  creatives: Creative[];
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
  selectedIds: Set<string>;
  onCreativeSelect: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
}

const MAX_VISIBLE = 16;  // Show max 16 creatives before "show more"

export function ClusterCard({ campaign, creatives, onRename, onDelete, selectedIds, onCreativeSelect }: ClusterCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(campaign.name);
  const [isExpanded, setIsExpanded] = useState(false);
  const [openPopupId, setOpenPopupId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('spend');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [zoomLevel, setZoomLevel] = useState(1); // Index into ZOOM_LEVELS
  const inputRef = useRef<HTMLInputElement>(null);

  const { setNodeRef, isOver } = useDroppable({
    id: campaign.id,
  });

  const handleTogglePopup = (creativeId: string | null) => {
    setOpenPopupId(creativeId);
  };

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  useEffect(() => {
    setName(campaign.name);
  }, [campaign.name]);

  const handleSave = () => {
    if (name.trim() && name !== campaign.name) {
      onRename(campaign.id, name.trim());
    } else {
      setName(campaign.name);
    }
    setIsEditing(false);
  };

  // Sort creatives based on current sort settings
  const sortedCreatives = useMemo(() => {
    const sorted = [...creatives].sort((a, b) => {
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
        case 'id':
          aVal = parseInt(String(a.id)) || 0;
          bVal = parseInt(String(b.id)) || 0;
          break;
        default:
          return 0;
      }

      return sortDirection === 'desc' ? bVal - aVal : aVal - bVal;
    });
    return sorted;
  }, [creatives, sortField, sortDirection]);

  const cycleSort = () => {
    if (sortField === 'spend' && sortDirection === 'desc') {
      setSortDirection('asc');
    } else if (sortField === 'spend' && sortDirection === 'asc') {
      setSortField('impressions');
      setSortDirection('desc');
    } else if (sortField === 'impressions' && sortDirection === 'desc') {
      setSortDirection('asc');
    } else if (sortField === 'impressions' && sortDirection === 'asc') {
      setSortField('id');
      setSortDirection('desc');
    } else if (sortField === 'id' && sortDirection === 'desc') {
      setSortDirection('asc');
    } else {
      setSortField('spend');
      setSortDirection('desc');
    }
  };

  const getSortLabel = () => {
    const fieldLabels: Record<SortField, string> = {
      spend: 'Spend',
      impressions: 'Imp',
      id: 'ID',
    };
    return fieldLabels[sortField];
  };

  const SortIcon = sortDirection === 'desc' ? ArrowDown : ArrowUp;
  const currentZoom = ZOOM_LEVELS[zoomLevel];

  // Calculate total spend
  const totalSpend = creatives.reduce(
    (sum, c) => sum + (c.performance?.total_spend_micros || 0),
    0
  );

  const formatTotalSpend = (micros: number): string => {
    const dollars = micros / 1_000_000;
    if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
    if (dollars >= 1) return `$${dollars.toFixed(0)}`;
    return `$${dollars.toFixed(2)}`;
  };

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "rounded-xl border-2 p-4 transition-colors",
        isOver ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
      )}
      style={{
        backgroundImage: `
          linear-gradient(to right, #f9fafb 1px, transparent 1px),
          linear-gradient(to bottom, #f9fafb 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        {isEditing ? (
          <input
            ref={inputRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave();
              if (e.key === 'Escape') {
                setName(campaign.name);
                setIsEditing(false);
              }
            }}
            className="text-lg font-semibold w-full border-b-2 border-blue-500 outline-none bg-transparent"
          />
        ) : (
          <h3
            className="text-lg font-semibold flex items-center gap-2 cursor-pointer hover:text-blue-600 group"
            onDoubleClick={() => setIsEditing(true)}
          >
            {campaign.name}
            <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity" />
          </h3>
        )}

        <div className="flex items-center gap-1">
          {/* Sort button */}
          <button
            onClick={cycleSort}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:bg-gray-200 rounded transition-colors"
            title={`Sort by ${getSortLabel()} ${sortDirection === 'desc' ? '↓' : '↑'}`}
          >
            <SortIcon className="h-3 w-3" />
            <span>{getSortLabel()}</span>
          </button>

          {/* Zoom controls */}
          <button
            onClick={() => setZoomLevel(Math.max(0, zoomLevel - 1))}
            disabled={zoomLevel === 0}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            onClick={() => setZoomLevel(Math.min(ZOOM_LEVELS.length - 1, zoomLevel + 1))}
            disabled={zoomLevel === ZOOM_LEVELS.length - 1}
            className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>

          {/* Delete button */}
          <button
            onClick={() => onDelete(campaign.id)}
            className="p-1 text-gray-400 hover:text-red-500 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Creative Grid */}
      <SortableContext items={sortedCreatives.map(c => String(c.id))} strategy={rectSortingStrategy}>
        <div
          className="grid gap-1 min-h-[60px]"
          style={{
            gridTemplateColumns: `repeat(${currentZoom.cols}, ${currentZoom.size}px)`,
            gridAutoRows: `${currentZoom.size}px`,
          }}
        >
          {(isExpanded ? sortedCreatives : sortedCreatives.slice(0, MAX_VISIBLE)).map((creative, index) => (
            <DraggableCreative
              key={creative.id}
              creative={creative}
              clusterId={campaign.id}
              isLarge={index === 0 && sortedCreatives.length > 1 && zoomLevel >= 1}
              isSelected={selectedIds.has(String(creative.id))}
              isPopupOpen={openPopupId === String(creative.id)}
              onSelect={onCreativeSelect}
              onTogglePopup={handleTogglePopup}
            />
          ))}
        </div>
      </SortableContext>

      {/* Show more/less button */}
      {sortedCreatives.length > MAX_VISIBLE && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="mt-2 text-sm text-blue-600 hover:text-blue-800"
        >
          {isExpanded
            ? 'Show less'
            : `Show ${sortedCreatives.length - MAX_VISIBLE} more`}
        </button>
      )}

      {/* Stats */}
      <div className="mt-2 text-sm text-gray-600 flex items-center gap-3">
        <span>{creatives.length} creative{creatives.length !== 1 ? 's' : ''}</span>
        {totalSpend > 0 && (
          <>
            <span>·</span>
            <span>{formatTotalSpend(totalSpend)}</span>
          </>
        )}
      </div>
    </div>
  );
}
