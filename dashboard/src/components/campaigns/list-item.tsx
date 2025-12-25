'use client';

import { useRef, useEffect, useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { cn, getFormatLabel } from '@/lib/utils';

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

interface ListItemProps {
  creative: Creative;
  clusterId: string;
  isDragOverlay?: boolean;
  isSelected?: boolean;
  onSelect?: (id: string, event?: { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean }) => void;
  onOpenPreview?: (id: string) => void;
  sortField?: 'spend' | 'impressions' | 'clicks' | 'country' | 'id' | 'date_added';
}

function getThumbnail(creative: Creative): string | null {
  if (creative.format === 'VIDEO') {
    return creative.video?.thumbnail_url || `/thumbnails/${creative.id}.jpg`;
  }
  if (creative.format === 'NATIVE') {
    return creative.native?.logo?.url || creative.native?.image?.url || null;
  }
  if (creative.format === 'HTML') {
    return creative.html?.thumbnail_url || null;
  }
  return null;
}

function formatSpend(micros?: number): string {
  if (!micros) return '$0';
  const dollars = micros / 1_000_000;
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
  if (dollars >= 1) return `$${dollars.toFixed(0)}`;
  return `$${dollars.toFixed(2)}`;
}

function formatNumber(num?: number): string {
  if (!num) return '0';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toLocaleString();
}

function getHostname(url?: string): string {
  if (!url) return 'No URL';
  try {
    return new URL(url).hostname;
  } catch {
    return url.substring(0, 30);
  }
}

export function ListItem({
  creative,
  clusterId,
  isDragOverlay = false,
  isSelected = false,
  onSelect,
  onOpenPreview,
  sortField = 'spend',
}: ListItemProps) {
  const wasDraggingRef = useRef(false);
  const [isHovered, setIsHovered] = useState(false);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: String(creative.id),
    data: {
      clusterId,
      creative,
      type: 'creative',
    },
    disabled: isDragOverlay,
  });

  useEffect(() => {
    if (isDragging) {
      wasDraggingRef.current = true;
    }
  }, [isDragging]);

  const handleClick = (e: React.MouseEvent) => {
    if (wasDraggingRef.current) {
      wasDraggingRef.current = false;
      return;
    }

    // Ctrl/Cmd or Shift click = selection
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      onSelect?.(String(creative.id), {
        ctrlKey: e.ctrlKey,
        metaKey: e.metaKey,
        shiftKey: e.shiftKey,
      });
      return;
    }

    // Plain click = open preview modal
    onOpenPreview?.(String(creative.id));
  };

  const style = isDragOverlay ? undefined : {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const thumbnail = getThumbnail(creative);
  const perf = creative.performance;
  const spend = perf?.total_spend_micros || 0;
  const impressions = perf?.total_impressions || 0;
  const clicks = perf?.total_clicks || 0;
  const ctr = impressions > 0 ? (clicks / impressions) * 100 : 0;

  const showTooltip = isHovered && !isDragging && !isDragOverlay;

  return (
    <div
      className="relative"
      onMouseEnter={() => !isDragOverlay && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Hover Tooltip */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 min-w-[220px] bg-gray-900 text-white text-xs rounded-lg p-3 shadow-xl pointer-events-none">
          <div className="font-medium text-sm mb-2">#{creative.id}</div>

          <div className="space-y-1 text-gray-300">
            <div className="flex justify-between">
              <span>Spend:</span>
              <span className="text-white font-medium">{formatSpend(spend)}</span>
            </div>
            <div className="flex justify-between">
              <span>Impressions:</span>
              <span className="text-white">{impressions.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>Clicks:</span>
              <span className="text-white">{clicks.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span>CTR:</span>
              <span className="text-white">{ctr.toFixed(2)}%</span>
            </div>
          </div>

          {creative.final_url && (
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="text-gray-400 text-[10px] mb-0.5">Destination:</div>
              <div className="text-blue-300 truncate text-[11px]">{creative.final_url}</div>
            </div>
          )}

          {/* Arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-gray-900" />
        </div>
      )}

      {/* List item content */}
      <div
        ref={isDragOverlay ? undefined : setNodeRef}
        style={style}
        {...(isDragOverlay ? {} : attributes)}
        {...(isDragOverlay ? {} : listeners)}
        onClick={handleClick}
        className={cn(
          "p-2 mb-1 rounded border bg-white cursor-grab hover:bg-gray-50 transition-colors",
          isDragging && "opacity-40",
          isDragOverlay && "shadow-lg ring-2 ring-blue-500",
          isSelected && !isDragOverlay && "ring-2 ring-blue-500 bg-blue-50",
        )}
      >
        <div className="flex items-center gap-2">
          {/* Small thumbnail */}
          <div className="w-10 h-10 rounded bg-gray-100 flex-shrink-0 overflow-hidden">
            {thumbnail ? (
              <img
                src={thumbnail}
                alt=""
                className="w-full h-full object-cover"
                draggable={false}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400 text-[10px]">
                {getFormatLabel(creative.format)}
              </div>
            )}
          </div>

          {/* Text info */}
          <div className="min-w-0 flex-1">
            <div className="font-medium text-sm truncate">
              #{creative.id}
            </div>
            <div className="text-xs text-gray-500 truncate">
              {sortField === 'country' && creative.country
                ? creative.country
                : getHostname(creative.final_url)}
            </div>
          </div>

          {/* Metrics */}
          <div className="flex-shrink-0 text-right">
            {/* Always show spend */}
            <div className="text-sm font-medium text-green-600">
              {formatSpend(spend)}
            </div>
            {/* Show sorted metric if different from spend */}
            {sortField === 'impressions' && (
              <div className="text-xs text-gray-500">
                {formatNumber(impressions)} imp
              </div>
            )}
            {sortField === 'clicks' && (
              <div className="text-xs text-gray-500">
                {formatNumber(clicks)} clicks
              </div>
            )}
            {sortField === 'date_added' && creative.created_at && (
              <div className="text-xs text-gray-500">
                {new Date(creative.created_at).toLocaleDateString()}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
